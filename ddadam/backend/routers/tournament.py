# backend/routers/tournament.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
import json
import os
import logging
from datetime import datetime

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
    jba_credentials: Dict,
    generate_pdf: bool = True
):
    """大会IDからCSVを取得してJBA照合を実行するバックグラウンドジョブ"""
    logger.info(f"🚀 BackgroundTask開始: job_id={job_id}, game_id={game_id}")
    
    from worker.integrated_system import IntegratedTournamentSystem
    from config import settings
    
    job_file = f"temp_results/job_{job_id}.json"
    
    # ジョブファイルを読み込み（エンドポイント内で既に作成済み）
    try:
        with open(job_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        logger.info(f"✅ 既存ジョブファイル読み込み: {job_file}")
    except Exception as e:
        logger.error(f"❌ ジョブファイル読み込み失敗: {e}")
        # フォールバック: 新規作成
        meta = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "message": "ジョブを開始しています...",
            "game_id": game_id
        }
    
    try:
        # ジョブ開始
        meta["status"] = "processing"
        meta["message"] = "大会CSVを取得中..."
        meta["updated_at"] = datetime.now().isoformat()
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # JBAシステム初期化（選手検索用）
        from worker.jba_verification_lib import JBAVerificationSystem, DataValidator
        
        jba_system = JBAVerificationSystem()
        validator = DataValidator()
        
        # JBAログイン（選手検索用）
        logger.info("JBAログイン中（選手検索用）...")
        if not jba_system.login(jba_credentials["email"], jba_credentials["password"]):
            raise Exception("JBAログインに失敗しました")
        
        # システム初期化
        system = IntegratedTournamentSystem(
            jba_system=jba_system,
            validator=validator,
            use_parallel=True,
            max_workers=5
        )
        
        # 管理画面ログインしてCSV取得（環境変数から認証情報を取得）
        meta["message"] = f"大会ID {game_id} のCSVを取得中..."
        meta["progress"] = 0.1
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"管理画面ログイン: {settings.admin_username}")
        
        combined_df = system.login_and_get_tournament_csvs(
            username=settings.admin_username,  # 管理画面用（環境変数）
            password=settings.admin_password,  # 管理画面用（環境変数）
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
        
        # PDF生成
        meta["message"] = "PDFを生成中..."
        meta["progress"] = 0.7
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_filename = f"tournament_{game_id}_{job_id[:8]}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # 大学ごとにPDF生成
        system.generate_pdfs_by_university(
            df=result_df,
            output_dir=output_dir,
            filename_prefix=f"tournament_{game_id}"
        )
        
        logger.info(f"✅ PDF生成完了: {pdf_path}")
        
        # 完了
        meta["status"] = "done"
        meta["progress"] = 1.0
        meta["message"] = f"処理が完了しました（{len(universities)}大学）"
        meta["output_path"] = pdf_path
        meta["output_filename"] = pdf_filename
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 大会ジョブ完了: {job_id}")
        
    except Exception as e:
        logger.error(f"❌ 大会ジョブエラー: {str(e)}", exc_info=True)
        
        # エラー詳細を取得
        import traceback
        error_traceback = traceback.format_exc()
        
        meta = {
            "job_id": job_id,
            "status": "error",
            "progress": 0.0,
            "message": "エラーが発生しました",
            "error": str(e),
            "error_detail": error_traceback,
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as write_error:
            logger.error(f"❌ エラーファイル書き込み失敗: {write_error}")


@router.post("/", response_model=TournamentResponse, include_in_schema=True)
@router.post("", response_model=TournamentResponse, include_in_schema=False)  # 末尾スラッシュなしも対応
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
        
        # ジョブファイルを即座に作成（ポーリング開始前に確実に存在させる）
        os.makedirs("temp_results", exist_ok=True)
        job_file = f"temp_results/job_{job_id}.json"
        initial_meta = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "message": "ジョブをキューに追加しました...",
            "game_id": req.game_id,
            "created_at": datetime.now().isoformat()
        }
        
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(initial_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ ジョブファイル作成完了: {job_file}")
        
        # バックグラウンドジョブを開始
        background_tasks.add_task(
            run_tournament_job,
            job_id=job_id,
            game_id=req.game_id,
            jba_credentials=req.jba_credentials,
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

