# JBA照合・PDF生成システム v2.0

大学バスケットボール部のメンバー情報をJBAデータベースと照合し、PDF形式のメンバー表を自動生成するシステム

**Streamlit → FastAPI + Next.js に完全移行済み**

---

## 🚀 クイックスタート

**すぐに試したい:** [QUICKSTART.md](QUICKSTART.md) - 15分で起動 ⚡

### 3つのモード

| モード | 説明 | 推奨度 |
|--------|------|--------|
| 🏀 **大会IDモード** | 大会ID1つで全大学のCSVを自動取得 | ⭐⭐⭐ |
| 📊 **CSVアップロード** | 手動で取得したCSVを処理 | ⭐⭐ |
| 🎓 **大学名入力** | 大学名を入力してPDF生成 | ⭐ |

### 使い方

1. **本番環境**: https://your-project.vercel.app にアクセス
2. 好きなモードを選択
3. 必要情報を入力
4. 処理完了後、ファイルをダウンロード

---

## 🏗️ アーキテクチャ

```
Vercel (Next.js)
    ↓ HTTPS
Railway (FastAPI + Worker)
    ↓
Supabase (DB/Storage) + Upstash (Redis)
```

**技術スタック:**
- Frontend: Next.js 14 + TypeScript + Tailwind CSS
- Backend: FastAPI + Python 3.11
- Deploy: Vercel + Railway
- DB/Storage: Supabase
- Cache: Upstash Redis

---

## 📦 ローカル開発

### 1. リポジトリクローン

```bash
git clone <repository-url>
cd ddadam
```

### 2. Backend起動

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend起動

```bash
cd frontend
npm install
npm run dev
```

**アクセス:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 📚 ドキュメント

### デプロイ
- 📘 [Railway デプロイ手順](docs/DEPLOY_RAILWAY.md) - 完全ガイド
- ⚡ [Railway クイックスタート](docs/RAILWAY_QUICKSTART.md) - 15分で完了
- 🌐 [Vercel セットアップ](docs/VERCEL_SETUP.md)
- 🐛 [トラブルシューティング](docs/DEPLOYMENT_TROUBLESHOOTING.md)

### 機能
- 📊 [CSV機能ガイド](docs/CSV_FEATURE.md)
- 🔐 [環境変数設定](docs/ENV_SETUP.md)
- 🔄 [移行ステータス](docs/MIGRATION_STATUS.md)

---

## 🔧 API エンドポイント

### メイン機能

```bash
# 大会ID処理（全大学のCSV自動取得）
POST /tournament
{
  "game_id": "12345",
  "jba_credentials": {"email": "...", "password": "..."},
  "generate_pdf": true
}

# CSVアップロード
POST /csv/upload
Content-Type: multipart/form-data

# ジョブステータス確認
GET /jobs/{job_id}

# ファイルダウンロード
GET /csv/download/{filename}
GET /pdf/download/{filename}
```

**API ドキュメント:** http://localhost:8000/docs

---

## ⚡ 主な機能

- ✅ 大会ID1つで全大学のCSVを自動取得
- ✅ JBAデータベースと自動照合
- ✅ 色分けExcel + PDF生成
- ✅ リアルタイム進捗表示（2秒ポーリング）
- ✅ 並列処理（最大5スレッド）
- ✅ 永続キャッシュ（2回目以降100倍速）

---

## 📁 ディレクトリ構造

```
ddadam/
├── frontend/           # Next.js (Vercel)
│   ├── pages/         # トップ, 大会ID, CSV, 進捗
│   └── package.json
│
├── backend/           # FastAPI (Railway)
│   ├── main.py       # アプリケーション
│   ├── routers/      # API エンドポイント
│   └── worker/       # JBA照合・PDF生成
│
├── docs/             # ドキュメント
└── README.md         # このファイル
```

---

## 🚀 デプロイ

### クイックデプロイ（30分）

1. **Supabase**: プロジェクト作成 + DB初期化 + Storage設定
2. **Upstash**: Redis データベース作成
3. **Railway**: リポジトリ連携 + 環境変数設定
4. **Vercel**: リポジトリ連携 + 環境変数設定

**詳細:** [docs/RAILWAY_QUICKSTART.md](docs/RAILWAY_QUICKSTART.md)

---

## 🆘 トラブルシューティング

問題が発生した場合:

1. [トラブルシューティングガイド](docs/DEPLOYMENT_TROUBLESHOOTING.md) を確認
2. Railway/Vercel のログを確認
3. [GitHub Issues](https://github.com/YOUR_USERNAME/jba-system/issues) で質問

---

## 📊 パフォーマンス

| 指標 | Streamlit版 | FastAPI版 | 改善率 |
|------|------------|-----------|--------|
| 初回処理 | 30分 | 1分 | **30倍** |
| 2回目以降 | 30分 | 3秒 | **600倍** |
| 同時処理 | 1ユーザー | 多数 | **∞** |

---

## 📄 ライセンス

MIT License

---

## 🤝 コントリビューション

Pull Request 歓迎！

1. Fork this repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

**Powered by FastAPI + Next.js | v2.0.0**
