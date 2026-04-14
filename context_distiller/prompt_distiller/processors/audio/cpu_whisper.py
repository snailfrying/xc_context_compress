import time
import logging
from typing import Dict, Any
from pathlib import Path
from ..base import BaseProcessor

logger = logging.getLogger(__name__)

# 本地模型路径：优先使用 models/whisper-small，不存在时回退到 HuggingFace Hub
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_WHISPER_LOCAL = str(_PROJECT_ROOT / "models" / "whisper-small")
_WHISPER_MODEL = _WHISPER_LOCAL if Path(_WHISPER_LOCAL).exists() else "Systran/faster-whisper-small"

_SHARED_MODEL = None


class CPUWhisperProcessor(BaseProcessor):
    """音频转文字处理器 — 基于 faster-whisper (CTranslate2) 实现 STT

    支持 .mp3 / .wav / .flac / .m4a / .ogg / .wma 等常见音频格式。
    输出转录文本 + 时间戳分段，可直接接入文本压缩流水线。
    """

    SUPPORTED_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma", ".aac", ".opus"}

    def __init__(self, model_size: str = "small", language: str = None):
        self._model = None
        self._model_size = model_size
        self._language = language  # None = 自动检测

    def _load_model(self):
        global _SHARED_MODEL
        if _SHARED_MODEL is not None:
            self._model = _SHARED_MODEL
            return
        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model from {_WHISPER_MODEL} ...")
            _SHARED_MODEL = WhisperModel(
                _WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )
            self._model = _SHARED_MODEL
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Whisper model load failed: {e}")

    def process(self, data: Any, **kwargs) -> Dict[str, Any]:
        """处理音频文件，返回转录文本

        Args:
            data: 音频文件路径 (str) 或路径列表
            **kwargs:
                language: 指定语言代码 (如 "zh", "en")，None 自动检测
                beam_size: beam search 宽度，默认 5

        Returns:
            {text, segments, stats}
        """
        start = time.time()
        self._load_model()

        language = kwargs.get("language", self._language)
        beam_size = kwargs.get("beam_size", 5)

        if isinstance(data, list):
            paths = data
        else:
            paths = [data]

        all_segments = []
        all_text_parts = []
        input_duration = 0.0

        for audio_path in paths:
            if not isinstance(audio_path, str):
                continue
            if not Path(audio_path).exists():
                logger.warning(f"Audio file not found: {audio_path}")
                continue

            try:
                segments_iter, info = self._model.transcribe(
                    audio_path,
                    language=language,
                    beam_size=beam_size,
                    vad_filter=True,
                )
                input_duration += info.duration

                file_segments = []
                for seg in segments_iter:
                    file_segments.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": seg.text.strip(),
                    })

                text = " ".join(s["text"] for s in file_segments)
                all_text_parts.append(text)
                all_segments.append({
                    "file": audio_path,
                    "language": info.language,
                    "language_probability": round(info.language_probability, 3),
                    "duration": round(info.duration, 2),
                    "segments": file_segments,
                })
            except Exception as e:
                logger.error(f"Transcription failed for {audio_path}: {e}")
                all_segments.append({"file": audio_path, "error": str(e)})

        full_text = "\n\n".join(all_text_parts)
        latency = (time.time() - start) * 1000

        # token 估算：输入按音频时长（1s ≈ 25 tokens whisper），输出按文本长度
        input_tokens = int(input_duration * 25)
        output_tokens = len(full_text) // 4

        return {
            "text": full_text,
            "segments": all_segments,
            "duration": round(input_duration, 2),
            "stats": self.get_stats(input_tokens, output_tokens, latency),
        }

    def estimate_tokens(self, data: Any) -> int:
        """粗略估算：1 秒音频 ≈ 25 tokens"""
        return 2500  # 默认估算 ~100 秒音频
