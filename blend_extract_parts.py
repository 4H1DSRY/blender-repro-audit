# -*- coding: utf-8 -*-
"""
blend_extract_parts.py —— 从 Blender 场景中提取唯一部件、聚类同类、导出可复用资产

用途
----
AI 生成的场景往往把每个零件做成独立物体并大量复制（.001 / .002 …），
再加上「同一根梁绕不同轴旋转」这类旋转等价的变体。
一个 668 物体的场景，实际可能只有几十种部件。

本脚本做三件事：
  1. 按「几何签名」把物体聚成同类组，能识别**旋转 / 镜像等价**的同形部件
     （这是单纯按名字去重做不到的：`beam | X` 与 `beam | Y` 名字不同、mesh 坐标不同，
      但排序后的包围盒三边完全相同）
  2. 每组选一个代表，输出可审阅的清单（Markdown + CSV）
  3. 可选：把代表标记为 Blender Asset，或导出为独立 .glb

用法
----
    "Blender路径\\blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
        --out "输出目录" [--export-glb "资产目录"] [--mark-assets]

    # 只分析不导出
    "...blender.exe" -b "scene.blend" -P blend_extract_parts.py -- --out "D:\\out"

    # 导出代表为独立 .glb（按族分目录）
    "...blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
        --out "D:\\out" --export-glb "D:\\assets" --mark-assets

参数
----
    --out DIR         报告输出目录（默认与 .blend 同目录）
    --export-glb DIR  把每个代表导出为 <DIR>/<族>/<部件名>.glb
    --mark-assets     把每个代表标记为 Blender Asset（供 Asset Browser 复用）
    --tol FLOAT       几何容差，默认 0.02（2%）——判断"同形"的相对误差上限
    --min-tris INT    忽略面数低于此值的碎件，默认 0（全要）
    --skip-variants   导出时跳过「材质变体」（同形但材质不同，默认也会导出）

输出
----
    parts_cluster_report.md   聚类报告（人读）
    parts_manifest.csv        逐物体清单（机器读，含所属组）

分组逻辑（三层，从严到宽）
--------------------------
    L1 精确组：顶点数 + 面数 + 排序包围盒 + 材质槽集合     → 完全一致的复制品
    L2 形状组：顶点数 + 面数 + 排序包围盒（容差内）        → 旋转/镜像等价的同形件
    L3 名称族：按名字前缀（`|` 或空格切分的前两个 token） → 语义上的同一类构件
"""

import bpy
import sys
import os
import re
import csv
import json
import math
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============================================================================
# 一、签名计算
# ============================================================================

_SUFFIX_RE = re.compile(r"\.\d{3}$")


def base_name(name):
    """去掉 Blender 的 .001 / .002 复制后缀。"""
    return _SUFFIX_RE.sub("", name)


def has_suffix(name):
    return bool(_SUFFIX_RE.search(name))


def family_of(name):
    """按名字前缀取语义族。用 | 或空格切分，取前两个 token。"""
    core = base_name(name)
    parts = [p for p in re.split(r"[|｜\s]+", core) if p]
    if len(parts) >= 2:
        return " ".join(parts[:2])
    return core


def local_bbox_size(ob):
    """
    物体在**局部空间**的包围盒尺寸（再乘上 object scale）。

    必须用局部空间：世界空间包围盒会因物体旋转而改变，
    那样就无法识别「同一根梁绕不同轴旋转」。
    """
    if not ob.bound_box:
        return [0.0, 0.0, 0.0]
    xs = [c[0] for c in ob.bound_box]
    ys = [c[1] for c in ob.bound_box]
    zs = [c[2] for c in ob.bound_box]
    sx, sy, sz = (abs(v) for v in ob.scale)
    return [(max(xs) - min(xs)) * sx,
            (max(ys) - min(ys)) * sy,
            (max(zs) - min(zs)) * sz]


def local_area(ob):
    """局部空间的表面积总和，再按平均缩放折算到世界尺度（用于同形判定）。"""
    me = ob.data
    a = 0.0
    for p in me.polygons:
        a += p.area
    sx, sy, sz = (abs(v) for v in ob.scale)
    scale_avg = (sx + sy + sz) / 3.0
    return a * scale_avg * scale_avg


def tri_count(me):
    return sum(max(len(p.vertices) - 2, 1) for p in me.polygons)


def quantize(v, rel_tol):
    """
    把长度值量化到「相对容差」的对数格子。
    用对数格子而非线性：无论尺寸大小，容差的相对宽度都一致。
    """
    if v <= 0:
        return 0
    return int(round(math.log(v) / math.log(1.0 + rel_tol)))


def signature(ob, rel_tol):
    me = ob.data
    tris = tri_count(me)
    dims = local_bbox_size(ob)
    dims_sorted = sorted(dims)                 # 排序 → 旋转不变
    area = local_area(ob)
    mats = tuple(sorted(m.name for m in me.materials if m))

    return {
        "name": ob.name,
        "base": base_name(ob.name),
        "family": family_of(ob.name),
        "verts": len(me.vertices),
        "polys": len(me.polygons),
        "tris": tris,
        "dims": [round(d, 5) for d in dims],           # 原始朝向的尺寸（供人读）
        "dims_sorted": [round(d, 5) for d in dims_sorted],
        "area": round(area, 6),
        "materials": mats,
        "has_suffix": has_suffix(ob.name),
        # --- 聚类键 ---
        "key_exact": (
            len(me.vertices), len(me.polygons),
            tuple(quantize(d, rel_tol) for d in dims_sorted if d > 0),
            quantize(area, rel_tol),
            mats,
        ),
        "key_shape": (
            len(me.vertices), len(me.polygons),
            tuple(quantize(d, rel_tol) for d in dims_sorted if d > 0),
            quantize(area, rel_tol),
        ),
        # 参数化族：截面（排序后最小的两维）相同 + 顶点/面数相同。
        # 用于识别「同一部件、不同规格」——如吊杆的三种长度、编钟的三种高度。
        # 这类变体必须**全部保留**，但应作为一个族统一管理：
        # 改基础形状时可一次性更新所有规格。
        "key_param": (
            len(me.vertices), len(me.polygons),
            quantize(dims_sorted[0], rel_tol) if len(dims_sorted) > 0 else 0,
            quantize(dims_sorted[1], rel_tol) if len(dims_sorted) > 1 else 0,
        ),
    }


# ============================================================================
# 二、聚类
# ============================================================================

def cluster(objs, rel_tol, min_tris):
    sigs = []
    for ob in objs:
        if ob.type != "MESH":
            continue
        s = signature(ob, rel_tol)
        if s["tris"] < min_tris:
            continue
        s["obj"] = ob
        sigs.append(s)

    # L1 精确组
    exact = {}
    for s in sigs:
        exact.setdefault(s["key_exact"], []).append(s)
    for i, k in enumerate(sorted(exact, key=lambda k: -len(exact[k]))):
        for s in exact[k]:
            s["exact_gid"] = i

    # L2 形状组：把 L1 组按 key_shape 合并
    merged = {}
    for s in sigs:
        merged.setdefault(s["key_shape"], []).append(s)
    shape_keys = sorted(merged, key=lambda k: -len(merged[k]))
    shape_id = {k: i for i, k in enumerate(shape_keys)}
    for s in sigs:
        s["shape_gid"] = shape_id[s["key_shape"]]

    # L3 参数化族：形状同族、仅规格参数不同（同截面 / 不同长度）
    by_param = {}
    for s in sigs:
        by_param.setdefault(s["key_param"], []).append(s)
    param_keys = sorted(by_param, key=lambda k: -len(by_param[k]))
    param_id = {k: i for i, k in enumerate(param_keys)}
    for s in sigs:
        s["param_gid"] = param_id[s["key_param"]]

    # 组装组结构
    groups = []
    for k in shape_keys:
        members = merged[k]
        # L1 子组数量 = 这组里有多少种材质变体
        variants = len({m["key_exact"] for m in members})
        groups.append({
            "shape_gid": shape_id[k],
            "param_gid": param_id[members[0]["key_param"]],
            "shape_key": k,
            "members": members,
            "family": members[0]["family"],
            "variants": variants,
            "tris": members[0]["tris"],
            "dims_sorted": members[0]["dims_sorted"],
            "materials": sorted({mat for m in members for mat in m["materials"]}),
            "representative": pick_representative(members),
        })
    return sigs, groups


def pick_representative(members):
    """
    选代表：优先「没有 .001 后缀」的原始件，其次名字最短，再其次面数最大。
    """
    def rank(s):
        return (s["has_suffix"], len(s["name"]), -s["tris"], s["name"])
    return sorted(members, key=rank)[0]


def family_summary(groups):
    fam = {}
    for g in groups:
        f = g["family"]
        e = fam.setdefault(f, {"groups": 0, "meshes": 0, "families": set()})
        e["groups"] += 1
        e["meshes"] += len(g["members"])
    return fam


# ============================================================================
# 三、导出
# ============================================================================

SAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(s, limit=80):
    s = SAFE_RE.sub("_", s).strip().strip(".")
    return (s[:limit] or "unnamed")


def export_glb(groups, out_dir, skip_variants):
    """把每个形状组的代表导出为独立 .glb，按族分目录。"""
    ok, fail = 0, []
    for gi, g in enumerate(groups):
        rep = g["representative"]
        fam_dir = os.path.join(out_dir, safe_name(g["family"], 40))
        os.makedirs(fam_dir, exist_ok=True)

        name = safe_name(rep["name"])
        if len(g["members"]) > 1 and not skip_variants:
            name = "%s__n%d" % (name, len(g["members"]))
        path = os.path.join(fam_dir, name + ".glb")
        if os.path.exists(path):
            path = os.path.join(fam_dir, "%s__g%d.glb" % (name, gi))

        try:
            bpy.ops.object.select_all(action="DESELECT")
            rep["obj"].select_set(True)
            bpy.context.view_layer.objects.active = rep["obj"]
            bpy.ops.export_scene.gltf(
                filepath=path, use_selection=True, export_format="GLB")
            ok += 1
        except Exception as e:
            fail.append((rep["name"], str(e)))
    return ok, fail


def mark_assets(groups):
    """把代表标记为 Blender Asset，供 Asset Browser 拖拽复用。"""
    ok, fail = 0, []
    for g in groups:
        rep = g["representative"]
        try:
            rep["obj"].asset_mark()
            rep["obj"].asset_data.description = (
                "family=%s | members=%d | tris=%d | loc=%.4f"
                % (g["family"], len(g["members"]), g["tris"],
                   rep["area"])
            )
            ok += 1
        except Exception as e:
            fail.append((rep["name"], str(e)))
    return ok, fail


# ============================================================================
# 四、报告
# ============================================================================

def esc(s):
    return str(s).replace("|", "\\|")


def write_reports(sigs, groups, out_dir, src, args, export_info, asset_info):
    total_meshes = len(sigs)
    total_tris = sum(s["tris"] for s in sigs)
    fam = family_summary(groups)

    L = []
    A = L.append
    A("# 部件提取与同类聚类报告")
    A("")
    A(f"- **源文件**：`{src}`")
    A(f"- **网格物体总数**：{total_meshes}")
    A(f"- **三角面总数**：{total_tris}")
    A(f"- **几何容差**：{args.tol*100:.1f}%")
    A(f"- **面数下限**：{args.min_tris}")
    A("")
    A("---")
    A("")
    A("## 一、聚类结果")
    A("")
    n_exact = len({s["key_exact"] for s in sigs})
    n_param = len({g["param_gid"] for g in groups})
    A("| 层级 | 含义 | 组数 | 相比上一层的压缩 |")
    A("|---|---|---:|---|")
    A(f"| 原始物体 | — | {total_meshes} | — |")
    A(f"| **L1 精确组** | 顶点/面数/尺寸/材质全同 | {n_exact} | "
      f"{-100*(1-n_exact/total_meshes):.1f}% |")
    A(f"| **L2 形状组** | 再加「旋转/镜像等价」合并 | {len(groups)} | "
      f"{-100*(1-len(groups)/max(n_exact,1)):.1f}% |")
    A(f"| **L3 参数族** | 截面向同、仅规格不同（如不同长度的吊杆） | {n_param} | "
      f"{-100*(1-n_param/max(len(groups),1)):.1f}% |")
    A(f"| L4 名称族 | 按名字前缀的语义归类 | {len(fam)} | — |")
    A("")
    A(f"> **结论**：{total_meshes} 个物体实际只有 **{len(groups)} 种形状**，"
      f"归为 **{n_param} 个几何族**、**{len(fam)} 个语义族**。")
    A(f"> 需要存储的资产从 {total_meshes} 个降到 **{len(groups)} 个**，"
      f"压缩率 **{100*(1-len(groups)/max(total_meshes,1)):.1f}%**。")
    A("")

    if export_info:
        ok, fail = export_info
        A(f"**已导出 .glb**：{ok} 个" + (f"，失败 {len(fail)} 个" if fail else ""))
        A("")
        for n, e in fail[:10]:
            A(f"- ❌ `{n}`：{e}")
        if fail:
            A("")
    if asset_info:
        ok, fail = asset_info
        A(f"**已标记为 Asset**：{ok} 个" + (f"，失败 {len(fail)} 个" if fail else ""))
        A("")

    # --- 形状组明细 ---
    A("## 二、形状组明细")
    A("")
    A("按成员数降序。**代表** = 建议保留并存储的那一个。")
    A("")
    A("| # | 代表（建议保留） | 成员数 | 三角面 | 排序尺寸 (X/Y/Z) | 材质变体 | 族 |")
    A("|---|---|---:|---:|---|---:|---|")
    for i, g in enumerate(groups):
        rep = g["representative"]
        dims = " × ".join(f"{d:.4f}" for d in g["dims_sorted"])
        A(f"| {i} | `{esc(rep['name'])}` | {len(g['members'])} | {g['tris']} "
          f"| {dims} | {g['variants']} | {esc(g['family'])} |")
    A("")

    # --- 重复度 Top ---
    A("## 三、重复度最高的组（优先处理）")
    A("")
    A("| 代表 | 成员数 | 成员示例 |")
    A("|---|---:|---|")
    for g in sorted(groups, key=lambda x: -len(x["members"]))[:15]:
        if len(g["members"]) < 2:
            continue
        rep = g["representative"]
        ex = ", ".join(f"`{m['name']}`" for m in g["members"][:4])
        more = f" … +{len(g['members'])-4}" if len(g["members"]) > 4 else ""
        A(f"| `{esc(rep['name'])}` | {len(g['members'])} | {esc(ex)}{more} |")
    A("")

    # --- 参数化族 ---
    param_groups = {}
    for g in groups:
        param_groups.setdefault(g["param_gid"], []).append(g)
    multi_param = {k: v for k, v in param_groups.items() if len(v) > 1}
    A("## 四、参数化族（同一部件、不同规格）")
    A("")
    if multi_param:
        A("这些组的形状同族，仅尺寸参数不同——**每一档规格都要单独保留**，"
          "但应作为一个族统一管理（改基础形状时可一次性更新所有规格）。")
        A("")
        A("> ⚠ **「跨语义族」标记的含义**：这些部件几何同形，但**语义不同**"
          "（例如灯笼托架与桌腿恰好都是同截面柱体）。")
        A("> 它们适合「用一个基础形状参数化派生」，"
          "但**是否合并存储必须人工判断**——若将来各自独立演化，应分开存。")
        A("")
        for k, gs in sorted(multi_param.items(), key=lambda x: -len(x[1])):
            fams = sorted({g["family"] for g in gs})
            if len(fams) > 1:
                A(f"**⚠ 跨 {len(fams)} 个语义族** · {len(gs)} 档规格 —— "
                  f"{'、'.join(esc(f) for f in fams)}")
            else:
                A(f"**{esc(fams[0])}** · {len(gs)} 档规格")
            A("")
            A("| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |")
            A("|---|---:|---|---:|")
            for g in sorted(gs, key=lambda x: x["dims_sorted"][-1]):
                dims = " × ".join(f"{d:.4f}" for d in g["dims_sorted"])
                A(f"| `{esc(g['representative']['name'])}` | {g['tris']} | {dims} "
                  f"| {len(g['members'])} |")
            A("")
    else:
        A("_未检出参数化族（所有形状相互独立，没有「同款不同规格」的情况）。_")
        A("")

    # --- 名称族 ---
    A("## 五、语义族汇总（L4）")
    A("")
    A("| 族 | 形状组数 | 物体数 |")
    A("|---|---:|---:|")
    for f, e in sorted(fam.items(), key=lambda x: -x[1]["meshes"]):
        A(f"| {esc(f)} | {e['groups']} | {e['meshes']} |")
    A("")

    # --- 单件（无同类）---
    singles = [g for g in groups if len(g["members"]) == 1]
    A("## 六、独一件（没有同类的部件）")
    A("")
    A(f"共 {len(singles)} 个。这类部件每个都要单独存储，也是成本最高的部分。")
    A("")
    if singles:
        A("| 部件 | 三角面 | 排序尺寸 | 族 |")
        A("|---|---:|---|---|")
        for g in sorted(singles, key=lambda x: -x["tris"])[:40]:
            rep = g["representative"]
            dims = " × ".join(f"{d:.4f}" for d in g["dims_sorted"])
            A(f"| `{esc(rep['name'])}` | {g['tris']} | {dims} | {esc(g['family'])} |")
        if len(singles) > 40:
            A(f"| _…其余 {len(singles)-40} 个略（见 CSV）_ | | | |")
        A("")

    A("## 七、下一步")
    A("")
    A("1. **审阅** `parts_manifest.csv`：确认聚类是否正确，"
      "尤其是那些「形状相同但语义不同」的误合并")
    A("2. **保留代表**：把每组的代表物体归入一个新集合（如 `ASSET_LIBRARY`），"
      "其余可删或移到 `_SUPERSEDED` 集合备用")
    A("3. **存入资产库**：把代表导出为 .glb，或标记为 Blender Asset 后"
      "在 Asset Browser 中跨项目拖拽复用")
    A("4. **命名规范**：导出前把代表改名为 `<族>_<序号>`，"
      "去掉 `.001` 之类的复制后缀")
    A("")
    A("---")
    A("")
    A("_由 `blend_extract_parts.py` 生成_")
    A("")

    md_path = os.path.join(out_dir, "parts_cluster_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    csv_path = os.path.join(out_dir, "parts_manifest.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["object_name", "base_name", "family", "shape_group",
                    "param_group", "exact_group", "is_representative",
                    "members_in_group",
                    "tris", "verts", "polys",
                    "dim_x", "dim_y", "dim_z",
                    "dim_sorted_1", "dim_sorted_2", "dim_sorted_3",
                    "area", "materials"])
        reps = {g["representative"]["name"]: i for i, g in enumerate(groups)}
        for s in sigs:
            gid = s["shape_gid"]
            grp = next((g for g in groups if g["shape_gid"] == gid), None)
            w.writerow([
                s["name"], s["base"], s["family"], gid, s["param_gid"], s["exact_gid"],
                "YES" if s["name"] in reps else "",
                len(grp["members"]) if grp else 0,
                s["tris"], s["verts"], s["polys"],
                s["dims"][0], s["dims"][1], s["dims"][2],
                s["dims_sorted"][0], s["dims_sorted"][1], s["dims_sorted"][2],
                s["area"], ";".join(s["materials"]),
            ])
    return md_path, csv_path


# ============================================================================
# 五、入口
# ============================================================================

def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Extract unique parts from a Blender scene")
    p.add_argument("--out", default=None, help="报告输出目录")
    p.add_argument("--export-glb", dest="export_glb", default=None,
                   help="导出代表为 .glb 的目录（按族分子目录）")
    p.add_argument("--mark-assets", dest="mark_assets", action="store_true",
                   help="把代表标记为 Blender Asset")
    p.add_argument("--tol", type=float, default=0.02, help="几何容差，默认 0.02")
    p.add_argument("--min-tris", dest="min_tris", type=int, default=0,
                   help="忽略面数低于此值的碎件")
    p.add_argument("--skip-variants", dest="skip_variants", action="store_true",
                   help="导出时不在文件名里标注成员数")
    return p.parse_args(argv)


def main():
    args = parse_args()

    src = bpy.data.filepath or "(未保存文件)"
    out_dir = os.path.abspath(args.out or os.path.dirname(src) or os.getcwd())
    os.makedirs(out_dir, exist_ok=True)

    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    if not mesh_objs:
        print(json.dumps({"error": "场景中没有网格物体"}, ensure_ascii=False))
        return

    sigs, groups = cluster(mesh_objs, args.tol, args.min_tris)

    export_info = None
    if args.export_glb:
        edir = os.path.abspath(args.export_glb)
        os.makedirs(edir, exist_ok=True)
        export_info = export_glb(groups, edir, args.skip_variants)

    asset_info = None
    if args.mark_assets:
        asset_info = mark_assets(groups)

    md_path, csv_path = write_reports(
        sigs, groups, out_dir, src, args, export_info, asset_info)

    print("\n" + "=" * 66)
    print("EXTRACT RESULT")
    print("=" * 66)
    print(json.dumps({
        "mesh_objects": len(mesh_objs),
        "analyzed": len(sigs),
        "exact_groups": len({s["key_exact"] for s in sigs}),
        "shape_groups": len(groups),
        "param_families": len({g["param_gid"] for g in groups}),
        "families": len(family_summary(groups)),
        "singletons": len([g for g in groups if len(g["members"]) == 1]),
        "compression": round(1 - len(groups) / max(len(sigs), 1), 3),
        "representatives": [g["representative"]["name"] for g in groups[:40]],
        "exported_glb": export_info[0] if export_info else 0,
        "marked_assets": asset_info[0] if asset_info else 0,
        "report_md": md_path,
        "manifest_csv": csv_path,
    }, ensure_ascii=False, indent=2))
    print("=" * 66)


if __name__ == "__main__":
    main()
