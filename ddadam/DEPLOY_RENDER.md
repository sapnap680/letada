# 🚀 Render + Vercel デプロイ手順書

このドキュメントは **Vercel (Frontend) + Render (Backend + Worker) + Supabase + Upstash** 構成でのデプロイ手順を説明します。

---

## 🎯 構成概要

| コンポーネント | サービス | 役割 | 無料枠 |
|------------|---------|------|--------|
| Frontend | **Vercel** | Next.js ホスティング | 100GB/月 |
| Backend API | **Render (Web Service)** | FastAPI | 750時間/月 |
| PDF生成 | **Render (Background Worker)** | 非同期処理 | 750時間/月 |
| ストレージ | **Supabase Storage** | PDF/ZIP保存 | 1GB |
| DB | **Supabase Postgres** | jobs テーブル | 500MB |
| キャッシュ | **Upstash Redis** | 永続キャッシュ | 10,000コマンド/日 |

**合計コスト: $0/月（無料枠内）** ✅

---

## 📋 前提条件

- [x] GitHub アカウント
- [x] Render アカウント（[render.com](https://render.com)）
- [x] Vercel アカウント（[vercel.com](https://vercel.com)）
- [x] Supabase アカウント（[supabase.com](https://supabase.com)）
- [x] Upstash アカウント（[upstash.com](https://upstash.com)）

---

## 🔧 Step 1: GitHub リポジトリ準備

### 1.1 リポジトリ作成

```bash
# ローカルでコミット
git init
git add .
git commit -m "Initial commit"

# GitHub に push
git remote add origin https://github.com/YOUR_USERNAME/jba-system.git
git branch -M main
git push -u origin main
```

---

## 💾 Step 2: Supabase セットアップ

### 2.1 プロジェクト作成

1. [Supabase Dashboard](https://app.supabase.com/) にアクセス
2. "New Project" をクリック
3. 設定:
   - Name: `jba-system`
   - Database Password: （強力なパスワードを設定）
   - Region: **Singapore**（東京に最も近い）
4. "Create new project" をクリック
5. プロジェクト作成完了まで待機（2-3分）

### 2.2 データベース初期化

1. Dashboard > **SQL Editor** を開く
2. `backend/supabase_init.sql` の内容をコピー
3. SQL Editor に貼り付けて **RUN** をクリック

```sql
-- 確認: jobs テーブルが作成されたか
SELECT * FROM jobs LIMIT 5;
```

### 2.3 Storage バケット作成

1. Dashboard > **Storage** を開く
2. "Create a new bucket" をクリック
3. 設定:
   - Name: `outputs`
   - Public bucket: ✅ **ON**
4. "Create bucket" をクリック

### 2.4 認証情報を取得

1. Dashboard > **Settings** > **API** を開く
2. 以下をメモ：
   - **Project URL**: `https://xxxxx.supabase.co`
   - **Project API keys**:
     - `anon` `public`: `eyJxxx...` (公開用)
     - `service_role` `secret`: `eyJxxx...` (**機密情報・サーバー用**)

---

## 💾 Step 3: Upstash Redis セットアップ

### 3.1 データベース作成

1. [Upstash Console](https://console.upstash.com/) にアクセス
2. "Create Database" をクリック
3. 設定:
   - Name: `jba-cache`
   - Type: **Regional**
   - Region: **ap-southeast-1**（Singapore）
4. "Create" をクリック

### 3.2 接続情報を取得

1. 作成したデータベースを開く
2. **Redis Connect** タブを選択
3. **UPSTASH_REDIS_REST_URL** をコピー:
   ```
   redis://default:xxxxx@xxxxx.upstash.io:6379
   ```

---

## 🛠️ Step 4: Render セットアップ（Backend + Worker）

### 4.1 Render アカウント作成

1. [Render Dashboard](https://dashboard.render.com/) にアクセス
2. GitHub アカウントで連携

### 4.2 Blueprint からデプロイ（推奨）

1. Dashboard > **Blueprints** を開く
2. "New Blueprint Instance" をクリック
3. GitHub リポジトリを選択
4. **render.yaml** が自動検出される
5. 環境変数を設定（次のステップ）

#### 環境変数設定

以下の環境変数を **両方のサービス（Web + Worker）** に設定：

| 変数名 | 値 | 説明 |
|-------|---|------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` | Supabase プロジェクトURL |
| `SUPABASE_KEY` | `eyJxxx...` | Service role key（機密） |
| `OUTPUT_BUCKET` | `outputs` | Storage バケット名 |
| `REDIS_URL` | `redis://default:xxxxx@...` | Upstash Redis URL |

6. "Apply" をクリックしてデプロイ開始

### 4.3 手動デプロイ（代替方法）

Blueprint が使えない場合は手動で作成：

#### Web Service

1. Dashboard > "New" > "Web Service" をクリック
2. GitHub リポジトリを選択
3. 設定:
   - Name: `jba-backend`
   - Region: **Singapore**
   - Branch: `main`
   - Root Directory: `backend`
   - Runtime: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Plan: **Free**
4. 環境変数を上記の表に従って設定
5. "Create Web Service" をクリック

#### Background Worker

1. Dashboard > "New" > "Background Worker" をクリック
2. 同じリポジトリを選択
3. 設定:
   - Name: `jba-worker`
   - Region: **Singapore**
   - Branch: `main`
   - Root Directory: `backend`
   - Runtime: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python worker/worker_runner.py`
   - Plan: **Free**
4. 環境変数を同じように設定
5. "Create Background Worker" をクリック

### 4.4 デプロイ確認

デプロイ完了後（5-10分）：

```bash
# ヘルスチェック
curl https://jba-backend.onrender.com/health

# API ドキュメント
open https://jba-backend.onrender.com/docs
```

⚠️ **注意**: 無料プランは15分非アクティブでスリープします。初回アクセスは起動に30秒ほどかかります。

---

## 🌐 Step 5: Vercel セットアップ（Frontend）

### 5.1 プロジェクト作成

1. [Vercel Dashboard](https://vercel.com/dashboard) にアクセス
2. "New Project" をクリック
3. GitHub リポジトリを選択
4. 設定:
   - Framework Preset: **Next.js**
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

### 5.2 環境変数を設定

**環境変数を追加（デプロイ前）:**

| Name | Value | Environment |
|------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://jba-backend.onrender.com` | Production, Preview, Development |

### 5.3 デプロイ

1. "Deploy" をクリック
2. デプロイ完了まで待機（2-3分）
3. デプロイされたURLを確認:
   ```
   https://jba-system.vercel.app
   ```

---

## ✅ Step 6: 動作確認

### 6.1 Backend 確認

```bash
# ヘルスチェック
curl https://jba-backend.onrender.com/health

# レスポンス例:
# {"status":"healthy","cache_exists":true,"output_dir":true,"temp_dir":true}

# ジョブ一覧
curl https://jba-backend.onrender.com/jobs/

# キャッシュ統計
curl https://jba-backend.onrender.com/cache
```

### 6.2 Frontend 確認

1. `https://jba-system.vercel.app` にアクセス
2. 大学名を入力（例: 白鴎大学, 筑波大学）
3. JBA認証情報を入力
4. "PDF生成を開始" をクリック
5. 進捗画面に遷移 → リアルタイム進捗を確認
6. 完了後、PDFをダウンロード

### 6.3 Worker 確認

1. Render Dashboard > `jba-worker` > **Logs** を開く
2. ログに以下が表示されることを確認:
   ```
   Worker started
   Found X pending job(s)
   Processing job xxxx-xxxx-xxxx...
   Job completed successfully
   ```

### 6.4 Supabase 確認

1. Dashboard > **Table Editor** > `jobs` を開く
2. ジョブレコードが作成されているか確認
3. Dashboard > **Storage** > `outputs` を開く
4. PDF/ZIPファイルがアップロードされているか確認

---

## 🔄 Step 7: CI/CD セットアップ（オプション）

### 7.1 GitHub Actions

既存の `.github/workflows/` を使用：

- `backend-deploy.yml` → Render（render.yaml で自動デプロイ）
- `frontend-deploy.yml` → Vercel（Git 連携で自動デプロイ）

**推奨**: render.yaml + Vercel Git 連携で自動デプロイされるため、手動設定は不要です。

---

## 📊 Step 8: 監視とログ

### 8.1 Render ログ

```bash
# Web Service
# Dashboard > jba-backend > Logs

# Worker
# Dashboard > jba-worker > Logs
```

### 8.2 Vercel ログ

1. Dashboard > Project > **Logs** タブ
2. リアルタイムログを確認

### 8.3 Supabase 監視

1. Dashboard > **Database** > **Query Performance**
2. Dashboard > **Storage** > **Usage**

---

## 🐛 トラブルシューティング

### Backend がスリープしている

**原因**: 無料プランは15分非アクティブでスリープ

**対策**:
```bash
# 定期的にアクセス（GitHub Actions で5分ごと）
# .github/workflows/keep-alive.yml
# または Render Cron Jobs を使用
```

### Worker がジョブを処理しない

**確認事項**:
1. Render Dashboard > Worker > Logs を確認
2. 環境変数が正しく設定されているか
3. Supabase jobs テーブルに `status='queued'` のレコードがあるか

```sql
-- Supabase SQL Editor で確認
SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at DESC LIMIT 10;
```

### Supabase 接続エラー

```bash
# 環境変数を確認
# Render Dashboard > Service > Environment > Environment Variables

# SUPABASE_URL と SUPABASE_KEY が正しいか確認
```

### Redis 接続エラー

```bash
# Upstash Console で接続情報を確認
# REDIS_URL が正しいか確認

# テスト接続
curl -X POST https://your-redis.upstash.io/PING \
  -H "Authorization: Bearer your_token"
```

---

## 💰 コスト管理

### 無料枠の制限

| サービス | 制限 | 超過時の挙動 |
|---------|------|-----------|
| Render Web | 750時間/月 | **停止** |
| Render Worker | 750時間/月 | **停止** |
| Supabase Storage | 1GB | **追加料金** |
| Supabase DB | 500MB | **追加料金** |
| Upstash Redis | 10,000コマンド/日 | **追加料金** |
| Vercel | 100GB帯域/月 | **追加料金** |

### 監視

1. Render Dashboard > **Usage** で時間を確認
2. Supabase Dashboard > **Settings** > **Usage** で容量を確認
3. Upstash Console > **Database** > **Metrics** でコマンド数を確認

---

## 🔐 セキュリティチェックリスト

- [x] Supabase Service Role Key は環境変数で管理
- [x] Render 環境変数は暗号化
- [x] CORS 設定を本番環境に合わせて制限
- [x] Supabase Storage のポリシー設定
- [x] Rate Limiting の実装
- [x] HTTPS 強制（Render/Vercel で自動）

---

## 📚 参考リンク

- [Render Documentation](https://render.com/docs)
- [Vercel Documentation](https://vercel.com/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Upstash Redis Documentation](https://docs.upstash.com/redis)

---

## 🎯 次のステップ

1. ✅ **カスタムドメイン設定**（オプション）
   - Render: Dashboard > Service > Settings > Custom Domain
   - Vercel: Dashboard > Project > Settings > Domains

2. ✅ **アラート設定**
   - Render: Dashboard > Notifications
   - Upstash: Console > Alerts

3. ✅ **パフォーマンス最適化**
   - キャッシュTTLの調整
   - Worker並列度の調整
   - Storage容量の監視

---

**デプロイ完了おめでとうございます！🎉**

何か問題があれば、Render/Vercel/Supabase のログを確認してください。

