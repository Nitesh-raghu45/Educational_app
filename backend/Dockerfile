FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    EMBEDDING_CACHE_DIR=/models

# Tesseract is only for reading text from uploaded images (~30 MB); remove this line if you don't need OCR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the ONNX all-MiniLM-L6-v2 model (~90 MB) into the image so containers start without downloading it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/models')"

COPY app ./app

RUN useradd --create-home appuser && mkdir -p /data/uploads && chown -R appuser /data /models
USER appuser

EXPOSE 8000
# Render (and similar hosts) pass the port in $PORT; docker-compose uses the default 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
