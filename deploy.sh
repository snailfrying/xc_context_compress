#!/usr/bin/env bash
# =====================================================================
# Context Distiller 2.0 — Linux Deployment Script
# =====================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PYTHON_MIN="3.10"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# =====================================================================
# 1. System Dependencies Check
# =====================================================================
info "Checking system dependencies..."

# Python version check
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON_CMD="$cmd"
            info "Found Python $ver ($cmd)"
            break
        fi
    fi
done
[ -z "$PYTHON_CMD" ] && error "Python >= $PYTHON_MIN not found. Install with: sudo apt install python3.10"

# System packages (for OpenCV headless & other native deps)
MISSING_PKGS=()
for pkg in libgl1-mesa-glx libglib2.0-0; do
    if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    warn "Missing system packages: ${MISSING_PKGS[*]}"
    warn "Install with: sudo apt install -y ${MISSING_PKGS[*]}"
    read -rp "Install now? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        sudo apt install -y "${MISSING_PKGS[@]}"
    fi
fi

# =====================================================================
# 2. Virtual Environment
# =====================================================================
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q

# =====================================================================
# 3. Install Dependencies
# =====================================================================
info "Installing base dependencies..."
pip install -r requirements.txt -q

# GPU support (optional)
read -rp "Install GPU dependencies (torch, transformers, onnxruntime-gpu)? [y/N] " gpu_ans
if [[ "$gpu_ans" =~ ^[Yy]$ ]]; then
    info "Installing GPU dependencies..."
    pip install ".[gpu]" -q
fi

# Install package in editable mode
pip install -e . -q

# =====================================================================
# 4. Models Directory
# =====================================================================
info "Setting up models directory..."
mkdir -p models uploads .transcripts

if [ ! -f "models/llmlingua2.onnx" ]; then
    warn "ONNX model not found at models/llmlingua2.onnx"
    warn "Options:"
    warn "  1. Copy from Windows: scp user@windows:path/to/models/llmlingua2.onnx* models/"
    warn "  2. Generate locally:  python test_demo/convert_to_onnx.py"
    warn "  (Requires GPU extras: pip install '.[gpu]')"
fi

# =====================================================================
# 5. HuggingFace Mirror (China)
# =====================================================================
if [ -z "${HF_ENDPOINT:-}" ]; then
    read -rp "Set HuggingFace mirror for China (hf-mirror.com)? [y/N] " hf_ans
    if [[ "$hf_ans" =~ ^[Yy]$ ]]; then
        export HF_ENDPOINT="https://hf-mirror.com"
        echo 'export HF_ENDPOINT="https://hf-mirror.com"' >> "$VENV_DIR/bin/activate"
        info "HF_ENDPOINT set to https://hf-mirror.com"
    fi
fi

# =====================================================================
# 6. Configuration Check
# =====================================================================
info "Checking configuration..."
CONFIG_FILE="context_distiller/config/default.yaml"
if [ -f "$CONFIG_FILE" ]; then
    OLLAMA_URL=$(grep "base_url" "$CONFIG_FILE" | head -1 | awk '{print $2}' | tr -d '"')
    info "Ollama server: $OLLAMA_URL"
    if command -v curl &>/dev/null; then
        if curl -s --connect-timeout 3 "$OLLAMA_URL" >/dev/null 2>&1; then
            info "Ollama server is reachable"
        else
            warn "Cannot reach Ollama server at $OLLAMA_URL"
            warn "Update llm_server.base_url in $CONFIG_FILE if needed"
        fi
    fi
fi

# =====================================================================
# 7. Verify Installation
# =====================================================================
info "Running installation verification..."
python verify_installation.py || warn "Some checks failed (see above)"

# =====================================================================
# 8. Summary
# =====================================================================
echo ""
echo "=============================================="
echo "  Context Distiller 2.0 — Deployment Ready"
echo "=============================================="
echo ""
info "Start the server:"
echo "  source $VENV_DIR/bin/activate"
echo "  context-distiller serve"
echo "  # or: uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port 8080"
echo ""
info "Firewall: ensure port 8080 is open"
echo "  sudo ufw allow 8085/tcp"
echo ""
