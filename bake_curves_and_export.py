# -*- coding: utf-8 -*-
"""
bake_curves_and_export.py —— 把场景里的曲线物体并入烘焙管线，然后导出整场景 .glb

背景（这一步为什么必须做）
--------------------------
场景里除 668 个网格物体外，还有 **88 个 CURVE 物体**，携带 27,648 个三角面的
真实可见几何（铜环、钟冠眼、钟口缘、鎏金边框）。它们共用两个材质：
  * `Worn golden bronze.001`
  * `Hero bronze | layered oxidation`

两个后果：
 1. 只按网格物体统计/清理的流程会把这 88 个物件整体漏掉——包括它们共用的
    材质会被误判成「零引用孤儿」而被删掉，导出后这些零件在 glTF 里就没有材质。
 2. 曲线在 glTF 里会被转成网格，但程序化节点材质不会随行，导出即变成白模。

所以这里：曲线 → 网格 → 与网格物体同一套烘焙流程 → 再导出。
只用 EMIT 烘焙（确定性求值，无光照采样），不入库、不改动磁盘上的 .blend。

用法
----
    blender.exe -b "<baked>.blend" -P bake_curves_and_export.py -- \
        --dst "out/scene.glb" [--tex-dir "out/textures"] [--samples 1]
"""
import bpy
import os
import sys
import json
import time
import argparse
import hashlib
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import bake_materials as bm  # noqa: E402  （已加 __main__ 保护，可安全导入）
import blend_extract_parts as bx  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Bake curve-object materials and export the scene")
    p.add_argument("--dst", required=True, help="整场景 .glb 输出路径")
    p.add_argument("--tex-dir", dest="tex_dir", default=None, help="烘焙贴图输出目录")
    p.add_argument("--samples", type=int, default=1, help="EMIT 烘焙采样数")
    p.add_argument("--no-collapse", action="store_true", help="不做实例折叠（调试用）")
    return p.parse_args(argv)


def tris_of_data(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def geo_key(me, ndigits=5):
    """几何指纹：只按精确坐标 + 面顶点索引，用于「同形同材质」的实例折叠。"""
    n = len(me.vertices)
    buf = [0.0] * (n * 3)
    me.vertices.foreach_get("co", buf)
    ibuf = [0] * (len(me.polygons) * 3)
    try:
        me.polygons.foreach_get("vertices", ibuf)
    except Exception:
        ibuf = []
    h = hashlib.md5()
    h.update(repr([round(v, ndigits) for v in buf]).encode())
    h.update(repr(ibuf).encode())
    return h.hexdigest()


def main():
    t0 = time.time()
    args = parse_args()
    dst = os.path.abspath(args.dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tex_dir = os.path.abspath(args.tex_dir or os.path.join(os.path.dirname(dst), "textures"))
    os.makedirs(tex_dir, exist_ok=True)

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.cycles.device = "CPU"
        sc.cycles.samples = args.samples
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.render.bake.margin = 4
    sc.render.bake.use_selected_to_active = False

    stats = {}

    # ---- 0. 记录曲线物体的几何量（转换前） ---------------------------------
    conv_types = ("CURVE", "SURFACE", "FONT", "META")
    curve_objs = [o for o in bpy.data.objects if o.type in conv_types]
    before = {}
    for o in curve_objs:
        tot = 0
        try:
            me = o.to_mesh()
            if me:
                tot = tris_of_data(me)
                o.to_mesh_clear()
        except Exception:
            pass
        before[o.name] = tot
    stats["curve_objects"] = len(curve_objs)
    stats["curve_triangles_before"] = sum(before.values())

    # ---- 1. 曲线 → 网格 -----------------------------------------------------
    if curve_objs:
        bpy.ops.object.select_all(action="DESELECT")
        for o in curve_objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = curve_objs[0]
        bpy.ops.object.convert(target="MESH")
    converted = [o for o in bpy.data.objects if o.name in before]
    stats["curve_triangles_after"] = sum(
        tris_of_data(o.data) for o in converted if o.type == "MESH" and o.data)
    stats["convert_ok"] = all(o.type == "MESH" for o in converted)

    # ---- 2. 用管线同一套聚类分组，每组只烘焙一个代表 --------------------------
    # 容差聚类（而不是逐点精确哈希）能把近似同形的曲线零件并成一组：
    # 本场景 88 个曲线物件只落成 7 组，贴图从 176 张降到 14 张。
    # 已核对：这些组内材质一致（mixed_materials = 0），共用一套烘焙图是安全的。
    _sigs, curve_groups = bx.cluster(converted, 0.02, 0)
    stats["curve_shape_groups"] = len(curve_groups)

    bakes_ok = bakes_fail = mats_made = 0
    new_images = []
    for gi, g in enumerate(curve_groups):
        rep = g["representative"]
        ob_rep = rep["obj"]
        members = [g["representative"]] + list(g["members"])
        ob_members = [m["obj"] for m in members]
        tris = g["tris"]
        size = bm.res_for(tris)
        rep_name = bx.safe_name(rep["name"], 48)
        n_slots = max(1, len(ob_rep.data.materials))

        for si in range(n_slots):
            src_mat = ob_rep.data.materials[si] if si < len(ob_rep.data.materials) else None
            if src_mat is None or not getattr(src_mat, "node_tree", None):
                continue
            nt = src_mat.node_tree
            pr = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if pr is None:
                continue

            if len(ob_rep.data.uv_layers) == 0:
                bm.box_project_uv(ob_rep)

            tag = "CV_g%02d_s%d_%s" % (gi, si, rep_name)
            base = pr.inputs["Base Color"]
            rough = pr.inputs["Roughness"]
            metal = pr.inputs["Metallic"]

            al_img = bm.new_img("BC_" + tag, size, is_data=False)
            ok, err = bm.bake_socket(ob_rep, src_mat, base, al_img, args.samples)
            bakes_ok += 1 if ok else 0
            if not ok:
                bakes_fail += 1
                print("[curve-bake] albedo FAIL %s: %s" % (tag, err), flush=True)

            r_img = m_img = orm_img = None
            if rough.is_linked or metal.is_linked:
                if rough.is_linked:
                    r_img = bm.new_img("RG_" + tag, size, is_data=True)
                    ok, err = bm.bake_socket(ob_rep, src_mat, rough, r_img, args.samples)
                    bakes_ok += 1 if ok else 0
                    if not ok:
                        bakes_fail += 1
                        r_img = None
                if metal.is_linked:
                    m_img = bm.new_img("MT_" + tag, size, is_data=True)
                    ok, err = bm.bake_socket(ob_rep, src_mat, metal, m_img, args.samples)
                    bakes_ok += 1 if ok else 0
                    if not ok:
                        bakes_fail += 1
                        m_img = None
                orm_img = bm.combine_orm(
                    r_img, m_img, "ORM_" + tag,
                    rough.default_value if not rough.is_linked else 0.5,
                    metal.default_value if not metal.is_linked else 0.0,
                    size)
                bm.save_and_pack(orm_img, tex_dir, "ORM_" + tag + ".png")
                new_images.append("ORM_" + tag + ".png")
                for tmp in (r_img, m_img):
                    if tmp is not None:
                        bpy.data.images.remove(tmp)

            bm.save_and_pack(al_img, tex_dir, "BC_" + tag + ".png")
            new_images.append("BC_" + tag + ".png")

            exp = bm.build_export_mat(
                "BAKED_" + tag, al_img, orm_img,
                metal.default_value if not metal.is_linked else 0.0,
                rough.default_value if not rough.is_linked else 0.5)
            mats_made += 1

            # 代表 + 同组所有成员都换成烘焙材质
            for mo in ob_members:
                if si < len(mo.data.materials):
                    mo.data.materials[si] = exp

        if (gi + 1) % 5 == 0:
            print("[curve-bake] %d/%d groups" % (gi + 1, len(curve_groups)), flush=True)

    stats["bakes_ok"] = bakes_ok
    stats["bakes_fail"] = bakes_fail
    stats["curve_materials_made"] = mats_made
    stats["new_textures"] = new_images

    # ---- 3. 只删「真的没有任何物体在用」的材质 ------------------------------
    # 注意：必须遍历所有物体类型。只看 MESH 会漏掉曲线物体，把它们的材质
    # 误判成孤儿删掉——这正是本流程要修的那个坑。
    used = set()
    for o in bpy.data.objects:
        for s in o.material_slots:
            if s.material is not None:
                used.add(s.material)
    removed_materials = []
    for m in list(bpy.data.materials):
        if m not in used:
            removed_materials.append(m.name)
            m.use_fake_user = False
            bpy.data.materials.remove(m)
    stats["removed_unused_materials"] = removed_materials

    # ---- 4. 实例折叠（同几何同材质 → 共用一个网格数据块） ------------------
    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    collapse_groups = defaultdict(list)
    for o in mesh_objs:
        matkey = tuple(s.material.name if s.material else None for s in o.material_slots)
        collapse_groups[(geo_key(o.data), matkey)].append(o)

    collapsed = 0
    if not args.no_collapse:
        for key, objs in collapse_groups.items():
            rep_data = objs[0].data
            for o in objs[1:]:
                o.data = rep_data
                collapsed += 1
    stats["mesh_datablocks_before"] = len(bpy.data.meshes)
    kept = {o.data for o in mesh_objs}
    for me in list(bpy.data.meshes):
        if me not in kept:
            me.use_fake_user = False
    for _ in range(6):
        changed = False
        for coll in (bpy.data.meshes, bpy.data.images, bpy.data.materials, bpy.data.node_groups):
            for db in list(coll):
                if db.users == 0 and not db.use_fake_user:
                    coll.remove(db)
                    changed = True
        if not changed:
            break
    stats["mesh_datablocks_after"] = len(bpy.data.meshes)
    stats["objects_collapsed"] = collapsed
    stats["mesh_objects_total"] = len(mesh_objs)
    stats["total_triangles"] = sum(tris_of_data(o.data) for o in mesh_objs)
    stats["materials_at_export"] = len(bpy.data.materials)

    # ---- 5. 导出 -----------------------------------------------------------
    kwargs = dict(
        filepath=dst,
        export_format="GLB",
        use_selection=False,
        export_apply=False,          # 逐物体求值会破坏网格数据块共享
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_lights=False,
        export_cameras=True,
        export_extras=False,
        export_skins=False,
        export_animations=False,
        export_draco_mesh_compression_enable=False,
        export_shared_accessors=True,
    )
    rna = bpy.ops.export_scene.gltf.get_rna_type().properties
    bpy.ops.export_scene.gltf(**{k: v for k, v in kwargs.items() if k in rna})

    stats["glb_bytes"] = os.path.getsize(dst)
    stats["glb_mb"] = round(stats["glb_bytes"] / 1048576, 2)
    stats["seconds"] = round(time.time() - t0, 1)
    stats["dst"] = dst
    print("REPORT_JSON " + json.dumps(stats, ensure_ascii=False), flush=True)


main()
