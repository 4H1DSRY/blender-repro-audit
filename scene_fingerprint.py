# -*- coding: utf-8 -*-
"""scene_fingerprint.py — order-independent equivalence fingerprint of a scene.

Used to prove that a rebuilt scene is the same scene as the original: the
fingerprint is a set of *sorted multisets* plus a handful of totals, so it does
not care in what order objects were created, nor what the temporary .001
suffixes happened to be.

The strongest single check is `eval_*`: vertex/face/triangle counts of the
**evaluated** (modifier-applied) geometry. If 668 Bevel modifiers were rebuilt
with the wrong width or segments, or a curve's bevel_depth was off, these totals
move. Everything else is a per-object cross-check.

Usage from another script:
    import scene_fingerprint as sf
    fp = sf.fingerprint(bpy.context)
    sf.save(fp, "original.json")
    print(sf.diff(fp_a, fp_b))
"""
import json
import collections
import hashlib

R6 = 6          # decimals kept for lengths
R4 = 4          # decimals kept for angles

#: Comparison tolerance for *derived* lengths (bbox dims = max - min).
#:
#: Blender stores mesh vertices as float32, whose quantum at this scene's
#: ~10 m extents is about 0.6 um — so the source .blend is itself only
#: micrometre-accurate out at the walls. A spec that quantises lengths to
#: 1 um therefore discards nothing real. But a *difference* of two quantised
#: values can land on the far side of a rounding boundary, which would show up
#: as a phantom 1e-6 diff, so derived lengths are compared at 10 um — still
#: four orders of magnitude below the smallest part (0.018 m).
#: `tolerance_report()` prints the actual worst-case deviation so the slack is
#: never taken on faith.
COMPARE_LEN = 1e-5

#: node properties skipped when hashing a node — editor-only state and the
#: pointer / collection props that are serialised explicitly instead.
_SKIP = {
    "rna_type", "name", "label", "location", "width", "height", "dimensions",
    "mute", "hide", "parent", "inputs", "outputs", "internal_links", "color",
    "select", "show_options", "show_preview", "show_texture", "type",
    "warning_propagation", "use_custom_color", "is_active_output", "node_tree",
    "image", "text", "script", "material", "object", "color_ramp",
    #: derived editor state — recomputed from `location`, and stale in a freshly
    #: opened file, so it must never take part in an equivalence check.
    "location_absolute",
}


def _bevel_of(obj):
    out = []
    for m in obj.modifiers:
        if m.type == "BEVEL":
            out.append((round(m.width, R6), m.segments, m.limit_method,
                        bool(m.harden_normals), m.affect))
        else:
            out.append((m.type,))
    return tuple(out)


def _q(v):
    """Quantise a derived length to the comparison tolerance."""
    return int(round(v / COMPARE_LEN))


def _mesh_sig(me):
    """Geometry signature that survives being rebuilt from a recipe."""
    d = me.vertices
    if len(d):
        xs = [v.co.x for v in d]
        ys = [v.co.y for v in d]
        zs = [v.co.z for v in d]
        dims = (_q(max(xs) - min(xs)), _q(max(ys) - min(ys)), _q(max(zs) - min(zs)))
    else:
        dims = (0, 0, 0)
    loops = tuple(sorted(collections.Counter(p.loop_total for p in me.polygons).items()))
    return (len(me.vertices), len(me.polygons), loops, dims,
            sum(1 for p in me.polygons if p.use_smooth),
            len(me.uv_layers))


def _curve_sig(cu):
    sp = []
    for s in cu.splines:
        pts = tuple((round(p.co.x, R6), round(p.co.y, R6), round(p.co.z, R6))
                    for p in s.points)
        sp.append((s.type, len(pts), s.use_cyclic_u, pts))
    return (cu.dimensions, cu.fill_mode, round(cu.bevel_depth, R6),
            cu.bevel_resolution, round(cu.extrude, R6),
            cu.twist_mode, cu.use_fill_caps, cu.bevel_mode, tuple(sp))


def _raw_dims(me):
    d = me.vertices
    if not len(d):
        return [0.0, 0.0, 0.0]
    return [max(v.co[i] for v in d) - min(v.co[i] for v in d) for i in range(3)]


def _xf(obj):
    """Transform as *stored*, not as decomposed.

    Reading obj.matrix_world.to_euler() looks more general, but at the +-180 deg
    branch cut the decomposed euler can come back with the opposite sign for an
    identical orientation, which shows up as a phantom diff. The scene has no
    parents and no constraints, so the stored channels are authoritative.
    """
    t = obj.location
    e = obj.rotation_euler
    return ((round(t.x, R6), round(t.y, R6), round(t.z, R6)),
            (round(e.x, R4), round(e.y, R4), round(e.z, R4)))


def fingerprint(context, include_world_space=True):
    """Return a plain-dict fingerprint of everything in the given context."""
    dg = context.evaluated_depsgraph_get()

    meshes, curves, lights, cameras = [], [], [], []
    mat_pairs = []
    precise = {}
    obj_kinds = collections.Counter()
    eval_mv = eval_mf = eval_mp = 0
    eval_cv = eval_cf = eval_cp = 0
    coll_members = collections.Counter()

    for obj in sorted(context.scene.objects, key=lambda o: o.name):
        obj_kinds[obj.type] += 1
        for c in obj.users_collection:
            coll_members[c.name] += 1
        slots = tuple(ms.material.name if ms.material else None
                      for ms in obj.material_slots)
        if obj.type == "MESH" and obj.data:
            meshes.append((obj.name, _mesh_sig(obj.data), slots,
                           _bevel_of(obj), _xf(obj) if include_world_space else None))
            precise[obj.name] = {"dims": _raw_dims(obj.data),
                                 "loc": [obj.location.x, obj.location.y,
                                         obj.location.z]}
            for ms in obj.material_slots:
                mat_pairs.append((obj.name, ms.material.name if ms.material else None))
            ev = obj.evaluated_get(dg)
            m = ev.to_mesh()
            eval_mv += len(m.vertices)
            eval_mf += len(m.polygons)
            eval_mp += sum(len(p.vertices) - 2 for p in m.polygons)
            ev.to_mesh_clear()
        elif obj.type == "CURVE" and obj.data:
            curves.append((obj.name, _curve_sig(obj.data), slots, _bevel_of(obj),
                           _xf(obj) if include_world_space else None))
            pts = [p.co for s in obj.data.splines for p in s.points]
            precise[obj.name] = {
                "dims": [max(p[i] for p in pts) - min(p[i] for p in pts)
                         for i in range(3)] if pts else [0.0, 0.0, 0.0],
                "loc": [obj.location.x, obj.location.y, obj.location.z]}
            for ms in obj.material_slots:
                mat_pairs.append((obj.name, ms.material.name if ms.material else None))
            ev = obj.evaluated_get(dg)
            m = ev.to_mesh()
            eval_cv += len(m.vertices)
            eval_cf += len(m.polygons)
            eval_cp += sum(len(p.vertices) - 2 for p in m.polygons)
            ev.to_mesh_clear()
        elif obj.type == "LIGHT" and obj.data:
            lt = obj.data
            lights.append((obj.name, lt.type, getattr(lt, "shape", None),
                           round(lt.energy, R4),
                           round(getattr(lt, "size", 0.0), R6),
                           round(getattr(lt, "size_y", 0.0), R6),
                           round(getattr(lt, "spread", 0.0), R4),
                           tuple(round(c, R6) for c in lt.color),
                           bool(lt.use_shadow),
                           _xf(obj) if include_world_space else None))
        elif obj.type == "CAMERA" and obj.data:
            cd = obj.data
            cameras.append((obj.name, round(cd.lens, R4),
                            round(cd.sensor_width, R4), cd.sensor_fit,
                            bool(cd.dof.use_dof),
                            _xf(obj) if include_world_space else None))

    mats = []
    for m in sorted(__import__("bpy").data.materials, key=lambda x: x.name):
        nt = m.node_tree
        if nt is None:
            mats.append((m.name, 0, 0))
            continue
        node_sig = tuple(sorted(
            (n.bl_idname,
             tuple(round(v, 2) for v in n.location),
             tuple(sorted((p.identifier, repr(getattr(n, p.identifier)))
                          for p in n.bl_rna.properties
                          if p.identifier not in _SKIP and not p.identifier.startswith("bl_")
                          and p.type in {"FLOAT", "INT", "BOOLEAN", "ENUM", "STRING"})),
             tuple((round(e.position, 6), tuple(round(c, 6) for c in e.color))
                   for e in n.color_ramp.elements) if hasattr(n, "color_ramp") else (),
             tuple(sorted((i.identifier, repr(i.default_value))
                          for i in n.inputs
                          if not i.is_linked and hasattr(i, "default_value"))))
            for n in nt.nodes))
        link_sig = tuple(sorted(
            (l.from_node.bl_idname, l.from_socket.identifier,
             l.to_node.bl_idname, l.to_socket.identifier) for l in nt.links))
        mats.append((m.name, node_sig, link_sig))

    fp = {
        "counts": {
            "objects": len(context.scene.objects),
            "by_type": dict(sorted(obj_kinds.items())),
            "materials": len(__import__("bpy").data.materials),
            "collections": len(__import__("bpy").data.collections),
        },
        "source_geometry": {
            "mesh_verts": sum(m[1][0] for m in meshes),
            "mesh_faces": sum(m[1][1] for m in meshes),
            "curve_control_points": sum(
                sum(s[1] for s in c[1][8]) for c in curves),
        },
        "evaluated_geometry": {
            "mesh_verts": eval_mv, "mesh_faces": eval_mf, "mesh_tris": eval_mp,
            "curve_verts": eval_cv, "curve_faces": eval_cf, "curve_tris": eval_cp,
            "total_tris": eval_mp + eval_cp,
        },
        "collection_membership": dict(sorted(coll_members.items())),
        "meshes": sorted(meshes),
        "curves": sorted(curves),
        "lights": sorted(lights),
        "cameras": sorted(cameras),
        "material_slots": sorted(mat_pairs),
        "materials": sorted(mats),
        "precise": precise,
    }
    fp["digest"] = _digest(fp)
    return fp


def _digest(fp):
    """One hash over the payload sections (excludes volatile counts)."""
    payload = json.dumps({k: fp[k] for k in
                          ("evaluated_geometry", "meshes", "curves",
                           "lights", "cameras", "material_slots")},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def tolerance_report(a, b):
    """Measure — rather than assume — how far a rebuild drifted from its source.

    A PASS at a stated tolerance is only worth something if the real number is
    printed next to it, so this returns the worst per-object bbox deviation and
    the worst placement deviation over every object present in both scenes.
    """
    pa, pb = a.get("precise", {}), b.get("precise", {})
    common = sorted(set(pa) & set(pb))
    rows = []
    worst_loc, worst_loc_name = 0.0, None
    over_1um = over_tol = 0
    for n in common:
        dd = max(abs(x - y) for x, y in zip(pa[n]["dims"], pb[n]["dims"]))
        dl = max(abs(x - y) for x, y in zip(pa[n]["loc"], pb[n]["loc"]))
        if dl > worst_loc:
            worst_loc, worst_loc_name = dl, n
        if dd > 1e-6:
            over_1um += 1
        if dd > COMPARE_LEN:
            over_tol += 1
        rows.append((dd, n, pa[n]["dims"], pb[n]["dims"]))
    rows.sort(key=lambda r: -r[0])
    worst_dim = rows[0][0] if rows else 0.0
    worst_dim_name = rows[0][1] if rows else None
    return {
        "objects_compared": len(common),
        "missing_in_second": sorted(set(pa) - set(pb))[:10],
        "missing_in_first": sorted(set(pb) - set(pa))[:10],
        "worst_dims_deviation_m": worst_dim,
        "worst_dims_object": worst_dim_name,
        "worst_location_deviation_m": worst_loc,
        "worst_location_object": worst_loc_name,
        "objects_over_1um": over_1um,
        "objects_over_compare_tol": over_tol,
        "compare_tolerance_m": COMPARE_LEN,
        "top10": [{"obj": n, "dev_m": d,
                   "dims_source": [round(x, 9) for x in da],
                   "dims_rebuilt": [round(x, 9) for x in db]}
                  for d, n, da, db in rows[:10]],
    }


def save(fp, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fp, f, ensure_ascii=False, indent=1, default=str)
    return path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def diff(a, b):
    """Compare two fingerprints; return (ok, list_of_report_lines)."""
    lines = []
    ok = True

    for section in ("counts", "source_geometry", "evaluated_geometry",
                    "collection_membership"):
        ka, kb = a.get(section, {}), b.get(section, {})
        for key in sorted(set(ka) | set(kb)):
            va, vb = ka.get(key), kb.get(key)
            mark = "OK  " if va == vb else "DIFF"
            if va != vb:
                ok = False
            lines.append("%s %-34s %-22s -> %s" % (mark, section + "." + key, va, vb))

    for section in ("meshes", "curves", "lights", "cameras",
                    "material_slots", "materials"):
        sa = collections.Counter(json.dumps(x, sort_keys=True, default=str)
                                 for x in a.get(section, []))
        sb = collections.Counter(json.dumps(x, sort_keys=True, default=str)
                                 for x in b.get(section, []))
        only_a = sa - sb
        only_b = sb - sa
        n_a = sum(sa.values())
        n_b = sum(sb.values())
        if only_a or only_b:
            ok = False
            lines.append("DIFF %-34s %d items -> %d items | only-in-A=%d only-in-B=%d"
                         % (section, n_a, n_b, sum(only_a.values()),
                            sum(only_b.values())))
            for k, v in list(only_a.items())[:5]:
                lines.append("       A-only x%d: %s" % (v, k[:180]))
            for k, v in list(only_b.items())[:5]:
                lines.append("       B-only x%d: %s" % (v, k[:180]))
        else:
            lines.append("OK   %-34s %d items identical" % (section, n_a))

    lines.append("%s digest %s vs %s" %
                 ("OK  " if a.get("digest") == b.get("digest") else "DIFF",
                  a.get("digest"), b.get("digest")))
    if a.get("digest") != b.get("digest"):
        ok = False
    return ok, lines
