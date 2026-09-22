# -*- coding: utf-8 -*-
"""strip_embedded_scripts.py — remove embedded Text datablocks from a .blend.

Run:  blender.exe -b scene.blend -P strip_embedded_scripts.py -- \
          [--out <path>] [--dry-run] [--no-backup]

Why this exists
---------------
A Text datablock is invisible in the viewport but travels with the file. If a
build/audit script was ever run inside Blender and left behind — or pasted into
the Text Editor — it ships to whoever receives the .blend, including internal
notes and paths. Run this before committing or delivering a scene.

It touches nothing else: no geometry, no materials, no modifiers. `--dry-run`
lists what would go without writing.

Exits with a JSON summary: how many Text datablocks were found, their names and
sizes, and the sha256 of the file before and after.
"""
import bpy, os, sys, json, shutil, hashlib, argparse


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args(argv)

    src = bpy.data.filepath
    res = {"file": src, "sha256_before": sha256(src) if src else None,
           "size_before": os.path.getsize(src) if src else None}

    found = []
    for t in bpy.data.texts:
        body = t.as_string()
        head = body.strip().splitlines()[:1]
        found.append({"name": t.name,
                      "lines": body.count("\n") + 1,
                      "chars": len(body),
                      "first_line": head[0] if head else "",
                      "external_path": getattr(t, "filepath", "") or ""})
    res["text_datablocks"] = found
    res["n_text_datablocks"] = len(found)

    if args.dry_run:
        res["dry_run"] = True
        print("STRIP_JSON " + json.dumps(res, ensure_ascii=False))
        return

    for t in list(bpy.data.texts):
        bpy.data.texts.remove(t)
    res["text_datablocks_after"] = len(bpy.data.texts)

    out = args.out or src
    if not args.no_backup and src:
        bak = os.path.splitext(src)[0] + ".backup.blend"
        shutil.copy2(src, bak)
        res["backup"] = bak

    if out and os.path.abspath(out) != os.path.abspath(src):
        # save as a separate file, keep the original untouched
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True,
                                    copy=True)
    else:
        bpy.ops.wm.save_as_mainfile(filepath=src, compress=True)

    res["written"] = out
    res["sha256_after"] = sha256(out)
    res["size_after"] = os.path.getsize(out)
    res["size_delta"] = res["size_after"] - res["size_before"]
    print("STRIP_JSON " + json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
