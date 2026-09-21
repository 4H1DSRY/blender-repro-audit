# blender-repro-audit

评估 **AI 生成的 Blender 场景模型**对人工复现的难度，并把场景拆解成可复用的独立部件。

面向一个具体问题：拿到一个「看起来很复杂」的 AI 生成 `.blend`，它到底是真复杂，还是
**少量部件被复制了几百次**？值不值得照着从零做一个？如果只挑有用的零件留下来，能留下哪些？

两个脚本都跑在 Blender 无头模式（headless），不打开 GUI。

---

## 1. `blend_repro_audit.py` —— 工时难度审计

回答：「一个熟练的 3D 美术照着这个成品复现一遍，要多少小时？」

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_repro_audit.py -- --out "输出目录"
```

输出 `audit_report.md`（人读）+ `audit.json`（机读）。

### 核心设计：为什么不能直接数物体

天真的做法是「一个物体算一份工时」。AI 生成场景会把这个数字放大十倍以上——典型症状是
同一个部件存在 `Small hanging bell` / `Small hanging bell.001` / `.002` …… 九个物体，
每个 1598 三角面，于是工时被算成 842 小时。

本脚本按 **`(基名, 三角面数)`** 分组去重：

```python
groups.setdefault((_base_name(m["name"]), m["tris"]), []).append(m)
```

第一个复制按全价计，后续复制只按 **实例放置**（`instance_place ≈ 0.025 h`）计。
上例实际为 **97.2 小时**。

### 工时模型

| 量 | 说明 |
| --- | --- |
| `hours_appearance_equivalent` | **外观等价**：复现出「看起来一样」的结果（可用烘焙贴图、简化拓扑） |
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
  AI 导出的网格常常已经是很规整的四边面（quad_ratio ≈ 0.999），没有重拓扑工作量。
- **区分「生成脚本」与「工具脚本」**。
  场景里有一段 209 行的 Text 块，看行数会以为要重写，实际它只是辅助工具，
  用 `UTIL_MARKERS` 命中后只算 0.5 h。
- **`Material.use_nodes` 在 Blender 6.0 已废弃**，改为
  `getattr(mat, "node_tree", None)`。
- **Markdown 表格必须转义 `|`**：物体/材质名里常带竖线
  （如 `Great bell | hollow cast shell`），不转义会把表格列冲散。

---

## 2. `blend_extract_parts.py` —— 提取唯一部件 + 聚类 + 导出

回答：「这个场景里到底有几种零件？哪些是同一件东西？」

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "输出目录" --export-glb "资产目录"
```

| 参数 | 说明 |
| --- | --- |
| `--out DIR` | 报告输出目录（默认与 `.blend` 同目录） |
| `--export-glb DIR` | 每个代表导出为 `<DIR>/<族>/<部件名>.glb` |
| `--mark-assets` | 把代表标记为 Blender Asset（Asset Browser 可直接拖拽复用） |
| `--tol FLOAT` | 几何容差，默认 `0.02`（2%）——判定「同形」的相对误差上限 |
| `--min-tris INT` | 忽略面数低于此值的碎件，默认 `0` |
| `--skip-variants` | 导出时不在文件名追加 `__n<成员数>` |

输出 `parts_cluster_report.md` + `parts_manifest.csv`。

### 旋转不变签名

**这是关键点**：`beam | X` 和 `beam | Y` 是同一根梁绕不同轴旋转出来的，
名字不同、mesh 顶点坐标也不同，但**排序后的包围盒三边完全相同**。

所以签名用「本地空间包围盒 × 物体缩放」，再把三条边**排序**：

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

用量化（对数刻度）而不是精确浮点比较，才能在 2% 相对容差下跨数量级一致：

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

L3 只看横截面与拓扑。一根 0.1×0.1 的 12 面棱柱，既可能是**灯笼的挑梁**，
也可能是**桌腿**——几何上完全同形，语义上毫无关系。

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

用 `--export-glb` 从示例场景（青铜编钟 `v2.3.0.blend`，668 个网格物体）导出的
**86 个唯一部件**，按语义族分目录。每个 `.glb` 可独立导入任意 DCC / 引擎。

- 文件名中的 `__n<N>` 表示该代表覆盖了 N 个成员实例
- `_INDEX.csv` 列出每个文件的族 / 成员数 / 三角面数 / 尺寸

重新导出：

```bash
"Blender路径/blender.exe" -b "scene.blend" -P blend_extract_parts.py -- \
    --out "out" --export-glb "exports/glb"
```

`_INDEX.csv` 由 `make_glb_index.py` 生成（读取 `parts_manifest.csv` + 扫描 glb 目录）：

```bash
python make_glb_index.py "out/parts_manifest.csv" "exports/glb"
```

> 注意：物体名里的 `|`（如 `Great bell | hollow cast shell`）在导出时被替换为 `_`，
> 索引脚本用 `safe_name()` 建键才能匹配上，不要用原始名。

---

## `examples/`

示例输出，来自青铜编钟 `v2.3.0.blend`（668 网格物体 / ≥1 万个实例）：

- `audit_report.md` —— 难度审计报告
- `parts_cluster_report.md` —— 部件聚类报告

---

## 环境

- Blender 5.2 LTS（`bpy` API；`-b` 无头模式）
- 仅用标准库，无第三方依赖

## 已知限制

- **绝对工时的不确定度约 ±35%**，主要来自材质节点的手工参数（个别程序化材质
  一个就能差出几小时）。结构诊断（部件数、去重率、隐藏成本占比）是可靠的，
  绝对小时数只应当作量级参考。
- 工时模型按「熟练美术」标定；换人换水平需重调 `RATES`。
- L3 参数族的合并需要人工按语义族复核。
