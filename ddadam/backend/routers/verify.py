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
    
    TODO: 既存の integrated_system.py の処理をここに移植
    - st.* を logging に置き換え
    - 進捗を job_meta に書き込み
    """
    job_file = f"temp_results/job_{job_id}.json"
    
    try:
        # ジョブメタ初期化
        meta = {
            "job_id": job_id,
            "status": "processing",
            "progress": 0.0,
            "message": "照合処理を開始しました",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": {
                "universities": universities,
                "total_count": len(universities)
            }
        }
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # TODO: 既存の照合処理を実行
        # system = IntegratedTournamentSystem(max_workers=workers)
        # system.login(credentials["email"], credentials["password"])
        # results = system.process_universities(universities, job_id=job_id)
        
        # 仮の処理（実際には integrated_system.py の処理を移植）
        import time
        for i, univ in enumerate(universities):
            time.sleep(1)  # 仮の処理時間
            
            progress = (i + 1) / len(universities)
            meta["progress"] = progress
            meta["message"] = f"{univ}を処理中... ({i+1}/{len(universities)})"
            meta["updated_at"] = datetime.now().isoformat()
            
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Job {job_id}: Processed {univ} ({progress*100:.1f}%)")
        
        # 完了
        meta["status"] = "done"
        meta["progress"] = 1.0
        meta["message"] = f"照合完了: {len(universities)}大学"
        meta["updated_at"] = datetime.now().isoformat()
        meta["output_path"] = f"outputs/verification_{job_id}.json"
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        
        # エラー情報を保存
        meta["status"] = "error"
        meta["error"] = str(e)
        meta["updated_at"] = datetime.now().isoformat()
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

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

