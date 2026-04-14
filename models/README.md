# Models Directory

All local model files used by Context Distiller are stored here.

## Directory Structure

```
models/
├── gpt2/                  # L1: GPT-2 (SelectiveContext self-information filtering)
│   ├── config.json
│   ├── generation_config.json
│   ├── merges.txt
│   ├── model.safetensors
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   └── vocab.json
├── llmlingua2/            # L2: LLMLingua-2 (XLM-RoBERTa token classification)
│   ├── config.json
│   ├── model.safetensors
│   ├── special_tokens_map.json
│   ├── tokenizer.json
│   └── tokenizer_config.json
├── whisper-small/         # Audio: Whisper STT (faster-whisper CTranslate2)
│   ├── config.json
│   ├── model.bin
│   ├── tokenizer.json
│   └── vocabulary.txt
└── clip/                  # Vision: CLIP ROI extraction (optional, need manual download)
    └── (empty - download if needed)
```

## Source

These models are originally from HuggingFace Hub:

| Directory | HuggingFace Model ID | Size |
|-----------|---------------------|------|
| `gpt2/` | `gpt2` | ~523 MB |
| `llmlingua2/` | `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | ~2.1 GB |
| `whisper-small/` | `Systran/faster-whisper-small` | ~464 MB |
| `clip/` | `openai/clip-vit-base-patch32` | ~600 MB |

## How to Download (if missing)

```python
from transformers import AutoModel, AutoTokenizer

# GPT-2
AutoTokenizer.from_pretrained("gpt2").save_pretrained("models/gpt2")
AutoModel.from_pretrained("gpt2").save_pretrained("models/gpt2")

# LLMLingua-2
AutoTokenizer.from_pretrained("microsoft/llmlingua-2-xlm-roberta-large-meetingbank").save_pretrained("models/llmlingua2")
AutoModel.from_pretrained("microsoft/llmlingua-2-xlm-roberta-large-meetingbank").save_pretrained("models/llmlingua2")

# Whisper (faster-whisper uses CTranslate2 format, auto-downloads on first use)
# No manual download needed - will auto-download from Systran/faster-whisper-small

# CLIP (optional)
from transformers import CLIPProcessor, CLIPModel
CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32").save_pretrained("models/clip")
CLIPModel.from_pretrained("openai/clip-vit-base-patch32").save_pretrained("models/clip")
```

For Chinese users:
```bash
export HF_ENDPOINT=https://hf-mirror.com
```
