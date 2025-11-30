# Backend Dockerfile
FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# システムパッケージの更新と日本語フォントのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 依存ライブラリをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# 必要なディレクトリを作成
RUN mkdir -p outputs temp_results worker

# ポート公開（Fly.io用）
ENV PORT=8000
EXPOSE $PORT

# アプリケーション起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]


