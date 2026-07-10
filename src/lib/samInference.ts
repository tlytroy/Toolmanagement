/**
 * SAM（Segment Anything）浏览器内 ONNX 推理脚手架。
 *
 * 这是「模型运行时胶水」层（非轮廓算法），故独立于 opencvUtils.ts 单文件铁律之外，
 * 集中放在本文件。轮廓算法本身（Fast / union / 基元化 / SAM 后处理）仍在 opencvUtils.ts。
 *
 * 数据流：
 *   图像(Mat RGBA) → 预处理(缩放到 1024 + 归一化) → 与网格点(16×16)逐点喂合并 ONNX 模型
 *   → 每张候选 mask(低分辨率 256²) → 上采样 + 裁剪回原图 → 二值化
 *   → 返回 RawSamMask[]（对齐 opencvUtils.prepareSamMask 的输入）→ prepareSamMask → segmentDetail。
 *
 * 依赖：onnxruntime-web（package.json 已声明，需 npm install）；模型文件(.onnx)由
 * scripts/convert_sam_onnx.py 在本地用 torch+segment_anything 导出，放到 public/models/sam_vit_b.onnx。
 *
 * 模型格式：官方 export_onnx_model.py 导出的「合并模型」(单 session)：
 *   输入: image[1,3,1024,1024] | point_coords[1,N,2] | point_labels[1,N] | mask_input[1,1,256,256] | has_mask_input[1]
 *   输出: masks[1,3,256,256] | iou_predictions[1,3] | low_res_masks[1,3,256,256]
 * 解码器输出为 logits，本模块做 sigmoid 后按 0.5 二值化（等价于 SAM mask_threshold=0）。
 * 若你的导出已含 sigmoid，把 SAM_SIGMOID_OUTPUT 置 false。
 */
import type { OpenCV } from "@/types/opencv";
// import type { RawSamMask } from "@/lib/opencvUtils";

const SAM_SIGMOID_OUTPUT = true; // 解码器输出是否为 logits（true=需 sigmoid）
const POINTS_PER_SIDE = 16;
const PRED_IOU_THRESH = 0.8;
const MIN_MASK_REGION_AREA = 300;
const IMG_SIZE = 1024;

const findName = (names: string[], substr: string): string => {
  const n = names.find((x) => x.toLowerCase().includes(substr));
  if (!n)
    throw new Error(
      `SAM ONNX 找不到含 "${substr}" 的 tensor 名，实际: ${names.join(",")}`,
    );
  return n;
};

export interface SamModelPaths {
  /** 合并 ONNX 模型 URL（导出见 scripts/convert_sam_onnx.py） */
  modelUrl: string;
  /** 推理后端：'wasm' | 'webgl' | 'webgpu'，默认 webgl */
  backend?: "wasm" | "webgl" | "webgpu";
}

export class SamInference {
  private session: any;
  private ort: any;

  private constructor(session: any, ort: any) {
    this.session = session;
    this.ort = ort;
  }

  /** 加载合并 ONNX 模型（懒加载 onnxruntime-web，避免无模型时拖慢首屏）。 */
  static async create(paths: SamModelPaths): Promise<SamInference> {
    const ort = await import("onnxruntime-web");
    if (paths.backend) {
      try {
        await (ort.env as any).registerBackend(
          paths.backend,
          undefined as any,
          1,
        );
      } catch {
        /* 后端已注册则忽略 */
      }
      (ort.env as any).wasm.numThreads = 1;
    }
    const session = await ort.InferenceSession.create(paths.modelUrl, {
      executionProviders: [paths.backend ?? "webgl"],
    });
    return new SamInference(session, ort);
  }

  /** 对单张图生成全部候选 mask（RawSamMask[]，已二值化 0/255、已裁剪回原图尺寸）。 */
  async generate(cv: OpenCV, src: any): Promise<any[]> {
    const c: any = cv;
    const rgb = new c.Mat();
    c.cvtColor(src, rgb, c.COLOR_RGBA2RGB);
    const h = rgb.rows;
    const w = rgb.cols;
    const scale = IMG_SIZE / Math.max(h, w);
    const nh = Math.round(h * scale);
    const nw = Math.round(w * scale);
    const resized = new c.Mat();
    c.resize(rgb, resized, new c.Size(nw, nh), 0, 0, c.INTER_LINEAR);
    const padH = IMG_SIZE - nh;
    const padW = IMG_SIZE - nw;
    const top = Math.floor(padH / 2);
    const left = Math.floor(padW / 2);
    const padded = new c.Mat();
    c.copyMakeBorder(
      resized,
      padded,
      top,
      padH - top,
      left,
      padW - left,
      c.BORDER_CONSTANT,
      new c.Scalar(0, 0, 0),
    );

    // data 顺序 R,G,B（上面已转 RGB）。归一化到 CHW。
    const px = padded.data as Uint8ClampedArray;
    const mean = [0.485, 0.456, 0.406];
    const std = [0.229, 0.224, 0.225];
    const chw = new Float32Array(3 * IMG_SIZE * IMG_SIZE);
    for (let i = 0; i < IMG_SIZE * IMG_SIZE; i++) {
      for (let ch = 0; ch < 3; ch++) {
        const v = px[i * 3 + ch] / 255;
        chw[ch * IMG_SIZE * IMG_SIZE + i] = (v - mean[ch]) / std[ch];
      }
    }
    rgb.delete();
    resized.delete();
    padded.delete();

    const imageTensor = new this.ort.Tensor("float32", chw, [
      1,
      3,
      IMG_SIZE,
      IMG_SIZE,
    ]);

    // 解析 tensor 名（容错不同导出命名）
    const names = this.session.inputNames;
    const nImage = findName(names, "image");
    const nCoord = findName(names, "point_coord");
    const nLabel = findName(names, "point_label");
    const nMask = findName(names, "mask_input");
    const nHas = findName(names, "has_mask");
    const nMasks = findName(this.session.outputNames, "mask");
    const nIou = findName(this.session.outputNames, "iou");

    const step = IMG_SIZE / POINTS_PER_SIDE;
    const results: any[] = [];
    const zerosMask = new Float32Array(256 * 256);
    const hasMask = new Float32Array([0]);

    for (let gy = 0; gy < POINTS_PER_SIDE; gy++) {
      for (let gx = 0; gx < POINTS_PER_SIDE; gx++) {
        const px2 = (gx + 0.5) * step;
        const py = (gy + 0.5) * step;
        const feeds: Record<string, any> = {};
        feeds[nImage] = imageTensor;
        feeds[nCoord] = new this.ort.Tensor(
          "float32",
          new Float32Array([px2 / IMG_SIZE, py / IMG_SIZE]),
          [1, 1, 2],
        );
        feeds[nLabel] = new this.ort.Tensor(
          "float32",
          new Float32Array([1]),
          [1, 1],
        );
        feeds[nMask] = new this.ort.Tensor(
          "float32",
          zerosMask,
          [1, 1, 256, 256],
        );
        feeds[nHas] = new this.ort.Tensor("float32", hasMask, [1]);
        let dout: any;
        try {
          dout = await this.session.run(feeds);
        } catch {
          continue;
        }
        const masksT = dout[nMasks].data as Float32Array; // 3*256*256
        const ious = dout[nIou].data as Float32Array; // 3
        let bi = 0;
        for (let i = 1; i < 3; i++) if (ious[i] > ious[bi]) bi = i;
        if (ious[bi] < PRED_IOU_THRESH) continue;

        // 低分辨率 mask → 上采样 4× → 裁剪回 nh×nw → resize 回 w×h → 二值化
        const lr = new Float32Array(256 * 256);
        for (let i = 0; i < 256 * 256; i++) {
          let v = masksT[bi * 256 * 256 + i];
          if (SAM_SIGMOID_OUTPUT) v = 1 / (1 + Math.exp(-v));
          lr[i] = v;
        }
        const lrMat = c.matFromArray(256, 256, c.CV_32FC1, lr);
        const up = new c.Mat();
        c.resize(
          lrMat,
          up,
          new c.Size(IMG_SIZE, IMG_SIZE),
          0,
          0,
          c.INTER_LINEAR,
        );
        const roi = new c.Rect(left, top, nw, nh);
        const cropped = new c.Mat(up, roi);
        const up2 = new c.Mat();
        c.resize(cropped, up2, new c.Size(w, h), 0, 0, c.INTER_LINEAR);
        const bin = new c.Mat();
        c.threshold(up2, bin, 0.5, 255, c.THRESH_BINARY);
        const data = new Uint8Array(w * h);
        const bd = bin.data;
        let area = 0;
        for (let i = 0; i < w * h; i++) {
          const v = bd[i] > 0 ? 255 : 0;
          data[i] = v;
          if (v > 0) area++;
        }
        if (area >= MIN_MASK_REGION_AREA) results.push({ data, w, h });
        lrMat.delete();
        up.delete();
        cropped.delete();
        up2.delete();
        bin.delete();
      }
    }
    return results;
  }
}
