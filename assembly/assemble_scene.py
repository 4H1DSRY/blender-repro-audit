# -*- coding: utf-8 -*-
"""assemble_scene.py — rebuild the whole hall from a declarative spec.

Run:  blender.exe -b -P assemble_scene.py -- \
          --spec assembly/assembly_spec.json --out rebuilt.blend

The spec is the only input: this script never opens the source .blend. That is
the point — the hall becomes reproducible from a text file, and every part of it
(geometry, placement, shader graphs, lighting rig, cameras) is data rather than
hand-placed state.

What it does, in order:
  1.  wipe to an empty scene
  2.  scene/render/colour-management settings
  3.  materials — rebuild each node tree: nodes, properties, ColorRamp elements,
      links, then unlinked-socket defaults
  4.  world
  5.  collections (flat, as in the source)
  6.  part library — build each recipe once as a template mesh/curve
  7.  objects — one *private* datablock per object (the source has zero linked
      duplicates: 668 objects, 668 mesh datablocks), private bevel modifier,
      material slots, transform, datablock name
  8.  lights, cameras, scene camera

Also importable:  from assemble_scene import assemble
"""
import bpy, json, os, sys, collections, argparse
from mathutils import Vector

# ==========================================================================
# node graph rebuild
# ==========================================================================
def _sockets(node):
    by = {}
    for s in node.inputs:
        by[s.identifier] = s
        by.setdefault(s.name, s)
    return by


def _out_sockets(node):
    by = {}
    for s in node.outputs:
        by[s.identifier] = s
        by.setdefault(s.name, s)
    return by


def _set_socket(sock, sv):
    kind, val = sv[0], sv[1]
    try:
        if kind == "bool":
            sock.default_value = bool(val)
        elif kind == "int":
            sock.default_value = int(val)
        elif kind == "float":
            sock.default_value = float(val)
        elif kind == "str":
            sock.default_value = str(val)
        elif kind == "seq":
            if len(val) == 1:
                sock.default_value = float(val[0])
            else:
                try:
                    sock.default_value = [float(x) for x in val]
                except Exception:
                    for i, x in enumerate(val):
                        try:
                            sock.default_value[i] = float(x)
                        except Exception:
                            pass
    except Exception:
        pass


def _build_color_ramp(node, data):
    cr = node.color_ramp
    els = data["elements"]
    while len(cr.elements) < len(els):
        cr.elements.new(0.5)
    while len(cr.elements) > len(els) and len(cr.elements) > 2:
        cr.elements.remove(cr.elements[-1])
    for el, src in zip(cr.elements, els):
        try:
            el.position = src["position"]
        except Exception:
            pass
        try:
            el.color = src["color"]
        except Exception:
            pass
    for attr in ("interpolation", "color_mode", "hue_interpolation"):
        if attr in data:
            try:
                setattr(cr, attr, data[attr])
            except Exception:
                pass


def build_node_tree(nt, data, stats):
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    byname = {}
    for nd in data["nodes"]:
        try:
            n = nt.nodes.new(nd["bl"])
        except Exception as e:
            stats["node_failures"].append("%s: %s" % (nd["bl"], e))
            continue
        n.name = nd["id"]
        if nd.get("label"):
            n.label = nd["label"]
        n.location = nd["loc"]
        for k, v in nd.get("props", {}).items():
            try:
                setattr(n, k, v)
            except Exception:
                pass
        if "color_ramp" in nd and hasattr(n, "color_ramp"):
            _build_color_ramp(n, nd["color_ramp"])
        byname[nd["id"]] = n
    linked = set()
    for l in data["links"]:
        a, b = byname.get(l["from"]), byname.get(l["to"])
        if a is None or b is None:
            stats["node_failures"].append("link %s->%s: node missing"
                                          % (l["from"], l["to"]))
            continue
        so = _out_sockets(a).get(l["from_socket"])
        si = _sockets(b).get(l["to_socket"])
        if so is None or si is None:
            stats["node_failures"].append("link %s.%s->%s.%s: socket missing"
                                          % (l["from"], l["from_socket"],
                                             l["to"], l["to_socket"]))
            continue
        try:
            nt.links.new(so, si)
            linked.add((l["to"], l["to_socket"]))
        except Exception as e:
            stats["node_failures"].append("link: %s" % e)
    for nd in data["nodes"]:
        n = byname.get(nd["id"])
        if n is None:
            continue
        socks = _sockets(n)
        for ident, sv in nd.get("inputs", {}).items():
            s = socks.get(ident)
            if s is None or s.is_linked:
                continue
            _set_socket(s, sv)


# ==========================================================================
# part templates
# ==========================================================================
def _primitive_cube_template(dims, smooth):
    bpy.ops.mesh.primitive_cube_add(size=1.0, calc_uvs=True)
    me = bpy.context.object.data
    for v in me.vertices:
        v.co.x *= dims[0]
        v.co.y *= dims[1]
        v.co.z *= dims[2]
    _finish_template(bpy.context.object, me, smooth)
    return me


def _primitive_cylinder_template(p, smooth):
    bpy.ops.mesh.primitive_cylinder_add(vertices=p["sides"], radius=p["radius"],
                                        depth=p["depth"], end_fill_type="NGON",
                                        calc_uvs=True)
    me = bpy.context.object.data
    _finish_template(bpy.context.object, me, smooth)
    return me


def _raw_template(rec, smooth):
    me = bpy.data.meshes.new("template_raw")
    me.from_pydata([tuple(v) for v in rec["verts"]], [], rec["faces"])
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    return me


def _finish_template(obj, me, smooth):
    for p in me.polygons:
        p.use_smooth = smooth
    bpy.data.objects.remove(obj, do_unlink=True)


def build_part_library(spec, stats):
    """Return {part_key: template datablock}. Templates are unlinked objects'
    leftover datablocks; they are copied per object and dropped afterwards."""
    templates = {}
    for key, rec in spec["part_library"].items():
        kind = rec["kind"]
        if kind == "box":
            templates[key] = _primitive_cube_template(rec["dims"], rec["smooth"])
        elif kind == "cylinder":
            templates[key] = _primitive_cylinder_template(rec["params"],
                                                          rec["smooth"])
        elif kind == "raw":
            templates[key] = _raw_template(rec, rec["smooth"])
        elif kind == "bevel_curve":
            templates[key] = _curve_template(rec)
        else:
            stats["unknown_part_kinds"].append(kind)
    return templates


def _curve_template(rec):
    cu = bpy.data.curves.new("template_curve", type="CURVE")
    cu.dimensions = rec["dimensions"]
    cu.fill_mode = rec["fill_mode"]
    cu.bevel_depth = rec["bevel_depth"]
    cu.bevel_resolution = rec["bevel_resolution"]
    cu.extrude = rec["extrude"]
    cu.offset = rec["offset"]
    cu.resolution_u = rec["resolution_u"]
    cu.use_fill_caps = rec["use_fill_caps"]
    for attr in ("twist_mode", "bevel_mode", "twist_smooth"):
        if attr in rec:
            try:
                setattr(cu, attr, rec[attr])
            except Exception:
                pass
    for sp in rec["splines"]:
        s = cu.splines.new(sp["type"])
        s.points.add(len(sp["points"]) - 1)
        s.use_cyclic_u = sp["cyclic"]
        for pt, co in zip(s.points, sp["points"]):
            pt.co = (co[0], co[1], co[2], 1.0)
    return cu


# ==========================================================================
# main assembly
# ==========================================================================
def _modifier(obj, rec):
    if rec.get("type") != "BEVEL":
        return
    m = obj.modifiers.new("Bevel", "BEVEL")
    for attr in ("width", "segments", "limit_method", "angle_limit",
                 "harden_normals", "affect", "miter_outer",
                 "use_clamp_overlap", "offset_type"):
        if attr in rec:
            try:
                setattr(m, attr, rec[attr])
            except Exception:
                pass


def assemble(spec_path, reset=True, material_preview=False, log=print):
    stats = {"node_failures": [], "unknown_part_kinds": [], "objects": 0,
             "meshes": 0, "curves": 0, "lights": 0, "cameras": 0}

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    if reset:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # ---- scene settings ----
    s = spec["scene"]
    scene.name = s["name"]
    scene.frame_start = s["frame_start"]
    scene.frame_end = s["frame_end"]
    scene.frame_current = s["frame_current"]
    scene.unit_settings.system = s["unit_system"]
    scene.unit_settings.scale_length = s["unit_scale"]
    r = s["render"]
    scene.render.engine = r["engine"]
    scene.render.resolution_x = r["resolution_x"]
    scene.render.resolution_y = r["resolution_y"]
    scene.render.resolution_percentage = r["resolution_percentage"]
    scene.render.film_transparent = r["film_transparent"]
    v = s["view"]
    try:
        scene.view_settings.view_transform = v["view_transform"]
        scene.view_settings.look = v["look"]
        scene.view_settings.exposure = v["exposure"]
        scene.view_settings.gamma = v["gamma"]
    except Exception:
        pass

    # ---- materials ----
    mats = {}
    for rec in spec["materials"]:
        m = bpy.data.materials.new(rec["name"])
        m.use_fake_user = False
        try:
            m.diffuse_color = rec["diffuse_color"]      # viewport display colour
        except Exception:
            pass
        for attr in ("metallic", "roughness", "use_backface_culling",
                     "blend_method", "surface_render_method"):
            if attr in rec:
                try:
                    setattr(m, attr, rec[attr])
                except Exception:
                    pass
        if rec.get("node_tree"):
            m.use_nodes = True
            build_node_tree(m.node_tree, rec["node_tree"], stats)
        mats[rec["name"]] = m

    # ---- world ----
    wrec = spec.get("world")
    if wrec:
        w = bpy.data.worlds.new(wrec["name"])
        scene.world = w
        if "color" in wrec:
            try:
                w.color = wrec["color"]          # used when use_nodes is off
            except Exception:
                pass
        if wrec.get("node_tree"):
            w.use_nodes = True
            build_node_tree(w.node_tree, wrec["node_tree"], stats)

    # ---- collections ----
    colls = {}
    for name in spec["collections"]:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        colls[name] = c

    # ---- part templates ----
    templates = build_part_library(spec, stats)

    # ---- objects ----
    pending_renames = []
    for rec in spec["objects"]:
        tpl = templates.get(rec["part"])
        if tpl is None:
            stats["node_failures"].append("missing part %s" % rec["part"])
            continue
        data = tpl.copy()
        obj = bpy.data.objects.new(rec["name"], data)
        coll = colls.get(rec["collection"]) or scene.collection
        coll.objects.link(obj)
        obj.rotation_mode = rec.get("rotation_mode", "XYZ")
        obj.location = rec["loc"]
        obj.rotation_euler = rec["rot"]
        obj.scale = rec["scale"]
        obj.hide_render = rec.get("hide_render", False)
        for mname in rec["materials"]:
            obj.data.materials.append(mats.get(mname) if mname else None)
        for mrec in rec["modifiers"]:
            _modifier(obj, mrec)
        pending_renames.append((data, rec["data_name"]))
        stats["objects"] += 1
        stats["meshes" if rec["kind"] == "mesh" else "curves"] += 1

    # drop the templates now that every object owns a private copy
    for tpl in templates.values():
        try:
            if tpl.users == 0:
                (bpy.data.meshes if isinstance(tpl, bpy.types.Mesh)
                 else bpy.data.curves).remove(tpl)
        except Exception:
            pass

    # ---- restore datablock names (two passes to dodge collisions) ----
    for i, (data, _) in enumerate(pending_renames):
        data.name = "__staging_%04d__" % i
    for data, name in pending_renames:
        if name:
            try:
                data.name = name
            except Exception:
                pass

    # ---- lights ----
    for rec in spec["lights"]:
        lt = bpy.data.lights.new(rec["data_name"], type=rec["type"])
        for attr in ("energy", "size", "size_y", "spread", "color",
                     "use_shadow", "shape"):
            if rec.get(attr) is not None and hasattr(lt, attr):
                try:
                    setattr(lt, attr, rec[attr])
                except Exception:
                    pass
        obj = bpy.data.objects.new(rec["name"], lt)
        (colls.get(rec["collection"]) or scene.collection).objects.link(obj)
        obj.rotation_mode = rec.get("rotation_mode", "XYZ")
        obj.location = rec["loc"]
        obj.rotation_euler = rec["rot"]
        obj.scale = rec["scale"]
        stats["lights"] += 1

    # ---- cameras ----
    for rec in spec["cameras"]:
        cd = bpy.data.cameras.new(rec["data_name"])
        for attr in ("lens", "sensor_width", "sensor_height", "sensor_fit",
                     "clip_start", "clip_end"):
            if attr in rec and hasattr(cd, attr):
                try:
                    setattr(cd, attr, rec[attr])
                except Exception:
                    pass
        if rec.get("dof") is not None:
            try:
                cd.dof.use_dof = rec["dof"]
            except Exception:
                pass
        obj = bpy.data.objects.new(rec["name"], cd)
        (colls.get(rec["collection"]) or scene.collection).objects.link(obj)
        obj.rotation_mode = rec.get("rotation_mode", "XYZ")
        obj.location = rec["loc"]
        obj.rotation_euler = rec["rot"]
        obj.scale = rec["scale"]
        stats["cameras"] += 1

    if spec["scene"].get("camera"):
        scene.camera = bpy.data.objects.get(spec["scene"]["camera"])

    # ---- optional: make the file open looking like the source ----
    if material_preview:
        for scr in bpy.data.screens:
            for area in scr.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.shading.type = "MATERIAL"
                            space.shading.color_type = "MATERIAL"
                            space.shading.use_scene_world = True
                            space.shading.use_scene_lights = True

    log("ASSEMBLE_JSON " + json.dumps(stats, ensure_ascii=False))
    return stats


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--material-preview", action="store_true")
    args = ap.parse_args(argv)

    assemble(args.spec, material_preview=args.material_preview)
    if args.out:
        out = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
        print("ASSEMBLE_SAVED " + json.dumps({"out": out,
                                              "bytes": os.path.getsize(out)}))


if __name__ == "__main__":
    main()
