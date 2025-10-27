# 🚂 Railway クイックスタートガイド

このガイドでは、**15分で** Railway + Vercel に JBA システムをデプロイする方法を説明します。

---

## ⚡ 3ステップでデプロイ

### Step 1: 外部サービスの準備（5分）

#### 1.1 Supabase

```bash
# 1. https://app.supabase.com/ でプロジェクト作成
# 2. SQL Editor で実行:
```

```sql
-- backend/supabase_init.sql の内容をコピペして RUN
CREATE TABLE jobs (
  job_id uuid PRIMARY KEY,
  status text NOT NULL,
  progress numeric DEFAULT 0,
  message text,
  output_path text,
  error text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX ON jobs (status);
```

```bash
# 3. Storage で "outputs" バケット作成（Public: ON）
# 4. Settings > API で以下をコピー:
#    - Project URL
#    - service_role key
```

#### 1.2 Upstash Redis

```bash
# 1. https://console.upstash.com/ でデータベース作成
#    - Name: jba-cache
#    - Region: ap-southeast-1 (Singapore)
# 2. Redis Connect から接続URLをコピー
```

---

### Step 2: Railway デプロイ（5分）

#### 2.1 プロジェクト作成

```bash
# 1. https://railway.app/ にアクセス
# 2. "Start a New Project" をクリック
# 3. "Deploy from GitHub repo" を選択
# 4. リポジトリを選択
```

#### 2.2 Web Service 追加

**Settings:**
- **Root Directory**: `backend`
- **Start Command**: 
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

**Variables（重要！）:**

```bash
PYTHON_VERSION=3.11
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxx...（service_role key）
OUTPUT_BUCKET=outputs
REDIS_URL=redis://default:xxxxx@...
CACHE_TYPE=redis
OUTPUT_DIR=/tmp/outputs
JOB_META_DIR=/tmp/temp_results
USE_SUPABASE_STORAGE=true
USE_SUPABASE_JOBS=true
```

**デプロイ:**
- "Deploy" をクリック
- 完了後、**Settings > Networking** で公開URLを確認

#### 2.3 Worker Service 追加

**Settings:**
- **Root Directory**: `backend`
- **Start Command**: 
  ```bash
  python worker/worker_runner.py
  ```

**Variables:**
- Web Service と同じ環境変数をコピー
- または "Copy from Service" を使用

---

### Step 3: Vercel デプロイ（5分）

#### 3.1 プロジェクト作成

```bash
# 1. https://vercel.com/dashboard にアクセス
# 2. "New Project" をクリック
# 3. GitHub リポジトリを選択
# 4. 設定:
#    - Framework: Next.js
#    - Root Directory: frontend
```

#### 3.2 環境変数を設定

```bash
NEXT_PUBLIC_API_URL=https://jba-backend-production.up.railway.app
```

⚠️ **Railway の公開URL**（Step 2.2で確認したURL）を使用

#### 3.3 デプロイ

- "Deploy" をクリック
- 完了後、デプロイされたURLにアクセス

---

## ✅ 動作確認（3分）

### 1. Backend 確認

```bash
# ヘルスチェック
curl https://YOUR-RAILWAY-URL.up.railway.app/health

# 期待される結果:
# {"status":"healthy","cache":true,"supabase":true}
```

### 2. Frontend 確認

1. Vercel URL にアクセス
2. 大学名を入力（例: 白鴎大学）
3. "PDF生成を開始" をクリック
4. 進捗画面で確認
5. 完了後、PDFをダウンロード

### 3. Worker 確認

```bash
# Railway Dashboard > Worker Service > Deployments > View Logs
# 以下のようなログが表示されれば成功:
# Worker started
# Checking for pending jobs...
# No pending jobs. Waiting...
```

---

## 🔧 環境変数一覧

### 必須の環境変数

| 変数名 | 取得元 | 例 |
|-------|--------|---|
| `SUPABASE_URL` | Supabase > Settings > API | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase > Settings > API | `eyJxxx...` |
| `OUTPUT_BUCKET` | Supabase で作成 | `outputs` |
| `REDIS_URL` | Upstash > Database > Connect | `redis://default:xxxxx@...` |

### オプション（デフォルト値あり）

| 変数名 | デフォルト | 説明 |
|-------|----------|------|
| `CACHE_TYPE` | `redis` | キャッシュタイプ |
| `OUTPUT_DIR` | `/tmp/outputs` | 出力ディレクトリ |
| `USE_SUPABASE_STORAGE` | `true` | Supabase Storage を使用 |
| `USE_SUPABASE_JOBS` | `true` | Supabase jobs テーブルを使用 |

---

## 🐛 よくあるエラー

### エラー 1: Backend が起動しない

```
Error: Application startup failed
```

**解決方法:**
1. Railway Dashboard > Service > **Logs** を確認
2. `PYTHON_VERSION=3.11` が設定されているか確認
3. Start Command が正しいか確認:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

### エラー 2: Supabase 接続エラー

```
Error: Invalid Supabase URL or Key
```

**解決方法:**
1. `SUPABASE_URL` が `https://xxxxx.supabase.co` 形式か確認
2. `SUPABASE_KEY` が **service_role key**（長いやつ）か確認
3. Supabase プロジェクトが正常に作成されているか確認

### エラー 3: Worker がジョブを処理しない

```
Worker is running but jobs are not processed
```

**解決方法:**
1. Railway > Worker Service > **Variables** を確認
2. Web Service と同じ環境変数が設定されているか確認
3. Supabase で jobs テーブルが作成されているか確認:
   ```sql
   SELECT * FROM jobs LIMIT 5;
   ```

### エラー 4: Frontend が Backend に接続できない

```
Failed to fetch
```

**解決方法:**
1. Vercel > Settings > Environment Variables を確認
2. `NEXT_PUBLIC_API_URL` が正しい Railway URL か確認
3. CORS エラーの場合、`backend/main.py` の CORS 設定を確認

---

## 💡 Tips

### デプロイを高速化

```bash
# Railway CLI をインストール
npm i -g @railway/cli

# ログをリアルタイムで確認
railway login
railway link
railway logs
```

### 環境変数を一括コピー

```bash
# Railway Dashboard で:
# 1. Web Service の Variables タブを開く
# 2. 右上の "..." > "Copy All Variables"
# 3. Worker Service の Variables タブで "Paste"
```

### デプロイ状況を確認

```bash
# Railway Dashboard で各サービスの Status を確認:
# - Active (緑): 正常稼働中
# - Deploying (黄): デプロイ中
# - Failed (赤): エラー
```

---

## 📊 コスト見積もり

| サービス | プラン | コスト |
|---------|--------|--------|
| Railway | $5クレジット/月 | $0* |
| Vercel | Hobby | $0 |
| Supabase | Free | $0 |
| Upstash | Free | $0 |
| **合計** | | **$0/月** |

\* 2つのサービスで月約 $3-4 程度、$5クレジット内で運用可能

---

## 🎯 次のステップ

1. ✅ **カスタムドメイン設定**（オプション）
2. ✅ **アラート設定**（エラー通知）
3. ✅ **パフォーマンスモニタリング**

詳細は **[DEPLOY_RAILWAY.md](./DEPLOY_RAILWAY.md)** を参照してください。

---

**15分でデプロイ完了！🎉**

何か問題があれば [GitHub Issues](https://github.com/YOUR_USERNAME/jba-system/issues) で質問してください。

