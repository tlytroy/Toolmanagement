# 工具轮廓识别 — Fast + SAM + 绿红并集（最终版）

把手机拍的「A4 纸 + 工具」照片，识别出工具的精确外轮廓。
最终方案：**Fast 检测器（绿）∪ SAM 自动分割（红）** 取并集，再轻微腐蚀去阴影、Chaikin 平滑保角。

---

## 文件

| 文件 | 作用 | 依赖 |
|------|------|------|
| `repro_contour_v9.py` | **Fast 检测器**（第 9 版·最终）+ 纸张检测/透视校正。四策略 mask 并集（Top-Hat+adaptive+Otsu / LAB 暗区 / BlackHat 去阴影 / Canny 桥接）→ 开运算 → 梯度阴影剥离 → 孔洞填充 → 最大连通块 → dilate(7) → 平滑样条。 | numpy, opencv |
| `sam_union_final.py` | **最终版并集管线**（跑它就对了）。调用 v9 拿 Fast 掩膜(绿)，跑 SAM 自动分割拿工具掩膜(红)，SAM 侧做**合并+桥接+外扩**，再 `Final = Red ∪ Green` → erode(3) 吃边缘薄阴影 → Chaikin(2) 平滑。 | + torch, segment-anything |
| `sam_merge.py` | **SAM 合并/外扩的纯净参考版**（union_final 的前身）。只做 SAM 掩膜的过滤→合并→桥接→外扩，**不含并集**。逻辑与 union_final 的 SAM 段逐行一致，但没有 Fast 并集/erode/Chaikin 的干扰，单独理解「合并、外扩」这两个小功能最清楚。 | + torch, segment-anything |

> `sam_union_final.py` / `sam_merge.py` 顶部都 `from repro_contour_v9 import ...`，必须与 v9 放同目录。
>
> **版本关系**：`sam_merge.py`（SAM 合并+外扩） →（加 Fast 并集+腐蚀+平滑）→ `sam_union_final.py`（最终版）。二者的 SAM 段参数完全相同（见下方参数表），union_final 是 merge 的严格超集，实际用 **union_final** 即可，merge 仅作参考。

---

## 管线总览

```
照片
 │  detect_paper_battery()            # 纸张四角检测(Otsu/Canny/自适应 多方案投票)
 ▼
warpPerspective 透视校正 → warped(A4 比例)
 │
 ├─ extract_tool_contour_v9(warped)   # 【绿 / Fast】
 │     四策略并集 → 开运算 → 剥阴影 → 填孔 → 最大块 → dilate7 → 平滑
 │
 └─ SamAutomaticMaskGenerator         # 【红 / SAM】
       逐 mask 过滤: 面积≥100 / 与Fast重叠≥50% / 几何拒阴影
       → 累积并集 → close(9) → dilate(7)
 ▼
Final = Red(SAM) ∪ Green(Fast)        # 并集
 → erode(3)                           # 轻微腐蚀吃边缘薄阴影/噪点
 → merged_contour()                   # 全组件并集+close9桥接，取最大轮廓
 → chaikin_smooth(passes=2)           # 保角平滑(不磨钳口尖角)
 ▼
最终轮廓 (union_smooth)
```

**为什么用并集**：Fast 对亮金属稳但会漏黑色/阴影吞没区；SAM 语义完整但偶尔把阴影/A4 也分进来。并集互补——Fast 兜底轮廓、SAM 补缺口（如尖嘴钳的缺口），再靠 `erode(3)` 啃掉边缘薄阴影，不做复杂几何去阴影（容易误伤钳子这类复杂工具）。

---

## 运行

```bash
pip install -r requirements.txt
# 下载 SAM 权重放到脚本 OUT 目录
wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth

python sam_union_final.py      # 完整并集（需要 torch + SAM 权重）
python repro_contour_v9.py     # 只跑 Fast(绿)，无需 torch，快速验证
```

输出对比图 `union_<name>.png`：绿=Fast 参考 / 橙=SAM 参考(淡) / 紫=并集 mask / 红=并集平滑轮廓。

---

## WSL 移植须知

1. **改路径**：两个文件顶部 `OUT = "C:/Users/tlyth/WorkBuddy/2026-07-07-14-40-46"` 改成你 WSL 里的目录，测试图（`test_cal.jpg` / `test_03.jpg` / `test_05.jpg`）和 `sam_vit_b_01ec64.pth` 放进去。
2. **无 GPU 也能跑**：`DEVICE` 会自动 `cuda→cpu`，但 SAM CPU 推理慢（单图数秒）。
3. **只要轮廓不要可视化**：`extract_tool_contour_v9()` 返回 `(union, debug_info, raw_cnt, smooth_cnt)`；并集结果在 `sam_union_final.py` 主循环的 `union_cnt` / `union_smooth`，可直接抽成函数复用。

---

## 关键参数（`sam_union_final.py` 顶部）

| 参数 | 值 | 含义 |
|------|-----|------|
| `AREA_MIN` | 100 | SAM 候选最小面积 |
| `OVERLAP_MIN` | 0.5 | 候选与 Fast 重叠比门控（防 A4 纸整块并入） |
| `CLOSE_K` | 9 | SAM 合并后闭运算核 |
| `EXPAND_PX` | 7 | SAM dilate 外扩（对齐 Fast dilate_px=7） |
| `ERODE_K` | 3 | 并集后腐蚀核（吃边缘薄阴影） |
| `CHAIKIN_PASSES` | 2 | Chaikin 平滑迭代（2 次已收敛） |

---

## SAM 侧「合并 / 外扩」小功能拆解（WSL 直接对照）

这是你记忆里那几个「合并、外扩等小功能」，都在 `sam_union_final.py` 主循环里，`sam_merge.py` 有一份不带并集干扰的同款：

1. **逐掩膜门控**（`sam_union_final.py` 259-268 行）：`SamAutomaticMaskGenerator` 吐出一堆候选 mask，逐个过三道闸——面积 `≥AREA_MIN(100)`、与 Fast 重叠比 `≥OVERLAP_MIN(0.5)`（防整张 A4 被并进来）、`is_shadow_mask_simple` 几何拒阴影（质心在 Fast 外且离工具 >25px，或面积 <200 → 判为阴影/独立物体拒掉）。
2. **合并 (merge)**：过闸的 mask 逐个 `cv2.bitwise_or(merged, seg)` 累积成一张并集掩膜（267 行）→ `CLOSE_K=9` 椭圆闭运算**桥接** SAM 子块之间 ≤8px 的断裂缝（271 行）。
3. **外扩 (expand)**：对合并+桥接后的掩膜做一次 `EXPAND_PX=7` 椭圆 dilate（272-274 行），让 SAM 轮廓像 Fast 一样向外留 7px 放工具余量，两侧口径一致才好做并集。
4. **并集 + 收边**（union_final 独有，merge 没有）：`union = SAM ∪ Fast`（277 行）→ `ERODE_K=3` 腐蚀吃掉边缘薄阴影（279-280 行）→ `merged_contour` 全组件并集+close9 取最大轮廓 → `chaikin_smooth(2)` 保角平滑。

> 一句话：**合并=多个 SAM 子块 OR 起来+close9 桥缝；外扩=dilate7 对齐 Fast 余量**。这两步在 `sam_merge.py` 里最干净，`sam_union_final.py` 在其后又接了 Fast 并集与收边平滑。
