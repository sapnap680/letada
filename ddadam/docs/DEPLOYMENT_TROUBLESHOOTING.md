# 🐛 デプロイトラブルシューティング

Railway/Vercel デプロイ時によくあるエラーとその解決方法

---

## 📦 依存関係の問題

### エラー 1: `httpx` と `supabase` のバージョン競合

```
ERROR: Cannot install httpx==0.26.0 and supabase==2.3.4 because 
these package versions have conflicting dependencies.
The conflict is caused by:
    supabase 2.3.4 depends on httpx<0.26 and >=0.24
```

**原因:**
- `supabase 2.3.4` は `httpx<0.26` を要求
- しかし `httpx==0.26.0` が指定されている

**解決済み（2025-10-27）:**
```diff
# backend/requirements.txt
- httpx==0.26.0
+ httpx==0.25.2  # supabase 2.3.4 requires httpx<0.26
```

**確認方法:**
```bash
cd backend
pip install -r requirements.txt
# エラーが出なければ OK
```

---

### エラー 2: Pydantic バージョン競合

```
ERROR: pydantic-core 2.16.1 requires pydantic==2.6.0, but you have pydantic 2.7.0
```

**解決方法:**
`requirements.txt` でバージョン範囲を指定：
```python
pydantic>=2.6.0,<3.0.0
pydantic-settings>=2.1.0,<3.0.0
```

---

## 🚂 Railway デプロイの問題

### エラー 3: Railway でビルドが失敗する

```
Error: Application startup failed
```

**チェックリスト:**
1. **Root Directory** が `backend` になっているか確認
2. **Start Command** が正しいか確認:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
3. **Python Version** が設定されているか確認:
   ```bash
   PYTHON_VERSION=3.11
   ```

**確認方法:**
1. Railway Dashboard > Service を開く
2. Settings > Build & Deploy を確認
3. Deployments > View Logs でエラー詳細を確認

---

### エラー 4: Worker が起動しない

```
ModuleNotFoundError: No module named 'worker'
```

**原因:**
Worker Service の Root Directory が正しくない

**解決方法:**
1. Railway Dashboard > Worker Service > Settings
2. **Root Directory**: `backend` に設定
3. **Start Command**: `python worker/worker_runner.py`

---

## 🗄️ Supabase の問題

### エラー 5: Supabase 接続エラー

```
Error: Invalid Supabase URL or Key
```

**チェックリスト:**
1. **URL が正しいか:**
   - 形式: `https://xxxxx.supabase.co`
   - プロトコル（`https://`）を含める

2. **Key が正しいか:**
   - **service_role** key を使用（長い方）
   - **anon** key ではない

3. **環境変数名が正しいか:**
   ```bash
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJxxxxx...（service_role key）
   ```

**確認方法:**
```bash
# Railway Dashboard > Service > Variables で確認
# または curl でテスト:
curl -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
     https://xxxxx.supabase.co/rest/v1/jobs
```

---

### エラー 6: jobs テーブルが見つからない

```
Error: relation "public.jobs" does not exist
```

**原因:**
`supabase_init.sql` が実行されていない

**解決方法:**
1. Supabase Dashboard > **SQL Editor** を開く
2. `backend/supabase_init.sql` の内容をコピー
3. SQL Editor に貼り付けて **RUN** をクリック

**確認:**
```sql
-- SQL Editor で実行
SELECT * FROM jobs LIMIT 5;
```

---

### エラー 7: Storage バケットが見つからない

```
Error: Bucket "outputs" does not exist
```

**解決方法:**
1. Supabase Dashboard > **Storage** を開く
2. "Create a new bucket" をクリック
3. Name: `outputs`
4. **Public bucket**: ✅ ON
5. "Create bucket" をクリック

**確認:**
```bash
# 環境変数を確認
OUTPUT_BUCKET=outputs
```

---

## 💾 Redis (Upstash) の問題

### エラー 8: Redis 接続エラー

```
Error: Failed to connect to Redis
```

**チェックリスト:**
1. **URL 形式が正しいか:**
   ```
   redis://default:xxxxx@region.upstash.io:6379
   ```

2. **環境変数が設定されているか:**
   ```bash
   REDIS_URL=redis://default:xxxxx@...
   CACHE_TYPE=redis
   ```

3. **Upstash データベースが有効か:**
   - Upstash Console で確認

**回避策（一時的）:**
```bash
# ファイルキャッシュに切り替え
CACHE_TYPE=file
```

---

## 🌐 Vercel の問題

### エラー 9: API に接続できない

```
Failed to fetch
```

**チェックリスト:**
1. **API URL が正しいか:**
   ```bash
   NEXT_PUBLIC_API_URL=https://jba-backend-production.up.railway.app
   ```

2. **プロトコルが正しいか:**
   - ✅ `https://`（本番）
   - ❌ `http://`

3. **Railway の公開 URL が有効か:**
   - Railway Dashboard > Service > Settings > Networking で確認

**確認方法:**
```bash
# ブラウザの開発者ツール > Console で確認
console.log(process.env.NEXT_PUBLIC_API_URL)

# または curl で確認
curl https://jba-backend-production.up.railway.app/health
```

---

### エラー 10: 環境変数が反映されない

```
process.env.NEXT_PUBLIC_API_URL is undefined
```

**原因:**
Vercel で環境変数が設定されていない

**解決方法:**
1. Vercel Dashboard > Project > **Settings** を開く
2. **Environment Variables** を選択
3. `NEXT_PUBLIC_API_URL` を追加
4. Environment: **All** を選択
5. **Save** をクリック
6. **Deployments** タブから **Redeploy**

**重要:**
- `NEXT_PUBLIC_` プレフィックスが必要
- 再デプロイが必要

---

## 🔧 一般的な問題

### エラー 11: ログが表示されない

**Railway:**
1. Dashboard > Service を開く
2. **Deployments** タブ
3. 最新のデプロイをクリック
4. **View Logs** をクリック

**Vercel:**
1. Dashboard > Project を開く
2. **Logs** タブ
3. リアルタイムログを確認

---

### エラー 12: デプロイが遅い

**Railway:**
- 初回デプロイ: 3-5分
- 2回目以降: 1-2分
- キャッシュが効いている場合: 30秒

**高速化:**
1. `.dockerignore` を追加:
   ```
   __pycache__
   *.pyc
   .venv
   outputs/
   temp_results/
   ```

2. `requirements.txt` で不要なパッケージを削除

---

### エラー 13: 環境変数が多すぎる

**簡略化:**

最小限の環境変数セット：
```bash
# 必須（Railway Web + Worker）
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxx...
OUTPUT_BUCKET=outputs
REDIS_URL=redis://default:xxxxx@...

# 必須（Vercel）
NEXT_PUBLIC_API_URL=https://jba-backend-production.up.railway.app

# オプション（デフォルト値がある）
CACHE_TYPE=redis
USE_SUPABASE_STORAGE=true
USE_SUPABASE_JOBS=true
```

---

## 📊 デバッグ方法

### ステップ 1: ローカルで動作確認

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload

# 別ターミナルで
curl http://localhost:8000/health
```

### ステップ 2: Railway でログ確認

```bash
# Railway CLI をインストール
npm i -g @railway/cli

# ログを表示
railway login
railway link
railway logs
```

### ステップ 3: Supabase でデータ確認

```sql
-- SQL Editor で実行
SELECT * FROM jobs ORDER BY created_at DESC LIMIT 10;
```

### ステップ 4: ブラウザで確認

```javascript
// ブラウザの開発者ツール > Console
fetch('https://jba-backend-production.up.railway.app/health')
  .then(r => r.json())
  .then(console.log)
```

---

## 🆘 サポート

問題が解決しない場合：

1. **ログを確認:**
   - Railway: Deployments > View Logs
   - Vercel: Logs タブ

2. **環境変数を確認:**
   - Railway: Settings > Variables
   - Vercel: Settings > Environment Variables

3. **GitHub Issues で質問:**
   - [GitHub Issues](https://github.com/YOUR_USERNAME/jba-system/issues)
   - ログとエラーメッセージを添付

---

## ✅ チェックリスト

デプロイ前に確認：

- [ ] `backend/requirements.txt` が正しい
- [ ] `httpx==0.25.2`（0.26 ではない）
- [ ] Supabase プロジェクト作成済み
- [ ] `supabase_init.sql` 実行済み
- [ ] Storage バケット `outputs` 作成済み（Public: ON）
- [ ] Upstash Redis 作成済み
- [ ] Railway で環境変数設定済み（8個）
- [ ] Vercel で環境変数設定済み（1個）
- [ ] Railway の公開 URL を確認
- [ ] Vercel の `NEXT_PUBLIC_API_URL` が正しい

---

**トラブルシューティングが完了したら [RAILWAY_QUICKSTART.md](./RAILWAY_QUICKSTART.md) に戻ってデプロイを続けてください。**

