FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY ddadam/backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY ddadam/backend/ .
RUN mkdir -p outputs temp_results worker
ENV PORT=8000
EXPOSE $PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]