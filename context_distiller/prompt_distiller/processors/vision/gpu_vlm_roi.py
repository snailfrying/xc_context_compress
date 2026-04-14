import time
import logging
from typing import Dict, Any, List
from pathlib import Path
from ..base import BaseProcessor

logger = logging.getLogger(__name__)

# 本地模型路径：优先使用 models/clip，不存在时回退到 HuggingFace Hub
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CLIP_LOCAL = str(_PROJECT_ROOT / "models" / "clip")
_CLIP_MODEL = _CLIP_LOCAL if Path(_CLIP_LOCAL).exists() else "openai/clip-vit-base-patch32"


class GPUVLMROIProcessor(BaseProcessor):
    """GPU VLM ROI 抠图 — 基于 CLIP 计算图像区域与 query 的相关性，裁剪高相关性区域"""

    def __init__(self, grid_size: int = 4, score_threshold: float = 0.15):
        self._clip_processor = None
        self._clip_model = None
        self._grid_size = grid_size
        self._score_threshold = score_threshold

    def _load_model(self):
        if self._clip_model is not None:
            return
        try:
            from transformers import CLIPProcessor, CLIPModel
            self._clip_processor = CLIPProcessor.from_pretrained(_CLIP_MODEL)
            self._clip_model = CLIPModel.from_pretrained(_CLIP_MODEL)
            self._clip_model.eval()
        except ImportError:
            raise ImportError(
                "CLIP ROI requires transformers and torch. "
                "Install with: pip install context-distiller[gpu]"
            )

    def process(self, data: Any, **kwargs) -> Dict[str, Any]:
        """处理图像列表，提取与 query 相关的 ROI 区域

        data: 单张图像路径(str) 或图像路径列表(List[str])
        kwargs: query — 用于计算 ROI 相关性的文本提示
        """
        start = time.time()
        query = kwargs.get("query", "important content")

        if isinstance(data, str):
            image_paths = [data]
        else:
            image_paths = list(data)

        try:
            self._load_model()
            results = [self._extract_roi(path, query) for path in image_paths]
        except Exception as e:
            logger.warning("CLIP ROI failed, returning originals: %s", e)
            results = image_paths

        latency = (time.time() - start) * 1000
        return {
            "images": results,
            "stats": self.get_stats(len(image_paths), len(results), latency),
        }

    def _extract_roi(self, image_path: str, query: str) -> str:
        """对单张图像做网格切分，用 CLIP 评分，拼接高分区域"""
        from PIL import Image
        import torch

        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        grid = self._grid_size
        tile_w, tile_h = w // grid, h // grid

        if tile_w < 32 or tile_h < 32:
            return image_path

        tiles = []
        coords = []
        for row in range(grid):
            for col in range(grid):
                box = (col * tile_w, row * tile_h, (col + 1) * tile_w, (row + 1) * tile_h)
                tiles.append(img.crop(box))
                coords.append(box)

        inputs = self._clip_processor(
            text=[query], images=tiles, return_tensors="pt", padding=True
        )
        with torch.no_grad():
            outputs = self._clip_model(**inputs)
            logits = outputs.logits_per_text[0]
            scores = torch.softmax(logits, dim=-1).cpu().numpy()

        kept_boxes = [
            coords[i] for i, score in enumerate(scores)
            if score >= self._score_threshold
        ]

        if not kept_boxes:
            return image_path

        x_min = min(b[0] for b in kept_boxes)
        y_min = min(b[1] for b in kept_boxes)
        x_max = max(b[2] for b in kept_boxes)
        y_max = max(b[3] for b in kept_boxes)

        cropped = img.crop((x_min, y_min, x_max, y_max))

        import os
        base, ext = os.path.splitext(image_path)
        roi_path = f"{base}_roi{ext}"
        cropped.save(roi_path)
        return roi_path

    def estimate_tokens(self, data: Any) -> int:
        if isinstance(data, list):
            return len(data) * 85
        return 85
