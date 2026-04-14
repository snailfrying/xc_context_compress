import os
import time
import logging
import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..base import BaseProcessor

logger = logging.getLogger(__name__)

# Constants for smart chunking (Sized to fit within 512 token local models)
MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 200


def _extract_text(filepath: str, backend: str, llm_url: str = None, llm_model: str = None, use_vlm: bool = False) -> str:
    """Extract raw text from a document file."""

    if backend == "markitdown":
        try:
            from markitdown import MarkItDown

            md_args = {}
            if use_vlm and llm_url and llm_model:
                try:
                    from openai import OpenAI
                    # Ensure url ends with /v1 as OpenAI SDK expects
                    base_url = llm_url if llm_url.endswith("/v1") else llm_url.rstrip("/") + "/v1"
                    client = OpenAI(base_url=base_url, api_key="ollama")
                    md_args["llm_client"] = client
                    md_args["llm_model"] = llm_model
                    logger.info(f"[MarkItDown] VLM enabled: model={llm_model} url={base_url}")
                except Exception as ve:
                    logger.warning(f"[MarkItDown] VLM init failed (running without VLM): {ve}")

            md = MarkItDown(**md_args)
            result = md.convert(str(Path(filepath).resolve()))
            text = result.text_content or ""
            logger.info(f"[MarkItDown] Extracted {len(text)} chars from {filepath}")
            return text
        except Exception as e:
            logger.error(f"[MarkItDown] Failed: {e}", exc_info=True)
            return ""

    elif backend == "docling":
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(Path(filepath).resolve()))
            text = result.document.export_to_markdown()
            logger.info(f"[Docling] Extracted {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"[Docling] Failed: {e}", exc_info=True)
            return ""

    elif backend == "pymupdf":
        try:
            import fitz
            doc = fitz.open(str(Path(filepath).resolve()))
            text = "\n".join(page.get_text() for page in doc)
            logger.info(f"[PyMuPDF] Extracted {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"[PyMuPDF] Failed: {e}", exc_info=True)
            return ""

    else:
        logger.warning(f"[DocExtract] Unknown backend '{backend}', falling back to PyMuPDF")
        try:
            import fitz
            doc = fitz.open(str(Path(filepath).resolve()))
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            logger.error(f"[Fallback PyMuPDF] Failed: {e}", exc_info=True)
            return ""


class CPUNativeProcessor(BaseProcessor):
    """L0/L1 Document Processor — Uses local CPU tools like MarkItDown/Docling/PyMuPDF."""

    def __init__(
        self,
        backend: str = "markitdown",
        model_url: Optional[str] = None,
        model_name: Optional[str] = None,
        use_vlm: bool = False,  # 默认不启用 VLM，需在 UI 手动勾选
    ):
        self.backend = backend
        self.model_url = model_url
        self.model_name = model_name
        self.use_vlm = use_vlm
        self._text_compressor: Optional[BaseProcessor] = None

    def set_text_compressor(self, compressor: BaseProcessor):
        self._text_compressor = compressor

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        start = time.time()
 
        raw_text = _extract_text(data, self.backend, self.model_url, self.model_name, self.use_vlm)
        if not raw_text.strip():
            return {
                "text": "",
                "chunks": [],
                "raw_length": 0,
                "compressed_length": 0,
                "stats": self.get_stats(0, 0, (time.time() - start) * 1000)
            }

        # Step 2: Smart Chunking (Regex-based header/paragraph split)
        chunks = self._smart_chunk(raw_text)
        
        # Step 3: Compression per chunk
        compressed_chunks = []
        total_in = 0
        total_out = 0

        for idx, chunk in enumerate(chunks):
            chunk_text = chunk["text"]
            total_in += len(chunk_text) # char count for now
            
            if self._text_compressor:
                c_res = self._text_compressor.process(chunk_text)
                c_text = c_res.get("text", chunk_text)
            else:
                c_text = chunk_text # No compression
            
            total_out += len(c_text)
            compressed_chunks.append({
                "index": idx,
                "title": chunk["title"],
                "text": chunk_text,
                "compressed": c_text
            })

        latency = (time.time() - start) * 1000
        
        return {
            "text": "\n\n".join([c["compressed"] for c in compressed_chunks]),
            "chunks": compressed_chunks,
            "raw_length": total_in,
            "compressed_length": total_out,
            "stats": self.get_stats(total_in // 4, total_out // 4, latency)
        }

    def _smart_chunk(self, text: str) -> List[Dict[str, str]]:
        """Split text into manageable chunks based on structural boundaries."""
        # Simple split by Double Newline or Headers
        boundaries = [m.start() for m in re.finditer(r'\n#{1,3}\s|\n\n', text)]
        
        chunks = []
        start = 0
        for boundary in boundaries:
            if boundary - start > MAX_CHUNK_CHARS:
                # Force split big blocks
                self._force_split(text[start:boundary], chunks, start_idx=start)
            else:
                chunk_body = text[start:boundary].strip()
                if len(chunk_body) > MIN_CHUNK_CHARS:
                    title = self._extract_title(chunk_body)
                    chunks.append({"text": chunk_body, "title": title})
            start = boundary

        # Last block
        last_body = text[start:].strip()
        if len(last_body) > 0:
            if len(last_body) > MAX_CHUNK_CHARS:
                self._force_split(last_body, chunks, start_idx=start)
            else:
                chunks.append({"text": last_body, "title": self._extract_title(last_body)})

        return chunks

    def _force_split(self, text: str, chunks: list, start_idx: int):
        """Rudimentary split for very long single paragraphs."""
        words = text.split()
        current = []
        current_len = 0
        for w in words:
            current.append(w)
            current_len += len(w) + 1
            if current_len > MAX_CHUNK_CHARS:
                body = " ".join(current)
                chunks.append({"text": body, "title": f"Segment @ {start_idx}"})
                current = []
                current_len = 0
        if current:
            chunks.append({"text": " ".join(current), "title": f"Segment @ {start_idx}"})

    def _extract_title(self, text: str) -> str:
        first_line = text.split('\n', 1)[0].strip()
        return first_line[:50] + "..." if len(first_line) > 50 else first_line

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
