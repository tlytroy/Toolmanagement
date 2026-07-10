# 抽稀 + 基元化

把稠密的工具外轮廓（几百~上千点）→ **抽稀** → 拟合成 **直线 + 圆弧** 基元，供下游 CAD / STL 拉伸使用。

本包含两代实现：**① 你的原始参考**（DP + 逐段直线/圆弧择优）和 **② 基于它改进的最终版**（曲率分段 + 椭圆拟合方案B）。

---

## 文件

| 文件 | 代 | 算法思路 | 依赖 | 说明 |
|------|----|---------|------|------|
| `contour_simplify.py` | ① 参考·单图 | HSV 取红轮廓 → DP 抽稀(ε=0.004·周长)找拐点 → **相邻拐点段** 逐段比较 `line_fit_error` vs `circle_fit_error`，误差小者胜 → line/arc/polyline | numpy, opencv | 你最早给的原始脚本 |
| `batch_process.py` | ① 参考·批量 | 同上，多图批处理 | numpy, opencv | 你最早给的原始脚本 |
| `abstract_primitive.py` | ② 最终版·全链路 | **方案B**：Chaikin 稠密点 → 一阶差分曲率 sin(θ) 标记弯曲点 → 开运算去噪 → `adaptive_rdp`（直线坍2点/弧保密度）→ 弧段 `fit_arc_b`（fitEllipse 最小二乘，非 minEnclosingCircle）+ 解缠绕角度裁劣弧 | + torch, SAM | 从照片跑通全链路(检测→并集→基元化)，含 IoU 校验 + JSON 导出 |
| `abstract_from_masks.py` | ② 最终版·无torch | 同 `abstract_primitive.py` 的基元化核心，但**从已存掩膜** `_fast_*.png`/`_sambox_*.png` 重建并集，跳过 SAM | numpy, opencv | 无 GPU/torch 也能验证基元化；含 IoU + JSON |
| `repro_contour_v9.py` | 依赖 | Fast 检测器 + 纸张检测（`abstract_primitive.py` import 它） | numpy, opencv | 与「工具轮廓识别包」同一文件 |

---

## 两代算法差异（重要）

**① 参考版（contour_simplify / batch_process）**
- 先 `approxPolyDP` 找拐点，把轮廓切成「拐点→拐点」的段。
- 每段同时做直线拟合和代数圆拟合，`is_arc_better = (err_c<err_l) and (err_c<ARC_TOL) and (err_l>LIN_TOL)`。
- 大半径缓弯(`r>55`)退化为折线 polyline。
- 参数：`EPS=0.004`, `LIN_TOL=ARC_TOL=4.0`, `MAX_ARC_RADIUS=55`。

**② 最终版（abstract_primitive / abstract_from_masks）**
- 不先切拐点，而是**逐点算曲率** `sin(θ)`，`>0.025` 标为弧点，再 3 窗口开运算去噪。
- `adaptive_rdp`：连续直线点坍成 2 端点，连续弧点整段送 `fit_arc_b`。
- 弧拟合用 `cv2.fitEllipse`（最小二乘），**不用 `minEnclosingCircle`**——后者对 <180° 短弧会退化成「弦直径圆」，半径偏小约 30%。
- 角度用 `np.unwrap` 解缠绕，避免 0/360 边界把弧方向判反画成优弧。
- 拒识守卫：圆度(轴长比)>0.25 拒 / 半径 5~150px / span 20~180° / 平均残差超限拒。
- 输出 `primitives_<name>.json`（`{type:line,p0,p1}` 或 `{type:arc,center,radius,angle_start,angle_end}`）+ 重绘 vs Chaikin 的 **IoU 自检**。

> 想要哪种风格自己选：参考版更简单直观（拐点分段）；最终版对真实圆角更准（椭圆拟合+劣弧裁剪），且直接吐 JSON 给下游 CAD。

---

## 运行

```bash
pip install -r requirements.txt

# 参考版(单图/批量，只需 numpy+opencv，改脚本内 IMG_PATH/WORKSPACE)
python contour_simplify.py
python batch_process.py

# 最终版·无torch(推荐先跑这个验证基元化，需要 _fast_*.png / _sambox_*.png)
python abstract_from_masks.py

# 最终版·全链路(照片→基元，需 torch + SAM 权重)
python abstract_primitive.py
```

---

## WSL 移植须知

1. **改路径**：各脚本顶部 `OUT` / `WORKSPACE` 改成你 WSL 目录。
2. **基元化核心可复用**：最终版的 `chaikin_smooth` / `classify_and_fit_fixed` / `fit_arc_b` / `adaptive_rdp` 是纯 numpy+cv2，输入一条稠密闭合轮廓 `(N,2)`，输出基元列表 + JSON，完全独立于检测管线，可直接抽出来接你的后端。
3. **输入契约**：最终版吃的是「并集+erode3+Chaikin(2)」后的稠密点；若你已有轮廓点，跳过前面直接喂 `classify_and_fit_fixed(pts_chaikin)` 即可。
