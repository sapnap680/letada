# backend/supabase_helper.py
"""
Supabase Storage + Postgres 統合ヘルパー

- Storage: PDF/ZIP ファイルのアップロード・ダウンロード
- Postgres: jobs テーブルの管理
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import os
from supabase import create_client, Client
from config import settings

logger = logging.getLogger(__name__)

class SupabaseHelper:
    """Supabase 操作を抽象化"""
    
    def __init__(self):
        """Supabase クライアントを初期化"""
        try:
            self.client: Client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            self.bucket_name = settings.output_bucket
            logger.info(f"Supabase initialized: bucket={self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            raise
    
    # ==================== Storage Operations ====================
    
    def upload_file(self, local_path: str, storage_path: str) -> Optional[str]:
        """
        ファイルを Supabase Storage にアップロード
        
        Args:
            local_path: ローカルファイルパス
            storage_path: Storage内のパス (例: "reports/output.pdf")
        
        Returns:
            公開URL または None
        """
        try:
            if not os.path.exists(local_path):
                logger.error(f"File not found: {local_path}")
                return None
            
            with open(local_path, "rb") as f:
                file_data = f.read()
            
            # アップロード
            logger.info(f"Uploading to Supabase bucket={self.bucket_name}, path={storage_path}")
            response = self.client.storage.from_(self.bucket_name).upload(
                storage_path,
                file_data,
                file_options={
                    "contentType": self._get_content_type(local_path),  # supabase-py expects contentType
                    "upsert": True  # 既存ファイルがある場合は上書き
                }
            )
            
            # 公開URLを取得
            # SDKの戻り値に依存せず、環境変数のURLから公開URLを構築
            base_url = settings.supabase_url.rstrip('/')
            public_url = f"{base_url}/storage/v1/object/public/{self.bucket_name}/{storage_path}"
            logger.info(f"Uploaded {local_path} to {storage_path}. public_url={public_url}")
            return public_url
        
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return None
    
    def get_signed_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        署名付きURL を生成（プライベートバケット用）
        
        Args:
            storage_path: Storage内のパス
            expires_in: 有効期限（秒）
        
        Returns:
            署名付きURL または None
        """
        try:
            response = self.client.storage.from_(self.bucket_name).create_signed_url(
                storage_path,
                expires_in
            )
            return response.get('signedURL')
        except Exception as e:
            logger.error(f"Failed to create signed URL: {e}")
            return None
    
    def _get_content_type(self, filename: str) -> str:
        """ファイル拡張子から Content-Type を判定"""
        ext = filename.lower().split('.')[-1]
        content_types = {
            'pdf': 'application/pdf',
            'zip': 'application/zip',
            'json': 'application/json',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'csv': 'text/csv'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    # ==================== Jobs Table Operations ====================
    
    def create_job(
        self,
        job_id: str,
        job_type: str = "pdf_generation",
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        新しいジョブを jobs テーブルに作成
        
        Args:
            job_id: ジョブID (UUID)
            job_type: ジョブタイプ
            metadata: メタデータ（大学リストなど）
        
        Returns:
            成功したか
        """
        try:
            data = {
                'job_id': job_id,
                'status': 'queued',
                'progress': 0.0,
                'message': 'ジョブを開始しました',
                'job_type': job_type,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            response = self.client.table('jobs').insert(data).execute()
            logger.info(f"Created job: {job_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to create job {job_id}: {e}")
            return False
    
    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
        error_detail: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        ジョブステータスを更新
        
        Args:
            job_id: ジョブID
            status: ステータス (queued/running/done/error)
            progress: 進捗 (0.0 ~ 1.0)
            message: メッセージ
            output_path: 出力ファイルのパス（Storage URL）
            error: エラーメッセージ
        
        Returns:
            成功したか
        """
        try:
            update_data = {
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if status is not None:
                update_data['status'] = status
            if progress is not None:
                update_data['progress'] = progress
            if message is not None:
                update_data['message'] = message
            if output_path is not None:
                update_data['output_path'] = output_path
            if error is not None:
                update_data['error'] = error
            if error_detail is not None:
                update_data['error_detail'] = error_detail
            if metadata is not None:
                update_data['metadata'] = metadata
            
            response = self.client.table('jobs').update(update_data).eq('job_id', job_id).execute()
            return True
        
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        ジョブ情報を取得
        
        Args:
            job_id: ジョブID
        
        Returns:
            ジョブデータ または None
        """
        try:
            response = self.client.table('jobs').select('*').eq('job_id', job_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    def list_jobs(self, limit: int = 100, status: Optional[str] = None) -> list:
        """
        ジョブ一覧を取得
        
        Args:
            limit: 取得件数
            status: フィルター（ステータス）
        
        Returns:
            ジョブリスト
        """
        try:
            query = self.client.table('jobs').select('*')
            
            if status:
                query = query.eq('status', status)
            
            response = query.order('created_at', desc=True).limit(limit).execute()
            return response.data
        
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

# グローバルインスタンス（シングルトン）
_supabase_helper = None

def get_supabase_helper() -> SupabaseHelper:
    """Supabase ヘルパーのシングルトンインスタンスを取得"""
    global _supabase_helper
    if _supabase_helper is None:
        _supabase_helper = SupabaseHelper()
    return _supabase_helper


