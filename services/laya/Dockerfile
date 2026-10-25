FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LAYA_ASSIST_HOME=/data \
    HF_HOME=/cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch first to avoid pulling >3GB of NVIDIA CUDA packages
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# Clone and install laya-assist-proxy (pulls convai's laya and PyYAML)
RUN git clone --depth 1 https://github.com/dwyschka/laya-assist-proxy.git /app && \
    pip install -e /app

# Ensure server binds to 0.0.0.0 inside container so Traefik can reach port 7788
RUN find /app/laya_assist -name "*.py" -exec sed -i 's/"127.0.0.1"/"0.0.0.0"/g; s/127\.0\.0\.1/0.0.0.0/g' {} + || true

RUN mkdir -p /data /cache && chown -R 1000:1000 /app /data /cache

EXPOSE 7788

CMD ["laya-assist"]
