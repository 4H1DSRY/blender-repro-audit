# -*- coding: utf-8 -*-
"""根据 parts_manifest.csv 与已导出的 glb 目录，生成 _INDEX.csv"""
import csv, os, re, sys

SAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def safe_name(s, limit=80):
    s = SAFE_RE.sub("_", s).strip().strip(".")
    return (s[:limit] or "unnamed")

manifest = sys.argv[1]
glb_dir  = sys.argv[2]

rows = []
with open(manifest, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)

# (目录名, 文件名主干) -> 行
# 注意：物体名里的 "|" 在导出时被 safe_name 换成 "_"（如
# "Great bell | hollow cast shell" -> "Great bell _ hollow cast shell"），
# 所以这里必须用 safe_name(object_name) 建键，不能用原始名。
lookup = {(safe_name(r["family"], 40), safe_name(r["object_name"])): r
          for r in rows if r["is_representative"] == "YES"}

out = []
missing = []
for root, dirs, files in os.walk(glb_dir):
    for fn in files:
        if not fn.lower().endswith(".glb"):
            continue
        fam_dir = os.path.basename(root)
        stem = fn[:-4]
        # 去掉 __n<N> / __g<N> 后缀
        base = re.sub(r"__(n\d+|g\d+)$", "", stem)
        r = lookup.get((fam_dir, base))
        if r is None:
            missing.append(os.path.join(fam_dir, fn))
            continue
        rel = "%s/%s" % (fam_dir, fn)
        size = os.path.getsize(os.path.join(root, fn))
        out.append({
            "file": rel,
            "family": r["family"],
            "members": r["members_in_group"],
            "tris": r["tris"],
            "verts": r["verts"],
            "dim_x": r["dim_x"], "dim_y": r["dim_y"], "dim_z": r["dim_z"],
            "materials": r["materials"],
            "bytes": size,
        })

out.sort(key=lambda d: (-int(d["members"]), d["family"], d["file"]))

cols = ["file", "family", "members", "tris", "verts",
        "dim_x", "dim_y", "dim_z", "materials", "bytes"]
dst = os.path.join(glb_dir, "_INDEX.csv")
with open(dst, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out)

tot_members = sum(int(d["members"]) for d in out)
print("索引写入: %s" % dst)
print("文件数: %d / 覆盖实例: %d / 未匹配: %d" % (len(out), tot_members, len(missing)))
for m in missing[:10]:
    print("  ! %s" % m)
