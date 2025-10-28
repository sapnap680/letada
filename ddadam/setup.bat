@echo off
REM セットアップスクリプト (Windows)

echo ========================================
echo  JBA照合・PDF生成システム v2.0
echo  初期セットアップ
echo ========================================
echo.

REM バックエンドのセットアップ
echo [1/3] バックエンドのセットアップ...
cd backend

echo  - 仮想環境を作成中...
python -m venv .venv

echo  - 仮想環境を有効化中...
call .venv\Scripts\activate

echo  - 依存ライブラリをインストール中...
pip install -r requirements.txt

echo  - 環境変数ファイルを作成中...
if not exist .env (
    copy env.example .env
    echo    .env ファイルを作成しました（必要に応じて編集してください）
) else (
    echo    .env ファイルは既に存在します
)

cd ..

REM フロントエンドのセットアップ
echo.
echo [2/3] フロントエンドのセットアップ...
cd frontend

echo  - 依存ライブラリをインストール中...
call npm install

echo  - 環境変数ファイルを作成中...
if not exist .env.local (
    copy env.local.example .env.local
    echo    .env.local ファイルを作成しました（必要に応じて編集してください）
) else (
    echo    .env.local ファイルは既に存在します
)

cd ..

REM 必要なディレクトリの作成
echo.
echo [3/3] 必要なディレクトリを作成中...
if not exist outputs mkdir outputs
if not exist temp_results mkdir temp_results

echo.
echo ========================================
echo  セットアップ完了！
echo ========================================
echo.
echo  次のステップ:
echo  1. backend\.env を編集（JBA認証情報など）
echo  2. frontend\.env.local を確認
echo  3. start-dev.bat を実行して開発サーバーを起動
echo.
echo  開発サーバー起動:
echo    start-dev.bat
echo.
echo ========================================

pause

