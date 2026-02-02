# RunPod Serverless Dockerfile for LingBot-World
# Optimized for RunPod GitHub integration (CPU-only build)
FROM runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04

WORKDIR /workspace

# Copy requirements first for caching
COPY requirements.txt /workspace/

# Install base dependencies (excluding flash_attn)
RUN python -m pip install --upgrade pip && \
    grep -v "flash_attn\|torch\|torchvision\|torchaudio" requirements.txt > /tmp/reqs.txt && \
    pip install -r /tmp/reqs.txt && \
    pip install requests einops

# Install flash-attn from prebuilt wheel (no CUDA compilation needed)
# This wheel is built for CUDA 12.2, torch 2.2, Python 3.10
RUN pip install https://github.com/Dao-AILab/flash-attention/releases/download/v2.5.9.post1/flash_attn-2.5.9.post1+cu122torch2.2cxx11abiFALSE-cp310-cp310-linux_x86_64.whl || \
    echo "Warning: flash-attn wheel failed, using sdpa fallback"

# Copy project files
COPY *.py /workspace/
COPY wan/ /workspace/wan/

# Set environment variables
ENV LINGBOT_CKPT_DIR=/runpod-volume/lingbot-world-base-cam
ENV PYTHONUNBUFFERED=1

# Start the serverless handler
CMD ["python", "-u", "handler.py"]
