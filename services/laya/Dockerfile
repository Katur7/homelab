FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LAYA_ASSIST_HOME=/data \
    HF_HOME=/cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch first to avoid pulling >3GB of NVIDIA CUDA packages
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# Install OpenVINO + NNCF for INT8 quantization and rupeshs/laya-openvino runtime
RUN pip install openvino nncf git+https://github.com/rupeshs/laya-openvino.git

# Clone and install laya-assist-proxy without overwriting laya-openvino
RUN git clone --depth 1 https://github.com/dwyschka/laya-assist-proxy.git /app && \
    pip install PyYAML && \
    pip install --no-deps -e /app

# Overlay English + Trilingual (EN/SV/IS) + OpenVINO INT8 modules
COPY laya_assist/ /app/laya_assist/

RUN mkdir -p /data /cache && chown -R 1000:1000 /app /data /cache

EXPOSE 7788

CMD ["laya-assist"]
