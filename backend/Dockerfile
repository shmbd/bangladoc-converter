FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BANGLADOC_STORAGE_DIR=/tmp/bangladoc_storage \
    PORT=7860

# Install Linux Tesseract OCR + OpenCV runtime libs + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 \
    libxcb1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Download high-accuracy (tessdata_best) and fast (tessdata_fast) Bangla + English LSTM models
RUN mkdir -p /app/vendor/tessdata_best/configs /app/vendor/tessdata_fast/configs && \
    cp -r /usr/share/tesseract-ocr/*/tessdata/configs/* /app/vendor/tessdata_best/configs/ 2>/dev/null || true && \
    cp -r /usr/share/tesseract-ocr/*/tessdata/configs/* /app/vendor/tessdata_fast/configs/ 2>/dev/null || true && \
    for lang in ben eng osd; do \
      curl -fsSL "https://github.com/tesseract-ocr/tessdata_best/raw/main/${lang}.traineddata" -o "/app/vendor/tessdata_best/${lang}.traineddata" && \
      curl -fsSL "https://github.com/tesseract-ocr/tessdata_fast/raw/main/${lang}.traineddata" -o "/app/vendor/tessdata_fast/${lang}.traineddata"; \
    done

# Copy backend source & SIL OFL Bangla fonts
COPY --chown=user:user app /app/app
COPY --chown=user:user assets /app/assets

RUN mkdir -p /tmp/bangladoc_storage && chown -R user:user /app /tmp/bangladoc_storage

USER user
EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
