# backend/routers/verify.py
"""
JBA照合API
大学リストを受け取り、バックグラウンドで照合処理を実行
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging
import uuid
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# TODO: 既存の integrated_system.py を import
# from worker.integrated_system import IntegratedTournamentSystem

class JBACredentials(BaseModel):
    """JBA認証情報"""
    email: str
    password: str

class VerifyRequest(BaseModel):
    """照合リクエスト"""
    universities: List[str]
    jba_credentials: Optional[JBACredentials] = None
    parallel_workers: int = 5

class VerifyResponse(BaseModel):
    """照合レスポンス"""
    job_id: str
    status: str
    message: str
    polling_url: str

def run_verification_job(job_id: str, universities: List[str], credentials: Optional[Dict] = None, workers: int = 5):
    """
    バックグラウンドで照合処理を実行
    
    NOTE: この機能は未実装です。大会ID処理（/tournament）を使用してください。
    """
    from supabase_helper import get_supabase_helper
    supabase = get_supabase_helper()
    
    try:
        supabase.update_job(job_id, status="error", message="この機能は未実装です。大会ID処理（/tournament）を使用してください。")
        logger.warning(f"Verification job {job_id} attempted but not implemented")
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)

@router.post("/", response_model=VerifyResponse)
async def verify_universities(req: VerifyRequest, background_tasks: BackgroundTasks):
    """
    大学リストの照合ジョブを開始
    
    NOTE: 現在は BackgroundTasks を使用しているが、
    将来的には Redis + RQ/Celery に置き換える
    """
    job_id = str(uuid.uuid4())
    
    logger.info(f"Starting verification job {job_id} for {len(req.universities)} universities")
    
    # バックグラウンドタスクとして実行
    credentials = req.jba_credentials.dict() if req.jba_credentials else None
    background_tasks.add_task(
        run_verification_job,
        job_id=job_id,
        universities=req.universities,
        credentials=credentials,
        workers=req.parallel_workers
    )
    
    return VerifyResponse(
        job_id=job_id,
        status="queued",
        message=f"{len(req.universities)}大学の照合ジョブを開始しました",
        polling_url=f"/jobs/{job_id}"
    )


