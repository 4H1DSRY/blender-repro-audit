# 模型复现难度审计报告 · v2.3.0

- **文件**：`scene/bronze_bell_hall_v2.3.0.blend`
- **Blender**：5.2.0 LTS
- **审计时间**：2026-09-23 21:51:50

---

## 一、结论摘要

| 项目 | 结果 |
|---|---|
| **难度等级** | **难** —— 结构复杂或含程序化系统，需 2–4 周全职 |
| **外观等价复现**（推荐参考值） | **96.7h** |
| 结构等价复现（1:1 照原结构） | 106.9h（区间 74.3h – 175.5h）|
| 其中隐性成本 | 32.0h（占 30%）—— 看成品无法察觉的部分 |
| 不做实例去重（朴素算法） | 678.7h—— 工时虚高 6.4×，见下方对照 |
| 网格规模 | 668 个网格 → 去重后 86 个唯一部件 |
| 三角面 | 35942 |
| 材质 | 22 个（其中 16 个重度程序化）|
| 几何节点组 | 0 个 |
| 文本脚本块 | 0 个 |
| 动画动作 | 0 个 |

> **两个数字的区别**：
> - **结构等价** 106.9h：连原模型「把每个零件拆成独立物体」的组织方式一起复刻。这种拆法是脚本装配的产物，人工不必如此。
> - **外观等价** 96.7h：产出视觉一致的模型，但按人的合理方式组织（合并微碎件、复用模板，折让系数 0.60）。**这个才是「人工复现」的真实成本。**

> **朴素算法对照**（本报告数字的推导出处）：完全不做实例去重——每个网格物体都按独立部件计建模（87.8h，而非 25.4h）、UV 逐物体足额展开（525.6h，而非 16.2h）——总工时是 678.7h，为 106.9h 的 6.4×。差额全部来自同一批零件的重复计数。

> ⚠ **隐性成本 30%**：即使一比一临摹外观，也无法复现它的**行为**——程序化材质、几何节点、脚本逻辑只能重建，不能临摹。

## 二、结构特征诊断

以下特征反映的是它的**装配方式**：部件由人工逐个建模，装配（实例化布置、分阶段推进）由脚本辅助完成，因此留下了成片的实例复制与阶段化集合。

- **实例化复制 582 个**（去重后仅 86 个唯一部件）——同名同面数的物体被反复复制，手工逐个摆放不会留下这种痕迹
- **碎片化：540 个小件（≤60 三角面）占 81%**——典型的「先建零件、再累加成组」式装配
- **阶段化集合 13 个**（如 `10 | Advanced construction`）——暴露出装配是分多轮增量推进的
- **重复集合 3 个**（`.001` 后缀）——组织层级未经清理
- **16/22 个材质为重度程序化**，且无一张贴图——观感完全由节点参数决定

| 指标 | 数值 |
|---|---|
| 网格物体 | 668 |
| 唯一部件（去重后） | 86 |
| 复制实例 | 582（去重率 13%）|
| 小件（≤60 三角面）| 540（占 81%）|
| 集合总数 / 阶段化 / 重复 | 14 / 13 / 3 |
| 残留默认命名 | 0 |
| 全部物体总数（含曲线/灯光/相机）| 772 |

**阶段化集合**（分多轮装配推进的证据）：

- `01 | Room and circulation`
- `01 | Room and circulation.001`
- `02 | Central dais and suspension`
- `02 | Central dais and suspension.001`
- `03 | Bronze bell ensemble`
- `04 | Furniture and wall fittings`
- `05 | Coffers and lanterns`
- `06 | Light and viewpoints`
- `06 | Light and viewpoints.001`
- `07 | Final coherence adjustments`
- `08 | Final review fixes`
- `09 | Craft refinement`
- `10 | Advanced construction`

**资源完整度**：UV ✅、贴图 ❌、骨骼 ❌、动画 ❌、几何节点 ❌

## 三、结构指标（原始数据）

### 3.1 网格物体（按三角面降序，前 25 个）

| 物体 | 三角面 | 顶点 | 四边形占比 | n-gon | UV | 修改器 |
|---|---:|---:|---:|---:|---:|---|
| `Great bell \| hollow cast shell` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.001` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.002` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.003` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.004` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.005` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.006` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.007` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.008` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Small hanging bell.009` | 1598 | 768 | 99.9% | 1 | 0 | BEVEL |
| `Clapper stem` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Clapper weight` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.001` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.002` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.003` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.004` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.005` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.006` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.007` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.008` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.009` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.010` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| `Column bronze collar.011` | 124 | 64 | 94.1% | 2 | 1 | BEVEL |
| _…其余 643 个略_ | | | | | | |

### 3.2 非网格物体

| 物体 | 类型 | 备注 |
|---|---|---|
| `01 Reference composition` | CAMERA |  |
| `02 Start walking` | CAMERA |  |
| `03 Side inspection` | CAMERA |  |
| `04 Reverse inspection` | CAMERA |  |
| `05 Bell material study` | CAMERA |  |
| `Bell crown eye` | CURVE | 1 条样条 |
| `Bell crown eye.001` | CURVE | 1 条样条 |
| `Bell \| crown rim` | CURVE | 1 条样条 |
| `Bell \| heavy mouth rim` | CURVE | 1 条样条 |
| `Entrance reflected fill` | LIGHT |  |
| `Frame bronze ring` | CURVE | 1 条样条 |
| `Frame bronze ring.001` | CURVE | 1 条样条 |
| `Frame bronze ring.002` | CURVE | 1 条样条 |
| `Frame bronze ring.003` | CURVE | 1 条样条 |
| `Frame bronze ring.004` | CURVE | 1 条样条 |
| `Frame bronze ring.005` | CURVE | 1 条样条 |
| `Frame bronze ring.006` | CURVE | 1 条样条 |
| `Frame bronze ring.007` | CURVE | 1 条样条 |
| `Frame bronze ring.008` | CURVE | 1 条样条 |
| `Frame bronze ring.009` | CURVE | 1 条样条 |
| `Frame bronze ring.010` | CURVE | 1 条样条 |
| `Frame bronze ring.011` | CURVE | 1 条样条 |
| `Lantern soft pool` | LIGHT |  |
| `Lantern soft pool.001` | LIGHT |  |
| `Lantern soft pool.002` | LIGHT |  |
| `Lantern soft pool.003` | LIGHT |  |
| `Lantern soft pool.004` | LIGHT |  |
| `Lantern soft pool.005` | LIGHT |  |
| `Panel gilded border` | CURVE | 1 条样条 |
| `Panel gilded border.001` | CURVE | 1 条样条 |
| _…其余 74 个略_ | | |

### 3.3 材质节点复杂度

| 材质 | 节点数 | 程序化节点 | 贴图节点 | 判定 |
|---|---:|---:|---:|---|
| `Stone \| timeworn limestone` | 27 | 3 | 0 | 🟡 轻度程序化 |
| `Craft timber \| beam \| X` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| beam \| Y` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| beam \| Z` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| column \| X` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| column \| Z` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| frame \| X` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| frame \| Y` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| frame \| Z` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| furniture \| X` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Craft timber \| furniture \| Z` | 25 | 6 | 0 | 🔴 重度程序化 |
| `Hero bronze \| layered oxidation` | 23 | 3 | 0 | 🟡 轻度程序化 |
| `Timber \| softened worn arrises` | 21 | 5 | 0 | 🔴 重度程序化 |
| `Bronze \| exposed cast edges` | 19 | 4 | 0 | 🔴 重度程序化 |
| `Verdigris bronze.001` | 19 | 4 | 0 | 🔴 重度程序化 |
| `Worn golden bronze.001` | 19 | 4 | 0 | 🔴 重度程序化 |
| `Earth plaster.001` | 14 | 4 | 0 | 🔴 重度程序化 |
| `Warm limestone.001` | 14 | 4 | 0 | 🔴 重度程序化 |
| `Hanger bronze \| dark worked alloy` | 8 | 2 | 0 | 🟡 轻度程序化 |
| `Flax mat` | 7 | 2 | 0 | 🟡 轻度程序化 |
| `Dark joints.001` | 2 | 0 | 0 | 🟢 贴图驱动 |
| `Warm luminous parchment` | 2 | 0 | 0 | 🟢 贴图驱动 |

### 3.5 文件内文本脚本块

**文件内没有文本脚本块。**

> 关键事实：如果这个场景确实是脚本装配的，那么装配脚本**不在这个文件里**。它现在只以「结果」的形式存在——几何数据。规则、参数、随机种子已经丢失。

### 3.6 贴图资源

**无任何贴图。**观感完全由程序化材质节点承担——这意味着外观与节点参数强耦合，改一个值观感就变。

## 四、分维度工时估算

| 维度 | 低 | 中 | 高 | 计量依据 |
|---|---:|---:|---:|---|
| 建模（体块 + 塑形） | 17.8h | **25.4h** | 40.6h | 668 个网格 → 去重后 86 个唯一部件（582 个为复制实例）/ 35942 三角面；小件 68 个已计批量折扣 0.58× |
| 曲线 / 灯光相机布置 | 2.8h | **4.7h** | 7.5h | 88 条曲线 → 去重后 7 条（88 条样条）+ 16 个灯光/相机 |
| UV 展开 | 11.3h | **16.2h** | 24.3h | 主体 16 张 UV 图 × 0.8h + 小件 68 张 × 0.05h |
| 材质制作 | 42.0h | **60.0h** | 102.0h | 22 个材质 / 425 个节点；16 个重度程序化，须逐个调参对齐观感 |
| 参考采集 / 比例测量 | 0.4h | **0.6h** | 1.1h | 确定尺度、比例关系、对称轴、结构分解 |
| **合计** | **74.3h** | **106.9h** | **175.5h** | — |

**外观等价复现**：**96.7h**（建模维度按 0.60 折让，其余维度不变）

> 工时基准：熟练 3D 建模师（非新手、非顶尖），**无参考脚本、仅凭观察成品**。区间下沿 = 顺利且经验充足；上沿 = 反复返工。

## 五、复现步骤清单

按执行顺序排列。工时为该步骤的**中位估算**。

| # | 步骤 | 说明 | 低 | 中 | 高 |
|---|---|---|---:|---:|---:|
| 1 | **采集参考与测量比例** | 多角度观察，确定整体尺寸、比例关系、对称轴与结构分解方式。此步决定后续误差上限。 | 0.4h | **0.6h** | 1.1h |
| 2 | **体块搭建（Blockout）** | 用基本体摆出体量与位置：Great bell \| hollow cast shell, Small hanging bell, Clapper stem, Clapper weight, Column bronze collar 等 86 种部件（共 668 个物体，其中 582 个为复制）。只求比例正确。 | 4.5h | **6.3h** | 10.2h |
| 3 | **主体建模与塑形** | 逐部件塑形，目标 35942 三角面。同款部件建一个模板后复制即可，不必逐个重做。 | 10.7h | **15.2h** | 24.4h |
| 4 | **细节刻画** | 倒角、凹槽、纹饰、边缘厚度。细节密度决定成品是否「像」，也最容易被低估。 | 2.7h | **3.8h** | 6.1h |
| 5 | **UV 展开与排布** | 按材质划分 UV 岛，处理接缝与纹素密度一致性。 | 11.3h | **16.2h** | 24.3h |
| 6 | **材质制作** | 重建着色节点链。程序化部分须逐个调参对齐观感——这是旧文件最难复现的环节之一。 | 42.0h | **60.0h** | 102.0h |
| 7 | **曲线 / 灯光相机布置** | 重建曲线样条走线与镜头布光。 | 2.8h | **4.7h** | 7.5h |
| 末 | **组织、命名与优化** | 集合层级、命名规范、变换归零、导出前清理。注意原文件残留了 582 个实例与 540 个小件，人工产出应主动归并。 | 0.3h | **0.5h** | 1.0h |

## 六、隐性成本警告

以下部分**无法通过观察成品还原**——只能看到「是什么样」，看不到「为什么是这样」。

| 风险项 | 中位工时 | 为什么无法凭观察复现 |
|---|---:|---|
| 程序化材质 | 60.0h | 噪声 / 沃罗诺伊链的节点连线与参数，看成品完全不可推断，只能反复试参对齐。 |

**隐性成本合计：32.0h，占总工时的 30%。**

## 七、装配脚本的存档判定

**结论：属于「静态资产」，装配脚本可不必长期存档——但有条件。**

- ✅ **不必存**：若装配脚本只做过一次性摆放，产物已是完整可编辑网格，且确定不会再改结构。
- ⚠ **仍应存**：脚本里编码了你的**决策**——对话中确认过的比例、命名、层级、材质参数。这些信息不在网格数据里，重新生成会漂移。
- 📌 **建议**：把装配脚本与产出一并存档。成本是几 KB 文本，收益是模型永远可重造、可追溯、可对比迭代。

- 🔴 **本文件特别提示**：16 个材质全部是程序化的，且无贴图。若这些材质的节点参数是脚本里定义的，那么**丢掉脚本等于丢掉全部材质规格**——人工只能靠肉眼反推 60.0h 的材质工时才能还原观感。仅此一项，就足以决定「必须存档」。


---

_由 `blend_repro_audit.py` 生成 · Blender 5.2.0 LTS · 2026-09-23 21:51:50_
