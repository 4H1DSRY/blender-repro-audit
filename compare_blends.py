# -*- coding: utf-8 -*-
"""compare_blends.py — prove two .blend files contain the same scene.

A Blender session can only have one file open, so this is a two-step tool.

  step 1 (per file):  blender.exe -b A.blend -P compare_blends.py -- --save a.json
  step 2 (offline):   python compare_blends.py --diff a.json b.json

Step 2 is plain Python and does not need Blender.

Typical uses:
  * after cleaning / re-saving a file, show that nothing but the removal changed
  * after a rebuild from a spec, show the rebuild is the same scene
  * after upgrading a Blender version, show the file survived the round-trip

Exit code is 0 when everything matches, 1 otherwise, so it can gate a commit.
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scene_fingerprint as sf      # noqa: E402


def save(path):
    import bpy
    bpy.context.view_layer.update()
    fp = sf.fingerprint(bpy.context)
    fp["blend_file"] = bpy.data.filepath
    fp["text_datablocks"] = [t.name for t in bpy.data.texts]
    sf.save(fp, path)
    print("COMPARE_JSON " + json.dumps({
        "saved": path, "file": bpy.data.filepath, "digest": fp["digest"],
        "objects": fp["counts"]["objects"],
        "evaluated_geometry": fp["evaluated_geometry"],
        "text_datablocks": fp["text_datablocks"],
    }, ensure_ascii=False))


def diff(pa, pb, report=""):
    a, b = sf.load(pa), sf.load(pb)
    ok, lines = sf.diff(a, b)
    tol = sf.tolerance_report(a, b)

    out = ["# compare_blends", "",
           "- A: `%s`  digest `%s`" % (a.get("blend_file") or pa, a.get("digest")),
           "- B: `%s`  digest `%s`" % (b.get("blend_file") or pb, b.get("digest")),
           "", "## scene equivalence", "", "```"] + lines + ["```", "",
           "## measured deviation", "", "```",
           "objects compared            %d" % tol["objects_compared"],
           "worst bbox deviation        %.3g m  (%s)"
           % (tol["worst_dims_deviation_m"], tol["worst_dims_object"]),
           "worst placement deviation   %.3g m  (%s)"
           % (tol["worst_location_deviation_m"], tol["worst_location_object"]),
           "objects over %.0e m       %d"
           % (tol["compare_tolerance_m"], tol["objects_over_compare_tol"]),
           "```", "",
           "## datablocks outside the scene graph", "", "```",
           "A text datablocks  %s" % (a.get("text_datablocks") or []),
           "B text datablocks  %s" % (b.get("text_datablocks") or []),
           "```", "",
           "note: Text datablocks are not part of the scene graph, so removing an"
           " embedded script changes the file without changing the cell above.",
           "", "## verdict", "", "**%s**" % ("IDENTICAL SCENE" if ok else "DIFFERENT"),
           ""]

    text = "\n".join(out)
    for ln in out:
        print("COMPARE " + ln)
    if report:
        with open(os.path.abspath(report), "w", encoding="utf-8") as f:
            f.write(text)
    return 0 if ok else 1


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--save")
    ap.add_argument("--diff", nargs=2)
    ap.add_argument("--report", default="")
    args = ap.parse_args(argv)
    if args.save:
        save(args.save)
    if args.diff:
        sys.exit(diff(args.diff[0], args.diff[1], args.report))
    if not args.save and not args.diff:
        ap.error("need --save <json> or --diff <a.json> <b.json>")


if __name__ == "__main__":
    main()
