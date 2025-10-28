# backend/main.py
"""
FastAPI メインアプリケーション
Streamlit から移行した JBA 照合システムのバックエンド
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import verify, pdf, cache, jobs, tournament
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="JBA Verification API",
    description="大学バスケットボール選手のJBA照合・PDF生成システム",
    version="2.0.0"
)

# CORS設定（開発用 - 本番では適切に制限）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 本番では特定のオリジンのみ許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(verify.router, prefix="/verify", tags=["verify"])
app.include_router(pdf.router, prefix="/pdf", tags=["pdf"])
app.include_router(cache.router, prefix="/cache", tags=["cache"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(tournament.router, prefix="/tournament", tags=["tournament"])  # 大会ID処理

@app.get("/")
def root():
    """ヘルスチェック"""
    return {
        "status": "ok",
        "service": "JBA Verification API",
        "version": "2.0.0"
    }

@app.get("/health")
def health():
    """詳細なヘルスチェック"""
    import os
    
    # ディレクトリの存在チェック
    temp_results_exists = os.path.exists("temp_results")
    outputs_exists = os.path.exists("outputs")
    worker_exists = os.path.exists("worker")
    
    # ファイル一覧
    temp_results_files = []
    if temp_results_exists:
        try:
            temp_results_files = os.listdir("temp_results")
        except Exception as e:
            temp_results_files = [f"Error: {str(e)}"]
    
    return {
        "status": "healthy",
        "directories": {
            "temp_results": temp_results_exists,
            "outputs": outputs_exists,
            "worker": worker_exists
        },
        "temp_results_files": temp_results_files[:10],  # 最初の10件のみ
        "cwd": os.getcwd(),
        "env": {
            "admin_username": os.getenv("ADMIN_USERNAME", "not set"),
            "admin_password_set": bool(os.getenv("ADMIN_PASSWORD"))
        }
    }

