# 🚂 Railway + Vercel デプロイ手順書

このドキュメントは **Vercel (Frontend) + Railway (Backend + Worker) + Supabase + Upstash** 構成でのデプロイ手順を説明します。

---

## 🎯 構成概要

| コンポーネント | サービス | 役割 | 無料枠 |
|------------|---------|------|--------|
| Frontend | **Vercel** | Next.js ホスティング | 100GB/月 |
| Backend API | **Railway (Web Service)** | FastAPI | $5/月クレジット |
| PDF生成 | **Railway (Worker Service)** | 非同期処理 | $5/月クレジット |
| ストレージ | **Supabase Storage** | PDF/ZIP保存 | 1GB |
| DB | **Supabase Postgres** | jobs テーブル | 500MB |
| キャッシュ | **Upstash Redis** | 永続キャッシュ | 10,000コマンド/日 |

**合計コスト: $0/月（$5クレジット内）** ✅

---

## 📋 前提条件

- [x] GitHub アカウント
- [x] Railway アカウント（[railway.app](https://railway.app)）
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
git commit -m "Initial commit - Railway deployment"

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
     - `service_role` `secret`: `eyJxxx...` (**サーバー用・機密情報**)

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

## 🚂 Step 4: Railway セットアップ（Backend + Worker）

### 4.1 Railway プロジェクト作成

1. [Railway Dashboard](https://railway.app/) にアクセス
2. "Start a New Project" をクリック
3. "Deploy from GitHub repo" を選択
4. GitHub アカウントで認証
5. リポジトリを選択: `YOUR_USERNAME/jba-system`

### 4.2 Web Service（Backend API）追加

1. プロジェクト作成後、"+ New" をクリック
2. "GitHub Repo" を選択（既に接続済み）
3. **Service Settings** を設定:

   **Root Directory**: `backend`
   
   **Start Command**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
   
   **Build Command**（オプション）:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables** を追加（Variables タブ）:

   | 変数名 | 値 |
   |-------|---|
   | `PYTHON_VERSION` | `3.11` |
   | `SUPABASE_URL` | `https://xxxxx.supabase.co` |
   | `SUPABASE_KEY` | `eyJxxx...`（service_role） |
   | `OUTPUT_BUCKET` | `outputs` |
   | `REDIS_URL` | `redis://default:xxxxx@...` |
   | `CACHE_TYPE` | `redis` |
   | `OUTPUT_DIR` | `/tmp/outputs` |
   | `JOB_META_DIR` | `/tmp/temp_results` |
   | `USE_SUPABASE_STORAGE` | `true` |
   | `USE_SUPABASE_JOBS` | `true` |

5. **Deploy** をクリック

6. デプロイ完了後、**Settings** > **Networking** で公開URLを確認:
   ```
   https://jba-backend-production.up.railway.app
   ```

### 4.3 Worker Service（PDF生成）追加

1. 同じプロジェクト内で "+" をクリック
2. "GitHub Repo" を選択（同じリポジトリ）
3. **Service Settings** を設定:

   **Root Directory**: `backend`
   
   **Start Command**:
   ```bash
   python worker/worker_runner.py
   ```

4. **Environment Variables** を追加:
   - Web Service と**同じ環境変数**をコピー
   - または "Copy from Service" で Web Service から一括コピー

5. **Deploy** をクリック

### 4.4 デプロイ確認

デプロイ完了後（3-5分）：

```bash
# ヘルスチェック
curl https://jba-backend-production.up.railway.app/health

# API ドキュメント
open https://jba-backend-production.up.railway.app/docs
```

---

## 🌐 Step 5: Vercel セットアップ（Frontend）

### 5.1 プロジェクト作成

1. [Vercel Dashboard](https://vercel.com/dashboard) にアクセス
2. "New Project" をクリック
3. GitHub リポジトリを選択
4. 設定:
   - Framework Preset: **Next.js**
   - Root Directory: `frontend`

### 5.2 環境変数を設定

**環境変数を追加:**

| Name | Value |
|------|-------|
| `NEXT_PUBLIC_API_URL` | `https://jba-backend-production.up.railway.app` |

⚠️ **重要**: Railway でデプロイした Backend の公開URLを使用してください

### 5.3 デプロイ

1. "Deploy" をクリック
2. デプロイ完了まで待機（2-3分）
3. デプロイされたURLを確認

---

## ✅ Step 6: 動作確認

### 6.1 Backend 確認

```bash
# ヘルスチェック
curl https://jba-backend-production.up.railway.app/health

# ジョブ一覧
curl https://jba-backend-production.up.railway.app/jobs/

# キャッシュ統計
curl https://jba-backend-production.up.railway.app/cache
```

### 6.2 Frontend 確認

1. Vercel URL にアクセス
2. 大学名を入力
3. JBA認証情報を入力
4. "PDF生成を開始" をクリック
5. 進捗画面で確認
6. 完了後、PDFをダウンロード

### 6.3 Worker 確認

1. Railway Dashboard > Worker Service > **Deployments** を開く
2. 最新のデプロイをクリック > **View Logs**
3. ログに以下が表示されることを確認:
   ```
   Worker started
   Found X pending job(s)
   Processing job xxxx...
   Job completed successfully
   ```

### 6.4 Supabase 確認

1. Dashboard > **Table Editor** > `jobs` を開く
2. ジョブレコードが作成されているか確認
3. Dashboard > **Storage** > `outputs` を開く
4. PDF/ZIPファイルがアップロードされているか確認

---

## 📊 Step 7: 監視とログ

### 7.1 Railway ログ

**リアルタイムログ:**
1. Dashboard > Service を選択
2. **Deployments** タブ
3. 最新のデプロイをクリック
4. **View Logs** をクリック

**または:**
```bash
# Railway CLI をインストール
npm i -g @railway/cli

# ログを表示
railway logs
```

### 7.2 Vercel ログ

1. Dashboard > Project > **Logs** タブ
2. リアルタイムログを確認

### 7.3 Supabase 監視

1. Dashboard > **Database** > **Query Performance**
2. Dashboard > **Storage** > **Usage**

---

## 🐛 トラブルシューティング

### Backend が起動しない

**確認事項:**
1. Railway Dashboard > Service > **Logs** を確認
2. Start Command が正しいか確認:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
3. Root Directory が `backend` になっているか確認

**再デプロイ:**
1. Dashboard > Service > **Deployments**
2. 最新デプロイの "..." > **Redeploy** をクリック

### Worker がジョブを処理しない

**確認事項:**
1. Railway Dashboard > Worker Service > **Logs** を確認
2. 環境変数が Web Service と同じか確認
3. Start Command が正しいか:
   ```bash
   python worker/worker_runner.py
   ```

**Supabase でジョブ確認:**
```sql
-- SQL Editor で実行
SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at DESC LIMIT 10;
```

### Supabase 接続エラー

```
Error: Invalid Supabase URL or Key
```

**解決方法:**
1. Railway Dashboard > Service > **Variables** を開く
2. `SUPABASE_URL` と `SUPABASE_KEY` が正しいか確認
3. Key は **service_role** を使用（anon ではない）

### Redis 接続エラー

```
Error: Failed to connect to Redis
```

**解決方法:**
1. Upstash Console で接続文字列を再確認
2. `REDIS_URL` が正しく設定されているか確認
3. Railway Variables で確認

### 環境変数が反映されない

**Railway の場合:**
1. Dashboard > Service > **Variables** で変更
2. 自動的に再デプロイされる（2-3分待機）
3. または手動で Redeploy

**Vercel の場合:**
1. Settings > Environment Variables で変更
2. Deployments タブから Redeploy

---

## 💰 コスト見積もり

### Railway 無料枠

- **$5/月のスターター クレジット** が付与
- 2つのサービス（Web + Worker）で月約 $3-4 程度
- **無料枠内で十分運用可能** ✅

| サービス | 推定コスト |
|---------|-----------|
| Railway Web | ~$2/月 |
| Railway Worker | ~$2/月 |
| Vercel | $0（無料枠） |
| Supabase | $0（無料枠） |
| Upstash | $0（無料枠） |
| **合計** | **$0-4/月** |

### スケールアップ時

- Railway: 使った分だけ課金（従量制）
- より多くのリソースが必要な場合は Pro プラン

---

## 🔐 セキュリティチェックリスト

- [x] Supabase Service Role Key は環境変数で管理
- [x] Railway Variables は暗号化
- [x] CORS 設定を本番環境に合わせて制限
- [x] Supabase Storage のポリシー設定
- [x] Rate Limiting の実装
- [x] HTTPS 強制（Railway/Vercel で自動）

---

## 🚀 Railway の利点

### ✅ **Render との比較**

| 項目 | Render | **Railway** |
|------|--------|----------|
| **セットアップ** | render.yaml 必要 | **GUI のみ**（設定ファイル不要） ✅ |
| **デプロイ速度** | 5-10分 | **2-3分** ✅ |
| **ログ** | リアルタイム | **リアルタイム + 検索機能** ✅ |
| **自動スリープ** | 15分で停止 | **常時起動**（$5クレジット内） ✅ |
| **CLI** | なし | **Railway CLI** ✅ |
| **料金体系** | プラン固定 | **従量制**（使った分だけ） ✅ |

---

## 📚 参考リンク

- [Railway Documentation](https://docs.railway.app/)
- [Railway CLI](https://docs.railway.app/develop/cli)
- [Vercel Documentation](https://vercel.com/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Upstash Redis Documentation](https://docs.upstash.com/redis)

---

## 🎯 次のステップ

1. ✅ **カスタムドメイン設定**（オプション）
   - Railway: Settings > Networking > Custom Domain
   - Vercel: Settings > Domains

2. ✅ **アラート設定**
   - Railway: Integrations でメール通知設定
   - Upstash: Console > Alerts

3. ✅ **パフォーマンス最適化**
   - キャッシュTTLの調整
   - Worker並列度の調整

---

**Railway デプロイ完了おめでとうございます！🎉**

何か問題があれば、Railway Dashboard > Service > Logs で確認してください。

