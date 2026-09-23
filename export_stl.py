# -*- coding: utf-8 -*-
"""
export_stl.py —— 把整座场景导成**单个 STL**，供浏览器 / 评审直接旋转查看

为什么需要它
------------
GitHub 只把 `.stl` 当 3D 模型渲染（`.glb` 与 `.blend` 都不会预览，见 GitHub Docs
"Working with non-code files"），且单文件上限 10 MB。所以交付里放两份导出、
各司其职：

    .glb   带 PBR 贴图，给引擎 / XR —— bake_curves_and_export.py 产出
    .stl   只有几何，给浏览器 / 评审 —— 本脚本产出

先把 `CURVE` / `SURFACE` / `FONT` / `META` 转成网格再导出：STL 只吃网格，
不转换的话这些物体会被静默丢掉（见 PITFALLS.md 第 3 条）。

用法
----
    blender.exe -b scene/scene.blend -P export_stl.py -- --out out/scene.stl

不给 `--out` 时，输出到 `<输入文件同目录>/<输入文件名>.stl`。
脚本只读场景、不改场景，也不会回写 `.blend`。

默认**不**应用修改器（`BEVEL` 等），原因有三：
  1. 体积 —— 本场景基础几何 63,974 面 → binary STL 约 3.0 MB；
     应用倒角后涨到 211,526 面 → 10.09 MB，正好越过 GitHub 的 10 MB 预览上限。
  2. 口径一致 —— 基础面数与 `blend_repro_audit.py` 报出的 63,590 面同源，
     交付里的数字能互相对得上。
  3. 倒角是显示层的美化，不是建模出来的拓扑。
需要应用修改器时加 `--apply-modifiers`。
"""

import bpy
import json
import os
import sys
import time


CONVERTIBLE = ("CURVE", "SURFACE", "FONT", "META")
GITHUB_PREVIEW_LIMIT = 10 * 1024 * 1024   # 10 MB，GitHub 的 3D 预览上限


def parse_args():
    argv = sys.argv
    rest = argv[argv.index("--") + 1:] if "--" in argv else []
    out = None
    apply_modifiers = False
    i = 0
    while i < len(rest):
        if rest[i] == "--out" and i + 1 < len(rest):
            out = rest[i + 1]
            i += 2
        elif rest[i] == "--apply-modifiers":
            apply_modifiers = True
            i += 1
        else:
            i += 1
    return out, apply_modifiers


def convert_non_mesh(objects):
    """把非网格几何转成网格。返回成功转换的物体数。"""
    todo = [o for o in objects if o.type in CONVERTIBLE]
    if not todo:
        return 0
    bpy.ops.object.select_all(action="DESELECT")
    done = 0
    for o in todo:
        try:
            o.hide_set(False)
            o.select_set(True)
        except RuntimeError:
            continue
    if not any(o.select_get() for o in todo):
        return 0
    bpy.context.view_layer.objects.active = next(o for o in todo if o.select_get())
    try:
        bpy.ops.object.convert(target="MESH")
        done = len(todo)
    except RuntimeError as e:
        print(f"[warn] 非网格转换失败，这些物体会被 STL 丢掉：{e}")
    return done


def count_triangles(objects, apply_modifiers):
    """统计网格物体数与三角面数。应用修改器时按 evaluated 结果计。"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    n_mesh = 0
    n_tris = 0
    for o in objects:
        if o.type != "MESH":
            continue
        n_mesh += 1
        if apply_modifiers:
            ev = o.evaluated_get(depsgraph)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            n_tris += len(me.loop_triangles)
            ev.to_mesh_clear()
        else:
            me = o.data
            me.calc_loop_triangles()
            n_tris += len(me.loop_triangles)
    return n_mesh, n_tris


def main():
    t0 = time.time()

    out, apply_modifiers = parse_args()
    if not out:
        base = os.path.splitext(bpy.data.filepath or os.path.join(os.getcwd(), "scene"))[0]
        out = base + ".stl"
    out = os.path.abspath(out)
    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    converted = convert_non_mesh(list(bpy.data.objects))
    n_mesh, n_tris = count_triangles(list(bpy.data.objects), apply_modifiers)

    bpy.ops.wm.stl_export(
        filepath=out,
        export_selected_objects=False,
        apply_modifiers=apply_modifiers,
        ascii_format=False,      # binary：同几何下体积约为 ASCII 的 1/6
        global_scale=1.0,
    )

    size = os.path.getsize(out) if os.path.exists(out) else 0
    report = {
        "out": out,
        "bytes": size,
        "mib": round(size / 1048576, 2),
        "format": "binary STL",
        "modifiers_applied": apply_modifiers,
        "converted_to_mesh": converted,
        "mesh_objects": n_mesh,
        "triangles": n_tris,
        "github_preview_limit_mib": round(GITHUB_PREVIEW_LIMIT / 1048576, 1),
        "within_github_preview_limit": size <= GITHUB_PREVIEW_LIMIT,
        "seconds": round(time.time() - t0, 1),
    }

    print("\n" + "=" * 66)
    print("STL EXPORT RESULT")
    print("=" * 66)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("=" * 66)

    if not report["within_github_preview_limit"]:
        print("[warn] 超过 GitHub 的 10 MB 预览上限，在线查看会失败。"
              "考虑按部件拆分，或用 meshopt / Draco 先降面。")


if __name__ == "__main__":
    main()
