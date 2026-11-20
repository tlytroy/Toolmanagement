# Gridfinity 常量交叉验证笔记（主会话一手取证）

## cq-gridfinity constants.py（commit d317286，2026-11-20 直接读取）
来源：https://raw.githubusercontent.com/michaelgale/cq-gridfinity/d317286ec15dc52587fadbd4f4c1e13f9cd8a8b2/cqgridfinity/constants.py

- `GRU = 42`、`GRHU = 7`、`GRU_CUT = 42.2`
- `GR_BASE_HEIGHT = 4.75`
- 底座剖面 `GR_BASE_PROFILE = ((GR_BASE_TOP_CHAMF*√2, 45), 1.8, (GR_BASE_CHAMF_H*√2, 45))`
  - `GR_BASE_CHAMF_H = 0.98994949/√2 ≈ 0.7`
  - `GR_STR_H = 1.8`
  - `GR_BASE_TOP_CHAMF = 4.75 - 0.7 - 1.8 = 2.25`
  - **即垂直分段 2.25 / 1.8 / 0.7**（顺序：上斜 2.25、直壁 1.8、下斜 0.7）
- 堆叠唇 `GR_LIP_PROFILE = ((1.6*√2,45), 1.2, (0.7*√2,-45), 1.8, (1.3*√2,-45))`
  - `GR_LIP_H` = 1.6 + 1.2 + 0.7 + 1.8 + 1.3 = **6.6mm**（代码按 tuple 首元素/√2 + 非 tuple 原值累加）
- 磁孔 `GR_HOLE_D = 6.5`、`GR_HOLE_H = 2.4`、`GR_HOLE_DIST = 26/2 = 13`
- 外角 `GR_RAD = 4`

## 本项目基准（tracefinity 剖面，SDS §7.2 / geometry/constants.py）
- `GRU=42`、`GRHU=7`（3U=21）、`GRU_CUT=42.2`、`EDGE_MM=5`
- 底座 `0.8 + 1.8 + 2.15 = 4.75`（**注意顺序与 cq 不同**：0.8/1.8/2.15）
- 堆叠唇五段 `LIP_D0..D4 = 1.9/1.8/0.7/1.2/1.9`，垂直高 **8.2mm**，径向宽 `LIP_WIDTH=2.6`
- 磁孔孔心相对格心 **±13mm**（与 cq 的 GR_HOLE_DIST=13 一致）、φ6.5×2.4
- 外角 `GF_CORNER_R = 3.75`

## Cross-check 结论（关键：不能混用两个来源）
| 参数 | 本项目(tracefinity) | cq-gridfinity | 一致? |
|---|---|---|---|
| 格距 GRU | 42 | 42 | ✅ |
| 单元高 GRHU | 7 | 7 | ✅ |
| 底座总高 | 4.75 | 4.75 | ✅ |
| 底座分段 | 0.8/1.8/2.15 | 2.25/1.8/0.7 | ❌ 分段不同（总和同） |
| 唇垂直高 | 8.2 | 6.6 | ❌ 差 1.6mm |
| 唇分段 | 1.9/1.8/0.7/1.2/1.9 | 1.6/1.2/0.7/1.8/1.3 | ❌ |
| 磁孔孔心偏移 | ±13 | 13 (=26/2) | ✅ |
| 磁孔 φ/深 | 6.5/2.4 | 6.5/2.4 | ✅ |
| 外角 R | 3.75 | 4 | ❌ |

**印证了计划修订表 #9 的判断**：不能抄 cq-gridfinity 的剖面写法（其唇高折算与 tracefinity 的 8.2 不符）。cq 只能做“总量级”交叉验证（底座总高、格距、磁孔偏移这些能对齐），**分段几何必须以 tracefinity 为唯一真源**。这正支持“开源项目是算法/校验参考，不是规格来源”。
