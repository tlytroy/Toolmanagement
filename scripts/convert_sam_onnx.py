"""将 Segment Anything ViT-B 官方权重导出为浏览器可用的「合并 ONNX」模型。

对应前端 src/lib/samInference.ts（单 session：image + 网格点 → masks + iou）。
本脚本需在能跑 torch 的机器上执行（WSL 沙箱里 torch 段错误，故留给用户在本地跑）。

用法:
  python convert_sam_onnx.py \
      --checkpoint sam_vit_b_01ec64.pth \
      --model-type vit_b \
      --output ../public/models/sam_vit_b.onnx

依赖:  torch, torchvision, segment_anything
  pip install torch torchvision
  pip install git+https://github.com/facebookresearch/segment-anything.git

导出后把 .onnx 放到前端 public/models/ 下，并在调用 SamInference.create 时传入其 URL。
"""
import argparse
import os

import torch
from segment_anything import sam_model_registry
from segment_anything.utils.onnx import SamOnnxModel


def export_onnx(model_type: str, checkpoint: str, output: str) -> None:
    if not os.path.exists(checkpoint):
        raise FileNotFoundError(f"checkpoint 不存在: {checkpoint}")
    sam = sam_model_registry[model_type](checkpoint=checkpoint)
    onnx_model = SamOnnxModel(sam, return_single_mask=False)

    embed_size = sam.prompt_encoder.image_embedding_size  # (64, 64)
    mask_input_size = [4 * embed_size[0], 4 * embed_size[1]]  # (256, 256)

    dummy_inputs = {
        "point_coords": torch.randn(1, 2, 2, dtype=torch.float),
        "point_labels": torch.randn(1, 2, dtype=torch.float),
        "image": torch.randn(1, 3, 1024, 1024, dtype=torch.float),
        "mask_input": torch.randn(1, 1, *mask_input_size, dtype=torch.float),
        "has_mask_input": torch.tensor([1], dtype=torch.float),
    }
    output_names = ["masks", "iou_predictions", "low_res_masks"]

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "wb") as f:
        torch.onnx.export(
            onnx_model,
            (
                dummy_inputs["point_coords"],
                dummy_inputs["point_labels"],
                dummy_inputs["image"],
                dummy_inputs["mask_input"],
                dummy_inputs["has_mask_input"],
            ),
            f,
            export_params=True,
            verbose=False,
            opset_version=17,
            do_constant_folding=True,
            input_names=["point_coords", "point_labels", "image", "mask_input", "has_mask_input"],
            output_names=output_names,
            # 允许网格点数量动态（前端逐点喂 1 个点，导出 dummy 用 2 个）
            dynamic_axes={
                "point_coords": {1: "num_points"},
                "point_labels": {1: "num_points"},
            },
        )
    print(f"✅ 已导出合并 ONNX: {output}")


def main():
    p = argparse.ArgumentParser(description="导出 SAM ViT-B 为浏览器 ONNX")
    p.add_argument("--checkpoint", default="sam_vit_b_01ec64.pth", help="SAM 官方 .pth 权重路径")
    p.add_argument("--model-type", default="vit_b", choices=["vit_b", "vit_l", "vit_h"])
    p.add_argument("--output", default="../public/models/sam_vit_b.onnx", help="导出 .onnx 路径")
    args = p.parse_args()
    export_onnx(args.model_type, args.checkpoint, args.output)


if __name__ == "__main__":
    main()
