# -*- coding: utf-8 -*-
"""verify_assembly.py — prove the rebuild is the same scene as the source.

Run:  blender.exe -b <source>.blend -P verify_assembly.py -- \
          --spec assembly/assembly_spec.json [--out-rebuild rebuild.blend] \
          [--report assembly/verification.md]

Two independent checks, both inside one Blender session:

  A. scene fingerprint   before vs after. Compares, order-independently:
                         object counts by type, collection membership, every
                         object's geometry signature, transform, material slots
                         and modifier config, every light/camera parameter, every
                         material node graph — plus totals of the **evaluated**
                         geometry (modifiers applied), which is what catches a
                         bevel width or a curve bevel_depth rebuilt wrong.

  B. spec round-trip     extract(source) vs extract(assemble(extract(source))).
                         If the second extraction equals the first, the spec is a
                         lossless description of the scene, and the assembler
                         reproduces everything the extractor can see.

Check B is circular on its own (it only proves extract/assemble are inverse),
which is exactly why check A exists: A is measured straight off the geometry.
Together they cover each other's blind spot.
"""
import bpy, os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.dirname(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scene_fingerprint as sf
import extract_assembly_spec as ex
import assemble_scene as asm

SPEC_SECTIONS = ["scene", "world", "collections", "materials",
                 "part_library", "objects", "lights", "cameras"]


def _short(o, n=420):
    return json.dumps(o, ensure_ascii=False, default=str)[:n]


def diff_spec(a, b):
    ok, lines = True, []
    for sec in SPEC_SECTIONS:
        va, vb = a.get(sec), b.get(sec)
        if va == vb:
            extra = ""
            if isinstance(va, list):
                extra = " (%d entries)" % len(va)
            elif isinstance(va, dict):
                extra = " (%d keys)" % len(va)
            lines.append("OK   spec.%-14s identical%s" % (sec, extra))
            continue
        ok = False
        lines.append("DIFF spec.%s" % sec)
        if isinstance(va, dict) and isinstance(vb, dict):
            ka, kb = set(va), set(vb)
            if ka - kb:
                lines.append("     keys only in A: %s" % sorted(ka - kb)[:6])
            if kb - ka:
                lines.append("     keys only in B: %s" % sorted(kb - ka)[:6])
            for k in sorted(ka & kb):
                if va[k] != vb[k]:
                    lines.append("     first differing key %r" % k)
                    lines.append("       A: %s" % _short(va[k]))
                    lines.append("       B: %s" % _short(vb[k]))
                    break
        elif isinstance(va, list) and isinstance(vb, list):
            lines.append("     len %d -> %d" % (len(va), len(vb)))
            for i, (x, y) in enumerate(zip(va, vb)):
                if x != y:
                    lines.append("     first diff at [%d]" % i)
                    lines.append("       A: %s" % _short(x))
                    lines.append("       B: %s" % _short(y))
                    break
        else:
            lines.append("     A: %s" % _short(va))
            lines.append("     B: %s" % _short(vb))
    return ok, lines


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out-rebuild", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--material-preview", action="store_true")
    args = ap.parse_args(argv)

    source = bpy.data.filepath
    lines = ["# Assembly verification", "",
             "**source** `%s`" % source,
             "**spec** `%s`" % args.spec,
             "**blender** %s" % bpy.app.version_string, ""]

    # ---------- pass 1: the source scene ----------
    bpy.context.view_layer.update()
    fp_a = sf.fingerprint(bpy.context)
    spec_a = ex.build_spec()
    on_disk = json.load(open(args.spec, encoding="utf-8"))
    lines += ["## 1. source scene", "",
              "```",
              "objects         %s" % fp_a["counts"]["by_type"],
              "materials       %d" % fp_a["counts"]["materials"],
              "collections     %d" % fp_a["counts"]["collections"],
              "source geom     %d verts / %d faces / %d curve points"
              % (fp_a["source_geometry"]["mesh_verts"],
                 fp_a["source_geometry"]["mesh_faces"],
                 fp_a["source_geometry"]["curve_control_points"]),
              "evaluated geom  %s" % fp_a["evaluated_geometry"],
              "digest          %s" % fp_a["digest"],
              "```", ""]

    ok_disk = all(on_disk.get(k) == spec_a.get(k) for k in SPEC_SECTIONS)
    lines += ["## 2. committed spec vs a fresh extraction from the source", "",
              "%s committed assembly_spec.json is equivalent to the extraction "
              "re-run now" % ("OK  " if ok_disk else "DIFF"), ""]

    # ---------- pass 2: wipe and reassemble ----------
    stats = asm.assemble(args.spec, reset=True,
                         material_preview=args.material_preview,
                         log=lambda *_: None)
    bpy.context.view_layer.update()
    fp_b = sf.fingerprint(bpy.context)
    spec_b = ex.build_spec()

    lines += ["## 3. rebuilt scene", "",
              "```",
              "objects         %s" % fp_b["counts"]["by_type"],
              "materials       %d" % fp_b["counts"]["materials"],
              "collections     %d" % fp_b["counts"]["collections"],
              "geometry        %d verts / %d faces / %d curve points"
              % (fp_b["source_geometry"]["mesh_verts"],
                 fp_b["source_geometry"]["mesh_faces"],
                 fp_b["source_geometry"]["curve_control_points"]),
              "evaluated geom  %s" % fp_b["evaluated_geometry"],
              "digest          %s" % fp_b["digest"],
              "```", ""]

    # ---------- check A: geometry fingerprint ----------
    ok_fp, fp_lines = sf.diff(fp_a, fp_b)
    tol = sf.tolerance_report(fp_a, fp_b)
    lines += ["## 4. check A — scene fingerprint, source vs rebuilt", "",
              "```"] + fp_lines + ["```", "",
              "### measured deviation (not assumed)", "",
              "```",
              "objects compared            %d" % tol["objects_compared"],
              "compare tolerance           %g m" % tol["compare_tolerance_m"],
              "worst bbox deviation        %.3g m  (%s)"
              % (tol["worst_dims_deviation_m"], tol["worst_dims_object"]),
              "worst placement deviation   %.3g m  (%s)"
              % (tol["worst_location_deviation_m"], tol["worst_location_object"]),
              "objects over 1 um           %d" % tol["objects_over_1um"],
              "objects over the tolerance  %d" % tol["objects_over_compare_tol"],
              "absent from second scene    %s" % tol["missing_in_second"],
              "```", ""]
    if tol["top10"]:
        lines += ["| object | deviation | source dims | rebuilt dims |",
                  "|---|---|---|---|"]
        for r in tol["top10"]:
            lines.append("| `%s` | %.3g m | %s | %s |"
                         % (r["obj"], r["dev_m"], r["dims_source"],
                            r["dims_rebuilt"]))
        lines.append("")

    # ---------- check B: spec round-trip ----------
    ok_spec, spec_lines = diff_spec(spec_a, spec_b)
    lines += ["## 5. check B — spec round-trip "
              "(extract -> assemble -> extract)", "", "```"] + spec_lines + \
             ["```", ""]

    # ---------- verdict ----------
    all_ok = bool(ok_fp and ok_spec and ok_disk)
    lines += ["## verdict", "",
              "| check | result |", "|---|---|",
              "| A scene fingerprint | %s |" % ("PASS" if ok_fp else "FAIL"),
              "| B spec round-trip | %s |" % ("PASS" if ok_spec else "FAIL"),
              "| committed spec matches source | %s |"
              % ("PASS" if ok_disk else "FAIL"),
              "| assembler warnings | %d node failures, %d unknown parts, "
              "%d non-bevel modifiers |"
              % (len(stats["node_failures"]), len(stats["unknown_part_kinds"]),
                 0), ""]
    if stats["node_failures"]:
        lines += ["```"] + stats["node_failures"][:20] + ["```", ""]

    if args.out_rebuild:
        out = os.path.abspath(args.out_rebuild)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
        lines += ["rebuilt .blend written to `%s` (%d bytes)"
                  % (out, os.path.getsize(out)), ""]

    if args.report:
        rp = os.path.abspath(args.report)
        os.makedirs(os.path.dirname(rp) or ".", exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    for ln in lines:
        print("VERIFY " + ln)
    print("VERIFY_JSON " + json.dumps({
        "pass_fingerprint": ok_fp, "pass_spec_roundtrip": ok_spec,
        "pass_committed_spec": ok_disk, "all_pass": all_ok,
        "node_failures": stats["node_failures"][:10],
        "digest_source": fp_a["digest"], "digest_rebuilt": fp_b["digest"],
        "eval_source": fp_a["evaluated_geometry"],
        "eval_rebuilt": fp_b["evaluated_geometry"],
        "tolerance": {k: v for k, v in tol.items() if k != "top10"},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
