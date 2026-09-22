# Hygiene verification — stripping embedded Text datablocks

A `.blend` can carry Text datablocks (scripts) that travel with the file. This scene exists in
**two copies**, and each had to be stripped separately — cleaning one leaves the other still
carrying the script. Both strips are recorded below, each proven with `compare_blends.py`, which
compares a *scene fingerprint*, not the file bytes.

| # | Copy | Before | After | Embedded script | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | `scene/bronze_bell_hall_v2.3.0.blend` — repo, editable | 673,734 B | 635,575 B | `文本` — 1,138 lines / 40,679 chars | IDENTICAL SCENE |
| 2 | `01_scene/bronze_bell_hall_v2.3.0_baked.blend` — delivery zip, baked | 6,333,479 B | 6,294,221 B | `文本` — the same script | IDENTICAL SCENE |

Both files carried the same datablock: `blend_repro_audit.py`, this project's own cost-audit
script, left behind after it was run inside the file.

Text datablocks are **not part of the scene graph**, so removing them leaves the fingerprint
byte-identical. That is what makes the strips safe, and it is why the "0 m deviation" lines below
are the proof rather than a coincidence.

---

## 1. Repo copy — `scene/bronze_bell_hall_v2.3.0.blend`

- A = the pre-strip backup written by `strip_embedded_scripts.py` (`*.backup.blend`, gitignored)
- B = the committed file

```bash
blender.exe -b scene/bronze_bell_hall_v2.3.0.blend -P compare_blends.py -- --save a.json
blender.exe -b scene/bronze_bell_hall_v2.3.0.backup.blend -P compare_blends.py -- --save b.json
python compare_blends.py --diff a.json b.json --report hygiene-verify.md
```

### compare_blends

- A: `scene\bronze_bell_hall_v2.3.0.backup.blend`  digest `78b135637a82de87`
- B: `scene\bronze_bell_hall_v2.3.0.blend`  digest `78b135637a82de87`

#### scene equivalence

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
OK   evaluated_geometry.curve_verts      14400                  -> 14400
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

#### measured deviation

```
objects compared            756
worst bbox deviation        0 m  (Attendant bench apron)
worst placement deviation   0 m  (None)
objects over 1e-05 m        0
```

#### datablocks outside the scene graph

```
A text datablocks  ['文本']
B text datablocks  []
```

#### verdict

**IDENTICAL SCENE**

---

## 2. Delivery copy — `01_scene/bronze_bell_hall_v2.3.0_baked.blend`

Found during a post-delivery audit: the package shipped its own baked `.blend`, a *different file*
from the repo's editable one, and that copy **still carried the script**. The `.glb` was never
affected — glTF has no datablock concept — but the `.blend` did.

- A = the package's original baked `.blend`
- B = the stripped rebuild that replaced it in `BronzeBellHall_Delivery_*_clean.zip`

```bash
blender.exe -b *_baked.blend       -P compare_blends.py -- --save a.json
blender.exe -b *_baked_stripped.blend -P compare_blends.py -- --save b.json
python compare_blends.py --diff a.json b.json --report verify_baked_strip.md
```

### compare_blends

- A: `bronze_bell_hall_v2.3.0_baked.blend`  digest `8dce78fdcee5f1f4`
- B: `bronze_bell_hall_v2.3.0_baked_stripped.blend`  digest `8dce78fdcee5f1f4`

#### scene equivalence

```
OK   counts.by_type                     {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668} -> {'CAMERA': 5, 'CURVE': 88, 'LIGHT': 11, 'MESH': 668}
OK   counts.collections                 14                     -> 14
OK   counts.materials                   115                    -> 115
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
OK   collection_membership.*            (all 10 collections identical)
OK   meshes                             668 items identical
OK   curves                             88 items identical
OK   lights                             11 items identical
OK   cameras                            5 items identical
OK   material_slots                     837 items identical
OK   materials                          115 items identical
OK   digest 8dce78fdcee5f1f4 vs 8dce78fdcee5f1f4
```

#### measured deviation

```
objects compared            756
worst bbox deviation        0 m  (Attendant bench apron)
worst placement deviation   0 m  (None)
objects over 1e-05 m        0
```

#### datablocks outside the scene graph

```
A text datablocks  ['文本']
B text datablocks  []
```

#### file deltas

```
sha256 before   45a2704bb6fecebca94d9e5fe189d2bae9a3f0149d4272aba1a5f7f7306633eb
sha256 after    3278dfaa38ccc2e891c3740aa86722b051763118e887f5b990867b7c63aeb842
size            6,333,479 B -> 6,294,221 B  (-39,258 B)
```

The 115 materials here versus 22 in the repo copy are the baked export materials, not a
discrepancy — the two files are different artifacts of the same scene.

#### verdict

**IDENTICAL SCENE**

---

## Repackaging

`BronzeBellHall_Delivery_2026-09-21_clean.zip` was rebuilt from the original package with **two**
entries substituted — the stripped `.blend`, and `README.md` (which was extended with a
`File integrity` block carrying the post-strip sha256 values, a hygiene statement, and a pointer to
this repository). Note that the hash table therefore documents the *clean* package, not the original.

Every other entry was verified byte-identical by sha256, and `zipfile.testzip()` reported all CRCs
valid:

```
entries             347  ->  347
changed             README.md
                    01_scene/bronze_bell_hall_v2.3.0_baked.blend
unchanged           345 entries, sha256 identical
testzip             OK (all CRCs valid)
readme              25,806 B -> 29,130 B  (414 -> 462 lines)
```

Reproducing the substitutions from the original package:

```bash
blender.exe -b 01_scene/bronze_bell_hall_v2.3.0_baked.blend \
    -P strip_embedded_scripts.py -- --out <stripped>.blend --no-backup
# then swap <stripped>.blend and the updated README.md back into the archive,
# replacing only those two entries and copying every other entry verbatim
```

⚠ The original `BronzeBellHall_Delivery_2026-09-21.zip` on the Desktop was **never modified** —
the clean package is a separate file. Whether to ship it is the author's call, since the original
may already have been sent.

