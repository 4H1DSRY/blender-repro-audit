"""Audit a .glb: are the baked textures actually wired up, or is it white again?

Plain Python — **no Blender required**.

    python audit_scene_glb.py scene.glb [--out report.txt]

Without `--out` the report goes to stdout and nothing is written to disk.

Why this exists: glTF export discards procedural node networks *silently*. There is no error and no
warning — the materials simply collapse to `baseColorFactor = [1,1,1,1]` and arrive as white models.
So the only way to know the bake worked is to assert against the produced artifact, not to trust the
exporter. This walks the GLB container itself and reports what is actually wired to what.
"""
import argparse
import json
import os
import struct

ap = argparse.ArgumentParser(description="Audit a .glb for real texture wiring")
ap.add_argument("glb", help="path to the .glb to inspect")
ap.add_argument("--out", default=None, help="also write the report to this file")
args = ap.parse_args()

path = args.glb

with open(path, "rb") as f:
    data = f.read()

magic, ver, length = struct.unpack_from("<III", data, 0)
assert magic == 0x46546C67, "not a glb"

off = 12
gltf = None
bin_chunk = None
while off < length:
    clen, ctype = struct.unpack_from("<II", data, off)
    body = data[off + 8: off + 8 + clen]
    if ctype == 0x4E4F534A:
        gltf = json.loads(body.decode("utf-8"))
    elif ctype == 0x004E4942:
        bin_chunk = body
    off += 8 + clen
    off += (-off) % 4

lines = []
def p(s=""):
    lines.append(str(s))

p(f"file            : {os.path.basename(path)}")
p(f"bytes           : {len(data):,} ({len(data)/1048576:.2f} MB)")
p(f"glTF version    : {gltf.get('asset', {}).get('version')}  generator={gltf.get('asset',{}).get('generator')}")
p()
p(f"nodes           : {len(gltf.get('nodes', []))}")
p(f"meshes          : {len(gltf.get('meshes', []))}")
p(f"materials       : {len(gltf.get('materials', []))}")
p(f"images          : {len(gltf.get('images', []))}")
p(f"textures        : {len(gltf.get('textures', []))}")
p(f"samplers        : {len(gltf.get('samplers', []))}")
p(f"cameras         : {len(gltf.get('cameras', []))}")
p(f"extensionsUsed  : {gltf.get('extensionsUsed')}")

# image byte sizes from bufferViews
bvs = gltf.get("bufferViews", [])
img_sizes = []
for img in gltf.get("images", []):
    bv = img.get("bufferView")
    if bv is not None:
        img_sizes.append(bvs[bv].get("byteLength", 0))
    else:
        img_sizes.append(0)
p(f"image bytes sum : {sum(img_sizes):,} ({sum(img_sizes)/1048576:.2f} MB)")

# ---- where do the bytes go? ----
img_bv = set(img.get("bufferView") for img in gltf.get("images", []) if img.get("bufferView") is not None)
tot_bv = sum(bv.get("byteLength", 0) for bv in bvs)
geo_bv = sum(bv.get("byteLength", 0) for i, bv in enumerate(bvs) if i not in img_bv)
p(f"bufferViews     : {len(bvs)}  bufferView bytes total = {tot_bv:,} ({tot_bv/1048576:.2f} MB)")
p(f"  -> image BVs  : {len(img_bv)}  = {sum(bvs[i].get('byteLength',0) for i in img_bv):,} bytes")
p(f"  -> geometry   : {len(bvs)-len(img_bv)} BVs = {geo_bv:,} bytes ({geo_bv/1048576:.2f} MB)")

acc_types = {}
for a in gltf.get("accessors", []):
    key = (a.get("type"), a.get("componentType"))
    acc_types[key] = acc_types.get(key, 0) + 1
p(f"accessors       : {len(gltf.get('accessors', []))}")
for k, v in sorted(acc_types.items(), key=lambda x: -x[1]):
    p(f"    {k}: {v}")
prim_count = sum(len(m.get("primitives", [])) for m in gltf.get("meshes", []))
p(f"mesh primitives : {prim_count}")

mimes = {}
for img in gltf.get("images", []):
    mimes[img.get("mimeType")] = mimes.get(img.get("mimeType"), 0) + 1
p(f"image mimeTypes : {mimes}")

# dedupe by bufferView offset+len (cheap proxy for duplication)
keys = []
for img in gltf.get("images", []):
    bv = img.get("bufferView")
    if bv is None:
        keys.append(None)
    else:
        keys.append((bvs[bv].get("byteOffset", 0), bvs[bv].get("byteLength", 0)))
uniq = len(set(k for k in keys if k))
p(f"unique img data : {uniq}  (duplicates: {len([k for k in keys if k]) - uniq})")
p()

# ---- material wiring ----
def tex_of(mat, kind):
    pbr = mat.get("pbrMetallicRoughness", {})
    if kind == "base":
        t = pbr.get("baseColorTexture")
    elif kind == "mr":
        t = pbr.get("metallicRoughnessTexture")
    elif kind == "normal":
        t = mat.get("normalTexture")
    elif kind == "emis":
        t = mat.get("emissiveTexture")
    else:
        t = None
    if not t:
        return None
    return t.get("index")

mats = gltf.get("materials", [])
n_base = n_mr = n_norm = n_emis = 0
white = []
texture_use = {}
for m in mats:
    i_base = tex_of(m, "base")
    i_mr = tex_of(m, "mr")
    i_norm = tex_of(m, "normal")
    i_emis = tex_of(m, "emis")
    if i_base is not None:
        n_base += 1
        texture_use[i_base] = texture_use.get(i_base, 0) + 1
    if i_mr is not None:
        n_mr += 1
    if i_norm is not None:
        n_norm += 1
    if i_emis is not None:
        n_emis += 1
    pbr = m.get("pbrMetallicRoughness", {})
    bcf = pbr.get("baseColorFactor", [1, 1, 1, 1])
    if i_base is None and bcf[:3] == [1, 1, 1]:
        white.append(m.get("name", "?"))

p(f"mat with baseColorTexture          : {n_base}/{len(mats)}")
p(f"mat with metallicRoughnessTexture  : {n_mr}/{len(mats)}")
p(f"mat with normalTexture             : {n_norm}/{len(mats)}")
p(f"mat with emissiveTexture           : {n_emis}/{len(mats)}")
p(f"materials still pure white (no tex) : {len(white)}")
for w in white[:12]:
    p(f"    - {w}")
p()
p(f"distinct base textures actually referenced : {len(texture_use)}")
p(f"most-reused base texture                   : {max(texture_use.values()) if texture_use else 0} materials")
p()

# sample a few materials
p("sample materials:")
for m in mats[:6]:
    pbr = m.get("pbrMetallicRoughness", {})
    p(f"  {m.get('name','?')[:44]:<46} "
      f"base={'T' if tex_of(m,'base') is not None else '-'} "
      f"mr={'T' if tex_of(m,'mr') is not None else '-'} "
      f"bcf={pbr.get('baseColorFactor')} "
      f"mf={pbr.get('metallicFactor')} rf={pbr.get('roughnessFactor')}")

report = "\n".join(lines)
print(report)

if args.out:
    dst = os.path.abspath(args.out)
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(report)
    print("\nwrote %s" % dst)
