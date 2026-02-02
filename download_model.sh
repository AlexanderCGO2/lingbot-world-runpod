#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${MODEL_ID:-robbyant/lingbot-world-base-cam}"
OUTPUT_DIR="${OUTPUT_DIR:-/workspace/lingbot-world-base-cam}"

python -m pip install "huggingface_hub[cli]"
if [[ -n "${HF_TOKEN:-}" ]]; then
  huggingface-cli login --token "${HF_TOKEN}"
fi
huggingface-cli download "${MODEL_ID}" --local-dir "${OUTPUT_DIR}"
echo "Model downloaded to ${OUTPUT_DIR}"
