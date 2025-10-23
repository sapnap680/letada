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
    
    # 処理開始ボタン
    if st.sidebar.button("🚀 処理開始", type="primary"):
        try:
            st.info("🔄 システムを初期化中...")
            
            # システム初期化
            jba_system = JBAVerificationSystem()
            validator = DataValidator()
            
            st.success("✅ システム初期化完了")
            
            # 統合システムの処理
            st.info("📝 統合システムを実行中...")
            st.write(f"ログインID: {username}")
            st.write(f"パスワード: {'*' * len(password)}")
            st.write(f"大会ID: {game_id}")
            
            # 統合システムのインポートと実行
            from integrated_system import IntegratedTournamentSystem
            
            integrated_system = IntegratedTournamentSystem(jba_system, validator)
            
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
