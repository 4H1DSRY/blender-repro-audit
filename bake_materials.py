# -*- coding: utf-8 -*-
"""
bake_materials.py —— 把程序化材质烘焙成贴图，产出 glTF / Unreal 可用的 PBR 材质

为什么必须做
------------
本场景 22 个材质全部由节点程序化生成（噪波 / 波层 / 色彩斜坡），
glTF 是「贴图格式」不是「节点格式」——导出时整套计算过程会被丢弃，
结果就是 baseColorFactor=[1,1,1,1] 的白模，进 Unreal 只剩纯白或发黑。

做法
----
对每个「形状组代表 × 材质槽」：
  1. 把 Principled 的某个输入临时改接到 Emission，用 EMIT 烘焙把该通道「拍平」成图
     （EMIT 烘焙是直接求值，不需要采样光照，所以极快）
  2. Base Color  → albedo 图（sRGB）
     Roughness / Metallic → 合成一张 ORM 图（Non-Color，G=粗糙度, B=金属度，符合 glTF 规范）
  3. 用烘焙图新建一个「导出材质」，替换掉原材质
  4. 同组所有成员实例共用这套烘焙材质（同形同材质，无需重复烘焙）
  5. 另存为新 .blend（**绝不覆盖原文件**）

用法
----
    blender.exe -b "scene.blend" -P bake_materials.py -- \
        --save "out/scene_baked.blend" [--tex-dir "out/textures"] [--tol 0.02]

参数
----
    --save FILE     烘焙后的 .blend 输出路径（必填）
    --tex-dir DIR   贴图落盘目录（默认 <save 同目录>/textures）
    --tol FLOAT     形状聚类容差，与 blend_extract_parts.py 保持一致，默认 0.02
    --samples INT   EMIT 烘焙采样数，默认 4（EMIT 是确定性求值，低采样足够）
"""
import bpy
import os
import sys
import json
import time
import argparse
import numpy as np
import mathutils

# ---------- 复用部件提取脚本的聚类逻辑 ----------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import blend_extract_parts as bx   # noqa: E402  （模块内有 __main__ 保护，可安全导入）


# ---------- 分辨率策略：小件不给大图 ----------
def res_for(tris):
    if tris <= 60:
        return 128
    if tris <= 600:
        return 256
    return 512


# ---------- 保险：给缺 UV 的物体做包围盒投影展开 ----------
def box_project_uv(obj):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active.data
    vs = [v.co for v in me.vertices]
    if not vs:
        return False
    mn = [min(v[i] for v in vs) for i in range(3)]
    mx = [max(v[i] for v in vs) for i in range(3)]
    size = [(mx[i] - mn[i]) if (mx[i] - mn[i]) > 1e-9 else 1.0 for i in range(3)]

    def nrm(co, i):
        return (co[i] - mn[i]) / size[i]

    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        ui, vi = (1, 2) if ax == 0 else ((0, 2) if ax == 1 else (0, 1))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl[li].uv = (nrm(co, ui), nrm(co, vi))
    return True


# ---------- 把某个 socket 的结果重接到 Emission，供 EMIT 烘焙 ----------
class EmissionReroute:
    def __init__(self, mat, socket):
        self.nt = mat.node_tree
        self.outn = next(n for n in self.nt.nodes
                         if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        self.saved = [(l.from_node, l.from_socket.name)
                      for l in self.outn.inputs["Surface"].links]
        for l in list(self.outn.inputs["Surface"].links):
            self.nt.links.remove(l)
        self.em = self.nt.nodes.new("ShaderNodeEmission")
        self.em.location = (self.outn.location.x - 220.0, self.outn.location.y - 300.0)
        if socket.is_linked:
            self.nt.links.new(socket.links[0].from_socket, self.em.inputs["Color"])
        else:
            v = socket.default_value
            if isinstance(v, float):
                v = (v, v, v, 1.0)
            self.em.inputs["Color"].default_value = v
        self.nt.links.new(self.em.outputs[0], self.outn.inputs["Surface"])

    def restore(self):
        self.nt.nodes.remove(self.em)
        for fn, fsn in self.saved:
            self.nt.links.new(fn.outputs[fsn], self.outn.inputs["Surface"])


def bake_socket(obj, src_mat, socket, img, samples):
    """
    把 socket 的值烘焙进 img（EMIT 通道）

    坑：bpy.ops.object.bake 会烘焙物体的**全部材质槽**，每个槽的材质都必须有
    一个「活动且选中的图像纹理节点」，否则报「未找到活动和选定的图像纹理节点」，
    多槽共用同一材质时还会触发「循环依赖」并把 Blender 拖崩。
    所以这里给该物体用到的每个材质都装一个临时图像节点：
      - 目标材质的节点指向 img（我们要的结果）
      - 其余材质的节点指向一张 8×8 草稿图（结果丢弃）
    """
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    mats = []
    for m in obj.data.materials:
        if m is not None and getattr(m, "node_tree", None) and m not in mats:
            mats.append(m)
    if src_mat not in mats:
        mats.append(src_mat)

    scratch = bpy.data.images.new("__scratch", 8, 8, alpha=False)
    installed = []
    rr = None
    try:
        for m in mats:
            nt = m.node_tree
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img if m is src_mat else scratch
            installed.append((nt, t))

        # 先给所有槽装好节点，再改目标材质的输出链路，最后统一定 active
        rr = EmissionReroute(src_mat, socket)
        for nt, t in installed:
            for n in nt.nodes:
                n.select = False
            t.select = True
            nt.nodes.active = t

        bpy.ops.object.bake(type="EMIT", margin=4, use_clear=True)
        ok, err = True, None
    except Exception as e:
        ok, err = False, str(e)
    finally:
        if rr is not None:
            rr.restore()
        for nt, t in installed:
            try:
                nt.nodes.remove(t)
            except Exception:
                pass
        try:
            bpy.data.images.remove(scratch)
        except Exception:
            pass
    return ok, err


def new_img(name, size, is_data):
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    im.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    return im


def combine_orm(img_rough, img_metal, name, rough_default, metal_default, size):
    """G=粗糙度, B=金属度；R 留 1.0（未用 AO），A=1"""
    buf = np.empty(size * size * 4, dtype=np.float32)
    if img_rough is not None:
        img_rough.pixels.foreach_get(buf)
        g = buf[1::4].copy()
    else:
        g = np.full(size * size, float(rough_default), dtype=np.float32)
    if img_metal is not None:
        img_metal.pixels.foreach_get(buf)
        b = buf[2::4].copy()
    else:
        b = np.full(size * size, float(metal_default), dtype=np.float32)

    out = np.ones(size * size * 4, dtype=np.float32)
    out[1::4] = g
    out[2::4] = b
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(out)
    return im


def save_and_pack(img, tex_dir, filename):
    path = os.path.join(tex_dir, filename)
    img.filepath_raw = path
    img.file_format = "PNG"
    try:
        img.save()
    except Exception:
        return False
    try:
        img.pack()
    except Exception:
        pass
    return True


def build_export_mat(name, base_img, orm_img, metal_const, rough_const):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (60, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tb = nt.nodes.new("ShaderNodeTexImage")
    tb.image = base_img
    tb.location = (-420, 220)
    nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])

    if orm_img is not None:
        to = nt.nodes.new("ShaderNodeTexImage")
        to.image = orm_img
        to.location = (-460, -180)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-160, -180)
        nt.links.new(to.outputs["Color"], sep.inputs["Color"])
        outs = [o.name for o in sep.outputs]
        gname = "Green" if "Green" in outs else outs[1]
        bname = "Blue" if "Blue" in outs else outs[2]
        nt.links.new(sep.outputs[gname], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs[bname], bsdf.inputs["Metallic"])
    else:
        bsdf.inputs["Roughness"].default_value = float(rough_const)
        bsdf.inputs["Metallic"].default_value = float(metal_const)
    return m


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Bake procedural materials to textures")
    p.add_argument("--save", required=True, help="烘焙后 .blend 输出路径")
    p.add_argument("--tex-dir", dest="tex_dir", default=None, help="贴图目录")
    p.add_argument("--tol", type=float, default=0.02, help="形状聚类容差")
    p.add_argument("--samples", type=int, default=1,
                   help="EMIT 烘焙采样数，默认 1（EMIT 是确定性求值，1 足够且最快）")
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 个组（调试用）")
    return p.parse_args(argv)


def main():
    t0 = time.time()
    args = parse_args()

    save_path = os.path.abspath(args.save)
    save_dir = os.path.dirname(save_path)
    os.makedirs(save_dir, exist_ok=True)
    tex_dir = os.path.abspath(args.tex_dir or os.path.join(save_dir, "textures"))
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

    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    sigs, groups = bx.cluster(mesh_objs, args.tol, 0)
    if args.limit:
        groups = groups[:args.limit]

    # 补 UV
    fixed_uv = []
    for g in groups:
        for ob in [g["representative"]["obj"]] + [m["obj"] for m in g["members"]]:
            if len(ob.data.uv_layers) == 0:
                if box_project_uv(ob):
                    fixed_uv.append(ob.name)

    stats = {"groups": len(groups), "uv_fixed": len(fixed_uv),
             "bakes_ok": 0, "bakes_fail": [], "mats_made": 0,
             "slots_done": 0, "images": 0}

    for gi, g in enumerate(groups):
        rep = g["representative"]
        ob_rep = rep["obj"]
        tris = g["tris"]
        size = res_for(tris)
        rep_name = bx.safe_name(rep["name"], 60)
        n_slots = max(1, len(ob_rep.data.materials))

        for si in range(n_slots):
            src_mat = ob_rep.data.materials[si]
            if src_mat is None or not getattr(src_mat, "node_tree", None):
                continue
            nt = src_mat.node_tree
            pr = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if pr is None:
                continue

            tag = "g%02d_s%d_%s" % (gi, si, rep_name)
            base = pr.inputs["Base Color"]
            rough = pr.inputs["Roughness"]
            metal = pr.inputs["Metallic"]

            al_img = new_img("BC_" + tag, size, is_data=False)
            ok1, e1 = bake_socket(ob_rep, src_mat, base, al_img, args.samples)
            if ok1:
                stats["bakes_ok"] += 1
            else:
                stats["bakes_fail"].append(tag + ":albedo: " + str(e1))

            r_img = m_img = None
            if rough.is_linked or metal.is_linked:
                if rough.is_linked:
                    r_img = new_img("RG_" + tag, size, is_data=True)
                    ok, err = bake_socket(ob_rep, src_mat, rough, r_img, args.samples)
                    if ok:
                        stats["bakes_ok"] += 1
                    else:
                        stats["bakes_fail"].append(tag + ":rough: " + str(err))
                        r_img = None
                if metal.is_linked:
                    m_img = new_img("MT_" + tag, size, is_data=True)
                    ok, err = bake_socket(ob_rep, src_mat, metal, m_img, args.samples)
                    if ok:
                        stats["bakes_ok"] += 1
                    else:
                        stats["bakes_fail"].append(tag + ":metal: " + str(err))
                        m_img = None
                orm = combine_orm(
                    r_img, m_img, "ORM_" + tag,
                    rough.default_value if not rough.is_linked else 0.5,
                    metal.default_value if not metal.is_linked else 0.0,
                    size)
                save_and_pack(orm, tex_dir, "ORM_" + tag + ".png")
                stats["images"] += 1
                for tmp in (r_img, m_img):
                    if tmp is not None:
                        bpy.data.images.remove(tmp)
                orm_img = orm
            else:
                orm_img = None

            save_and_pack(al_img, tex_dir, "BC_" + tag + ".png")
            stats["images"] += 1

            exp = build_export_mat("BAKED_" + tag, al_img, orm_img,
                                   metal.default_value if not metal.is_linked else 0.0,
                                   rough.default_value if not rough.is_linked else 0.5)
            stats["mats_made"] += 1

            # 代表 + 同组所有成员都换成烘焙材质
            for m in g["members"]:
                mo = m["obj"]
                if len(mo.data.materials) > si:
                    mo.data.materials[si] = exp
            stats["slots_done"] += 1

        if (gi + 1) % 5 == 0:
            print("[bake] %d/%d groups  %.1fs" % (gi + 1, len(groups), time.time() - t0),
                  flush=True)

    # 清理未使用的原材质（可选，保持文件干净）
    bpy.ops.wm.save_as_mainfile(filepath=save_path)

    stats["seconds"] = round(time.time() - t0, 1)
    stats["saved"] = save_path
    stats["tex_dir"] = tex_dir
    print("\n=== BAKE RESULT ===")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


main()
