#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ダミーデータでPDF生成をテストするスクリプト
"""
import os
import sys

# 現在のディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worker.integrated_system import IntegratedTournamentSystem
from worker.jba_verification_lib import JBAVerificationSystem, DataValidator

def create_dummy_reports():
    """ダミーレポートデータを作成"""
    reports = {}
    
    # 大学1: 長い選手名・カナ名を含むテストデータ
    univ1_name = "開智国際大学"
    reports[univ1_name] = {
        "results": [
            {
                "original_data": {
                    "No": "1",
                    "選手名": "山本太郎",
                    "カナ名": "ヤマモトタロウ",
                    "学部": "経営",
                    "学年": "3",
                    "身長": "180.5",
                    "体重": "75.2",
                    "ポジション": "PG",
                    "出身校": "開智高校"
                },
                "status": "match",
                "correction": {
                    "No": "1",
                    "選手名": "山本太郎",
                    "カナ名": "ヤマモトタロウ",
                    "学部": "経営",
                    "学年": "3",
                    "身長": "180.8cm",
                    "体重": "75.5kg",
                    "ポジション": "PG",
                    "出身校": "開智高校"
                },
                "message": "JBAデータベースと完全一致"
            },
            {
                "original_data": {
                    "No": "2",
                    "選手名": "とても長い選手名のテストデータです",
                    "カナ名": "ヤナギモトヨシロウマサヤス",
                    "学部": "商",
                    "学年": "2",
                    "身長": "185.3",
                    "体重": "80.7",
                    "ポジション": "SG",
                    "出身校": "横浜商業高校"
                },
                "status": "partial_match",
                "correction": {
                    "No": "2",
                    "選手名": "とても長い選手名のテストデータです",
                    "カナ名": "ヤナギモトヨシロウマサヤス",
                    "学部": "商",
                    "学年": "2",
                    "身長": "185.5cm",
                    "体重": "80.9kg",
                    "ポジション": "SG",
                    "出身校": "横浜商業高校"
                },
                "message": "部分一致: 類似度 0.85"
            },
            {
                "original_data": {
                    "No": "1234567890",
                    "選手名": "田中花子",
                    "カナ名": "タナカハナコ",
                    "学部": "文",
                    "学年": "1",
                    "身長": "170",
                    "体重": "65",
                    "ポジション": "PF",
                    "出身校": "東京高校"
                },
                "status": "not_found",
                "correction": None,
                "message": "JBAデータベースに登録されていません"
            },
            {
                "original_data": {
                    "No": "4",
                    "選手名": "短い名前",
                    "カナ名": "ミジカイナ",
                    "学部": "理",
                    "学年": "4",
                    "身長": "175",
                    "体重": "70",
                    "ポジション": "C",
                    "出身校": "理科大附属"
                },
                "status": "match",
                "correction": {
                    "No": "4",
                    "選手名": "短い名前",
                    "カナ名": "ミジカイナ",
                    "学部": "理",
                    "学年": "4",
                    "身長": "175cm",
                    "体重": "70kg",
                    "ポジション": "C",
                    "出身校": "理科大附属"
                },
                "message": "JBAデータベースと完全一致"
            },
            {
                "original_data": {
                    "No": "999",
                    "選手名": "最大30文字まで表示されるテス",
                    "カナ名": "サンゼンサンテンモジマデヒョウジサレルテスト",
                    "学部": "工",
                    "学年": "3",
                    "身長": "190",
                    "体重": "90",
                    "ポジション": "C",
                    "出身校": "工業高校"
                },
                "status": "match",
                "correction": {
                    "No": "999",
                    "選手名": "最大30文字まで表示されるテス",
                    "カナ名": "サンゼンサンテンモジマデヒョウジサレルテスト",
                    "学部": "工",
                    "学年": "3",
                    "身長": "190cm",
                    "体重": "90kg",
                    "ポジション": "C",
                    "出身校": "工業高校"
                },
                "message": "JBAデータベースと完全一致"
            }
        ]
    }
    
    # 大学2: 通常のテストデータ
    univ2_name = "横浜商業大学"
    reports[univ2_name] = {
        "results": [
            {
                "original_data": {
                    "No": "1",
                    "選手名": "佐藤次郎",
                    "カナ名": "サトウジロウ",
                    "学部": "商",
                    "学年": "2",
                    "身長": "175",
                    "体重": "70",
                    "ポジション": "PG",
                    "出身校": "横浜商業高校"
                },
                "status": "match",
                "correction": {
                    "No": "1",
                    "選手名": "佐藤次郎",
                    "カナ名": "サトウジロウ",
                    "学部": "商",
                    "学年": "2",
                    "身長": "175cm",
                    "体重": "70kg",
                    "ポジション": "PG",
                    "出身校": "横浜商業高校"
                },
                "message": "JBAデータベースと完全一致"
            },
            {
                "original_data": {
                    "No": "2",
                    "選手名": "鈴木三郎",
                    "カナ名": "スズキサブロウ",
                    "学部": "経",
                    "学年": "3",
                    "身長": "180",
                    "体重": "75",
                    "ポジション": "SG",
                    "出身校": "鈴木高校"
                },
                "status": "partial_match",
                "correction": {
                    "No": "2",
                    "選手名": "鈴木三郎",
                    "カナ名": "スズキサブロウ",
                    "学部": "経",
                    "学年": "3",
                    "身長": "180cm",
                    "体重": "75kg",
                    "ポジション": "SG",
                    "出身校": "鈴木高校"
                },
                "message": "部分一致: 類似度 0.90"
            }
        ]
    }
    
    return reports

def main():
    """メイン関数"""
    print("=" * 60)
    print("PDF生成テスト（ダミーデータ）")
    print("=" * 60)
    
    # JBAシステムとバリデーターの初期化（ダミーなので実際には使わない）
    jba_system = JBAVerificationSystem()
    validator = DataValidator()
    
    # 統合システムの初期化
    system = IntegratedTournamentSystem(
        jba_system=jba_system,
        validator=validator,
        use_parallel=False,
        max_workers=1
    )
    
    # ダミーレポートデータを作成
    print("\n📊 ダミーレポートデータを作成中...")
    reports = create_dummy_reports()
    print(f"✅ {len(reports)} 大学のレポートデータを作成しました")
    
    # 出力ディレクトリを作成
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    # PDF出力パス
    output_path = os.path.join(output_dir, "test_dummy_report.pdf")
    
    # PDF生成
    print(f"\n📝 PDF生成を開始します...")
    print(f"   出力先: {output_path}")
    print(f"   使用フォント: {getattr(system, 'default_font', 'Unknown')}")
    
    try:
        system.export_all_university_reports_as_pdf(reports, output_path=output_path)
        print(f"\n✅ PDF生成が完了しました！")
        print(f"   ファイル: {output_path}")
        print(f"\n📋 テスト内容:")
        print(f"   - No.列: 10文字まで表示（例: 1234567890）")
        print(f"   - 選手名列: 30文字まで表示")
        print(f"   - カナ名列: 30文字まで表示")
        print(f"   - 完全一致/部分一致/未発見の表示")
        print(f"   - 訂正箇所の赤字表示")
        
    except Exception as e:
        print(f"\n❌ PDF生成エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

