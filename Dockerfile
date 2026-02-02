FROM runpod/pytorch:2.4.0-py3.10-cuda12.1.1-devel-ubuntu22.04

WORKDIR /workspace
COPY . /workspace

RUN python -m pip install --upgrade pip \
  && python -m pip install -r requirements.txt

ENV LINGBOT_CKPT_DIR=/workspace/lingbot-world-base-cam

# Optional: bake model into the image at build time.
# Example:
#   docker build --build-arg HF_TOKEN=... -t lingbot-world .
ARG HF_TOKEN
RUN if [ -n "$HF_TOKEN" ]; then \
    bash /workspace/download_model.sh; \
  fi

CMD ["python", "handler.py"]
