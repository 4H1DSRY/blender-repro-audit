# `assembly/` — rebuild a Blender scene from a declarative spec

Turns the whole hall into a text file, and rebuilds it from that text file alone.

```
extract_assembly_spec.py   scene.blend  ->  assembly_spec.json     (186 recipes / 756 objects)
assemble_scene.py          assembly_spec.json  ->  a full .blend   (no source .blend needed)
verify_assembly.py         proves the two are the same scene, two independent ways
../scene_fingerprint.py    the order-independent fingerprint both use
```

The point is not that a script can place boxes. The point is that **every decision in this scene is
data**: part dimensions, placement, shader graphs, light energies, lens choices. Nothing lives only in
hand-placed state, so the whole scene can be diffed, reviewed, version-controlled as text, and
rebuilt deterministically on another machine.

## Commands

```bash
# 1. dump the scene to a spec  (needs the source .blend)
blender.exe -b "scene/bronze_bell_hall_v2.3.0.blend" -P assembly/extract_assembly_spec.py -- \
    --out assembly/assembly_spec.json

# 2. rebuild from the spec alone  (no input .blend)
blender.exe -b -P assembly/assemble_scene.py -- \
    --spec assembly/assembly_spec.json --out rebuilt.blend

# 3. prove the rebuild is the same scene
blender.exe -b "scene/bronze_bell_hall_v2.3.0.blend" -P assembly/verify_assembly.py -- \
    --spec assembly/assembly_spec.json --report assembly/verification.md
```

`extract_assembly_spec.py` also accepts `--indent N` if you want readable JSON rather than the
compact default, and `assemble_scene.py` accepts `--material-preview` to set every 3D viewport to
Material Preview in the saved file (otherwise a rebuilt file opens in Solid and shows flat viewport
colours — see trap 7 in `../PITFALLS.md`).

## What the spec holds

| Section | Content |
| --- | --- |
| `part_library` | **186 recipes covering 756 objects.** 71 boxes (dimensions), 16 cylinders (sides / radius / depth), 11 raw vertex+face payloads for the cast bell shells, 88 bevelled POLY curves for the bell rims. Keyed by a content hash, so identical geometry is stored once. |
| `objects` | 756 entries: exact object name, datablock name, collection, transform, material slots, modifier config. |
| `materials` | All 22 node graphs — node types, simple properties, unlinked socket defaults, ColorRamp stops, and every link. |
| `world`, `lights`, `cameras` | World node tree; 11 area lights (shape, energy, size, spread, colour); 5 cameras (lens, sensor, clip, DoF). |
| `scene` | Engine, resolution, unit system, colour management, frame range, active camera, collection list. |

Note `objects` carries a full entry **per object**, not per part: the source has 668 mesh objects and
668 mesh datablocks — not one linked duplicate anywhere — so the assembler gives each object a private
copy too. Reproducing that is what keeps the rebuild honest rather than merely similar.

## How the verification works

Two checks, deliberately independent, both inside one Blender session.

**Check A — scene fingerprint.** Fingerprint the source scene, wipe it, rebuild from the spec,
fingerprint again, then compare. The fingerprint is built from *sorted multisets*, so it does not care
about object creation order or which object happened to get the `.001` suffix. It covers object counts
by type, collection membership, every object's geometry signature / transform / material slots /
modifier config, every light and camera parameter, every material node graph — and, decisively, the
totals of the **evaluated** geometry, i.e. with modifiers applied. That last one is what catches a
Bevel rebuilt at the wrong width or a curve rebuilt at the wrong `bevel_depth`; vertex counts alone
would not.

**Check B — spec round-trip.** Extract a *second* spec from the rebuilt scene and diff it against the
first, section by section. If they are byte-equal, the spec is a lossless description of the scene and
the assembler reproduces everything the extractor can see.

Neither alone is sufficient. Check B is circular on its own — it only proves `extract` and `assemble`
are inverses, not that either matches the real geometry. Check A measures the real geometry but only
samples what the fingerprint happens to look at. Together they cover each other.

### Result

```
check A  scene fingerprint    PASS  digest 78b135637a82de87 == 78b135637a82de87
check B  spec round-trip      PASS  all 8 spec sections byte-identical
         committed spec        PASS  matches a fresh extraction from the source
         evaluated triangles    211,526 -> 211,526
         objects compared       756, worst deviation 0.95 um, none above 1 um
         assembler warnings     0 node failures, 0 unknown parts, 0 non-bevel modifiers
```

Full output: `verification.md`. Scene-level provenance for the two `.blend` copies that were re-saved
to strip an embedded script — the committed one and the one inside the delivery package:
`hygiene-verify.md`.

## Honest caveats

- **The spec quantises lengths to 1 um.** That is not a loss: Blender stores mesh vertices as float32,
  whose quantum at this scene's ~10 m extent is about 0.6 um, so 1 um discards nothing the `.blend`
  could have represented. The measured worst-case rebuild deviation is 0.95 um on a bounding box and
  0.24 um on a placement, i.e. **0 of 756 objects exceed 1 um** — printed by the verifier rather than
  asserted here.
- **Derived values need a tolerance, not a rounding step.** A bbox size is `max - min`, so quantising
  lengths can push the *difference* onto the far side of a rounding boundary and invent a 1e-6
  mismatch — which is exactly what happened to 6 of 668 objects on the first run. Derived lengths are
  therefore compared at a stated 1e-5 m with the real deviation printed alongside.
- **Not reproduced:** Blender's UI state (workspaces, screen layout) and embedded Text datablocks.
  Everything else in the scene graph is.
- The extractor is written for *this* scene's feature set: procedural node graphs, no node groups, no
  image textures, no OSL, no shape keys, no drivers, no parenting. It reports anything it cannot
  handle in `meta.warnings` instead of dropping it silently — check that list first when pointing it at
  a different scene.

## Reusing this on another scene

The pipeline is scene-agnostic apart from two assumptions worth knowing before you try it elsewhere:

1. **Non-primitive geometry is stored as raw vertex + face data.** Boxes and cylinders are stored as
   recipes; anything else is dumped verbatim. A scene full of sculpted meshes would produce a large
   spec — the recipe layer only pays for itself on primitive-built scenes.
2. **It does not reproduce driven state.** No drivers, no constraints, no animation, no parenting, no
   geometry nodes. It flattens what is there rather than reproducing the machinery that produced it.

Two traps found while building it, both worth carrying over:

- **Never sweep every RNA property into an equivalence check.** Blender exposes derived editor state
  (`location_absolute` on a node, for instance) whose value is stale in a freshly opened file. Sweeping
  it in makes the spec non-reproducible for no benefit. The extractor skips read-only properties.
- **Never compare transforms by decomposing the matrix.** `matrix_world.to_euler()` is ambiguous at the
  ±180° branch cut and can return the opposite sign for an identical orientation, which reads as a
  phantom diff. With no parents and no constraints, the stored channels are authoritative.

---

# `assembly/` —— 从声明式 spec 重建 Blender 场景

把整座厅堂变成一份文本文件，并且只用这份文本文件就能重建出来。

```
extract_assembly_spec.py   scene.blend  ->  assembly_spec.json     （186 条配方 / 756 个物体）
assemble_scene.py          assembly_spec.json  ->  一个完整 .blend  （不需要源 .blend）
verify_assembly.py         用两项独立检查证明二者是同一个场景
../scene_fingerprint.py    两者共用的「顺序无关」场景指纹
```

重点不是「脚本能摆方块」，而是**这个场景里的每一个决定都是数据**：部件尺寸、摆放位置、着色器图、
灯光能量、镜头选择。没有任何东西只存在于手工摆放的状态里 —— 所以整个场景可以被 diff、被审阅、
以文本形式纳入版本控制，并且能在另一台机器上确定性地重建。

## 命令

```bash
# 1. 导出 spec（需要源 .blend）
"Blender路径/blender.exe" -b "scene/bronze_bell_hall_v2.3.0.blend" -P assembly/extract_assembly_spec.py -- \
    --out assembly/assembly_spec.json

# 2. 仅凭 spec 重建（不需要输入 .blend）
"Blender路径/blender.exe" -b -P assembly/assemble_scene.py -- \
    --spec assembly/assembly_spec.json --out rebuilt.blend

# 3. 证明重建就是同一个场景
"Blender路径/blender.exe" -b "scene/bronze_bell_hall_v2.3.0.blend" -P assembly/verify_assembly.py -- \
    --spec assembly/assembly_spec.json --report assembly/verification.md
```

`extract_assembly_spec.py` 另接受 `--indent N`（输出可读缩进 JSON，默认紧凑）；
`assemble_scene.py` 另接受 `--material-preview`（把保存文件里所有 3D 视口设为材质预览）——
否则重建出来的文件打开时是 Solid 模式，只显示纯色视口色（见 `../PITFALLS.md` 第 7 条坑）。

## spec 里装了什么

| 分节 | 内容 |
| --- | --- |
| `part_library` | **186 条配方，覆盖 756 个物体。** 71 个长方体（尺寸）、16 个圆柱（边数/半径/高度）、11 份原始顶点+面数据（铸造钟体）、88 条倒角 POLY 曲线（铃口/铃眼）。按内容哈希作键，同形几何只存一份。 |
| `objects` | 756 条：物体精确名称、数据块名、所属集合、变换、材质槽、修改器配置。 |
| `materials` | 全部 22 个节点图 —— 节点类型、简单属性、未连线插槽默认值、色彩斜坡端点、以及全部连线。 |
| `world`、`lights`、`cameras` | world 节点树；11 盏面光（形状、能量、尺寸、扩散角、颜色）；5 个相机（焦距、感光、裁剪、景深）。 |
| `scene` | 引擎、分辨率、单位制、色彩管理、帧范围、活动相机、集合列表。 |

注意 `objects` 是**逐物体**一条，不是逐部件：源文件是 668 个网格物体配 668 个网格数据块 ——
一个关联复制都没有 —— 所以装配器也让每个物体各持一份私有拷贝。正是这一点让重建是**忠实**的，
而不只是「看起来差不多」。

## 验证是怎么做的

两项检查，刻意保持独立，都在同一个 Blender 会话里跑完。

**检查 A —— 场景指纹。** 先对源场景取指纹，清空，从 spec 重建，再取一次指纹，然后比对。
指纹由**排序后的多重集**构成，因此不关心物体创建顺序，也不关心谁恰好拿到了 `.001` 后缀。
它覆盖：按类型的物体计数、集合成员关系、每个物体的几何签名/变换/材质槽/修改器配置、每盏灯与
每个相机的参数、每个材质节点图 —— 以及决定性的那一项：**求值后**（即修改器已应用）几何的总量。
最后这一项正是揪出「Bevel 宽度装错」或「曲线 `bevel_depth` 装错」的地方；光比顶点数是发现不了的。

**检查 B —— spec 回环。** 从重建后的场景再导出**第二份** spec，与第一份逐分节比对。
若完全相等，说明 spec 是场景的无损描述、装配器复现了提取器能看到的一切。

两者单独都不够。检查 B 自身是循环论证 —— 它只证明 `extract` 与 `assemble` 互为逆运算，
并不证明任一方与真实几何相符。检查 A 量的是真实几何，但只抽样指纹恰好覆盖到的部分。
合起来，两者互相补上对方的盲区。

### 结果

```
检查 A  场景指纹        PASS  摘要 78b135637a82de87 == 78b135637a82de87
检查 B  spec 回环       PASS  8 个 spec 分节全部逐字节相同
        提交的 spec     PASS  与此刻从源文件重新导出的一致
        求值后三角面     211,526 -> 211,526
        比对物体数       756 个，最大偏差 0.95 µm，无一超过 1 µm
        装配器警告       0 个节点失败、0 个未知部件、0 个非 Bevel 修改器
```

完整输出见 `verification.md`。两份被重新保存以剥离内嵌脚本的 `.blend`（随仓库提交的那份，以及
交付包内的那份）的场景级溯源见 `hygiene-verify.md`。

## 诚实的前提与限制

- **spec 把长度量化到 1 µm。** 这不是损失：Blender 的网格顶点是 float32，在本场景约 10 m 的尺度
  下量化步长约为 0.6 µm，所以 1 µm 并没有丢掉 `.blend` 本来能表示的任何信息。实测重建最大偏差为
  包围盒 0.95 µm、摆放位置 0.24 µm，即 **756 个物体中 0 个超过 1 µm** —— 这个数字由验证器**打印**
  出来，而不是在这里声称。
- **派生量需要容差，而不是再取一次整。** 包围盒尺寸是 `max - min`，所以量化长度可能把这个**差值**
  推到四舍五入边界的另一侧，凭空造出一个 1e-6 的差异 —— 第一次跑的时候 668 个物体里就有 6 个是
  这样。因此派生长度按声明的 1e-5 m 比较，并把真实偏差一并打印出来。
- **不重建的部分：** Blender 的界面状态（工作区、屏幕布局）与内嵌 Text 数据块。场景图里的其余
  一切都重建。
- 提取器是照**本场景**的特性写的：程序化节点图、无节点组、无贴图、无 OSL、无形态键、无 driver、
  无父级。它遇到处理不了的东西会在 `meta.warnings` 里报告而不是静默丢弃 —— 指向别的场景时，
  先看这个列表。

## 用在别的场景上

这条管线与具体场景无关，但有两个前提值得先知道：

1. **非图元几何按原始顶点+面数据存储。** 长方体与圆柱存成配方；其余原样转储。一个全是雕刻网格的
   场景会产生一份很大的 spec —— 配方层只在「图元搭建型」场景里才划算。
2. **它不重建被驱动的状态。** 没有 driver、约束、动画、父级、几何节点。它把「现有的结果」拍平，
   而不是复现「产生它的机制」。

搭建过程中踩到的两个坑，都值得带走：

- **不要把 RNA 属性全量扫进等价性判定。** Blender 会把**派生**的编辑器状态暴露成属性
  （例如节点上的 `location_absolute`），而它在刚打开的文件里是过期值。扫进来只会让 spec 不可
  复现，没有任何好处。提取器会跳过只读属性。
- **不要靠分解矩阵来比较变换。** `matrix_world.to_euler()` 在 ±180° 分支割线上有歧义，对同一个
  朝向可能返回相反的符号，看起来就像一个不存在的差异。在无父级、无约束的前提下，**存储的通道值**
  才是权威。
