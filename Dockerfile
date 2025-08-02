# We will use a single base image and conditionally install packages
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install common Python packages from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install system dependencies needed at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Use a conditional RUN block to install either CPU or GPU dependencies
ARG USE_GPU=false
RUN if [ "$USE_GPU" = "true" ]; then \
    # Install GPU-specific dependencies
    pip install --no-cache-dir 'faster-whisper[cu121]' 'ctranslate2[cu121]'; \
    elif [ "$USE_GPU" = "false" ]; then \
    # Install CPU-specific dependencies
    pip install --no-cache-dir 'faster-whisper[cpu]' 'ctranslate2[cpu]'; \
    fi

# Copy the rest of the application files into the container
COPY . .

# Pre-download a default model (if needed)
# RUN mkdir -p models && \
#     python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-tiny.en', local_dir='models/tiny.en', local_files_only=False)"

# Expose the port and run the Streamlit application
EXPOSE 8502
CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.address=0.0.0.0"]