# Stage 1: GPU-specific build environment
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as gpu_builder
ARG USE_GPU=false
RUN if [ "$USE_GPU" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3.11-venv \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'faster-whisper[cu121]' 'ctranslate2[cu121]'; \
    fi

# Stage 2: CPU-specific build environment
FROM python:3.11-slim as cpu_builder
ARG USE_GPU=false
RUN if [ "$USE_GPU" = "false" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir 'faster-whisper[cpu]' 'ctranslate2[cpu]'; \
    fi

# Final Stage: The production image
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
ARG USE_GPU=false
COPY --from=gpu_builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=cpu_builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
EXPOSE 8502
CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.address=0.0.0.0"]