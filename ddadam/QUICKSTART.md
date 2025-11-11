# ⚡ クイックスタートガイド

JBA照合・PDF生成システムを**15分で起動**

---

## 🎯 3ステップで起動

### Step 1: リポジトリクローン（1分）

```bash
git clone <repository-url>
cd ddadam
```

### Step 2: Backend起動（5分）

```bash
cd backend

# 仮想環境作成
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 起動
uvicorn main:app --reload --port 8000
```

**確認:** http://localhost:8000/docs にアクセス

### Step 3: Frontend起動（5分）

```bash
cd frontend

# 依存関係インストール
npm install

# 起動
npm run dev
```

**確認:** http://localhost:3000 にアクセス

---

## ✅ 動作確認

### 1. ブラウザで確認

http://localhost:3000 にアクセスして:

- ✅ トップページが表示される
- ✅ 3つのモードボタンが表示される
- ✅ 入力フォームが表示される

### 2. API確認

http://localhost:8000/docs にアクセスして:

- ✅ Swagger UI が表示される
- ✅ `/health` エンドポイントをテスト
- ✅ ステータスが `healthy` になる

---

## 🏀 初回使用（大会IDモード）

1. http://localhost:3000 にアクセス
2. 「🏀 大会IDモード」をクリック
3. 大会IDを入力（例: `12345`）
4. JBAログイン情報を入力
5. 「大会CSVを取得して照合開始」をクリック
6. 進捗画面で待機
7. 完了後、ExcelまたはPDFをダウンロード

---

## 🚀 本番デプロイ（30分）

詳細: [docs/RAILWAY_QUICKSTART.md](docs/RAILWAY_QUICKSTART.md)

**簡易版:**

1. **Supabase**: プロジェクト作成（5分）
2. **Upstash**: Redis作成（3分）
3. **Railway**: Backend + Worker デプロイ（10分）
4. **Vercel**: Frontend デプロイ（5分）
5. **動作確認**（5分）

---

## 📚 詳細ドキュメント

- [README.md](README.md) - プロジェクト概要
- [docs/INDEX.md](docs/INDEX.md) - 全ドキュメント一覧
- [docs/RAILWAY_QUICKSTART.md](docs/RAILWAY_QUICKSTART.md) - 本番デプロイ

---

## 🆘 トラブルシューティング

### Backend が起動しない

```bash
# 依存関係を再インストール
pip install --upgrade -r requirements.txt
```

### Frontend が起動しない

```bash
# node_modules を削除して再インストール
rm -rf node_modules
npm install
```

### ポート競合エラー

```bash
# 別のポートで起動
uvicorn main:app --reload --port 8001
npm run dev -- --port 3001
```

---

**これで起動完了！🎉**

次は [README.md](README.md) を読んで機能を確認してください。


