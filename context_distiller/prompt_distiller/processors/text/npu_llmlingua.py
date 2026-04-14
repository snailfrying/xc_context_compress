import time
from typing import Dict, Any
from pathlib import Path
from ..base import BaseProcessor

_SHARED_COMPRESSOR = None

# 本地模型路径：优先使用 models/llmlingua2，不存在时回退到 HuggingFace Hub
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LLMLINGUA2_LOCAL = str(_PROJECT_ROOT / "models" / "llmlingua2")
_LLMLINGUA2_MODEL = _LLMLINGUA2_LOCAL if Path(_LLMLINGUA2_LOCAL).exists() else "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

class NPULLMLinguaProcessor(BaseProcessor):
    """L2: LLMLingua-2 真实模型压缩"""

    def __init__(self):
        self._compressor = None

    def _load_model(self):
        """懒加载LLMLingua-2模型 (全局单例缓存)"""
        global _SHARED_COMPRESSOR
        if _SHARED_COMPRESSOR is None:
            try:
                import torch
                from llmlingua import PromptCompressor

                print(f"[Info] First run: Loading LLMLingua-2 from {_LLMLINGUA2_MODEL}...")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                _SHARED_COMPRESSOR = PromptCompressor(
                    model_name=_LLMLINGUA2_MODEL,
                    use_llmlingua2=True,
                    device_map=device
                )
            except Exception as e:
                print(f"[Warning] Failed to load LLMLingua-2: {e}, falling back to simple compression")
                _SHARED_COMPRESSOR = "fallback"
        
        self._compressor = _SHARED_COMPRESSOR
        return self._compressor

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        """处理文本"""
        start = time.time()

        compressor = self._load_model()
        rate = kwargs.get("rate", 0.4)

        # 使用真实模型或降级
        if compressor and compressor != "fallback":
            try:
                # LLMLingua-2 (XLM-RoBERTa) has a 512 token limit. 
                # Roughly 1800-2000 chars. If exceeded, we truncate to avoid crash.
                safe_data = data
                if len(data) > 1800:
                    safe_data = data[:1800]
                
                results = compressor.compress_prompt(safe_data, rate=rate)
                result_text = results.get('compressed_prompt', "")
                input_tokens = results.get('origin_tokens', 0)
                output_tokens = results.get('compressed_tokens', 0)
            except Exception as e:
                print(f"[Warning] LLMLingua-2 Error: {e}")
                # Fallback to simple truncation
                result_text = data[:int(len(data) * rate)]
                input_tokens = self.estimate_tokens(data)
                output_tokens = self.estimate_tokens(result_text)
        else:
            result_text = data[:int(len(data) * rate)]
            input_tokens = self.estimate_tokens(data)
            output_tokens = self.estimate_tokens(result_text)

        latency = (time.time() - start) * 1000

        return {
            "text": result_text,
            "stats": self.get_stats(input_tokens, output_tokens, latency)
        }

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
