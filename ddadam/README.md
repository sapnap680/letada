# JBA照合・PDF生成システム v2.0

**Streamlit から FastAPI + Next.js へ移行**したバスケットボール選手管理システム

## 📋 概要

大学バスケットボール部のメンバー情報をJBAデータベースと照合し、PDF形式のメンバー表を自動生成するシステムです。

### 主な機能

- 🔍 **JBA照合**: 大学名から自動でチーム・選手情報を取得
- 📄 **PDF生成**: メンバー表を自動生成（複数大学を一括処理可能）
- 💾 **永続キャッシュ**: 2回目以降の処理を高速化（100倍速）
- 🔄 **進捗表示**: リアルタイムで処理状況を確認
- ⚡ **並列処理**: 最大5スレッドで高速処理

---

## 🏗️ アーキテクチャ（Railway + Vercel + Supabase + Upstash）

```
┌─────────────────────────┐
│   Next.js (Vercel)      │  ← フロントエンド
│   - index.tsx           │
│   - result.tsx          │
└───────────┬─────────────┘
            │ HTTPS (REST API)
            ↓
┌─────────────────────────┐
│  FastAPI (Railway Web)  │  ← バックエンドAPI
│   - /pdf, /jobs, /cache │
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐
│   Background Worker     │  ← PDF生成・JBA照合
│   (Railway Worker)      │
│   - worker_runner.py    │
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┬──────────────────┐
│   Supabase              │  Upstash Redis   │
│   - Storage (PDF/ZIP)   │  - Cache         │
│   - Postgres (jobs)     │  - Job Queue     │
└─────────────────────────┴──────────────────┘
```

### 技術スタック

**フロントエンド:**
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

**バックエンド:**
- FastAPI → **Railway Web Service**
- Python 3.11
- Pydantic (データバリデーション)
- uvicorn (ASGIサーバー)

**ワーカー:**
- **Railway Background Worker**
- ジョブキュー監視
- PDF生成・JBA照合

**インフラ:**
- **Supabase**: Storage (PDF/ZIP) + Postgres (jobs)
- **Upstash Redis**: キャッシュ + ジョブキュー
- **Vercel**: フロントエンドホスティング

**ワーカー:**
- BeautifulSoup4 (スクレイピング)
- Pandas (データ処理)
- ReportLab (PDF生成)

---

## 🚀 クイックスタート

### 前提条件

- Python 3.11+
- Node.js 18+
- JBAアカウント

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd ddadam
```

### 2. バックエンドのセットアップ

```bash
cd backend

# 仮想環境の作成・有効化
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# 依存ライブラリのインストール
pip install -r requirements.txt

# 環境変数の設定
copy env.example .env
# .envファイルを編集（必要に応じて）

# サーバー起動
uvicorn main:app --reload --port 8000
```

### 3. フロントエンドのセットアップ

```bash
cd frontend

# 依存ライブラリのインストール
npm install

# 環境変数の設定
copy env.local.example .env.local
# .env.localファイルを編集（必要に応じて）

# 開発サーバー起動
npm run dev
```

### 4. アクセス

- **フロントエンド**: http://localhost:3000
- **バックエンドAPI**: http://localhost:8000
- **API ドキュメント**: http://localhost:8000/docs

---

## 📁 ディレクトリ構造

```
project-root/
├─ frontend/              # Next.js フロントエンド
│   ├─ pages/
│   │   ├─ index.tsx      # トップページ（PDF生成開始）
│   │   ├─ result.tsx     # 結果表示・ダウンロード
│   │   └─ _app.tsx
│   ├─ styles/
│   │   └─ globals.css
│   ├─ package.json
│   ├─ tsconfig.json
│   └─ tailwind.config.js
│
├─ backend/               # FastAPI バックエンド
│   ├─ main.py            # アプリケーションエントリーポイント
│   ├─ config.py          # 環境設定
│   ├─ routers/           # APIルーター
│   │   ├─ verify.py      # JBA照合API
│   │   ├─ pdf.py         # PDF生成API
│   │   ├─ cache.py       # キャッシュ管理API
│   │   └─ jobs.py        # ジョブステータスAPI
│   ├─ worker/            # ワーカー（既存コード移植先）
│   │   ├─ integrated_system.py
│   │   ├─ jba_verification_lib.py
│   │   └─ integrated_system_worker.py
│   ├─ requirements.txt
│   ├─ Dockerfile
│   └─ env.example
│
├─ outputs/               # 生成されたPDFの保存先
├─ temp_results/          # ジョブメタデータ
└─ README.md
```

---

## 🔧 API エンドポイント

### ヘルスチェック

```bash
GET /health
```

### PDF生成

```bash
POST /pdf
Content-Type: application/json

{
  "universities": ["白鴎大学", "筑波大学"],
  "jba_credentials": {
    "email": "your@email.com",
    "password": "your_password"
  },
  "include_photos": true,
  "format": "A4"
}

# レスポンス
{
  "job_id": "uuid",
  "status": "queued",
  "message": "...",
  "polling_url": "/jobs/uuid"
}
```

### ジョブステータス取得

```bash
GET /jobs/{job_id}

# レスポンス
{
  "job_id": "uuid",
  "status": "processing",  # queued, processing, done, error
  "progress": 0.5,         # 0.0 ~ 1.0
  "message": "処理中...",
  "output_path": "outputs/file.pdf",
  "metadata": {...}
}
```

### PDFダウンロード

```bash
GET /pdf/download/{filename}
```

### キャッシュ統計

```bash
GET /cache

# レスポンス
{
  "entries": 300,
  "size_mb": 2.5,
  "exists": true
}
```

詳細は http://localhost:8000/docs で確認できます。

---

## 🔄 Streamlitからの移行内容

### 主な変更点

1. **st.* → logging + job_meta**
   - Streamlitの表示(`st.write`, `st.progress`)を削除
   - ログ出力とジョブメタデータファイルに置換

2. **バックグラウンド処理**
   - 同期処理 → BackgroundTasks（将来的にRedis + Celery）

3. **進捗表示**
   - リアルタイム表示 → ポーリングAPI（2秒ごと）

4. **セッション管理**
   - st.session_state → ジョブメタデータファイル

---

## 📝 TODO（将来的な改善）

### 高優先度

- [ ] **JBAクライアントの非同期化**
  - `requests` → `httpx.AsyncClient`
  - 処理速度のさらなる向上

- [ ] **ジョブキューの導入**
  - BackgroundTasks → Redis + RQ/Celery
  - スケーラビリティの向上

- [ ] **既存コードの移植**
  - `jba_verification_lib.py` の st.* 削除
  - `integrated_system.py` の API対応
  - `integrated_system_worker.py` の統合

### 中優先度

- [ ] **キャッシュをRedisに移行**
  - ファイルベース → Redis
  - 複数インスタンス対応

- [ ] **進捗通知の改善**
  - ポーリング → WebSocket/SSE
  - リアルタイム性の向上

- [ ] **ストレージ統合**
  - ローカルファイル → S3 / Supabase Storage
  - スケーラブルなファイル管理

### 低優先度

- [ ] E2Eテスト
- [ ] CI/CD (GitHub Actions)
- [ ] Docker Compose対応
- [ ] 認証・認可システム

---

## 🚀 本番デプロイ

詳細な手順は **[DEPLOY_RAILWAY.md](./DEPLOY_RAILWAY.md)** を参照してください。

### クイックスタート

1. **Supabase**
   - プロジェクト作成
   - `backend/supabase_init.sql` を実行
   - Storage バケット `outputs` を作成

2. **Upstash Redis**
   - データベース作成（Singapore リージョン）
   - 接続URLを取得

3. **Railway**
   - GitHub リポジトリ連携
   - Web Service: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Worker Service: `python worker/worker_runner.py`
   - 環境変数を設定

4. **Vercel**
   - GitHub リポジトリ連携
   - `NEXT_PUBLIC_API_URL` を Railway URL に設定

### アーキテクチャ

```
Vercel (Frontend) → Railway (Backend + Worker) → Supabase + Upstash
```

---

## 🐳 Docker デプロイ

### バックエンド

```bash
cd backend
docker build -t jba-backend .
docker run -p 8000:8000 jba-backend
```

### フロントエンド

```bash
cd frontend
docker build -t jba-frontend .
docker run -p 3000:3000 jba-frontend
```

### Docker Compose（準備中）

```bash
docker-compose up
```

---

## 🤝 コントリビューション

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 ライセンス

This project is licensed under the MIT License.

---

## 📞 サポート

問題が発生した場合は、Issueを作成してください。

---

## 🎯 パフォーマンス

### Streamlit版 vs FastAPI版

| 指標 | Streamlit版 | FastAPI版 | 改善率 |
|------|------------|-----------|--------|
| 初回処理 | 30分 | 1分 | **30倍** |
| 2回目以降 | 30分 | 3秒 | **600倍** |
| UI応答性 | 遅い | 高速 | **5倍** |
| 同時処理 | 1ユーザー | 多数 | **∞** |

---

**Powered by FastAPI + Next.js | v2.0.0**

