# backend/routers/cache.py
"""
キャッシュ管理API
JBA選手データのキャッシュを管理
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_PATH = "worker/jba_player_cache.json"

class CacheStats(BaseModel):
    """キャッシュ統計情報"""
    entries: int
    size_mb: float
    exists: bool
    path: str

class CacheEntry(BaseModel):
    """キャッシュエントリ"""
    key: str
    player_name: str
    university: str
    jba_data: dict

@router.get("/", response_model=CacheStats)
async def get_cache_stats():
    """
    キャッシュの統計情報を取得
    """
    if not os.path.exists(CACHE_PATH):
        return CacheStats(
            entries=0,
            size_mb=0.0,
            exists=False,
            path=CACHE_PATH
        )
    
    try:
        size_bytes = os.path.getsize(CACHE_PATH)
        size_mb = size_bytes / 1024 / 1024
        
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return CacheStats(
            entries=len(data),
            size_mb=round(size_mb, 2),
            exists=True,
            path=CACHE_PATH
        )
    
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/")
async def clear_cache():
    """
    キャッシュをクリア
    """
    if not os.path.exists(CACHE_PATH):
        return {"status": "no_cache", "message": "キャッシュファイルが存在しません"}
    
    try:
        # バックアップを作成
        backup_path = CACHE_PATH + ".backup"
        if os.path.exists(CACHE_PATH):
            import shutil
            shutil.copy2(CACHE_PATH, backup_path)
        
        # キャッシュを削除
        os.remove(CACHE_PATH)
        
        logger.info("Cache cleared successfully")
        return {
            "status": "cleared",
            "message": "キャッシュをクリアしました",
            "backup": backup_path
        }
    
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries")
async def get_cache_entries(limit: int = 100, offset: int = 0):
    """
    キャッシュエントリの一覧を取得
    """
    if not os.path.exists(CACHE_PATH):
        return {"entries": [], "total": 0, "limit": limit, "offset": offset}
    
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # エントリをリスト化
        entries = []
        for key, value in list(data.items())[offset:offset+limit]:
            entries.append({
                "key": key,
                "data": value
            })
        
        return {
            "entries": entries,
            "total": len(data),
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Failed to get cache entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/warm")
async def warm_cache(universities: list[str]):
    """
    指定した大学のキャッシュを事前にウォームアップ
    
    TODO: 既存の _preload_university_data を活用
    """
    # TODO: 実装
    return {
        "status": "not_implemented",
        "message": "キャッシュウォームアップ機能は未実装です"
    }

# TODO: Redis 対応
# @router.get("/redis/stats")
# async def get_redis_stats():
#     """Redis キャッシュの統計情報"""
#     pass

