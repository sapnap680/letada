import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import time
import threading
import argparse
from urllib.parse import urljoin
import getpass
from datetime import datetime
import json
from io import StringIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
import multiprocessing

# 既存のJBA検証システムのインポート
import sys
sys.path.append('.')

# JBA検証システムのインポート
from jba_verification_lib import JBAVerificationSystem, FastCSVCorrectionSystem, DataValidator

class IntegratedTournamentSystem:
    """大会IDからJBA照合まで一括処理する統合システム"""
    
    def __init__(self, jba_system, validator, max_workers=20, use_parallel=True):
        self.jba_system = jba_system
        self.validator = validator
        self.base_url = "https://www.kcbbf.jp"
        self.max_workers = max_workers
        self.use_parallel = use_parallel
        
        # パフォーマンス監視用
        self.performance_stats = {
            'total_time': 0,
            'io_time': 0,
            'processing_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'requests_count': 0,
            'avg_response_time': 0
        }
        
        # キャッシュ用
        self._cache = {}
        self._cache_lock = threading.Lock()
        
        # CPU最適化
        self.cpu_count = multiprocessing.cpu_count()
        self.max_workers = min(self.max_workers, self.cpu_count * 2)
        
        # 一時保存用ディレクトリ
        self.temp_dir = "temp_results"
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    def _truncate_text(self, text, max_chars=30):
        """テキストを指定文字数で切り詰め（PDF軽量化用）"""
        if not isinstance(text, str):
            text = str(text)
        return text if len(text) <= max_chars else text[:max_chars] + "..."
    
    def _get_cached_data(self, key):
        """キャッシュからデータを取得"""
        with self._cache_lock:
            if key in self._cache:
                self.performance_stats['cache_hits'] += 1
                return self._cache[key]
            else:
                self.performance_stats['cache_misses'] += 1
                return None
    
    def _set_cached_data(self, key, value):
        """データをキャッシュに保存"""
        with self._cache_lock:
            self._cache[key] = value
    
    def _clear_cache(self):
        """キャッシュをクリア"""
        with self._cache_lock:
            self._cache.clear()
    
    def _measure_time(self, func, *args, **kwargs):
        """関数の実行時間を測定"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    def _save_temp_results(self, univ_name, results):
        """大学ごとの結果を一時保存"""
        temp_file = os.path.join(self.temp_dir, f"temp_results_{univ_name}.csv")
        try:
            if results:
                df = pd.DataFrame(results)
                df.to_csv(temp_file, index=False, encoding='utf-8-sig')
                st.write(f"💾 {univ_name}: 一時保存完了")
        except Exception as e:
            st.warning(f"⚠️ {univ_name}: 一時保存エラー - {str(e)}")
    
    def _load_temp_results(self, univ_name):
        """大学ごとの結果を一時保存から読み込み"""
        temp_file = os.path.join(self.temp_dir, f"temp_results_{univ_name}.csv")
        if os.path.exists(temp_file):
            try:
                df = pd.read_csv(temp_file, encoding='utf-8-sig')
                st.write(f"📂 {univ_name}: 一時保存から復元")
                return df.to_dict('records')
            except Exception as e:
                st.warning(f"⚠️ {univ_name}: 一時保存読み込みエラー - {str(e)}")
        return None
    
    def _clear_temp_results(self):
        """一時保存ファイルをクリア"""
        try:
            for file in os.listdir(self.temp_dir):
                if file.startswith("temp_results_") and file.endswith(".csv"):
                    os.remove(os.path.join(self.temp_dir, file))
            st.success("🗑️ 一時保存ファイルをクリアしました")
        except Exception as e:
            st.warning(f"⚠️ 一時保存クリアエラー: {str(e)}")
        
    def login_and_get_tournament_csvs(self, username, password, game_id):
        """ログインして大会の全CSVを取得"""
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        try:
            # ログイン処理
            st.info("🔐 ログイン処理中...")
            login_url = f"{self.base_url}/restrict/login"
            login_page = session.get(login_url, timeout=30)
            
            if login_page.status_code != 200:
                st.error("❌ ログインページにアクセスできません")
                return None
            
            soup = BeautifulSoup(login_page.text, "html.parser")
            form = soup.find("form")
            
            if not form:
                st.error("❌ ログインフォームが見つかりません")
                return None
            
            # ログイン実行
            form_action = f"{self.base_url}/master-admin/login"
            login_data = {"uid": username, "pass": password}
            session.headers.update({"Referer": login_url})
            
            login_response = session.post(form_action, data=login_data, timeout=30)
            
            if "login" in login_response.url.lower():
                st.error("❌ ログインに失敗しました")
                return None
            
            st.success("✅ ログインに成功しました！")
            
            # 大会CSV取得
            st.info(f"🏀 大会ID {game_id} のCSVを取得中...")
            target_url = f"{self.base_url}/master-admin-game_category_teams/index/search/true/game_category_id/{game_id}"
            
            response = session.get(target_url, timeout=30)
            if response.status_code != 200:
                st.error(f"❌ 大会ページにアクセスできません (ステータス: {response.status_code})")
                return None
            
            if "404" in response.text or "Error" in response.text:
                st.error("❌ 大会が見つかりませんでした")
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # CSVリンクを抽出
            csv_links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if href and "/master-admin-game_category_teams/csv/id/" in href:
                    if href.startswith("/"):
                        full_url = f"{self.base_url}{href}"
                    else:
                        full_url = href
                    csv_links.append(full_url)
            
            st.info(f"📊 {len(csv_links)} 件のCSVリンクを検出")
            
            if not csv_links:
                st.warning("⚠️ CSVリンクが見つかりませんでした")
                st.info("🔍 デバッグ情報:")
                st.write(f"アクセスURL: {target_url}")
                st.write(f"レスポンスステータス: {response.status_code}")
                
                # ページの内容を一部表示
                page_content = response.text[:1000]  # 最初の1000文字
                st.code(f"ページ内容（最初の1000文字）:\n{page_content}")
                
                return None
            
            # CSVを取得してDataFrameに変換
            all_universities_data = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, csv_url in enumerate(csv_links):
                try:
                    status_text.text(f"CSV {i+1}/{len(csv_links)} を取得中...")
                    
                    csv_response = session.get(csv_url, timeout=30)
                    csv_response.raise_for_status()
                    
                    # CSVをDataFrameに変換（日本語対応）
                    csv_text = csv_response.text
                    # エンコーディングを試行
                    try:
                        df = pd.read_csv(StringIO(csv_text))
                    except UnicodeDecodeError:
                        # UTF-8で失敗した場合はShift_JISを試行
                        csv_text = csv_response.content.decode('shift_jis')
                        df = pd.read_csv(StringIO(csv_text))
                    
                    # 大学名を取得
                    content_disposition = csv_response.headers.get("content-disposition", "")
                    filename_match = re.search(r'filename="(.+)"', content_disposition)
                    
                    if filename_match:
                        university_name = filename_match.group(1).replace('.csv', '')
                    else:
                        university_name = f"大学_{i+1}"
                    
                    # 大学名をDataFrameに追加
                    df['大学名'] = university_name
                    all_universities_data.append(df)
                    
                    progress = (i + 1) / len(csv_links)
                    progress_bar.progress(progress)
                    
                    time.sleep(0.5)  # サーバー負荷軽減
                    
                except Exception as e:
                    st.warning(f"⚠️ CSV {i+1} の取得に失敗: {str(e)}")
                    continue
            
            progress_bar.progress(1.0)
            status_text.text("✅ CSV取得完了")
            
            if all_universities_data:
                # 全大学のデータを結合
                combined_df = pd.concat(all_universities_data, ignore_index=True)
                st.success(f"✅ {len(all_universities_data)} 大学のデータを取得しました")
                return combined_df
            else:
                return None
                
        except Exception as e:
            st.error(f"❌ エラー: {str(e)}")
            return None
    
    def process_tournament_data(self, df, university_name=None):
        """大会データをJBA照合で処理（並列処理対応）"""
        
        if df is None or df.empty:
            st.error("❌ 処理するデータがありません")
            return None
        
        if self.use_parallel:
            st.info(f"⚡ 並列処理を使用（{self.max_workers}スレッド）")
            return self._process_tournament_data_parallel(df, university_name)
        else:
            st.info("🔄 順次処理を使用")
            return self._process_tournament_data_sequential(df, university_name)
    
    def _process_tournament_data_sequential(self, df, university_name=None):
        """順次処理でJBA照合"""
        st.info("🔍 JBA照合処理を開始...")
        
        # 大学ごとに処理
        universities = df['大学名'].unique() if '大学名' in df.columns else [university_name or "Unknown"]
        
        all_results = []
        
        for univ in universities:
            st.info(f"🏫 {univ} を処理中...")
            
            # 大学のデータを抽出
            if '大学名' in df.columns:
                univ_data = df[df['大学名'] == univ].copy()
            else:
                univ_data = df.copy()
            
            # JBA照合処理
            results = []
            
            for index, row in univ_data.iterrows():
                # 選手名を取得
                player_name = None
                name_columns = ['選手名', '氏名', 'name', 'Name']
                
                for col in name_columns:
                    if col in univ_data.columns and pd.notna(row[col]):
                        player_name = str(row[col]).strip()
                        break
                
                if not player_name:
                    results.append({
                        'index': index,
                        'original_data': row.to_dict(),
                        'status': 'missing_data',
                        'message': '選手名が取得できませんでした',
                        'correction': None
                    })
                    continue
                
                # JBA照合
                verification_result = self.jba_system.verify_player_info(
                    player_name, None, univ, get_details=True, threshold=1.0
                )
                
                result = {
                    'index': index,
                    'original_data': row.to_dict(),
                    'verification_result': verification_result,
                    'status': verification_result['status'],
                    'university': univ
                }
                
                # 完全一致の場合
                if verification_result['status'] == 'match':
                    if 'jba_data' in verification_result:
                        jba_data = verification_result['jba_data']
                        is_valid, validation_issues, school_corrections = self.validator.validate_player_data(jba_data)
                        
                        corrected_data = row.to_dict().copy()
                        
                        # JBA情報を追加
                        if 'height' in jba_data and jba_data['height']:
                            corrected_data['身長'] = f"{jba_data['height']}cm"
                        if 'weight' in jba_data and jba_data['weight']:
                            corrected_data['体重'] = f"{jba_data['weight']}kg"
                        if 'position' in jba_data and jba_data['position']:
                            corrected_data['ポジション'] = jba_data['position']
                        if 'school' in jba_data and jba_data['school']:
                            if 'school' in school_corrections:
                                corrected_data['出身校'] = school_corrections['school']
                            else:
                                corrected_data['出身校'] = jba_data['school']
                        if 'grade' in jba_data and jba_data['grade']:
                            corrected_data['学年'] = jba_data['grade']
                        if 'uniform_number' in jba_data and jba_data['uniform_number']:
                            corrected_data['背番号'] = jba_data['uniform_number']
                        
                        result['correction'] = corrected_data
                        
                        if not is_valid:
                            result['validation_issues'] = validation_issues
                            result['message'] = f'JBAデータベースと完全一致（詳細情報追加）⚠️ 異常値検出: {", ".join(validation_issues)}'
                        else:
                            result['message'] = 'JBAデータベースと完全一致（詳細情報追加）'
                    else:
                        result['correction'] = None
                        result['message'] = 'JBAデータベースと完全一致'
                
                # 部分一致の場合
                elif verification_result['status'] == 'partial_match':
                    jba_data = verification_result['jba_data']
                    similarity = verification_result.get('similarity', 0.0)
                    
                    corrected_data = row.to_dict().copy()
                    
                    if 'height' in jba_data and jba_data['height']:
                        corrected_data['身長'] = f"{jba_data['height']}cm"
                    if 'weight' in jba_data and jba_data['weight']:
                        corrected_data['体重'] = f"{jba_data['weight']}kg"
                    if 'position' in jba_data and jba_data['position']:
                        corrected_data['ポジション'] = jba_data['position']
                    if 'school' in jba_data and jba_data['school']:
                        corrected_data['出身校'] = jba_data['school']
                    if 'grade' in jba_data and jba_data['grade']:
                        corrected_data['学年'] = jba_data['grade']
                    if 'uniform_number' in jba_data and jba_data['uniform_number']:
                        corrected_data['背番号'] = jba_data['uniform_number']
                    
                    result['correction'] = corrected_data
                    result['message'] = f"部分一致: {jba_data['name']} (類似度: {similarity:.3f}) - 手動確認推奨"
                
                # 一致なしの場合
                else:
                    result['correction'] = None
                    result['message'] = verification_result.get('message', '照合できませんでした')
                
                results.append(result)
            
            all_results.extend(results)
        
        # 結果をコンパクトに表示
        with st.expander("📊 処理結果詳細", expanded=False):
            st.metric("処理選手数", len(all_results))
            st.metric("処理大学数", len(universities))
        
        return all_results
    
    def _process_tournament_data_parallel(self, df, university_name=None):
        """並列処理でJBA照合"""
        import concurrent.futures
        import time
        
        st.info(f"🔍 JBA照合処理を開始（並列処理: {self.max_workers}スレッド）...")
        
        # パフォーマンス統計をリセット
        self.performance_stats = {
            'total_time': 0,
            'io_time': 0,
            'processing_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'requests_count': 0,
            'avg_response_time': 0
        }
        
        # 大学ごとに処理
        universities = df['大学名'].unique() if '大学名' in df.columns else [university_name or "Unknown"]
        
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        start_time = time.time()
        total_players = len(df)
        processed = 0
        
        # 全選手のデータを準備（Pandas最適化）
        player_data = []
        
        # ベクトル化処理で選手名を一括取得
        name_columns = ['選手名', '氏名', 'name', 'Name']
        available_name_cols = [col for col in name_columns if col in df.columns]
        
        if available_name_cols:
            # 最初に見つかった名前カラムを使用
            name_col = available_name_cols[0]
            df[name_col] = df[name_col].astype(str).str.strip()
            
            # 大学ごとに処理
            for univ in universities:
                if '大学名' in df.columns:
                    univ_data = df[df['大学名'] == univ].copy()
                else:
                    univ_data = df.copy()
                
                # 有効な選手名のみを抽出
                valid_players = univ_data[pd.notna(univ_data[name_col]) & (univ_data[name_col] != '')]
                
                for index, row in valid_players.iterrows():
                    player_name = str(row[name_col]).strip()
                    if player_name:
                        player_data.append((index, row, univ, player_name))
        else:
            # フォールバック: 従来の方法
            for univ in universities:
                if '大学名' in df.columns:
                    univ_data = df[df['大学名'] == univ].copy()
                else:
                    univ_data = df.copy()
                
                for index, row in univ_data.iterrows():
                    player_name = None
                    for col in name_columns:
                        if col in univ_data.columns and pd.notna(row[col]):
                            player_name = str(row[col]).strip()
                            break
                    
                    if player_name:
                        player_data.append((index, row, univ, player_name))
        
        # 並列処理でJBA照合（スレッド数を動的調整）
        optimal_workers = min(self.max_workers, len(player_data), 20)
        
        # 大学ごとの結果を一時保存
        university_results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            futures = []
            
            for index, row, univ, player_name in player_data:
                future = executor.submit(self._process_single_player_parallel, 
                                       index, row, univ, player_name)
                futures.append(future)
            
            # 結果を収集
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    all_results.append(result)
                    processed += 1
                    
                    # 大学ごとの結果を一時保存
                    univ = result.get('university', 'Unknown')
                    if univ not in university_results:
                        university_results[univ] = []
                    university_results[univ].append(result)
                    
                    # 進捗更新（10選手ごと）
                    if processed % 10 == 0 or processed == total_players:
                        progress = processed / total_players
                        progress_bar.progress(progress)
                        status_text.text(f"処理中: {processed}/{total_players} - {result['original_data'].get('選手名', 'Unknown')}")
                        
                        # 大学ごとの結果を一時保存（10選手ごと）
                        if processed % 10 == 0:
                            for univ_name, univ_results in university_results.items():
                                self._save_temp_results(univ_name, univ_results)
                    
                except Exception as e:
                    st.error(f"❌ 並列処理エラー: {str(e)}")
        
        # 最終的な一時保存
        for univ_name, univ_results in university_results.items():
            self._save_temp_results(univ_name, univ_results)
        
        elapsed_time = time.time() - start_time
        self.performance_stats['total_time'] = elapsed_time
        
        # 結果をコンパクトに表示
        with st.expander("📊 処理結果詳細", expanded=False):
            st.metric("処理時間", f"{elapsed_time:.2f}秒")
            st.metric("平均処理時間", f"{elapsed_time/processed:.2f}秒/選手")
            st.metric("処理速度", f"{processed/elapsed_time:.1f}選手/秒")
            st.metric("使用スレッド数", f"{optimal_workers}")
            st.metric("キャッシュヒット率", f"{self.performance_stats['cache_hits']/(self.performance_stats['cache_hits']+self.performance_stats['cache_misses'])*100:.1f}%")
            st.metric("リクエスト数", f"{self.performance_stats['requests_count']}")
        
        st.success(f"✅ 並列処理完了: {processed}選手を{elapsed_time:.2f}秒で処理")
        
        return all_results
    
    def _process_single_player_parallel(self, index, row, univ, player_name):
        """単一選手の並列処理（キャッシュ付き）"""
        # キャッシュキーを生成
        cache_key = f"player_{player_name}_{univ}"
        cached_result = self._get_cached_data(cache_key)
        
        if cached_result:
            # キャッシュから取得
            cached_result['index'] = index
            cached_result['original_data'] = row.to_dict()
            return cached_result
        
        # 実際にJBA照合を実行
        start_time = time.time()
        verification_result = self.jba_system.verify_player_info(
            player_name, None, univ, get_details=True, threshold=1.0
        )
        end_time = time.time()
        
        # パフォーマンス統計を更新
        self.performance_stats['requests_count'] += 1
        response_time = end_time - start_time
        self.performance_stats['avg_response_time'] = (
            (self.performance_stats['avg_response_time'] * (self.performance_stats['requests_count'] - 1) + response_time) 
            / self.performance_stats['requests_count']
        )
        
        result = {
            'index': index,
            'original_data': row.to_dict(),
            'verification_result': verification_result,
            'status': verification_result['status'],
            'university': univ
        }
        
        # 結果をキャッシュに保存
        self._set_cached_data(cache_key, result)
        
        return result
    
    def create_university_reports(self, results):
        """大学ごとのレポートを作成"""
        
        if not results:
            st.error("❌ 処理結果がありません")
            return None
        
        # 大学ごとにグループ化
        universities = {}
        for result in results:
            univ = result.get('university', 'Unknown')
            if univ not in universities:
                universities[univ] = []
            universities[univ].append(result)
        
        reports = {}
        
        for univ, univ_results in universities.items():
            # 統計情報を計算
            total_players = len(univ_results)
            match_count = len([r for r in univ_results if r['status'] == 'match'])
            partial_match_count = len([r for r in univ_results if r['status'] == 'partial_match'])
            not_found_count = len([r for r in univ_results if r['status'] == 'not_found'])
            
            # レポートデータを作成
            report_data = {
                'university': univ,
                'total_players': total_players,
                'match_count': match_count,
                'partial_match_count': partial_match_count,
                'not_found_count': not_found_count,
                'match_rate': (match_count / total_players * 100) if total_players > 0 else 0,
                'results': univ_results
            }
            
            reports[univ] = report_data
        
        return reports
    
    def _generate_university_report(self, university_name, report):
        """単一大学のレポートを生成"""
        html_content = f"""
        <html>
        <head>
            <title>{university_name} 選手データ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .stats {{ display: flex; justify-content: space-around; margin-bottom: 30px; }}
                .stat-box {{ text-align: center; padding: 10px; border: 1px solid #ccc; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .page-break {{ page-break-before: always; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{university_name} 選手データ</h1>
                <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>総選手数</h3>
                    <p>{report['total_players']}</p>
                </div>
                <div class="stat-box">
                    <h3>完全一致</h3>
                    <p>{report['match_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>部分一致</h3>
                    <p>{report['partial_match_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>未発見</h3>
                    <p>{report['not_found_count']}</p>
                </div>
                <div class="stat-box">
                    <h3>一致率</h3>
                    <p>{report['match_rate']:.1f}%</p>
                </div>
            </div>
            
            <h2>選手詳細データ</h2>
            <table>
                <tr>
                    <th>選手名</th>
                    <th>身長</th>
                    <th>体重</th>
                    <th>ポジション</th>
                    <th>出身校</th>
                    <th>学年</th>
                    <th>背番号</th>
                    <th>照合結果</th>
                </tr>
        """
        
        for result in report['results']:
            data = result['original_data']
            message = result.get('message', '')
            
            html_content += f"""
                <tr>
                    <td>{data.get('選手名', data.get('氏名', ''))}</td>
                    <td>{data.get('身長', '')}</td>
                    <td>{data.get('体重', '')}</td>
                    <td>{data.get('ポジション', '')}</td>
                    <td>{data.get('出身校', '')}</td>
                    <td>{data.get('学年', '')}</td>
                    <td>{data.get('背番号', '')}</td>
                    <td>{message}</td>
                </tr>
            """
        
        html_content += """
            </table>
        </body>
        </html>
        """
        
        return html_content
    
    def _generate_all_universities_report(self, reports):
        """全大学の一括レポートを生成"""
        html_content = f"""
        <html>
        <head>
            <title>全大学選手データ一覧</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .university-section {{ margin-bottom: 50px; page-break-before: always; }}
                .university-section:first-child {{ page-break-before: auto; }}
                .stats {{ display: flex; justify-content: space-around; margin-bottom: 30px; }}
                .stat-box {{ text-align: center; padding: 10px; border: 1px solid #ccc; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .university-title {{ background-color: #4CAF50; color: white; padding: 15px; text-align: center; font-size: 18px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>全大学選手データ一覧</h1>
                <p>生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>
                <p>総大学数: {len(reports)} 大学</p>
            </div>
        """
        
        # 全大学の統計情報
        total_players = sum(report['total_players'] for report in reports.values())
        total_matches = sum(report['match_count'] for report in reports.values())
        total_partial = sum(report['partial_match_count'] for report in reports.values())
        total_not_found = sum(report['not_found_count'] for report in reports.values())
        overall_match_rate = (total_matches / total_players * 100) if total_players > 0 else 0
        
        html_content += f"""
            <div class="stats">
                <div class="stat-box">
                    <h3>総選手数</h3>
                    <p>{total_players}</p>
                </div>
                <div class="stat-box">
                    <h3>完全一致</h3>
                    <p>{total_matches}</p>
                </div>
                <div class="stat-box">
                    <h3>部分一致</h3>
                    <p>{total_partial}</p>
                </div>
                <div class="stat-box">
                    <h3>未発見</h3>
                    <p>{total_not_found}</p>
                </div>
                <div class="stat-box">
                    <h3>全体一致率</h3>
                    <p>{overall_match_rate:.1f}%</p>
                </div>
            </div>
        """
        
        # 各大学のデータ
        for univ_name, report in reports.items():
            html_content += f"""
                <div class="university-section">
                    <div class="university-title">{univ_name}</div>
                    
                    <div class="stats">
                        <div class="stat-box">
                            <h4>総選手数</h4>
                            <p>{report['total_players']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>完全一致</h4>
                            <p>{report['match_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>部分一致</h4>
                            <p>{report['partial_match_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>未発見</h4>
                            <p>{report['not_found_count']}</p>
                        </div>
                        <div class="stat-box">
                            <h4>一致率</h4>
                            <p>{report['match_rate']:.1f}%</p>
                        </div>
                    </div>
                    
                    <h3>選手詳細データ</h3>
                    <table>
                        <tr>
                            <th>選手名</th>
                            <th>身長</th>
                            <th>体重</th>
                            <th>ポジション</th>
                            <th>出身校</th>
                            <th>学年</th>
                            <th>背番号</th>
                            <th>照合結果</th>
                        </tr>
            """
            
            for result in report['results']:
                data = result['original_data']
                message = result.get('message', '')
                
                html_content += f"""
                    <tr>
                        <td>{data.get('選手名', data.get('氏名', ''))}</td>
                        <td>{data.get('身長', '')}</td>
                        <td>{data.get('体重', '')}</td>
                        <td>{data.get('ポジション', '')}</td>
                        <td>{data.get('出身校', '')}</td>
                        <td>{data.get('学年', '')}</td>
                        <td>{data.get('背番号', '')}</td>
                        <td>{message}</td>
                    </tr>
                """
            
            html_content += """
                    </table>
                </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        return html_content
    
    def display_university_report(self, selected_univ, report, game_id, reports):
        """大学別レポートを表示"""
        st.markdown(f"### {selected_univ} レポート")
        
        # 統計情報
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("総選手数", report['total_players'])
        with col2:
            st.metric("完全一致", report['match_count'])
        with col3:
            st.metric("部分一致", report['partial_match_count'])
        with col4:
            st.metric("未発見", report['not_found_count'])
        with col5:
            st.metric("一致率", f"{report['match_rate']:.1f}%")
        
        # タブ表示
        tab1, tab2, tab3, tab4 = st.tabs(["全詳細", "完全一致", "部分一致", "未発見"])
        
        with tab1:
            st.subheader("全選手データ")
            if report['results']:
                df_all = pd.DataFrame([r['original_data'] for r in report['results']])
                st.dataframe(df_all)
            else:
                st.info("データがありません")
        
        with tab2:
            st.subheader("完全一致選手")
            match_results = [r for r in report['results'] if r['status'] == 'match']
            if match_results:
                df_match = pd.DataFrame([r['original_data'] for r in match_results])
                st.dataframe(df_match)
            else:
                st.info("完全一致の選手はありません")
        
        with tab3:
            st.subheader("部分一致選手")
            partial_results = [r for r in report['results'] if r['status'] == 'partial_match']
            if partial_results:
                df_partial = pd.DataFrame([r['original_data'] for r in partial_results])
                st.dataframe(df_partial)
            else:
                st.info("部分一致の選手はありません")
        
        with tab4:
            st.subheader("未発見選手")
            not_found_results = [r for r in report['results'] if r['status'] == 'not_found']
            if not_found_results:
                df_not_found = pd.DataFrame([r['original_data'] for r in not_found_results])
                st.dataframe(df_not_found)
            else:
                st.info("未発見の選手はありません")
        
        # 全大学一括印刷レポート
        st.subheader("🖨️ 全大学一括印刷レポート")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 選択大学のレポートを生成"):
                # 選択された大学のレポートを生成
                html_content = self._generate_university_report(selected_univ, report)
                
                st.download_button(
                    label="📄 HTMLレポートをダウンロード",
                    data=html_content,
                    file_name=f"{selected_univ}_選手データ.html",
                    mime="text/html"
                )
        
        with col2:
            if st.button("📚 全大学一括レポートを生成", type="primary"):
                # 全大学のレポートを生成
                st.info("📚 全大学のレポートを生成中...")
                
                html_content = self._generate_all_universities_report(reports)
                
                st.download_button(
                    label="📚 全大学一括HTMLレポートをダウンロード",
                    data=html_content,
                    file_name=f"大会ID{game_id}_全大学選手データ.html",
                    mime="text/html"
                )
                
                st.success("✅ 全大学のレポートが生成されました！")

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
        
        # システム初期化
        from jba_verification_lib import JBAVerificationSystem, DataValidator
        
        jba_system = JBAVerificationSystem()
        validator = DataValidator()
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
                    selected_univ = st.selectbox("大学を選択:", list(reports.keys()))
                    
                    if selected_univ:
                        report = reports[selected_univ]
                        
                        # 統計情報表示
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("総選手数", report['total_players'])
                        with col2:
                            st.metric("完全一致", report['match_count'])
                        with col3:
                            st.metric("部分一致", report['partial_match_count'])
                        with col4:
                            st.metric("未発見", report['not_found_count'])
                        
                        # 一致率
                        st.metric("一致率", f"{report['match_rate']:.1f}%")
                        
                        # 詳細データ表示
                        st.subheader(f"📋 {selected_univ} 詳細データ")
                        
                        # タブで分類表示
                        tab1, tab2, tab3, tab4 = st.tabs(["全詳細", "完全一致", "部分一致", "未発見"])
                        
                        with tab1:
                            st.dataframe(pd.DataFrame([r['original_data'] for r in report['results']]))
                        
                        with tab2:
                            match_results = [r for r in report['results'] if r['status'] == 'match']
                            if match_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in match_results]))
                            else:
                                st.info("完全一致のデータはありません")
                        
                        with tab3:
                            partial_results = [r for r in report['results'] if r['status'] == 'partial_match']
                            if partial_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in partial_results]))
                            else:
                                st.info("部分一致のデータはありません")
                        
                        with tab4:
                            not_found_results = [r for r in report['results'] if r['status'] == 'not_found']
                            if not_found_results:
                                st.dataframe(pd.DataFrame([r['original_data'] for r in not_found_results]))
                            else:
                                st.info("未発見のデータはありません")
                        
                        # 全大学一括印刷レポート
                        st.subheader("🖨️ 全大学一括印刷レポート")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("📄 選択大学のレポートを生成"):
                                # 選択された大学のレポートを生成
                                html_content = self._generate_university_report(selected_univ, report)
                                
                                st.download_button(
                                    label="📄 HTMLレポートをダウンロード",
                                    data=html_content,
                                    file_name=f"{selected_univ}_選手データ.html",
                                    mime="text/html"
                                )
                        
                        with col2:
                            if st.button("📚 全大学一括レポートを生成", type="primary"):
                                # 全大学のレポートを生成
                                st.info("📚 全大学のレポートを生成中...")
                                
                                html_content = self._generate_all_universities_report(reports)
                                
                                st.download_button(
                                    label="📚 全大学一括HTMLレポートをダウンロード",
                                    data=html_content,
                                    file_name=f"大会ID{game_id}_全大学選手データ.html",
                                    mime="text/html"
                                )
                                
                                st.success("✅ 全大学のレポートが生成されました！")
                
                else:
                    st.error("❌ レポートの作成に失敗しました")
            else:
                st.error("❌ JBA照合処理に失敗しました")
        else:
            st.error("❌ CSV取得に失敗しました")
    
    def export_all_university_reports_as_pdf(self, reports, output_path="all_universities_report.pdf"):
        """全大学レポートを1ファイルのPDFにまとめて出力"""
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # ヘッダー情報
        elements.append(Paragraph("🏀 全大学選手データ一覧", styles["Title"]))
        elements.append(Paragraph(f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}", styles["Normal"]))
        elements.append(Paragraph(f"総大学数: {len(reports)} 大学", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # 全体統計
        total_players = sum(report['total_players'] for report in reports.values())
        total_matches = sum(report['match_count'] for report in reports.values())
        overall_match_rate = (total_matches / total_players * 100) if total_players > 0 else 0
        
        elements.append(Paragraph("📊 全体統計", styles["Heading2"]))
        elements.append(Paragraph(f"総選手数: {total_players}", styles["Normal"]))
        elements.append(Paragraph(f"完全一致: {total_matches}", styles["Normal"]))
        elements.append(Paragraph(f"全体一致率: {overall_match_rate:.1f}%", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # 各大学のレポート
        for i, (univ_name, report) in enumerate(reports.items()):
            elements.append(Paragraph(f"🏫 {univ_name}", styles["Heading1"]))
            elements.append(Spacer(1, 12))
            
            # 大学統計
            elements.append(Paragraph(f"総選手数: {report['total_players']}", styles["Normal"]))
            elements.append(Paragraph(f"完全一致: {report['match_count']}", styles["Normal"]))
            elements.append(Paragraph(f"部分一致: {report['partial_match_count']}", styles["Normal"]))
            elements.append(Paragraph(f"未発見: {report['not_found_count']}", styles["Normal"]))
            elements.append(Paragraph(f"一致率: {report['match_rate']:.1f}%", styles["Normal"]))
            elements.append(Spacer(1, 12))
            
            # 選手データテーブル
            elements.append(Paragraph("選手詳細データ", styles["Heading2"]))
            
            # テーブルデータ作成（軽量化）
            data = [["選手名", "身長", "体重", "ポジション", "出身校", "学年", "背番号", "照合結果"]]
            for r in report["results"]:
                d = r["original_data"]
                status = r.get("status", "unknown")
                message = r.get("message", "")
                
                # ステータスに応じて色分け
                status_text = ""
                if status == "match":
                    status_text = "✅ 完全一致"
                elif status == "partial_match":
                    status_text = "⚠️ 部分一致"
                elif status == "not_found":
                    status_text = "❌ 未発見"
                else:
                    status_text = f"❓ {status}"
                
                # テキストを短縮してPDF軽量化
                data.append([
                    self._truncate_text(d.get("選手名", d.get("氏名", "")), 20),
                    self._truncate_text(d.get("身長", ""), 10),
                    self._truncate_text(d.get("体重", ""), 10),
                    self._truncate_text(d.get("ポジション", ""), 15),
                    self._truncate_text(d.get("出身校", ""), 25),
                    self._truncate_text(d.get("学年", ""), 10),
                    self._truncate_text(d.get("背番号", ""), 10),
                    self._truncate_text(status_text, 20)
                ])
            
            # テーブル作成
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            elements.append(table)
            
            # 各大学をページ区切り（最後の大学以外）
            if i < len(reports) - 1:
                elements.append(PageBreak())
        
        # PDF生成
        doc.build(elements)
        return output_path
    
    def export_single_university_report_as_pdf(self, university_name, report, output_path=None):
        """単一大学のレポートをPDF出力"""
        if output_path is None:
            output_path = f"{university_name}_選手データ.pdf"
        
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # ヘッダー情報
        elements.append(Paragraph(f"🏫 {university_name} 選手データ", styles["Title"]))
        elements.append(Paragraph(f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # 統計情報
        elements.append(Paragraph("📊 統計情報", styles["Heading2"]))
        elements.append(Paragraph(f"総選手数: {report['total_players']}", styles["Normal"]))
        elements.append(Paragraph(f"完全一致: {report['match_count']}", styles["Normal"]))
        elements.append(Paragraph(f"部分一致: {report['partial_match_count']}", styles["Normal"]))
        elements.append(Paragraph(f"未発見: {report['not_found_count']}", styles["Normal"]))
        elements.append(Paragraph(f"一致率: {report['match_rate']:.1f}%", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # 選手データテーブル
        elements.append(Paragraph("選手詳細データ", styles["Heading2"]))
        
        # テーブルデータ作成（軽量化）
        data = [["選手名", "身長", "体重", "ポジション", "出身校", "学年", "背番号", "照合結果"]]
        for r in report["results"]:
            d = r["original_data"]
            status = r.get("status", "unknown")
            
            # ステータスに応じて色分け
            status_text = ""
            if status == "match":
                status_text = "✅ 完全一致"
            elif status == "partial_match":
                status_text = "⚠️ 部分一致"
            elif status == "not_found":
                status_text = "❌ 未発見"
            else:
                status_text = f"❓ {status}"
            
            # テキストを短縮してPDF軽量化
            data.append([
                self._truncate_text(d.get("選手名", d.get("氏名", "")), 20),
                self._truncate_text(d.get("身長", ""), 10),
                self._truncate_text(d.get("体重", ""), 10),
                self._truncate_text(d.get("ポジション", ""), 15),
                self._truncate_text(d.get("出身校", ""), 25),
                self._truncate_text(d.get("学年", ""), 10),
                self._truncate_text(d.get("背番号", ""), 10),
                self._truncate_text(status_text, 20)
            ])
        
        # テーブル作成
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(table)
        
        # PDF生成
        doc.build(elements)
        return output_path

if __name__ == "__main__":
    main()
