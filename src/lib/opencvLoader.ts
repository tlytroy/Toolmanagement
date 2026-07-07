/**
 * 从 window.cv 等待并解析出真正的 OpenCV 实例。
 *
 * opencv.js（UMD，由 index.html 的 <script> 标签加载）在浏览器分支执行
 *   window.cv = cv(Module)
 * 而 cv 是 async 函数，因此 window.cv 实际是一个（可能嵌套多层的）Promise，
 * resolve 后得到真正的 cv 对象。
 *
 * ⚠️ 严禁用 import() / import 加载 @techstark/opencv-js：
 *    Vite dev 会因 13MB 的 CJS 文件卡死。一律走 window.cv。
 */
export async function loadCv(): Promise<any> {
  // 1) 轮询 window.cv（脚本可能尚未下载/执行完）
  let cvReady: any = (window as any).cv;
  let pollTries = 0;
  while (!cvReady && pollTries < 100) {
    await new Promise((r) => setTimeout(r, 100));
    cvReady = (window as any).cv;
    pollTries++;
  }
  if (!cvReady) {
    throw new Error('window.cv 不存在 — opencv.js 的 <script> 未成功加载');
  }

  // 2) 展平嵌套 Promise（UMD async 包装会套多层）
  let guard = 0;
  while (cvReady instanceof Promise && guard < 10) {
    cvReady = await cvReady;
    guard++;
  }

  // 3) 校验关键方法
  if (!cvReady || typeof cvReady.imread !== 'function') {
    throw new Error('OpenCV 已加载，但 cv.imread 不可用');
  }

  return cvReady;
}
