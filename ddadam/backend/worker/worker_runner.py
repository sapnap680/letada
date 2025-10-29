#!/usr/bin/env python3
"""
Render Background Worker ランナー

ジョブキューを監視し、PDF生成タスクを実行する
Upstash Redis をジョブキューとして使用
"""

import sys
import os
import time
import logging
import json
from datetime import datetime

# backend ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from supabase_helper import get_supabase_helper
from cache_adapter import get_cache

# ログ設定
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JobWorker:
    """ジョブワーカー（Background Worker）"""
    
    def __init__(self):
        self.supabase = get_supabase_helper()
        self.cache = get_cache()
        self.running = True
        self.poll_interval = int(os.getenv('WORKER_POLL_INTERVAL', '5'))
        logger.info(f"Worker initialized (poll interval: {self.poll_interval}s)")
    
    def get_pending_jobs(self):
        """
        実行待ちのジョブを取得
        
        Returns:
            list: ジョブリスト
        """
        try:
            # Supabase から status='queued' のジョブを取得
            jobs = self.supabase.list_jobs(limit=10, status='queued')
            return jobs
        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            return []
    
    def process_job(self, job):
        """
        ジョブを処理
        
        Args:
            job: ジョブデータ
        """
        job_id = job['job_id']
        job_type = job.get('job_type', 'unknown')
        
        logger.info(f"Processing job {job_id} (type: {job_type})")
        
        try:
            # ステータスを running に更新
            self.supabase.update_job(
                job_id,
                status='running',
                message=f'{job_type} 処理を開始しました'
            )
            
            # ジョブタイプに応じて処理を分岐
            if job_type == 'pdf_generation':
                self.process_pdf_job(job)
            elif job_type == 'verification':
                self.process_verification_job(job)
            elif job_type == 'tournament':
                self.process_tournament_job(job)
            else:
                logger.warning(f"Unknown job type: {job_type}")
                self.supabase.update_job(
                    job_id,
                    status='error',
                    error=f'Unknown job type: {job_type}'
                )
        
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            
            # エラー情報を保存
            self.supabase.update_job(
                job_id,
                status='error',
                error=str(e)
            )
    
    def process_pdf_job(self, job):
        """
        PDF生成ジョブを処理
        
        Args:
            job: ジョブデータ
        """
        job_id = job['job_id']
        metadata = job.get('metadata', {})
        universities = metadata.get('universities', [])
        
        logger.info(f"Generating PDF for {len(universities)} universities")
        
        # TODO: 実際の PDF 生成処理を実装
        # from integrated_system_worker import generate_pdfs_background
        
        try:
            # 仮の処理（実際には integrated_system_worker.py を使用）
            total = len(universities)
            
            for i, univ in enumerate(universities):
                # 進捗更新
                progress = (i + 1) / total
                self.supabase.update_job(
                    job_id,
                    progress=progress,
                    message=f'{univ} を処理中... ({i+1}/{total})'
                )
                
                logger.info(f"Processing university {i+1}/{total}: {univ}")
                
                # 実際の処理（仮）
                time.sleep(2)
            
            # 完了
            # TODO: Supabase Storage にアップロード
            output_path = f"reports/output_{job_id}.pdf"
            
            self.supabase.update_job(
                job_id,
                status='done',
                progress=1.0,
                message=f'PDF生成完了: {total}大学',
                output_path=output_path
            )
            
            logger.info(f"Job {job_id} completed successfully")
        
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            raise
    
    def process_verification_job(self, job):
        """
        JBA照合ジョブを処理
        
        Args:
            job: ジョブデータ
        """
        job_id = job['job_id']
        metadata = job.get('metadata', {})
        universities = metadata.get('universities', [])
        
        logger.info(f"Verifying {len(universities)} universities")
        
        # TODO: 実際の照合処理を実装
        # from integrated_system import IntegratedTournamentSystem
        
        try:
            total = len(universities)
            
            for i, univ in enumerate(universities):
                # 進捗更新
                progress = (i + 1) / total
                self.supabase.update_job(
                    job_id,
                    progress=progress,
                    message=f'{univ} を照合中... ({i+1}/{total})'
                )
                
                logger.info(f"Verifying university {i+1}/{total}: {univ}")
                
                # 実際の処理（仮）
                time.sleep(1)
            
            # 完了
            self.supabase.update_job(
                job_id,
                status='done',
                progress=1.0,
                message=f'照合完了: {total}大学'
            )
            
            logger.info(f"Job {job_id} completed successfully")
        
        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            raise

    def process_tournament_job(self, job):
        """
        大会IDジョブを処理（CSV取得→照合→PDF）
        """
        job_id = job['job_id']
        metadata = job.get('metadata', {})
        game_id = metadata.get('game_id')
        jba_credentials = metadata.get('jba_credentials')
        generate_pdf = metadata.get('generate_pdf', True)

        if not game_id or not jba_credentials:
            raise ValueError("Job metadata missing required fields (game_id, jba_credentials)")

        try:
            # 実処理は tournament ルーターのランナーを使用
            from routers.tournament import run_tournament_job as tournament_runner
            tournament_runner(job_id, game_id, jba_credentials, generate_pdf)
            # 上記内で Supabase のステータス更新（done/error）まで実施
        except Exception as e:
            logger.error(f"Tournament job failed: {e}", exc_info=True)
            # フェイルセーフでエラーを書き戻す
            self.supabase.update_job(
                job_id,
                status='error',
                error=str(e)
            )
            raise
    
    def run(self):
        """ワーカーのメインループ"""
        logger.info("🚀 Worker started")
        
        try:
            while self.running:
                # 実行待ちのジョブを取得
                jobs = self.get_pending_jobs()
                
                if jobs:
                    logger.info(f"Found {len(jobs)} pending job(s)")
                    
                    for job in jobs:
                        self.process_job(job)
                else:
                    # ジョブがない場合は待機
                    logger.debug(f"No pending jobs. Sleeping for {self.poll_interval}s...")
                
                # 次のポーリングまで待機
                time.sleep(self.poll_interval)
        
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker crashed: {e}", exc_info=True)
            raise
        finally:
            logger.info("Worker shutdown")

def main():
    """メイン関数"""
    logger.info("=" * 60)
    logger.info("JBA Background Worker")
    logger.info("=" * 60)
    logger.info(f"Environment: {os.getenv('RENDER', 'local')}")
    logger.info(f"Worker mode: {os.getenv('WORKER_MODE', 'false')}")
    logger.info(f"Supabase URL: {settings.supabase_url[:30]}...")
    logger.info(f"Redis URL: {settings.redis_url[:30] if settings.redis_url else 'None'}...")
    logger.info("=" * 60)
    
    # 出力ディレクトリを作成
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.job_meta_dir, exist_ok=True)
    
    # ワーカー起動
    worker = JobWorker()
    worker.run()

if __name__ == "__main__":
    main()


