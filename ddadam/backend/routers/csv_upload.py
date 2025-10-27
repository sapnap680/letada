# backend/routers/csv_upload.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import pandas as pd
import uuid
import json
import os
import logging
from io import StringIO

router = APIRouter(tags=["csv"])
logger = logging.getLogger(__name__)

class CsvVerifyRequest(BaseModel):
    university_name: str
    jba_credentials: Optional[Dict] = None
    threshold: float = 0.8
    max_workers: int = 5

class CsvVerifyResponse(BaseModel):
    status: str
    job_id: str
    message: str
    polling_url: str

def run_csv_verification_job(
    job_id: str,
    df: pd.DataFrame,
    university_name: str,
    credentials: Optional[Dict] = None,
    threshold: float = 0.8,
    max_workers: int = 5
):
    """CSVファイルを処理するバックグラウンドジョブ"""
    from worker.jba_verification_lib import JBAVerificationSystem, FastCSVCorrectionSystem
    
    job_file = f"temp_results/job_{job_id}.json"
    os.makedirs("temp_results", exist_ok=True)
    
    try:
        # ジョブ開始
        meta = {
            "job_id": job_id,
            "status": "processing",
            "progress": 0.0,
            "message": "CSVファイルを処理中...",
            "university": university_name,
            "rows": len(df)
        }
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # JBAシステム初期化
        jba_system = JBAVerificationSystem()
        
        # ログイン
        if credentials:
            meta["message"] = "JBAにログイン中..."
            meta["progress"] = 0.1
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            jba_system.login(credentials["email"], credentials["password"])
        
        # CSV処理システム初期化
        meta["message"] = "CSV処理システムを初期化中..."
        meta["progress"] = 0.2
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        csv_system = FastCSVCorrectionSystem(
            jba_system=jba_system,
            max_workers=max_workers
        )
        
        # CSV処理
        meta["message"] = f"選手データを照合中...（{len(df)}行）"
        meta["progress"] = 0.3
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        results = csv_system.process_csv_file_parallel(
            df=df,
            university_name=university_name,
            threshold=threshold
        )
        
        # Excelファイル生成
        meta["message"] = "Excelファイルを生成中..."
        meta["progress"] = 0.8
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        excel_buffer = csv_system.create_colored_excel(df, results)
        
        # ファイル保存
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{university_name}_verified_{job_id[:8]}.xlsx"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, "wb") as f:
            f.write(excel_buffer.getvalue())
        
        # 完了
        meta["status"] = "done"
        meta["progress"] = 1.0
        meta["message"] = "処理が完了しました"
        meta["output_path"] = output_path
        meta["output_filename"] = output_filename
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ CSVジョブ完了: {job_id}")
        
    except Exception as e:
        logger.error(f"❌ CSVジョブエラー: {str(e)}", exc_info=True)
        
        meta = {
            "job_id": job_id,
            "status": "error",
            "progress": 0.0,
            "message": "エラーが発生しました",
            "error": str(e)
        }
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


@router.post("/upload", response_model=CsvVerifyResponse)
async def upload_csv(
    file: UploadFile = File(...),
    university_name: str = None,
    background_tasks: BackgroundTasks = None
):
    """
    CSVファイルをアップロードしてJBA照合を開始
    
    - **file**: CSVファイル（UTF-8またはShift_JIS）
    - **university_name**: 大学名（省略可能）
    """
    try:
        # ファイルタイプチェック
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="CSVファイルのみアップロード可能です"
            )
        
        # CSVファイルを読み込み
        content = await file.read()
        
        # エンコーディングを試行
        df = None
        encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig']
        
        for encoding in encodings:
            try:
                text = content.decode(encoding)
                df = pd.read_csv(StringIO(text))
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        
        if df is None:
            raise HTTPException(
                status_code=400,
                detail="CSVファイルの読み込みに失敗しました。UTF-8またはShift_JISで保存してください。"
            )
        
        # 大学名が指定されていない場合はファイル名から取得
        if not university_name:
            university_name = file.filename.replace('.csv', '').replace('_', ' ')
        
        # ジョブID生成
        job_id = str(uuid.uuid4())
        
        # バックグラウンドジョブを開始
        background_tasks.add_task(
            run_csv_verification_job,
            job_id=job_id,
            df=df,
            university_name=university_name,
            threshold=0.8,
            max_workers=5
        )
        
        logger.info(f"📊 CSVジョブ開始: {job_id} - {university_name} ({len(df)}行)")
        
        return CsvVerifyResponse(
            status="queued",
            job_id=job_id,
            message=f"CSVファイルの処理を開始しました（{len(df)}行）",
            polling_url=f"/jobs/{job_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSVアップロードエラー: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_excel(filename: str):
    """処理済みExcelファイルをダウンロード"""
    from fastapi.responses import FileResponse
    
    file_path = os.path.join("outputs", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

