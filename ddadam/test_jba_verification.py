#!/usr/bin/env python3
"""
JBA照合システムのテストスクリプト
"""
import sys
sys.path.append('backend')

from worker.jba_verification_lib import JBAVerificationSystem
import logging

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_verification():
    """JBA照合をテスト"""
    print("=" * 60)
    print("JBA照合システムテスト")
    print("=" * 60)
    
    # システム初期化
    jba = JBAVerificationSystem()
    
    # テスト1: ログイン前の照合（エラーになるはず）
    print("\n[テスト1] ログイン前の照合")
    result = jba.verify_player_info(
        player_name="山田太郎",
        birth_date=None,
        university="東京大学",
        get_details=False,
        threshold=1.0
    )
    print(f"結果: {result}")
    assert result["status"] == "error", "ログイン前はエラーになるべき"
    print("✅ テスト1 成功")
    
    # テスト2: ログイン
    print("\n[テスト2] JBAログイン")
    print("JBA認証情報を入力してください:")
    email = input("Email: ")
    password = input("Password: ")
    
    login_success = jba.login(email, password)
    print(f"ログイン結果: {'成功' if login_success else '失敗'}")
    assert login_success, "ログインに失敗しました"
    print("✅ テスト2 成功")
    
    # テスト3: 実際の照合
    print("\n[テスト3] 選手照合")
    result = jba.verify_player_info(
        player_name="山村颯奈",  # テスト用の選手名
        birth_date=None,
        university="日本ウェルネススポーツ大学",
        get_details=True,
        threshold=1.0,
        player_no="1"
    )
    print(f"\n照合結果:")
    print(f"  status: {result.get('status')}")
    print(f"  message: {result.get('message', 'N/A')}")
    if result.get('jba_data'):
        print(f"  選手名: {result['jba_data'].get('name')}")
        print(f"  類似度: {result.get('similarity', 'N/A')}")
    print("✅ テスト3 完了")
    
    print("\n" + "=" * 60)
    print("すべてのテスト完了！")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_verification()
    except KeyboardInterrupt:
        print("\n\nテスト中断")
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()

