# 部件提取与同类聚类报告

- **源文件**：`scene/bronze_bell_hall_v2.3.0.blend`
- **网格物体总数**：668
- **三角面总数**：35942
- **几何容差**：2.0%
- **面数下限**：0

---

## 一、聚类结果

| 层级 | 含义 | 组数 | 相比上一层的压缩 |
|---|---|---:|---|
| 原始物体 | — | 668 | — |
| **L1 精确组** | 顶点/面数/尺寸/材质全同 | 91 | -86.4% |
| **L2 形状组** | 再加「旋转/镜像等价」合并 | 91 | -0.0% |
| **L3 参数族** | 截面向同、仅规格不同（如不同长度的吊杆） | 80 | -12.1% |
| L4 名称族 | 按名字前缀的语义归类 | 75 | — |

> **结论**：668 个物体实际只有 **91 种形状**，归为 **80 个几何族**、**75 个语义族**。
> 需要存储的资产从 668 个降到 **91 个**，压缩率 **86.4%**。

## 二、形状组明细

按成员数降序。**代表** = 建议保留并存储的那一个。

| # | 代表（建议保留） | 成员数 | 三角面 | 排序尺寸 (X/Y/Z) | 材质变体 | 族 |
|---|---|---:|---:|---|---:|---|
| 0 | `Limestone paving` | 180 | 12 | 0.1100 × 0.7310 × 0.7310 | 1 | Limestone paving |
| 1 | `Attendant bench bronze plate` | 54 | 12 | 0.0250 × 0.0650 × 0.2200 | 1 | Attendant bench |
| 2 | `Column bronze collar` | 24 | 124 | 0.1800 × 0.5100 × 0.5100 | 1 | Column bronze |
| 3 | `Lantern corner` | 24 | 12 | 0.0250 × 0.0250 × 0.4400 | 1 | Lantern corner |
| 4 | `Raised bronze panel` | 24 | 12 | 0.0650 × 0.4450 × 0.4500 | 1 | Raised bronze |
| 5 | `Panel bronze rail` | 18 | 12 | 0.0400 × 0.0550 × 1.8700 | 1 | Panel bronze |
| 6 | `Panel timber stile` | 18 | 12 | 0.0450 × 0.1300 × 0.8900 | 1 | Panel timber |
| 7 | `Attendant bench leg` | 16 | 12 | 0.1000 × 0.1000 × 0.4300 | 1 | Attendant bench |
| 8 | `Frame hardwood drawbore peg` | 16 | 76 | 0.0520 × 0.0560 × 0.0560 | 1 | Frame hardwood |
| 9 | `Low offering table leg` | 16 | 12 | 0.1000 × 0.1000 × 0.7300 | 1 | Low offering |
| 10 | `Strap rivet` | 16 | 76 | 0.0450 × 0.0620 × 0.0620 | 1 | Strap rivet |
| 11 | `Lantern cap` | 12 | 12 | 0.0700 × 0.3200 × 0.3600 | 1 | Lantern cap |
| 12 | `Offering vessel` | 12 | 92 | 0.1300 × 0.1400 × 0.1400 | 1 | Offering vessel |
| 13 | `Ring mounting boss` | 12 | 76 | 0.0950 × 0.1080 × 0.1080 | 1 | Ring mounting |
| 14 | `Rack top finial` | 10 | 12 | 0.1300 × 0.1600 × 0.2200 | 1 | Rack top |
| 15 | `Small bell crown` | 10 | 124 | 0.0800 × 0.0800 × 0.1300 | 1 | Small bell |
| 16 | `Attendant bench apron` | 8 | 12 | 0.0900 × 0.2400 × 1.3500 | 1 | Attendant bench |
| 17 | `Column capital` | 8 | 12 | 0.2300 × 0.6400 × 0.7200 | 1 | Column capital |
| 18 | `Frame protective strap` | 8 | 12 | 0.0550 × 0.2300 × 0.5100 | 1 | Frame protective |
| 19 | `Low offering table apron` | 8 | 12 | 0.0900 × 0.2400 × 1.4500 | 1 | Low offering |
| 20 | `Timber column` | 8 | 124 | 0.4600 × 0.4600 × 4.7000 | 1 | Timber column |
| 21 | `Lantern bracket` | 6 | 12 | 0.1000 × 0.1000 × 0.4200 | 1 | Lantern bracket |
| 22 | `Lantern parchment` | 6 | 12 | 0.2400 × 0.2800 × 0.4000 | 1 | Lantern parchment |
| 23 | `Wall timber panel` | 6 | 12 | 0.1000 × 0.9500 × 1.8000 | 1 | Wall timber |
| 24 | `Longitudinal ceiling timber` | 5 | 12 | 0.1600 × 0.2000 × 11.2000 | 1 | Longitudinal ceiling |
| 25 | `Attendant bench top` | 4 | 12 | 0.1300 × 0.3200 × 1.5000 | 1 | Attendant bench |
| 26 | `Ceremonial table leg` | 4 | 12 | 0.1000 × 0.1000 × 0.7400 | 1 | Ceremonial table |
| 27 | `Cross ceiling beam` | 4 | 12 | 0.2800 × 0.3800 × 9.1500 | 1 | Cross ceiling |
| 28 | `Earthen jar` | 4 | 92 | 0.2200 × 0.2200 × 0.3500 | 1 | Earthen jar |
| 29 | `Entrance panel rail` | 4 | 12 | 0.0500 × 0.0550 × 1.5000 | 1 | Entrance panel |
| 30 | `Hanger \| clevis cheek` | 4 | 12 | 0.0430 × 0.1250 × 0.3400 | 1 | Hanger clevis |
| 31 | `Hanger \| pin retaining head` | 4 | 124 | 0.0220 × 0.0900 × 0.0900 | 1 | Hanger pin |
| 32 | `Hanger \| saddle return` | 4 | 12 | 0.0390 × 0.1600 × 0.3800 | 1 | Hanger saddle |
| 33 | `Low offering table top` | 4 | 12 | 0.1300 × 0.6000 × 1.6000 | 1 | Low offering |
| 34 | `Rack bronze cap` | 4 | 12 | 0.1500 × 0.1900 × 0.2500 | 1 | Rack bronze |
| 35 | `Rack foot` | 4 | 12 | 0.2000 × 0.3000 × 0.8000 | 1 | Rack foot |
| 36 | `Rack upright` | 4 | 12 | 0.1200 × 0.1700 × 2.1000 | 1 | Rack upright |
| 37 | `Small bell hanger` | 4 | 12 | 0.0180 × 0.0180 × 0.3700 | 1 | Small bell |
| 38 | `Small bell hanger.001` | 4 | 12 | 0.0180 × 0.0180 × 0.4250 | 1 | Small bell |
| 39 | `Small hanging bell` | 4 | 1598 | 0.2299 × 0.2603 × 0.7019 | 1 | Small hanging |
| 40 | `Small hanging bell.001` | 4 | 1598 | 0.2304 × 0.2614 × 0.6469 | 1 | Small hanging |
| 41 | `Stone chime on table` | 3 | 12 | 0.0900 × 0.2000 × 0.3000 | 1 | Stone chime |
| 42 | `Cast ornamental face backing` | 2 | 12 | 0.2200 × 1.4550 × 2.0200 | 1 | Cast ornamental |
| 43 | `Ceremonial table apron` | 2 | 12 | 0.0900 × 0.2400 × 2.3500 | 1 | Ceremonial table |
| 44 | `Coffer frame` | 2 | 12 | 0.1300 × 0.1300 × 2.6500 | 1 | Coffer frame |
| 45 | `Coffer frame.002` | 2 | 12 | 0.1300 × 0.1300 × 2.7500 | 1 | Coffer frame |
| 46 | `Entrance jamb` | 2 | 12 | 0.1900 × 0.2500 × 3.3000 | 1 | Entrance jamb |
| 47 | `Entrance recessed panel` | 2 | 12 | 0.0800 × 1.4500 × 1.5000 | 1 | Entrance recessed |
| 48 | `Entrance wall` | 2 | 12 | 0.3000 × 3.2000 × 5.2000 | 1 | Entrance wall |
| 49 | `Frame capital` | 2 | 12 | 0.2000 × 0.6200 × 0.6500 | 1 | Frame capital |
| 50 | `Frame foot` | 2 | 12 | 0.2800 × 0.8200 × 1.1500 | 1 | Frame foot |
| 51 | `Great frame upright` | 2 | 12 | 0.3600 × 0.4500 × 3.7000 | 1 | Great frame |
| 52 | `Hanger \| crown stud` | 2 | 124 | 0.0740 × 0.0740 × 0.0900 | 1 | Hanger crown |
| 53 | `Hanger \| locking washer` | 2 | 124 | 0.0250 × 0.1500 × 0.1500 | 1 | Hanger locking |
| 54 | `Hanger \| lower bearing` | 2 | 12 | 0.0470 × 0.2100 × 0.2400 | 1 | Hanger lower |
| 55 | `Hanger \| transverse load pin` | 2 | 124 | 0.0660 × 0.0660 × 0.2350 | 1 | Hanger transverse |
| 56 | `Hanger \| upper bearing saddle` | 2 | 12 | 0.0460 × 0.2200 × 0.6400 | 1 | Hanger upper |
| 57 | `Lintel end bronze shoe` | 2 | 12 | 0.2300 × 0.4800 × 0.5400 | 1 | Lintel end |
| 58 | `Rack hanging rail` | 2 | 12 | 0.0800 × 0.1100 × 1.4700 | 1 | Rack hanging |
| 59 | `Rack lintel` | 2 | 12 | 0.1600 × 0.2300 × 1.6200 | 1 | Rack lintel |
| 60 | `Side plaster wall` | 2 | 12 | 0.3000 × 5.2000 × 11.3000 | 1 | Side plaster |
| 61 | `Small bell hanger.002` | 2 | 12 | 0.0180 × 0.0180 × 0.4800 | 1 | Small bell |
| 62 | `Small hanging bell.002` | 2 | 1598 | 0.2306 × 0.2626 × 0.5916 | 1 | Small hanging |
| 63 | `Splayed upper bracket` | 2 | 12 | 0.2600 × 0.2600 × 0.7369 | 1 | Splayed upper |
| 64 | `Suspension pin` | 2 | 124 | 0.0900 × 0.1300 × 0.1300 | 1 | Suspension pin |
| 65 | `Suspension rod` | 2 | 12 | 0.0525 × 0.0525 × 0.5000 | 1 | Suspension rod |
| 66 | `Vestibule wall` | 2 | 12 | 0.3000 × 2.3000 × 4.0000 | 1 | Vestibule wall |
| 67 | `Wall dado` | 2 | 12 | 0.0900 × 1.0500 × 11.2000 | 1 | Wall dado |
| 68 | `Wall dado cap` | 2 | 12 | 0.0900 × 0.1600 × 11.2000 | 1 | Wall dado |
| 69 | `Back dado` | 1 | 12 | 0.1200 × 1.0500 × 9.0000 | 1 | Back dado |
| 70 | `Ceiling` | 1 | 12 | 0.2400 × 9.6000 × 11.6000 | 1 | Ceiling |
| 71 | `Central luminous coffer` | 1 | 12 | 0.0550 × 2.3500 × 2.5000 | 1 | Central luminous |
| 72 | `Ceremonial mallet` | 1 | 12 | 0.0400 × 0.0400 × 0.9200 | 1 | Ceremonial mallet |
| 73 | `Ceremonial table top` | 1 | 12 | 0.1300 × 0.6300 × 2.5000 | 1 | Ceremonial table |
| 74 | `Clapper stem` | 1 | 124 | 0.1100 × 0.1100 × 0.8000 | 1 | Clapper stem |
| 75 | `Clapper weight` | 1 | 124 | 0.2200 × 0.2800 × 0.2800 | 1 | Clapper weight |
| 76 | `Continuous floor` | 1 | 12 | 0.3000 × 9.5000 × 11.5000 | 1 | Continuous floor |
| 77 | `Dais step` | 1 | 12 | 0.1500 × 2.6750 × 4.8000 | 1 | Dais step |
| 78 | `Dais step.001` | 1 | 12 | 0.1500 × 2.5250 × 4.5000 | 1 | Dais step |
| 79 | `Dais step.002` | 1 | 12 | 0.1500 × 2.3750 × 4.2000 | 1 | Dais step |
| 80 | `Dais woven mat` | 1 | 12 | 0.0180 × 1.8000 × 2.5000 | 1 | Dais woven |
| 81 | `Entrance carved lintel` | 1 | 12 | 0.2500 × 0.3000 × 3.3000 | 1 | Entrance carved |
| 82 | `Entrance lintel wall` | 1 | 12 | 0.3000 × 1.8000 × 3.0000 | 1 | Entrance lintel |
| 83 | `Entrance threshold` | 1 | 12 | 0.1200 × 0.6000 × 2.9000 | 1 | Entrance threshold |
| 84 | `Great bell \| hollow cast shell` | 1 | 1598 | 1.1662 × 1.9316 × 2.3562 | 1 | Great bell |
| 85 | `Great suspension lintel` | 1 | 12 | 0.3800 × 0.5500 × 3.8500 | 1 | Great suspension |
| 86 | `Mallet bronze head` | 1 | 124 | 0.1500 × 0.1500 × 0.1800 | 1 | Mallet bronze |
| 87 | `Rear plaster wall` | 1 | 12 | 0.3000 × 5.2000 × 9.5000 | 1 | Rear plaster |
| 88 | `Vestibule end wall` | 1 | 12 | 0.2500 × 3.6000 × 4.2000 | 1 | Vestibule end |
| 89 | `Vestibule floor` | 1 | 12 | 0.1400 × 2.0000 × 3.0000 | 1 | Vestibule floor |
| 90 | `Vestibule roof` | 1 | 12 | 0.2000 × 2.4000 × 3.6000 | 1 | Vestibule roof |

## 三、重复度最高的组（优先处理）

| 代表 | 成员数 | 成员示例 |
|---|---:|---|
| `Limestone paving` | 180 | `Limestone paving`, `Limestone paving.001`, `Limestone paving.002`, `Limestone paving.003` … +176 |
| `Attendant bench bronze plate` | 54 | `Attendant bench bronze plate`, `Attendant bench bronze plate.001`, `Attendant bench bronze plate.002`, `Attendant bench bronze plate.003` … +50 |
| `Column bronze collar` | 24 | `Column bronze collar`, `Column bronze collar.001`, `Column bronze collar.002`, `Column bronze collar.003` … +20 |
| `Lantern corner` | 24 | `Lantern corner`, `Lantern corner.001`, `Lantern corner.002`, `Lantern corner.003` … +20 |
| `Raised bronze panel` | 24 | `Raised bronze panel`, `Raised bronze panel.001`, `Raised bronze panel.002`, `Raised bronze panel.003` … +20 |
| `Panel bronze rail` | 18 | `Panel bronze rail`, `Panel bronze rail.001`, `Panel bronze rail.002`, `Panel bronze rail.003` … +14 |
| `Panel timber stile` | 18 | `Panel timber stile`, `Panel timber stile.001`, `Panel timber stile.002`, `Panel timber stile.003` … +14 |
| `Attendant bench leg` | 16 | `Attendant bench leg`, `Attendant bench leg.001`, `Attendant bench leg.002`, `Attendant bench leg.003` … +12 |
| `Frame hardwood drawbore peg` | 16 | `Frame hardwood drawbore peg`, `Frame hardwood drawbore peg.001`, `Frame hardwood drawbore peg.002`, `Frame hardwood drawbore peg.003` … +12 |
| `Low offering table leg` | 16 | `Low offering table leg`, `Low offering table leg.001`, `Low offering table leg.002`, `Low offering table leg.003` … +12 |
| `Strap rivet` | 16 | `Strap rivet`, `Strap rivet.001`, `Strap rivet.002`, `Strap rivet.003` … +12 |
| `Lantern cap` | 12 | `Lantern cap`, `Lantern cap.001`, `Lantern cap.002`, `Lantern cap.003` … +8 |
| `Offering vessel` | 12 | `Offering vessel`, `Offering vessel.001`, `Offering vessel.002`, `Offering vessel.003` … +8 |
| `Ring mounting boss` | 12 | `Ring mounting boss`, `Ring mounting boss.001`, `Ring mounting boss.002`, `Ring mounting boss.003` … +8 |
| `Rack top finial` | 10 | `Rack top finial`, `Rack top finial.001`, `Rack top finial.002`, `Rack top finial.003` … +6 |

## 四、参数化族（同一部件、不同规格）

这些组的形状同族，仅尺寸参数不同——**每一档规格都要单独保留**，但应作为一个族统一管理（改基础形状时可一次性更新所有规格）。

> ⚠ **「跨语义族」标记的含义**：这些部件几何同形，但**语义不同**（例如灯笼托架与桌腿恰好都是同截面柱体）。
> 它们适合「用一个基础形状参数化派生」，但**是否合并存储必须人工判断**——若将来各自独立演化，应分开存。

**⚠ 跨 4 个语义族** · 4 档规格 —— Attendant bench、Ceremonial table、Lantern bracket、Low offering

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Lantern bracket` | 12 | 0.1000 × 0.1000 × 0.4200 | 6 |
| `Attendant bench leg` | 12 | 0.1000 × 0.1000 × 0.4300 | 16 |
| `Low offering table leg` | 12 | 0.1000 × 0.1000 × 0.7300 | 16 |
| `Ceremonial table leg` | 12 | 0.1000 × 0.1000 × 0.7400 | 4 |

**⚠ 跨 3 个语义族** · 3 档规格 —— Attendant bench、Ceremonial table、Low offering

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Attendant bench apron` | 12 | 0.0900 × 0.2400 × 1.3500 | 8 |
| `Low offering table apron` | 12 | 0.0900 × 0.2400 × 1.4500 | 8 |
| `Ceremonial table apron` | 12 | 0.0900 × 0.2400 × 2.3500 | 2 |

**Small bell** · 3 档规格

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Small bell hanger` | 12 | 0.0180 × 0.0180 × 0.3700 | 4 |
| `Small bell hanger.001` | 12 | 0.0180 × 0.0180 × 0.4250 | 4 |
| `Small bell hanger.002` | 12 | 0.0180 × 0.0180 × 0.4800 | 2 |

**Small hanging** · 3 档规格

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Small hanging bell.002` | 1598 | 0.2306 × 0.2626 × 0.5916 | 2 |
| `Small hanging bell.001` | 1598 | 0.2304 × 0.2614 × 0.6469 | 4 |
| `Small hanging bell` | 1598 | 0.2299 × 0.2603 × 0.7019 | 4 |

**Coffer frame** · 2 档规格

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Coffer frame` | 12 | 0.1300 × 0.1300 × 2.6500 | 2 |
| `Coffer frame.002` | 12 | 0.1300 × 0.1300 × 2.7500 | 2 |

**⚠ 跨 2 个语义族** · 2 档规格 —— Rear plaster、Side plaster

| 规格代表 | 三角面 | 排序尺寸 (X/Y/Z) | 成员数 |
|---|---:|---|---:|
| `Rear plaster wall` | 12 | 0.3000 × 5.2000 × 9.5000 | 1 |
| `Side plaster wall` | 12 | 0.3000 × 5.2000 × 11.3000 | 2 |

## 五、语义族汇总（L4）

| 族 | 形状组数 | 物体数 |
|---|---:|---:|
| Limestone paving | 1 | 180 |
| Attendant bench | 4 | 82 |
| Low offering | 3 | 28 |
| Column bronze | 1 | 24 |
| Lantern corner | 1 | 24 |
| Raised bronze | 1 | 24 |
| Small bell | 4 | 20 |
| Panel bronze | 1 | 18 |
| Panel timber | 1 | 18 |
| Frame hardwood | 1 | 16 |
| Strap rivet | 1 | 16 |
| Lantern cap | 1 | 12 |
| Offering vessel | 1 | 12 |
| Ring mounting | 1 | 12 |
| Rack top | 1 | 10 |
| Small hanging | 3 | 10 |
| Column capital | 1 | 8 |
| Frame protective | 1 | 8 |
| Timber column | 1 | 8 |
| Ceremonial table | 3 | 7 |
| Lantern bracket | 1 | 6 |
| Lantern parchment | 1 | 6 |
| Wall timber | 1 | 6 |
| Longitudinal ceiling | 1 | 5 |
| Cross ceiling | 1 | 4 |
| Earthen jar | 1 | 4 |
| Entrance panel | 1 | 4 |
| Hanger clevis | 1 | 4 |
| Hanger pin | 1 | 4 |
| Hanger saddle | 1 | 4 |
| Rack bronze | 1 | 4 |
| Rack foot | 1 | 4 |
| Rack upright | 1 | 4 |
| Coffer frame | 2 | 4 |
| Wall dado | 2 | 4 |
| Stone chime | 1 | 3 |
| Dais step | 3 | 3 |
| Cast ornamental | 1 | 2 |
| Entrance jamb | 1 | 2 |
| Entrance recessed | 1 | 2 |
| Entrance wall | 1 | 2 |
| Frame capital | 1 | 2 |
| Frame foot | 1 | 2 |
| Great frame | 1 | 2 |
| Hanger crown | 1 | 2 |
| Hanger locking | 1 | 2 |
| Hanger lower | 1 | 2 |
| Hanger transverse | 1 | 2 |
| Hanger upper | 1 | 2 |
| Lintel end | 1 | 2 |
| Rack hanging | 1 | 2 |
| Rack lintel | 1 | 2 |
| Side plaster | 1 | 2 |
| Splayed upper | 1 | 2 |
| Suspension pin | 1 | 2 |
| Suspension rod | 1 | 2 |
| Vestibule wall | 1 | 2 |
| Back dado | 1 | 1 |
| Ceiling | 1 | 1 |
| Central luminous | 1 | 1 |
| Ceremonial mallet | 1 | 1 |
| Clapper stem | 1 | 1 |
| Clapper weight | 1 | 1 |
| Continuous floor | 1 | 1 |
| Dais woven | 1 | 1 |
| Entrance carved | 1 | 1 |
| Entrance lintel | 1 | 1 |
| Entrance threshold | 1 | 1 |
| Great bell | 1 | 1 |
| Great suspension | 1 | 1 |
| Mallet bronze | 1 | 1 |
| Rear plaster | 1 | 1 |
| Vestibule end | 1 | 1 |
| Vestibule floor | 1 | 1 |
| Vestibule roof | 1 | 1 |

## 六、独一件（没有同类的部件）

共 22 个。这类部件每个都要单独存储，也是成本最高的部分。

| 部件 | 三角面 | 排序尺寸 | 族 |
|---|---:|---|---|
| `Great bell \| hollow cast shell` | 1598 | 1.1662 × 1.9316 × 2.3562 | Great bell |
| `Clapper stem` | 124 | 0.1100 × 0.1100 × 0.8000 | Clapper stem |
| `Clapper weight` | 124 | 0.2200 × 0.2800 × 0.2800 | Clapper weight |
| `Mallet bronze head` | 124 | 0.1500 × 0.1500 × 0.1800 | Mallet bronze |
| `Back dado` | 12 | 0.1200 × 1.0500 × 9.0000 | Back dado |
| `Ceiling` | 12 | 0.2400 × 9.6000 × 11.6000 | Ceiling |
| `Central luminous coffer` | 12 | 0.0550 × 2.3500 × 2.5000 | Central luminous |
| `Ceremonial mallet` | 12 | 0.0400 × 0.0400 × 0.9200 | Ceremonial mallet |
| `Ceremonial table top` | 12 | 0.1300 × 0.6300 × 2.5000 | Ceremonial table |
| `Continuous floor` | 12 | 0.3000 × 9.5000 × 11.5000 | Continuous floor |
| `Dais step` | 12 | 0.1500 × 2.6750 × 4.8000 | Dais step |
| `Dais step.001` | 12 | 0.1500 × 2.5250 × 4.5000 | Dais step |
| `Dais step.002` | 12 | 0.1500 × 2.3750 × 4.2000 | Dais step |
| `Dais woven mat` | 12 | 0.0180 × 1.8000 × 2.5000 | Dais woven |
| `Entrance carved lintel` | 12 | 0.2500 × 0.3000 × 3.3000 | Entrance carved |
| `Entrance lintel wall` | 12 | 0.3000 × 1.8000 × 3.0000 | Entrance lintel |
| `Entrance threshold` | 12 | 0.1200 × 0.6000 × 2.9000 | Entrance threshold |
| `Great suspension lintel` | 12 | 0.3800 × 0.5500 × 3.8500 | Great suspension |
| `Rear plaster wall` | 12 | 0.3000 × 5.2000 × 9.5000 | Rear plaster |
| `Vestibule end wall` | 12 | 0.2500 × 3.6000 × 4.2000 | Vestibule end |
| `Vestibule floor` | 12 | 0.1400 × 2.0000 × 3.0000 | Vestibule floor |
| `Vestibule roof` | 12 | 0.2000 × 2.4000 × 3.6000 | Vestibule roof |

## 七、下一步

1. **审阅** `parts_manifest.csv`：确认聚类是否正确，尤其是那些「形状相同但语义不同」的误合并
2. **保留代表**：把每组的代表物体归入一个新集合（如 `ASSET_LIBRARY`），其余可删或移到 `_SUPERSEDED` 集合备用
3. **存入资产库**：把代表导出为 .glb，或标记为 Blender Asset 后在 Asset Browser 中跨项目拖拽复用
4. **命名规范**：导出前把代表改名为 `<族>_<序号>`，去掉 `.001` 之类的复制后缀

---

_由 `blend_extract_parts.py` 生成_
