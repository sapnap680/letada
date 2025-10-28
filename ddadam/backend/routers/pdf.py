# backend/routers/pdf.py
"""
PDF生成API
大学リストからメンバー表PDFを生成
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import logging
import uuid
import json
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# TODO: 既存の integrated_system_worker.py を import
# from worker.integrated_system_worker import generate_pdfs_background

class PdfRequest(BaseModel):
    """PDF生成リクエスト"""
    universities: List[str]
    jba_credentials: Optional[Dict] = None
    include_photos: bool = True
    format: str = "A4"  # "A4" or "Letter"

class PdfResponse(BaseModel):
    """PDF生成レスポンス"""
    job_id: str
    status: str
    message: str
    polling_url: str

def run_pdf_generation_job(job_id: str, universities: List[str], credentials: Optional[Dict] = None, options: Dict = None):
    """
    バックグラウンドでPDF生成処理を実行
    
    TODO: 既存の integrated_system_worker.py の処理をここに移植
    - st.* を logging に置き換え
    - 進捗を job_meta に書き込み
    - 生成したPDFのパスを output_path に設定
    """
    job_file = f"temp_results/job_{job_id}.json"
    
    try:
        # ジョブメタ初期化
        meta = {
            "job_id": job_id,
            "status": "processing",
            "progress": 0.0,
            "message": "PDF生成を開始しました",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": {
                "universities": universities,
                "total_count": len(universities),
                "options": options or {}
            }
        }
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # TODO: 既存のPDF生成処理を実行
        # from worker.integrated_system_worker import generate_pdfs_background
        # result = generate_pdfs_background(universities, credentials, job_id=job_id)
        
        # 仮の処理（実際には integrated_system_worker.py の処理を移植）
        import time
        output_files = []
        
        for i, univ in enumerate(universities):
            time.sleep(2)  # 仮のPDF生成時間
            
            progress = (i + 1) / len(universities)
            meta["progress"] = progress
            meta["message"] = f"{univ}のPDFを生成中... ({i+1}/{len(universities)})"
            meta["updated_at"] = datetime.now().isoformat()
            
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            # 仮のPDFファイルパス
            pdf_path = f"outputs/{univ}_members_{job_id}.pdf"
            output_files.append(pdf_path)
            
            logger.info(f"Job {job_id}: Generated PDF for {univ} ({progress*100:.1f}%)")
        
        # ZIPにまとめる（複数大学の場合）
        if len(universities) > 1:
            zip_path = f"outputs/members_all_{job_id}.zip"
            # TODO: ZIPファイル作成処理
            final_output = zip_path
        else:
            final_output = output_files[0] if output_files else None
        
        # 完了
        meta["status"] = "done"
        meta["progress"] = 1.0
        meta["message"] = f"PDF生成完了: {len(universities)}大学"
        meta["updated_at"] = datetime.now().isoformat()
        meta["output_path"] = final_output
        meta["metadata"]["output_files"] = output_files
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Job {job_id} completed successfully: {final_output}")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        
        # エラー情報を保存
        meta["status"] = "error"
        meta["error"] = str(e)
        meta["updated_at"] = datetime.now().isoformat()
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

@router.post("/", response_model=PdfResponse)
async def generate_pdf(req: PdfRequest, background_tasks: BackgroundTasks):
    """
    PDF生成ジョブを開始
    
    NOTE: 現在は BackgroundTasks を使用しているが、
    将来的には Redis + RQ/Celery に置き換える
    """
    job_id = str(uuid.uuid4())
    
    logger.info(f"Starting PDF generation job {job_id} for {len(req.universities)} universities")
    
    # バックグラウンドタスクとして実行
    options = {
        "include_photos": req.include_photos,
        "format": req.format
    }
    
    background_tasks.add_task(
        run_pdf_generation_job,
        job_id=job_id,
        universities=req.universities,
        credentials=req.jba_credentials,
        options=options
    )
    
    return PdfResponse(
        job_id=job_id,
        status="queued",
        message=f"{len(req.universities)}大学のPDF生成ジョブを開始しました",
        polling_url=f"/jobs/{job_id}"
    )

@router.get("/download/{filename}")
async def download_pdf(filename: str):
    """
    生成したPDFをダウンロード
    
    セキュリティ: ファイル名のバリデーションを実装
    """
    # パストラバーサル対策
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    path = os.path.join("outputs", filename)
    
    if not os.path.exists(path):
        logger.warning(f"File not found: {path}")
        raise HTTPException(status_code=404, detail="File not found")
    
    # ファイルタイプの判定
    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".zip"):
        media_type = "application/zip"
    else:
        media_type = "application/octet-stream"
    
    logger.info(f"Downloading file: {filename}")
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename
    )

@router.get("/list")
async def list_pdfs():
    """
    生成済みPDFの一覧を取得
    """
    try:
        if not os.path.exists("outputs"):
            return {"files": [], "total": 0}
        
        files = []
        for filename in os.listdir("outputs"):
            if filename.endswith((".pdf", ".zip")):
                path = os.path.join("outputs", filename)
                size = os.path.getsize(path)
                files.append({
                    "filename": filename,
                    "size_bytes": size,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "download_url": f"/pdf/download/{filename}"
                })
        
        return {"files": files, "total": len(files)}
    
    except Exception as e:
        logger.error(f"Failed to list PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

