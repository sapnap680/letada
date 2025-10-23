import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import time
from urllib.parse import urljoin
from datetime import datetime
import json

# JBA検証システムのインポート
from jba_verification_lib import JBAVerificationSystem, FastCSVCorrectionSystem, DataValidator

def main():
    """メイン処理"""
    st.title("🏀 大会統合システム")
    st.markdown("---")
    
    # サイドバーで設定
    st.sidebar.header("⚙️ 設定")
    
    # ログイン情報
    st.sidebar.subheader("🔐 ログイン情報")
    username = st.sidebar.text_input("ログインID", value="kcbf")
    password = st.sidebar.text_input("パスワード", value="sakura272", type="password")
    
    # 大会ID
    st.sidebar.subheader("🏀 大会設定")
    game_id = st.sidebar.number_input("大会ID", value=76, min_value=1)
    
    # 並列処理設定
    st.sidebar.subheader("⚡ 並列処理設定")
    max_workers = st.sidebar.slider("並列スレッド数", min_value=1, max_value=50, value=20, help="スレッド数を増やすと高速化されますが、サーバー負荷が高くなります")
    use_parallel = st.sidebar.checkbox("並列処理を使用", value=True, help="チェックを外すと従来の順次処理になります")
    
    
    # JBAログイン情報
    st.sidebar.subheader("🔐 JBAログイン情報")
    jba_email = st.sidebar.text_input("JBAメールアドレス", value="")
    jba_password = st.sidebar.text_input("JBAパスワード", value="", type="password")
    
    # JBAログインボタン
    if st.sidebar.button("🔐 JBAにログイン", type="secondary"):
        if jba_email and jba_password:
            try:
                jba_system = JBAVerificationSystem()
                if jba_system.login(jba_email, jba_password):
                    st.session_state.jba_logged_in = True
                    st.session_state.jba_system = jba_system
                    # JBAログイン成功
                else:
                    # JBAログイン失敗
            except Exception as e:
                # JBAログインエラー
        else:
            # JBAログイン情報を入力してください
    
    # 処理開始ボタン
    if st.sidebar.button("🚀 処理開始", type="primary"):
        try:
            # JBAログイン状態をチェック
            if not st.session_state.get('jba_logged_in', False):
                # 先にJBAにログインしてください
                return
            
            # システムを初期化中
            
            # システム初期化
            jba_system = st.session_state.jba_system
            validator = DataValidator()
            
            # システム初期化完了
            
            # 統合システムの処理
            # 統合システムを実行中
            
            # 設定情報をコンパクトに表示
            with st.expander("⚙️ 実行設定", expanded=False):
                st.write(f"ログインID: {username}")
                st.write(f"パスワード: {'*' * len(password)}")
                st.write(f"大会ID: {game_id}")
                st.write(f"並列処理: {'ON' if use_parallel else 'OFF'}")
                st.write(f"スレッド数: {max_workers}")
            
            # 統合システムのインポートと実行
            from integrated_system import IntegratedTournamentSystem
            
            # 並列処理設定を渡す
            integrated_system = IntegratedTournamentSystem(jba_system, validator, max_workers=max_workers, use_parallel=use_parallel)
            
            # ステップ1: CSV取得
            st.header("📥 ステップ1: 大会CSV取得")
            df = integrated_system.login_and_get_tournament_csvs(username, password, game_id)
            
            if df is not None:
                # データを取得しました
                
                # ステップ2: JBA照合
                st.header("🔍 ステップ2: JBA照合処理")
                results = integrated_system.process_tournament_data(df)
                
                if results:
                    # 照合が完了しました
                    
                    # ステップ3: レポート作成
                    st.header("📊 ステップ3: 大学別レポート")
                    reports = integrated_system.create_university_reports(results)
                    
                    if reports:
                        # 大学のレポートを作成しました
                        
                        # 大学選択
                        selected_univ = st.selectbox(
                            "レポートを表示する大学を選択してください:",
                            list(reports.keys())
                        )
                        
                        if selected_univ:
                            integrated_system.display_university_report(selected_univ, reports[selected_univ], game_id, reports)
                            
                            # PDF出力ボタン
                            st.subheader("🖨️ PDF出力")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("📄 選択大学のPDFを生成"):
                                    try:
                                        pdf_path = integrated_system.export_single_university_report_as_pdf(selected_univ, reports[selected_univ])
                                        with open(pdf_path, "rb") as f:
                                            st.download_button(
                                                label="📄 PDFをダウンロード",
                                                data=f.read(),
                                                file_name=f"{selected_univ}_選手データ.pdf",
                                                mime="application/pdf"
                                            )
                                    except Exception as e:
                                        # PDF生成エラー
                            
                            with col2:
                                # 全大学PDF生成（非同期）
                                st.subheader("🖨️ 全大学PDF（非同期）")
                                if st.button("📚 全大学PDFを生成（バックグラウンド）", type="primary"):
                                    try:
                                        # ジョブを開始して job_meta_path を返す
                                        job_meta_path = integrated_system.start_pdf_generation_background(
                                            reports,
                                            output_filename=os.path.join(integrated_system.temp_dir, f"大会ID{game_id}_全大学選手データ.zip")
                                        )
                                        st.session_state['pdf_job_meta'] = job_meta_path
                                        # PDF生成ジョブを開始しました
                                    except Exception as e:
                                        # PDF生成ジョブ開始エラー

                                # 進捗表示・ダウンロード
                                job_meta_path = st.session_state.get('pdf_job_meta')
                                if job_meta_path and os.path.exists(job_meta_path):
                                    try:
                                        with open(job_meta_path, "r", encoding="utf-8") as f:
                                            meta = json.load(f)
                                        status = meta.get("status", "unknown")
                                        progress = meta.get("progress", 0.0)
                                        message = meta.get("message", "")
                                        output_path = meta.get("output_path")
                                        error = meta.get("error")

                                        st.info(f"ジョブ: {meta.get('job_id')} 状態: {status} 進捗: {progress*100:.1f}%")
                                        st.progress(progress)

                                        if status == "done" and output_path and os.path.exists(output_path):
                                            with open(output_path, "rb") as pdf_file:
                                                st.download_button(
                                                    label="📚 完了したZIPファイルをダウンロード",
                                                    data=pdf_file.read(),
                                                    file_name=os.path.basename(output_path),
                                                    mime="application/zip"
                                                )
                                        elif status == "error":
                                            # PDF生成エラー
                                            if error:
                                                st.text(error)
                                        else:
                                            # 更新用ボタン（手動で最新状態に）
                                            if st.button("🔁 更新"):
                                                st.rerun()
                                    except Exception as e:
                                        # ジョブメタの読み込みに失敗しました
                    else:
                        # レポートの作成に失敗しました
                else:
                    # JBA照合処理に失敗しました
            else:
                # CSV取得に失敗しました
            
        except Exception as e:
            # エラーが発生しました
            st.write("詳細なエラー情報:")
            st.code(str(e))

if __name__ == "__main__":
    main()
