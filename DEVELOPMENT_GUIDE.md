以暗猜接口为耻，以认真查阅为荣
以模糊执行为耻，以寻求确认为荣
以盲想业务为耻，以人类确认为荣
以创造接口为耻，以复用现有为荣
以跳过验证为耻，以主动测试为荣
以破坏架构为耻，以遵循规范为荣
以假装理解为耻，以诚实无知为菜
以盲目修改为耻，以谨慎重构为荣

📌 项目背景（给AI看）
本项目是仿Tooltrace的Web工具：用户上传「工具放在A4纸上的俯拍照片」，浏览器本地完成A4纸检测、透视校正、工具轮廓提取、参数配置，最终导出STL/STEP/DXF文件用于3D打印工具收纳。
技术栈：Vite + React + TypeScript + OpenCV.js + Fabric.js + Three.js + Zustand，所有计算均在浏览器本地完成，无后端依赖。
一、项目结构铁律（严禁违反）

1. 单一调试入口（核心红线）
   所有OpenCV/纸张检测/轮廓提取的调试，仅允许在src/features/calibration/CalibrationPage.tsx中进行，严禁新增任何零散HTML测试文件（包括但不限于public/_.html、test-_.html）。
   已永久删除的冗余文件（AI不得再提及或使用）：
   public/optimized-detector-test.html、public/debug-test.html、public/paper-detector-test.html、public/opencv-debug.html、public/simple-test.html、test-paper-detector.html
2. 文件存放规范（不得随意新增）
   功能

唯一文件路径

OpenCV核心算法
src/lib/opencvUtils.ts

OpenCV加载Hook
src/hooks/useOpenCV.ts

校准/调试页面
src/features/calibration/CalibrationPage.tsx

全局状态管理
src/app/store.ts
确需新增文件需先说明理由，禁止AI擅自创建零散文件。3. 参数管理规范
所有调试参数（Canny阈值、模糊核大小、最小轮廓面积、轮廓偏移量等）必须以React State形式存放在CalibrationPage中，通过函数参数传递给工具函数，严禁写死在工具函数的默认值以外的位置。
二、OpenCV.js开发专项规范

1. 内存管理（必查项）
   所有cv.Mat、cv.MatVector、cv.Kernel等OpenCV对象，使用完毕后必须立即调用.delete()，严禁内存泄漏。不得编造dispose()等不存在的销毁方法。
2. API合规性
   仅使用OpenCV.js的Web端API，严禁混用其他环境的API：
   ✅ 正确：cv.imread(imgElement)、cv.imshow(canvas, mat)、cv.findContours(cnts, hier, ...)
   ❌ 错误：cv2.imread()（Python API）、cv.imwrite()（Node API）、cv.drawContours(img, cnts)（缺参数版本）
3. 透视校正必做逻辑
   使用cv.approxPolyDP获取四边形后，必须对4个点按「左上→右上→右下→左下」排序，严禁直接使用approxPolyDP的无序输出做透视变换。
4. 单位明确
   透视校正后必须明确标注像素与实际毫米的换算关系（例如SCALE=10代表1px=0.1mm），所有轮廓坐标运算必须标注单位，严禁无单位的数值计算。
5. 验证流程
   复杂算法（如纸张检测、轮廓提取）必须先通过Python OpenCV验证正确性，再迁移到OpenCV.js，严禁直接让AI编写未经验证的复杂算法。
   三、AI协作八荣八耻（AI专属约束）
   以集中逻辑为荣，以拆分散文件为耻：核心功能代码必须集中在≤3个文件中，拒绝过度抽象、拆分无意义的小文件。
   以非阻塞执行为荣，以长命令卡死为耻：严禁执行npm run dev等长期阻塞终端的命令；启动服务前必须先检测端口占用，若端口已占用直接提示用户访问现有地址，不得反复重试。
   以显式释放内存为荣，以OpenCV内存泄漏为耻：所有OpenCV对象必须显式调用.delete()，不得遗漏。
   以适配目标环境为荣，以混用跨端API为耻：严格区分Web/Node/Python环境API，本项目为纯Web应用，所有代码必须运行在浏览器中。
   以先读现有配置为荣，以覆盖原有配置为耻：修改vite.config.ts/tsconfig.json前必须先读取现有文件内容，不得直接覆盖原有配置，不得私自添加未声明的插件或loader。
   以验证依赖真实性为荣，以虚构不存在包为耻：引用npm包前必须先验证包是否存在，严禁虚构@types/fabric、opencv-contrib-js等不存在/已废弃的依赖。
   以完整报错分析为荣，以甩锅用户环境为耻：遇到报错必须先索要完整日志/截图，先分析代码逻辑问题，不得张口就说“你环境有问题”“换个Node版本试试”。
   以输出可运行代码为荣，以留TODO半成品为耻：输出的代码必须是复制粘贴后可直接运行的，不得遗留未定义的变量、未实现的TODO、缺少import的模块。
   四、开发流程规范
   小步提交：每调通一个功能点（如纸张检测、透视校正、轮廓提取）立即git commit，禁止累积大量修改后一次性提交。
   先验证后固化：调试阶段的参数调整仅在CalibrationPage的State中进行，待参数稳定后，再将最优值作为工具函数的默认值，禁止AI擅自修改已验证稳定的参数。
   禁止全自动：所有AI生成的代码必须经过人工Review后方可合并，严禁开启Auto-accept后直接合并AI代码。
   五、违规处理
   若AI违反上述任何一条规定，立即点击Cancel终止当前对话，Reload Window后重新开始，无需与AI争辩。

## OpenCV纸张四角检测开发指南

### 1. 统一调试入口

项目已完成测试界面断舍离，仅保留唯一调试入口：

- `src/features/calibration/CalibrationPage.tsx` - 唯一的OpenCV调试、纸张检测、参数调优入口

所有零散测试页已删除，包括：

- `public/optimized-detector-test.html`
- `public/debug-test.html`
- `public/paper-detector-test.html`
- `public/opencv-debug.html`
- `public/simple-test.html`
- `test-paper-detector.html`
- `src/pages/OpenCVTestPage.tsx`
- `src/pages/SimpleTestPage.tsx`

### 2. SimplePaperDetector优化说明

已针对`testpic.jpg`图片专门优化了`simplePaperDetector.ts`：

#### 优化点：

1. **边缘检测优化**：将自适应阈值改为Canny边缘检测，更适合木纹背景
   - 降低Canny阈值到50/150，检测更多边缘
   - 使用7x7高斯模糊减少木纹噪声
   - 5x5膨胀操作增强边缘连接

2. **轮廓检测优化**：
   - 降低最小面积阈值到5%，适应不同大小的纸张
   - 多epsilon尝试(0.01-0.03)，提高四边形检测成功率
   - 添加四角排序功能，确保输出顺序为[左上, 右上, 右下, 左下]

3. **类型系统优化**：
   - 使用Point类型替代any，提高代码可维护性
   - 完善返回类型为`Point[] | null`

#### 核心代码改进：

```typescript
// Canny边缘检测替代自适应阈值
cv.Canny(blurred, edges, 50, 150);

// 多epsilon多边形近似
const epsilons = [0.01, 0.015, 0.02, 0.025, 0.03];
for (const epsilon of epsilons) {
  cv.approxPolyDP(contour, approx, epsilon * perimeter, true);
  if (approx.rows === 4) {
    // 检测到四边形
    break;
  }
}

// 四角排序算法
private sortPoints(points: Point[]): Point[] {
  points.sort((a, b) => a.y - b.y);
  const topPoints = points.slice(0, 2).sort((a, b) => a.x - b.x);
  const bottomPoints = points.slice(2, 4).sort((a, b) => a.x - b.x);
  return [topPoints[0], topPoints[1], bottomPoints[1], bottomPoints[0]];
}
```

### 3. 测试方法

### 4. 常见问题排查

#### 检测不到纸张？

- **原因**：边缘检测阈值过高，背景噪声干扰
- **解决**：调整Canny阈值，如`cv.Canny(blurred, edges, 30, 100)`

#### 四角顺序错误？

- **原因**：轮廓点顺序未标准化
- **解决**：确保使用`sortPoints`方法对四角进行排序

#### 性能问题？

- **原因**：高斯模糊核过大，膨胀操作太频繁
- **解决**：减小高斯模糊核到5x5，或减少膨胀迭代次数

### 5. 后续维护规范

1. **统一测试界面管理**：
   - 所有测试必须在现有界面中进行，禁止创建新的测试文件
   - 若确需创建新测试界面，必须先获得团队负责人批准，并更新本文档
   - 每次修改测试界面后，需在本文档中记录修改内容和原因
   - 当前唯一有效的测试界面是：`src/features/calibration/CalibrationPage.tsx`

2. **参数调整规范**：针对不同场景调整参数时，在代码中添加明确注释，说明调整原因和适用场景

3. **类型安全**：所有新增代码必须使用TypeScript类型系统，避免any类型

4. **资源清理**：确保所有OpenCV Mat对象都正确释放，避免内存泄漏

5. **测试界面使用规范**：
   - 所有OpenCV相关的调试、纸张检测、参数调优都应通过`src/features/calibration/CalibrationPage.tsx`进行
   - 不再维护多个独立的测试界面，避免功能重复和维护困难

### 6. 下一步优化建议

1. 添加参数自动调优功能，根据输入图片自动调整检测参数
2. 实现多纸张检测支持
3. 添加旋转校正功能，处理倾斜纸张
4. 优化性能，减少检测时间到100ms以内

---

_本指南最后更新：2026-07-07_
