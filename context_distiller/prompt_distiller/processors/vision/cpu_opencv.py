import time
import hashlib
from typing import Dict, Any, List
from ..base import BaseProcessor


class CPUOpenCVProcessor(BaseProcessor):
    """CPU图像预处理：降维/裁剪 + pHash去重"""

    def __init__(self):
        self._phash_cache = set()

    def process(self, data: Any, **kwargs) -> Dict[str, Any]:
        """处理图像路径或列表"""
        start = time.time()

        import cv2
        import numpy as np

        import os
        from pathlib import Path
        uploads_dir = Path(os.environ.get("CONTEXT_DISTILLER_UPLOAD_DIR", "uploads"))
        uploads_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(data, list):
            paths = data
        else:
            paths = [data]

        results = []
        for img_path in paths:
            # 检查输入是否为合法的路径字符串
            if not isinstance(img_path, str):
                continue

            img = cv2.imread(img_path)
            if img is None:
                continue

            # pHash去重
            phash = self._compute_phash(img)
            if phash in self._phash_cache:
                continue
            self._phash_cache.add(phash)

            # 降维
            resized = self._resize_image(img, max_size=1024)
            
            # 保存处理后的图片以便 UI 展示
            ext = Path(img_path).suffix or ".jpg"
            save_name = f"opt_{phash}{ext}"
            save_path = uploads_dir / save_name
            cv2.imwrite(str(save_path), resized)
            
            results.append({"path": f"uploads/{save_name}", "phash": phash})

        latency = (time.time() - start) * 1000

        # 生成描述性文本供 UI 显示
        summary = f"Processed {len(results)} unique images."
        if results:
            summary += f" (pHash cache size: {len(self._phash_cache)})"

        return {
            "text": summary,
            "images": results,
            "stats": self.get_stats(len(paths), len(results), latency)
        }

    def _compute_phash(self, img) -> str:
        """计算感知哈希"""
        import cv2
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (8, 8))
        avg = resized.mean()
        diff = resized > avg
        return hashlib.md5(diff.tobytes()).hexdigest()

    def _resize_image(self, img, max_size: int):
        """自适应缩放"""
        import cv2
        h, w = img.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            return cv2.resize(img, (new_w, new_h))
        return img

    def estimate_tokens(self, data: Any) -> int:
        return 0
