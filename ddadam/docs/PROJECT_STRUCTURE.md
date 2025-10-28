# 📁 プロジェクト構造

JBA照合・PDF生成システムのディレクトリ構造とファイル説明

---

## 🌳 ディレクトリツリー

```
ddadam/
├── frontend/                   # Next.js フロントエンド (Vercel)
│   ├── pages/                 # ページコンポーネント
│   │   ├── index.tsx         # トップページ（大学名入力モード）
│   │   ├── tournament.tsx    # 大会IDモード
│   │   ├── csv.tsx           # CSVアップロードモード
│   │   ├── result.tsx        # 進捗・結果表示
│   │   └── _app.tsx          # アプリケーションルート
│   ├── styles/               # CSS
│   │   └── globals.css       # グローバルスタイル
│   ├── components/           # 共有コンポーネント（将来用）
│   ├── package.json          # 依存関係
│   ├── tsconfig.json         # TypeScript設定
│   ├── next.config.js        # Next.js設定
│   ├── tailwind.config.js    # Tailwind CSS設定
│   ├── vercel.json           # Vercel設定
│   └── env.local.example     # 環境変数テンプレート
│
├── backend/                   # FastAPI バックエンド (Railway)
│   ├── main.py               # アプリケーションエントリーポイント
│   ├── config.py             # 環境設定（Pydantic Settings）
│   ├── routers/              # API エンドポイント
│   │   ├── __init__.py
│   │   ├── tournament.py    # 大会ID処理
│   │   ├── csv_upload.py    # CSVアップロード
│   │   ├── pdf.py           # PDF生成
│   │   ├── verify.py        # JBA照合
│   │   ├── jobs.py          # ジョブステータス
│   │   └── cache.py         # キャッシュ管理
│   ├── worker/               # バックグラウンドワーカー
│   │   ├── integrated_system.py          # 統合システム
│   │   ├── jba_verification_lib.py       # JBA照合ライブラリ
│   │   ├── integrated_system_worker.py   # PDF生成ワーカー
│   │   └── worker_runner.py              # Workerランナー
│   ├── cache_adapter.py      # キャッシュアダプター（Redis/File）
│   ├── supabase_helper.py    # Supabase クライアント
│   ├── supabase_init.sql     # DB初期化スクリプト
│   ├── requirements.txt      # Python依存関係
│   ├── Dockerfile            # Dockerイメージ
│   └── env.example           # 環境変数テンプレート
│
├── docs/                      # ドキュメント
│   ├── INDEX.md              # ドキュメント一覧
│   ├── DEPLOY_RAILWAY.md     # Railway デプロイガイド
│   ├── RAILWAY_QUICKSTART.md # 15分クイックスタート
│   ├── VERCEL_SETUP.md       # Vercel セットアップ
│   ├── DEPLOYMENT_TROUBLESHOOTING.md  # トラブルシューティング
│   ├── ENV_SETUP.md          # 環境変数ガイド
│   ├── CSV_FEATURE.md        # CSV機能ガイド
│   ├── MIGRATION_STATUS.md   # 移行ステータス
│   └── PROJECT_STRUCTURE.md  # このファイル
│
├── outputs/                   # 生成されたPDF/Excelファイル（Git除外）
├── temp_results/              # ジョブメタデータ（Git除外）
│
├── README.md                  # プロジェクト概要
├── QUICKSTART.md              # 15分クイックスタート
├── .gitignore                # Git除外設定
├── setup.bat                  # 初期セットアップスクリプト（Windows）
└── start-dev.bat              # 開発サーバー起動スクリプト（Windows）
```

---

## 📄 主要ファイル説明

### Frontend（Next.js）

#### ページ

| ファイル | 説明 |
|---------|------|
| `pages/index.tsx` | 大学名入力モード（トップページ） |
| `pages/tournament.tsx` | 大会IDモード（CSV自動取得） |
| `pages/csv.tsx` | CSVアップロードモード |
| `pages/result.tsx` | 進捗表示・結果ダウンロード |
| `pages/_app.tsx` | アプリケーションルート |

#### 設定

| ファイル | 説明 |
|---------|------|
| `package.json` | Node.js依存関係 |
| `tsconfig.json` | TypeScript設定 |
| `next.config.js` | Next.js設定 |
| `tailwind.config.js` | Tailwind CSS設定 |
| `vercel.json` | Vercel デプロイ設定 |

### Backend（FastAPI）

#### API エンドポイント

| ファイル | エンドポイント | 説明 |
|---------|-------------|------|
| `routers/tournament.py` | `/tournament` | 大会ID処理 |
| `routers/csv_upload.py` | `/csv/upload` | CSVアップロード |
| `routers/pdf.py` | `/pdf` | PDF生成 |
| `routers/verify.py` | `/verify` | JBA照合 |
| `routers/jobs.py` | `/jobs/{job_id}` | ジョブステータス |
| `routers/cache.py` | `/cache` | キャッシュ統計 |

#### ワーカー

| ファイル | 説明 |
|---------|------|
| `worker/integrated_system.py` | 統合システム（大会処理） |
| `worker/jba_verification_lib.py` | JBA照合・CSV処理 |
| `worker/integrated_system_worker.py` | PDF生成ワーカー |
| `worker/worker_runner.py` | Railway Worker用ランナー |

#### コア

| ファイル | 説明 |
|---------|------|
| `main.py` | FastAPI アプリケーション |
| `config.py` | 環境設定（Pydantic） |
| `cache_adapter.py` | キャッシュアダプター |
| `supabase_helper.py` | Supabase クライアント |

### ドキュメント

| ファイル | 説明 |
|---------|------|
| `docs/INDEX.md` | 全ドキュメント一覧 |
| `docs/DEPLOY_RAILWAY.md` | 詳細デプロイ手順 |
| `docs/RAILWAY_QUICKSTART.md` | 15分デプロイガイド |
| `docs/VERCEL_SETUP.md` | Vercel設定 |
| `docs/DEPLOYMENT_TROUBLESHOOTING.md` | エラー対処法 |
| `docs/CSV_FEATURE.md` | CSV機能の使い方 |

### ルート

| ファイル | 説明 |
|---------|------|
| `README.md` | プロジェクト概要 |
| `QUICKSTART.md` | 15分起動ガイド |
| `.gitignore` | Git除外設定 |

---

## 🔀 データフロー

### 1. 大会IDモード

```
User
  ↓ 大会ID + ログイン情報
Frontend (tournament.tsx)
  ↓ POST /tournament
Backend (tournament.py)
  ↓ バックグラウンドジョブ
Worker (integrated_system.py)
  ↓ JBAログイン + CSV取得
JBA Website
  ↓ CSV データ
Worker (jba_verification_lib.py)
  ↓ JBA照合
Worker (integrated_system_worker.py)
  ↓ PDF/Excel生成
Supabase Storage
  ↓ ダウンロードURL
User
```

### 2. CSVアップロードモード

```
User
  ↓ CSVファイル
Frontend (csv.tsx)
  ↓ POST /csv/upload
Backend (csv_upload.py)
  ↓ バックグラウンドジョブ
Worker (jba_verification_lib.py)
  ↓ JBA照合
Worker (create_colored_excel)
  ↓ Excelファイル
outputs/
  ↓ ダウンロード
User
```

### 3. 進捗確認

```
Frontend (result.tsx)
  ↓ 2秒ごとにポーリング
Backend (jobs.py)
  ↓ GET /jobs/{job_id}
temp_results/job_{id}.json
  ↓ ジョブメタデータ
Frontend
  ↓ プログレスバー更新
User
```

---

## 🗄️ データ保存

### ローカル開発

```
outputs/              # 生成されたファイル
temp_results/         # ジョブメタデータ
worker/jba_player_cache.json  # 永続キャッシュ
```

### 本番環境

```
Supabase Storage     # PDF/Excelファイル
Supabase Postgres    # jobsテーブル
Upstash Redis        # キャッシュデータ
```

---

## 🔧 設定ファイル

### 環境変数

**Backend（`backend/.env`）:**
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxx...
OUTPUT_BUCKET=outputs
REDIS_URL=redis://default:xxxxx@...
CACHE_TYPE=redis
```

**Frontend（`frontend/.env.local`）:**
```bash
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
```

---

## 📦 依存関係

### Backend（Python）

主要パッケージ:
- FastAPI
- uvicorn
- pandas
- beautifulsoup4
- requests
- reportlab
- openpyxl
- supabase
- redis

### Frontend（Node.js）

主要パッケージ:
- next
- react
- typescript
- tailwindcss

---

**[← ドキュメント一覧に戻る](INDEX.md)**

