# -*- coding: utf-8 -*-
"""extract_assembly_spec.py — dump a whole Blender scene to a declarative spec.

CLI:  blender.exe -b scene.blend -P extract_assembly_spec.py -- \
          --out assembly/assembly_spec.json [--root <repo>]

Importable:  from extract_assembly_spec import build_spec
             spec = build_spec()

What it emits, and why it can be complete for *this* scene:

  materials      every material's node tree as (bl_idname, simple properties,
                 unlinked socket defaults) + links. Safe here because the scene
                 uses no node groups, no image textures and no OSL. The only
                 pointer property that carries data is the ColorRamp of a
                 ValToRGB node, handled explicitly; any other data-carrying
                 pointer is reported in meta.warnings rather than dropped.
  part_library   186 recipes covering 756 objects: a literal box (dims), a
                 literal cylinder (sides/radius/depth), raw vertex+face data for
                 the 11 cast bell shells, and bevel curves for the 88 bell rims.
  objects        one entry per object: exact name, datablock name, collection,
                 transform, material slots, modifier config.
  curves         POLY splines with bevel_depth — the bell rims/eyes. The
                 datablock transform is identity, so points carry absolute
                 geometry.
  lights/cameras 11 area lights and 5 inspection cameras with parameters.

The output is self-contained: assemble_scene.py never opens the source .blend.
"""
import bpy, json, os, sys, hashlib, collections, argparse

SKIP_NODE_PROPS = {
    "rna_type", "name", "label", "location", "width", "height", "dimensions",
    "mute", "hide", "parent", "inputs", "outputs", "internal_links", "color",
    "select", "show_options", "show_preview", "show_texture", "type",
    "warning_propagation", "use_custom_color", "is_active_output", "node_tree",
    "image", "text", "script", "material", "object", "color_ramp",
    #: derived editor state — recomputed from `location`, and stale in a freshly
    #: opened file. Sweeping it in makes the spec non-reproducible.
    "location_absolute",
}
ALLOWED_POINTERS = {"color_ramp", "node_tree"}

WARNINGS = []


# ==========================================================================
# generic node serialisation
# ==========================================================================
def _socket_value(sock):
    if not hasattr(sock, "default_value"):
        return None
    v = sock.default_value
    if isinstance(v, bool):
        return ["bool", bool(v)]
    if isinstance(v, int):
        return ["int", int(v)]
    if isinstance(v, float):
        return ["float", round(float(v), 6)]
    if isinstance(v, str):
        return ["str", v]
    try:
        seq = list(v)
    except TypeError:
        return None
    if not seq:
        return None
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in seq):
        if len(seq) == 1:
            return ["float", round(float(seq[0]), 6)]
        return ["seq", [round(float(x), 6) for x in seq]]
    return None


def dump_node(node):
    d = {"id": node.name, "bl": node.bl_idname,
         "loc": [round(v, 2) for v in node.location],
         "label": node.label or "", "props": {}, "inputs": {}}
    for p in node.bl_rna.properties:
        ident = p.identifier
        if ident in SKIP_NODE_PROPS or ident.startswith("bl_"):
            continue
        if p.type not in {"FLOAT", "INT", "BOOLEAN", "ENUM", "STRING"}:
            if p.type == "POINTER" and ident not in ALLOWED_POINTERS:
                val = getattr(node, ident, None)
                if val is not None and getattr(val, "name", None) is not None:
                    WARNINGS.append("node %s (%s) carries pointer %s=%s"
                                    % (node.name, node.bl_idname, ident, val.name))
            continue
        if p.is_readonly:
            continue          # computed / cache values, not authored settings
        try:
            val = getattr(node, ident)
        except Exception:
            continue
        if isinstance(val, float):
            val = round(val, 6)
        d["props"][ident] = val
    for sock in node.inputs:
        if sock.is_linked:
            continue
        sv = _socket_value(sock)
        if sv is not None:
            d["inputs"][sock.identifier] = sv
    if hasattr(node, "color_ramp"):
        cr = node.color_ramp
        d["color_ramp"] = {
            "interpolation": cr.interpolation, "color_mode": cr.color_mode,
            "hue_interpolation": getattr(cr, "hue_interpolation", "NEAR"),
            "elements": [{"position": round(e.position, 6),
                          "color": [round(c, 6) for c in e.color]}
                         for e in cr.elements],
        }
    return d


def dump_tree(nt):
    return {
        "nodes": [dump_node(n) for n in nt.nodes],
        "links": [{"from": l.from_node.name,
                   "from_socket": l.from_socket.identifier,
                   "to": l.to_node.name,
                   "to_socket": l.to_socket.identifier} for l in nt.links],
    }


# ==========================================================================
# geometry recipes
# ==========================================================================
def _is_box(me):
    if len(me.vertices) != 8 or len(me.polygons) != 6:
        return None
    co = [v.co for v in me.vertices]
    uniq = [sorted({round(c[i], 6) for c in co}) for i in range(3)]
    if any(len(u) != 2 for u in uniq):
        return None
    if any(abs(sum(c[i] for c in co) / 8.0) > 1e-6 for i in range(3)):
        return None                       # origin must sit at the bbox centre
    return [round(uniq[i][1] - uniq[i][0], 6) for i in range(3)]


def _is_cylinder(me):
    quad = sum(1 for p in me.polygons if p.loop_total == 4)
    ngon = [p for p in me.polygons if p.loop_total > 4]
    if quad == 0 or len(ngon) != 2 or quad != len(me.vertices) // 2:
        return None
    if any(p.loop_total != quad for p in ngon):
        return None
    zs = sorted({round(v.co.z, 6) for v in me.vertices})
    if len(zs) != 2:
        return None
    radii = {round((v.co.x ** 2 + v.co.y ** 2) ** 0.5, 5) for v in me.vertices}
    if len(radii) != 1:
        return None
    return {"sides": quad, "radius": list(radii)[0],
            "depth": round(zs[1] - zs[0], 6)}


def mesh_recipe(me):
    smooth = bool(me.polygons[0].use_smooth) if len(me.polygons) else False
    mixed = len({bool(p.use_smooth) for p in me.polygons}) > 1
    box = _is_box(me)
    if box:
        rec = {"kind": "box", "dims": box, "smooth": smooth,
               "uv": bool(me.uv_layers)}
        return "box|%s|%s" % ("x".join("%.6f" % d for d in box), smooth), rec
    cyl = _is_cylinder(me)
    if cyl:
        rec = {"kind": "cylinder", "params": cyl, "smooth": smooth,
               "uv": bool(me.uv_layers)}
        return "cyl|%d|%.5f|%.6f|%s" % (cyl["sides"], cyl["radius"],
                                        cyl["depth"], smooth), rec
    verts = [[round(c, 6) for c in v.co] for v in me.vertices]
    faces = [list(p.vertices) for p in me.polygons]
    h = hashlib.sha1(json.dumps([verts, faces], separators=(",", ":"))
                     .encode()).hexdigest()[:12]
    return "raw|" + h, {"kind": "raw", "verts": verts, "faces": faces,
                        "smooth": smooth, "uv": bool(me.uv_layers),
                        "mixed_smooth": mixed}


def curve_recipe(cu):
    sp = [{"type": s.type, "cyclic": s.use_cyclic_u,
           "points": [[round(c, 6) for c in p.co] for p in s.points]}
          for s in cu.splines]
    rec = {"kind": "bevel_curve", "splines": sp, "dimensions": cu.dimensions,
           "fill_mode": cu.fill_mode, "bevel_depth": round(cu.bevel_depth, 6),
           "bevel_resolution": cu.bevel_resolution,
           "extrude": round(cu.extrude, 6), "offset": round(cu.offset, 6),
           "resolution_u": cu.resolution_u, "twist_mode": cu.twist_mode,
           "twist_smooth": round(getattr(cu, "twist_smooth", 0.0), 4),
           "use_fill_caps": cu.use_fill_caps, "bevel_mode": cu.bevel_mode}
    h = hashlib.sha1(json.dumps(rec, sort_keys=True,
                                separators=(",", ":")).encode()).hexdigest()[:12]
    return "curve|" + h, rec


def bevel_of(obj):
    """Modifier config, read defensively — Blender renames modifier props."""
    out = []
    for m in obj.modifiers:
        if m.type == "BEVEL":
            def g(*names, default=None):
                for n in names:
                    if hasattr(m, n):
                        return getattr(m, n)
                return default
            out.append({"type": "BEVEL", "width": round(m.width, 6),
                        "segments": m.segments,
                        "limit_method": g("limit_method"),
                        "angle_limit": round(g("angle_limit", default=0.0), 6),
                        "harden_normals": bool(g("harden_normals", default=False)),
                        "affect": g("affect"), "miter_outer": g("miter_outer"),
                        "use_clamp_overlap": bool(
                            g("use_clamp_overlap", "clamp_overlap", default=True)),
                        "offset_type": g("offset_type")})
        else:
            out.append({"type": m.type})
            WARNINGS.append("non-bevel modifier %s on %s" % (m.type, obj.name))
    return out


# ==========================================================================
# the spec
# ==========================================================================
def _xf(o):
    return {"loc": [round(v, 6) for v in o.location],
            "rot": [round(v, 6) for v in o.rotation_euler],
            "scale": [round(v, 6) for v in o.scale],
            "rotation_mode": o.rotation_mode,
            "hide_render": bool(o.hide_render)}


def build_spec():
    """Return the declarative spec for the currently open scene."""
    del WARNINGS[:]
    scene = bpy.context.scene
    spec = {
        "spec_version": 1,
        "meta": {"generator": "extract_assembly_spec.py",
                 "blender": bpy.app.version_string,
                 "source_blend": os.path.basename(bpy.data.filepath),
                 "source_sha256": "", "extracted_objects": 0,
                 "part_library_size": 0, "warnings": list(WARNINGS)},
        "scene": {"name": scene.name,
                  "camera": scene.camera.name if scene.camera else None,
                  "frame_start": scene.frame_start, "frame_end": scene.frame_end,
                  "frame_current": scene.frame_current,
                  "unit_system": scene.unit_settings.system,
                  "unit_scale": scene.unit_settings.scale_length,
                  "render": {"engine": scene.render.engine,
                             "resolution_x": scene.render.resolution_x,
                             "resolution_y": scene.render.resolution_y,
                             "resolution_percentage":
                                 scene.render.resolution_percentage,
                             "film_transparent": scene.render.film_transparent},
                  "view": {"view_transform": scene.view_settings.view_transform,
                           "look": scene.view_settings.look,
                           "exposure": round(scene.view_settings.exposure, 6),
                           "gamma": round(scene.view_settings.gamma, 6)}},
        "world": None, "collections": [], "materials": [],
        "part_library": {}, "objects": [], "lights": [], "cameras": [],
    }
    src = bpy.data.filepath
    if src and os.path.exists(src):
        h = hashlib.sha256()
        with open(src, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        spec["meta"]["source_sha256"] = h.hexdigest()

    if scene.world:
        w = scene.world
        spec["world"] = {"name": w.name,
                         "color": [round(c, 6) for c in w.color],
                         "node_tree": dump_tree(w.node_tree)
                         if w.node_tree else None}

    spec["collections"] = sorted(c.name for c in bpy.data.collections)
    spec["meta"]["collection_tree"] = {
        c.name: sorted(x.name for x in c.children) for c in bpy.data.collections}

    for m in sorted(bpy.data.materials, key=lambda x: x.name):
        rec = {"name": m.name,
               "diffuse_color": [round(c, 6) for c in m.diffuse_color],
               "metallic": round(m.metallic, 6),
               "roughness": round(m.roughness, 6),
               "use_backface_culling": bool(m.use_backface_culling),
               "node_tree": dump_tree(m.node_tree) if m.node_tree else None}
        for attr in ("blend_method", "surface_render_method",
                     "use_transparency_overlap"):
            if hasattr(m, attr):
                rec[attr] = getattr(m, attr)
        spec["materials"].append(rec)

    for o in sorted(bpy.data.objects, key=lambda x: x.name):
        if o.type == "LIGHT":
            lt = o.data
            spec["lights"].append({
                "name": o.name, "data_name": lt.name, "type": lt.type,
                "shape": getattr(lt, "shape", None),
                "energy": round(lt.energy, 6),
                "size": round(getattr(lt, "size", 0.0), 6),
                "size_y": round(getattr(lt, "size_y", 0.0), 6),
                "spread": round(getattr(lt, "spread", 0.0), 6),
                "color": [round(c, 6) for c in lt.color],
                "use_shadow": bool(lt.use_shadow),
                "collection": (o.users_collection[0].name
                               if o.users_collection else None), **_xf(o)})
        elif o.type == "CAMERA":
            cd = o.data
            spec["cameras"].append({
                "name": o.name, "data_name": cd.name,
                "lens": round(cd.lens, 6),
                "sensor_width": round(cd.sensor_width, 6),
                "sensor_height": round(cd.sensor_height, 6),
                "sensor_fit": cd.sensor_fit,
                "clip_start": round(cd.clip_start, 6),
                "clip_end": round(cd.clip_end, 6),
                "dof": bool(cd.dof.use_dof),
                "collection": (o.users_collection[0].name
                               if o.users_collection else None), **_xf(o)})
        elif o.type == "MESH" and o.data:
            key, rec = mesh_recipe(o.data)
            spec["part_library"].setdefault(key, rec)
            spec["objects"].append({
                "kind": "mesh", "name": o.name, "part": key,
                "data_name": o.data.name,
                "collection": (o.users_collection[0].name
                               if o.users_collection else None),
                "materials": [ms.material.name if ms.material else None
                              for ms in o.material_slots],
                "modifiers": bevel_of(o), **_xf(o)})
        elif o.type == "CURVE" and o.data:
            key, rec = curve_recipe(o.data)
            spec["part_library"].setdefault(key, rec)
            spec["objects"].append({
                "kind": "curve", "name": o.name, "part": key,
                "data_name": o.data.name,
                "collection": (o.users_collection[0].name
                               if o.users_collection else None),
                "materials": [ms.material.name if ms.material else None
                              for ms in o.material_slots],
                "modifiers": bevel_of(o), **_xf(o)})
        elif o.type not in {"LIGHT", "CAMERA"}:
            WARNINGS.append("unhandled object type %s: %s" % (o.type, o.name))

    spec["meta"]["extracted_objects"] = len(spec["objects"])
    spec["meta"]["part_library_size"] = len(spec["part_library"])
    spec["meta"]["warnings"] = list(WARNINGS)
    return spec


def _json_default(o):
    """mathutils Vector/Color and other array-likes -> plain lists."""
    try:
        return [round(float(x), 6) for x in o]
    except TypeError:
        return str(o)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assembly_spec.json")
    ap.add_argument("--root", default="")
    ap.add_argument("--indent", type=int, default=None)
    args = ap.parse_args(argv)

    spec = build_spec()
    out = args.out
    if args.root and not os.path.isabs(out):
        out = os.path.join(args.root, out)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, separators=(",", ":"),
                  indent=args.indent, default=_json_default)

    kinds = collections.Counter(r.get("kind", "?")
                                for r in spec["part_library"].values())
    print("SPEC_JSON " + json.dumps({
        "out": out, "bytes": os.path.getsize(out),
        "objects": spec["meta"]["extracted_objects"],
        "part_library": spec["meta"]["part_library_size"],
        "part_kinds": dict(kinds), "materials": len(spec["materials"]),
        "collections": len(spec["collections"]),
        "lights": len(spec["lights"]), "cameras": len(spec["cameras"]),
        "warnings": spec["meta"]["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
