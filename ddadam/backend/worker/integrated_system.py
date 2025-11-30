# -*- coding: utf-8 -*-
import requests
import logging
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import time
import threading
from datetime import datetime
import json
import uuid
import multiprocessing
import unicodedata
from io import StringIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import platform

# 既存のJBA検証システムのインポート
import sys
sys.path.append('.')

# JBA検証システムのインポート
from worker.jba_verification_lib import JBAVerificationSystem, DataValidator

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
        
        # 編集ページから取得した選手名を記録（JBA照合時に優先するため）
        # キー: (university_name, player_name) -> True
        self.edited_player_names = {}
        
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
        """テキストを指定文字数で切り詰め（HTMLタグを含む場合はそのまま返す）"""
        if not isinstance(text, str):
            text = str(text)
        if pd.isna(text) or text == 'nan':
            return ""
        
        # HTMLタグを含む場合はそのまま返す（タグが壊れるのを防ぐ）
        if '<font' in text or '<b>' in text or '<i>' in text or '<u>' in text:
            return text
        
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
    
    def _get_player_name_from_edit_page(self, session, view_url, player_name_with_question):
        """編集ページから正しい選手名を取得（「?」を含む選手名を修正）"""
        try:
            # 詳細ページのURLから編集ページのURLを推測
            edit_url = view_url.replace("/view/", "/edit/")
            
            # 編集ページにアクセス
            response = session.get(edit_url, timeout=30)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # テーブルを探す
            tables = soup.find_all("table")
            
            # 「?」を含む選手名から比較用の文字列を生成
            # 例: "島? 輝" -> "島 輝"（?を除く）
            question_cleaned = player_name_with_question.replace('?', '').strip()
            
            # 候補を収集（より厳密なマッチングのため）
            candidates = []
            
            for table in tables:
                rows = table.find_all("tr")
                if len(rows) > 5:  # 選手リストの可能性
                    for row in rows:
                        # セレクトボックスから選択されている選手名を取得
                        selects = row.find_all("select")
                        player_name_from_edit = None
                        
                        for select in selects:
                            name_attr = select.get("name", "")
                            selected_option = select.find("option", selected=True)
                            if selected_option:
                                value = selected_option.get_text(strip=True)
                                if "user_id" in name_attr:
                                    if value and value != '選択してください' and '?' not in value:
                                        player_name_from_edit = value
                        
                        # 選手名が取得できた場合、マッチングを試みる
                        if player_name_from_edit:
                            # 方法1: 「?」を除いた部分が正しい名前に完全一致するか（最も厳密）
                            if question_cleaned == player_name_from_edit:
                                return player_name_from_edit
                            
                            # 方法2: 名前の後半部分（名字の後）が完全一致するか
                            # 例: "島? 輝" と "島 輝" -> " 輝" が一致
                            if ' ' in question_cleaned:
                                parts = question_cleaned.split(' ', 1)
                                if len(parts) == 2:
                                    last_part = parts[1]  # "輝"
                                    if ' ' in player_name_from_edit:
                                        correct_parts = player_name_from_edit.split(' ', 1)
                                        if len(correct_parts) == 2 and correct_parts[1] == last_part:
                                            # 名字部分の文字数が同じか、1文字差以内の場合のみ候補に追加
                                            if abs(len(parts[0]) - len(correct_parts[0])) <= 1:
                                                candidates.append(player_name_from_edit)
                            
                            # 方法3: 文字数が同じで、最初の文字以外が完全一致するか
                            if len(question_cleaned) == len(player_name_from_edit):
                                if question_cleaned[1:] == player_name_from_edit[1:]:
                                    candidates.append(player_name_from_edit)
            
            # 候補が1つだけの場合はそれを返す（複数ある場合は返さない）
            if len(candidates) == 1:
                return candidates[0]
            
            # 候補が複数ある場合は、最も類似度が高いものを返す（ただし1.0のみ）
            if len(candidates) > 1:
                from difflib import SequenceMatcher
                best_match = None
                best_similarity = 0.0
                for candidate in candidates:
                    similarity = SequenceMatcher(None, question_cleaned, candidate).ratio()
                    if similarity > best_similarity and similarity >= 1.0:
                        best_similarity = similarity
                        best_match = candidate
                if best_match:
                    return best_match
            
            return None
        except Exception:
            return None
    
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
                    print(f"🔍 CSV {i+1} レスポンスエンコーディング: {response_encoding}")
                    
                    # 複数のエンコーディングを試行
                    csv_encodings = ['utf-8', 'shift_jis', 'cp932', 'iso-2022-jp', 'euc-jp', 'utf-8-sig']
                    df = None
                    
                    for encoding in csv_encodings:
                        try:
                            if encoding == 'utf-8-sig':
                                csv_text = csv_response.content.decode('utf-8-sig')
                            else:
                                csv_text = csv_response.content.decode(encoding)
                            df = pd.read_csv(StringIO(csv_text))
                            print(f"✅ CSV {i+1} エンコーディング成功: {encoding}")
                            break
                        except (UnicodeDecodeError, pd.errors.ParserError, UnicodeError) as e:
                            print(f"⚠️ CSV {i+1} エンコーディング失敗: {encoding} - {e}")
                            continue
                    
                    if df is None:
                        print(f"❌ CSV {i+1} 全てのエンコーディングで失敗")
                        continue
                    
                    # CSV URLから詳細ページURLを推測（編集ページ参照用）
                    csv_id_match = re.search(r'/csv/id/(\d+)', csv_url)
                    view_url = None
                    if csv_id_match:
                        view_id = csv_id_match.group(1)
                        view_url = f"{self.base_url}/master-admin-game_category_teams/view/id/{view_id}"
                    
                    # 大学名を取得（文字エンコーディング対応）
                    content_disposition = csv_response.headers.get("content-disposition", "")
                    filename_match = re.search(r'filename="(.+)"', content_disposition)
                    
                    if filename_match:
                        # 文字エンコーディングを修正
                        university_name = filename_match.group(1).replace('.csv', '')
                        print(f"🔍 元の大学名: {repr(university_name)}")
                        
                        try:
                            # 複数のエンコーディングを試行
                            encodings_to_try = ['utf-8', 'shift_jis', 'cp932', 'iso-2022-jp', 'euc-jp']
                            
                            for encoding in encodings_to_try:
                                try:
                                    # バイト列に戻してから指定エンコーディングでデコード
                                    if isinstance(university_name, str):
                                        # 文字列をバイト列に変換（latin-1経由）
                                        byte_name = university_name.encode('latin-1')
                                        university_name = byte_name.decode(encoding)
                                        print(f"✅ エンコーディング成功: {encoding} -> {university_name}")
                                        break
                                except (UnicodeDecodeError, UnicodeEncodeError):
                                    continue
                            
                            # URLデコードも試行
                            import urllib.parse
                            university_name = urllib.parse.unquote(university_name)
                            
                        except Exception as e:
                            print(f"⚠️ エンコーディング変換失敗: {e}")
                            # エンコーディング変換に失敗した場合はそのまま使用
                            pass
                        
                        print(f"📝 最終大学名: {university_name}")
                    else:
                        university_name = f"大学_{i+1}"
                    
                    # 大学名の正規化（余分な文字を除去）
                    university_name = university_name.strip()
                    # よくある文字化けパターンを修正
                    university_name = university_name.replace('æ', '東').replace('å', '大').replace('é', '学')
                    university_name = university_name.replace('ç', '科').replace('è', '学').replace('ã', 'ー')
                    university_name = university_name.replace('ï', '学').replace('í', '学').replace('ó', '学')
                    
                    print(f"🎯 正規化後大学名: {university_name}")
                    
                    # 「?」を含む選手名を編集ページから修正（可能な場合）
                    try:
                        # 選手名カラムを推定
                        player_name_columns = []
                        for col in df.columns:
                            col_lower = str(col).lower()
                            if any(keyword in col_lower for keyword in ['選手', '氏名', 'name', '名前']):
                                player_name_columns.append(col)
                        if player_name_columns and view_url:
                            player_name_col = player_name_columns[0]
                            corrected_count = 0
                            for idx, row in df.iterrows():
                                player_name = str(row[player_name_col]) if pd.notna(row[player_name_col]) else ""
                                if player_name and '?' in player_name:
                                    correct_name = self._get_player_name_from_edit_page(session, view_url, player_name)
                                    if correct_name:
                                        df.at[idx, player_name_col] = correct_name
                                        corrected_count += 1
                                        # 編集ページから取得した選手名を記録（JBA照合時に優先するため）
                                        self.edited_player_names[(university_name, correct_name)] = True
                                        print(f"  ✅ 選手名を修正: {player_name} → {correct_name} (編集ページから取得、JBA照合時に優先)")
                            if corrected_count > 0:
                                print(f"  ✅ {corrected_count} 件の選手名を編集ページから修正しました（JBA照合時に優先されます）")
                    except Exception as e:
                        print(f"  ⚠️ 編集ページからの名前修正に失敗: {e}")
                    
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
    
    def process_tournament_data(self, df, university_name=None, job_id=None, progress_callback=None):
        """大会データをJBA照合で処理（並列処理対応）"""
        
        if df is None or df.empty:
            print("❌ 処理するデータがありません")
            return None
        
        if self.use_parallel:
            print(f"⚡ 並列処理を使用（{self.max_workers}スレッド）")
            return self._process_tournament_data_parallel(df, university_name, job_id=job_id, progress_callback=progress_callback)
        else:
            print("🔄 順次処理を使用")
            return self._process_tournament_data_sequential(df, university_name, job_id=job_id, progress_callback=progress_callback)
    
    def _process_tournament_data_sequential(self, df, university_name=None, job_id=None, progress_callback=None):
        """順次処理でJBA照合"""
        print("🔍 JBA照合処理を開始...")
        
        # 大学ごとに処理
        universities = df['大学名'].unique() if '大学名' in df.columns else [university_name or "Unknown"]
        
        all_results = []
        total_universities = len(universities)
        
        for idx, univ in enumerate(universities):
            print(f"🏫 {univ} を処理中...")
            
            # 進捗を更新（大学ごと）
            if progress_callback:
                progress = idx / total_universities
                message = f"{univ} を処理中... ({idx+1}/{total_universities})"
                progress_callback(progress, message)
            
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
                
                # カナ名を取得
                kana_name = None
                kana_columns = ['カナ名', 'カナ', 'kana', 'Kana', 'フリガナ', 'ふりがな']
                for col in kana_columns:
                    if col in row.index and pd.notna(row[col]):
                        kana_name = str(row[col]).strip()
                        break
                
                # CSVから背番号（No）を取得（数字のみ有効）
                # 数値以外の値（「トレーナー」「学生コーチ」など）は背番号がない人として扱う
                player_no = None
                no_columns = ['No', 'NO', 'no', '背番号', 'No.', '番号', 'ナンバー', '#']
                for col in no_columns:
                    if col in row.index and pd.notna(row[col]):
                        value = str(row[col]).strip()
                        # 数字のみ有効（純粋な整数または小数点を含む数値のみ）
                        # 数字以外の文字（例: "10A", "10-1", "トレーナー"）が含まれている場合は無視
                        if value.isdigit():
                            # 整数のみ
                            player_no = value
                            break
                        elif '.' in value and value.replace('.', '').isdigit() and value.count('.') == 1:
                            # 小数点を含む数値（例: "10.5"）のみ
                            player_no = value
                            break
                        # それ以外（数字以外の文字を含む）はplayer_no = Noneのまま
                
                # 編集ページから取得した選手名かチェック
                # 編集ページから取得した選手名は「CSVの正しい選手名」であって、
                # JBAの選手名と一致するとは限らないため、通常の閾値（0.6）を使用
                is_edited_from_html = False
                if univ and player_name:
                    is_edited_from_html = self.edited_player_names.get((univ, player_name), False)
                
                # 通常の閾値（0.6）を使用（編集ページから取得した選手名でも同様）
                # 編集ページから取得した選手名は「正しい」CSVの選手名なので、
                # JBA照合時は通常の閾値で柔軟に照合する（「栁本 晴暖」と「柳本 晴暖」のような類似文字の違いでも照合できる）
                threshold = 0.6
                
                # JBA照合
                verification_result = self.jba_system.verify_player_info(
                    player_name, None, univ, get_details=True, threshold=threshold, player_no=player_no, kana_name=kana_name
                )
                
                result = {
                    'index': index,
                    'original_data': row.to_dict(),
                    'verification_result': verification_result,
                    'status': verification_result['status'],
                    'university': univ,
                    'player_no': player_no  # 背番号を結果に含める
                }
                
                # JBA登録あり（〇）の場合
                if verification_result['status'] == 'match':
                    if 'jba_data' in verification_result:
                        jba_data = verification_result['jba_data']
                        is_valid, validation_issues, school_corrections = self.validator.validate_player_data(jba_data)
                        
                        corrected_data = row.to_dict().copy()
                        
                        # 変更されたフィールドを追跡（赤字表示用）
                        changed_fields = set()
                        
                        # 背番号がある場合のみ身長・体重を照合
                        if player_no:
                            # 身長の照合（5cm以上差があったらJBAの値に変更）
                            if 'height' in jba_data and jba_data['height']:
                                try:
                                    jba_height_str = str(jba_data['height']).replace('cm', '').strip()
                                    # 値が空、0.0、nanの場合は空欄のまま
                                    if jba_height_str and jba_height_str.lower() not in ['', 'nan', 'none', '0', '0.0']:
                                        jba_height = float(jba_height_str)
                                        csv_height_str = str(corrected_data.get('身長', '')).replace('cm', '').strip()
                                        if csv_height_str and csv_height_str.replace('.', '').isdigit():
                                            csv_height = float(csv_height_str)
                                            height_diff = abs(csv_height - jba_height)
                                            if height_diff >= 5.0:
                                                corrected_data['身長'] = f"{jba_height}cm"
                                                changed_fields.add('身長')
                                        else:
                                            # CSVに身長がない場合はJBAの値を使用
                                            corrected_data['身長'] = f"{jba_height}cm"
                                            changed_fields.add('身長')
                                except (ValueError, AttributeError):
                                    # パースエラーの場合は空欄のまま（何もしない）
                                    pass
                            
                            # 体重の照合（5kg以上差があったらJBAの値に変更）
                            if 'weight' in jba_data and jba_data['weight']:
                                try:
                                    jba_weight_str = str(jba_data['weight']).replace('kg', '').strip()
                                    # 値が空、0.0、nanの場合は空欄のまま
                                    if jba_weight_str and jba_weight_str.lower() not in ['', 'nan', 'none', '0', '0.0']:
                                        jba_weight = float(jba_weight_str)
                                        csv_weight_str = str(corrected_data.get('体重', '')).replace('kg', '').strip()
                                        if csv_weight_str and csv_weight_str.replace('.', '').isdigit():
                                            csv_weight = float(csv_weight_str)
                                            weight_diff = abs(csv_weight - jba_weight)
                                            if weight_diff >= 5.0:
                                                corrected_data['体重'] = f"{jba_weight}kg"
                                                changed_fields.add('体重')
                                        else:
                                            # CSVに体重がない場合はJBAの値を使用
                                            corrected_data['体重'] = f"{jba_weight}kg"
                                            changed_fields.add('体重')
                                except (ValueError, AttributeError):
                                    # パースエラーの場合は空欄のまま（何もしない）
                                    pass
                        
                        # 学年の照合（背番号がある場合のみ、JBAが正しいので異なる場合はJBAに合わせる）
                        # 背番号がない場合は選手名とカナ名だけで照合するため、学年の照合は不要
                        if player_no and 'grade' in jba_data and jba_data['grade']:
                            original_grade = str(corrected_data.get('学年', '')).strip()
                            jba_grade = str(jba_data['grade']).strip()
                            # 数字部分だけを抽出して比較（「2」と「大学2年」などに対応）
                            import re
                            original_grade_match = re.search(r'(\d+(?:\.\d+)?)', original_grade)
                            jba_grade_match = re.search(r'(\d+(?:\.\d+)?)', jba_grade)
                            
                            if original_grade_match and jba_grade_match:
                                # 数字部分が一致しているか確認
                                original_grade_num = float(original_grade_match.group(1))
                                jba_grade_num = float(jba_grade_match.group(1))
                                if abs(original_grade_num - jba_grade_num) >= 0.1:  # 0.1以上の差がある場合のみ変更
                                    corrected_data['学年'] = jba_grade
                                    changed_fields.add('学年')
                                # 数字が一致していれば正しい判定（changed_fieldsに追加しない）
                            elif original_grade != jba_grade:
                                # 数字が見つからない場合は文字列比較
                                corrected_data['学年'] = jba_grade
                                changed_fields.add('学年')
                        
                        # 名前とカナ名はJBAのデータで上書き（JBAが正しい）
                        if 'name' in jba_data and jba_data['name']:
                            jba_name = str(jba_data['name']).strip()
                            # 全角スペースを半角スペースに統一
                            jba_name = unicodedata.normalize('NFKC', jba_name)
                            csv_name = str(corrected_data.get('選手名', corrected_data.get('氏名', ''))).strip()
                            # 編集ページから取得した選手名かチェック（優先して上書きしない）
                            is_edited_from_html = False
                            if univ and csv_name:
                                is_edited_from_html = self.edited_player_names.get((univ, csv_name), False)
                            if jba_name != csv_name and not is_edited_from_html:
                                corrected_data['選手名'] = jba_name
                                if '氏名' in corrected_data:
                                    corrected_data['氏名'] = jba_name
                                changed_fields.add('選手名')
                        
                        if 'kana_name' in jba_data and jba_data['kana_name']:
                            jba_kana = str(jba_data['kana_name']).strip()
                            # 全角スペースを半角スペースに統一
                            jba_kana = unicodedata.normalize('NFKC', jba_kana)
                            csv_kana = str(corrected_data.get('カナ名', '')).strip()
                            if jba_kana != csv_kana:
                                corrected_data['カナ名'] = jba_kana
                                changed_fields.add('カナ名')
                        
                        # ポジション・出身校・背番号はCSVのデータをそのまま使用（変更しない）
                        
                        # 変更されたフィールド情報を保存
                        result['changed_fields'] = changed_fields
                    
                        result['correction'] = corrected_data
                        result['message'] = 'JBA登録あり（〇）'
                    else:
                        result['correction'] = None
                        result['message'] = 'JBA登録あり（〇）'
                
                # JBA登録なし（×）の場合
                elif verification_result['status'] == 'not_found':
                    result['correction'] = None
                    result['message'] = 'JBA登録なし（×）'
                
                # その他の場合（エラーなど）
                else:
                    result['correction'] = None
                    result['message'] = verification_result.get('message', '照合できませんでした')
                
                results.append(result)
            
            all_results.extend(results)
            
            # 進捗を更新（大学処理完了時）
            if progress_callback:
                progress = (idx + 1) / total_universities
                message = f"{univ} を処理完了 ({idx+1}/{total_universities})"
                progress_callback(progress, message)
        
        # 結果をコンパクトに表示
        print(f"📊 処理結果: {len(all_results)}選手")
        print(f"📊 処理大学数: {len(universities)}")
        
        return all_results
    
    def _process_tournament_data_parallel(self, df, university_name=None, job_id=None, progress_callback=None):
        """並列処理でJBA照合（大学ごとに最適化）"""
        import concurrent.futures
        import time
        import logging
        logger = logging.getLogger(__name__)
        
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
        start_time = time.time()
        total_players = len(df)
        
        logger.info(f"🚀 処理開始: {len(universities)} 大学, {total_players} 選手")
        
        # 🚀 パフォーマンス改善2: 大学間の並列処理（適度な並列度で）
        def process_single_university(univ):
            """単一大学の処理（並列化用）"""
            try:
                logger.info(f"🏫 {univ} を処理中...")
                
                # この大学の選手を抽出
                if '大学名' in df.columns:
                    univ_data = df[df['大学名'] == univ].copy()
                else:
                    univ_data = df.copy()
                
                # ★ この大学のチーム情報を1回だけ事前取得（リアルタイム性を保つ）
                logger.info(f"📥 {univ} のチーム情報を取得中（リアルタイム）...")
                preload_start = time.time()
                self._preload_university_teams(univ)
                preload_elapsed = time.time() - preload_start
                logger.info(f"✅ {univ} のチーム取得完了: {preload_elapsed:.2f}秒")
                
                # ★ この大学の選手を並列処理（チーム情報はキャッシュから取得）
                logger.info(f"⚡ {univ} の {len(univ_data)} 名を処理中...")
                univ_results = self._process_university_players_parallel(univ_data, univ)
                
                logger.info(f"✅ {univ} 完了: {len(univ_results)} 名処理")
                return univ_results
            except Exception as e:
                logger.error(f"❌ {univ} の処理でエラー: {e}", exc_info=True)
                return []
        
        # 大学間を並列処理（適度な並列度で、レート制限対策）
        # 大学数が多い場合は並列度を制限（最大5大学まで同時処理）
        max_univ_workers = min(self.max_workers, len(universities), 5)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_univ_workers) as executor:
            futures = {executor.submit(process_single_university, univ): univ for univ in universities}
            
            completed_universities = 0
            total_universities = len(universities)
            
            for future in concurrent.futures.as_completed(futures):
                univ = futures[future]
                try:
                    univ_results = future.result()
                    all_results.extend(univ_results)
                    completed_universities += 1
                    
                    # 進捗を更新（大学ごと）
                    if progress_callback:
                        progress = completed_universities / total_universities
                        message = f"{univ} を処理完了 ({completed_universities}/{total_universities})"
                        progress_callback(progress, message)
                except Exception as e:
                    logger.error(f"❌ {univ} の処理で例外: {e}", exc_info=True)
                    completed_universities += 1
                    if progress_callback:
                        progress = completed_universities / total_universities
                        message = f"{univ} の処理でエラー ({completed_universities}/{total_universities})"
                        progress_callback(progress, message)
        
        elapsed_time = time.time() - start_time
        self.performance_stats['total_time'] = elapsed_time
        
        # JBA照合統計を表示
        match_count = len([r for r in all_results if r.get('status') == 'match'])
        not_found_count = len([r for r in all_results if r.get('status') == 'not_found'])
        error_count = len([r for r in all_results if r.get('status') == 'error'])
        
        print(f"📊 JBA照合統計:")
        print(f"   総選手数: {len(all_results)}")
        print(f"   JBA登録あり（〇）: {match_count}")
        print(f"   JBA登録なし（×）: {not_found_count}")
        print(f"   エラー: {error_count}")
        print(f"   総処理時間: {elapsed_time:.2f}秒")
        
        return all_results
    
    def _preload_university_teams(self, university_name):
        """大学のチーム情報とメンバー情報を事前に1回だけ取得（リアルタイム性を保つ）"""
        import logging
        import concurrent.futures
        logger = logging.getLogger(__name__)
        
        # 検索名を取得
        search_variations = self.jba_system.get_search_variations(university_name)
        if not search_variations:
            return
        
        search_name = search_variations[0]
        
        # キャッシュに既にある場合はスキップ
        if search_name in self.jba_system.teams_cache:
            logger.debug(f"💾 {university_name} のチーム情報は既にキャッシュにあります")
            # メンバー情報も既に取得済みか確認
            teams = self.jba_system.teams_cache[search_name]
            all_cached = True
            for team in teams:
                if team['url'] not in self.jba_system.team_members_cache:
                    all_cached = False
                    break
            if all_cached:
                logger.debug(f"💾 {university_name} のメンバー情報も既にキャッシュにあります")
                return
        
        # チーム情報を取得（1回だけ）
        try:
            teams = self.jba_system._search_teams_by_university_silent(search_name)
            # キャッシュに保存
            self.jba_system.teams_cache[search_name] = teams
            logger.debug(f"✅ {university_name} のチーム情報を取得: {len(teams)} チーム")
            
            # 🚀 パフォーマンス改善1: メンバー情報も事前取得（並列化）
            if teams:
                logger.debug(f"📥 {university_name} のメンバー情報を事前取得中...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(teams), 5)) as executor:
                    futures = []
                    for team in teams:
                        # 既にキャッシュにある場合はスキップ
                        if team['url'] not in self.jba_system.team_members_cache:
                            future = executor.submit(
                                self.jba_system._get_team_members_silent, 
                                team['url']
                            )
                            futures.append((future, team['url']))
                    
                    # 結果をキャッシュに保存
                    for future, team_url in futures:
                        try:
                            team_data = future.result()
                            self.jba_system.team_members_cache[team_url] = team_data
                        except Exception as e:
                            logger.error(f"❌ メンバー情報取得エラー ({team_url}): {e}")
                
                logger.debug(f"✅ {university_name} のメンバー情報を事前取得完了")
        except Exception as e:
            logger.error(f"❌ {university_name} のチーム検索エラー: {e}")
    
    def _process_university_players_parallel(self, univ_df, univ):
        """大学の選手を並列処理（チーム情報はキャッシュから取得）"""
        import concurrent.futures
        import time
        import logging
        logger = logging.getLogger(__name__)
        
        # 選手データを準備
        player_data = []
        name_columns = ['選手名', '氏名', 'name', 'Name']
        available_name_cols = [col for col in name_columns if col in univ_df.columns]
        
        if available_name_cols:
            name_col = available_name_cols[0]
            univ_df[name_col] = univ_df[name_col].astype(str).str.strip()
            valid_players = univ_df[pd.notna(univ_df[name_col]) & (univ_df[name_col] != '')]
            for index, row in valid_players.iterrows():
                player_name = str(row[name_col]).strip()
                if player_name:
                    player_data.append((index, row, univ, player_name))
        else:
            # フォールバック
            for index, row in univ_df.iterrows():
                player_name = None
                for col in name_columns:
                    if col in univ_df.columns and pd.notna(row[col]):
                        player_name = str(row[col]).strip()
                        break
                if player_name:
                    player_data.append((index, row, univ, player_name))
        
        if not player_data:
            return []
        
        # 並列処理でJBA照合
        optimal_workers = min(self.max_workers, len(player_data), self.cpu_count * 4)
        results = []
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
                    results.append(result)
                    
                    # 大学ごとの結果を一時保存
                    univ = result.get('university', 'Unknown')
                    if univ not in university_results:
                        university_results[univ] = []
                    university_results[univ].append(result)
                    
                except Exception as e:
                    logger.error(f"❌ 処理中にエラーが発生しました: {str(e)}", exc_info=True)
        
        # 大学ごとの結果を一時保存
        for univ_name, univ_results in university_results.items():
            self._save_temp_results(univ_name, univ_results)
        
        return results
    
    def _process_single_player_parallel(self, index, row, univ, player_name):
        """単一選手の並列処理（キャッシュ付き）"""
        import logging
        logger = logging.getLogger(__name__)
        
        # 先に背番号を取得（キャッシュキーに含めるため）
        player_no = None
        no_columns = ['No', 'NO', 'no', '背番号', 'No.', '番号', 'ナンバー', '#']
        for col in no_columns:
            if col in row.index and pd.notna(row[col]):
                value = str(row[col]).strip()
                # 数字のみ有効（純粋な整数または小数点を含む数値のみ）
                # 数字以外の文字（例: "10A", "10-1", "トレーナー"）が含まれている場合は無視
                if value.isdigit():
                    # 整数のみ
                    player_no = value
                    break
                elif '.' in value and value.replace('.', '').isdigit() and value.count('.') == 1:
                    # 小数点を含む数値（例: "10.5"）のみ
                    player_no = value
                    break
                # それ以外（数字以外の文字を含む）はplayer_no = Noneのまま
        
        # キャッシュキーを生成（背番号を含める）
        cache_key = f"player_{player_name}_{univ}_{player_no or 'no_number'}"
        cached_result = self._get_cached_data(cache_key)
        
        if cached_result:
            # キャッシュから取得
            cached_result['index'] = index
            cached_result['original_data'] = row.to_dict()
            cached_result['player_no'] = player_no  # 背番号を確実に設定
            return cached_result
        
        # 実際にJBA照合を実行
        # 🚀 パフォーマンス改善: ログ出力を削減
        logger.debug(f"🔍 JBA照合開始: {player_name} ({univ}, 背番号: {player_no or 'なし'})")
        
        start_time = time.time()
        try:
            
            # カナ名を取得
            kana_name = None
            kana_columns = ['カナ名', 'カナ', 'kana', 'Kana', 'フリガナ', 'ふりがな']
            for col in kana_columns:
                if col in row.index and pd.notna(row[col]):
                    kana_name = str(row[col]).strip()
                    break
            
            # 🔍 デバッグログ: 背番号情報
            if player_no:
                logger.debug(f"  - 背番号: {player_no}")
            else:
                logger.debug(f"  - 背番号: なし（コーチ扱い）")
            
            # 編集ページから取得した選手名かチェック
            # 編集ページから取得した選手名は「CSVの正しい選手名」であって、
            # JBAの選手名と一致するとは限らないため、通常の閾値（0.6）を使用
            is_edited_from_html = False
            if univ and player_name:
                is_edited_from_html = self.edited_player_names.get((univ, player_name), False)
            
            # 通常の閾値（0.6）を使用（編集ページから取得した選手名でも同様）
            # 編集ページから取得した選手名は「正しい」CSVの選手名なので、
            # JBA照合時は通常の閾値で柔軟に照合する（「栁本 晴暖」と「柳本 晴暖」のような類似文字の違いでも照合できる）
            threshold = 0.6
            
            # 詳細情報を取得（学年は背番号の有無に関わらず必要）
            verification_result = self.jba_system.verify_player_info(
                player_name, None, univ, get_details=True, threshold=threshold, player_no=player_no, kana_name=kana_name
            )
            
            # 結果をログに記録
            status = verification_result.get('status')
            logger.debug(f"✅ JBA照合完了: {player_name} -> {status}")
        except Exception as e:
            # 🔍 デバッグログ: 例外詳細を強制出力（トレースバック含む）
            logger.error(f"🔍🔍🔍 DEBUG: 例外発生！")
            logger.error(f"  - 例外タイプ: {type(e).__name__}")
            logger.error(f"  - 例外メッセージ: {str(e)}")
            logger.error(f"  - トレースバック:", exc_info=True)
            
            logger.error(f"❌ JBA照合エラー: {player_name} - {e}")
            verification_result = {
                'status': 'error',
                'message': f'JBA照合エラー: {str(e)}',
                'jba_data': None
            }
        end_time = time.time()
        
        # 処理時間をログに記録（DEBUG レベル）
        logger.debug(f"⏱️ 処理時間: {end_time - start_time:.2f}秒")
        
        # パフォーマンス統計を更新
        self.performance_stats['requests_count'] += 1
        response_time = end_time - start_time
        self.performance_stats['avg_response_time'] = (
            (self.performance_stats['avg_response_time'] * (self.performance_stats['requests_count'] - 1) + response_time) 
            / self.performance_stats['requests_count']
        )
        
        # player_no は既に取得済み（キャッシュキー生成時に取得）
        
        result = {
            'index': index,
            'original_data': row.to_dict(),
            'verification_result': verification_result,
            'status': verification_result['status'],
            'university': univ,
            'player_no': player_no  # 背番号を結果に含める
        }
        
        # JBA照合結果の詳細処理
        if verification_result['status'] == 'match':
            if 'jba_data' in verification_result:
                jba_data = verification_result['jba_data']
                corrected_data = row.to_dict().copy()
                
                # 変更されたフィールドを追跡（赤字表示用）
                changed_fields = set()
                
                # 背番号がある場合のみ身長・体重を照合
                if player_no:
                    # 身長の照合（5cm以上差があったらJBAの値に変更）
                    if 'height' in jba_data and jba_data['height']:
                        try:
                            jba_height_str = str(jba_data['height']).replace('cm', '').strip()
                            # 値が空、0.0、nanの場合は空欄のまま
                            if jba_height_str and jba_height_str.lower() not in ['', 'nan', 'none', '0', '0.0']:
                                jba_height = float(jba_height_str)
                                csv_height_str = str(corrected_data.get('身長', '')).replace('cm', '').strip()
                                if csv_height_str and csv_height_str.replace('.', '').isdigit():
                                    csv_height = float(csv_height_str)
                                    height_diff = abs(csv_height - jba_height)
                                    if height_diff >= 5.0:
                                        corrected_data['身長'] = f"{jba_height}cm"
                                        changed_fields.add('身長')
                                else:
                                    # CSVに身長がない場合はJBAの値を使用
                                    corrected_data['身長'] = f"{jba_height}cm"
                                    changed_fields.add('身長')
                        except (ValueError, AttributeError):
                            # パースエラーの場合は空欄のまま（何もしない）
                            pass
                    
                    # 体重の照合（5kg以上差があったらJBAの値に変更）
                    if 'weight' in jba_data and jba_data['weight']:
                        try:
                            jba_weight_str = str(jba_data['weight']).replace('kg', '').strip()
                            # 値が空、0.0、nanの場合は空欄のまま
                            if jba_weight_str and jba_weight_str.lower() not in ['', 'nan', 'none', '0', '0.0']:
                                jba_weight = float(jba_weight_str)
                                csv_weight_str = str(corrected_data.get('体重', '')).replace('kg', '').strip()
                                if csv_weight_str and csv_weight_str.replace('.', '').isdigit():
                                    csv_weight = float(csv_weight_str)
                                    weight_diff = abs(csv_weight - jba_weight)
                                    if weight_diff >= 5.0:
                                        corrected_data['体重'] = f"{jba_weight}kg"
                                        changed_fields.add('体重')
                                else:
                                    # CSVに体重がない場合はJBAの値を使用
                                    corrected_data['体重'] = f"{jba_weight}kg"
                                    changed_fields.add('体重')
                        except (ValueError, AttributeError):
                            # パースエラーの場合は空欄のまま（何もしない）
                            pass
                
                # 学年の照合（背番号がある場合のみ、JBAが正しいので異なる場合はJBAに合わせる）
                # 背番号がない場合は選手名とカナ名だけで照合するため、学年の照合は不要
                if player_no and 'grade' in jba_data and jba_data['grade']:
                    original_grade = str(corrected_data.get('学年', '')).strip()
                    jba_grade = str(jba_data['grade']).strip()
                    # 数字部分だけを抽出して比較（「2」と「大学2年」などに対応）
                    import re
                    original_grade_match = re.search(r'(\d+(?:\.\d+)?)', original_grade)
                    jba_grade_match = re.search(r'(\d+(?:\.\d+)?)', jba_grade)
                    
                    if original_grade_match and jba_grade_match:
                        # 数字部分が一致しているか確認
                        original_grade_num = float(original_grade_match.group(1))
                        jba_grade_num = float(jba_grade_match.group(1))
                        if abs(original_grade_num - jba_grade_num) >= 0.1:  # 0.1以上の差がある場合のみ変更
                            corrected_data['学年'] = jba_grade
                            changed_fields.add('学年')
                        # 数字が一致していれば正しい判定（changed_fieldsに追加しない）
                    elif original_grade != jba_grade:
                        # 数字が見つからない場合は文字列比較
                        corrected_data['学年'] = jba_grade
                        changed_fields.add('学年')
                
                # 名前とカナ名はJBAのデータで上書き（JBAが正しい）
                if 'name' in jba_data and jba_data['name']:
                    jba_name = str(jba_data['name']).strip()
                    # 全角スペースを半角スペースに統一
                    jba_name = unicodedata.normalize('NFKC', jba_name)
                    csv_name = str(corrected_data.get('選手名', corrected_data.get('氏名', ''))).strip()
                    # 編集ページから取得した選手名かチェック（優先して上書きしない）
                    is_edited_from_html = False
                    if univ and csv_name:
                        is_edited_from_html = self.edited_player_names.get((univ, csv_name), False)
                    if jba_name != csv_name and not is_edited_from_html:
                        corrected_data['選手名'] = jba_name
                        if '氏名' in corrected_data:
                            corrected_data['氏名'] = jba_name
                        changed_fields.add('選手名')
                
                if 'kana_name' in jba_data and jba_data['kana_name']:
                    jba_kana = str(jba_data['kana_name']).strip()
                    # 全角スペースを半角スペースに統一
                    jba_kana = unicodedata.normalize('NFKC', jba_kana)
                    csv_kana = str(corrected_data.get('カナ名', '')).strip()
                    if jba_kana != csv_kana:
                        corrected_data['カナ名'] = jba_kana
                        changed_fields.add('カナ名')
                
                # ポジション・出身校・背番号はCSVのデータをそのまま使用（変更しない）
                
                # 変更されたフィールド情報を保存
                result['changed_fields'] = changed_fields
            
                result['correction'] = corrected_data
                result['message'] = 'JBA登録あり（〇）'
            else:
                result['correction'] = None
                result['message'] = 'JBA登録あり（〇）'
        
        elif verification_result['status'] == 'not_found':
            result['correction'] = None
            result['message'] = 'JBA登録なし（×）'
        
        else:
            result['correction'] = None
            result['message'] = verification_result.get('message', '照合できませんでした')
        
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
            # CSVの順番を保持するため、indexでソート
            univ_results.sort(key=lambda x: x.get('index', 0))
            
            # 重複チェック: 同じ大学名、同じ選手名、同じ種類（選手/スタッフ）の組み合わせで重複をチェック
            # 選手（背番号あり）とスタッフ（背番号なし）は別々のものとして扱う
            seen_players = {}
            deduplicated_results = []
            
            for result in univ_results:
                original_data = result.get('original_data', {})
                player_name = str(original_data.get('選手名', original_data.get('氏名', ''))).strip()
                player_no = result.get('player_no')  # 背番号（数字のみ有効）
                
                # 選手名が空の場合はスキップ
                if not player_name:
                    deduplicated_results.append(result)
                    continue
                
                # 選手（背番号あり）とスタッフ（背番号なし）を区別するため、
                # キーに背番号の有無を含める
                has_player_no = player_no is not None
                key = (univ, player_name, has_player_no)
                
                if key in seen_players:
                    # 重複が見つかった場合（同じ大学名、同じ選手名、同じ種類）
                    # 最初に見つかった方を保持（indexが小さい方）
                    existing_result = seen_players[key]
                    if result.get('index', 0) < existing_result.get('index', 0):
                        # 現在のレコードの方がindexが小さい場合は、既存のレコードを置き換え
                        deduplicated_results.remove(existing_result)
                        deduplicated_results.append(result)
                        seen_players[key] = result
                    # 既存のレコードの方がindexが小さい場合は、現在のレコードをスキップ
                    else:
                        continue
                else:
                    # 重複がない場合は追加（選手とスタッフは別々のものとして扱われる）
                    deduplicated_results.append(result)
                    seen_players[key] = result
            
            # 重複除去後の結果をindexでソート（順番を保持）
            deduplicated_results.sort(key=lambda x: x.get('index', 0))
            
            # 統計情報を計算
            total_players = len(deduplicated_results)
            match_count = len([r for r in deduplicated_results if r['status'] == 'match'])
            not_found_count = len([r for r in deduplicated_results if r['status'] == 'not_found'])
            
            # レポートデータを作成
            report_data = {
                'university': univ,
                'total_players': total_players,
                'match_count': match_count,
                'not_found_count': not_found_count,
                'match_rate': (match_count / total_players * 100) if total_players > 0 else 0,
                'results': deduplicated_results
            }
            
            reports[univ] = report_data
        
        return reports
    
    def export_all_university_reports_as_pdf(self, reports, output_path="all_universities_report.pdf", max_rows_per_page=100):
        """全大学レポートをコンパクトなPDFで出力（画像の形式に準拠）"""
        # A4横向きで作成（50行目まで入るように余白を完全にゼロに）
        # ReportLabでは明示的に0を指定する必要がある
        # 各大学の総ページ数を事前に計算
        univ_total_pages = {}  # {univ_name: total_pages}
        
        doc = SimpleDocTemplate(output_path, pagesize=landscape(A4), 
                               leftMargin=0, rightMargin=0,
                               topMargin=0, bottomMargin=0)  # 余白を完全にゼロにして50行目まで入るように
        styles = getSampleStyleSheet()
        elements = []
        
        # 各大学の総ページ数を事前に計算
        univ_page_info = {}  # {univ_name: {'total_pages': int, 'start_page': int}}
        current_page = 1
        
        for univ_name, report in reports.items():
            results = report["results"]
            results.sort(key=lambda x: x.get('index', 0))
            total_rows = len(results)
            max_rows_per_page = 50
            if total_rows <= max_rows_per_page:
                rows_per_page = total_rows
            else:
                rows_per_page = max_rows_per_page
            total_pages = (total_rows + rows_per_page - 1) // rows_per_page
            univ_page_info[univ_name] = {
                'total_pages': total_pages,
                'start_page': current_page
            }
            current_page += total_pages
        
        # 現在のページがどの大学のページかを追跡
        current_univ_index = 0
        current_univ_page = 0
        univ_names_list = list(reports.keys())
        
        # ページ番号を表示するコールバック関数
        def add_page_number(canvas, doc):
            """各ページの右下にページ番号を追加"""
            nonlocal current_univ_index, current_univ_page
            
            page_num = canvas.getPageNumber()
            
            # 現在のページがどの大学のページかを判定
            if current_univ_index < len(univ_names_list):
                univ_name = univ_names_list[current_univ_index]
                univ_info = univ_page_info.get(univ_name, {})
                total_pages = univ_info.get('total_pages', 1)
                start_page = univ_info.get('start_page', 1)
                
                # 現在の大学内でのページ番号を計算
                univ_page_num = page_num - start_page + 1
                
                # ページ番号を表示（例：1/2）
                canvas.saveState()
                canvas.setFont(getattr(self, 'default_font', 'MS-Gothic'), 9)
                # 横向きA4のサイズ: 297mm x 210mm
                # 右下の位置: 右端から10mm、下端から5mm
                page_text = f"{univ_page_num}/{total_pages}"
                canvas.drawRightString(210*mm - 10*mm, 5*mm, page_text)
                canvas.restoreState()
                
                # 次のページで大学が変わるかチェック
                if univ_page_num >= total_pages:
                    current_univ_index += 1
                    current_univ_page = 0
        
        # onPageコールバックを設定
        doc.onPage = add_page_number
        
        # カスタムスタイル（文字を大きく、100行収めるため行間を調整）
        compact_style = ParagraphStyle(
            'Compact',
            parent=styles['Normal'],
            fontSize=8,  # 6pt → 8ptに増加
            leading=6,   # 行間を6ptに設定（100行収めるため）
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        # 長いテキスト用のフォントスタイル（選手名、カナ名用）
        small_compact_style = ParagraphStyle(
            'SmallCompact',
            parent=styles['Normal'],
            fontSize=7.5,  # 4.5pt → 7.5ptに増加
            leading=6,      # 行間を6ptに設定
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        # 出身校用のフォントスタイル
        extra_small_compact_style = ParagraphStyle(
            'ExtraSmallCompact',
            parent=styles['Normal'],
            fontSize=7,   # 4pt → 7ptに増加
            leading=6,     # 行間を6ptに設定
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )

        # 学部用のフォントスタイル
        department_compact_style = ParagraphStyle(
            'DepartmentCompact',
            parent=styles['Normal'],
            fontSize=7,   # 4.0pt → 7ptに増加
            leading=6,     # 行間を6ptに設定
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        title_style = ParagraphStyle(
            'TitleCompact',
            parent=styles['Title'],
            fontSize=10,  # 8pt → 10ptに増加
            leading=11,   # 行間を調整
            fontName=getattr(self, 'default_font', 'MS-Gothic')
        )
        
        # タイトルは削除（もっと上に詰めるため）
        
        # デバッグ情報
        print(f"📝 PDF生成開始 - 使用フォント: {getattr(self, 'default_font', 'Unknown')}")
        print(f"📊 レポート数: {len(reports)}")
        
        # データ数に応じてフォーマットを自動調整（エクセルの1ページに印刷機能のように）
        # 横向きA4の高さ: 約210mm = 約595pt
        # マージン: 上0 + 下0 = 0pt（余白完全ゼロ）
        # 大学名ヘッダー: 約8pt（7pt + leading 8pt、50行目まで入るため）
        # 利用可能な高さ: 595 - 0 - 8 = 約587pt（余白完全ゼロにより最大限に）
        available_height_pt = 587
        
        # 変更点を収集するリスト
        all_changes = []  # [{'univ': str, 'player_name': str, 'field': str, 'csv_value': str, 'corrected_value': str, 'source': str}]
        
        # 各大学のレポート（コンパクトな表形式）
        for i, (univ_name, report) in enumerate(reports.items()):
            # 大学名ヘッダー（最小限、タイトルは削除して上に詰める）
            
            # 選手データをページング（CSVの順番を保持するため、indexでソート）
            results = report["results"]
            results.sort(key=lambda x: x.get('index', 0))
            
            # データ行数に応じて1ページあたりの行数を決定
            # 少ない場合は1ページに全て収める、多い場合は分割
            total_rows = len(results)
            if total_rows <= max_rows_per_page:
                # 1ページに収まる場合、データ数に応じてフォーマットを調整
                rows_per_page = total_rows
            else:
                # 1ページに収まらない場合、max_rows_per_pageで分割
                rows_per_page = max_rows_per_page
            
            total_pages = (total_rows + rows_per_page - 1) // rows_per_page
            
            for page_num in range(total_pages):
                # 各ページのテーブル直前に大学名とページ情報を表示
                # 大学名から括弧内の情報（例：「（100行）」）を除去
                univ_name_clean = univ_name
                import re
                # 括弧とその中身を除去（例：「流通経済大学（100行）」→「流通経済大学」）
                univ_name_clean = re.sub(r'[（(].*?[）)]', '', univ_name_clean).strip()
                
                if total_pages > 1:
                    # 複数ページの場合: 【○○大学】ページ X/Y
                    univ_header = f"【{univ_name_clean}】ページ {page_num + 1}/{total_pages}"
                else:
                    # 1ページのみの場合: 【○○大学】
                    univ_header = f"【{univ_name_clean}】"
                
                # 大学名ヘッダーのフォントサイズを大きくする
                univ_header_style = ParagraphStyle(
                    f'UnivHeader_{i}',
                    parent=styles['Normal'],
                    fontSize=12,  # 大きくする（7 → 12）
                    leading=14,   # 行間も大きくする（8 → 14）
                    fontName=getattr(self, 'default_font', 'MS-Gothic')
                )
                elements.append(Paragraph(univ_header, univ_header_style))
                elements.append(Spacer(1, 2))  # 少しスペースを追加（表示を確認するため）
                
                start_idx = page_num * rows_per_page
                end_idx = min(start_idx + rows_per_page, total_rows)
                page_results = results[start_idx:end_idx]
                
                # デバッグ: ページ情報を確認
                # print(f"Page {page_num + 1}/{total_pages}: start_idx={start_idx}, end_idx={end_idx}, page_results count={len(page_results)}")
                
                # 固定値を使用（動的ロジックを削除）
                # フォントサイズ（固定）
                base_font_size = 7.5
                small_font_size = 7
                extra_small_font_size = 6.5
                dept_font_size = 6.5
                header_font_size = 7.5
                small_header_font_size = 5.25  # header_font_size * 0.7
                
                # 行の高さと行間（固定）
                row_height_pt = 7.2
                leading = 3.6  # row_height_pt * 0.5
                header_height_pt = 5.5
                univ_header_height_pt = 16  # フォントサイズ12に対応して高さを大きくする（8 → 16）
                
                # 列幅の倍率（固定、中サイズのフォント用）
                width_multiplier = 1.33  # 2.8 / 2.1
                
                # スタイルを一度だけ作成（ページごとではなく）
                if not hasattr(self, '_pdf_styles_created'):
                    self._pdf_compact_style = ParagraphStyle(
                        'Compact',
                        parent=styles['Normal'],
                        fontSize=base_font_size,
                        leading=leading,
                        fontName=getattr(self, 'default_font', 'MS-Gothic')
                    )
                    
                    self._pdf_small_compact_style = ParagraphStyle(
                        'SmallCompact',
                        parent=styles['Normal'],
                        fontSize=small_font_size,
                        leading=leading,
                        fontName=getattr(self, 'default_font', 'MS-Gothic')
                    )
                    
                    self._pdf_extra_small_compact_style = ParagraphStyle(
                        'ExtraSmallCompact',
                        parent=styles['Normal'],
                        fontSize=extra_small_font_size,
                        leading=leading,
                        fontName=getattr(self, 'default_font', 'MS-Gothic')
                    )
                    
                    self._pdf_department_compact_style = ParagraphStyle(
                        'DepartmentCompact',
                        parent=styles['Normal'],
                        fontSize=dept_font_size,
                        leading=leading,
                        fontName=getattr(self, 'default_font', 'MS-Gothic')
                    )
                    
                    self._pdf_header_style = ParagraphStyle(
                    'HeaderStyle',
                    parent=styles['Normal'],
                        fontSize=header_font_size,
                        leading=header_font_size + 0.5,
                        fontName=getattr(self, 'default_font', 'MS-Gothic'),
                    alignment=1,  # CENTER
                        textColor=colors.white,
                        spaceAfter=0,
                        spaceBefore=0
                    )
                    
                    self._pdf_small_header_style = ParagraphStyle(
                        'SmallHeaderStyle',
                        parent=styles['Normal'],
                        fontSize=small_header_font_size,
                        leading=small_header_font_size + 0.5,
                        fontName=getattr(self, 'default_font', 'MS-Gothic'),
                        alignment=1,  # CENTER
                        textColor=colors.white,
                        spaceAfter=0,
                        spaceBefore=0
                    )
                    
                    self._pdf_styles_created = True
                
                # スタイルを参照
                page_compact_style = self._pdf_compact_style
                page_small_compact_style = self._pdf_small_compact_style
                page_extra_small_compact_style = self._pdf_extra_small_compact_style
                page_department_compact_style = self._pdf_department_compact_style
                page_header_style = self._pdf_header_style
                page_small_header_style = self._pdf_small_header_style
                
                # テーブルデータ作成（画像の形式に準拠）
                # 1ページ目の場合のみヘッダー行を作成
                data = []
                if page_num == 0:
                    # ヘッダー行をParagraphに変換（日本語フォントを適用、ページごとのスタイルを使用）
                    # すべてのヘッダーを身長・体重などと同じ小さなフォントサイズに統一
                    header_row = [
                        Paragraph("No", page_small_header_style),
                        Paragraph("選手名", page_small_header_style),
                        Paragraph("カナ名", page_small_header_style),
                        Paragraph("学部", page_small_header_style),
                        Paragraph("学年", page_small_header_style),
                        Paragraph("身長", page_small_header_style),
                        Paragraph("体重", page_small_header_style),
                        Paragraph("ポジ", page_small_header_style),
                        Paragraph("出身", page_small_header_style),
                        Paragraph("JBA", page_small_header_style)
                    ]
                    data.append(header_row)
                # 2ページ目以降ではヘッダー行を作成しない（dataは空のリストのまま）
                
                for idx, r in enumerate(page_results, start=start_idx+1):
                    d = r["original_data"]
                    status = r.get("status", "unknown")
                    
                    # データ行を作成（画像の列構成に準拠）
                    # 変更されたデータを赤字で表示
                    no = d.get("No", d.get("背番号", ""))
                    player_name = d.get("選手名", d.get("氏名", ""))
                    kana_name = d.get("カナ名", "")
                    department = d.get("学部", "")
                    grade = d.get("学年", "")
                    height = d.get("身長", "")
                    weight = d.get("体重", "")
                    
                    # nanを空欄に変換
                    import re
                    import pandas as pd
                    
                    def clean_value(val):
                        """nanや空文字を空欄に変換"""
                        if val is None:
                            return ""
                        val_str = str(val).strip()
                        if val_str.lower() in ['nan', 'none', ''] or pd.isna(val):
                            return ""
                        return val_str
                    
                    no = clean_value(no)
                    player_name = clean_value(player_name)
                    kana_name = clean_value(kana_name)
                    department = clean_value(department)
                    # 学年の元の値を保持（clean_value処理前のCSVの元の値）
                    original_grade_raw = d.get("学年", "")
                    original_grade = str(original_grade_raw).strip() if original_grade_raw is not None else ""
                    grade = clean_value(grade)
                    height = clean_value(height)
                    weight = clean_value(weight)
                    position = clean_value(d.get("ポジション", ""))
                    school = clean_value(d.get("出身校", ""))
                    
                    # 身長・体重・学年の小数点以下を切り捨て（数字のみ表示）
                    def truncate_decimal(value):
                        """小数点以下を切り捨てて整数に変換"""
                        if not value:
                            return ""
                        value_str = str(value)
                        # 数値部分を抽出して小数点以下を切り捨て
                        match = re.search(r'(\d+(?:\.\d+)?)', value_str)
                        if match:
                            try:
                                num = int(float(match.group(1)))
                                return str(num)
                            except (ValueError, TypeError):
                                return ""
                        return ""
                    
                    height = truncate_decimal(height)
                    weight = truncate_decimal(weight)
                    
                    # 学年の処理（一桁チェック用）
                    grade_truncated = truncate_decimal(grade)
                    
                    # 学年が一桁（1-9）かどうかをチェック
                    def is_single_digit_grade(grade_str):
                        """学年が一桁の数字（1-9）かどうかを判定"""
                        if not grade_str:
                            return False
                        try:
                            num = int(grade_str)
                            return 1 <= num <= 9
                        except (ValueError, TypeError):
                            return False
                    
                    # 学年が一桁でない場合は、CSVの元の値から小数点を削除して使用
                    if grade_truncated and not is_single_digit_grade(grade_truncated):
                        # 元のCSVの値から小数点を削除（数値部分のみ抽出）
                        original_grade_clean = original_grade
                        if original_grade:
                            # 数値部分を抽出（小数点を含む）
                            grade_num_match = re.search(r'(\d+(?:\.\d+)?)', str(original_grade))
                            if grade_num_match:
                                # 小数点以下を削除して整数のみ表示
                                try:
                                    grade_num = int(float(grade_num_match.group(1)))
                                    original_grade_clean = str(grade_num)
                                except (ValueError, TypeError):
                                    original_grade_clean = original_grade
                        grade = original_grade_clean  # 元のCSVの値から小数点を削除した値を使用
                    else:
                        grade = grade_truncated
                    
                    # ステータス記号の設定（登録状態チェックを最優先）
                    # 構成員区分を考慮して登録状態を確認
                    # 選手（背番号あり）は「競技者」の登録状態を確認
                    # スタッフ（背番号なし）は「競技者」以外の登録状態を確認（競技者は絶対見ない）
                    jba_registration_status = None
                    jba_member_category = None
                    verification_result = r.get("verification_result", {})
                    if verification_result and verification_result.get("status") == "match":
                        jba_data = verification_result.get("jba_data", {})
                        if jba_data:
                            # 構成員区分を取得
                            if "member_category" in jba_data:
                                member_category_raw = jba_data["member_category"]
                                if member_category_raw is not None and str(member_category_raw).strip():
                                    jba_member_category = str(member_category_raw).strip()
                            
                            # 登録状態が存在するかチェック（空文字列やNoneも含む）
                            if "registration_status" in jba_data:
                                registration_status_raw = jba_data["registration_status"]
                                # 空文字列やNoneでない場合のみ取得
                                if registration_status_raw is not None and str(registration_status_raw).strip():
                                    jba_registration_status = str(registration_status_raw).strip()
                    
                    # CSVの背番号の有無で選手かスタッフかを判断
                    csv_player_no = None
                    no_columns = ['No', 'NO', 'no', '背番号', 'No.', '番号', 'ナンバー', '#']
                    for col in no_columns:
                        if col in d and pd.notna(d[col]):
                            value = str(d[col]).strip()
                            if value.isdigit() or ('.' in value and value.replace('.', '').isdigit() and value.count('.') == 1):
                                csv_player_no = value
                                break
                    
                    # JBA照合でmatchした場合の処理
                    if status == "match":
                        # 構成員区分を考慮して登録状態を確認
                        is_valid_registration = False
                        
                        if csv_player_no:
                            # 選手の場合：構成員区分が「競技者」の登録状態を確認
                            if jba_member_category and "競技者" in jba_member_category:
                                if jba_registration_status and jba_registration_status.strip() == "登録完了":
                                    is_valid_registration = True
                        else:
                            # スタッフの場合：構成員区分が「競技者」以外の登録状態を確認（競技者は絶対見ない）
                            if jba_member_category and "競技者" not in jba_member_category:
                                if jba_registration_status and jba_registration_status.strip() == "登録完了":
                                    is_valid_registration = True
                            # 構成員区分が取得できない場合も確認（競技者でない可能性がある）
                            elif not jba_member_category:
                                if jba_registration_status and jba_registration_status.strip() == "登録完了":
                                    is_valid_registration = True
                        
                        # 登録状態が有効な場合のみ〇
                        if is_valid_registration:
                            status_symbol = "〇"
                        else:
                            # 登録状態が「登録完了」以外、または取得できない場合は△
                            status_symbol = "△"
                    elif status == "not_found":
                        # JBA照合で見つからなかった場合は×
                        status_symbol = "×"
                    else:
                        # その他の場合は-
                        status_symbol = "-"
                    
                    # 変更があった場合は赤字で表示（changed_fieldsを使用）
                    # また、変更点を収集してまとめページ用に保存
                    if r.get("correction"):
                        corrected_data = r["correction"]
                        changed_fields = r.get("changed_fields", set())
                        
                        # 編集サイトから取得したかどうかを確認
                        is_edited_from_html = False
                        if univ_name and player_name:
                            # HTMLタグを除去してから確認
                            player_name_clean = re.sub(r'<[^>]+>', '', player_name)
                            is_edited_from_html = self.edited_player_names.get((univ_name, player_name_clean), False)
                        
                        # 学部は一切変更しないので、比較処理を削除
                        
                        # 元の選手名を取得（変更点記録用）
                        original_player_name = d.get("選手名", d.get("氏名", ""))
                        
                        # 選手名が変更された場合のみ赤字で表示
                        if '選手名' in changed_fields:
                            corrected_name = corrected_data.get("選手名", player_name)
                            player_name = f'<font color="red">{corrected_name}</font>'
                            # 変更点を記録
                            original_name_clean = str(original_player_name) if original_player_name else ""
                            corrected_name_clean = re.sub(r'<[^>]+>', '', corrected_name)
                            source = "編" if is_edited_from_html else "JBA"
                            all_changes.append({
                                'univ': univ_name,
                                'player_name': original_name_clean,
                                'field': '選手名',
                                'csv_value': original_name_clean,
                                'corrected_value': corrected_name_clean,
                                'source': source
                            })
                        
                        # カナ名が変更された場合のみ赤字で表示
                        if 'カナ名' in changed_fields:
                            corrected_kana = corrected_data.get("カナ名", kana_name)
                            kana_name = f'<font color="red">{corrected_kana}</font>'
                            # 変更点を記録
                            original_kana_clean = str(d.get("カナ名", "")) if d.get("カナ名") else ""
                            corrected_kana_clean = re.sub(r'<[^>]+>', '', corrected_kana)
                            source = "編" if is_edited_from_html else "JBA"
                            all_changes.append({
                                'univ': univ_name,
                                'player_name': str(original_player_name) if original_player_name else "",
                                'field': 'カナ名',
                                'csv_value': original_kana_clean,
                                'corrected_value': corrected_kana_clean,
                                'source': source
                            })
                        
                        # 学年が変更された場合のみ赤字で表示
                        if '学年' in changed_fields:
                            corrected_grade = corrected_data.get("学年", grade)
                            # 修正された学年が一桁かどうかをチェック
                            corrected_grade_truncated = truncate_decimal(corrected_grade)
                            if corrected_grade_truncated and not is_single_digit_grade(corrected_grade_truncated):
                                # 一桁でない場合はCSVの元の値から小数点を削除して使用（赤字表示しない、変更扱いも解除）
                                original_grade_clean = original_grade
                                if original_grade:
                                    # 数値部分を抽出（小数点を含む）
                                    grade_num_match = re.search(r'(\d+(?:\.\d+)?)', str(original_grade))
                                    if grade_num_match:
                                        # 小数点以下を削除して整数のみ表示
                                        try:
                                            grade_num = int(float(grade_num_match.group(1)))
                                            original_grade_clean = str(grade_num)
                                        except (ValueError, TypeError):
                                            original_grade_clean = original_grade
                                grade = original_grade_clean if original_grade_clean else ""
                                # 一桁でない場合は変更扱いを解除（changed_fieldsから削除）
                                changed_fields.discard('学年')
                            else:
                                # 一桁の場合は切り捨てた値を使用（赤字表示）
                                grade = f'<font color="red">{corrected_grade_truncated}</font>' if corrected_grade_truncated else ""
                                # 変更点を記録
                                original_grade_clean = str(original_grade) if original_grade else ""
                                corrected_grade_clean = str(corrected_grade_truncated) if corrected_grade_truncated else ""
                                all_changes.append({
                                    'univ': univ_name,
                                    'player_name': str(original_player_name) if original_player_name else "",
                                    'field': '学年',
                                    'csv_value': original_grade_clean,
                                    'corrected_value': corrected_grade_clean,
                                    'source': "JBA"
                                })
                        
                        # 身長が変更された場合のみ赤字で表示
                        if '身長' in changed_fields:
                            corrected_height = corrected_data.get("身長", height)
                            # 修正された身長も小数点以下を切り捨て（数字のみ表示）
                            corrected_height = truncate_decimal(corrected_height)
                            height = f'<font color="red">{corrected_height}</font>' if corrected_height else ""
                            # 変更点を記録
                            original_height_raw = d.get("身長", "")
                            original_height_clean = str(original_height_raw).replace('cm', '').strip() if original_height_raw else ""
                            corrected_height_clean = str(corrected_height) if corrected_height else ""
                            all_changes.append({
                                'univ': univ_name,
                                'player_name': str(original_player_name) if original_player_name else "",
                                'field': '身長',
                                'csv_value': original_height_clean,
                                'corrected_value': corrected_height_clean,
                                'source': "JBA"
                            })
                        
                        # 体重が変更された場合のみ赤字で表示
                        if '体重' in changed_fields:
                            corrected_weight = corrected_data.get("体重", weight)
                            # 修正された体重も小数点以下を切り捨て（数字のみ表示）
                            corrected_weight = truncate_decimal(corrected_weight)
                            weight = f'<font color="red">{corrected_weight}</font>' if corrected_weight else ""
                            # 変更点を記録
                            original_weight_raw = d.get("体重", "")
                            original_weight_clean = str(original_weight_raw).replace('kg', '').strip() if original_weight_raw else ""
                            corrected_weight_clean = str(corrected_weight) if corrected_weight else ""
                            all_changes.append({
                                'univ': univ_name,
                                'player_name': str(original_player_name) if original_player_name else "",
                                'field': '体重',
                                'csv_value': original_weight_clean,
                                'corrected_value': corrected_weight_clean,
                                'source': "JBA"
                            })
                        
                        # ポジション・出身校はCSVのデータをそのまま使用（変更しないので赤字表示不要）
                    
                    # 英語名かどうかを判定（アルファベットのみかチェック）
                    def is_english_name(text):
                        """テキストが英語名（アルファベットのみ）かどうかを判定"""
                        if not text or not isinstance(text, str):
                            return False
                        # HTMLタグを除去してから判定
                        import re
                        text_clean = re.sub(r'<[^>]+>', '', text)
                        # 引用符（"）やその他の記号も含めて判定、日本語文字（ひらがな、カタカナ、漢字）が含まれていないかチェック
                        # 日本語文字が含まれていなければ英語として扱う
                        has_japanese = bool(re.search(r'[ひらがなカタカナ漢字一-龯]', text_clean))
                        if has_japanese:
                            return False
                        # アルファベット、スペース、ピリオド、ハイフン、アポストロフィ、引用符が含まれているか
                        return bool(re.match(r'^[A-Za-z\s\.\-\'"]+$', text_clean))
                    
                    # 英語名の場合は文字数を倍にする
                    player_name_max = 40 if is_english_name(player_name) else 20
                    kana_name_max = 40 if is_english_name(kana_name) else 20
                    department_max = 30 if is_english_name(department) else 15
                    school_max = 50 if is_english_name(school) else 25
                    position_max = 12 if is_english_name(position) else 6
                    
                    # 数値系はタグを壊さないようにトリムせずにそのまま出力
                    row_data = [
                        self._truncate_text(no, 10),  # No（10文字まで表示）
                        self._truncate_text(player_name, player_name_max),  # 選手名（英語の場合は倍）
                        self._truncate_text(kana_name, kana_name_max),  # カナ名（英語の場合は倍）
                        self._truncate_text(department, department_max),  # 学部（英語の場合は倍）
                        self._truncate_text(grade, 3),  # 学年
                        str(height) if height else "",  # 身長（空欄の場合は空文字）
                        str(weight) if weight else "",  # 体重（空欄の場合は空文字）
                        self._truncate_text(position, position_max),  # ポジション（英語の場合は倍）
                        self._truncate_text(school, school_max),  # 出身校（英語の場合は倍）
                        status_symbol  # JBA登録状況
                    ]

                    # すべてのセルを Paragraph に変換（<font> を解釈し、適切なフォント適用）
                    # 英語名の場合はHelvetica、日本語の場合は日本語フォントを使用
                    formatted_row_data = []
                    for i, cell in enumerate(row_data):
                        cell_str = str(cell) if cell else ""
                        # 英語名かどうかを判定（HTMLタグを除去）
                        import re
                        cell_clean = re.sub(r'<[^>]+>', '', cell_str)
                        # 日本語文字が含まれていなければ英語として扱う
                        has_japanese = bool(re.search(r'[ひらがなカタカナ漢字一-龯]', cell_clean)) if cell_clean else False
                        is_english = not has_japanese and bool(re.match(r'^[A-Za-z\s\.\-\'"]+$', cell_clean)) if cell_clean else False
                        
                        # 英語の場合はHelvetica、日本語の場合は日本語フォント
                        # サイズ感と左揃えは日本語と同じにする（ページごとのスタイルを使用）
                        if is_english:
                            # 英語用スタイル（Helvetica、日本語と同じサイズ・左揃え）
                            if i == 0:  # No(0)の列 - 選手名と同じサイズ
                                english_style = ParagraphStyle(
                                    f'EnglishStyle0_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_small_compact_style.fontSize,
                                    leading=page_small_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=0  # LEFT（日本語と同じ）
                                )
                            elif i in [1, 2]:  # 選手名(1)、カナ名(2)の列
                                english_style = ParagraphStyle(
                                    f'EnglishStyle12_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_small_compact_style.fontSize,
                                    leading=page_small_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=0  # LEFT（日本語と同じ）
                                )
                            elif i == 3:  # 学部(3)の列
                                english_style = ParagraphStyle(
                                    f'EnglishStyle3_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_department_compact_style.fontSize,
                                    leading=page_department_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=0  # LEFT（日本語と同じ）
                                )
                            elif i == 8:  # 出身校(8)の列
                                english_style = ParagraphStyle(
                                    f'EnglishStyle8_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_extra_small_compact_style.fontSize,
                                    leading=page_extra_small_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=0  # LEFT（日本語と同じ）
                                )
                            elif i in [4, 5, 6]:  # 学年(4)、身長(5)、体重(6)の列 - 中央揃え
                                english_style = ParagraphStyle(
                                    f'EnglishStyle456_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_compact_style.fontSize,
                                    leading=page_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=1  # CENTER（中央揃え）
                                )
                            else:
                                english_style = ParagraphStyle(
                                    f'EnglishStyleOther_{page_num}',
                                    parent=styles['Normal'],
                                    fontSize=page_compact_style.fontSize,
                                    leading=page_compact_style.leading,
                                    fontName='Helvetica',
                                    alignment=0  # LEFT（日本語と同じ）
                                )
                            formatted_row_data.append(Paragraph(cell_str, english_style))
                        else:
                            # 日本語用スタイル（ページごとのスタイルを使用）
                            if i == 0:  # No(0)の列 - 選手名と同じサイズ
                                formatted_row_data.append(Paragraph(cell_str, page_small_compact_style))
                            elif i in [1, 2]:  # 選手名(1)、カナ名(2)の列
                                formatted_row_data.append(Paragraph(cell_str, page_small_compact_style))
                            elif i == 3:  # 学部(3)の列
                                formatted_row_data.append(Paragraph(cell_str, page_department_compact_style))
                            elif i in [4, 5, 6]:  # 学年(4)、身長(5)、体重(6)の列 - 中央揃え
                                # 中央揃え用のスタイルを作成
                                center_style = ParagraphStyle(
                                    f'CenterStyle456_{page_num}',
                                    parent=page_compact_style,
                                    alignment=1  # CENTER（中央揃え）
                                )
                                formatted_row_data.append(Paragraph(cell_str, center_style))
                            elif i == 8:  # 出身校(8)の列
                                formatted_row_data.append(Paragraph(cell_str, page_extra_small_compact_style))
                            else:
                                formatted_row_data.append(Paragraph(cell_str, page_compact_style))
                    row_data = formatted_row_data
                    
                    data.append(row_data)
                
                # 2ページ目以降の場合、ヘッダー行を確実に除外
                # dataの最初の要素がヘッダー行（Paragraph("No", ...)など）かどうかを確認
                if page_num > 0 and len(data) > 0:
                    first_row = data[0]
                    if isinstance(first_row, list) and len(first_row) > 0:
                        first_cell = first_row[0]
                        # Paragraphオブジェクトの場合、そのテキストを確認
                        if hasattr(first_cell, 'text'):
                            first_cell_text = str(first_cell.text) if first_cell.text else ""
                            # ヘッダー行のキーワードが含まれている場合は削除
                            if any(keyword in first_cell_text for keyword in ['No', '選手名', 'カナ名', '学部', '学年', '身長', '体重', 'ポジ', '出身', 'JBA']):
                                data = data[1:]
                        # または、Paragraphオブジェクトのtext属性がNoneの場合もヘッダー行の可能性がある
                        elif hasattr(first_cell, 'text') and first_cell.text is None:
                            # 念のため、最初の行を削除
                            data = data[1:]
                
                # テーブル作成（A4横向き最適化）- フォントサイズに応じて列幅を動的に調整
                # 基準列幅（6ptの時の幅）
                # 身長・体重: 学年と同じ幅（8mm、横書きで表示されるように）
                # 学年: 2文字が横書きで入る（8mm、縦にならないように広げる）
                # ポジション: 短い文字列が入る（5mm、PG/SG/SF/PF/Cなど）
                # JBA: 1文字が入る（5mm、〇/×/△、少し余裕を持たせる）
                # 選手名・カナ名: 24文字が入るように調整（4文字分拡大）
                # 6ptの時: 日本語1文字 ≈ 2.5mm → 24文字 × 2.5mm = 60mm
                # 出身校: 英語50文字、日本語30文字が入るように調整（選手名・カナ名を広げるため縮小）
                # 6ptの時: 英語1文字 ≈ 1.25mm → 50文字 × 1.25mm = 62.5mm
                # 6ptの時: 日本語1文字 ≈ 2.5mm → 30文字 × 2.5mm = 75mm
                # 両方が同時に入る可能性を考慮: 62.5mm + 75mm = 137.5mm + 余裕-17.5mm = 約120mm（選手名・カナ名を広げるため20mm縮小）
                # [No, 選手名, カナ名, 学部, 学年, 身長, 体重, ポジション, 出身校, JBA]
                base_col_widths = [16*mm, 60*mm, 60*mm, 26*mm, 8*mm, 8*mm, 8*mm, 5*mm, 120*mm, 5*mm]
                # フォントサイズに応じて列幅を拡大（細かい文字の時と同じ文字数が入るように）
                col_widths = [w * width_multiplier for w in base_col_widths]
                
                # 横向きA4の幅（約297mm）- 左右マージン（8mm×2）= 約281mm
                # 列幅の合計が281mmを超えないように調整
                total_width = sum(col_widths)
                max_width = 281 * mm
                if total_width > max_width:
                    # 列幅を縮小して収める
                    scale_factor = max_width / total_width
                    col_widths = [w * scale_factor for w in col_widths]
                
                # パディング（固定値）
                padding = 0.11  # row_height_pt * 0.015 ≈ 0.11
                header_padding = 0.6  # header_font_size * 0.08 ≈ 0.6
                
                # 行の高さ（固定値）
                # leadingとpaddingを含めた実際の行の高さ
                # 実際の行の高さ = row_height_pt + leading + padding*2 = 7.2 + 3.6 + 0.11*2 = 11.02pt
                actual_row_height = row_height_pt + leading + padding * 2
                # 2ページ目以降の場合はヘッダー行の高さを含めない
                if page_num == 0:
                    header_row_height = header_height_pt
                    row_heights = [header_row_height] + [actual_row_height] * (len(data) - 1)
                    # 1ページ目はrepeatRowsを指定しない（デフォルト）
                    table = Table(data, colWidths=col_widths, rowHeights=row_heights)
                else:
                    row_heights = [actual_row_height] * len(data)
                    # 2ページ目以降はrepeatRowsを指定せず、dataにヘッダー行を含めないことで自動繰り返しを防ぐ
                    table = Table(data, colWidths=col_widths, rowHeights=row_heights)
                    # 念のため、repeatRows属性を明示的にNoneに設定（ReportLabの内部処理を回避）
                    table.repeatRows = None
                # テーブルスタイルを構築（2ページ目以降はヘッダー行のスタイルを除外）
                table_style = []
                
                # 1ページ目の場合のみヘッダー行のスタイルを追加
                if page_num == 0:
                    table_style.extend([
                        # ヘッダー
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        # ヘッダー行はParagraphで作成しているため、フォントはParagraph内で設定済み
                        ("TOPPADDING", (0, 0), (-1, 0), header_padding),  # ヘッダー上部パディング（フォントサイズに応じて調整）
                        ("BOTTOMPADDING", (0, 0), (-1, 0), header_padding),  # ヘッダー下部パディング（フォントサイズに応じて調整）
                    ])
                    data_start_row = 1
                else:
                    data_start_row = 0
                
                table_style.extend([
                    # デフォルトは左揃え（全行）
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    # 学年(4)、身長(5)、体重(6)のデータ行だけ中央揃え
                    ("ALIGN", (4, data_start_row), (4, -1), "CENTER"),  # 学年（データ行のみ）
                    ("ALIGN", (5, data_start_row), (5, -1), "CENTER"),  # 身長（データ行のみ）
                    ("ALIGN", (6, data_start_row), (6, -1), "CENTER"),  # 体重（データ行のみ）
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),  # 中央揃えに変更
                    
                    # データ行（固定フォントサイズ）
                    ("FONTNAME", (0, data_start_row), (-1, -1), getattr(self, 'default_font', 'MS-Gothic')),
                    ("FONTSIZE", (0, data_start_row), (-1, -1), base_font_size),  # 固定フォントサイズ
                    ("ROWBACKGROUNDS", (0, data_start_row), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
                ])
                
                table_style.extend([
                    # 罫線
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),  # 罫線を細く
                    # ラベルのすぐ下の濃い黒線を削除（LINEBELOWを削除）
                    
                    # パディング調整
                    ("TOPPADDING", (0, data_start_row), (-1, -1), padding),  # 上部パディング
                    ("BOTTOMPADDING", (0, data_start_row), (-1, -1), padding),  # 下部パディング
                    ("LEFTPADDING", (0, 0), (-1, -1), 0.2),  # 左パディングを最小限に（50行目まで入るため：0.3 → 0.2）
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0.2),  # 右パディングを最小限に（50行目まで入るため：0.3 → 0.2）
                ])
                
                table.setStyle(TableStyle(table_style))
                
                elements.append(table)
                
                # ページ区切り（最後のページ以外）
                if page_num < total_pages - 1:
                    elements.append(PageBreak())
            
            # 大学区切り（最後の大学以外）
            if i < len(reports) - 1:
                elements.append(PageBreak())
        
        # 変更点のまとめページを追加
        if all_changes:
            elements.append(PageBreak())
            elements.append(Spacer(1, 20))
            
            # タイトル
            title_style = ParagraphStyle(
                'ChangeSummaryTitle',
                parent=styles['Normal'],
                fontSize=16,
                leading=20,
                fontName=getattr(self, 'default_font', 'MS-Gothic'),
                alignment=1,  # CENTER
                spaceAfter=20
            )
            elements.append(Paragraph("変更点まとめ", title_style))
            elements.append(Spacer(1, 10))
            
            # 変更点をテーブル形式で表示
            change_data = []
            change_header = [
                Paragraph("大学名", page_small_header_style),
                Paragraph("選手名", page_small_header_style),
                Paragraph("変更内容", page_small_header_style)
            ]
            change_data.append(change_header)
            
            for change in all_changes:
                univ = change['univ']
                player = change['player_name']
                field = change['field']
                csv_val = change['csv_value']
                corrected_val = change['corrected_value']
                source = change['source']
                
                # 変更内容のフォーマット
                if source == "編":
                    change_text = f"CSV {csv_val}→編 {corrected_val}"
                else:
                    change_text = f"CSV {csv_val}→JBA {corrected_val}"
                
                change_row = [
                    Paragraph(univ, page_compact_style),
                    Paragraph(player, page_compact_style),
                    Paragraph(change_text, page_compact_style)
                ]
                change_data.append(change_row)
            
            # 変更点テーブルの列幅（横向きA4に合わせて調整）
            change_col_widths = [80*mm, 60*mm, 150*mm]
            change_table = Table(change_data, colWidths=change_col_widths, repeatRows=1)
            change_table.setStyle(TableStyle([
                # ヘッダー
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), getattr(self, 'default_font', 'MS-Gothic')),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                # データ行
                ("FONTNAME", (0, 1), (-1, -1), getattr(self, 'default_font', 'MS-Gothic')),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(change_table)
        
        # PDF生成
        doc.build(elements)
        print(f"📄 PDF生成完了: {output_path} (フォント: {getattr(self, 'default_font', 'Unknown')})")
        return output_path
    


def main():
    """メイン処理"""
    # CLI/Streamlit UI は削除済み
    return

if __name__ == "__main__":
    main()
