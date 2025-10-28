# backend/routers/jobs.py
"""
ジョブステータス管理API
フロントエンドからポーリングで進捗を取得
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class JobStatus(BaseModel):
    """ジョブステータスレスポンス"""
    job_id: str
    status: str  # "queued", "processing", "done", "error"
    progress: float  # 0.0 ~ 1.0
    message: str
    output_path: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    ジョブの進捗・完了状態を取得
    
    フロントエンドは2秒ごとにポーリングして進捗を表示
    TODO: 将来的にSSE/WebSocketで置き換え
    """
    job_file = f"temp_results/job_{job_id}.json"
    
    if not os.path.exists(job_file):
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    try:
        with open(job_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        return JobStatus(
            job_id=job_id,
            status=meta.get("status", "unknown"),
            progress=meta.get("progress", 0.0),
            message=meta.get("message", ""),
            output_path=meta.get("output_path"),
            error=meta.get("error"),
            created_at=meta.get("created_at"),
            updated_at=meta.get("updated_at"),
            metadata=meta.get("metadata", {})
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse job meta: {e}")
        raise HTTPException(status_code=500, detail="Invalid job metadata")
    except Exception as e:
        logger.error(f"Error reading job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """
    ジョブメタデータを削除（クリーンアップ用）
    """
    job_file = f"temp_results/job_{job_id}.json"
    
    if not os.path.exists(job_file):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    try:
        os.remove(job_file)
        logger.info(f"Deleted job {job_id}")
        return {"status": "deleted", "job_id": job_id}
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_jobs():
    """
    全ジョブの一覧を取得
    """
    try:
        job_files = [f for f in os.listdir("temp_results") if f.startswith("job_") and f.endswith(".json")]
        jobs = []
        
        for job_file in job_files:
            job_id = job_file.replace("job_", "").replace(".json", "")
            with open(f"temp_results/{job_file}", "r", encoding="utf-8") as f:
                meta = json.load(f)
                jobs.append({
                    "job_id": job_id,
                    "status": meta.get("status", "unknown"),
                    "progress": meta.get("progress", 0.0),
                    "created_at": meta.get("created_at")
                })
        
        return {"jobs": jobs, "total": len(jobs)}
    
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

