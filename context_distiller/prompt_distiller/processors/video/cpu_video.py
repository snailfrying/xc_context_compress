import time
import math
import logging
import os
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..base import BaseProcessor

logger = logging.getLogger(__name__)


class CPUVideoProcessor(BaseProcessor):
    """视频处理器 — 提供抽帧、音频提取、resize、多帧合并等基础算子

    处理流程:
      1. 抽帧 (frame extraction)  → 按间隔/关键帧采样
      2. 音频提取 (audio extract) → 通过 ffmpeg 分离音轨
      3. resize (可选)            → 缩放帧分辨率降低开销
      4. 多帧合并 (grid merge)    → 将多张帧拼为一张网格图

    所有子操作均可独立调用，也可通过 process() 一站式串联。
    """

    SUPPORTED_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts"}

    def __init__(self, fps_sample: float = 1.0, max_frames: int = 16,
                 resize_max: int = 512, grid_cols: int = 4):
        """
        Args:
            fps_sample: 每秒采样帧数，默认 1 fps
            max_frames: 最大采样帧数限制
            resize_max: 帧最大边长像素
            grid_cols: 多帧合并时每行列数
        """
        self._fps_sample = fps_sample
        self._max_frames = max_frames
        self._resize_max = resize_max
        self._grid_cols = grid_cols

    def process(self, data: Any, **kwargs) -> Dict[str, Any]:
        """一站式处理视频

        Args:
            data: 视频文件路径 (str)
            **kwargs:
                fps_sample: 覆盖采样帧率
                max_frames: 覆盖最大帧数
                resize_max: 覆盖缩放尺寸
                grid_cols: 覆盖网格列数
                extract_audio: 是否提取音频 (默认 True)
                merge_grid: 是否生成网格合并图 (默认 True)

        Returns:
            {frames, audio_path, grid_path, video_info, text, stats}
        """
        start = time.time()
        import cv2

        if isinstance(data, list):
            video_path = data[0]
        else:
            video_path = data

        if not Path(video_path).exists():
            return {"text": f"Video not found: {video_path}", "stats": self.get_stats(0, 0, 0)}

        fps_sample = kwargs.get("fps_sample", self._fps_sample)
        max_frames = kwargs.get("max_frames", self._max_frames)
        resize_max = kwargs.get("resize_max", self._resize_max)
        grid_cols = kwargs.get("grid_cols", self._grid_cols)
        extract_audio = kwargs.get("extract_audio", True)
        merge_grid = kwargs.get("merge_grid", True)

        uploads_dir = Path(os.environ.get("CONTEXT_DISTILLER_UPLOAD_DIR", "uploads"))
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # 视频信息
        video_info = self._get_video_info(video_path, cv2)

        # 1. 抽帧
        frames = self.extract_frames(video_path, fps_sample, max_frames, cv2=cv2)

        # 2. resize
        if resize_max:
            frames = [self.resize_frame(f, resize_max, cv2=cv2) for f in frames]

        # 3. 保存帧到 uploads
        frame_paths = []
        vid_id = uuid.uuid4().hex[:8]
        for i, frame in enumerate(frames):
            fname = f"vid_{vid_id}_f{i:03d}.jpg"
            fpath = uploads_dir / fname
            cv2.imwrite(str(fpath), frame)
            frame_paths.append(f"uploads/{fname}")

        # 4. 多帧合并
        grid_path = None
        if merge_grid and len(frames) > 0:
            grid_img = self.merge_frames_grid(frames, grid_cols, cv2=cv2)
            grid_name = f"vid_{vid_id}_grid.jpg"
            grid_full = uploads_dir / grid_name
            cv2.imwrite(str(grid_full), grid_img)
            grid_path = f"uploads/{grid_name}"

        # 5. 音频提取
        audio_path = None
        if extract_audio:
            audio_name = f"vid_{vid_id}_audio.wav"
            audio_full = uploads_dir / audio_name
            audio_path = self.extract_audio(video_path, str(audio_full))
            if audio_path:
                audio_path = f"uploads/{audio_name}"

        latency = (time.time() - start) * 1000

        summary_parts = [
            f"Video: {Path(video_path).name}",
            f"Duration: {video_info.get('duration', 0):.1f}s",
            f"Resolution: {video_info.get('width', 0)}x{video_info.get('height', 0)}",
            f"Extracted {len(frames)} frames at {fps_sample} fps",
        ]
        if grid_path:
            summary_parts.append(f"Grid: {grid_cols} cols")
        if audio_path:
            summary_parts.append("Audio extracted")

        input_tokens = int(video_info.get("duration", 0) * 30)  # 粗估
        output_tokens = len(frames) * 100 + (500 if audio_path else 0)

        return {
            "text": " | ".join(summary_parts),
            "frames": frame_paths,
            "grid_path": grid_path,
            "audio_path": audio_path,
            "video_info": video_info,
            "frame_count": len(frames),
            "stats": self.get_stats(input_tokens, output_tokens, latency),
        }

    # ---- 基础算子 ----

    def extract_frames(self, video_path: str, fps_sample: float = None,
                       max_frames: int = None, cv2=None) -> List:
        """抽帧算子：按时间间隔采样视频帧

        Args:
            video_path: 视频文件路径
            fps_sample: 每秒采样帧数
            max_frames: 最大帧数

        Returns:
            List[np.ndarray] — BGR 帧列表
        """
        if cv2 is None:
            import cv2
        fps_sample = fps_sample or self._fps_sample
        max_frames = max_frames or self._max_frames

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return []

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps if video_fps > 0 else 0

        # 计算采样间隔 (按帧号)
        frame_interval = max(1, int(video_fps / fps_sample))
        target_count = min(max_frames, int(duration * fps_sample) + 1)

        # 均匀采样帧号
        if target_count >= total_frames:
            sample_indices = list(range(total_frames))
        else:
            sample_indices = [int(i * total_frames / target_count) for i in range(target_count)]

        frames = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)

        cap.release()
        logger.info(f"Extracted {len(frames)} frames from {video_path} ({duration:.1f}s)")
        return frames

    def extract_audio(self, video_path: str, output_path: str) -> Optional[str]:
        """音频提取算子：从视频中分离音轨为 WAV

        依赖 ffmpeg，提取后可直接传入 CPUWhisperProcessor 进行 STT。

        Returns:
            成功返回输出路径，失败返回 None
        """
        import subprocess
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", output_path],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and Path(output_path).exists():
                logger.info(f"Audio extracted: {output_path}")
                return output_path
            else:
                logger.warning(f"ffmpeg audio extraction failed: {result.stderr[:200]}")
                return None
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install ffmpeg for audio extraction.")
            return None
        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            return None

    def resize_frame(self, frame, max_size: int = None, cv2=None):
        """resize 算子：自适应缩放帧

        保持宽高比，将最大边缩放到 max_size 像素。
        """
        if cv2 is None:
            import cv2
        max_size = max_size or self._resize_max
        h, w = frame.shape[:2]
        if max(h, w) <= max_size:
            return frame
        scale = max_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def merge_frames_grid(self, frames: List, cols: int = None, cv2=None):
        """多帧合并算子：将多张帧拼接为网格图

        用于一张图概览视频全貌，适合 VLM 理解视频内容。

        Args:
            frames: 帧列表 (BGR ndarray, 尺寸需一致或已 resize)
            cols: 每行列数

        Returns:
            np.ndarray — 合并后的网格图
        """
        import numpy as np
        if cv2 is None:
            import cv2
        if not frames:
            return np.zeros((64, 64, 3), dtype=np.uint8)

        cols = cols or self._grid_cols
        rows = math.ceil(len(frames) / cols)

        # 统一尺寸到第一帧的尺寸
        target_h, target_w = frames[0].shape[:2]
        resized = []
        for f in frames:
            if f.shape[:2] != (target_h, target_w):
                f = cv2.resize(f, (target_w, target_h))
            resized.append(f)

        # 补足空白帧
        while len(resized) < rows * cols:
            resized.append(np.zeros((target_h, target_w, 3), dtype=np.uint8))

        # 拼接
        row_imgs = []
        for r in range(rows):
            row_frames = resized[r * cols: (r + 1) * cols]
            row_imgs.append(np.hstack(row_frames))
        grid = np.vstack(row_imgs)

        return grid

    def _get_video_info(self, video_path: str, cv2=None) -> Dict[str, Any]:
        """获取视频基本信息"""
        if cv2 is None:
            import cv2
        cap = cv2.VideoCapture(video_path)
        info = {}
        if cap.isOpened():
            info = {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": round(cap.get(cv2.CAP_PROP_FPS), 2),
                "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "duration": round(cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1), 2),
            }
            cap.release()
        return info

    def estimate_tokens(self, data: Any) -> int:
        return 5000  # 默认估算
