# Bronze Bell Hall — Manual Scene Reconstruction & Part-Decomposition Toolkit

**This repository comes out of a manual scene-reconstruction job of mine.** Working from a single
reference image of a bronze-bell ceremonial hall, I rebuilt the scene by hand in Blender — timber
post-and-beam framing, a great bell on a gallows frame, two racks of small bells on bronze hangers,
offering tables and ritual vessels, kneeling attendants, a colonnade, a coffered ceiling, stone
paving and rear wall niches. The scripts here are the tooling I wrote for that job; they turned out
to generalise to any Blender scene, so I split them out into a repo of their own. All of them run in
Blender's headless mode — no GUI.

**Reference image:** supplied by Prof. Eugene Ch'ng (庄以仁), 22 July 2026.

## The reconstruction, in short

- **Decompose before modelling.** The hall *reads* as enormously complex, but it is built from a
  small set of repeated elements — beams, post collars, panel rails, bell hangers, bell bodies —
  arranged in arrays. Model one of each and place instances; that is the whole game.
- **Build in passes:** timber frame → bronze hardware → furnishings and figures → lighting.
- **Procedural materials, zero textures.** Every material is node-built, so the palette is tuned
  from a handful of parameters and the file stays self-contained.
- **Result:** 668 mesh objects, 35,942 triangles, 22 materials, no rig, no animation — and after
  clustering, only **91 distinct shapes** in **75 semantic families** (86.4% compression). That
  ratio is what made the job tractable. Add the 88 curve objects (see trap 3) and the scene
  totals **756 geometry objects / 63,590 triangles**.

| Path | What it is |
| --- | --- |
| `scene/` | The source scene itself — `.blend` + whole-scene `.glb` |
| `blend_repro_audit.py` | Cost audit — hours to rebuild the scene from scratch |
| `blend_extract_parts.py` | Extract unique parts, cluster them, export `.glb` |
| `bake_materials.py` | Procedural materials → baked PBR maps |
| `bake_curves_and_export.py` | Curve objects → same bake → whole-scene `.glb` export |
| `audit_scene_glb.py` | Read a `.glb` back and check the texture wiring |
| `make_glb_index.py` | Builds `exports/glb/_INDEX.csv` |
| `examples/`, `exports/glb/` | Reports from this scene; 91 PBR-textured `.glb` parts |
| `assembly/` | Parametric rebuild — spec, assembler, verifier, and the proof |
| `scene_fingerprint.py` | Order-independent scene fingerprint (shared by the verifier) |
| `compare_blends.py` | Prove two `.blend` files hold the same scene |
| `strip_embedded_scripts.py` | Strip embedded Text datablocks before shipping |

**`scene/`** holds the two files everything else was run on:

- `bronze_bell_hall_v2.3.0.blend` (621 KB) — the working file. 22 materials, all procedural
  and no image textures, so it carries no external dependency at all. Re-saved to strip the
  embedded audit script (trap 7); the scene itself is unchanged, per `assembly/hygiene-verify.md`.
- `bronze_bell_hall_v2.3.0.glb` (8.07 MB) — the whole scene, engine-ready: 756 geometry nodes
  sharing 186 mesh datablocks, 192 embedded maps.

Point `blend_repro_audit.py` and `blend_extract_parts.py` at that `.blend` and the reports in
`examples/` reproduce.

## 1. `blend_repro_audit.py` — cost audit

Answers *"how many hours would a skilled 3D artist need to reproduce this scene from scratch?"*

```bash
"path/to/blender.exe" -b "scene.blend" -P blend_repro_audit.py -- --out "out_dir"
```

→ `audit_report.md` (human) + `audit.json` (machine).

**Why you cannot just count objects.** Charging a full unit of work per object inflates an instanced
scene by an order of magnitude: nine objects named `Small hanging bell`, `.001`, `.002` … each at
1598 triangles price the job at 842 hours. Grouping by **`(base name, triangle count)`** instead
charges the first copy in full and every further copy only as **instance placement** — the same job
comes out at **97.2 hours**.

It reports an **appearance-equivalent** figure (visually identical result, baking allowed) alongside
a **structural-equivalent** one (clean original topology and real material nodes), plus an interval
and a hidden-cost share that is *already included* in the totals, not an addition. Rates and
difficulty bands live in `RATES` / `DIFFICULTY_BANDS` at the top of the script — retune them for a
different skill level.

## 2. `blend_extract_parts.py` — extract, cluster, export

Answers *"how many distinct parts are actually in this scene, and which objects are the same thing?"*

```bash
"path/to/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "out_dir" --export-glb "assets_dir"
```

→ `parts_cluster_report.md` + `parts_manifest.csv`.

| Flag | Meaning |
| --- | --- |
| `--out DIR` | Report output directory |
| `--export-glb DIR` | Write each representative to `<DIR>/<family>/<part>.glb` |
| `--mark-assets` | Mark representatives as Blender Assets |
| `--tol FLOAT` | Tolerance for "same shape", default `0.02` (2%) |
| `--min-tris INT` / `--skip-variants` | Drop fragments below N triangles / omit `__n<count>` from filenames |

**Rotation-invariant signature — the crux.** A beam used along `X` and the same beam used along `Y`
are one part rotated about different axes: different names *and* different mesh coordinates, but
identical **sorted** bounding-box edges. So the signature takes the local-space bbox scaled by the
object's scale and sorts the three edges, comparing them through a logarithmic bucket
(`int(round(log(v) / log(1 + rel_tol)))`) so a single relative tolerance holds across all magnitudes.

| Layer | Criterion | Purpose |
| --- | --- | --- |
| L1 exact group | verts + polys + sorted bbox + area + material slots | Interchangeable duplicates |
| L2 shape group | as L1, minus materials | Same shape, different material |
| L3 parameter family | verts + polys + first two sorted bbox edges (length may vary) | Same cross-section, different length |
| L4 semantic family | name prefix | Human-readable grouping |

L3 earns its keep: `Small bell hanger` exists at three lengths (0.37 / 0.425 / 0.48), which L1/L2
alone would classify as three different shapes. Representative selection: no `.001` suffix wins →
then the shortest name → then the highest triangle count.

## 3. `bake_materials.py` — procedural materials → PBR maps

Blender's glTF exporter is a **texture** exporter, not a node exporter. Every material here is a
procedural node network (noise, wave, colour ramp — 7 to 27 nodes, zero image textures). Export them
directly and the whole chain is thrown away, collapsing to `baseColorFactor = [1,1,1,1]`: white
models, no bronze patina, no timber grain. This script flattens each material into maps first — base
colour to an sRGB albedo PNG, roughness and metallic into one packed **ORM** PNG (G = roughness,
B = metallic, per the glTF spec) wired through a Separate Color node so the exporter emits a real
`metallicRoughnessTexture`.

```bash
"path/to/blender.exe" -b "scene.blend" -P bake_materials.py -- \
    --save "out/scene_baked.blend" [--tex-dir "out/textures"] [--samples 1]
```

It bakes once per shape-group representative and shares the result across that group's instances,
allocates resolution by triangle budget (128 px for small parts → 512 px above 600 triangles), skips
the ORM bake for materials whose roughness *and* metallic are both constants, and never modifies the
source `.blend`.

## 4. `bake_curves_and_export.py` — curves, then the whole-scene `.glb`

`bake_materials.py` assumes the scene *is* meshes. This scene is not: 88 of its objects are `CURVE`
objects carrying 27,648 real triangles — the bronze rings, the bell crown and mouth-rim mouldings,
the gilded panel borders. This script is the last mile. It brings them into the same bake pipeline
and then writes the engine-ready `.glb`.

```bash
"path/to/blender.exe" -b "out/scene_baked.blend" -P bake_curves_and_export.py -- \
    --dst "out/scene.glb" [--tex-dir "out/textures"] [--samples 1]
```

Five steps, in order:

1. **Record before converting.** Every curve object's triangle count is captured first, so the
   conversion can later be *shown* not to have lost geometry rather than assumed to be safe.
2. **Curves to meshes**, all 88 at once via `bpy.ops.object.convert(target="MESH")`.
3. **Re-cluster with the pipeline's own tolerance** (`cluster(objs, 0.02, 0)`). The 88 curve objects
   collapse to just **7 shape groups**, so 7 representatives get baked instead of 88 and the map
   count drops **176 to 14**. The pipeline notes record that these groups were checked to share one
   material (`mixed_materials = 0`) — that check is what makes one bake per group a safe shortcut
   rather than a gamble.
4. **Purge materials nothing uses — across every object type.** This is the fix for trap 3: the
   sweep walks `bpy.data.objects`, not just meshes. Walk meshes only and the two curve-only
   materials look like zero-reference orphans, get deleted, and those parts arrive in the engine
   with no material at all and no error anywhere.
5. **Collapse instances, then export.** Objects sharing both a geometry fingerprint and a material
   tuple are made to share one mesh datablock (**756 objects to 186 datablocks**), orphan datablocks
   are swept, and the scene is exported with `export_apply=False` — see trap 9 for why that flag is
   not optional.

Nothing is written back to disk; the input `.blend` is never modified.

## 5. `audit_scene_glb.py` — read the `.glb` back and check the wiring

Baking is only correct if the maps actually **arrive**. glTF export drops procedural node networks
*silently* — no error, no warning, just a white model. So the last step asserts against the artifact
instead of trusting the exporter.

This one is plain Python — **no Blender needed**:

```bash
python audit_scene_glb.py "scene/bronze_bell_hall_v2.3.0.glb" [--out report.txt]
```

It parses the GLB container by hand (magic `0x46546C67`, JSON chunk `0x4E4F534A`, BIN chunk
`0x004E4942`, each chunk 4-byte aligned) and reports:

- **object counts** — nodes, meshes, materials, images, textures, samplers, cameras;
- **where the bytes went** — bufferViews split into image versus geometry. On this scene: 192 image
  views totalling **6.78 MB**, 573 geometry views totalling **1.05 MB**;
- accessor types, mesh primitive count, image mime types, and duplicated image data;
- **the actual assertion** — per material, whether `baseColorTexture`,
  `metallicRoughnessTexture`, `normalTexture` and `emissiveTexture` are wired, plus a count of
  materials still **pure white** (`baseColorFactor == [1,1,1]` with no base texture).

On this scene it returns `baseColorTexture 98/98`, `metallicRoughnessTexture 94/98`,
`normalTexture 0/98`, `pure white 0`. That is how "normal maps are not baked" gets *measured*
rather than asserted. The `BAKED_CV_g*` names in its sample output are also a direct check that
step 3 above actually ran on the curve groups.

### The pipeline, end to end

```bash
B="path/to/blender.exe"
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P blend_repro_audit.py    -- --out out/
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P blend_extract_parts.py  -- --out out/ --export-glb out/glb
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P bake_materials.py       -- --save out/baked.blend
$B -b "out/baked.blend"                     -P bake_curves_and_export.py -- --dst out/scene.glb
   python audit_scene_glb.py out/scene.glb --out out/audit.txt
```

Every stage is repeatable from the `scene/` files committed here. Only the two bake/export steps
touch Blender scene state, and neither modifies its input `.blend`.

## 6. `assembly/` — parametric rebuild from a spec

The tools above audit, bake and export the scene; `assembly/` **rebuilds** it. `extract_assembly_spec.py` dumps the
whole hall to a declarative JSON spec — 186 recipes covering 756 objects, all 22 procedural node
graphs, the lighting rig and the cameras. `assemble_scene.py` then reconstructs every object from
primitives and shader graphs in a fresh file, never opening the original `.blend`.
`verify_assembly.py` proves the rebuild is the same scene, two independent ways.

Both checks pass and the digest over the **evaluated** geometry matches exactly
(`78b135637a82de87`): across 756 objects the worst bounding-box deviation is **0.95 um**. Commands
are in `assembly/README.md`; the full report is `assembly/verification.md`.

Not reproduced: Blender's UI state (workspaces, screen layout) and embedded Text datablocks.

## Traps worth knowing

1. **Instances inflate audits** — group by `(base name, triangle count)` before charging hours;
   the difference here is 842 h versus 97.2 h.
2. **L3 merges geometric twins, not semantic twins.** A 0.1 × 0.1 twelve-face prism might be a
   lantern bracket or a table leg. The report marks such merges `⚠ spans N semantic families` —
   split the group back apart by semantic family before acting on it.
3. **Mesh-only is not the whole scene.** `CURVE`, `SURFACE`, `FONT` and `META` objects can carry real
   visible geometry — here **88 curve objects holding 27,648 triangles**, whose shared materials look
   exactly like zero-reference orphans. Delete those and your parts arrive in the engine
   material-less, with no error message anywhere. Convert non-mesh types first, or build the "in use"
   material set from *all* object types.
4. **`bpy.ops.object.bake` bakes every material slot**, and each slot's material needs an active,
   selected image texture node, or the run dies mid-way. Install a temporary image node in *every*
   material on the object (the fix lives in `bake_socket()`). Flatten procedural inputs by routing the
   socket to an **Emission** node and baking `EMIT` — no light sampling, so `--samples 1` is enough.
5. **`|` in names bites twice:** escape it in Markdown tables, and use `safe_name()` for index keys,
   because the exporter rewrites pipes to `_` (`Great bell | hollow cast shell`).
6. **`Material.use_nodes` is deprecated in Blender 6.0** — use `getattr(mat, "node_tree", None)`.
7. **A `.blend` can carry code.** Text datablocks are invisible in the viewport but travel with
   the file — a build or audit script left behind, or pasted into the Text Editor, ships to
   whoever receives the `.blend`: internal notes, absolute paths and all. This scene arrived with
   our own `blend_repro_audit.py` embedded (1,138 lines / 40,679 chars). Run
   `strip_embedded_scripts.py` before committing or delivering; it removes Text datablocks only,
   and `compare_blends.py` proves the scene is untouched (measured: 0 m deviation, all 756 objects).
   **Then check every copy.** The same scene exists in two places here — a 621 KB editable `.blend`
   in the repo and a 6.3 MB baked `.blend` inside the delivery zip — and stripping one leaves the
   other still carrying the script. Enumerate `bpy.data.texts` in *each* `.blend` before packaging,
   not just the one you happen to be working on.
8. **Never fold a derived value into an equivalence check.** A bounding-box size is `max - min`,
   so a spec that quantises lengths to 1 um can round the *difference* onto the far side of a
   boundary and report a phantom 1e-6 mismatch — 6 of 668 objects did exactly that here. Compare
   derived lengths against a stated tolerance, and print the measured deviation next to the PASS.
   The tolerance is honest too: Blender stores mesh vertices as float32, whose quantum at this
   scene's ~10 m extent is ~0.6 um, so a 1 um spec discards nothing the `.blend` could represent.

9. **`export_apply=True` silently destroys instancing.** It evaluates every object separately, so
   each one gets its own copy of the evaluated mesh and the shared datablocks built in the previous
   step are gone — 756 objects sharing 186 meshes becomes 756 meshes, and the `.glb` grows
   accordingly with no error message. Here it is not a performance trade-off but a correctness one:
   the sharing has to be built by hand first, and the exporter then told **`export_apply=False`** to
   leave it alone.

## Environment & limitations

Blender 5.2 LTS (`bpy` API, `-b` headless mode) for every stage except `audit_scene_glb.py`,
which is plain Python and needs no Blender at all. Standard library only, no third-party
dependencies.

- **Absolute hours carry roughly ±35% uncertainty**, driven mainly by hand-tuned materials. The
  structural diagnosis (part count, dedup ratio, hidden-cost share) is reliable; treat the hour
  figure as an order of magnitude only. Rates are calibrated for a *skilled artist*.
- L3 parameter families need human review by semantic family before you act on the merges.
- The bake covers base colour and metallic/roughness only. **Normal maps are not baked**, so relief
  carried by bump nodes does not survive the glTF export.
- Part extraction operates on mesh objects; a scene with geometry-carrying non-mesh objects needs the
  conversion step in trap 3 first.
- The exported `.glb` carries **756 geometry nodes over 186 mesh datablocks** plus 192 embedded maps.
  `audit_scene_glb.py` prints those counts directly, so it doubles as a regression check on the export.

---
---

# 青铜编钟厅 · 人工场景复现与部件拆解工具

**这个仓库来自我的一项人工场景复现工程。** 我照着一张青铜编钟厅的参考图，用 Blender 手工把整座
场景复现了出来 —— 木构梁架、架上的大钟、两列小钟及青铜挂件、供桌与礼器、跽坐侍者、廊柱、
藻井天花、石铺地面与后壁壁龛。这里的脚本是我为这项工程量身写的工具；写完后发现它们对任何
Blender 场景都通用，就单独抽出来成了这个仓库。所有脚本都跑在无头模式（headless），不打开 GUI。

**参考图来源：** 庄以仁教授（Prof. Eugene Ch'ng）提供，2026 年 7 月 22 日。

## 这项复现工作，几句话说完

- **先分解，再建模。** 这座厅堂*看起来*极其复杂，实际是由少量重复构件 —— 梁、柱头箍、板条、
  钟挂件、钟体 —— 阵列排布而成。各建一个、其余放实例，就是全部诀窍。
- **分轮推进：** 木构梁架 → 青铜配件 → 陈设与人像 → 灯光。
- **全程序化材质，零贴图。** 每个材质都是节点搭建，整套配色由少数几个参数控制，文件保持自包含。
- **结果：** 668 个网格物体、35,942 三角面、22 个材质、无骨骼、无动画 —— 聚类之后只有
  **91 种不同形状**，归入 **75 个语义族**（压缩率 86.4%）。正是这个比例让整件事可行。再加上 88 个曲线物体（见第 3 条坑），整场景合计
**756 个几何物体 / 63,590 三角面**。

| 路径 | 说明 |
| --- | --- |
| `scene/` | 源场景本体 —— `.blend` + 整场景 `.glb` |
| `blend_repro_audit.py` | 工时成本审计 —— 从零重建需要多少小时 |
| `blend_extract_parts.py` | 提取唯一部件、聚类、导出 `.glb` |
| `bake_materials.py` | 程序化材质 → 烘焙 PBR 贴图 |
| `bake_curves_and_export.py` | 曲线物体并入同一套烘焙 → 导出整场景 `.glb` |
| `audit_scene_glb.py` | 回读 `.glb`，检查贴图是否真的接上 |
| `make_glb_index.py` | 生成 `exports/glb/_INDEX.csv` |
| `examples/`、`exports/glb/` | 本场景的工具输出；91 个已带 PBR 贴图的 `.glb` 部件 |
| `assembly/` | 参数化重建 —— spec、装配器、验证器与验证报告 |
| `scene_fingerprint.py` | 顺序无关的场景指纹（验证器共用） |
| `compare_blends.py` | 证明两个 `.blend` 是同一个场景 |
| `strip_embedded_scripts.py` | 交付前剥离内嵌的 Text 数据块 |

**`scene/`** 里放着上面所有工具实际处理的源文件：

- `bronze_bell_hall_v2.3.0.blend`（621 KB）—— 工作文件。22 个材质全部程序化、零贴图，
  因此**没有任何外部依赖**。已重新保存以剥离内嵌的审计脚本（见第 7 条坑）；
  场景本体未变，证据见 `assembly/hygiene-verify.md`。
- `bronze_bell_hall_v2.3.0.glb`（8.07 MB）—— 整场景，引擎即用：756 个几何节点共享
  186 个网格数据块，192 张贴图全部内嵌。

把 `blend_repro_audit.py` 与 `blend_extract_parts.py` 指向这个 `.blend`，`examples/` 里的报告即可复现。

## 1. `blend_repro_audit.py` —— 工时成本审计

回答 *「一个熟练 3D 美术从零复现这个场景，需要多少小时？」*

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_repro_audit.py -- --out "输出目录"
```

→ `audit_report.md`（人读）+ `audit.json`（机读）。

**为什么不能直接数物体。** 「一个物体算一份工时」在实例化场景里会把数字放大一个数量级：同一个
部件存在 `Small hanging bell` / `.001` / `.002` …… 九个物体，每个 1598 三角面，于是工时被算成
842 小时。改按 **`(基名, 三角面数)`** 分组后，第一个复制按全价计、后续复制只按**实例放置**计，
同一份工作算出来是 **97.2 小时**。

脚本同时给出**外观等价**工时（产出视觉一致的结果，允许烘焙与简化拓扑）与**结构等价**工时
（复现干净的原始拓扑与真实材质节点），另有区间估计，以及一项**已含在总数内**的隐性成本占比
（不是额外相加项）。费率与难度分级是脚本顶部的常量 `RATES` / `DIFFICULTY_BANDS`，换人换水平直接改。

## 2. `blend_extract_parts.py` —— 提取唯一部件 + 聚类 + 导出

回答 *「这个场景里到底有几种零件？哪些是同一件东西？」*

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "输出目录" --export-glb "资产目录"
```

→ `parts_cluster_report.md` + `parts_manifest.csv`。

| 参数 | 说明 |
| --- | --- |
| `--out DIR` | 报告输出目录 |
| `--export-glb DIR` | 每个代表导出为 `<DIR>/<族>/<部件名>.glb` |
| `--mark-assets` | 把代表标记为 Blender Asset（Asset Browser 可拖拽复用） |
| `--tol FLOAT` | 判定「同形」的容差，默认 `0.02`（2%） |
| `--min-tris INT` / `--skip-variants` | 忽略低于此面数的碎件 / 不在文件名追加 `__n<成员数>` |

**旋转不变签名 —— 这是关键点。** 同一根梁沿 `X` 向与沿 `Y` 向使用，是同一件绕不同轴旋转的结果：
名字不同、mesh 顶点坐标也不同，但**排序后的包围盒三边完全相同**。所以签名取「本地空间包围盒 ×
物体缩放」，把三条边**排序**，再用对数格子量化比较（`int(round(log(v) / log(1 + rel_tol)))`），
一个相对容差即可跨数量级成立。

| 层 | 判据 | 用途 |
| --- | --- | --- |
| L1 精确组 | 顶点数 + 面数 + 排序包围盒 + 面积 + 材质槽 | 真正可替换的同一件 |
| L2 形状组 | 同 L1，去掉材质 | 同形不同材质 |
| L3 参数族 | 顶点数 + 面数 + 排序包围盒前两边（长度可变） | 同一截面、不同长度的杆件 |
| L4 语义族 | 名称前缀 | 人可读的分组 |

L3 是必要的：`Small bell hanger` 存在 0.37 / 0.425 / 0.48 三种长度，只做 L1/L2 会把它们算成三种
不同形状。代表选取规则：名字不带 `.001` 后缀的优先 → 名字最短的优先 → 三角面数最多的优先。

## 3. `bake_materials.py` —— 程序化材质 → PBR 贴图

Blender 的 glTF 导出器是**贴图导出器，不是节点导出器**。本场景每个材质都是程序化节点网络
（噪波、波层、色彩斜坡，每个 7~27 个节点，零贴图）。直接导出会把整套计算过程丢掉，材质塌缩成
`baseColorFactor = [1,1,1,1]` —— 白模，青铜铜绿与木质纹理全无。本脚本在导出**之前**把每个材质
拍平成贴图：Base Color 烘成 sRGB albedo PNG，粗糙度与金属度合成一张 **ORM** PNG
（G = 粗糙度，B = 金属度，符合 glTF 规范），经 Separate Color 节点接线，导出器才会输出真正的
`metallicRoughnessTexture`。

```bash
"Blender路径/blender.exe" -b "scene.blend" -P bake_materials.py -- \
    --save "out/scene_baked.blend" [--tex-dir "out/textures"] [--samples 1]
```

按「形状组代表」烘焙一次、再共享给该组所有实例；分辨率按面数预算分配（极小件 128 px → 600 面以上
512 px）；粗糙度与金属度**都是常量**的材质跳过 ORM 烘焙；**绝不修改原 `.blend`**，结果另存新文件。

## 4. `bake_curves_and_export.py` —— 曲线，然后是整场景 `.glb`

`bake_materials.py` 假设「场景 = 网格物体」。这个场景不是：它有 88 个物体是 `CURVE` 类型，
携带 27,648 个真实三角面 —— 铜环、钟冠与钟口缘线脚、鎏金板边框。这个脚本是**最后一公里**：
把它们并入同一套烘焙管线，然后写出引擎即用的 `.glb`。

```bash
"Blender路径/blender.exe" -b "out/scene_baked.blend" -P bake_curves_and_export.py -- \
    --dst "out/scene.glb" [--tex-dir "out/textures"] [--samples 1]
```

五步，按顺序：

1. **转换前先记账。** 先记下每个曲线物体的三角面数，事后才能**证明**（而不是假设）转换没丢几何。
2. **曲线 → 网格**：一次选中全部 88 个，`bpy.ops.object.convert(target="MESH")`。
3. **用管线自己的容差重新聚类**（`cluster(objs, 0.02, 0)`）。88 个曲线件只并成 **7 组**，
   于是只烘 7 个代表而不是 88 个，**贴图从 176 张降到 14 张**。管线注释记录了已核对这些组
   组内材质一致（`mixed_materials = 0`）—— 正是这项核对让「每组只烘一次」成为安全捷径，
   而不是一场赌注。
4. **只删真正没人用的材质 —— 且必须遍历所有物体类型。** 这是第 3 条坑的修法：清理时遍历
   `bpy.data.objects` 而非只看网格。只看网格的话，那**两个只被曲线引用的材质**会被当成
   「零引用孤儿」删掉，那些零件进引擎后完全没有材质，而且**全程没有任何报错**。
5. **实例折叠，然后导出。** 把「几何指纹 + 材质元组」都相同的物体合并为共用一个网格数据块
   （**756 个物体 → 186 个数据块**），回收孤立数据块，最后以 `export_apply=False` 导出 ——
   为什么这个开关不是可选项，见第 9 条坑。

全程不回写磁盘，输入 `.blend` 不被修改。

## 5. `audit_scene_glb.py` —— 回读 `.glb`，检查接线

烘焙只有在贴图**确实送达**时才算对。glTF 导出丢弃程序化节点网络是**静默的** —— 不报错、
不警告，只是变白模。所以最后一步是对**产物**做断言，而不是相信导出器。

这一个用纯 Python 就够了，**不需要 Blender**：

```bash
python audit_scene_glb.py "scene/bronze_bell_hall_v2.3.0.glb" [--out report.txt]
```

它手工解析 GLB 容器（magic `0x46546C67`、JSON 块 `0x4E4F534A`、BIN 块 `0x004E4942`，
每块 4 字节对齐），报告：

- **对象计数** —— nodes、meshes、materials、images、textures、samplers、cameras；
- **字节都花在哪** —— bufferViews 按「图像 vs 几何」拆开。本场景实测：192 个图像 view 共
  **6.78 MB**，573 个几何 view 共 **1.05 MB**；
- accessors 类型分布、网格图元数、图像 mimeType、重复图像数据；
- **真正的断言** —— 逐材质检查 `baseColorTexture`、`metallicRoughnessTexture`、
  `normalTexture`、`emissiveTexture` 是否接上，并统计仍然**纯白**
  （`baseColorFactor == [1,1,1]` 且无 base 贴图）的材质数。

本场景输出 `baseColorTexture 98/98`、`metallicRoughnessTexture 94/98`、`normalTexture 0/98`、
`纯白 0` —— 也就是说，「法线贴图没有烘焙」这件事是**量出来的**，不是嘴上说的。
样本输出里的 `BAKED_CV_g*` 材质名同时也直接证明了上面第 3 步真的在曲线分组上跑过。

### 完整流水线（按顺序）

```bash
B="Blender路径/blender.exe"
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P blend_repro_audit.py    -- --out out/
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P blend_extract_parts.py  -- --out out/ --export-glb out/glb
$B -b "scene/bronze_bell_hall_v2.3.0.blend" -P bake_materials.py       -- --save out/baked.blend
$B -b "out/baked.blend"                     -P bake_curves_and_export.py -- --dst out/scene.glb
   python audit_scene_glb.py out/scene.glb --out out/audit.txt
```

每一段都能从仓库里提交的 `scene/` 文件重新跑一遍。只有烘焙与导出两步会动 Blender 的场景状态，
且都不修改自己的输入 `.blend`。

## 6. `assembly/` —— 从声明式 spec 参数化重建

上面五个工具负责审计、烘焙与导出，`assembly/` 则是**重建**场景。`extract_assembly_spec.py` 把整座厅堂导出成
一份声明式 JSON spec —— **186 条配方覆盖 756 个物体**，含全部 22 个程序化节点图、灯光组与相机。
`assemble_scene.py` 随后在一个全新文件里用图元 + 着色器图把每个物体重新装配出来，
**全程不打开原始 `.blend`**。`verify_assembly.py` 用两项独立检查判定重建是否忠实。

两项都通过，**求值后几何的摘要值完全一致**（`78b135637a82de87`）—— 756 个物体中最大的包围盒偏差
是 **0.95 µm**。命令见 `assembly/README.md`，完整报告见 `assembly/verification.md`。

**不重建的部分**：Blender 的界面状态（工作区、屏幕布局）与内嵌 Text 数据块。

## 几个容易踩的坑

1. **实例会虚高审计结果** —— 计工时前先按 `(基名, 三角面数)` 分组；本场景差值是 842 小时对
   97.2 小时。
2. **L3 合的是几何同形，不是语义等价。** 一根 0.1 × 0.1 的 12 面棱柱，既可能是**灯笼的挑梁**，
   也可能是**桌腿**。报告里对这类合并会打 `⚠ 跨 N 个语义族` 的警告 —— 人工复核时看到该标记，
   就该按语义族拆回去再采用。
3. **只处理网格不等于处理完了整个场景。** `CURVE`、`SURFACE`、`FONT`、`META` 类型的物体同样可能
   携带真实可见几何 —— 本场景有 **88 个曲线物体、共 27,648 个三角面**，而它们共用的材质看起来和
   「零引用的孤儿材质」一模一样。一旦被当作孤儿删掉，导进引擎的部件就是没有材质的白模，**全程
   没有任何报错**。要么先把非网格类型转成网格，要么在统计「在用材质」时遍历**所有**物体类型。
4. **`bpy.ops.object.bake` 会烘焙物体的全部材质槽**，每个槽的材质都必须有一个「活动且选中的图像
   纹理节点」，否则会在跑的中途崩掉。解法是给该物体用到的**每个**材质都装一个临时图像节点（实现
   在 `bake_socket()` 里）。程序化输入必须改接到 **Emission** 节点再烘 `EMIT` 才能拍平；EMIT 直接
   求值、不采样光照，所以 `--samples 1` 就够。
5. **名字里的 `|` 会咬两次：** Markdown 表格里必须转义，索引键必须用 `safe_name()` —— 因为导出时
   竖线会被替换成 `_`（如 `Great bell | hollow cast shell`）。
6. **`Material.use_nodes` 在 Blender 6.0 已废弃**，改用 `getattr(mat, "node_tree", None)`。
7. **`.blend` 会携带代码。** Text 数据块在视口里看不见，却跟着文件一起走 —— 跑构建/审计脚本
   时留下的、或往 Text Editor 里粘过的代码，会原样交付给收到 `.blend` 的人：内部备注、绝对
   路径都在里面。这份场景当初就内嵌着我们自己的 `blend_repro_audit.py`（1,138 行 / 40,679
   字符）。提交或交付前先跑 `strip_embedded_scripts.py`；它**只删 Text 数据块**，并由
   `compare_blends.py` 证明场景本体没被改动（实测 756 个物体偏差 0 m）。
   **然后逐个副本都要查。** 同一份场景在本项目里存在两处 —— 仓库里 621 KB 的可编辑 `.blend`，
   以及交付 zip 里 6.3 MB 的烘焙版 `.blend` —— 只清一份，另一份照样带着脚本。
   打包前要**对每一个** `.blend` 都列一遍 `bpy.data.texts`，不能只查手头正在改的那个。
8. **别把「派生量」塞进等价性判定。** 包围盒尺寸是 `max - min`，所以一份把长度量化到 1 µm 的
   spec，可能让这个**差值**落到四舍五入边界的另一侧，报出一个并不存在的 1e-6 差异 —— 本场景
   668 个物体里就有 6 个是这样。派生长度要按**声明的容差**比较，并且把**实测偏差**打在 PASS
   旁边。这个容差本身也是诚实的：Blender 的网格顶点是 float32，在本场景约 10 m 的尺度下量化
   步长约 0.6 µm，所以 1 µm 的 spec 并没有丢掉 `.blend` 本来能表示的任何信息。

9. **`export_apply=True` 会静默摧毁实例化。** 它逐物体求值，于是每个物体都拿到自己独立的一份
   求值后网格，上一步刚建立的数据块共享全部作废：756 个物体共享 186 个网格 → 变成 756 个网格，
   `.glb` 随之膨胀，**全程没有任何报错**。这里它不是性能取舍而是**正确性**问题 ——
   共享必须自己提前建好，然后显式告诉导出器 **`export_apply=False`**，别去动它。

## 环境与已知限制

除 `audit_scene_glb.py`（纯 Python，完全不需要 Blender）外，其余各阶段均跑在 Blender 5.2 LTS
（`bpy` API，`-b` 无头模式）；仅用标准库，无第三方依赖。

- **绝对工时的不确定度约 ±35%**，主要来自手工调参的材质。结构诊断（部件数、去重率、隐藏成本
  占比）是可靠的；绝对小时数只应当作量级参考。费率按「熟练美术」标定。
- L3 参数族的合并需要人工按语义族复核后才能采用。
- 烘焙只覆盖 base color 与 metallic/roughness。**法线贴图没有烘焙**，程序化材质里由 bump 节点
  承担的表面起伏不会进入 glTF 导出。
- 部件提取只针对网格物体；含「携带几何的非网格物体」的场景，需要先做第 3 条坑里的转换步骤。
- 导出后的 `.glb` 是 **756 个几何节点共享 186 个网格数据块** + 192 张内嵌贴图；
  `audit_scene_glb.py` 会把这几项数字直接打出来，因此它也是一个导出回归检查。
