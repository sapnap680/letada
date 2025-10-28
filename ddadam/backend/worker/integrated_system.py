# Streamlit removed
import requests
import logging

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
import uuid
import multiprocessing
# オプション: バックグラウンドPDFワーカー（存在しない環境でも動作するようにガード）
try:
    from integrated_system_worker import pdf_worker_main
except Exception:
    pdf_worker_main = None
from io import StringIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import multiprocessing
import platform

# 既存のJBA検証システムのインポート
import sys
sys.path.append('.')

# JBA検証システムのインポート
from worker.jba_verification_lib import JBAVerificationSystem, FastCSVCorrectionSystem, DataValidator

class IntegratedTournamentSystem:
    """大会IDからJBA照合まで一括処理する統合システム"""
    
    logger = logging.getLogger(__name__)
    
    
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
        
        # 日本語フォントを登録
        self._register_japanese_fonts()
    
    def _register_japanese_fonts(self):
        """日本語フォントを登録"""
        try:
            # TTCフォントを堅牢に登録するヘルパー
            def _try_register_ttc(font_name_base: str, ttc_path: str, max_index: int = 8) -> str:
                """.ttc のサブフォントを順に試す。成功したフォント名を返す（失敗時は空文字）。"""
                from reportlab.pdfbase.ttfonts import TTFont
                for i in range(max_index):
                    try:
                        candidate_name = f"{font_name_base}-{i}"
                        pdfmetrics.registerFont(TTFont(candidate_name, ttc_path, subfontIndex=i))
                        return candidate_name
                    except Exception:
                        continue
                return ""

            # Windowsの場合
            if platform.system() == "Windows":
                # MS ゴシック
                try:
                    pdfmetrics.registerFont(TTFont('MS-Gothic', 'C:/Windows/Fonts/msgothic.ttc'))
                    self.default_font = 'MS-Gothic'
                    print("✅ MS-Gothic フォント登録成功")
                except Exception as e:
                    print(f"⚠️ MS-Gothic 登録失敗: {e}")
                
                # MS 明朝
                if not hasattr(self, 'default_font'):
                    try:
                        pdfmetrics.registerFont(TTFont('MS-Mincho', 'C:/Windows/Fonts/msmincho.ttc'))
                        self.default_font = 'MS-Mincho'
                        print("✅ MS-Mincho フォント登録成功")
                    except Exception as e:
                        print(f"⚠️ MS-Mincho 登録失敗: {e}")
                
                # メイリオ
                if not hasattr(self, 'default_font'):
                    try:
                        pdfmetrics.registerFont(TTFont('Meiryo', 'C:/Windows/Fonts/meiryo.ttc'))
                        self.default_font = 'Meiryo'
                        print("✅ Meiryo フォント登録成功")
                    except Exception as e:
                        print(f"⚠️ Meiryo 登録失敗: {e}")
            
            # Linux/Macの場合
            else:
                # Linux環境での日本語フォント対応
                font_paths_ttc = [
                    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc'
                ]
                font_paths_ttf_otf = [
                    '/usr/share/fonts/truetype/noto/NotoSansCJKjp-Regular.otf',
                    '/usr/share/fonts/truetype/noto/NotoSerifCJKjp-Regular.otf',
                ]
                
                font_registered = False
                # まず .ttc をサブフォント含めて試す
                for ttc_path in font_paths_ttc:
                    if os.path.exists(ttc_path):
                        name = _try_register_ttc('NotoCJK', ttc_path, max_index=16)
                        if name:
                            self.default_font = name
                            print(f"✅ 日本語フォント登録成功 (TTC): {ttc_path} -> {name}")
                            font_registered = True
                            break
                        else:
                            print(f"⚠️ TTC登録失敗: {ttc_path}")
                # 次に、CIDフォント（組み込み日本語フォント）を優先して試す
                if not font_registered:
                    try:
                        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
                        self.default_font = 'HeiseiKakuGo-W5'
                        print("✅ ReportLab組み込み日本語フォント使用 (HeiseiKakuGo-W5)")
                        font_registered = True
                    except Exception as e:
                        print(f"⚠️ 組み込みCIDフォント登録失敗: {e}")

                # つぎに単一CJKフォントファイル（OTF）を試す（存在する場合）
                if not font_registered:
                    for font_path in font_paths_ttf_otf:
                        if os.path.exists(font_path):
                            try:
                                pdfmetrics.registerFont(TTFont('NotoCJK', font_path))
                                self.default_font = 'NotoCJK'
                                print(f"✅ 日本語フォント登録成功: {font_path}")
                                font_registered = True
                                break
                            except Exception as e:
                                print(f"⚠️ フォント登録失敗 {font_path}: {e}")
                                continue
                
                # フォント登録に失敗した場合は、ReportLabのデフォルトフォントを使用
                if not font_registered:
                    # 最後の手段として、英字フォントを使用（日本語は豆腐になる可能性あり）
                    self.default_font = 'Helvetica'
                    print("⚠️ 日本語フォントが見つからないため、Helveticaを一時使用（日本語は表示不可の可能性）")
                    
        except Exception as e:
            print(f"⚠️ 日本語フォント登録エラー: {str(e)}")
            self.default_font = 'Helvetica'
        
        print(f"📝 使用フォント: {self.default_font}")
    
    def _truncate_text(self, text, max_chars=15):
        """テキストを指定文字数で切り詰め"""
        if not isinstance(text, str):
            text = str(text)
        if pd.isna(text) or text == 'nan':
            return ""
        # 改行文字を除去
        text = text.replace('\n', ' ').replace('\r', ' ')
        # 長すぎる場合は切り詰め
        if len(text) <= max_chars:
            return text
        else:
            return text[:max_chars-2] + ".."
    
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
                # メッセージを削除（進捗バーのみで十分）
        except Exception as e:
            pass  # エラーメッセージも表示しない
    
    def _load_temp_results(self, univ_name):
        """大学ごとの結果を一時保存から読み込み"""
        temp_file = os.path.join(self.temp_dir, f"temp_results_{univ_name}.csv")
        if os.path.exists(temp_file):
            try:
                df = pd.read_csv(temp_file, encoding='utf-8-sig')
                return df.to_dict('records')
            except Exception as e:
                pass
        return None
    
    def _clear_temp_results(self):
        """一時保存ファイルをクリア"""
        try:
            for file in os.listdir(self.temp_dir):
                if file.startswith("temp_results_") and file.endswith(".csv"):
                    os.remove(os.path.join(self.temp_dir, file))
            pass  # メッセージを表示しない
        except Exception as e:
            pass  # エラーメッセージも表示しない
        
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
            print("🔐 ログイン処理中...")
            login_url = f"{self.base_url}/restrict/login"
            login_page = session.get(login_url, timeout=30)
            
            if login_page.status_code != 200:
                print("❌ ログインページにアクセスできません")
                return None
            
            soup = BeautifulSoup(login_page.text, "html.parser")
            form = soup.find("form")
            
            if not form:
                print("❌ ログインフォームが見つかりません")
                return None
            
            # ログイン実行
            form_action = f"{self.base_url}/master-admin/login"
            login_data = {"uid": username, "pass": password}
            session.headers.update({"Referer": login_url})
            
            login_response = session.post(form_action, data=login_data, timeout=30)
            
            if "login" in login_response.url.lower():
                print("❌ ログインに失敗しました")
                return None
            
            print("✅ ログインに成功しました！")
            
            # 大会CSV取得
            print(f"🏀 大会ID {game_id} のCSVを取得中...")
            target_url = f"{self.base_url}/master-admin-game_category_teams/index/search/true/game_category_id/{game_id}"
            
            response = session.get(target_url, timeout=30)
            if response.status_code != 200:
                print(f"❌ 大会ページにアクセスできません (ステータス: {response.status_code})")
                return None
            
            if "404" in response.text or "Error" in response.text:
                print("❌ 大会が見つかりませんでした")
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
            
            print(f"📊 {len(csv_links)} 件のCSVリンクを検出")
            
            if not csv_links:
                print("⚠️ CSVリンクが見つかりませんでした")
                print("🔍 デバッグ情報:")
                print(f"アクセスURL: {target_url}")
                print(f"レスポンスステータス: {response.status_code}")
                
                # ページの内容を一部表示
                page_content = response.text[:1000]  # 最初の1000文字
                print(f"ページ内容（最初の1000文字）:\n{page_content}")
                
                return None
            
            # CSVを取得してDataFrameに変換
            all_universities_data = []
            
            print("📊 CSV取得処理中...")
            
            for i, csv_url in enumerate(csv_links):
                try:
                    print(f"CSV {i+1}/{len(csv_links)} を取得中...")
                    
                    csv_response = session.get(csv_url, timeout=30)
                    csv_response.raise_for_status()
                    
                    # CSVをDataFrameに変換（日本語対応）
                    # まずはレスポンスのエンコーディングを確認
                    response_encoding = csv_response.encoding or 'utf-8'
                    csv_text = csv_response.text
                    
                    # エンコーディングを試行
                    try:
                        df = pd.read_csv(StringIO(csv_text))
                    except UnicodeDecodeError:
                        # UTF-8で失敗した場合はShift_JISを試行
                        try:
                            csv_text = csv_response.content.decode('shift_jis')
                            df = pd.read_csv(StringIO(csv_text))
                        except UnicodeDecodeError:
                            # Shift_JISでも失敗した場合はcp932を試行
                            csv_text = csv_response.content.decode('cp932')
                            df = pd.read_csv(StringIO(csv_text))
                    
                    # 大学名を取得（文字エンコーディング対応）
                    content_disposition = csv_response.headers.get("content-disposition", "")
                    filename_match = re.search(r'filename="(.+)"', content_disposition)
                    
                    if filename_match:
                        # 文字エンコーディングを修正
                        university_name = filename_match.group(1).replace('.csv', '')
                        try:
                            # URLデコードしてからUTF-8でデコード
                            import urllib.parse
                            university_name = urllib.parse.unquote(university_name)
                            # さらにISO-8859-1からUTF-8に変換を試行
                            if '\\' in university_name:
                                university_name = university_name.encode('latin-1').decode('utf-8')
                        except:
                            # エンコーディング変換に失敗した場合はそのまま使用
                            pass
                    else:
                        university_name = f"大学_{i+1}"
                    
                    # 大学名をDataFrameに追加
                    df['大学名'] = university_name
                    all_universities_data.append(df)
                    
                    print(f"✅ CSV {i+1} 取得成功")
                    # Sleep removed  # サーバー負荷軽減
                    
                except Exception as e:
                    print(f"⚠️ CSV {i+1} の取得に失敗: {str(e)}")
                    continue
            
            print("✅ CSV取得完了")
            
            if all_universities_data:
                # 全大学のデータを結合
                combined_df = pd.concat(all_universities_data, ignore_index=True)
                print(f"✅ {len(all_universities_data)} 大学のデータを取得しました")
                return combined_df
            else:
                return None
                
        except Exception as e:
            print(f"❌ エラー: {str(e)}")
            return None
    
    def process_tournament_data(self, df, university_name=None):
        """大会データをJBA照合で処理（並列処理対応）"""
        
        if df is None or df.empty:
            print("❌ 処理するデータがありません")
            return None
        
        if self.use_parallel:
            print(f"⚡ 並列処理を使用（{self.max_workers}スレッド）")
            return self._process_tournament_data_parallel(df, university_name)
        else:
            print("🔄 順次処理を使用")
            return self._process_tournament_data_sequential(df, university_name)
    
    def _process_tournament_data_sequential(self, df, university_name=None):
        """順次処理でJBA照合"""
        print("🔍 JBA照合処理を開始...")
        
        # 大学ごとに処理
        universities = df['大学名'].unique() if '大学名' in df.columns else [university_name or "Unknown"]
        
        all_results = []
        
        for univ in universities:
            print(f"🏫 {univ} を処理中...")
            
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
        print(f"📊 処理結果: {len(all_results)}選手")
        print(f"📊 処理大学数: {len(universities)}")
        
        return all_results
    
    def _process_tournament_data_parallel(self, df, university_name=None):
        """並列処理でJBA照合"""
        import concurrent.futures
        import time
        
        # JBA照合処理を開始（並列処理）
        
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
        # Progress bar removed - use update_job_progress() instead
        # status_text = st.empty() removed
        
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
                        # Progress update - use update_job_progress(job_id, )
                        # status update removed - use update_job_message()}")
                        
                        # 大学ごとの結果を一時保存（10選手ごと）
                        if processed % 10 == 0:
                            for univ_name, univ_results in university_results.items():
                                self._save_temp_results(univ_name, univ_results)
                    
                except Exception as e:
                    logging.error(f"❌ 処理中にエラーが発生しました: {str(e)}", exc_info=True)
        
        # 最終的な一時保存
        for univ_name, univ_results in university_results.items():
            self._save_temp_results(univ_name, univ_results)
        
        elapsed_time = time.time() - start_time
        self.performance_stats['total_time'] = elapsed_time
        
        # 結果をコンパクトに表示 (Streamlit removed)
        # Metrics removed
        
        # 並列処理完了
        
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
            # 処理結果がありません
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
        # Markdown removed
        
        # Streamlit UI 削除済み: 何もしない
        return None

    def export_all_university_reports_as_pdf(self, reports, output_path="all_universities_report.pdf", max_rows_per_page=100):
        """全大学レポートをコンパクトなPDFで出力（画像の形式に準拠）"""
        # A4縦向きで作成
        doc = SimpleDocTemplate(output_path, pagesize=A4, 
                               leftMargin=8*mm, rightMargin=8*mm,
                               topMargin=10*mm, bottomMargin=10*mm)
        styles = getSampleStyleSheet()
        elements = []
        
        # カスタムスタイル（超コンパクト）
        compact_style = ParagraphStyle(
            'Compact',
            parent=styles['Normal'],
            fontSize=6,
            leading=6,  # 行間をさらに縮小
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        title_style = ParagraphStyle(
            'TitleCompact',
            parent=styles['Title'],
            fontSize=8,
            leading=9,  # 行間をさらに縮小
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        # ヘッダー情報（最小限）
        elements.append(Paragraph("🏀 全大学選手データ一覧", title_style))
        elements.append(Spacer(1, 1))  # スペースを最小限に
        
        # 各大学のレポート（コンパクトな表形式）
        for i, (univ_name, report) in enumerate(reports.items()):
            # 大学名ヘッダー（最小限）
            univ_header = f"【{univ_name}】"
            elements.append(Paragraph(univ_header, compact_style))
            elements.append(Spacer(1, 1))  # スペースを最小限に
            
            # 選手データをページング
            results = report["results"]
            total_pages = (len(results) + max_rows_per_page - 1) // max_rows_per_page
            
            for page_num in range(total_pages):
                start_idx = page_num * max_rows_per_page
                end_idx = min(start_idx + max_rows_per_page, len(results))
                page_results = results[start_idx:end_idx]
                
                # テーブルデータ作成（画像の形式に準拠）
                data = [["No", "選手名", "カナ名", "学部", "学年", "身長", "体重", "ポジション", "出身校", "JBA"]]
                
                for idx, r in enumerate(page_results, start=start_idx+1):
                    d = r["original_data"]
                    status = r.get("status", "unknown")
                    
                    # ステータス記号
                    if status == "match":
                        status_symbol = "✓"
                    elif status == "partial_match":
                        status_symbol = "△"
                    elif status == "not_found":
                        status_symbol = "×"
                    else:
                        status_symbol = "-"
                    
                    # データ行を作成（画像の列構成に準拠）
                    # 変更されたデータを赤字で表示
                    no = d.get("No", d.get("背番号", ""))
                    player_name = d.get("選手名", d.get("氏名", ""))
                    kana_name = d.get("カナ名", "")
                    department = d.get("学部", "")
                    grade = d.get("学年", "")
                    height = d.get("身長", "")
                    weight = d.get("体重", "")
                    position = d.get("ポジション", "")
                    school = d.get("出身校", "")
                    
                    # 変更があった場合は赤字で表示
                    if r.get("correction"):
                        corrected_data = r["correction"]
                        if corrected_data.get("No") != no:
                            no = f'<font color="red">{corrected_data.get("No", no)}</font>'
                        if corrected_data.get("選手名") != player_name:
                            player_name = f'<font color="red">{corrected_data.get("選手名", player_name)}</font>'
                        if corrected_data.get("カナ名") != kana_name:
                            kana_name = f'<font color="red">{corrected_data.get("カナ名", kana_name)}</font>'
                        if corrected_data.get("学部") != department:
                            department = f'<font color="red">{corrected_data.get("学部", department)}</font>'
                        if corrected_data.get("学年") != grade:
                            grade = f'<font color="red">{corrected_data.get("学年", grade)}</font>'
                        if corrected_data.get("身長") != height:
                            height = f'<font color="red">{corrected_data.get("身長", height)}</font>'
                        if corrected_data.get("体重") != weight:
                            weight = f'<font color="red">{corrected_data.get("体重", weight)}</font>'
                        if corrected_data.get("ポジション") != position:
                            position = f'<font color="red">{corrected_data.get("ポジション", position)}</font>'
                        if corrected_data.get("出身校") != school:
                            school = f'<font color="red">{corrected_data.get("出身校", school)}</font>'
                    
                    row_data = [
                        self._truncate_text(no, 3),  # No
                        self._truncate_text(player_name, 8),  # 選手名
                        self._truncate_text(kana_name, 8),  # カナ名
                        self._truncate_text(department, 6),  # 学部
                        self._truncate_text(grade, 3),  # 学年
                        self._truncate_text(height, 5),  # 身長
                        self._truncate_text(weight, 4),  # 体重
                        self._truncate_text(position, 6),  # ポジション
                        self._truncate_text(school, 10),  # 出身校
                        status_symbol  # JBA登録状況
                    ]
                    
                    data.append(row_data)
                
                # テーブル作成（A4縦向き最適化）
                col_widths = [8*mm, 18*mm, 18*mm, 12*mm, 8*mm, 10*mm, 8*mm, 12*mm, 20*mm, 8*mm]
                
                # 行の高さを固定で設定（final_100_output.pdfと同じ設定）
                row_heights = [10] + [7] * (len(data) - 1)  # ヘッダー10pt、データ行7pt
                
                table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
                table.setStyle(TableStyle([
                # ヘッダー
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),  # 上揃えに変更
                ("FONTNAME", (0, 0), (-1, 0), getattr(self, 'default_font', 'MS-Gothic')),
                ("FONTSIZE", (0, 0), (-1, 0), 5),  # ヘッダーフォントサイズ（final_100_outputと同じ）
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),  # ヘッダーパディング（final_100_outputと同じ）
                
                # データ行
                ("FONTNAME", (0, 1), (-1, -1), getattr(self, 'default_font', 'MS-Gothic')),
                ("FONTSIZE", (0, 1), (-1, -1), 4),  # データフォントサイズ（final_100_outputと同じ）
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
                
                # 罫線
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),  # 罫線を細く
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                    
                # パディング調整（文字がテーブル内に正しく配置されるように）
                ("TOPPADDING", (0, 1), (-1, -1), 1),  # 上部パディングを少し追加
                ("BOTTOMPADDING", (0, 1), (-1, -1), 1),  # 下部パディングを少し追加
                ("LEFTPADDING", (0, 0), (-1, -1), 1),  # 左パディングを少し追加
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),  # 右パディングを少し追加
                ]))
                
                elements.append(table)
                
                # ページ区切り（最後のページ以外）
                if page_num < total_pages - 1:
                    elements.append(Spacer(1, 5))  # スペースを削減
                    page_info = f"(ページ {page_num+1}/{total_pages})"
                    elements.append(Paragraph(page_info, compact_style))
                    elements.append(PageBreak())
            
            # 大学区切り（最後の大学以外）
            if i < len(reports) - 1:
                elements.append(PageBreak())
        
        # PDF生成
        doc.build(elements)
        print(f"📄 PDF生成完了: {output_path} (フォント: {getattr(self, 'default_font', 'Unknown')})")
        return output_path
    
    def start_pdf_generation_background(self, reports, output_filename=None):
        """reports をバックグラウンドでPDF化するジョブを開始する（別プロセス版）。"""
        if output_filename is None:
            output_filename = os.path.join(self.temp_dir, f"all_universities_report_{int(time.time())}.zip")
        job_id = str(uuid.uuid4())
        job_meta = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "message": "queued",
            "output_path": output_filename,
            "error": None,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        job_meta_path = os.path.join(self.temp_dir, f"pdf_job_{job_id}.json")
        with open(job_meta_path, "w", encoding="utf-8") as f:
            json.dump(job_meta, f, ensure_ascii=False, indent=2)

        # --- 安全対策: reports をプリシリアライズ（pickle での不整合を避ける） ---
        try:
            serializable_reports = json.loads(json.dumps(reports, default=str))
        except Exception:
            # 最低限: 文字列化に失敗したらそのまま渡す（pickle に任せる）
            serializable_reports = reports

        # --- spawn コンテキストでプロセスを作成（ワーカー未提供なら同期生成にフォールバック） ---
        if pdf_worker_main is None:
            # フォールバック: 同期でPDF生成を実行（最低限の動作確保）
            try:
                # フォールバックとして全大学PDFを単発生成（reports 構造に依存）
                output_pdf = output_filename if output_filename.endswith('.pdf') else output_filename.replace('.zip', '.pdf')
                self.export_all_university_reports_as_pdf(reports=reports, output_path=output_pdf)
                self._write_job_meta(job_meta_path, status="done", progress=1.0, message="PDF generated (fallback)", output_path=output_pdf)
            except Exception as e:
                self._write_job_meta(job_meta_path, status="error", message=f"Fallback PDF generation failed: {e}", error=str(e))
                raise
        else:
            try:
                ctx = multiprocessing.get_context("spawn")
                proc = ctx.Process(
                    target=pdf_worker_main,
                    args=(serializable_reports, output_filename, job_meta_path),
                    daemon=False
                )
                proc.start()
            except Exception as e:
                # 失敗したら job_meta にエラーを書き込む
                self._write_job_meta(job_meta_path, status="error", message=f"Failed to start worker: {e}", error=str(e))
                raise

        return job_meta_path

    def _write_job_meta(self, job_meta_path, **kwargs):
        """job_meta JSON を上書き更新"""
        try:
            # read existing
            meta = {}
            if os.path.exists(job_meta_path):
                with open(job_meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            meta.update(kwargs)
            with open(job_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # ロギングのみ
            print(f"Failed to write job meta: {e}")

    
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

    def generate_pdfs_by_university(self, df, output_dir, filename_prefix="tournament"):
        """大学ごとにPDFを生成（1大学1ページ）"""
        if df is None or df.empty:
            return None

        # 大学ごとにグループ化
        universities = df['大学名'].unique() if '大学名' in df.columns else ["Unknown"]
        pdf_files = []

        for univ in universities:
            if '大学名' in df.columns:
                univ_data = df[df['大学名'] == univ].copy()
            else:
                univ_data = df.copy()

            # 大学のレポートを作成
            report = {
                'university': univ,
                'total_players': len(univ_data),
                'match_count': 0,  # 簡易版
                'partial_match_count': 0,
                'not_found_count': 0,
                'match_rate': 0.0,
                'results': []  # 簡易版
            }

            # 選手データを結果形式に変換
            for index, row in univ_data.iterrows():
                result = {
                    'index': index,
                    'original_data': row.to_dict(),
                    'status': 'unknown',
                    'message': '処理済み'
                }
                report['results'].append(result)

            # PDF生成
            pdf_filename = f"{filename_prefix}_{univ}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)
            
            try:
                self.export_single_university_report_as_pdf(univ, report, pdf_path)
                pdf_files.append(pdf_path)
                logger.info(f"✅ PDF生成完了: {pdf_path}")
            except Exception as e:
                logger.error(f"❌ PDF生成エラー ({univ}): {e}")

        return pdf_files


def main():
    """メイン処理"""
    # CLI/Streamlit UI は削除済み
    return

if __name__ == "__main__":
    main()
