# backend/routers/tournament.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
import json
import os
import logging

router = APIRouter(tags=["tournament"])
logger = logging.getLogger(__name__)

class TournamentRequest(BaseModel):
    game_id: str  # 大会ID
    jba_credentials: Dict  # {"email": "...", "password": "..."}
    generate_pdf: bool = True  # PDF生成するか

class TournamentResponse(BaseModel):
    status: str
    job_id: str
    message: str
    polling_url: str

def run_tournament_job(
    job_id: str,
    game_id: str,
    credentials: Dict,
    generate_pdf: bool = True
):
    """大会IDからCSVを取得してJBA照合を実行するバックグラウンドジョブ"""
    from worker.integrated_system import IntegratedTournamentSystem
    
    job_file = f"temp_results/job_{job_id}.json"
    os.makedirs("temp_results", exist_ok=True)
    
    try:
        # ジョブ開始
        meta = {
            "job_id": job_id,
            "status": "processing",
            "progress": 0.0,
            "message": "大会CSVを取得中...",
            "game_id": game_id
        }
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # システム初期化
        system = IntegratedTournamentSystem(
            use_parallel=True,
            max_workers=5
        )
        
        # JBAログインしてCSV取得
        meta["message"] = f"大会ID {game_id} のCSVを取得中..."
        meta["progress"] = 0.1
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        combined_df = system.login_and_get_tournament_csvs(
            username=credentials["email"],
            password=credentials["password"],
            game_id=game_id
        )
        
        if combined_df is None or combined_df.empty:
            raise Exception("大会データの取得に失敗しました")
        
        # 取得した大学数を記録
        universities = combined_df['大学名'].unique().tolist()
        meta["universities"] = universities
        meta["total_universities"] = len(universities)
        meta["total_rows"] = len(combined_df)
        
        logger.info(f"✅ 大会データ取得完了: {len(universities)}大学, {len(combined_df)}行")
        
        # JBA照合処理
        meta["message"] = f"JBA照合処理中...（{len(universities)}大学）"
        meta["progress"] = 0.3
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        result_df = system.process_tournament_data(combined_df)
        
        if result_df is None:
            raise Exception("JBA照合処理に失敗しました")
        
        # Excelファイル保存
        meta["message"] = "Excelファイルを生成中..."
        meta["progress"] = 0.7
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        excel_filename = f"tournament_{game_id}_{job_id[:8]}.xlsx"
        excel_path = os.path.join(output_dir, excel_filename)
        
        result_df.to_excel(excel_path, index=False, engine='openpyxl')
        logger.info(f"✅ Excel保存: {excel_path}")
        
        # PDF生成（オプション）
        pdf_filename = None
        if generate_pdf:
            meta["message"] = "PDFを生成中..."
            meta["progress"] = 0.85
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            pdf_filename = f"tournament_{game_id}_{job_id[:8]}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)
            
            # 大学ごとにPDF生成
            system.generate_pdfs_by_university(
                df=result_df,
                output_dir=output_dir,
                filename_prefix=f"tournament_{game_id}"
            )
        
        # 完了
        meta["status"] = "done"
        meta["progress"] = 1.0
        meta["message"] = f"処理が完了しました（{len(universities)}大学）"
        meta["output_excel"] = excel_path
        meta["output_excel_filename"] = excel_filename
        
        if pdf_filename:
            meta["output_pdf"] = pdf_path
            meta["output_pdf_filename"] = pdf_filename
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 大会ジョブ完了: {job_id}")
        
    except Exception as e:
        logger.error(f"❌ 大会ジョブエラー: {str(e)}", exc_info=True)
        
        meta = {
            "job_id": job_id,
            "status": "error",
            "progress": 0.0,
            "message": "エラーが発生しました",
            "error": str(e)
        }
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


@router.post("/", response_model=TournamentResponse)
async def start_tournament_job(
    req: TournamentRequest,
    background_tasks: BackgroundTasks
):
    """
    大会IDからCSVを取得してJBA照合を実行
    
    - **game_id**: 大会ID（例: "12345"）
    - **jba_credentials**: JBAログイン情報
    - **generate_pdf**: PDF生成するか（デフォルト: True）
    """
    try:
        # バリデーション
        if not req.game_id:
            raise HTTPException(status_code=400, detail="大会IDを入力してください")
        
        if not req.jba_credentials or not req.jba_credentials.get("email") or not req.jba_credentials.get("password"):
            raise HTTPException(status_code=400, detail="JBAログイン情報を入力してください")
        
        # ジョブID生成
        job_id = str(uuid.uuid4())
        
        # バックグラウンドジョブを開始
        background_tasks.add_task(
            run_tournament_job,
            job_id=job_id,
            game_id=req.game_id,
            credentials=req.jba_credentials,
            generate_pdf=req.generate_pdf
        )
        
        logger.info(f"🏀 大会ジョブ開始: {job_id} - 大会ID: {req.game_id}")
        
        return TournamentResponse(
            status="queued",
            job_id=job_id,
            message=f"大会ID {req.game_id} の処理を開始しました",
            polling_url=f"/jobs/{job_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"大会ジョブ開始エラー: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/{game_id}")
async def get_tournament_info(game_id: str):
    """
    大会IDの情報を取得（CSVリンク数など）
    
    注: この機能は将来的な拡張用
    """
    # TODO: JBAにログインせずに大会情報を取得する機能を実装
    return {
        "game_id": game_id,
        "message": "この機能は現在開発中です。/tournament エンドポイントを使用してください。"
    }

