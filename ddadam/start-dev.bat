@echo off
REM 開発サーバー起動スクリプト (Windows)

echo ========================================
echo  JBA照合・PDF生成システム v2.0
echo  開発サーバー起動
echo ========================================
echo.

REM バックエンドの起動
echo [1/2] バックエンドを起動中...
cd backend
start "Backend - FastAPI" cmd /k "call .venv\Scripts\activate && uvicorn main:app --reload --port 8000"
cd ..

REM 少し待機
timeout /t 3 /nobreak >nul

REM フロントエンドの起動
echo [2/2] フロントエンドを起動中...
cd frontend
start "Frontend - Next.js" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo  起動完了！
echo ========================================
echo.
echo  フロントエンド: http://localhost:3000
echo  バックエンドAPI: http://localhost:8000
echo  API ドキュメント: http://localhost:8000/docs
echo.
echo  終了するには各ウィンドウで Ctrl+C を押してください
echo ========================================

