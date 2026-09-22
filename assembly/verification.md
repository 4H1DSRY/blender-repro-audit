# Assembly verification

**source** `D:\Claw\blender-repro-audit\scene\bronze_bell_hall_v2.3.0.blend`
**spec** `D:/Claw/blender-repro-audit/assembly/assembly_spec.json`
**blender** 5.2.0 LTS

## 1. source scene

```
objects         {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668}
materials       22
collections     14
source geom     18944 verts / 15021 faces / 1328 curve points
evaluated geom  {'mesh_verts': 92912, 'mesh_faces': 90949, 'mesh_tris': 183878, 'curve_verts': 14400, 'curve_faces': 13824, 'curve_tris': 27648, 'total_tris': 211526}
digest          78b135637a82de87
```

## 2. committed spec vs a fresh extraction from the source

OK   committed assembly_spec.json is equivalent to the extraction re-run now

## 3. rebuilt scene

```
objects         {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668}
materials       22
collections     14
geometry        18944 verts / 15021 faces / 1328 curve points
evaluated geom  {'mesh_verts': 92912, 'mesh_faces': 90949, 'mesh_tris': 183878, 'curve_verts': 14400, 'curve_faces': 13824, 'curve_tris': 27648, 'total_tris': 211526}
digest          78b135637a82de87
```

## 4. check A — scene fingerprint, source vs rebuilt

```
OK   counts.by_type                     {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668} -> {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668}
OK   counts.collections                 14                     -> 14
OK   counts.materials                   22                     -> 22
OK   counts.objects                     772                    -> 772
OK   source_geometry.curve_control_points 1328                   -> 1328
OK   source_geometry.mesh_faces         15021                  -> 15021
OK   source_geometry.mesh_verts         18944                  -> 18944
OK   evaluated_geometry.curve_faces     13824                  -> 13824
OK   evaluated_geometry.curve_tris      27648                  -> 27648
OK   evaluated_geometry.curve_verts     14400                  -> 14400
OK   evaluated_geometry.mesh_faces      90949                  -> 90949
OK   evaluated_geometry.mesh_tris       183878                 -> 183878
OK   evaluated_geometry.mesh_verts      92912                  -> 92912
OK   evaluated_geometry.total_tris      211526                 -> 211526
OK   collection_membership.01 | Room and circulation.001 248                    -> 248
OK   collection_membership.02 | Central dais and suspension.001 12                     -> 12
OK   collection_membership.03 | Bronze bell ensemble 159                    -> 159
OK   collection_membership.04 | Furniture and wall fittings 190                    -> 190
OK   collection_membership.05 | Coffers and lanterns 59                     -> 59
OK   collection_membership.06 | Light and viewpoints.001 8                      -> 8
OK   collection_membership.07 | Final coherence adjustments 2                      -> 2
OK   collection_membership.08 | Final review fixes 1                      -> 1
OK   collection_membership.09 | Craft refinement 47                     -> 47
OK   collection_membership.10 | Advanced construction 46                     -> 46
OK   meshes                             668 items identical
OK   curves                             88 items identical
OK   lights                             11 items identical
OK   cameras                            5 items identical
OK   material_slots                     837 items identical
OK   materials                          22 items identical
OK   digest 78b135637a82de87 vs 78b135637a82de87
```

### measured deviation (not assumed)

```
objects compared            756
compare tolerance           1e-05 m
worst bbox deviation        9.54e-07 m  (Small hanging bell.004)
worst placement deviation   2.38e-07 m  (Dais step)
objects over 1 um           0
objects over the tolerance  0
absent from second scene    []
```

| object | deviation | source dims | rebuilt dims |
|---|---|---|---|
| `Small hanging bell.004` | 9.54e-07 m | [0.223868847, 0.260312557, 0.690000057] | [0.223867893, 0.26031208, 0.690000057] |
| `Small hanging bell.005` | 9.54e-07 m | [0.223868847, 0.260312557, 0.690000057] | [0.223867893, 0.26031208, 0.690000057] |
| `Splayed upper bracket` | 7.15e-07 m | [0.25999999, 0.25999999, 0.736932695] | [0.25999999, 0.25999999, 0.73693198] |
| `Splayed upper bracket.001` | 7.15e-07 m | [0.25999999, 0.25999999, 0.736932695] | [0.25999999, 0.25999999, 0.73693198] |
| `Small hanging bell` | 4.77e-07 m | [0.223868608, 0.260312557, 0.690000057] | [0.223868132, 0.26031208, 0.690000057] |
| `Small hanging bell.001` | 4.77e-07 m | [0.224834442, 0.261435509, 0.63499999] | [0.224833965, 0.261435986, 0.63499999] |
| `Small hanging bell.003` | 4.77e-07 m | [0.224834204, 0.261435509, 0.63499999] | [0.224834204, 0.261435986, 0.63499999] |
| `Small hanging bell.006` | 4.77e-07 m | [0.224834204, 0.261435509, 0.63499999] | [0.224834204, 0.261435986, 0.63499999] |
| `Small hanging bell.008` | 4.77e-07 m | [0.224834442, 0.261435509, 0.63499999] | [0.224833965, 0.261435986, 0.63499999] |
| `Small hanging bell.009` | 4.77e-07 m | [0.223868608, 0.260312557, 0.690000057] | [0.223868132, 0.26031208, 0.690000057] |

## 5. check B — spec round-trip (extract -> assemble -> extract)

```
OK   spec.scene          identical (9 keys)
OK   spec.world          identical (3 keys)
OK   spec.collections    identical (14 entries)
OK   spec.materials      identical (22 entries)
OK   spec.part_library   identical (186 keys)
OK   spec.objects        identical (756 entries)
OK   spec.lights         identical (11 entries)
OK   spec.cameras        identical (5 entries)
```

## verdict

| check | result |
|---|---|
| A scene fingerprint | PASS |
| B spec round-trip | PASS |
| committed spec matches source | PASS |
| assembler warnings | 0 node failures, 0 unknown parts, 0 non-bevel modifiers |
