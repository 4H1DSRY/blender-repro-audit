# -*- coding: utf-8 -*-
"""sanitize_blend_paths.py —— 交付前把 `.blend` 里的**作者本机绝对路径**改写成相对路径。

为什么需要：`.blend` 会把图像数据块的 `filepath` 原样存下来。贴图即使已经打包
（`image.packed_file` 非空，渲染与打开都不依赖外部文件），`filepath` 仍然指着作者的磁盘 ——
交付出去等于把自己的目录结构、工作目录名一并给了对方。

判据只有一条：`image.filepath` 是否匹配盘符 / `/Users/` / `/home/` 前缀。
命中就改写成相对路径，未命中一律不动。

用法：
    blender.exe -b -noaudio <file.blend> -P sanitize_blend_paths.py -- [--save-as <out.blend>]

不传 `--save-as` 就原地覆盖，建议先备份。

改完务必用 `compare_blends.py` 证明「只改了路径」：

    blender.exe -b <原文件> -P compare_blends.py -- --save fp_before.json
    blender.exe -b <新文件> -P compare_blends.py -- --save fp_after.json
    python compare_blends.py --diff fp_before.json fp_after.json

两条指纹摘要应当完全一致。配套只读体检：`check_abs_paths.py`。
"""
import os
import re
import sys

import bpy

ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/Users/|/home/|//?[A-Za-z]:)")
REL_DIR = "//baked_textures/"

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
save_as = argv[argv.index("--save-as") + 1] if "--save-as" in argv else bpy.data.filepath

changed = []
kept = []
for img in bpy.data.images:
    old = img.filepath
    if not old:
        kept.append((img.name, "(empty)"))
        continue
    if ABS_RE.match(old):
        img.filepath = REL_DIR + os.path.basename(old.replace("\\", "/"))
        changed.append((img.name, old, img.filepath))
    else:
        kept.append((img.name, old))

print("=== SANITIZE ===")
print(f"file          : {bpy.data.filepath}")
print(f"save to       : {save_as}")
print(f"images total  : {len(bpy.data.images)}")
print(f"rewritten     : {len(changed)}")
print(f"left alone    : {len(kept)}")
for name, old, new in changed[:3]:
    print(f"   {name}: {old}  ->  {new}")
if len(changed) > 3:
    print(f"   ... and {len(changed) - 3} more")
still_abs = [i.filepath for i in bpy.data.images if ABS_RE.match(i.filepath or "")]
print(f"still absolute: {len(still_abs)}")
print(f"packed images : {sum(1 for i in bpy.data.images if i.packed_file)}")
print(f"texts         : {[t.name for t in bpy.data.texts]}")

if changed:
    bpy.ops.wm.save_as_mainfile(filepath=save_as)
    print(f"SAVED {save_as}  {os.path.getsize(save_as)} bytes")
else:
    print("nothing to rewrite, not saving")
