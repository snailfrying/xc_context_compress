import time
import math
import logging
from typing import Dict, Any, List
from pathlib import Path
from ..base import BaseProcessor

logger = logging.getLogger(__name__)

# 本地模型路径：优先使用 models/gpt2，不存在时回退到 HuggingFace Hub
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_GPT2_LOCAL = str(_PROJECT_ROOT / "models" / "gpt2")
_GPT2_MODEL = _GPT2_LOCAL if Path(_GPT2_LOCAL).exists() else "gpt2"


class CPUSelectiveProcessor(BaseProcessor):
    """L1: SelectiveContext — GPT-2 自信息量过滤

    基于 self-information 理论：token 的信息量 = -log2(P(token|context))。
    低信息量的 token/phrase 对 LLM 理解贡献小，可安全移除。
    """

    def __init__(self, reduce_ratio: float = 0.5):
        self._tokenizer = None
        self._model = None
        self._reduce_ratio = reduce_ratio

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from transformers import GPT2Tokenizer, GPT2LMHeadModel
            import torch
            self._tokenizer = GPT2Tokenizer.from_pretrained(_GPT2_MODEL)
            self._model = GPT2LMHeadModel.from_pretrained(_GPT2_MODEL)
            self._model.eval()
            self._torch = torch
        except ImportError:
            raise ImportError(
                "GPT-2 model requires transformers and torch. "
                "Install with: pip install transformers torch"
            )

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        start = time.time()
        input_tokens = self.estimate_tokens(data)
        reduce_ratio = kwargs.get("reduce_ratio", self._reduce_ratio)

        try:
            self._load_model()
            result = self._selective_context(data, reduce_ratio)
        except Exception as e:
            logger.warning("SelectiveContext failed, using fallback: %s", e)
            result = self._fallback_compress(data, reduce_ratio)

        output_tokens = self.estimate_tokens(result)
        latency = (time.time() - start) * 1000
        return {
            "text": result,
            "stats": self.get_stats(input_tokens, output_tokens, latency),
        }

    def _selective_context(self, text: str, reduce_ratio: float) -> str:
        """计算每个 token 的 self-information 并过滤低信息量 token"""
        sentences = self._split_sentences(text)
        if not sentences:
            return text

        sentence_scores = []
        for sent in sentences:
            score = self._compute_sentence_self_info(sent)
            sentence_scores.append((sent, score))

        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        keep_count = max(1, int(len(sentence_scores) * (1 - reduce_ratio)))
        kept = sentence_scores[:keep_count]

        kept_ordered = sorted(kept, key=lambda x: sentences.index(x[0]))
        return " ".join(s for s, _ in kept_ordered)

    def _compute_sentence_self_info(self, sentence: str) -> float:
        """计算句子级别的平均自信息量"""
        torch = self._torch
        encoding = self._tokenizer(sentence, return_tensors="pt", truncation=True, max_length=512)
        input_ids = encoding["input_ids"]

        if input_ids.shape[1] <= 1:
            return 0.0

        with torch.no_grad():
            outputs = self._model(input_ids)
            logits = outputs.logits

        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        token_ids = input_ids[0, 1:]
        token_log_probs = log_probs[0, :-1, :].gather(1, token_ids.unsqueeze(1)).squeeze(1)

        self_info = -token_log_probs / math.log(2)
        return self_info.mean().item()

    def _split_sentences(self, text: str) -> List[str]:
        import re
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _fallback_compress(self, text: str, reduce_ratio: float) -> str:
        """无模型降级：按句子长度排序保留信息密度高的句子"""
        sentences = self._split_sentences(text)
        if not sentences:
            return text
        scored = [(s, len(set(s.lower().split())) / max(len(s.split()), 1)) for s in sentences]
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_count = max(1, int(len(scored) * (1 - reduce_ratio)))
        kept = scored[:keep_count]
        kept_ordered = sorted(kept, key=lambda x: sentences.index(x[0]))
        return " ".join(s for s, _ in kept_ordered)

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
