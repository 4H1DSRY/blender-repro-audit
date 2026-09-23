# -*- coding: utf-8 -*-
"""check_abs_paths.py —— 只读体检：`.blend` 里还剩哪些指向作者本机的绝对路径。

查三类载体：图像数据块 `image.filepath`、链接库 `library.filepath`、
内嵌 Text 数据块的正文。可以一次传多个文件。

    blender.exe -b -noaudio -P check_abs_paths.py -- <a.blend> [<b.blend> ...]

每个文件打印一份 JSON。和 `strip_embedded_scripts.py`（清 Text 块）、
`sanitize_blend_paths.py`（清图像路径）一起构成交付前的卫生三件套：
前者清内容，后两者清路径，清完再用 `compare_blends.py` 证明场景没变。
"""
import json
import os
import re
import sys

import bpy

PATH_RE = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/")
out = []
for p in sys.argv[sys.argv.index("--") + 1:]:
    bpy.ops.wm.open_mainfile(filepath=p)
    abs_img = [i.filepath for i in bpy.data.images if i.filepath and PATH_RE.search(i.filepath)]
    abs_lib = [l.filepath for l in bpy.data.libraries if l.filepath and PATH_RE.search(l.filepath)]
    texts = [t.name for t in bpy.data.texts]
    abs_txt = []
    for t in bpy.data.texts:
        for n, line in enumerate(t.as_string().splitlines(), 1):
            if PATH_RE.search(line):
                abs_txt.append(f"{t.name}:{n}: {line.strip()[:120]}")
    out.append({
        "file": os.path.basename(p),
        "images_total": len(bpy.data.images),
        "images_absolute_path": len(abs_img),
        "images_absolute_sample": abs_img[:4],
        "libraries_absolute": len(abs_lib),
        "texts": texts,
        "absolute_paths_in_texts": abs_txt[:6],
        "filepath_setting": bpy.data.filepath.replace("\\", "/"),
    })

print("=== ABS PATH JSON ===")
print(json.dumps(out, ensure_ascii=False, indent=1))
