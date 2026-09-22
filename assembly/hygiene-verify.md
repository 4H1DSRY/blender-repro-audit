# compare_blends

- A: `D:\Claw\blender-repro-audit\scene\bronze_bell_hall_v2.3.0.backup.blend`  digest `78b135637a82de87`
- B: `D:\Claw\blender-repro-audit\scene\bronze_bell_hall_v2.3.0.blend`  digest `78b135637a82de87`

## scene equivalence

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

## measured deviation

```
objects compared            756
worst bbox deviation        0 m  (Attendant bench apron)
worst placement deviation   0 m  (None)
objects over 1e-05 m       0
```

## datablocks outside the scene graph

```
A text datablocks  ['文本']
B text datablocks  []
```

note: Text datablocks are not part of the scene graph, so removing an embedded script changes the file without changing the cell above.

## verdict

**IDENTICAL SCENE**
