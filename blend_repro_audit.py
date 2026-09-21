# -*- coding: utf-8 -*-
"""
blend_repro_audit.py —— 评估 Blender 3D 模型「人工完全复现」的难度与工时

用途
----
给定一个 AI 生成的 3D 模型，量化评估：一个人不借助 AI、也不使用原始生成脚本，
仅凭观察成品，从零重建它需要多少工时，并输出可直接执行的分步清单。

输出
----
1. audit.json        原始指标，便于程序化对比多个模型
2. audit_report.md   人读报告：结构诊断 + 分维度指标 + 复现步骤清单 + 隐性成本警告

用法
----
    # .blend 文件
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b "model.blend" \\
        -P blend_repro_audit.py -- --out "D:\\out"

    # 非 .blend 格式（先清空场景再导入）
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b \\
        -P blend_repro_audit.py -- --import "model.glb" --out "D:\\out"

设计原则
--------
工时不由「面数」单一决定，而由「独立决策点数量」决定：唯一部件数、材质节点复杂度、
程序化系统规模、拓扑规整度。更关键的是：AI 生成的资产会把每个零件做成独立物体
并大量复制同款（.001/.002…），若按物体数计时会把工时虚高数倍。
本脚本先做实例去重与碎片化修正，还原「人工实际会怎么做」，再分维度计量。

报告同时给出两个数字：
  · 结构等价复现 —— 1:1 照原结构重建所有部件
  · 外观等价复现 —— 视觉一致，但按人工的合理方式组织（合并碎件、复用模板）
"""

import bpy
import sys
import os
import re
import json
import argparse
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============================================================================
# 一、工时基准表（可调）
# ----------------------------------------------------------------------------
# 依据：熟练 3D 建模师（非新手、非顶尖）在**无参考脚本、仅凭观察**前提下的经验速率。
# 所有单位：小时。改这里即可重算全部结论。
# ============================================================================

RATES = {
    # --- 建模 ---
    "obj_base":               0.30,   # 一个部件的起手成本（建基础形、摆位、对齐）
    "tri_per_hour":           2000,   # 捏形速率：约 2000 三角面 / 小时（含反复调整）
    "island_extra":           0.50,   # 每个额外连通部件

    # --- 拓扑 ---
    "retopo_per_1k_tris":     0.50,   # 重拓扑：每 1000 三角面 0.5h（游戏级边流）

    # --- UV / 贴图 ---
    "uv_per_map":             0.80,   # 主体每张 UV 图展开 + 排布
    "uv_small":               0.05,   # 小件每张 UV 图（秒级操作）
    "texture_recreate":       1.20,   # 每张贴图若无源文件需重绘

    # --- 材质 ---
    "material_base":          0.50,   # 每个材质的起手（理解目标观感）
    "material_node":          0.04,   # 每个节点（连线 + 调试，约 2.4 分钟）
    "procedural_heavy":       2.00,   # 程序化链的额外调试成本（反复对齐观感）
    "procedural_heavy_thresh": 4,     # 程序化纹理节点数 ≥ 此值算「重度程序化」

    # --- 程序化系统（隐性成本核心）---
    "geonodes_base":          4.00,   # 重建一个几何节点组的起手（从零推导逻辑）
    "geonodes_per_node":      0.30,   # 每个节点（推参数 + 验证效果）

    # --- 绑定 / 动画 ---
    "bone":                   0.05,   # 每根骨骼（建立 + 权重）
    "action_base":            1.50,   # 每个动作的起手
    "keyframe_per_100":       1.00,   # 每 100 关键帧

    # --- 脚本逆向 ---
    "script_reverse":         6.00,   # 逆向一个未知生成脚本的逻辑
    "script_per_100_lines":   0.50,   # 每 100 行代码的理解成本
    "script_utility":         0.50,   # 非生成脚本（工具/检查类）：只需理解用途

    # --- 实例化 / 碎片化修正 ---
    # AI 生成的资产常把每个零件做成独立物体并大量复制同款，
    # 直接按「物体数」计时会把工时虚高数倍。以下参数用于还原人工的真实做法。
    "instance_place":         0.025,  # 复制实例的摆位与变换成本（含对齐、旋转）
    "small_part_thresh":      60,     # 三角面低于此值算「小件」
    "small_free_quota":       20,     # 前 N 个小件不打折
    "small_batch_factor":     0.40,   # 超出配额后小件的边际成本系数
    "curve_per_spline":       0.15,   # 每条曲线的建模
    "light_camera":           0.10,   # 每个灯光 / 相机的布置

    # --- 固定前置 ---
    "prep_reference":         0.60,   # 采集参考、测量比例、确定尺度
}

# 难度分级（按「外观等价」中位工时，单位小时）
DIFFICULTY_BANDS = [
    (4,     "极易", "基本体 + 少量调整，随时可重做"),
    (12,    "易",   "单一部件为主，手工建模当天可完成"),
    (45,    "中",   "多部件 + 材质，约 1 周专注投入"),
    (150,   "难",   "结构复杂或含程序化系统，需 2–4 周全职"),
    (500,   "极难", "重度程序化 / 深度绑定，需 1–3 个月"),
    (10**9, "近乎不可行", "工时量级已超过「重新生成一遍并迭代」的成本"),
]

# 程序化节点类型（「看成品看不出来」的部分）
PROCEDURAL_NODE_TYPES = {
    "ShaderNodeTexNoise", "ShaderNodeTexVoronoi", "ShaderNodeTexMusgrave",
    "ShaderNodeTexWave", "ShaderNodeTexMagic", "ShaderNodeTexGradient",
    "ShaderNodeTexBrick", "ShaderNodeTexChecker", "ShaderNodeTexEnvironment",
    "ShaderNodeTexCoord", "ShaderNodeMapping", "ShaderNodeTexSky",
    "ShaderNodeTexGabor", "ShaderNodeTexWhiteNoise", "ShaderNodeTexIES",
}

# 生成脚本的判别关键词（用于区分「生成脚本」与「工具脚本」）
GEN_MARKERS = ("primitive_", "from_pydata", "bmesh", "ops.mesh.",
               "modifier_add", "node_group_add", "extrude", "subdivide")
# 工具 / 检查类脚本的特征。这类脚本出现在 .blend 里，
# 不代表模型是脚本生成的，也不参与人工复现。
UTIL_MARKERS = ("def count_", "def check_", "def verify_", "def get_abs_path",
                "def report", "统计", "检查", "验证", "审计", "assert ")

# Blender 默认命名（未被清理的证据）
DEFAULT_NAMES = {"Cube", "Sphere", "Cylinder", "Plane", "Torus", "Cone",
                 "Icosphere", "Circle", "Empty", "Text", "Curve"}


# ============================================================================
# 二、参数解析
# ============================================================================

def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Blender model reproduction difficulty audit")
    p.add_argument("--out", default=None, help="输出目录，默认与模型同目录")
    p.add_argument("--import", dest="import_path", default=None,
                   help="非 .blend 格式的模型路径（fbx/glb/obj/usd）")
    p.add_argument("--label", default=None, help="报告标题中显示的模型名")
    return p.parse_args(argv)


# ============================================================================
# 三、指标采集
# ============================================================================

def count_islands(me, limit=300000):
    """并查集统计网格连通分量（= 需要单独塑造的部件数）。"""
    n = len(me.vertices)
    if n == 0:
        return 0
    if n > limit:
        return None
    parent = list(range(n))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for e in me.edges:
        a, b = e.vertices
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    return len({find(i) for i in range(n)})


def collect_mesh(ob):
    me = ob.data
    polys = list(me.polygons)
    tris = sum(max(len(p.vertices) - 2, 1) for p in polys)
    quads = sum(1 for p in polys if len(p.vertices) == 4)
    ngons = sum(1 for p in polys if len(p.vertices) > 4)
    quad_ratio = (quads / len(polys)) if polys else 0.0

    return {
        "verts": len(me.vertices),
        "edges": len(me.edges),
        "polys": len(polys),
        "tris": tris,
        "quads": quads,
        "ngons": ngons,
        "quad_ratio": round(quad_ratio, 3),
        "islands": count_islands(me),
        "dimensions": [round(d, 3) for d in ob.dimensions],
        "n_uv_layers": len(me.uv_layers) if hasattr(me, "uv_layers") else 0,
        "materials": [m.name if m else None for m in me.materials],
        "shape_keys": len(me.shape_keys.key_blocks) if getattr(me, "shape_keys", None) else 0,
        "vertex_groups": len(ob.vertex_groups),
        "has_custom_normals": bool(getattr(me, "has_custom_normals", False)),
        "smooth_ratio": round(
            sum(1 for p in polys if p.use_smooth) / len(polys), 3) if polys else 0.0,
    }


def collect_modifiers(ob):
    out = []
    for m in ob.modifiers:
        e = {"name": m.name, "type": m.type}
        ng = getattr(m, "node_group", None)
        if ng:
            e["node_group"] = ng.name
        out.append(e)
    return out


def collect_material(mat):
    info = {
        "name": mat.name,
        "node_count": 0,
        "node_types": {},
        "procedural_nodes": 0,
        "image_nodes": [],
        "group_nodes": 0,
        "is_procedural": False,
    }
    tree = getattr(mat, "node_tree", None)   # 不读已弃用的 use_nodes，避免警告
    if not tree:
        return info
    nodes = tree.nodes
    info["node_count"] = len(nodes)
    types = {}
    for n in nodes:
        types[n.bl_idname] = types.get(n.bl_idname, 0) + 1
        if n.bl_idname in PROCEDURAL_NODE_TYPES:
            info["procedural_nodes"] += 1
        if n.bl_idname == "ShaderNodeTexImage":
            img = getattr(n, "image", None)
            if img:
                info["image_nodes"].append({
                    "name": img.name, "size": list(img.size),
                    "packed": bool(img.packed_file), "source": img.source,
                })
        if n.bl_idname == "ShaderNodeGroup":
            info["group_nodes"] += 1
    info["node_types"] = types
    info["is_procedural"] = info["procedural_nodes"] >= RATES["procedural_heavy_thresh"]
    return info


def collect_all():
    data = {
        "filepath": bpy.data.filepath or "(未保存文件)",
        "blender_version": bpy.app.version_string,
        "audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "objects": [], "collections": [], "materials": [], "node_groups": [],
        "texts": [], "actions": [], "images": [], "drivers": [], "worlds": [],
        "warnings": [],
    }

    type_counts = {}
    for ob in bpy.data.objects:
        type_counts[ob.type] = type_counts.get(ob.type, 0) + 1
        entry = {
            "name": ob.name,
            "type": ob.type,
            "parent": ob.parent.name if ob.parent else None,
            "collections": [c.name for c in ob.users_collection],
            "modifiers": collect_modifiers(ob),
            "scale": [round(s, 4) for s in ob.scale],
        }
        if ob.type == "MESH":
            try:
                entry.update(collect_mesh(ob))
            except Exception as e:
                data["warnings"].append(f"mesh {ob.name}: {e}")
        elif ob.type == "ARMATURE":
            arm = ob.data
            max_depth = 0
            for b in arm.bones:
                d, p = 0, b.parent
                while p:
                    d += 1
                    p = p.parent
                max_depth = max(max_depth, d)
            entry["bones"] = len(arm.bones)
            entry["bone_tree_depth"] = max_depth
        elif ob.type == "CURVE":
            entry["splines"] = len(ob.data.splines)
        data["objects"].append(entry)
    data["object_type_counts"] = type_counts

    data["collections"] = [c.name for c in bpy.data.collections]

    for mat in bpy.data.materials:
        try:
            data["materials"].append(collect_material(mat))
        except Exception as e:
            data["warnings"].append(f"material {mat.name}: {e}")

    for g in bpy.data.node_groups:
        try:
            types = {}
            for n in g.nodes:
                types[n.bl_idname] = types.get(n.bl_idname, 0) + 1
            data["node_groups"].append({
                "name": g.name, "type": getattr(g, "type", "?"),
                "node_count": len(g.nodes), "link_count": len(g.links),
                "input_count": len(g.inputs) if hasattr(g, "inputs") else 0,
                "node_types": types,
            })
        except Exception as e:
            data["warnings"].append(f"node_group {g.name}: {e}")

    # 文本块：脚本可能藏在 .blend 内部
    for t in bpy.data.texts:
        try:
            raw = t.as_string()
            lines = raw.splitlines()
            is_gen = any(k in raw for k in GEN_MARKERS)
            is_util = any(k in raw for k in UTIL_MARKERS)
            data["texts"].append({
                "name": t.name,
                "lines": len(lines),
                "chars": len(raw),
                "looks_generative": is_gen and not is_util,
                "looks_utility": is_util,
                "head": "\n".join(lines[:12]),
            })
        except Exception as e:
            data["warnings"].append(f"text {t.name}: {e}")

    for a in bpy.data.actions:
        try:
            kf = sum(len(fc.keyframe_points) for fc in a.fcurves)
            data["actions"].append({"name": a.name, "fcurves": len(a.fcurves),
                                    "keyframes": kf})
        except Exception as e:
            data["warnings"].append(f"action {a.name}: {e}")

    for img in bpy.data.images:
        if img.name in ("Render Result", "Viewer Node"):
            continue
        data["images"].append({
            "name": img.name, "size": list(img.size),
            "packed": bool(img.packed_file), "source": img.source,
            "filepath": img.filepath if img.source == "FILE" else "",
        })

    def scan_drivers(idb, owner):
        ad = getattr(idb, "animation_data", None)
        if ad and ad.drivers:
            for d in ad.drivers:
                data["drivers"].append({
                    "owner": owner, "data_path": d.data_path,
                    "expression": getattr(d, "driver_expression", "") or "",
                })

    for ob in bpy.data.objects:
        scan_drivers(ob, f"obj:{ob.name}")
    for mat in bpy.data.materials:
        scan_drivers(mat, f"mat:{mat.name}")

    for w in bpy.data.worlds:
        tree = getattr(w, "node_tree", None)
        data["worlds"].append({
            "name": w.name, "node_count": len(tree.nodes) if tree else 0,
        })

    return data


# ============================================================================
# 四、结构诊断（识别 AI 生成特征）
# ============================================================================

def diagnose(data, meshes):
    """返回结构特征字典——直接反映「这是 AI 产物还是人工产物」。"""
    groups = {}
    for m in meshes:
        groups.setdefault((_base_name(m["name"]), m["tris"]), []).append(m)

    unique_parts = len(groups)
    dup_instances = len(meshes) - unique_parts
    small = [m for m in meshes if m["tris"] <= RATES["small_part_thresh"]]

    cols = data["collections"]
    phase_cols = [c for c in cols if re.match(r"^\d+\s*[|｜]", c)]
    dup_cols = [c for c in cols if re.search(r"\.\d{3}$", c)]
    default_named = [o["name"] for o in data["objects"]
                     if _base_name(o["name"]) in DEFAULT_NAMES]

    proc_mats = [m for m in data["materials"] if m["is_procedural"]]
    total_objs = max(len(data["objects"]), 1)

    return {
        "mesh_objects": len(meshes),
        "unique_parts": unique_parts,
        "dup_instances": dup_instances,
        "dedup_ratio": round(unique_parts / max(len(meshes), 1), 3),
        "small_parts": len(small),
        "small_ratio": round(len(small) / max(len(meshes), 1), 3),
        "collections": len(cols),
        "phase_collections": phase_cols,
        "dup_collections": dup_cols,
        "default_named_count": len(default_named),
        "default_named_sample": default_named[:8],
        "proc_materials": len(proc_mats),
        "total_materials": len(data["materials"]),
        "total_objects": len(data["objects"]),
        "has_uv": any(m["n_uv_layers"] > 0 for m in meshes),
        "has_textures": len(data["images"]) > 0,
        "has_rig": any(o["type"] == "ARMATURE" for o in data["objects"]),
        "has_anim": len(data["actions"]) > 0,
        "has_geonodes": len(data["node_groups"]) > 0,
    }


def ai_traits(diag):
    """把结构特征翻译成可读的 AI 生成迹象列表。"""
    out = []
    if diag["dup_instances"] > 0:
        out.append(
            f"**实例化复制 {diag['dup_instances']} 个**（去重后仅 {diag['unique_parts']} 个唯一部件）"
            f"——同名同面数的物体被反复复制，人工不会这么拆")
    if diag["small_parts"] > 30:
        out.append(
            f"**碎片化：{diag['small_parts']} 个小件（≤{RATES['small_part_thresh']} 三角面）"
            f"占 {diag['small_ratio']*100:.0f}%**——典型的分件累加式生成")
    if diag["phase_collections"]:
        out.append(
            f"**阶段化集合 {len(diag['phase_collections'])} 个**"
            f"（如 `{diag['phase_collections'][-1]}`）"
            "——暴露出多轮增量生成的过程痕迹")
    if diag["dup_collections"]:
        out.append(
            f"**重复集合 {len(diag['dup_collections'])} 个**（`.001` 后缀）"
            "——组织层级未经清理")
    if diag["default_named_count"] > 0:
        out.append(
            f"**残留 Blender 默认命名 {diag['default_named_count']} 个**"
            f"（如 `{diag['default_named_sample'][0]}`）——未做命名规范化")
    if diag["proc_materials"] > 0:
        out.append(
            f"**{diag['proc_materials']}/{diag['total_materials']} 个材质为重度程序化**，"
            "且无一张贴图——观感完全由节点参数决定")
    if not diag["has_uv"] and diag["has_textures"]:
        out.append("有贴图但无 UV——资源组织不完整")
    return out


# ============================================================================
# 五、工时估算
# ============================================================================

def _base_name(name):
    """去掉 Blender 的 .001 / .002 复制后缀。"""
    return re.sub(r"\.\d{3}$", "", name)


def _part_hours(tris):
    """单个唯一部件的建模工时。非线性——小件的人工成本远低于其面数占比。"""
    if tris <= 0:
        return 0.0
    if tris <= 20:
        return 0.06
    if tris <= 60:
        return 0.12
    if tris <= 200:
        return 0.30
    if tris <= 600:
        return 0.80
    if tris <= 1500:
        return 1.80
    return 1.80 + (tris - 1500) / RATES["tri_per_hour"]


def estimate(data, meshes, diag):
    dims = []

    def add(key, label, low, mid, high, basis):
        dims.append({"key": key, "label": label,
                     "low": round(low, 2), "mid": round(mid, 2),
                     "high": round(high, 2), "basis": basis})

    curves = [o for o in data["objects"] if o["type"] == "CURVE"]
    lights_cams = [o for o in data["objects"] if o["type"] in ("LIGHT", "CAMERA")]
    armatures = [o for o in data["objects"] if o["type"] == "ARMATURE"]

    # ---- 1. 建模（含实例去重与碎片化修正）----
    groups = {}
    for m in meshes:
        groups.setdefault((_base_name(m["name"]), m["tris"]), []).append(m)

    model_h = 0.0
    small_costs = []
    total_tris = sum(m["tris"] for m in meshes)
    for (bn, tris), obs in groups.items():
        model_h += _part_hours(tris)
        if tris <= RATES["small_part_thresh"]:
            small_costs.append(_part_hours(tris))
        model_h += (len(obs) - 1) * RATES["instance_place"]

    n_small = len(small_costs)
    quota = RATES["small_free_quota"]
    batch_factor = ((quota + (n_small - quota) * RATES["small_batch_factor"]) / n_small
                    if n_small > quota else 1.0)
    model_h = model_h - sum(small_costs) + sum(small_costs) * batch_factor

    add("model", "建模（体块 + 塑形）",
        model_h * 0.7, model_h, model_h * 1.6,
        f"{len(meshes)} 个网格 → 去重后 {diag['unique_parts']} 个唯一部件"
        f"（{diag['dup_instances']} 个为复制实例）/ {total_tris} 三角面"
        + (f"；小件 {n_small} 个已计批量折扣 {batch_factor:.2f}×" if n_small > quota else ""))

    # ---- 1b. 曲线 / 灯光 / 相机 ----
    spline_total = sum(o.get("splines", 0) for o in curves)
    unique_curves = len({_base_name(o["name"]) for o in curves})
    cl_h = (unique_curves * RATES["curve_per_spline"]
            + (len(curves) - unique_curves) * RATES["instance_place"]
            + len(lights_cams) * RATES["light_camera"])
    if cl_h > 0:
        add("curve_light", "曲线 / 灯光相机布置",
            cl_h * 0.6, cl_h, cl_h * 1.6,
            f"{len(curves)} 条曲线 → 去重后 {unique_curves} 条"
            f"（{spline_total} 条样条）+ {len(lights_cams)} 个灯光/相机")

    # ---- 2. 重拓扑 ----
    # 原模型拓扑已规整的话，人工建模时直接建成规整拓扑即可，
    # 不存在「先做高模再重拓扑」这一额外步骤。
    retopo_h = 0.0
    sculpt_meshes = [m for m in meshes if m["tris"] > 500 and m["quad_ratio"] < 0.8]
    if sculpt_meshes:
        st = sum(m["tris"] for m in sculpt_meshes)
        retopo_h = st / 1000 * RATES["retopo_per_1k_tris"]
        basis = (f"{len(sculpt_meshes)} 个非规整网格（{st} 三角面）"
                 f"× {RATES['retopo_per_1k_tris']}h/千面 —— 需手工重建边流")
    else:
        basis = ("原模型拓扑已规整（四边形占比高、无 n-gon），"
                 "人工建模时直接建成规整拓扑即可，无需额外重拓扑")
    add("retopo", "拓扑优化 / 重拓扑", retopo_h * 0.7, retopo_h, retopo_h * 1.5, basis)

    # ---- 3. UV 展开 ----
    small_uv = 0
    big_uv = 0
    for (bn, tris), obs in groups.items():
        uv = obs[0]["n_uv_layers"]      # 同款实例的 UV 随复制一起继承，只算一次
        if uv == 0:
            continue
        if tris <= RATES["small_part_thresh"]:
            small_uv += uv
        else:
            big_uv += uv
    uv_h = big_uv * RATES["uv_per_map"] + small_uv * RATES["uv_small"]
    add("uv", "UV 展开", uv_h * 0.7, uv_h, uv_h * 1.5,
        f"主体 {big_uv} 张 UV 图 × {RATES['uv_per_map']}h "
        f"+ 小件 {small_uv} 张 × {RATES['uv_small']}h")

    # ---- 4. 材质 ----
    mat_h = 0.0
    proc_mats = 0
    total_nodes = 0
    for mat in data["materials"]:
        if mat["node_count"] == 0:
            continue
        total_nodes += mat["node_count"]
        h = RATES["material_base"] + mat["node_count"] * RATES["material_node"]
        if mat["is_procedural"]:
            h += RATES["procedural_heavy"]
            proc_mats += 1
        mat_h += h
    add("material", "材质制作", mat_h * 0.7, mat_h, mat_h * 1.7,
        f"{len(data['materials'])} 个材质 / {total_nodes} 个节点"
        + (f"；{proc_mats} 个重度程序化，须逐个调参对齐观感" if proc_mats else ""))

    # ---- 5. 贴图重做 ----
    tex_h = sum(RATES["texture_recreate"] for i in data["images"]
                if i["source"] != "GENERATED")
    external = [i for i in data["images"] if i["source"] == "FILE" and not i["packed"]]
    add("texture", "贴图重绘 / 重制", tex_h * 0.6, tex_h, tex_h * 1.6,
        (f"{len(data['images'])} 张贴图，无源 PSD 需从成品反推重绘"
         + (f"；{len(external)} 张为外链文件（有丢失风险）" if external else ""))
        if data["images"] else "无贴图资源（观感由程序化节点承担）")

    # ---- 6. 程序化系统（隐性成本核心）----
    geo_h = 0.0
    geo_detail = []
    for g in data["node_groups"]:
        if g["type"] == "GEOMETRY" or g["node_count"] >= 3:
            geo_h += RATES["geonodes_base"] + g["node_count"] * RATES["geonodes_per_node"]
            geo_detail.append(f"{g['name']}({g['node_count']}节点)")
    add("procedural", "程序化系统重建", geo_h * 0.8, geo_h, geo_h * 1.8,
        ("、".join(geo_detail) if geo_detail else "无几何节点组")
        + "；此部分看成品无法察觉，须从零推导逻辑")

    # ---- 7. 绑定 ----
    bind_h = 0.0
    bones = 0
    for a in armatures:
        bones += a.get("bones", 0)
        bind_h += a.get("bones", 0) * RATES["bone"] + 1.0
    add("rig", "骨骼绑定", bind_h * 0.7, bind_h, bind_h * 1.6,
        f"{len(armatures)} 套骨架 / {bones} 根骨骼" if armatures else "无骨骼")

    # ---- 8. 动画 ----
    anim_h = 0.0
    kf_total = 0
    for a in data["actions"]:
        kf_total += a["keyframes"]
        anim_h += RATES["action_base"] + a["keyframes"] / 100 * RATES["keyframe_per_100"]
    add("anim", "动画", anim_h * 0.6, anim_h, anim_h * 1.7,
        f"{len(data['actions'])} 个动作 / {kf_total} 关键帧" if data["actions"] else "无动画")

    # ---- 9. 脚本逆向 ----
    # 区分「生成脚本」与「工具/检查脚本」：前者必须逆向，后者只需理解用途。
    script_h = 0.0
    script_detail = []
    for t in data["texts"]:
        if t.get("looks_generative"):
            script_h += RATES["script_reverse"] + t["lines"] / 100 * RATES["script_per_100_lines"]
            script_detail.append(f"{t['name']}（{t['lines']}行·疑似生成脚本）")
        else:
            script_h += RATES["script_utility"]
            script_detail.append(f"{t['name']}（{t['lines']}行·工具脚本，仅需理解用途）")
    add("script", "脚本逆向", script_h * 0.5, script_h, script_h * 2.0,
        "、".join(script_detail) if script_detail else "文件内无文本脚本块")

    # ---- 10. 前置准备 ----
    add("prep", "参考采集 / 比例测量",
        RATES["prep_reference"] * 0.7, RATES["prep_reference"],
        RATES["prep_reference"] * 1.8,
        "确定尺度、比例关系、对称轴、结构分解")

    low = sum(d["low"] for d in dims)
    mid = sum(d["mid"] for d in dims)
    high = sum(d["high"] for d in dims)

    # ---- 外观等价折让 ----
    # 人工会把大量微碎件合并处理，产出视觉一致但结构更简洁的模型。
    model_mid = next(d["mid"] for d in dims if d["key"] == "model")
    consolidation = 0.60 if diag["small_parts"] > 100 else (
        0.80 if diag["small_parts"] > 40 else 1.0)
    appear_mid = mid - model_mid * (1 - consolidation)

    mat_proc_h = proc_mats * RATES["procedural_heavy"]
    hidden = sum(d["mid"] for d in dims if d["key"] in ("procedural", "script"))
    hidden += mat_proc_h + len(data["drivers"]) * 0.5

    level, note = "极易", ""
    for band, name, desc in DIFFICULTY_BANDS:
        if appear_mid < band:
            level, note = name, desc
            break

    total = {
        "low": round(low, 1), "mid": round(mid, 1), "high": round(high, 1),
        "appear_mid": round(appear_mid, 1),
        "consolidation": consolidation,
        "level": level, "level_note": note,
        "hidden_hours": round(hidden, 1),
        "hidden_ratio": round(hidden / mid, 3) if mid > 0 else 0.0,
        "structure": diag,
    }
    return dims, total


def build_steps(data, dims, diag):
    d = {x["key"]: x for x in dims}
    meshes = [o for o in data["objects"] if o["type"] == "MESH"]
    # 人工关心的是「要建几种部件」，不是「场景里有多少个物体」——
    # 所以按去重后的唯一部件名生成清单。
    seen = []
    for m in sorted(meshes, key=lambda x: -x["tris"]):
        bn = _base_name(m["name"])
        if bn not in seen:
            seen.append(bn)
    names = seen[:5]
    more = (f" 等 {len(seen)} 种部件（共 {diag['mesh_objects']} 个物体，"
            f"其中 {diag['dup_instances']} 个为复制）") if len(seen) > 5 else ""

    def sc(dim, f):
        return {"low": round(dim["low"] * f, 2), "mid": round(dim["mid"] * f, 2),
                "high": round(dim["high"] * f, 2), "basis": dim["basis"]}

    steps = [
        ("1", "采集参考与测量比例",
         "多角度观察，确定整体尺寸、比例关系、对称轴与结构分解方式。此步决定后续误差上限。",
         d["prep"]),
        ("2", "体块搭建（Blockout）",
         f"用基本体摆出体量与位置：{', '.join(names)}{more}。只求比例正确。",
         sc(d["model"], 0.25)),
        ("3", "主体建模与塑形",
         f"逐部件塑形，目标 {sum(m['tris'] for m in meshes)} 三角面。"
         "同款部件建一个模板后复制即可，不必逐个重做。",
         sc(d["model"], 0.60)),
        ("4", "细节刻画",
         "倒角、凹槽、纹饰、边缘厚度。细节密度决定成品是否「像」，也最容易被低估。",
         sc(d["model"], 0.15)),
    ]
    def nxt():
        """动态编号——跳过零工时的步骤，编号保持连续。"""
        return str(len(steps) + 1)

    if d["retopo"]["mid"] > 0:
        steps.append((nxt(), "拓扑优化 / 重拓扑",
                      "重建均匀边流，清理非流形边与 n-gon。", d["retopo"]))
    if d["uv"]["mid"] > 0:
        steps.append((nxt(), "UV 展开与排布",
                      "按材质划分 UV 岛，处理接缝与纹素密度一致性。", d["uv"]))
    if d["material"]["mid"] > 0:
        steps.append((nxt(), "材质制作",
                      "重建着色节点链。程序化部分须逐个调参对齐观感——"
                      "这是旧文件最难复现的环节之一。", d["material"]))
    if d["texture"]["mid"] > 0:
        steps.append((nxt(), "贴图重绘",
                      "无源文件时需从成品反推重绘，或改用程序化方案替代。", d["texture"]))
    if d.get("curve_light", {}).get("mid", 0) > 0:
        steps.append((nxt(), "曲线 / 灯光相机布置",
                      "重建曲线样条走线与镜头布光。", d["curve_light"]))
    if d["procedural"]["mid"] > 0:
        steps.append((nxt(), "⚠ 程序化系统重建",
                      "几何节点组须从零推导生成逻辑（输入参数、迭代规则、随机种子）。"
                      "成品只能看到结果，看不到规则——工时具有高度不确定性。",
                      d["procedural"]))
    if d["rig"]["mid"] > 0:
        steps.append((nxt(), "骨骼绑定",
                      "搭建骨架层级、蒙皮权重、修正变形瑕疵。", d["rig"]))
    if d["anim"]["mid"] > 0:
        steps.append((nxt(), "动画制作",
                      "按原动作节奏重做曲线，含缓入缓出与插值方式。", d["anim"]))
    if d["script"]["mid"] > 0:
        steps.append(("★", "⚠ 脚本逆向",
                      "文件内含文本脚本块。须先读懂其用途，再决定是重写还是手工替代。",
                      d["script"]))
    steps.append(("末", "组织、命名与优化",
                  "集合层级、命名规范、变换归零、导出前清理。"
                  + (f"注意原文件残留了 {diag['dup_instances']} 个实例与 "
                     f"{diag['small_parts']} 个小件，人工产出应主动归并。"
                     if diag["dup_instances"] or diag["small_parts"] > 30 else ""),
                  {"low": 0.3, "mid": 0.5, "high": 1.0, "basis": "常规收尾"}))
    return steps


# ============================================================================
# 六、报告生成
# ============================================================================

def fmt_h(v):
    return f"{v:.1f}h"


def esc(s):
    """转义 Markdown 表格里的管道符——物体名/材质名常含 | 。"""
    return str(s).replace("|", "\\|")


def write_report(data, dims, total, steps, out_dir, label):
    diag = total["structure"]
    meshes = [o for o in data["objects"] if o["type"] == "MESH"]
    total_tris = sum(m["tris"] for m in meshes)
    L = []
    A = L.append

    A(f"# 模型复现难度审计报告 · {label}")
    A("")
    A(f"- **文件**：`{data['filepath']}`")
    A(f"- **Blender**：{data['blender_version']}")
    A(f"- **审计时间**：{data['audited_at']}")
    A("")
    A("---")
    A("")
    A("## 一、结论摘要")
    A("")
    A("| 项目 | 结果 |")
    A("|---|---|")
    A(f"| **难度等级** | **{total['level']}** —— {total['level_note']} |")
    A(f"| **外观等价复现**（推荐参考值） | **{fmt_h(total['appear_mid'])}** |")
    A(f"| 结构等价复现（1:1 照原结构） | {fmt_h(total['mid'])}"
      f"（区间 {fmt_h(total['low'])} – {fmt_h(total['high'])}）|")
    A(f"| 其中隐性成本 | {fmt_h(total['hidden_hours'])}"
      f"（占 {total['hidden_ratio']*100:.0f}%）—— 看成品无法察觉的部分 |")
    A(f"| 网格规模 | {len(meshes)} 个网格 → 去重后 {diag['unique_parts']} 个唯一部件 |")
    A(f"| 三角面 | {total_tris} |")
    A(f"| 材质 | {diag['total_materials']} 个（其中 {diag['proc_materials']} 个重度程序化）|")
    A(f"| 几何节点组 | {len(data['node_groups'])} 个 |")
    A(f"| 文本脚本块 | {len(data['texts'])} 个 |")
    A(f"| 动画动作 | {len(data['actions'])} 个 |")
    A("")
    A("> **两个数字的区别**：")
    A(f"> - **结构等价** {fmt_h(total['mid'])}：连原模型「把每个零件拆成独立物体」的"
      f"组织方式一起复刻。AI 这么拆是生成机制使然，人工不必如此。")
    A(f"> - **外观等价** {fmt_h(total['appear_mid'])}：产出视觉一致的模型，"
      f"但按人的合理方式组织（合并微碎件、复用模板，折让系数 {total['consolidation']:.2f}）。"
      f"**这个才是「人工复现」的真实成本。**")
    A("")
    if total["hidden_hours"] > total["mid"] * 0.2:
        A(f"> ⚠ **隐性成本 {total['hidden_ratio']*100:.0f}%**：即使一比一临摹外观，"
          "也无法复现它的**行为**——程序化材质、几何节点、脚本逻辑只能重建，不能临摹。")
        A("")

    # ---- 结构诊断 ----
    A("## 二、结构特征诊断")
    A("")
    traits = ai_traits(diag)
    if traits:
        A("以下特征直接暴露了该资产的生成方式：")
        A("")
        for t in traits:
            A(f"- {t}")
        A("")
    else:
        A("_未检出明显的自动化生成特征，结构组织接近人工制作习惯。_")
        A("")
    A("| 指标 | 数值 |")
    A("|---|---|")
    A(f"| 网格物体 | {diag['mesh_objects']} |")
    A(f"| 唯一部件（去重后） | {diag['unique_parts']} |")
    A(f"| 复制实例 | {diag['dup_instances']}（去重率 {diag['dedup_ratio']*100:.0f}%）|")
    A(f"| 小件（≤{RATES['small_part_thresh']} 三角面）| {diag['small_parts']}"
      f"（占 {diag['small_ratio']*100:.0f}%）|")
    A(f"| 集合总数 / 阶段化 / 重复 | {diag['collections']} / "
      f"{len(diag['phase_collections'])} / {len(diag['dup_collections'])} |")
    A(f"| 残留默认命名 | {diag['default_named_count']} |")
    A(f"| 全部物体总数（含曲线/灯光/相机）| {diag['total_objects']} |")
    A("")
    if diag["phase_collections"]:
        A("**阶段化集合**（多轮增量生成的证据）：")
        A("")
        for c in diag["phase_collections"]:
            A(f"- `{c}`")
        A("")
    A("**资源完整度**：" + "、".join([
        f"UV {'✅' if diag['has_uv'] else '❌'}",
        f"贴图 {'✅' if diag['has_textures'] else '❌'}",
        f"骨骼 {'✅' if diag['has_rig'] else '❌'}",
        f"动画 {'✅' if diag['has_anim'] else '❌'}",
        f"几何节点 {'✅' if diag['has_geonodes'] else '❌'}",
    ]))
    A("")

    # ---- 原始指标 ----
    A("## 三、结构指标（原始数据）")
    A("")
    A("### 3.1 网格物体（按三角面降序，前 25 个）")
    A("")
    A("| 物体 | 三角面 | 顶点 | 四边形占比 | n-gon | UV | 修改器 |")
    A("|---|---:|---:|---:|---:|---:|---|")
    for m in sorted(meshes, key=lambda x: -x["tris"])[:25]:
        mods = ",".join(x["type"] for x in m["modifiers"]) or "—"
        A(f"| `{esc(m['name'])}` | {m['tris']} | {m['verts']} | {m['quad_ratio']*100:.1f}% "
          f"| {m['ngons']} | {m['n_uv_layers']} | {mods} |")
    if len(meshes) > 25:
        A(f"| _…其余 {len(meshes)-25} 个略_ | | | | | | |")
    A("")

    non_mesh = [o for o in data["objects"] if o["type"] != "MESH"]
    if non_mesh:
        A("### 3.2 非网格物体")
        A("")
        A("| 物体 | 类型 | 备注 |")
        A("|---|---|---|")
        for o in non_mesh[:30]:
            note = ""
            if o["type"] == "ARMATURE":
                note = f"{o.get('bones',0)} 骨骼，层级深度 {o.get('bone_tree_depth',0)}"
            elif o["type"] == "CURVE":
                note = f"{o.get('splines',0)} 条样条"
            A(f"| `{esc(o['name'])}` | {o['type']} | {note} |")
        if len(non_mesh) > 30:
            A(f"| _…其余 {len(non_mesh)-30} 个略_ | | |")
        A("")

    if data["materials"]:
        A("### 3.3 材质节点复杂度")
        A("")
        A("| 材质 | 节点数 | 程序化节点 | 贴图节点 | 判定 |")
        A("|---|---:|---:|---:|---|")
        for m in sorted(data["materials"], key=lambda x: -x["node_count"])[:30]:
            flag = ("🔴 重度程序化" if m["is_procedural"]
                    else ("🟡 轻度程序化" if m["procedural_nodes"] else "🟢 贴图驱动"))
            A(f"| `{esc(m['name'])}` | {m['node_count']} | {m['procedural_nodes']} "
              f"| {len(m['image_nodes'])} | {flag} |")
        if len(data["materials"]) > 30:
            A(f"| _…其余 {len(data['materials'])-30} 个略_ | | | | |")
        A("")

    if data["node_groups"]:
        A("### 3.4 节点组（程序化系统）")
        A("")
        A("| 组名 | 类型 | 节点数 | 连线数 |")
        A("|---|---|---:|---:|")
        for g in sorted(data["node_groups"], key=lambda x: -x["node_count"]):
            A(f"| `{esc(g['name'])}` | {g['type']} | {g['node_count']} | {g['link_count']} |")
        A("")

    A("### 3.5 文件内文本脚本块")
    A("")
    if data["texts"]:
        A("| 名称 | 行数 | 字符数 | 判定 |")
        A("|---|---:|---:|---|")
        for t in data["texts"]:
            if t.get("looks_generative"):
                verdict = "⚠ 疑似生成脚本（含建模 API 调用）"
            elif t.get("looks_utility"):
                verdict = "工具 / 检查脚本（不参与复现）"
            else:
                verdict = "用途不明"
            A(f"| `{esc(t['name'])}` | {t['lines']} | {t['chars']} | {verdict} |")
        A("")
        for t in data["texts"]:
            A(f"<details><summary>展开 <code>{t['name']}</code> 开头片段</summary>")
            A("")
            A("```python")
            A(t["head"])
            A("```")
            A("")
            A("</details>")
            A("")
    else:
        A("**文件内没有文本脚本块。**")
        A("")
        A("> 关键事实：如果这个模型确实是脚本生成的，那么生成脚本**不在这个文件里**。"
          "它现在只以「结果」的形式存在——几何数据。规则、参数、随机种子已经丢失。")
        A("")

    if data["images"]:
        A("### 3.6 贴图资源")
        A("")
        A("| 名称 | 尺寸 | 来源 | 已打包 | 外链路径 |")
        A("|---|---|---|---|---|")
        for i in data["images"][:30]:
            A(f"| `{esc(i['name'])}` | {i['size'][0]}×{i['size'][1]} | {i['source']} "
              f"| {'是' if i['packed'] else '否'} | `{i['filepath'] or '—'}` |")
        A("")
    else:
        A("### 3.6 贴图资源")
        A("")
        A("**无任何贴图。**观感完全由程序化材质节点承担——"
          "这意味着外观与节点参数强耦合，改一个值观感就变。")
        A("")

    if data["actions"]:
        A("### 3.7 动画")
        A("")
        A("| 动作 | F-Curve | 关键帧 |")
        A("|---|---:|---:|")
        for a in data["actions"]:
            A(f"| `{esc(a['name'])}` | {a['fcurves']} | {a['keyframes']} |")
        A("")

    # ---- 工时分解 ----
    A("## 四、分维度工时估算")
    A("")
    A("| 维度 | 低 | 中 | 高 | 计量依据 |")
    A("|---|---:|---:|---:|---|")
    for d in dims:
        if d["mid"] == 0:
            continue
        A(f"| {d['label']} | {fmt_h(d['low'])} | **{fmt_h(d['mid'])}** | {fmt_h(d['high'])} "
          f"| {esc(d['basis'])} |")
    A(f"| **合计** | **{fmt_h(total['low'])}** | **{fmt_h(total['mid'])}** "
      f"| **{fmt_h(total['high'])}** | — |")
    A("")
    A(f"**外观等价复现**：**{fmt_h(total['appear_mid'])}**"
      f"（建模维度按 {total['consolidation']:.2f} 折让，其余维度不变）")
    A("")
    A("> 工时基准：熟练 3D 建模师（非新手、非顶尖），**无参考脚本、仅凭观察成品**。"
      "区间下沿 = 顺利且经验充足；上沿 = 反复返工。")
    A("")

    # ---- 步骤清单 ----
    A("## 五、复现步骤清单")
    A("")
    A("按执行顺序排列。工时为该步骤的**中位估算**。")
    A("")
    A("| # | 步骤 | 说明 | 低 | 中 | 高 |")
    A("|---|---|---|---:|---:|---:|")
    for num, title, desc, dim in steps:
        A(f"| {num} | **{title}** | {esc(desc)} | {fmt_h(dim['low'])} | **{fmt_h(dim['mid'])}** "
          f"| {fmt_h(dim['high'])} |")
    A("")

    # ---- 隐性成本 ----
    A("## 六、隐性成本警告")
    A("")
    A("以下部分**无法通过观察成品还原**——只能看到「是什么样」，看不到「为什么是这样」。")
    A("")
    risky = [d for d in dims
             if d["key"] in ("procedural", "script", "material", "rig", "anim")
             and d["mid"] > 0]
    if risky:
        A("| 风险项 | 中位工时 | 为什么无法凭观察复现 |")
        A("|---|---:|---|")
        if any(d["key"] == "procedural" for d in risky):
            A(f"| 几何节点 / 程序化系统 | "
              f"{fmt_h(next(d['mid'] for d in dims if d['key']=='procedural'))} "
              "| 成品只呈现一次运算结果。参数、随机种子、迭代规则全部不可见。 |")
        if any(d["key"] == "material" for d in risky):
            A(f"| 程序化材质 | "
              f"{fmt_h(next(d['mid'] for d in dims if d['key']=='material'))} "
              "| 噪声 / 沃罗诺伊链的节点连线与参数，看成品完全不可推断，只能反复试参对齐。 |")
        if any(d["key"] == "script" for d in risky):
            A(f"| 文本脚本块 | "
              f"{fmt_h(next(d['mid'] for d in dims if d['key']=='script'))} "
              "| 须逐行读懂逻辑后重写，且原代码可能已被删除。 |")
        if any(d["key"] == "rig" for d in risky):
            A(f"| 骨骼权重 | "
              f"{fmt_h(next(d['mid'] for d in dims if d['key']=='rig'))} "
              "| 权重分布不可见，只能靠变形表现反推。 |")
        if any(d["key"] == "anim" for d in risky):
            A(f"| 动画曲线插值 | "
              f"{fmt_h(next(d['mid'] for d in dims if d['key']=='anim'))} "
              "| 缓入缓出与插值方式影响手感，需反复比对。 |")
        A("")
    else:
        A("_未检出明显的程序化 / 脚本 / 绑定 / 动画成分，隐性成本低。_")
        A("")
    A(f"**隐性成本合计：{fmt_h(total['hidden_hours'])}，占总工时的 "
      f"{total['hidden_ratio']*100:.0f}%。**")
    A("")

    # ---- 脚本存档判定 ----
    A("## 七、生成脚本的存档判定")
    A("")
    gen_scripts = [t for t in data["texts"] if t.get("looks_generative")]
    if gen_scripts or data["node_groups"] or data["drivers"]:
        A("**结论：必须存档。**")
        A("")
        A("本文件检出了程序化成分：")
        if data["node_groups"]:
            A(f"- 几何节点组 {len(data['node_groups'])} 个")
        if gen_scripts:
            A(f"- 疑似生成脚本 {len(gen_scripts)} 个")
        if data["drivers"]:
            A(f"- 驱动器 {len(data['drivers'])} 条")
        A("")
        A("这些是模型的「行为定义」，不是「外观结果」。"
          "丢掉之后人工只能复现外观，无法复现行为。")
    else:
        A("**结论：属于「静态资产」，生成脚本可不必长期存档——但有条件。**")
        A("")
        A("- ✅ **不必存**：若生成脚本只做过一次性造型，产物已是完整可编辑网格，"
          "且确定不会再改结构。")
        A("- ⚠ **仍应存**：脚本里编码了你的**决策**——对话中确认过的比例、命名、"
          "层级、材质参数。这些信息不在网格数据里，重新生成会漂移。")
        A("- 📌 **建议**：把生成脚本（含提示词全文）与产出一并存档。"
          "成本是几 KB 文本，收益是模型永远可重造、可追溯、可对比迭代。")
        A("")
        if data["materials"]:
            A(f"- 🔴 **本文件特别提示**：{diag['proc_materials']} 个材质全部是程序化的，"
              f"且无贴图。若这些材质的节点参数是生成脚本里定义的，"
              f"那么**丢掉脚本等于丢掉全部材质规格**——"
              f"人工只能靠肉眼反推 {fmt_h(next(d['mid'] for d in dims if d['key']=='material'))} "
              f"的材质工时才能还原观感。仅此一项，就足以决定「必须存档」。")
            A("")
    A("")
    A("---")
    A("")
    A(f"_由 `blend_repro_audit.py` 生成 · Blender {data['blender_version']} · "
      f"{data['audited_at']}_")
    A("")

    md_path = os.path.join(out_dir, "audit_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    json_path = os.path.join(out_dir, "audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"raw": data, "dimensions": dims, "total": total},
                  f, ensure_ascii=False, indent=2)
    return md_path, json_path


# ============================================================================
# 七、入口
# ============================================================================

def main():
    args = parse_args()

    if args.import_path:
        p = os.path.abspath(args.import_path)
        bpy.ops.wm.read_homefile(use_empty=True)
        ext = os.path.splitext(p)[1].lower()
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=p)
        elif ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=p)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=p)
        elif ext in (".usd", ".usda", ".usdc", ".usdz"):
            bpy.ops.wm.usd_import(filepath=p)
        else:
            raise SystemExit(f"不支持的格式：{ext}")
        bpy.data.filepath = p

    data = collect_all()
    meshes = [o for o in data["objects"] if o["type"] == "MESH"]
    if not data["objects"]:
        print("[warn] 场景中没有任何物体")

    diag = diagnose(data, meshes)
    dims, total = estimate(data, meshes, diag)
    steps = build_steps(data, dims, diag)

    src = args.import_path or bpy.data.filepath or os.getcwd()
    out_dir = os.path.abspath(args.out or os.path.dirname(os.path.abspath(src)) or os.getcwd())
    os.makedirs(out_dir, exist_ok=True)

    label = args.label or os.path.splitext(os.path.basename(src))[0]
    md_path, json_path = write_report(data, dims, total, steps, out_dir, label)

    print("\n" + "=" * 66)
    print("AUDIT RESULT")
    print("=" * 66)
    print(json.dumps({
        "difficulty": total["level"],
        "hours_appearance_equivalent": total["appear_mid"],
        "hours_structural_equivalent": total["mid"],
        "hours_range": [total["low"], total["high"]],
        "hidden_hours": total["hidden_hours"],
        "hidden_ratio": total["hidden_ratio"],
        "structure": total["structure"],
        "report_md": md_path,
        "report_json": json_path,
    }, ensure_ascii=False, indent=2))
    print("=" * 66)
    if data["warnings"]:
        print("WARNINGS:", json.dumps(data["warnings"][:10], ensure_ascii=False))


if __name__ == "__main__":
    main()
