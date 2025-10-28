# 🔐 環境変数セットアップガイド

## 📝 重要なポイント

### ✅ **本番環境（Render/Vercel）**

**環境変数は各サービスのダッシュボードで設定します。ローカルファイルは不要です。**

- **Render**: Dashboard > Service > Environment で設定
- **Vercel**: Dashboard > Project > Settings > Environment Variables で設定

### 🔧 **ローカル開発環境**

ローカルで開発・テストする場合のみ `.env` ファイルを作成してください。

---

## 🌐 本番環境の環境変数設定

### 1. Render（Backend + Worker）

**設定場所**: Render Dashboard > Service > Environment

| 変数名 | 値の例 | 取得方法 |
|-------|--------|---------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` | Supabase Dashboard > Settings > API |
| `SUPABASE_KEY` | `eyJxxx...` | Supabase Dashboard > Settings > API > service_role key |
| `OUTPUT_BUCKET` | `outputs` | Supabase で作成した Storage バケット名 |
| `REDIS_URL` | `redis://default:xxxxx@...` | Upstash Console > Database > Redis Connect |
| `CACHE_TYPE` | `redis` | 固定値 |
| `USE_SUPABASE_STORAGE` | `true` | 固定値 |
| `USE_SUPABASE_JOBS` | `true` | 固定値 |

**設定方法:**

1. Render Dashboard にログイン
2. サービス（`jba-backend` または `jba-worker`）を選択
3. 左メニューから **Environment** をクリック
4. "Add Environment Variable" をクリック
5. 上記の変数を1つずつ追加
6. "Save Changes" をクリック
7. サービスが自動的に再起動されます

### 2. Vercel（Frontend）

**設定場所**: Vercel Dashboard > Project > Settings > Environment Variables

| 変数名 | 値の例 | 説明 |
|-------|--------|------|
| `NEXT_PUBLIC_API_URL` | `https://jba-backend.onrender.com` | Render でデプロイした Backend の URL |

**設定方法:**

1. Vercel Dashboard にログイン
2. プロジェクトを選択
3. Settings > Environment Variables を開く
4. "Add New" をクリック
5. `NEXT_PUBLIC_API_URL` を追加
6. Environment: **All** を選択
7. "Save" をクリック
8. 再デプロイが必要な場合は "Redeploy" をクリック

---

## 💻 ローカル開発環境の設定

### 1. Backend ローカル開発

```bash
cd backend
cp env.example .env
```

`.env` ファイルを編集：

```bash
# Supabase（本番と同じ or ローカルの Supabase）
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_service_role_key

# Redis（本番と同じ or ローカルの Redis）
REDIS_URL=redis://localhost:6379/0
CACHE_TYPE=file  # ローカルではファイルキャッシュでもOK

# ローカルファイルパス
OUTPUT_DIR=./outputs
JOB_META_DIR=./temp_results
CACHE_FILE_PATH=./worker/jba_player_cache.json

# 開発用（Supabase を使わない場合）
USE_SUPABASE_STORAGE=false
USE_SUPABASE_JOBS=false
```

### 2. Frontend ローカル開発

```bash
cd frontend
cp env.local.example .env.local
```

`.env.local` ファイルを編集：

```bash
# ローカルの Backend を指す
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 🚨 重要な注意事項

### ❌ **やってはいけないこと**

- ❌ `.env` ファイルを Git にコミットしない
- ❌ API キーや認証情報をコードに直接書かない
- ❌ `.env` ファイルを本番環境にアップロードしない

### ✅ **正しい運用**

- ✅ `.env.example` は Git にコミット（値は入れない）
- ✅ 本番の環境変数は各サービスのダッシュボードで設定
- ✅ ローカルの `.env` は `.gitignore` に含める（既に設定済み）

---

## 🔍 動作確認

### Backend 起動確認

```bash
cd backend
uvicorn main:app --reload

# 別ターミナルで
curl http://localhost:8000/health
```

**期待される結果:**
```json
{
  "status": "healthy",
  "cache_exists": true,
  "output_dir": true,
  "temp_dir": true
}
```

### Frontend 起動確認

```bash
cd frontend
npm run dev

# ブラウザで http://localhost:3000 にアクセス
```

---

## 🆘 トラブルシューティング

### Supabase 接続エラー

```
Error: Invalid Supabase URL or Key
```

**解決方法:**
1. Supabase Dashboard で URL と Key を再確認
2. Key は **service_role** を使用（anon ではない）
3. 環境変数が正しく設定されているか確認

### Redis 接続エラー

```
Error: Failed to connect to Redis
```

**解決方法:**
1. Upstash Console で接続文字列を再確認
2. ローカル開発の場合は `CACHE_TYPE=file` に変更

### 環境変数が反映されない

**Render の場合:**
1. Dashboard > Environment で変更を保存
2. サービスが自動再起動するまで待つ（2-3分）
3. または Manual Deploy で強制再デプロイ

**Vercel の場合:**
1. Settings > Environment Variables で変更を保存
2. Deployments タブから再デプロイ

---

## 📚 参考情報

### 環境変数の優先順位

1. **最優先**: サービスのダッシュボードで設定した環境変数
2. **次**: `.env` ファイル（ローカル開発のみ）
3. **デフォルト**: `config.py` のデフォルト値

### セキュリティのベストプラクティス

- 🔒 API キーは定期的にローテーション
- 🔒 service_role key は絶対にクライアント側で使用しない
- 🔒 本番と開発で異なる認証情報を使用
- 🔒 不要な権限は付与しない

---

**これで環境変数の設定は完了です！** 🎉

