# 鲁棒 A4 纸张四角检测（纯 OpenCV，无 PyTorch）

把「A4 白纸 + 工具」照片的纸张四角找出来，供后续透视校正（warp）→ 轮廓检测使用。
本模块是**独立于 SAM / torch 的传统 CV 方案**，是工具轮廓识别管线的第一步。

---

## 为什么单独做这个

原来的 `improved_paper_detector.detect_paper_corners_precise` 在**六角扳手**等图上崩了：
它只跑 Canny/自适应/Otsu 三种边缘预处理，拿到**第一个**凸四边形就返回，没有
「纸是最亮大区域」的先验，也没有比例约束。结果把桌面、周边工具、金属反光边缘
误认成纸角，检测出的四边形宽高比变成 **1.00（正方形）**，透视校正全歪。

本模块吸收了文档扫描类算法的经验，用三招修好：

1. **亮度先验为主**：A4 白纸在深色桌面上是最亮的连通区域 → 用 Otsu / 自适应阈值
   找最大亮轮廓，直接避开所有杂物边缘。
2. **三重打分择优**：`比例(1.414)×0.4 + 直角(90°)×0.3 + 亮度覆盖×0.3`，从多方案
   候选里选最优四边形（旧法是「拿到第一个就返回」，无打分）。
3. **正反都试 + 边缘兜底**：Otsu / 自适应阈值各取正反两个 mask，再加 Canny 边缘兜底，
   让打分器自动选对的方案。

---

## 文件

| 文件 | 作用 |
|------|------|
| `robust_paper_detector.py` | 核心算法 + `warp_paper` 辅助 + 自包含 demo |
| `requirements.txt` | 依赖：numpy + opencv-python |
| `README.md` | 本说明 |

---

## 接口

```python
import cv2
from robust_paper_detector import detect_paper_corners_robust, warp_paper

img = cv2.imread("photo.jpg")

res = detect_paper_corners_robust(img)
# res = (corners, candidates)
#   corners    : np.float32 (4,2)，顺序 [TL, TR, BR, BL] —— 直接喂 warp
#   candidates : list[(corners, score, method)]，已按 score 降序，调试用

if res is None:
    raise RuntimeError("未检测到纸张")

corners, candidates = res
warped = warp_paper(img, corners)        # 透视校正为标准 A4 比例 (1.414)
# warped 即可喂后续轮廓检测（如 optimize_yellow_tool_detection / repro_contour_v9）
```

### 参数可调

- `detect_paper_corners_robust` 内部策略固定，一般无需调参；
  若某类图全失败，可放宽 `_largest_quad` 的 `min_frac/max_frac`（默认 0.08 / 0.95）
  或 `_score_quad` 里的 `aspect_score < 0.15` 否决阈值。
- `warp_paper(img, corners, ratio=1.414)`：`ratio` 改成你实际纸张比例
  （A4 = 1.414，A3 = 1.414，正方形画纸 = 1.0）。

---

## 命令行快速验证

```bash
pip install -r requirements.txt

# 用真实图
python robust_paper_detector.py --image photo.jpg

# 或合成一张示意 A4+工具，验证算法本身能跑通
python robust_paper_detector.py
# 输出四角坐标、宽高比(≈1.414)、采用方案，并保存 demo_detect.png 透视校正结果
```

---

## 验证结果（7 张测试图对比旧法）

| 图 | 旧法宽高比 | 新法宽高比 | 新法分数 | 采用方案 |
|----|-----------|-----------|---------|---------|
| t1 钳子 | 1.41 | **1.41** | 0.85 | bright-otsu |
| t2 蓝钳 | 1.41 | **1.40** | 0.92 | edge-canny |
| t3 蓝卡尺 | 1.30 | **1.30** | 0.87 | bright-otsu |
| t4 黑卡尺 | 1.42 | **1.42** | **0.99** | bright-otsu |
| **t5 内六角** | **1.00 ❌ 崩** | **1.41 ✅ 修好** | 0.91 | **bright-adapt** |
| t6 测温枪 | 1.30 | **1.30** | 0.70 | bright-otsu |
| t7 红钳 | 1.41 | **1.41** | 0.93 | bright-otsu |

六角扳手（t5）从 1.00（正方形，warp 全歪）→ 1.41（标准 A4），其余图保持或更好。

---

## WSL 移植须知

1. **路径**：脚本里没有写死 Windows 路径，纯算法。你 WSL 里 `import` 后传 OpenCV 图即可。
2. **依赖**：`pip install -r requirements.txt`。无 GPU / torch 需求，CPU 单图毫秒级。
3. **返回格式契约**：`corners` 永远是 `[TL, TR, BR, BL]` 顺序的 `(4,2)` 浮点，
   接你现有 warp 逻辑时只需把旧 `detect_paper_corners_precise` 的调用替换为
   `detect_paper_corners_robust`，并用本模块的 `warp_paper`（或你自己的
   `getPerspectiveTransform(corners, dst)`）校正即可。
4. **对接轮廓管线**：warp 后的图直接喂 `optimize_yellow_tool_detection.extract_enhanced_tool_contour`
   或 `repro_contour_v9.extract_tool_contour_v9`，无需任何改动。
