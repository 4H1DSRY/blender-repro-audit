# Bronze Bell Ensemble — Manual Scene Reconstruction & Part Decomposition Toolkit

**This repository comes out of a manual scene-reconstruction job of mine.**

Working from a single reference image of a bronze-bell ceremonial hall, I rebuilt the scene by
hand in Blender — timber post-and-beam framing, a great bell suspended from a gallows frame,
two racks of small bells on bronze hangers, offering tables and ritual vessels, kneeling
attendants, a colonnade, a coffered ceiling, stone paving and rear wall niches.

The two analysis scripts here are the tooling I wrote for that job. They turned out to
generalise to any Blender scene, so I split them out into a repo of their own.
Both run in Blender's headless mode — no GUI.

---

## The reconstruction, in short

- **Decompose before modelling.** The hall *reads* as enormously complex, but it is built from
  a small set of repeated elements — beams, post collars, panel rails, bell hangers, bell bodies —
  arranged in arrays. Modelling one of each and placing instances is the whole game.
- **Build in passes:** timber frame → bronze hardware → furnishings and figures → lighting.
- **Procedural materials, zero textures.** All 22 materials are node-built, so the entire palette
  is tuned from a handful of parameters and the file stays self-contained.
- **Result:** 668 mesh objects, 35,942 triangles, 22 materials, no rig, no animation — and after
  geometric clustering, only **91 distinct shapes** across **75 semantic families**
  (86.4% compression). That ratio is what made the job tractable.

---

## 1. `blend_repro_audit.py` — cost audit

Answers: *"how many hours would a skilled 3D artist need to reproduce this scene from scratch?"*

```bash
"path/to/blender.exe" -b "scene.blend" -P blend_repro_audit.py -- --out "out_dir"
```

Emits `audit_report.md` (human) + `audit.json` (machine).

### Core design: why you cannot just count objects

The naive approach charges a full unit of work per object. In an instanced scene that inflates
the number by an order of magnitude — the classic symptom being nine objects named
`Small hanging bell`, `.001`, `.002` … each at 1598 triangles, which prices the job at 842 hours.

This script groups by **`(base name, triangle count)`** instead:

```python
groups.setdefault((_base_name(m["name"]), m["tris"]), []).append(m)
```

The first copy is charged in full; every further copy is charged only as **instance placement**
(`instance_place ≈ 0.025 h`). The example above comes out at **97.2 hours**.

### The hour model

| Quantity | Meaning |
| --- | --- |
| `hours_appearance_equivalent` | **Appearance-equivalent**: produce a visually identical result (baking and topology simplification allowed) |
| `hours_structural_equivalent` | **Structure-equivalent**: reproduce clean original topology and real material nodes |
| `hours_range` | Interval estimate, upper and lower bounds |
| `hidden_hours` | Hidden cost (**already included in the totals** — not an addition) |

Rates and difficulty bands live in `RATES` / `DIFFICULTY_BANDS` at the top of the script:

```python
RATES = {
    "instance_place": 0.025,      # placing one instance
    "small_part_thresh": 60,      # triangle threshold for "small part"
    "small_free_quota": 20,       # small parts charged at full rate
    "small_batch_factor": 0.40,   # batch discount beyond the quota
    "curve_per_spline": 0.15,
    "light_camera": 0.10,
    "material_base": 0.50,        # per material
    "material_node": 0.04,        # per node
    "procedural_heavy": 2.00,     # penalty for heavy procedural setups
    "script_utility": 0.50,       # utility scripts (not generation scripts)
}
DIFFICULTY_BANDS = [4, 12, 45, 150, 500, 1e9]   # → trivial / easy / medium / hard / very hard / infeasible
```

### Traps worth knowing

- **`retopo` only counts when topology is irregular** (`quad_ratio < 0.8`).
  Exported meshes are often already clean quads (`quad_ratio ≈ 0.999`), in which case there is
  no retopology step to charge for.
- **Separate "generation scripts" from "utility scripts."**
  A 209-line text block looks like a rewrite until you read it; `UTIL_MARKERS` catches helper
  scripts and charges them 0.5 h.
- **`Material.use_nodes` is deprecated in Blender 6.0** — use `getattr(mat, "node_tree", None)`.
- **Markdown tables must escape `|`**: object and material names routinely contain pipes
  (`Great bell | hollow cast shell`), and an unescaped pipe shreds the table columns.

---

## 2. `blend_extract_parts.py` — extract, cluster, export

Answers: *"how many distinct parts are actually in this scene, and which objects are the same thing?"*

```bash
"path/to/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "out_dir" --export-glb "assets_dir"
```

| Flag | Meaning |
| --- | --- |
| `--out DIR` | Report output directory (defaults to the `.blend`'s folder) |
| `--export-glb DIR` | Export each representative to `<DIR>/<family>/<part>.glb` |
| `--mark-assets` | Mark representatives as Blender Assets (drag-and-drop from the Asset Browser) |
| `--tol FLOAT` | Geometric tolerance, default `0.02` (2%) — the relative error allowed for "same shape" |
| `--min-tris INT` | Skip fragments below this triangle count, default `0` |
| `--skip-variants` | Don't append `__n<count>` to exported filenames |

Emits `parts_cluster_report.md` + `parts_manifest.csv`.

### Rotation-invariant signature

**This is the crux.** A beam used with `X` orientation and the same beam used with `Y` orientation
are one part rotated about different axes. They carry different names *and* different mesh
coordinates — but their **sorted** bounding-box edge lengths are identical.

So the signature takes the local-space bounding box scaled by the object's scale, and **sorts
the three edges**:

```python
def signature(ob, rel_tol):
    dims = local_bbox_size(ob)
    dims_sorted = sorted(dims)          # ← rotation/mirror invariant
    return {
        "key_exact": (len(me.vertices), len(me.polygons),
            tuple(quantize(d, rel_tol) for d in dims_sorted if d > 0),
            quantize(area, rel_tol), mats),
        "key_shape": (... same, minus mats ...),
        "key_param": (len(me.vertices), len(me.polygons),
            quantize(dims_sorted[0], rel_tol), quantize(dims_sorted[1], rel_tol)),
    }
```

Comparison uses a *logarithmic* bucket rather than exact floats, so a relative tolerance holds
across all magnitudes:

```python
quantize(v, rel_tol) = int(round(log(v) / log(1 + rel_tol)))
```

### Four clustering layers

| Layer | Name | Criterion | Purpose |
| --- | --- | --- | --- |
| L1 | Exact group `exact_group` | verts + polys + sorted bbox + area + **material slots** | Genuinely interchangeable duplicates |
| L2 | Shape group `shape_group` | As L1, **minus materials** | Same shape, different material |
| L3 | Parameter family `param_group` | verts + polys + first two sorted bbox edges (**length may vary**) | Same cross-section, different length |
| L4 | Semantic family `family` | Name prefix | Human-readable grouping |

L3 matters in practice: `Small bell hanger` exists at three lengths (0.37 / 0.425 / 0.48), and
L1/L2 alone would classify those as three different shapes.

### ⚠ The L3 trap: geometric homomorphy ≠ semantic equivalence

L3 only looks at cross-section and topology. A 0.1 × 0.1 twelve-face prism might be a
**lantern bracket** or a **table leg** — geometrically identical, semantically unrelated.

The report therefore flags such merges:

```
⚠ spans N semantic families
```

When you see that mark during review, split the group back apart by semantic family.

### CSV columns

`parts_manifest.csv`:

```
object_name, base_name, family, shape_group, param_group, exact_group,
is_representative, members_in_group, tris, verts, polys,
dim_x, dim_y, dim_z, dim_sorted_1/2/3, area, materials
```

### Representative selection

1. Names without a `.001` suffix win
2. Then the shortest name
3. Then the highest triangle count

---

## `exports/glb/`

91 standalone `.glb` parts decomposed out of the bronze-bell hall scene, grouped by semantic
family. Each file imports cleanly into any DCC tool or engine.

- `__n<N>` in a filename means that representative covers N member instances
- `_INDEX.csv` lists family / member count / triangle count / dimensions / material / bytes

Re-export:

```bash
"path/to/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "out" --export-glb "exports/glb"
```

`_INDEX.csv` is generated by `make_glb_index.py` (reads `parts_manifest.csv`, scans the glb tree):

```bash
python make_glb_index.py "out/parts_manifest.csv" "exports/glb"
```

> Note: a `|` in an object name (`Great bell | hollow cast shell`) is rewritten to `_` on export.
> The index script must build its keys with `safe_name()`, not the raw name, or every part with a
> pipe silently drops out.

---

## `examples/`

Tool output from the bronze-bell hall scene:

- `audit_report.md` — cost audit
- `parts_cluster_report.md` — part clustering

---

## Environment

- Blender 5.2 LTS (`bpy` API; `-b` headless mode)
- Standard library only, no third-party dependencies

## Known limitations

- **Absolute hours carry roughly ±35% uncertainty**, driven mainly by hand-tuned material
  parameters — a single procedural material can swing the total by hours. The structural
  diagnosis (part count, dedup ratio, hidden-cost share) is reliable; treat the absolute hour
  figure as an order of magnitude only.
- Rates are calibrated for a *skilled artist*. Different skill levels need different `RATES`.
- L3 parameter families need human review by semantic family before you act on the merges.

---
---

# 青铜编钟 · 人工场景复现与部件拆解工具

**这个仓库来自我的一项人工场景复现工程。**

我照着一张青铜编钟编钟厅的参考图，用 Blender 手工把整座场景复现了出来 —— 木构梁架、
悬于架上的大镈与两列小钟及青铜挂件、供桌与礼器、跽坐侍者、廊柱、藻井天花、石铺地面
与后壁壁龛。

这里放的两个分析脚本，是我为这项工程量身写的工具。写完后发现它们对任何 Blender 场景
都通用，就单独抽出来成了这个仓库。两者都跑在 Blender 无头模式（headless），不打开 GUI。

---

## 这项复现工作，几句话说完

- **先分解，再建模。** 这座厅堂*看起来*极其复杂，实际是由少量重复构件 —— 梁、柱头箍、
  板条、钟挂件、钟体 —— 阵列排布而成。各建一个、其余放实例，就是全部诀窍。
- **分轮推进：** 木构梁架 → 青铜配件 → 陈设与人像 → 灯光。
- **全程序化材质，零贴图。** 22 个材质全部节点搭建，整套配色由少数几个参数控制，
  文件保持自包含。
- **结果：** 668 个网格物体、35,942 三角面、22 个材质、无骨骼、无动画 —— 而几何聚类之后
  只有 **91 种不同形状**，归入 **75 个语义族**（压缩率 86.4%）。正是这个比例让整件事可行。

---

## 1. `blend_repro_audit.py` —— 工时成本审计

回答：*「一个熟练 3D 美术从零复现这个场景，需要多少小时？」*

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_repro_audit.py -- --out "输出目录"
```

输出 `audit_report.md`（人读）+ `audit.json`（机读）。

### 核心设计：为什么不能直接数物体

天真做法是「一个物体算一份工时」。在实例化场景里这会把数字放大一个数量级 —— 典型症状是
同一个部件存在 `Small hanging bell` / `.001` / `.002` …… 九个物体，每个 1598 三角面，
于是工时被算成 842 小时。

本脚本改按 **`(基名, 三角面数)`** 分组：

```python
groups.setdefault((_base_name(m["name"]), m["tris"]), []).append(m)
```

第一个复制按全价计，后续复制只按 **实例放置**（`instance_place ≈ 0.025 h`）计。
上例实际为 **97.2 小时**。

### 工时模型

| 量 | 说明 |
| --- | --- |
| `hours_appearance_equivalent` | **外观等价**：产出视觉一致的结果（可用烘焙贴图、简化拓扑） |
| `hours_structural_equivalent` | **结构等价**：复现出干净的原始拓扑与真实材质节点 |
| `hours_range` | 区间估计，反映上/下界 |
| `hidden_hours` | 隐性成本（**已含在总数内**，不是额外相加项） |

费率与难度分级在脚本顶部的 `RATES` / `DIFFICULTY_BANDS` 中，可直接调：

```python
RATES = {
    "instance_place": 0.025,      # 放置一个实例
    "small_part_thresh": 60,      # 小件面数阈值
    "small_free_quota": 20,       # 免费小件额度
    "small_batch_factor": 0.40,   # 超额度小件的批量折扣
    "curve_per_spline": 0.15,
    "light_camera": 0.10,
    "material_base": 0.50,        # 每个材质的基础成本
    "material_node": 0.04,        # 每个节点的成本
    "procedural_heavy": 2.00,     # 程序化节点重罚
    "script_utility": 0.50,       # 工具脚本（非生成脚本）
}
DIFFICULTY_BANDS = [4, 12, 45, 150, 500, 1e9]   # → 极易/易/中/难/极难/近乎不可行
```

### 几个容易踩的坑

- **`retopo` 只在拓扑不规则时计数**（`quad_ratio < 0.8`）。
  导出的网格常常已经是很规整的四边面（`quad_ratio ≈ 0.999`），此时没有重拓扑工作量。
- **区分「生成脚本」与「工具脚本」。**
  一段 209 行的 Text 块看行数会以为要重写，实际只是辅助工具，
  用 `UTIL_MARKERS` 命中后只算 0.5 h。
- **`Material.use_nodes` 在 Blender 6.0 已废弃**，改用 `getattr(mat, "node_tree", None)`。
- **Markdown 表格必须转义 `|`**：物体/材质名里常带竖线
  （如 `Great bell | hollow cast shell`），不转义会把表格列冲散。

---

## 2. `blend_extract_parts.py` —— 提取唯一部件 + 聚类 + 导出

回答：*「这个场景里到底有几种零件？哪些是同一件东西？」*

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "输出目录" --export-glb "资产目录"
```

| 参数 | 说明 |
| --- | --- |
| `--out DIR` | 报告输出目录（默认与 `.blend` 同目录） |
| `--export-glb DIR` | 每个代表导出为 `<DIR>/<族>/<部件名>.glb` |
| `--mark-assets` | 把代表标记为 Blender Asset（Asset Browser 可直接拖拽复用） |
| `--tol FLOAT` | 几何容差，默认 `0.02`（2%）—— 判定「同形」的相对误差上限 |
| `--min-tris INT` | 忽略面数低于此值的碎件，默认 `0` |
| `--skip-variants` | 导出时不在文件名追加 `__n<成员数>` |

输出 `parts_cluster_report.md` + `parts_manifest.csv`。

### 旋转不变签名

**这是关键点**：同一根梁沿 `X` 向与沿 `Y` 向使用，是同一件绕不同轴旋转的结果。
两者名字不同、mesh 顶点坐标也不同，但**排序后的包围盒三边完全相同**。

所以签名取「本地空间包围盒 × 物体缩放」，再把三条边**排序**：

```python
def signature(ob, rel_tol):
    dims = local_bbox_size(ob)
    dims_sorted = sorted(dims)          # ← 旋转/镜像不变
    return {
        "key_exact": (len(me.vertices), len(me.polygons),
            tuple(quantize(d, rel_tol) for d in dims_sorted if d > 0),
            quantize(area, rel_tol), mats),
        "key_shape": (... 同上，去掉 mats ...),
        "key_param": (len(me.vertices), len(me.polygons),
            quantize(dims_sorted[0], rel_tol), quantize(dims_sorted[1], rel_tol)),
    }
```

比较用量化（对数格子）而不是精确浮点，才能在相对容差下跨数量级一致：

```python
quantize(v, rel_tol) = int(round(log(v) / log(1 + rel_tol)))
```

### 四层聚类

| 层 | 名称 | 判据 | 用途 |
| --- | --- | --- | --- |
| L1 | 精确组 `exact_group` | 顶点数 + 面数 + 排序包围盒 + 面积 + **材质槽** | 真正可替换的同一件 |
| L2 | 形状组 `shape_group` | 同 L1，**去掉材质** | 同形不同材质 |
| L3 | 参数族 `param_group` | 顶点数 + 面数 + 排序包围盒前两边（**长度可变**） | 同一截面、不同长度的杆件 |
| L4 | 语义族 `family` | 名称前缀 | 人可读的分组 |

L3 是必要的：`Small bell hanger` 存在 0.37 / 0.425 / 0.48 三种长度，
只做 L1/L2 会把它们算成三种不同形状。

### ⚠ L3 的陷阱：几何同形 ≠ 语义等价

L3 只看横截面与拓扑。一根 0.1 × 0.1 的 12 面棱柱，既可能是**灯笼的挑梁**，
也可能是**桌腿** —— 几何上完全同形，语义上毫无关系。

因此报告里会对这类合并打出警告：

```
⚠ 跨 N 个语义族
```

人工复核时看到这个标记，就该按语义族拆回去。

### CSV 列

`parts_manifest.csv`：

```
object_name, base_name, family, shape_group, param_group, exact_group,
is_representative, members_in_group, tris, verts, polys,
dim_x, dim_y, dim_z, dim_sorted_1/2/3, area, materials
```

### 代表选取规则

1. 名字不带 `.001` 后缀的优先
2. 名字最短的优先
3. 三角面数最多的优先

---

## `exports/glb/`

从编钟厅场景中拆出的 **91 个独立 `.glb` 部件**，按语义族分目录，
每个文件都能独立导入任意 DCC 软件或引擎。

- 文件名中的 `__n<N>` 表示该代表覆盖了 N 个成员实例
- `_INDEX.csv` 列出每个文件的族 / 成员数 / 三角面数 / 尺寸 / 材质 / 字节数

重新导出：

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "out" --export-glb "exports/glb"
```

`_INDEX.csv` 由 `make_glb_index.py` 生成（读取 `parts_manifest.csv` + 扫描 glb 目录）：

```bash
python make_glb_index.py "out/parts_manifest.csv" "exports/glb"
```

> 注意：物体名里的 `|`（如 `Great bell | hollow cast shell`）在导出时被替换为 `_`。
> 索引脚本必须用 `safe_name()` 建键，用原始名会漏掉全部含竖线的部件。

---

## `examples/`

编钟厅场景的工具输出：

- `audit_report.md` —— 成本审计报告
- `parts_cluster_report.md` —— 部件聚类报告

---

## 环境

- Blender 5.2 LTS（`bpy` API；`-b` 无头模式）
- 仅用标准库，无第三方依赖

## 已知限制

- **绝对工时的不确定度约 ±35%**，主要来自手工调参的材质 —— 个别程序化材质一个就能差出
  几小时。结构诊断（部件数、去重率、隐藏成本占比）是可靠的；绝对小时数只应当作量级参考。
- 费率按「熟练美术」标定，换人换水平需重调 `RATES`。
- L3 参数族的合并需要人工按语义族复核后才能采用。
