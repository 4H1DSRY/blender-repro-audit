<a name="top"></a>

<p align="center">
  <b>English</b> &nbsp;·&nbsp; <a href="#zh">中文</a> &nbsp;·&nbsp; <a href="README.md">README</a>
</p>

---

# Pitfalls — nine traps from a hand-built Blender pipeline

Found the hard way while building the audit / bake / export pipeline in this repository. Each entry
gives the symptom, the cause and the fix. The numbers here are the ones the README refers to as
*trap N*.

1. **Instances inflate audits.** Group by `(base name, triangle count)` before charging hours — 842 h
   versus 97.2 h here.
2. **L3 merges geometric twins, not semantic twins.** A 0.1 × 0.1 twelve-face prism might be a lantern
   bracket or a table leg. Merges spanning families are marked `⚠ spans N semantic families` — split
   them back apart before acting on them.
3. **Mesh-only is not the whole scene.** `CURVE`, `SURFACE`, `FONT` and `META` objects can carry real
   geometry, and their shared materials look exactly like orphans. Convert non-mesh types first, or
   build the "in use" set from *all* object types — see §4.
4. **`bpy.ops.object.bake` bakes every material slot**, and each slot needs an active, selected image
   texture node or the run dies mid-way — install one in *every* material on the object
   (`bake_socket()`). Route procedural inputs through an **Emission** node and bake `EMIT`: no light
   sampling, so `--samples 1` suffices.
5. **`|` in names bites twice:** escape it in Markdown tables, and use `safe_name()` for index keys —
   the exporter rewrites pipes to `_`.
6. **`Material.use_nodes` is deprecated in Blender 6.0** — use `getattr(mat, "node_tree", None)`.
7. **A `.blend` can carry code.** Text datablocks are invisible in the viewport but travel with the file:
   internal notes, absolute paths and all (ours shipped with our own 1,138-line audit script). Run
   `strip_embedded_scripts.py` before committing or delivering — it removes Text datablocks only, and
   `compare_blends.py` proves the scene is untouched (0 m deviation, 756 objects). **Then check every
   copy** — the same scene sits in two `.blend` files here (repo + delivery zip), and stripping one
   leaves the other carrying the script. Enumerate `bpy.data.texts` in *each* `.blend` before packaging.
8. **Never fold a derived value into an equivalence check.** A bbox size is `max - min`, so a 1 um spec
   can round the *difference* across a boundary and report a phantom 1e-6 mismatch (6 of 668 objects did
   exactly that). Compare against a stated tolerance and print the measured deviation next to the PASS.
   The tolerance is honest: float32 vertices at a ~10 m extent quantise at ~0.6 um.
9. **`export_apply=True` silently destroys instancing** — 756 objects sharing 186 meshes becomes 756
   meshes, with no error. Build the sharing by hand first, then tell the exporter
   **`export_apply=False`** — see §4.

---

<a name="zh"></a>

<p align="center">
  <a href="#top">English</a> &nbsp;·&nbsp; <b>中文</b> &nbsp;·&nbsp; <a href="README.md">README</a>
</p>

---

# 几个容易踩的坑 —— 搭建 Blender 管线时踩出来的九个

九个在搭建这条管线时踩出来的坑，每条都写了现象、原因与修法。编号即 README 里引用的「第 N 条坑」。

1. **实例会虚高审计结果** —— 计工时前先按 `(基名, 三角面数)` 分组；本场景差值是 842 小时对 97.2 小时。
2. **L3 合的是几何同形，不是语义等价。** 一根 0.1 × 0.1 的 12 面棱柱，既可能是**灯笼的挑梁**，也可能是
   **桌腿**。报告里对这类合并会打 `⚠ 跨 N 个语义族` 的警告 —— 看到该标记就该按语义族拆回去再采用。
3. **只处理网格不等于处理完了整个场景。** `CURVE`、`SURFACE`、`FONT`、`META` 类型的物体同样可能携带
   真实可见几何，而它们共用的材质看起来和「零引用的孤儿材质」一模一样。要么先把非网格类型转成网格，
   要么在统计「在用材质」时遍历**所有**物体类型 —— 见第 4 节。
4. **`bpy.ops.object.bake` 会烘焙物体的全部材质槽**，每个槽的材质都必须有一个「活动且选中的图像纹理
   节点」，否则会在跑的中途崩掉 —— 解法是给该物体用到的**每个**材质都装一个临时图像节点（实现在
   `bake_socket()` 里）。程序化输入必须改接到 **Emission** 节点再烘 `EMIT` 才能拍平；EMIT 直接求值、
   不采样光照，所以 `--samples 1` 就够。
5. **名字里的 `|` 会咬两次：** Markdown 表格里必须转义，索引键必须用 `safe_name()` —— 导出时竖线会被
   替换成 `_`。
6. **`Material.use_nodes` 在 Blender 6.0 已废弃**，改用 `getattr(mat, "node_tree", None)`。
7. **`.blend` 会携带代码。** Text 数据块在视口里看不见，却跟着文件一起走：内部备注、绝对路径都在里面
   （这份场景当初就内嵌着我们自己的 1,138 行审计脚本）。提交或交付前先跑 `strip_embedded_scripts.py`
   —— 它**只删 Text 数据块**，并由 `compare_blends.py` 证明场景本体没被改动（实测 756 个物体偏差 0 m）。
   **然后逐个副本都要查** —— 同一份场景在本项目里存在两个 `.blend`（仓库 + 交付 zip），只清一份，
   另一份照样带着脚本。打包前要**对每一个** `.blend` 都列一遍 `bpy.data.texts`。
8. **别把「派生量」塞进等价性判定。** 包围盒尺寸是 `max - min`，所以一份把长度量化到 1 µm 的 spec，
   可能让这个**差值**落到四舍五入边界的另一侧，报出一个并不存在的 1e-6 差异（本场景 668 个物体里就有
   6 个）。派生长度要按**声明的容差**比较，并把**实测偏差**打在 PASS 旁边。这个容差本身也是诚实的：
   Blender 的网格顶点是 float32，在本场景约 10 m 的尺度下量化步长约 0.6 µm。
9. **`export_apply=True` 会静默摧毁实例化** —— 756 个物体共享 186 个网格，会变成 756 个网格，**全程
   没有任何报错**。共享必须自己提前建好，然后显式告诉导出器 **`export_apply=False`** —— 见第 4 节。

<p align="right">
  <a href="#top">↑ 回到顶部 / Back to top</a> &nbsp;·&nbsp; <a href="README.md">← README</a>
</p>

