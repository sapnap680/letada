#!/usr/bin/env python3
"""
CSV自動訂正システム
JBAデータベースと照合してCSVファイルを自動訂正
"""

# Streamlit import removed
import pandas as pd
import logging
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import re
import unicodedata
from difflib import SequenceMatcher
import io
# import google.generativeai as genai  # AI機能は使用しない
import os
import concurrent.futures
import time
import threading

# ロガー初期化
logger = logging.getLogger(__name__)

# Streamlit 非依存化のためのスタブ
try:
    import streamlit as st  # 実行環境にあれば使用
except Exception:
    class _DummyCtx:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
    class _STStub:
        def __getattr__(self, name):
            if name == 'columns':
                return lambda n: [_DummyCtx() for _ in range(n)]
            if name == 'tabs':
                return lambda names: [_DummyCtx() for _ in names]
            if name == 'expander':
                return lambda *a, **k: _DummyCtx()
            return lambda *a, **k: None
    st = _STStub()

# プレースホルダが未定義でも落ちないようにダミー定義
class _Placeholder:
    def __getattr__(self, name):
        return lambda *a, **k: None
status_placeholder = _Placeholder()
csv_progress = _Placeholder()
csv_status = _Placeholder()

class JBAVerificationSystem:
    """JBA検証システム（requests + BeautifulSoupベース）"""
    logger = logging.getLogger(__name__)
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'ja,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Origin': 'https://team-jba.jp',
            'Referer': 'https://team-jba.jp/organization/15250600/team/search',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.logged_in = False
        
        # 🚀 パフォーマンス改善: チーム情報のキャッシュ
        self.teams_cache = {}  # {search_name: [teams]}
        self.team_members_cache = {}  # {team_url: team_data}
    
    def get_current_fiscal_year(self):
        """現在の年度を取得"""
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if current_month >= 1:
            return str(current_year)
        else:
            return str(current_year - 1)
    
    def normalize_university_name(self, university_name):
        """大学名を正規化（柔軟な照合のため）"""
        if not university_name:
            return ""
        
        # 基本的な正規化
        normalized = university_name.strip()
        
        # よくある表記の統一
        replacements = {
            '白鷗大学': '白鴎大学',
            '白鴎大学': '白鴎大学',
            '白鷗': '白鴎',
            '白鴎': '白鴎',
            '大学': '大学',
            '学院': '学院',
            '短期大学': '短期大学',
            '短大': '短期大学'
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized
    
    def get_search_variations(self, university_name):
        """大学名から「大学校」または「大学」を外した名前だけを返す"""
        if not university_name:
            return []
        
        # 「大学校」を除いた部分を返す（「防衛大学校」→「防衛」）
        if '大学校' in university_name:
            base_without_daigakko = university_name.replace('大学校', '').strip()
            if base_without_daigakko and len(base_without_daigakko) > 1:  # 最低2文字以上
                return [base_without_daigakko]
        
        # 「大学」を除いた部分を返す（「早稲田大学」→「早稲田」）
        if '大学' in university_name:
            base_without_daigaku = university_name.replace('大学', '').strip()
            if base_without_daigaku and len(base_without_daigaku) > 1:  # 最低2文字以上
                return [base_without_daigaku]
        
        # 「大学校」「大学」がない場合はそのまま返す
        return [university_name.strip()]
    
    def login(self, email, password):
        """JBAサイトにログイン"""
        try:
            # 🆕 ステップ1: ログインページにアクセス
            # Status placeholder removed
            # Progress bar removed - use job_meta instead
            
            # Status placeholder update removed
            # Progress update removed
            
            login_page = self.session.get("https://team-jba.jp/login")
            soup = BeautifulSoup(login_page.content, 'html.parser')
            
            csrf_token = ""
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
            
            # Status placeholder update removed
            # Progress update removed
            
            login_data = {
                '_token': csrf_token,
                'login_id': email,
                'password': password
            }
            
            login_url = "https://team-jba.jp/login/done"
            login_response = self.session.post(login_url, data=login_data, allow_redirects=True)
            
            # Status placeholder update removed
            # Progress update removed
            
            if "ログアウト" in login_response.text:
                self.logged_in = True
                # Status placeholder update removed
                # Sleep removed  # 1秒表示
                # Progress bar cleanup removed
                pass
                return True
            else:
                # Status placeholder update removed
                # Sleep removed  # 2秒表示
                # Progress bar cleanup removed
                pass
                return False
                
        except Exception as e:
            logger.error(f"❌ ログインエラー: {str(e)}")
            return False
    
    def search_teams_by_university(self, university_name):
        """大学名でチームを検索（柔軟な照合）"""
        try:
            if not self.logged_in:
                # ログインが必要です
                return []
            
            current_year = self.get_current_fiscal_year()
            # 男子チームを検索中
            
            # 大学名の正規化（柔軟な照合のため）
            normalized_university = self.normalize_university_name(university_name)
            # 正規化された大学名
            
            # 正規化された大学名で検索
            search_university = normalized_university
            
            # 検索ページにアクセスしてCSRFトークンを取得
            search_url = "https://team-jba.jp/organization/15250600/team/search"
            search_page = self.session.get(search_url)
            
            if search_page.status_code != 200:
                # 検索ページにアクセスできません
                return []
            
            soup = BeautifulSoup(search_page.content, 'html.parser')
            
            # CSRFトークンを取得
            csrf_token = ""
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
            
            # JSON APIを使用した検索（男子チームのみ）
            search_data = {
                "limit": 100,
                "offset": 0,
                "searchLogic": "AND",
                "search": [
                    {"field": "fiscal_year", "type": "text", "operator": "is", "value": current_year},
                    {"field": "team_name", "type": "text", "operator": "contains", "value": search_university},
                    {"field": "competition_division_id", "type": "int", "operator": "is", "value": 1},
                    {"field": "team_search_out_of_range", "type": "int", "operator": "is", "value": 1}
                ]
            }
            
            form_data = {'request': json.dumps(search_data, ensure_ascii=False)}
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRF-Token': csrf_token,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # 検索リクエストを送信（JSON APIとして）
            search_response = self.session.post(
                search_url, 
                data=form_data,
                headers=headers
            )
            
            if search_response.status_code != 200:
                # 検索リクエストが失敗しました
                return []
            
            # JSONレスポンスを解析
            try:
                data = search_response.json()
                teams = []
                
                if data.get('status') == 'success' and 'records' in data:
                    for team_data in data['records']:
                        # 男子チームのみを対象
                        if team_data.get('team_gender_id') == '男子':
                            teams.append({
                                'id': team_data.get('id', ''),
                                'name': team_data.get('team_name', ''),
                                'url': f"https://team-jba.jp/organization/15250600/team/{team_data.get('id', '')}/detail"
                            })
                
                # 男子チームが見つかりました
                return teams
                
            except Exception as e:
                # 検索結果の解析に失敗しました
                return []
            
        except Exception as e:
            # チーム検索エラー
            return []
    
    def _search_teams_by_university_silent(self, university_name):
        """大学名でチームを検索（静かな実行版 - st.*出力なし）"""
        try:
            if not self.logged_in:
                return []
            
            current_year = self.get_current_fiscal_year()
            
            # 大学名の正規化（柔軟な照合のため）
            normalized_university = self.normalize_university_name(university_name)
            
            # 正規化された大学名で検索
            search_university = normalized_university
            
            # 検索ページにアクセスしてCSRFトークンを取得
            search_url = "https://team-jba.jp/organization/15250600/team/search"
            search_page = self.session.get(search_url)
            
            if search_page.status_code != 200:
                return []
            
            soup = BeautifulSoup(search_page.content, 'html.parser')
            
            # CSRFトークンを取得
            csrf_token = ""
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
            
            # JSON APIを使用した検索（男子チームのみ）
            search_data = {
                "limit": 100,
                "offset": 0,
                "searchLogic": "AND",
                "search": [
                    {"field": "fiscal_year", "type": "text", "operator": "is", "value": current_year},
                    {"field": "team_name", "type": "text", "operator": "contains", "value": search_university},
                    {"field": "competition_division_id", "type": "int", "operator": "is", "value": 1},
                    {"field": "team_search_out_of_range", "type": "int", "operator": "is", "value": 1}
                ]
            }
            
            form_data = {'request': json.dumps(search_data, ensure_ascii=False)}
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-CSRF-Token': csrf_token,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # 検索リクエストを送信（JSON APIとして）
            search_response = self.session.post(
                search_url, 
                data=form_data,
                headers=headers
            )
            
            if search_response.status_code != 200:
                return []
            
            # JSONレスポンスを解析
            try:
                data = search_response.json()
                teams = []
                
                if data.get('status') == 'success' and 'records' in data:
                    for team_data in data['records']:
                        # 男子チームのみを対象
                        if team_data.get('team_gender_id') == '男子':
                            teams.append({
                                'id': team_data.get('id', ''),
                                'name': team_data.get('team_name', ''),
                                'url': f"https://team-jba.jp/organization/15250600/team/{team_data.get('id', '')}/detail"
                            })
                
                return teams
                
            except Exception as e:
                return []
            
        except Exception as e:
            return []

    def get_team_members(self, team_url):
        """チームのメンバー情報を取得（男子チームのみ）"""
        try:
            # チームメンバー情報を取得中
            logger.info(f"🔍 チームURL: {team_url}")
            
            # チーム詳細ページにアクセス
            team_page = self.session.get(team_url)
            
            if team_page.status_code != 200:
                # チームページにアクセスできません
                return {"team_name": "Error", "members": []}
            
            soup = BeautifulSoup(team_page.content, 'html.parser')
            
            # チーム名を取得
            team_name = "Unknown Team"
            title_element = soup.find('title')
            if title_element:
                team_name = title_element.get_text(strip=True)
            
            logger.info(f"🔍 チーム名: {team_name}")

            # メンバー情報を抽出（男子チームのメンバーテーブルを特定）
            members = []
            
            tables = soup.find_all('table')

            # 男子チームのメンバーテーブルを探す（3列のテーブルを探す）
            member_table = None
            for i, table in enumerate(tables):
                rows = table.find_all('tr')
                if len(rows) > 10:  # メンバーテーブルは通常10行以上
                    # 最初の行に「メンバーID / 氏名 / 生年月日」があるかチェック
                    first_row_cells = rows[0].find_all(['td', 'th'])
                    if len(first_row_cells) >= 3:
                        first_cell = first_row_cells[0].get_text(strip=True)
                        second_cell = first_row_cells[1].get_text(strip=True)
                        third_cell = first_row_cells[2].get_text(strip=True)
                        if "メンバーID" in first_cell and "氏名" in second_cell and "生年月日" in third_cell:
                            member_table = table
                            break

            if member_table:
                rows = member_table.find_all('tr')
                for row in rows[1:]:  # ヘッダー行をスキップ
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        member_id = cells[0].get_text(strip=True)
                        name = cells[1].get_text(strip=True)
                        birth_date = cells[2].get_text(strip=True)
                        
                        # メンバーIDが数字で、名前が空でない場合のみ追加
                        if member_id.isdigit() and name and name != "氏名":
                            # 選手詳細ページのリンクを取得
                            detail_link = None
                            name_cell = cells[1]
                            link = name_cell.find('a')
                            if link and link.get('href'):
                                detail_link = link.get('href')
                                # 相対URLを絶対URLに変換
                                if detail_link.startswith('/'):
                                    detail_link = f"https://team-jba.jp{detail_link}"
                            
                            members.append({
                                "member_id": member_id,
                                "name": name,
                                "birth_date": birth_date,
                                "detail_url": detail_link
                            })

            return {
                "team_name": team_name,
                "members": members
            }
            
        except Exception as e:
            # メンバー取得エラー
            import traceback
            logger.info(f"**エラー詳細**: {traceback.format_exc()}")
            return {"team_name": "Error", "team_url": team_url, "members": []}
    
    def _get_team_members_silent(self, team_url):
        """チームのメンバー情報を取得（静かな実行版 - st.*出力なし）"""
        try:
            # チーム詳細ページにアクセス
            team_page = self.session.get(team_url)
            
            if team_page.status_code != 200:
                return {"team_name": "Error", "members": []}
            
            soup = BeautifulSoup(team_page.content, 'html.parser')
            
            # チーム名を取得
            team_name = "Unknown Team"
            title_element = soup.find('title')
            if title_element:
                team_name = title_element.get_text(strip=True)
            
            # メンバー情報を取得
            members = []
            
            # 選手一覧のテーブルを探す
            member_tables = soup.find_all('table', class_='table')
            
            for table_idx, table in enumerate(member_tables):
                rows = table.find_all('tr')
                
                for row_idx, row in enumerate(rows[1:], start=1):  # ヘッダー行をスキップ
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 3:  # 最低限の情報がある行のみ処理
                        # 選手名のリンクを探す（JBAの実際のURLパターン: /member/to-team/数字/detail）
                        name_link = row.find('a', href=re.compile(r'/member/to-team/\d+'))
                        
                        if name_link:
                            player_name = name_link.get_text(strip=True)
                            detail_url = name_link['href']
                            
                            if not detail_url.startswith('http'):
                                detail_url = f"https://team-jba.jp{detail_url}"
                            
                            # その他の情報を取得
                            position = ""
                            grade = ""
                            height = ""
                            weight = ""
                            
                            for i, cell in enumerate(cells):
                                cell_text = cell.get_text(strip=True)
                                
                                # ポジション（通常は2番目のカラム）
                                if i == 1 and cell_text and cell_text not in ['選手名', '氏名']:
                                    position = cell_text
                                
                                # 学年（通常は3番目のカラム）
                                elif i == 2 and cell_text and cell_text not in ['学年', '年']:
                                    grade = cell_text
                                
                                # 身長・体重の情報を探す
                                if 'cm' in cell_text:
                                    height = cell_text
                                elif 'kg' in cell_text:
                                    weight = cell_text
                            
                            members.append({
                                "name": player_name,
                                "position": position,
                                "grade": grade,
                                "height": height,
                                "weight": weight,
                                "detail_url": detail_url
                            })
            
            # 最終結果をログに記録（メンバーが0人の場合のみ警告）
            if len(members) == 0:
                logger.warning(f"⚠️ チーム {team_name} のメンバーが取得できませんでした")
            
            return {
                "team_name": team_name,
                "members": members
            }
            
        except Exception as e:
            logger.error(f"❌ メンバー取得エラー: {str(e)}", exc_info=True)
            return {"team_name": "Error", "members": []}
    
    def get_player_details(self, detail_url, fields=None):
        """
        選手詳細ページから必要最小限の情報のみ取得
        
        Args:
            detail_url: 選手詳細ページのURL
            fields: 取得するフィールドのリスト（Noneの場合は全て取得）
                   例: ['height', 'weight', 'grade'] または None（全て）
        """
        try:
            if not detail_url:
                return {}
            
            # 選手詳細ページにアクセス
            detail_page = self.session.get(detail_url)
            
            if detail_page.status_code != 200:
                return {}
            
            soup = BeautifulSoup(detail_page.content, 'html.parser')
            
            # 選手詳細情報を抽出
            player_details = {}
            
            # 🚀 パフォーマンス改善3: 必要最小限のフィールドのみ処理
            need_height = fields is None or 'height' in fields
            need_weight = fields is None or 'weight' in fields
            need_grade = fields is None or 'grade' in fields
            need_position = fields is None or 'position' in fields
            need_school = fields is None or 'school' in fields
            need_uniform = fields is None or 'uniform_number' in fields
            need_kana_name = fields is None or 'kana_name' in fields
            need_registration_status = fields is None or 'registration_status' in fields
            
            # 身長・体重情報を探す（必要な場合のみ）
            height_patterns = [
                r'身長[：:]\s*(\d+\.?\d*)\s*cm',
                r'身長[：:]\s*(\d+\.?\d*)\s*センチ',
                r'Height[：:]\s*(\d+\.?\d*)\s*cm'
            ] if need_height or need_weight else []
            
            weight_patterns = [
                r'体重[：:]\s*(\d+\.?\d*)\s*kg',
                r'体重[：:]\s*(\d+\.?\d*)\s*キロ',
                r'Weight[：:]\s*(\d+\.?\d*)\s*kg'
            ] if need_weight else []
            
            # テーブルから情報を抽出
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        
                        # 身長情報（必要な場合のみ）
                        if need_height and ('身長' in label or 'Height' in label):
                            import re
                            height_match = re.search(r'(\d+\.?\d*)', value)
                            if height_match and value.strip():
                                player_details['height'] = height_match.group(1)
                        
                        # 体重情報（必要な場合のみ）
                        elif need_weight and ('体重' in label or 'Weight' in label):
                            import re
                            weight_match = re.search(r'(\d+\.?\d*)', value)
                            if weight_match and value.strip():
                                player_details['weight'] = weight_match.group(1)
                        
                        # ポジション情報（必要な場合のみ）
                        elif need_position and ('ポジション' in label or 'Position' in label):
                            player_details['position'] = value
                        
                        # 出身校情報（必要な場合のみ）
                        elif need_school and ('出身校' in label or '出身' in label):
                            player_details['school'] = value
                        
                        # 学年情報（必要な場合のみ）
                        elif need_grade and ('学年' in label or 'Grade' in label):
                            player_details['grade'] = value
                        
                        # ユニフォーム番号（必要な場合のみ）
                        elif need_uniform and ('ユニフォーム番号' in label or '背番号' in label):
                            player_details['uniform_number'] = value
            
                        # 氏名カナ（必要な場合のみ）
                        elif need_kana_name and ('氏名カナ' in label or 'カナ名' in label or 'フリガナ' in label or 'ふりがな' in label):
                            player_details['kana_name'] = value
                        
                        # 登録状態（必要な場合のみ）
                        elif need_registration_status and ('登録状態' in label or '登録ステータス' in label or 'Registration Status' in label or 'Status' in label):
                            player_details['registration_status'] = value
            
            # テーブルで見つからない場合は、ページ全体から正規表現で検索（必要な場合のみ）
            if need_height and 'height' not in player_details:
                page_text = soup.get_text()
                for pattern in height_patterns:
                    import re
                    match = re.search(pattern, page_text)
                    if match:
                        player_details['height'] = match.group(1)
                        break
                
            if need_weight and 'weight' not in player_details:
                if 'page_text' not in locals():
                    page_text = soup.get_text()
                for pattern in weight_patterns:
                    import re
                    match = re.search(pattern, page_text)
                    if match:
                        player_details['weight'] = match.group(1)
                        break
            
            return player_details
            
        except Exception as e:
            # 選手詳細取得エラー
            return {}
    

    def normalize_name(self, name):
        """名前の正規化"""
        if not name or pd.isna(name):
            return ""
        
        name = str(name)
        
        # 1. 全角・半角統一
        name = unicodedata.normalize('NFKC', name)
        
        # 2. 記号・スペースの正規化（全角スペースも含む）
        name = re.sub(r'[・･、，,\.\s　]+', '', name)
        
        # 3. 大文字小文字統一
        name = name.lower()
        
        # 4. よくある表記揺れの統一
        name = re.sub(r'[ー−‐—–]', '', name)  # 長音符、ハイフン、エムダッシュ、エンダッシュ除去
        
        return name

    def calculate_similarity(self, name1, name2):
        """名前の類似度を計算"""
        if not name1 or not name2:
            return 0.0
        
        # 正規化
        norm_name1 = self.normalize_name(name1)
        norm_name2 = self.normalize_name(name2)
        
        if norm_name1 == norm_name2:
            return 1.0
        
        # 基本的な類似度
        basic_similarity = SequenceMatcher(None, norm_name1, norm_name2).ratio()
        
        return basic_similarity
    
    def show_name_differences(self, name1, name2):
        """名前の微妙な違いを視覚的に表示"""
        if not name1 or not name2:
            return ""
        
        # 正規化
        norm_name1 = self.normalize_name(name1)
        norm_name2 = self.normalize_name(name2)
        
        if norm_name1 == norm_name2:
            return "✅ 完全一致"
        
        # 文字単位での差分を表示
        matcher = SequenceMatcher(None, norm_name1, norm_name2)
        differences = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                differences.append(norm_name1[i1:i2])
            elif tag == 'delete':
                differences.append(f"❌{norm_name1[i1:i2]}❌")
            elif tag == 'insert':
                differences.append(f"➕{norm_name2[j1:j2]}➕")
            elif tag == 'replace':
                differences.append(f"🔄{norm_name1[i1:i2]}→{norm_name2[j1:j2]}🔄")
        
        result = "".join(differences)
        return f"🔍 差分: {result}"

    def verify_player_info(self, player_name, birth_date, university, get_details=False, threshold=1.0, player_no=None, kana_name=None):
        """個別選手情報の照合（男子チームのみ）"""
        try:
            logger.info(f"🔍 選手照合: {player_name}, 大学: {university}")
            
            # 氏名がアルファベットの場合のみ、カナ名で選手名を探す
            import re
            is_alphabet_only = bool(re.match(r'^[A-Za-z\s]+$', player_name)) if player_name else False
            
            # ログイン状態チェック
            if not self.logged_in:
                logger.error("❌ JBAにログインしていません")
                return {"status": "error", "message": "JBAログインが必要です"}
            
            # 背番号がない場合も選手名・カナ名で照合（コーチ扱いをやめる）
            # 背番号の有無に関わらず、選手名・カナ名で照合する
            
            # 大学名から「大学」を外した名前で検索
            search_variations = self.get_search_variations(university)
            if not search_variations:
                logger.warning(f"⚠️ {university}の検索名が生成できませんでした")
                return {"status": "not_found", "message": f"{university}の検索名が生成できませんでした"}
            
            # 最初のバリエーション（大学名から「大学」を外した名前）のみで検索
            search_name = search_variations[0]
            
            # 🚀 パフォーマンス改善: チーム情報をキャッシュから取得
            if search_name in self.teams_cache:
                teams = self.teams_cache[search_name]
                logger.debug(f"💾 キャッシュからチーム情報を取得: {len(teams)}チーム")
            else:
                logger.info(f"🔍 チーム検索開始: {search_name}")
                try:
                    teams = self._search_teams_by_university_silent(search_name)
                    # キャッシュに保存
                    self.teams_cache[search_name] = teams
                    logger.info(f"🔍 検索結果: {len(teams)}チーム見つかりました")
                except Exception as search_error:
                    logger.error(f"❌ チーム検索エラー ({search_name}): {search_error}")
                    teams = []
            
            if not teams:
                logger.warning(f"⚠️ {university}の男子チームが見つかりませんでした")
                return {"status": "not_found", "message": f"{university}の男子チームが見つかりませんでした"}

            # 各チームのメンバー情報を取得して照合
            for team in teams:
                try:
                    # 🚀 パフォーマンス改善: メンバー情報をキャッシュから取得
                    if team['url'] in self.team_members_cache:
                        team_data = self.team_members_cache[team['url']]
                        logger.debug(f"💾 キャッシュからメンバー情報を取得: {team['name']}")
                    else:
                        logger.info(f"🔍 チーム: {team['name']} のメンバーを取得中...")
                        team_data = self._get_team_members_silent(team['url'])
                        # キャッシュに保存
                        self.team_members_cache[team['url']] = team_data
                    
                    if not team_data or not team_data.get("members"):
                        logger.warning(f"⚠️ チーム {team['name']} のメンバーが取得できませんでした")
                        continue
                    
                    # 🚀 パフォーマンス改善: ログ出力を削減
                    logger.debug(f"🔍 メンバー数: {len(team_data['members'])}人")
                    
                    for i, member in enumerate(team_data["members"]):
                        try:
                            # 氏名がアルファベットの場合のみ、カナ名で選手名を探す
                            search_name = player_name
                            if is_alphabet_only and kana_name:
                                # カナ名で選手名を探す（JBAデータの氏名カナと照合）
                                search_name = kana_name
                        
                        # 名前の類似度チェック
                            name_similarity = self.calculate_similarity(search_name, member.get("name", ""))
                            
                            # カナ名も照合（JBAデータの氏名カナと照合）
                            kana_similarity = 0.0
                            if kana_name and member.get("kana_name"):
                                kana_similarity = self.calculate_similarity(kana_name, member.get("kana_name", ""))
                            
                            # 名前またはカナ名の類似度が0.6以上ならJBA登録あり（〇）として扱う
                            max_similarity = max(name_similarity, kana_similarity)
                            if max_similarity >= 0.6:
                                # 🚀 パフォーマンス改善: デバッグ情報（マッチした場合のみ）
                                logger.debug(f"  - JBA選手: {member.get('name', 'N/A')}, 名前類似度: {name_similarity:.3f}, カナ類似度: {kana_similarity:.3f}")
                                
                                # 🚀 パフォーマンス改善3: 詳細情報を取得する場合
                                if get_details and member.get("detail_url"):
                                    try:
                                        if player_no:
                                            # 背番号がある場合は身長・体重・学年・登録状態を取得
                                            fields = ['height', 'weight', 'grade', 'registration_status']
                                        else:
                                            # 背番号がない場合はカナ名も取得（照合に使用）
                                            fields = ['kana_name', 'registration_status']
                                        player_details = self.get_player_details(member["detail_url"], fields=fields)
                                        member.update(player_details)
                                    except Exception as detail_error:
                                        logger.error(f"❌ 選手詳細取得エラー: {detail_error}")
                                
                                # JBA登録あり（〇）として返す
                                return {
                                    "status": "match",
                                    "jba_data": member,
                                    "similarity": max_similarity
                                }
                        
                        except Exception as member_error:
                            logger.error(f"❌ メンバー処理エラー: {member_error}")
                            continue
                
                except Exception as team_error:
                    logger.error(f"❌ チーム処理エラー ({team.get('name', 'Unknown')}): {team_error}")
                    continue

            # JBA登録が見つからなかった場合（×）
            logger.warning(f"⚠️ {player_name} のJBA登録が見つかりませんでした")
            return {"status": "not_found", "message": "JBAデータベースに該当する選手が見つかりませんでした"}

        except Exception as e:
            logger.error(f"❌ 照合エラー ({player_name}): {str(e)}", exc_info=True)
            return {"status": "error", "message": f"照合エラー: {str(e)}"}

# AI機能は使用しないため削除
    
# AI機能は使用しないため削除
    
# AI機能は使用しないため削除

class DataValidator:
    """データ検証システム（AI機能なし）"""
    logger = logging.getLogger(__name__)
    
    def __init__(self, gemini_api_key=None):
        # AI機能は使用しない
        pass
    
    def validate_weight(self, weight):
        """体重の妥当性を評価（AI機能なし）"""
        if not weight:
            return True, []
        
        # シンプルな範囲チェック
        try:
            weight_value = float(weight)
            if 45 <= weight_value <= 140:
                return True, []
            else:
                return False, [f"体重が範囲外です: {weight}kg (45-140kgの範囲で入力してください)"]
        except (ValueError, TypeError):
            return False, [f"体重が数値ではありません: {weight}"]
    
    def validate_and_correct_school(self, school_name):
        """出身校の妥当性を評価（AI機能なし）"""
        if not school_name or school_name.strip() == "":
            return True, [], None
        
        # シンプルな文字列チェック
        school_name = str(school_name).strip()
        if len(school_name) < 2:
            return False, ["学校名が短すぎます"], None
        
        return True, [], None
    
    def validate_uniform_number(self, uniform_number):
        """背番号の妥当性を評価（AI機能なし）"""
        if not uniform_number:
            return True, []
        
        # 背番号は数字のみのシンプル検証
        try:
            num = int(uniform_number)
            if 1 <= num <= 99:
                return True, []
            else:
                return False, ["背番号は1〜99の範囲である必要があります"]
        except ValueError:
            return False, ["背番号は数字である必要があります"]
    
    def validate_player_data(self, player_data):
        """体重・出身校・背番号の検証（AI機能なし）"""
        all_issues = []
        
        # 体重の検証
        weight = player_data.get('weight')
        if weight:
            is_valid_weight, weight_issues = self.validate_weight(weight)
            all_issues.extend(weight_issues)
        
        # 出身校の検証
        school = player_data.get('school')
        if school:
            is_valid_school, school_issues, _ = self.validate_and_correct_school(school)
            all_issues.extend(school_issues)
        
        # 背番号の検証
        uniform_number = player_data.get('uniform_number')
        if uniform_number:
            is_valid_uniform, uniform_issues = self.validate_uniform_number(uniform_number)
            all_issues.extend(uniform_issues)
        
        return len(all_issues) == 0, all_issues

class FastCSVCorrectionSystem:
    """CSV訂正システム（改版）"""
    logger = logging.getLogger(__name__)
    
    def __init__(self, jba_system, gemini_api_key=None, max_workers=5):
        self.jba_system = jba_system
        self.validator = DataValidator(gemini_api_key)
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
        # 🆕 大学ごとのチームキャッシュ（Phase 1: 30倍高速化）
        self.university_teams_cache = {}
        self.team_members_cache = {}
        self.university_teams_data = {}
        
        # 🆕 Phase 3: 永続キャッシュ（2回目以降100倍高速）
        self.persistent_cache_file = "jba_player_cache.json"
        self.persistent_cache = self._load_persistent_cache()
        self.cache_dirty = False  # キャッシュが変更されたかどうか
    
    def _load_persistent_cache(self):
        """🆕 Phase 3: 永続キャッシュをファイルからロード"""
        if not os.path.exists(self.persistent_cache_file):
            return {}
        
        try:
            with open(self.persistent_cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
                # キャッシュの件数を表示（streamlitの外で実行される可能性があるため try-except）
                try:
                    logger.info(f"💾 永続キャッシュをロードしました: {len(cache)}件")
                except:
                    pass
                return cache
        except Exception as e:
            # キャッシュファイルが壊れている場合は無視
            return {}
    
    def _save_persistent_cache(self):
        """🆕 Phase 3: 永続キャッシュをファイルに保存"""
        if not self.cache_dirty:
            return
        
        try:
            with open(self.persistent_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.persistent_cache, f, ensure_ascii=False, indent=2)
            self.cache_dirty = False
        except Exception as e:
            # 保存に失敗しても処理は続行
            pass
    
    def _get_cache_key(self, player_name, university_name):
        """🆕 Phase 3: キャッシュキーを生成"""
        import hashlib
        # 選手名と大学名を正規化してハッシュ化
        normalized_name = self.jba_system.normalize_name(player_name)
        normalized_univ = self.jba_system.normalize_university_name(university_name)
        key_string = f"{normalized_name}_{normalized_univ}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _preload_university_data(self, university_name):
        """大学のチーム情報を事前に全て取得（1回だけ実行）"""
        if university_name in self.university_teams_data:
            return self.university_teams_data[university_name]
        
        # 🆕 プログレスバーとステータス表示
        # Status text placeholder removed
        # Progress bar removed - use job_meta instead
        
        # チーム検索（検索バリエーション対応）- 静かな実行
        status_text.info(f"🔍 {university_name}のチームを検索中...")
        search_variations = self.jba_system.get_search_variations(university_name)
        teams = []
        
        for i, variation in enumerate(search_variations):
            progress = (i + 1) / (len(search_variations) + 1)
            # Progress update removed  # 0-30%
            teams = self.jba_system._search_teams_by_university_silent(variation)
            if teams:
                break
        
        if not teams:
            status_text.warning(f"⚠️ {university_name}のチームが見つかりませんでした")
            # Progress bar cleanup removed
            with self.lock:
                self.university_teams_data[university_name] = None
            return None
        
        status_text.success(f"✅ {len(teams)}チーム発見！メンバー情報を取得中...")
        
        # 各チームのメンバーを取得 - 静かな実行
        teams_data = {}
        total_teams = len(teams)
        
        for idx, team in enumerate(teams):
            team_id = team['id']
            team_url = team['url']
            team_name = team['name']
            
            # プログレスバー更新（30-100%）
            progress = 0.3 + (0.7 * (idx + 1) / total_teams)
            # Progress update removed
            status_text.info(f"📥 チーム {idx+1}/{total_teams}: {team_name} のメンバーを取得中...")
            
            # 既にキャッシュにあれば使用
            if team_url in self.team_members_cache:
                team_data = self.team_members_cache[team_url]
            else:
                team_data = self.jba_system._get_team_members_silent(team_url)
                with self.lock:
                    self.team_members_cache[team_url] = team_data
            
            teams_data[team_id] = {
                'team_name': team['name'],
                'team_url': team_url,
                'members': team_data.get('members', [])
            }
        
        # 完了
        # Progress update removed
        total_members = sum(len(t['members']) for t in teams_data.values())
        status_text.success(f"✅ 事前ロード完了: {total_teams}チーム、{total_members}名の選手情報を取得")
        
        # プログレスバーとステータスを消去
        # Sleep removed  # 0.5秒表示
        # Progress bar cleanup removed
        status_text.empty()
        
        with self.lock:
            self.university_teams_data[university_name] = teams_data
        
        return teams_data
    
    def _find_player_from_cache(self, player_name, university_name):
        """🆕 キャッシュから選手を検索（ネットワークアクセスなし・超高速）"""
        teams_data = self.university_teams_data.get(university_name)
        
        if not teams_data:
            return {"status": "not_found", "message": f"{university_name}のチームデータが見つかりません"}
        
        all_matched_members = []
        
        # キャッシュされた全チームのメンバーを検索
        for team_id, team_info in teams_data.items():
            members = team_info.get('members', [])
            
            for member in members:
                # 名前の類似度チェック
                name_similarity = self.jba_system.calculate_similarity(player_name, member.get("name", ""))
                
                # 0.6以上の候補を保存
                if name_similarity >= 0.6:
                    # 完全一致
                    if name_similarity >= 1.0:
                        return {
                            "status": "match",
                            "jba_data": member,
                            "similarity": name_similarity
                        }
                    # 部分一致
                    else:
                        all_matched_members.append({
                            "status": "partial_match",
                            "jba_data": member,
                            "similarity": name_similarity,
                            "message": f"部分一致: {member['name']} (類似度: {name_similarity:.3f})"
                        })
        
        # 完全一致がなければ、部分一致を返す
        if all_matched_members:
            # 類似度が高い順にソート
            all_matched_members.sort(key=lambda x: x["similarity"], reverse=True)
            return all_matched_members[0]
        
        return {"status": "not_found", "message": f"{player_name}のJBA登録が見つかりませんでした"}
    
    def _process_single_player(self, row_data):
        """単一選手を処理（訂正必要な場合のみ情報を詰める）"""
        index, row, university_name, threshold = row_data
        
        try:
            player_name = None
            name_column = None
            name_columns = ['選手名', '氏名', 'name', 'Name']
            
            for col in name_columns:
                if col in row.index and pd.notna(row[col]):
                    player_name = str(row[col]).strip()
                    name_column = col
                    break
            
            if not player_name:
                return {
                    'index': index,
                    'original_data': row.to_dict(),
                    'status': 'missing_data',
                    'corrections': {},
                    'jba_data': {},
                    'validation_warnings': [],
                    'has_correction': False
                }
            
            # 🆕 Phase 3: 永続キャッシュをチェック（2回目以降は瞬時）
            cache_key = self._get_cache_key(player_name, university_name)
            if cache_key in self.persistent_cache:
                cached = self.persistent_cache[cache_key]
                cached['index'] = index
                cached['original_data'] = row.to_dict()
                return cached
            
            # 🆕 Phase 1: キャッシュから選手を検索（ネットワークアクセスなし・超高速）
            verification_result = self._find_player_from_cache(player_name, university_name)
            
            result = {
                'index': index,
                'original_data': row.to_dict(),
                'verification_result': verification_result,
                'status': verification_result.get('status', 'error'),
                'corrections': {},
                'jba_data': {},
                'validation_warnings': [],
                'has_correction': False
            }
            
            # jba_data を事前に初期化
            jba_data = {}
            
            if verification_result.get('status') in ['match', 'partial_match']:
                jba_data = verification_result.get('jba_data', {})
                result['jba_data'] = jba_data
                
                # 名前が異なる場合のみ訂正
                if jba_data.get('name') and jba_data['name'] != player_name:
                    result['corrections'][name_column] = jba_data['name']
                    result['has_correction'] = True
                
                # 体重：JBAにあれば優先し、元データと異なる場合のみ訂正
                if jba_data.get('weight') and str(jba_data['weight']).strip():
                    weight_value = str(jba_data['weight']).strip()
                    weight_match = re.search(r'(\d+\.?\d*)', weight_value)
                    if weight_match:
                        extracted_weight = weight_match.group(1)
                        try:
                            original_weight = float(row.get('体重', 0))
                            jba_weight = float(extracted_weight)
                            if original_weight != jba_weight:
                                result['corrections']['体重'] = extracted_weight
                                result['has_correction'] = True
                        except (ValueError, TypeError):
                            pass
                
                # 学年：JBAに記載があれば、数字だけを抽出し、元データと異なる場合のみ訂正
                if jba_data.get('grade') and str(jba_data['grade']).strip():
                    grade_value = str(jba_data['grade']).strip()
                    grade_match = re.search(r'(\d+)', grade_value)
                    if grade_match:
                        extracted_grade = grade_match.group(1)
                        try:
                            original_grade = str(row.get('学年', '')).strip()
                            if original_grade.isdigit():
                                original_grade_num = original_grade
                            else:
                                grade_num_match = re.search(r'(\d+)', original_grade)
                                original_grade_num = grade_num_match.group(1) if grade_num_match else original_grade
                            
                            if original_grade_num != extracted_grade:
                                result['corrections']['学年'] = extracted_grade
                                result['has_correction'] = True
                        except:
                            pass
                
                # 身長：JBAに記載があれば、数字だけを抽出し、元データと異なる場合のみ訂正
                if jba_data.get('height') and str(jba_data['height']).strip():
                    height_value = str(jba_data['height']).strip()
                    height_match = re.search(r'(\d+\.?\d*)', height_value)
                    if height_match:
                        extracted_height = height_match.group(1)
                        try:
                            original_height = float(row.get('身長', 0))
                            jba_height = float(extracted_height)
                            if original_height != jba_height:
                                result['corrections']['身長'] = extracted_height
                                result['has_correction'] = True
                        except (ValueError, TypeError):
                            pass
                
                # 元データの異常値をAIで検出（JBAにデータがない場合のみ）
                if not jba_data.get('weight') and not jba_data.get('height'):
                    validation_warnings = []  # AI機能は使用しない
                    result['validation_warnings'] = validation_warnings
            else:
                # JBA登録なし・未発見の場合も警告をチェック
                validation_warnings = []  # AI機能は使用しない
                result['validation_warnings'] = validation_warnings
            
            # 🆕 Phase 3: 結果を永続キャッシュに保存
            with self.lock:
                self.persistent_cache[cache_key] = {
                    'status': result['status'],
                    'corrections': result['corrections'],
                    'jba_data': result['jba_data'],
                    'validation_warnings': result['validation_warnings'],
                    'has_correction': result['has_correction']
                }
                self.cache_dirty = True
            
            return result
        
        except Exception as e:
            import traceback
            return {
                'index': index,
                'original_data': row.to_dict(),
                'status': 'error',
                'corrections': {},
                'jba_data': {},
                'validation_warnings': [f'エラー: {str(e)}'],
                'has_correction': False
            }
    
    def _validate_player_data_with_ai(self, row, jba_data):
        """元データの異常値を検出（JBAに記載がない場合のみ）"""
        warnings = []
        
        # 体重：JBAに記載がない場合のみ許容範囲でチェック
        if not jba_data.get('weight') and pd.notna(row.get('体重')):
            weight = row.get('体重')
            try:
                weight_value = float(weight)
                if weight_value < 45 or weight_value > 140:
                    warnings.append(f"⚠️ 体重が許容範囲外: {weight_value}kg (許容範囲: 45-140kg)")
            except (ValueError, TypeError):
                warnings.append(f"⚠️ 体重が数値ではない: {weight}")
        
        return warnings
    
    def process_csv_file_parallel(self, df, university_name, threshold=1.0):
        """CSVファイルを並列処理で高速に処理"""
        
        # Markdown removed
        # Subheader removed
        
        # 🆕 Phase 1: 大学データを事前に1回だけロード（30倍高速化）
        # Markdown removed
        preload_start = time.time()
        self._preload_university_data(university_name)
        preload_time = time.time() - preload_start
        
        # Markdown removed
        # Markdown removed
        logger.info(f"💨 並列処理モード: {self.max_workers}スレッドで高速処理中...")
        
        process_data = [
            (index, row, university_name, threshold)
            for index, row in df.iterrows()
        ]
        
        results = []
        # Progress bar removed - use job_meta instead
        # Status text placeholder removed
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._process_single_player, data): data[0] for data in process_data}
            
            completed = 0
            total = len(futures)
            update_interval = max(1, total // 20)  # 🆕 Phase 2: 20回だけ更新（5%ごと）
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                
                completed += 1
                
                # 🆕 Phase 2: 更新頻度を削減（5%ごと or 最終）
                if completed % update_interval == 0 or completed == total:
                    progress = completed / total
                    # Progress update removed
                    # Status text update removed")
        
        elapsed_time = time.time() - start_time
        
        # Progress update removed
        # Status text update removed
        
        # 🆕 Phase 3: 永続キャッシュをファイルに保存
        if self.cache_dirty:
            logger.info("💾 永続キャッシュを保存中...")
            self._save_persistent_cache()
            logger.info(f"✅ キャッシュを保存しました: {len(self.persistent_cache)}件")
        
        results.sort(key=lambda x: x['index'])
        
        # ★ 結果サマリーを表示
        logger.info(f"✅ {len(df)}行を{elapsed_time:.2f}秒で処理しました")
        
        # 統計情報
        matched = sum(1 for r in results if r['status'] == 'match')
        partial = sum(1 for r in results if r['status'] == 'partial_match')
        warnings_count = sum(len(r.get('validation_warnings', [])) for r in results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            pass
        with col2:
            pass
        with col3:
            pass
        with col4:
            pass
        
        return results
    
    def create_corrected_csv(self, df, results):
        """修正版CSVを作成（元の列順を保持、セル形式を保持）"""
        corrected_df = df.copy()
        
        for result in results:
            # 訂正がある場合のみ処理
            if not result.get('has_correction'):
                continue
            
            index = result['index']
            corrections = result.get('corrections', {})
            
            if not corrections:
                continue
            
            # 各修正項目をCSVに反映（列順は変わらない）
            for csv_col, corrected_value in corrections.items():
                if csv_col not in corrected_df.columns:
                    # 列が存在しない場合はスキップ（追加しない）
                    continue
                
                # 修正値を適用
                corrected_df.at[index, csv_col] = corrected_value
        
        return corrected_df
    
    # Excel出力は廃止 - PDFのみ使用

class CSVCorrectionSystem:
    """CSV自動訂正システム（従来版）"""
    logger = logging.getLogger(__name__)
    
    def __init__(self, jba_system, gemini_api_key=None):
        self.jba_system = jba_system
        self.validator = DataValidator(gemini_api_key)
    
    def process_csv_file(self, df, university_name, threshold=0.8, get_details=False):
        """CSVファイルを処理して訂正版を作成"""
        logger.info(f"📊 CSVファイルを処理中... ({len(df)}行)")
        logger.info(f"🔍 処理開始: 大学名={university_name}, 閾値={threshold}, 詳細取得={get_details}")
        
        results = []
        corrections = []
        
        # Progress bar removed - use job_meta instead
        # Status text placeholder removed
        
        for index, row in df.iterrows():
            progress = (index + 1) / len(df)
            # Progress update removed
            # Status text update removed} - {row.get('選手名', row.get('氏名', 'Unknown'))}")
            
            logger.info(f"🔍 行 {index + 1} を処理中...")
            
            # 選手名のみを取得
            player_name = None
            name_columns = ['選手名', '氏名', 'name', 'Name']
            
            for col in name_columns:
                if col in df.columns and pd.notna(row[col]):
                    player_name = str(row[col]).strip()
                    logger.info(f"  - 選手名取得: {player_name} (カラム: {col})")
                    break
            
            if not player_name:
                logger.warning(f"  - 選手名が取得できませんでした")
                results.append({
                    'index': index,
                    'original_data': row.to_dict(),
                    'status': 'missing_data',
                    'message': '選手名が不足しています',
                    'correction': None
                })
                continue
            
            # JBAデータベースとの照合
            verification_result = self.jba_system.verify_player_info(
                player_name, None, university_name, get_details, threshold
            )
            
            result = {
                'index': index,
                'original_data': row.to_dict(),
                'verification_result': verification_result,
                'status': verification_result['status']
            }
            
            # 完全一致の場合
            if verification_result['status'] == 'match':
                if get_details and 'jba_data' in verification_result:
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
                            result['school_correction'] = f"{jba_data['school']} → {school_corrections['school']}"
                        else:
                            corrected_data['出身校'] = jba_data['school']
                    if 'grade' in jba_data and jba_data['grade']:
                        corrected_data['学年'] = jba_data['grade']
                    if 'uniform_number' in jba_data and jba_data['uniform_number']:
                        corrected_data['背番号'] = jba_data['uniform_number']
                    
                    if not is_valid:
                        result['validation_issues'] = validation_issues
                        result['message'] = f'JBAデータベースと完全一致（詳細情報追加）⚠️ 異常値検出: {", ".join(validation_issues)}'
                    else:
                        result['message'] = 'JBAデータベースと完全一致（詳細情報追加）'
                    
                    result['correction'] = corrected_data
                else:
                    result['correction'] = None
                    result['message'] = 'JBAデータベースと完全一致'
            
            # 部分一致の場合
            elif verification_result['status'] == 'partial_match':
                jba_data = verification_result['jba_data']
                similarity = verification_result.get('similarity', 0.0)
                
                corrected_data = row.to_dict().copy()
                
                if get_details:
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
        
        # Progress update removed
        # Status text update removed
        
        return results, corrections
    
    def create_corrected_csv(self, df, results):
        """訂正版CSVを作成（訂正部分を赤字で表示）"""
        corrected_df = df.copy()
        
        # 訂正を適用
        for result in results:
            if result['correction']:
                index = result['index']
                corrected_data = result['correction']
                
                # 各カラムを更新
                for col, value in corrected_data.items():
                    if col in corrected_df.columns:
                        # 元の値と異なる場合のみ訂正
                        original_value = corrected_df.at[index, col]
                        if original_value != value:
                            # 訂正された値を赤字で表示
                            corrected_df.at[index, col] = f"🔴 {value}"
        
        return corrected_df

def main():
    """メイン関数（Streamlit UI は削除済み）"""
    # Streamlit UI は削除済み - 何もしない
    pass

# 統合システムを使用するため、このファイルは直接実行しない
# if __name__ == "__main__":
#     main()
