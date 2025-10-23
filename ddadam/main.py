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
    
    # パフォーマンス設定
    st.sidebar.subheader("🚀 パフォーマンス設定")
    enable_caching = st.sidebar.checkbox("キャッシュを有効化", value=True, help="同じデータの再取得を避けて高速化")
    request_delay = st.sidebar.slider("リクエスト間隔(秒)", min_value=0.0, max_value=2.0, value=0.1, step=0.1, help="サーバー負荷軽減のための間隔")
    show_performance = st.sidebar.checkbox("パフォーマンス統計を表示", value=True, help="詳細な処理統計を表示")
    
    if st.sidebar.button("🗑️ キャッシュをクリア", help="キャッシュをクリアして最新データを取得"):
        st.sidebar.success("✅ キャッシュをクリアしました")
    
    if st.sidebar.button("🗑️ 一時保存をクリア", help="一時保存ファイルをクリア"):
        st.sidebar.success("✅ 一時保存をクリアしました")
    
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
                    st.success("✅ JBAログイン成功")
                else:
                    st.error("❌ JBAログイン失敗")
            except Exception as e:
                st.error(f"❌ JBAログインエラー: {str(e)}")
        else:
            st.error("❌ JBAログイン情報を入力してください")
    
    # 処理開始ボタン
    if st.sidebar.button("🚀 処理開始", type="primary"):
        try:
            # JBAログイン状態をチェック
            if not st.session_state.get('jba_logged_in', False):
                st.error("❌ 先にJBAにログインしてください")
                return
            
            st.info("🔄 システムを初期化中...")
            
            # システム初期化
            jba_system = st.session_state.jba_system
            validator = DataValidator()
            
            st.success("✅ システム初期化完了")
            
            # 統合システムの処理
            st.info("📝 統合システムを実行中...")
            
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
                st.success(f"✅ {len(df)} 件のデータを取得しました")
                
                # ステップ2: JBA照合
                st.header("🔍 ステップ2: JBA照合処理")
                results = integrated_system.process_tournament_data(df)
                
                if results:
                    st.success(f"✅ {len(results)} 件の照合が完了しました")
                    
                    # ステップ3: レポート作成
                    st.header("📊 ステップ3: 大学別レポート")
                    reports = integrated_system.create_university_reports(results)
                    
                    if reports:
                        st.success(f"✅ {len(reports)} 大学のレポートを作成しました")
                        
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
                                        st.error(f"❌ PDF生成エラー: {str(e)}")
                            
                            with col2:
                                if st.button("📚 全大学PDFを生成", type="primary"):
                                    try:
                                        pdf_path = integrated_system.export_all_university_reports_as_pdf(reports)
                                        with open(pdf_path, "rb") as f:
                                            st.download_button(
                                                label="📚 全大学PDFをダウンロード",
                                                data=f.read(),
                                                file_name=f"大会ID{game_id}_全大学選手データ.pdf",
                                                mime="application/pdf"
                                            )
                                    except Exception as e:
                                        st.error(f"❌ PDF生成エラー: {str(e)}")
                    else:
                        st.error("❌ レポートの作成に失敗しました")
                else:
                    st.error("❌ JBA照合処理に失敗しました")
            else:
                st.error("❌ CSV取得に失敗しました")
            
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
            st.write("詳細なエラー情報:")
            st.code(str(e))

if __name__ == "__main__":
    main()
