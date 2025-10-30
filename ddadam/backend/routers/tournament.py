# backend/routers/tournament.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
import json
import os
import logging
from datetime import datetime
import traceback
import threading
from supabase_helper import get_supabase_helper

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
    logger.info(f"🚀 run_tournament_job開始: job_id={job_id}, game_id={game_id}")
    logger.info(f"🔍 Thread ID: {threading.current_thread().ident}")
    logger.info(f"🔍 Process ID: {os.getpid()}")
    logger.info(f"🔍 現在時刻: {datetime.now().isoformat()}")
    from worker.integrated_system import IntegratedTournamentSystem
    from config import settings
    supabase = get_supabase_helper()
    
    current_step = "init"
    try:
        # ジョブ開始（Supabase）
        current_step = "queue_to_processing"
        supabase.update_job(job_id, status="processing", progress=0.0, message="大会CSVを取得中...", metadata={"step": current_step})

        # JBAシステム初期化（選手検索用）
        current_step = "init_jba_system"
        from worker.jba_verification_lib import JBAVerificationSystem, DataValidator
        
        jba_system = JBAVerificationSystem()
        validator = DataValidator()
        
        # JBAログイン（選手検索用）
        current_step = "jba_login"
        logger.info("JBAログイン中（選手検索用）...")
        print(f"🔐 JBAログイン試行: {jba_credentials['email']}")
        login_success = jba_system.login(jba_credentials["email"], jba_credentials["password"])
        print(f"🔐 JBAログイン結果: {'成功' if login_success else '失敗'}")
        if not login_success:
            raise Exception("JBAログインに失敗しました（メール/パスワードをご確認ください）")
        
        # システム初期化
        current_step = "init_tournament_system"
        system = IntegratedTournamentSystem(
            jba_system=jba_system,
            validator=validator,
            use_parallel=True,
            max_workers=5
        )
        
        # 管理画面ログインしてCSV取得（環境変数から認証情報を取得）
        current_step = "fetch_tournament_csv"
        supabase.update_job(job_id, message=f"大会ID {game_id} のCSVを取得中...", progress=0.1, metadata={"step": current_step})
        
        logger.info(f"管理画面ログイン: {settings.admin_username}")
        
        combined_df = system.login_and_get_tournament_csvs(
            username=settings.admin_username,  # 管理画面用（環境変数）
            password=settings.admin_password,  # 管理画面用（環境変数）
            game_id=game_id
        )
        
        if combined_df is None or combined_df.empty:
            raise Exception("大会データの取得に失敗しました（CSVリンクが見つからない/アクセス不可）")
        
        # 取得した大学数を記録
        current_step = "csv_parsed"
        universities = combined_df['大学名'].unique().tolist()
        supabase.update_job(job_id, metadata={"universities": universities, "total_universities": len(universities), "total_rows": len(combined_df), "step": current_step})
        
        logger.info(f"✅ 大会データ取得完了: {len(universities)}大学, {len(combined_df)}行")
        
        # JBA照合処理
        current_step = "verification"
        supabase.update_job(job_id, message=f"JBA照合処理中...（{len(universities)}大学）", progress=0.3, metadata={"step": current_step})
        
        result_df = system.process_tournament_data(combined_df)
        
        if result_df is None:
            raise Exception("JBA照合処理に失敗しました（内部処理エラー）")
        
        # PDF生成
        current_step = "pdf_generate"
        supabase.update_job(job_id, message="PDFを生成中...", progress=0.7, metadata={"step": current_step})

        # PDFの保存先（アプリ用の出力ディレクトリに変更）
        from config import settings
        base_output_dir = getattr(settings, 'output_dir', 'outputs')
        output_dir = os.path.join(base_output_dir, "reports")
        os.makedirs(output_dir, exist_ok=True)
        pdf_filename = f"tournament_{game_id}_{job_id[:8]}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)

        # 結果から大学別レポートを作成し、1ファイルに統合してPDF生成
        reports = system.create_university_reports(result_df)
        system.export_all_university_reports_as_pdf(reports, output_path=pdf_path)
        
        logger.info(f"✅ PDF生成完了: {pdf_path}")
        logger.info(f"📁 PDF保存場所: {output_dir}")
        logger.info(f"📄 ファイル名: {pdf_filename}")

        # Supabase Storage にアップロード（ヘルパーにアップロード関数がある場合）
        current_step = "upload"
        public_url = None
        storage_path = f"reports/{pdf_filename}"
        try:
            public_url = supabase.upload_file(pdf_path, storage_path)
        except Exception as upload_err:
            logger.error(f"Upload failed: {upload_err}")
            public_url = None

        # 完了
        current_step = "done"
        supabase.update_job(
            job_id,
            status="done",
            progress=1.0,
            message=f"処理が完了しました（{len(universities)}大学）",
            output_path=public_url,
            metadata={"step": current_step, "storage_path": storage_path}
        )
        logger.info(f"✅ 大会ジョブ完了: {job_id}")
        
    except Exception as e:
        logger.error(f"❌ 大会ジョブエラー: {str(e)}", exc_info=True)
        import traceback
        error_traceback = traceback.format_exc()
        supabase.update_job(
            job_id,
            status="error",
            progress=0.0,
            message=f"エラー: {str(e)}",
            error=str(e),
            error_detail=error_traceback,
            metadata={"step": current_step}
        )


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

        # Supabase にジョブを作成（queued）
        supabase = get_supabase_helper()
        created = supabase.create_job(
            job_id=job_id,
            job_type="tournament",
            metadata={
                "game_id": req.game_id,
                "jba_credentials": req.jba_credentials,
                "generate_pdf": req.generate_pdf,
            },
        )

        if not created:
            raise HTTPException(status_code=500, detail="ジョブの作成に失敗しました")

        logger.info(f"✅ Supabaseにジョブを作成: {job_id} - 大会ID: {req.game_id}")
        
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



