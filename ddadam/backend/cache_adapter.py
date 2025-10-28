# backend/cache_adapter.py
"""
キャッシュアダプター（ファイル / Redis 切替可能）

設定: config.cache_type = "file" or "redis"
"""

import json
import os
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

class CacheAdapter(ABC):
    """キャッシュアダプターの抽象クラス"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """キーから値を取得"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """キーに値を設定"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """キーを削除"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """全キャッシュをクリア"""
        pass
    
    @abstractmethod
    def keys(self) -> list[str]:
        """全キーを取得"""
        pass
    
    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        pass

class FileCache(CacheAdapter):
    """ファイルベースのキャッシュ（既存実装）"""
    
    def __init__(self, cache_file: str = None):
        self.cache_file = cache_file or settings.cache_file_path
        self._cache: Dict[str, Any] = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """キャッシュファイルをロード"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
                return {}
        return {}
    
    def _save(self) -> bool:
        """キャッシュをファイルに保存"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        self._cache[key] = value
        return self._save()
    
    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return self._save()
        return False
    
    def clear(self) -> bool:
        self._cache = {}
        return self._save()
    
    def keys(self) -> list[str]:
        return list(self._cache.keys())
    
    def stats(self) -> Dict[str, Any]:
        size_mb = 0
        if os.path.exists(self.cache_file):
            size_mb = os.path.getsize(self.cache_file) / 1024 / 1024
        
        return {
            'type': 'file',
            'entries': len(self._cache),
            'size_mb': round(size_mb, 2),
            'path': self.cache_file
        }

class RedisCache(CacheAdapter):
    """Redis ベースのキャッシュ（Upstash 対応）"""
    
    def __init__(self, redis_url: str = None):
        try:
            import redis
            self.redis_url = redis_url or settings.redis_url
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.prefix = "jba_cache:"
            
            # 接続テスト
            self.client.ping()
            logger.info(f"Redis connected: {self.redis_url}")
        except ImportError:
            logger.error("redis package not installed. Run: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            value = self.client.get(f"{self.prefix}{key}")
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        try:
            json_value = json.dumps(value, ensure_ascii=False)
            if ttl:
                self.client.setex(f"{self.prefix}{key}", ttl, json_value)
            else:
                self.client.set(f"{self.prefix}{key}", json_value)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self.client.delete(f"{self.prefix}{key}")
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    def clear(self) -> bool:
        try:
            # prefix に一致するキーを全削除
            keys = self.client.keys(f"{self.prefix}*")
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    def keys(self) -> list[str]:
        try:
            keys = self.client.keys(f"{self.prefix}*")
            # prefix を除去して返す
            return [key.replace(self.prefix, '') for key in keys]
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []
    
    def stats(self) -> Dict[str, Any]:
        try:
            info = self.client.info('memory')
            keys_count = len(self.client.keys(f"{self.prefix}*"))
            
            return {
                'type': 'redis',
                'entries': keys_count,
                'used_memory_mb': round(info.get('used_memory', 0) / 1024 / 1024, 2),
                'connected': True
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {
                'type': 'redis',
                'connected': False,
                'error': str(e)
            }

# ファクトリー関数
_cache_instance = None

def get_cache() -> CacheAdapter:
    """
    設定に基づいてキャッシュアダプターを取得（シングルトン）
    
    Returns:
        CacheAdapter インスタンス
    """
    global _cache_instance
    
    if _cache_instance is None:
        cache_type = settings.cache_type.lower()
        
        if cache_type == 'redis':
            try:
                _cache_instance = RedisCache()
                logger.info("Using Redis cache")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis, falling back to file cache: {e}")
                _cache_instance = FileCache()
        else:
            _cache_instance = FileCache()
            logger.info("Using file cache")
    
    return _cache_instance

def get_cache_key(player_name: str, university_name: str) -> str:
    """
    キャッシュキーを生成
    
    Args:
        player_name: 選手名
        university_name: 大学名
    
    Returns:
        ハッシュ化されたキー
    """
    # 正規化して一意なキーを生成
    key_string = f"{player_name}_{university_name}".lower().strip()
    return hashlib.md5(key_string.encode()).hexdigest()


