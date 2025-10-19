#!/usr/bin/env python3
"""
CSV自動訂正システム
JBAデータベースと照合してCSVファイルを自動訂正
"""

import streamlit as st
import pandas as pd
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import re
import unicodedata
from difflib import SequenceMatcher
import io
import google.generativeai as genai
import os

# ページ設定
st.set_page_config(
    page_title="CSV自動訂正システム",
    page_icon="🏀",
    layout="wide"
)

class JBAVerificationSystem:
    """JBA検証システム（requests + BeautifulSoupベース）"""
    
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
        """大学名の検索バリエーションを生成"""
        if not university_name:
            return []
        
        variations = [university_name.strip()]
        
        # 長い大学名の場合、短縮バリエーションも追加
        if len(university_name) > 6:  # 長い名前の場合
            # 語尾を段階的に削除
            suffixes_to_remove = ['体育会バスケットボール部', 'バスケットボール部', '体育会', '部']
            
            for suffix in suffixes_to_remove:
                if university_name.endswith(suffix):
                    base_name = university_name[:-len(suffix)].strip()
                    if base_name and len(base_name) > 2:  # 最低3文字以上
                        variations.append(base_name)
        
        # 重複を削除
        return list(set(variations))
    
    def login(self, email, password):
        """JBAサイトにログイン"""
        try:
            st.info("🔐 JBAサイトにログイン中...")
            
            login_page = self.session.get("https://team-jba.jp/login")
            soup = BeautifulSoup(login_page.content, 'html.parser')
            
            csrf_token = ""
            csrf_input = soup.find('input', {'name': '_token'})
            if csrf_input:
                csrf_token = csrf_input.get('value', '')
            
            login_data = {
                '_token': csrf_token,
                'login_id': email,
                'password': password
            }
            
            login_url = "https://team-jba.jp/login/done"
            login_response = self.session.post(login_url, data=login_data, allow_redirects=True)
            
            if "ログアウト" in login_response.text:
                st.success("✅ ログイン成功")
                self.logged_in = True
                return True
            else:
                st.error("❌ ログインに失敗しました")
                return False
                
        except Exception as e:
            st.error(f"❌ ログインエラー: {str(e)}")
            return False
    
    def search_teams_by_university(self, university_name):
        """大学名でチームを検索（柔軟な照合）"""
        try:
            if not self.logged_in:
                st.error("❌ ログインが必要です")
                return []
            
            current_year = self.get_current_fiscal_year()
            st.info(f"🔍 {university_name}の男子チームを検索中... ({current_year}年度)")
            
            # 大学名の正規化（柔軟な照合のため）
            normalized_university = self.normalize_university_name(university_name)
            st.info(f"🔍 正規化された大学名: {normalized_university}")
            
            # 正規化された大学名で検索
            search_university = normalized_university
            
            # 検索ページにアクセスしてCSRFトークンを取得
            search_url = "https://team-jba.jp/organization/15250600/team/search"
            search_page = self.session.get(search_url)
            
            if search_page.status_code != 200:
                st.error("❌ 検索ページにアクセスできません")
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
                st.error("❌ 検索リクエストが失敗しました")
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
                
                st.success(f"✅ {university_name}の男子チーム: {len(teams)}件見つかりました")
                return teams
                
            except Exception as e:
                st.error(f"❌ 検索結果の解析に失敗しました: {str(e)}")
                return []
            
        except Exception as e:
            st.error(f"❌ チーム検索エラー: {str(e)}")
            return []
    
    def get_team_members(self, team_url):
        """チームのメンバー情報を取得（男子チームのみ）"""
        try:
            st.info(f"📊 チームメンバー情報を取得中...")
            
            # チーム詳細ページにアクセス
            team_page = self.session.get(team_url)
            
            if team_page.status_code != 200:
                st.error(f"❌ チームページにアクセスできません (Status: {team_page.status_code})")
                return {"team_name": "Error", "members": []}
            
            soup = BeautifulSoup(team_page.content, 'html.parser')
            
            # チーム名を取得
            team_name = "Unknown Team"
            title_element = soup.find('title')
            if title_element:
                team_name = title_element.get_text(strip=True)

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
            st.error(f"❌ メンバー取得エラー: {str(e)}")
            import traceback
            st.write(f"**エラー詳細**: {traceback.format_exc()}")
            return {"team_name": "Error", "team_url": team_url, "members": []}
    
    def get_player_details(self, detail_url):
        """選手詳細ページから身長・体重などの詳細情報を取得"""
        try:
            if not detail_url:
                return {}
            
            st.info(f"🔍 選手詳細情報を取得中: {detail_url}")
            
            # 選手詳細ページにアクセス
            detail_page = self.session.get(detail_url)
            
            if detail_page.status_code != 200:
                st.warning(f"⚠️ 選手詳細ページにアクセスできません (Status: {detail_page.status_code})")
                return {}
            
            soup = BeautifulSoup(detail_page.content, 'html.parser')
            
            # 選手詳細情報を抽出
            player_details = {}
            
            # 身長・体重情報を探す
            # 一般的なパターンを試す
            height_patterns = [
                r'身長[：:]\s*(\d+\.?\d*)\s*cm',
                r'身長[：:]\s*(\d+\.?\d*)\s*センチ',
                r'Height[：:]\s*(\d+\.?\d*)\s*cm'
            ]
            
            weight_patterns = [
                r'体重[：:]\s*(\d+\.?\d*)\s*kg',
                r'体重[：:]\s*(\d+\.?\d*)\s*キロ',
                r'Weight[：:]\s*(\d+\.?\d*)\s*kg'
            ]
            
            # テーブルから情報を抽出
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        
                        # 身長情報（JBAの「身長（競技者用）」に対応）
                        if '身長' in label or 'Height' in label:
                            # 数値部分を抽出
                            import re
                            height_match = re.search(r'(\d+\.?\d*)', value)
                            if height_match and value.strip():  # 空でない場合のみ
                                player_details['height'] = height_match.group(1)
                        
                        # 体重情報（JBAの「体重（競技者用）」に対応）
                        elif '体重' in label or 'Weight' in label:
                            # 数値部分を抽出
                            import re
                            weight_match = re.search(r'(\d+\.?\d*)', value)
                            if weight_match and value.strip():  # 空でない場合のみ
                                player_details['weight'] = weight_match.group(1)
                        
                        # ポジション情報
                        elif 'ポジション' in label or 'Position' in label:
                            player_details['position'] = value
                        
                        # 出身校情報
                        elif '出身校' in label or '出身' in label:
                            player_details['school'] = value
                        
                        # 学年情報
                        elif '学年' in label or 'Grade' in label:
                            player_details['grade'] = value
                        
                        # ユニフォーム番号
                        elif 'ユニフォーム番号' in label or '背番号' in label:
                            player_details['uniform_number'] = value
            
            # テーブルで見つからない場合は、ページ全体から正規表現で検索
            if 'height' not in player_details or 'weight' not in player_details:
                page_text = soup.get_text()
                
                # 身長を検索
                for pattern in height_patterns:
                    import re
                    match = re.search(pattern, page_text)
                    if match:
                        player_details['height'] = match.group(1)
                        break
                
                # 体重を検索
                for pattern in weight_patterns:
                    import re
                    match = re.search(pattern, page_text)
                    if match:
                        player_details['weight'] = match.group(1)
                        break
            
            return player_details
            
        except Exception as e:
            st.warning(f"⚠️ 選手詳細取得エラー: {str(e)}")
            return {}
    
    def normalize_date_format(self, date_str):
        """日付フォーマットを統一（JBAの「2004年5月31日」形式に対応）"""
        try:
            if not date_str:
                return ""

            # JBAの「2004年5月31日」形式を処理
            if "年" in date_str and "月" in date_str and "日" in date_str:
                # 「2004年5月31日」→「2004/5/31」に変換
                import re
                match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
                if match:
                    year, month, day = match.groups()
                    return f"{year}/{int(month)}/{int(day)}"

            # 既に統一された形式の場合はそのまま返す
            if "/" in date_str and len(date_str.split("/")) == 3:
                parts = date_str.split("/")
                year = parts[0]
                month = str(int(parts[1]))  # 先頭の0を削除
                day = str(int(parts[2]))    # 先頭の0を削除
                return f"{year}/{month}/{day}"

            return date_str
        except:
            return date_str

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

    def verify_player_info(self, player_name, birth_date, university, get_details=False):
        """個別選手情報の照合（男子チームのみ）"""
        try:
            # デバッグ情報を表示
            st.write(f"🔍 選手照合: {player_name}, 大学: {university}")
            
            # 大学名の検索バリエーションを生成
            search_variations = self.get_search_variations(university)
            st.write(f"🔍 検索バリエーション: {search_variations}")
            
            teams = []
            for variation in search_variations:
                st.write(f"🔍 チーム検索開始: {variation}")
                teams = self.search_teams_by_university(variation)
                st.write(f"🔍 検索結果: {len(teams)}チーム見つかりました")
                
                if teams:
                    st.success(f"✅ {variation}でチームが見つかりました")
                    break
                else:
                    st.info(f"❌ {variation}ではチームが見つかりませんでした")
            
            if not teams:
                st.warning(f"❌ {university}の男子チームが見つかりませんでした")
                return {"status": "not_found", "message": f"{university}の男子チームが見つかりませんでした"}

            # 各チームのメンバー情報を取得して照合
            for team in teams:
                team_data = self.get_team_members(team['url'])
                if team_data and team_data["members"]:
                    for member in team_data["members"]:
                        # 名前の類似度チェック
                        name_similarity = self.calculate_similarity(player_name, member["name"])

                        # デバッグ情報を表示
                        st.write(f"  - JBA選手: {member['name']}")
                        st.write(f"  - 名前類似度: {name_similarity:.3f}")
                        
                        if name_similarity >= threshold:
                            st.success(f"✅ 完全一致: {member['name']}")
                            # 詳細情報を取得する場合
                            if get_details and member.get("detail_url"):
                                player_details = self.get_player_details(member["detail_url"])
                                member.update(player_details)
                            
                            return {
                                "status": "match",
                                "jba_data": member,
                                "similarity": name_similarity
                            }

            return {"status": "not_found", "message": "JBAデータベースに該当する選手が見つかりませんでした"}

        except Exception as e:
            return {"status": "error", "message": f"照合エラー: {str(e)}"}

class GeminiValidator:
    """Google Gemini APIを使用したAI検証システム"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
    
    def validate_weight_with_ai(self, weight):
        """Gemini APIを使用した体重検証"""
        if not self.api_key or not self.model:
            return {'is_valid': True, 'reason': 'Gemini APIキーが設定されていません', 'correction': None}
        
        try:
            prompt = f"""
            以下の体重データが正常かどうかを判断してください。
            バスケットボール選手（成人男性）の体重として妥当かどうかを評価してください。
            
            体重: {weight}kg
            
            以下のJSON形式で回答してください：
            {{
                "status": "normal|abnormal|correction",
                "reason": "理由の説明",
                "suggested_value": "推奨値（訂正の場合のみ）"
            }}
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            try:
                # JSON形式の回答を解析
                import json
                data = json.loads(result)
                
                if data.get("status") == "abnormal":
                    return {'is_valid': False, 'reason': f'AI検証: {data.get("reason", "異常な体重です")}', 'correction': None}
                elif data.get("status") == "correction":
                    return {'is_valid': False, 'reason': f'AI検証: {data.get("reason", "訂正が必要です")}', 'correction': data.get("suggested_value")}
                else:
                    return {'is_valid': True, 'reason': 'AI検証: 正常', 'correction': None}
            except (json.JSONDecodeError, KeyError):
                # JSON解析に失敗した場合は従来の方法で判定
                result_lower = result.lower()
                if "異常" in result_lower or "abnormal" in result_lower:
                    return {'is_valid': False, 'reason': f'AI検証: {result}', 'correction': None}
                elif "訂正" in result_lower or "correction" in result_lower:
                    return {'is_valid': False, 'reason': f'AI検証: {result}', 'correction': None}
                else:
                    return {'is_valid': True, 'reason': 'AI検証: 正常', 'correction': None}
                
        except Exception as e:
            return {'is_valid': True, 'reason': f'Gemini API エラー: {str(e)}', 'correction': None}
    
    def validate_and_correct_school_with_ai(self, school_name):
        """Gemini APIを使用した出身校検証と訂正"""
        if not self.api_key or not self.model:
            return {'is_valid': True, 'reason': 'Gemini APIキーが設定されていません', 'correction': None}
        
        try:
            prompt = f"""
            以下の出身校名を検証し、必要に応じて訂正してください。
            
            出身校名: {school_name}
            
            以下の点を確認してください：
            1. 学校名として妥当かどうか
            2. 漢字の間違いがないか
            3. 正式名称に訂正が必要かどうか
            4. 留学生の場合は適切に処理する
            
            以下のJSON形式で回答してください：
            {{
                "status": "normal|abnormal|correction",
                "reason": "理由の説明",
                "corrected_name": "訂正後の学校名（訂正の場合のみ）"
            }}
            """
            
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            try:
                # JSON形式の回答を解析
                import json
                data = json.loads(result)
                
                if data.get("status") == "abnormal":
                    return {'is_valid': False, 'reason': f'AI検証: {data.get("reason", "異常な学校名です")}', 'correction': None}
                elif data.get("status") == "correction":
                    corrected_name = data.get("corrected_name", "")
                    return {'is_valid': True, 'reason': f'AI検証: {data.get("reason", "訂正が必要です")}', 'correction': corrected_name}
                else:
                    return {'is_valid': True, 'reason': 'AI検証: 正常', 'correction': None}
            except (json.JSONDecodeError, KeyError):
                # JSON解析に失敗した場合は従来の方法で判定
                result_lower = result.lower()
                if "異常" in result_lower or "abnormal" in result_lower:
                    return {'is_valid': False, 'reason': f'AI検証: {result}', 'correction': None}
                elif "訂正" in result_lower or "correction" in result_lower:
                    # 訂正された学校名を抽出
                    correction_match = re.search(r'訂正: (.+)', result)
                    if correction_match:
                        corrected_name = correction_match.group(1).strip()
                        return {'is_valid': True, 'reason': f'AI検証: {result}', 'correction': corrected_name}
                    else:
                        return {'is_valid': True, 'reason': f'AI検証: {result}', 'correction': None}
                else:
                    return {'is_valid': True, 'reason': 'AI検証: 正常', 'correction': None}
                
        except Exception as e:
            return {'is_valid': True, 'reason': f'Gemini API エラー: {str(e)}', 'correction': None}

class DataValidator:
    """データ検証システム"""
    
    def __init__(self, gemini_api_key=None):
        # Gemini API検証システム
        self.gemini_validator = GeminiValidator(gemini_api_key)
    
    def validate_weight(self, weight):
        """体重の妥当性を検証（Gemini API版）"""
        if not weight:
            return True, []
        
        # Gemini APIによる検証
        ai_validation = self.gemini_validator.validate_weight_with_ai(weight)
        if not ai_validation['is_valid']:
            return False, [ai_validation['reason']]
        
        return True, []
    
    def validate_and_correct_school(self, school_name):
        """出身校の妥当性を検証し、必要に応じて訂正を提案（Gemini API版）"""
        if not school_name or school_name.strip() == "":
            return True, [], None  # 空の場合は問題なし
        
        issues = []
        correction = None
        
        # Gemini APIによる出身校検証と訂正
        ai_validation = self.gemini_validator.validate_and_correct_school_with_ai(school_name)
        if not ai_validation['is_valid']:
            issues.append(ai_validation['reason'])
        elif ai_validation['correction']:
            correction = ai_validation['correction']
            issues.append(f"出身校名を訂正: {school_name} → {correction}")
        
        return len(issues) == 0, issues, correction
    
    
    def validate_player_data(self, player_data):
        """選手データ全体の妥当性を検証（体重・出身校のみ）"""
        all_issues = []
        corrections = {}
        
        # 体重の検証（身長は基本的に記載されているため除外）
        weight = player_data.get('weight')
        if weight:
            is_valid_weight, weight_issues = self.validate_weight(weight)
            all_issues.extend(weight_issues)
        
        # 出身校の検証と訂正
        school = player_data.get('school')
        if school:
            is_valid_school, school_issues, school_correction = self.validate_and_correct_school(school)
            all_issues.extend(school_issues)
            if school_correction:
                corrections['school'] = school_correction
        
        return len(all_issues) == 0, all_issues, corrections

class CSVCorrectionSystem:
    """CSV自動訂正システム"""
    
    def __init__(self, jba_system, gemini_api_key=None):
        self.jba_system = jba_system
        self.validator = DataValidator(gemini_api_key)
    
    def process_csv_file(self, df, university_name, threshold=0.8, get_details=False):
        """CSVファイルを処理して訂正版を作成"""
        st.info(f"📊 CSVファイルを処理中... ({len(df)}行)")
        st.write(f"🔍 処理開始: 大学名={university_name}, 閾値={threshold}, 詳細取得={get_details}")
        
        # 結果を保存するためのリスト
        results = []
        corrections = []
        
        # プログレスバー
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, row in df.iterrows():
            # プログレス更新
            progress = (index + 1) / len(df)
            progress_bar.progress(progress)
            status_text.text(f"処理中: {index + 1}/{len(df)} - {row.get('名前', row.get('氏名', 'Unknown'))}")
            
            # デバッグ情報を表示
            st.write(f"🔍 行 {index + 1} を処理中...")
            
            # 選手名のみを取得（生年月日は不要）
            player_name = None
            
            # 様々なカラム名に対応
            name_columns = ['名前', '氏名', '選手名', 'name', 'Name']
            
            for col in name_columns:
                if col in df.columns and pd.notna(row[col]):
                    player_name = str(row[col]).strip()
                    st.write(f"  - 選手名取得: {player_name} (カラム: {col})")
                    break
            
            if not player_name:
                st.warning(f"  - 選手名が取得できませんでした")
                results.append({
                    'index': index,
                    'original_data': row.to_dict(),
                    'status': 'missing_data',
                    'message': '選手名が不足しています',
                    'correction': None
                })
                continue
            
            # JBAデータベースと照合（詳細情報も取得するかどうか）
            verification_result = self.jba_system.verify_player_info(
                player_name, None, university_name, get_details
            )
            
            # 結果を保存
            result = {
                'index': index,
                'original_data': row.to_dict(),
                'verification_result': verification_result,
                'status': verification_result['status']
            }
            
            # 訂正が必要な場合
            if verification_result['status'] == 'match':
                # 完全一致の場合、詳細情報があれば追加
                if get_details and 'jba_data' in verification_result:
                    jba_data = verification_result['jba_data']
                    
                    # データ検証と訂正を実行
                    is_valid, validation_issues, corrections = self.validator.validate_player_data(jba_data)
                    
                    corrected_data = row.to_dict().copy()
                    
                    # 検証を通過した情報のみ追加
                    if 'height' in jba_data and jba_data['height']:
                        corrected_data['身長'] = f"{jba_data['height']}cm"
                    if 'weight' in jba_data and jba_data['weight']:
                        corrected_data['体重'] = f"{jba_data['weight']}kg"
                    if 'position' in jba_data and jba_data['position']:
                        corrected_data['ポジション'] = jba_data['position']
                    if 'school' in jba_data and jba_data['school']:
                        # 出身校の訂正を適用
                        if 'school' in corrections:
                            corrected_data['出身校'] = corrections['school']
                            result['school_correction'] = f"{jba_data['school']} → {corrections['school']}"
                        else:
                            corrected_data['出身校'] = jba_data['school']
                    if 'grade' in jba_data and jba_data['grade']:
                        corrected_data['学年'] = jba_data['grade']
                    if 'uniform_number' in jba_data and jba_data['uniform_number']:
                        corrected_data['背番号'] = jba_data['uniform_number']
                    
                    # 検証結果を記録
                    if not is_valid:
                        result['validation_issues'] = validation_issues
                        result['message'] = f'JBAデータベースと完全一致（詳細情報追加）⚠️ 異常値検出: {", ".join(validation_issues)}'
                    else:
                        result['message'] = 'JBAデータベースと完全一致（詳細情報追加）'
                    
                    result['correction'] = corrected_data
                else:
                    result['correction'] = None
                    result['message'] = 'JBAデータベースと完全一致'
            elif verification_result['status'] == 'name_match_birth_mismatch':
                # 名前は一致するが生年月日が異なる場合
                jba_data = verification_result['jba_data']
                
                # データ検証と訂正を実行
                is_valid, validation_issues, corrections = self.validator.validate_player_data(jba_data)
                
                corrected_data = row.to_dict().copy()
                
                # 生年月日をJBAデータに合わせて訂正
                corrected_data['生年月日'] = jba_data['birth_date']
                if '誕生日' in corrected_data:
                    corrected_data['誕生日'] = jba_data['birth_date']
                
                # 詳細情報があれば追加（検証を通過した情報のみ）
                if get_details:
                    if 'height' in jba_data and jba_data['height']:
                        corrected_data['身長'] = f"{jba_data['height']}cm"
                    if 'weight' in jba_data and jba_data['weight']:
                        corrected_data['体重'] = f"{jba_data['weight']}kg"
                    if 'position' in jba_data and jba_data['position']:
                        corrected_data['ポジション'] = jba_data['position']
                    if 'school' in jba_data and jba_data['school']:
                        # 出身校の訂正を適用
                        if 'school' in corrections:
                            corrected_data['出身校'] = corrections['school']
                            result['school_correction'] = f"{jba_data['school']} → {corrections['school']}"
                        else:
                            corrected_data['出身校'] = jba_data['school']
                    if 'grade' in jba_data and jba_data['grade']:
                        corrected_data['学年'] = jba_data['grade']
                    if 'uniform_number' in jba_data and jba_data['uniform_number']:
                        corrected_data['背番号'] = jba_data['uniform_number']
                
                # 検証結果を記録
                if not is_valid:
                    result['validation_issues'] = validation_issues
                    result['message'] = f"生年月日を訂正: {birth_date} → {jba_data['birth_date']} ⚠️ 異常値検出: {', '.join(validation_issues)}"
                else:
                    result['message'] = f"生年月日を訂正: {birth_date} → {jba_data['birth_date']}"
                
                result['correction'] = corrected_data
                corrections.append({
                    'index': index,
                    'original': row.to_dict(),
                    'corrected': corrected_data,
                    'reason': '生年月日の不一致'
                })
            else:
                # 照合できない場合
                result['correction'] = None
                result['message'] = verification_result.get('message', '照合できませんでした')
            
            results.append(result)
        
        progress_bar.progress(1.0)
        status_text.text("✅ 処理完了")
        
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
    """メイン関数"""
    # セッション状態の初期化
    if 'jba_logged_in' not in st.session_state:
        st.session_state.jba_logged_in = False
    if 'jba_system' not in st.session_state:
        st.session_state.jba_system = None
    if 'csv_system' not in st.session_state:
        st.session_state.csv_system = None
    if 'uploaded_df' not in st.session_state:
        st.session_state.uploaded_df = None
    if 'university_name' not in st.session_state:
        st.session_state.university_name = ""
    if 'threshold' not in st.session_state:
        st.session_state.threshold = 0.8
    if 'get_details' not in st.session_state:
        st.session_state.get_details = False
    
    st.title("🏀 CSV自動訂正システム")
    st.markdown("**JBAデータベースと照合してCSVファイルを自動訂正します**")
    
    # カスタムCSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #2563eb, #3b82f6);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.header("🔐 JBAログイン情報")
        email = st.text_input("JBAメールアドレス", type="default")
        password = st.text_input("JBAパスワード", type="password")
        
        if st.button("JBAにログイン", type="primary"):
            if email and password:
                # JBAシステムの初期化
                if st.session_state.jba_system is None:
                    st.session_state.jba_system = JBAVerificationSystem()
                
                if st.session_state.jba_system.login(email, password):
                    st.session_state.jba_logged_in = True
                    st.success("ログイン成功")
                else:
                    st.session_state.jba_logged_in = False
                    st.error("ログイン失敗")
            else:
                st.error("ログイン情報を入力してください")
        
        # ログイン状態の表示
        if st.session_state.jba_logged_in:
            st.success("✅ JBAにログイン済み")
        else:
            st.warning("⚠️ JBAにログインしてください")
        
        # 内部設定（表示なし）
        threshold = 1.0  # 完全一致のみ
        get_details = True  # 常にオン
        gemini_api_key = "AIzaSyBCX-rsrYsGbPCHrlWXdd2ECAxmbTqTJ34"  # 固定
        use_ai_validation = True  # 常にオン
    
    # システム初期化
    if 'jba_system' not in st.session_state:
        st.session_state.jba_system = JBAVerificationSystem()
    
    # ログイン状態の復元チェック
    if 'jba_logged_in' not in st.session_state:
        st.session_state.jba_logged_in = False
    
    # CSVシステムを毎回更新（APIキーの変更に対応）
    if st.session_state.jba_system is not None:
        st.session_state.csv_system = CSVCorrectionSystem(st.session_state.jba_system, gemini_api_key if use_ai_validation else None)
    else:
        st.session_state.csv_system = None
    
    # メインコンテンツ
    st.header("📄 CSVファイル処理")
    
    # 大学名入力
    university_name = st.text_input("大学名", placeholder="例: 白鴎大学", help="JBAデータベースに登録されている大学名を入力してください")
    
    # CSVファイルアップロード
    uploaded_file = st.file_uploader(
        "CSVファイルをアップロード",
        type=['csv'],
        help="選手名と生年月日が含まれるCSVファイルをアップロードしてください"
    )
    
    if uploaded_file is not None:
        try:
            # CSVファイルを読み込み（複数のエンコーディングを試行）
            encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig', 'iso-2022-jp']
            df = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)  # ファイルポインタをリセット
                    df = pd.read_csv(uploaded_file, encoding=encoding)
                    st.success(f"✅ CSVファイルを読み込みました ({len(df)}行) - エンコーディング: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                st.error("❌ CSVファイルの文字エンコーディングが判別できませんでした。ファイルをUTF-8で保存し直してください。")
                st.stop()
            
            # データプレビュー
            st.subheader("📊 データプレビュー")
            st.dataframe(df.head())
            
            # カラム情報
            st.subheader("📋 カラム情報")
            st.write(f"カラム数: {len(df.columns)}")
            st.write(f"カラム名: {list(df.columns)}")
            
            # 処理実行
            if st.button("🚀 自動訂正を実行", type="primary"):
                if not st.session_state.jba_logged_in:
                    st.error("❌ 先にJBAにログインしてください")
                elif not university_name:
                    st.error("❌ 大学名を入力してください")
                elif st.session_state.csv_system is None:
                    st.error("❌ CSVシステムが初期化されていません。JBAにログインしてください。")
                else:
                    # デバッグ情報を表示
                    st.info(f"🔍 デバッグ情報:")
                    st.write(f"- 大学名: {university_name}")
                    st.write(f"- データ行数: {len(df)}")
                    st.write(f"- カラム名: {list(df.columns)}")
                    st.write(f"- JBAログイン状態: {st.session_state.jba_logged_in}")
                    st.write(f"- 類似度閾値: {threshold}")
                    st.write(f"- 詳細情報取得: {get_details}")
                    
                    # 最初の数行のデータを表示
                    st.write("**最初の3行のデータ:**")
                    st.dataframe(df.head(3))
                    
                    # CSV処理実行
                    results, corrections = st.session_state.csv_system.process_csv_file(
                        df, university_name, threshold, get_details
                    )
                    
                    # 結果表示
                    st.subheader("📊 処理結果")
                    
                    # 統計情報
                    total_records = len(results)
                    matched_count = sum(1 for r in results if r['status'] == 'match')
                    corrected_count = len(corrections)
                    not_found_count = sum(1 for r in results if r['status'] == 'not_found')
                    validation_issues_count = sum(1 for r in results if 'validation_issues' in r)
                    school_correction_count = sum(1 for r in results if 'school_correction' in r)
                    
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    with col1:
                        st.metric("総件数", total_records)
                    with col2:
                        st.metric("完全一致", matched_count)
                    with col3:
                        st.metric("訂正件数", corrected_count)
                    with col4:
                        st.metric("未発見", not_found_count)
                    with col5:
                        st.metric("⚠️ 異常値", validation_issues_count, help="体重・出身校に異常値が検出された件数（AI検証）")
                    with col6:
                        st.metric("🏫 出身校訂正", school_correction_count, help="出身校名が自動訂正された件数（AI検証）")
                    
                    # 訂正版CSVを作成
                    corrected_df = st.session_state.csv_system.create_corrected_csv(df, results)
                    
                    # 訂正版CSVをダウンロード（文字化け対策）
                    csv_buffer = io.StringIO()
                    corrected_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                    csv_data = csv_buffer.getvalue()
                    
                    st.download_button(
                        label="📥 訂正版CSVをダウンロード",
                        data=csv_data.encode('utf-8-sig'),
                        file_name=f"corrected_{uploaded_file.name}",
                        mime="text/csv"
                    )
                    
                    # 詳細結果表示
                    st.subheader("📋 詳細結果")
                    
                    # タブで結果を分ける
                    tab1, tab2, tab3, tab4 = st.tabs(["完全一致", "訂正済み", "未発見", "⚠️ 異常値検出"])
                    
                    with tab1:
                        matched_results = [r for r in results if r['status'] == 'match']
                        if matched_results:
                            st.write(f"**完全一致: {len(matched_results)}件**")
                            for result in matched_results:
                                with st.expander(f"行 {result['index'] + 1}: {result['original_data'].get('名前', result['original_data'].get('氏名', 'Unknown'))}"):
                                    st.write("**元データ:**")
                                    st.json(result['original_data'])
                                    st.write("**照合結果:**")
                                    st.json(result['verification_result'])
                        else:
                            st.info("完全一致したデータはありません")
                    
                    with tab2:
                        if corrections:
                            st.write(f"**訂正済み: {len(corrections)}件**")
                            for correction in corrections:
                                with st.expander(f"行 {correction['index'] + 1}: {correction['original'].get('名前', correction['original'].get('氏名', 'Unknown'))}"):
                                    st.write("**訂正前:**")
                                    st.json(correction['original'])
                                    st.write("**訂正後 (JBAデータベースの正しい情報):**")
                                    st.json(correction['corrected'])
                                    st.info("🔴 赤字で表示された部分がJBAデータベースで訂正された情報です")
                                    if 'reason' in correction:
                                        st.write(f"**訂正理由:** {correction['reason']}")
                                    else:
                                        st.write("**訂正理由:** JBAデータベースの正しい情報に基づいて訂正")
                        else:
                            st.info("訂正されたデータはありません")
                    
                    with tab3:
                        not_found_results = [r for r in results if r['status'] == 'not_found']
                        if not_found_results:
                            st.write(f"**未発見: {len(not_found_results)}件**")
                            for result in not_found_results:
                                with st.expander(f"行 {result['index'] + 1}: {result['original_data'].get('名前', result['original_data'].get('氏名', 'Unknown'))}"):
                                    st.write("**元データ:**")
                                    st.json(result['original_data'])
                                    st.write("**照合結果:**")
                                    st.json(result['verification_result'])
                        else:
                            st.info("未発見のデータはありません")
                    
                    with tab4:
                        validation_issues_results = [r for r in results if 'validation_issues' in r]
                        school_correction_results = [r for r in results if 'school_correction' in r]
                        
                        if validation_issues_results or school_correction_results:
                            st.write(f"**異常値検出: {len(validation_issues_results)}件**")
                            if school_correction_results:
                                st.write(f"**出身校訂正: {len(school_correction_results)}件**")
                            st.warning("⚠️ 以下のデータに異常値が検出されました（体重・出身校のAI検証）。手動で確認してください。")
                            
                            # 異常値検出の結果
                            for result in validation_issues_results:
                                with st.expander(f"行 {result['index'] + 1}: {result['original_data'].get('名前', result['original_data'].get('氏名', 'Unknown'))} - 異常値検出"):
                                    st.write("**元データ:**")
                                    st.json(result['original_data'])
                                    
                                    st.write("**検出された異常値:**")
                                    for issue in result['validation_issues']:
                                        st.error(f"❌ {issue}")
                                    
                                    if result['correction']:
                                        st.write("**訂正版データ（異常値は除外）:**")
                                        st.json(result['correction'])
                                    
                                    st.write("**照合結果:**")
                                    st.json(result['verification_result'])
                            
                            # 出身校訂正の結果
                            for result in school_correction_results:
                                with st.expander(f"行 {result['index'] + 1}: {result['original_data'].get('名前', result['original_data'].get('氏名', 'Unknown'))} - 出身校訂正"):
                                    st.write("**元データ:**")
                                    st.json(result['original_data'])
                                    
                                    st.write("**出身校訂正:**")
                                    st.success(f"✅ {result['school_correction']}")
                                    
                                    if result['correction']:
                                        st.write("**訂正版データ:**")
                                        st.json(result['correction'])
                                    
                                    st.write("**照合結果:**")
                                    st.json(result['verification_result'])
                        else:
                            st.success("✅ 異常値は検出されませんでした")
        
        except Exception as e:
            st.error(f"❌ CSVファイルの読み込みに失敗しました: {str(e)}")

if __name__ == "__main__":
    main()
