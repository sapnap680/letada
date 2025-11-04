# backend/config.py
"""
環境設定管理（Pydantic Settings）
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # キャッシュ設定
    cache_type: str = "file"  # "file" or "redis"
    redis_url: Optional[str] = None  # Upstash Redis URL
    cache_file_path: str = "./worker/jba_player_cache.json"
    
    # 出力設定
    output_dir: str = "./outputs"
    job_meta_dir: str = "./temp_results"
    
    # Supabase 設定
    supabase_url: str = ""  # Required in production
    supabase_key: str = ""  # Service role key (required in production)
    supabase_anon: Optional[str] = None  # Anon key (optional)
    output_bucket: str = "outputs"  # Storage bucket name
    
    # ワーカー設定
    max_workers: int = 5
    enable_parallel: bool = True
    
    # JBA設定
    jba_base_url: str = "https://team-jba.jp"
    jba_timeout: int = 30
    jba_rate_limit: int = 10  # requests per second
    
    # 管理画面ログイン情報（CSV取得用 - コード内に固定）
    admin_username: str = "kcbf"
    admin_password: str = "sakura272"
    
    # API設定
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]  # TODO: 本番では制限すること
    
    # ログ設定
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    
    # 機能フラグ
    use_supabase_storage: bool = True  # False の場合はローカルファイル
    use_supabase_jobs: bool = True  # False の場合はファイルベース job_meta
    
    # TODO: 将来的な非同期化設定
    # enable_async: bool = False
    # async_http_client: str = "httpx"  # "httpx" or "aiohttp"
    
    # TODO: ジョブキュー設定
    # job_queue_type: str = "memory"  # "memory", "redis", "celery"
    # celery_broker_url: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# グローバル設定インスタンス
settings = Settings()

