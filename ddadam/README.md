# JBA照合・PDF生成システム v2.0

大学バスケットボール部のメンバー情報をJBAデータベースと照合し、**訂正箇所を赤字で表示したPDF**を自動生成するシステム

**Streamlit → FastAPI + Next.js に完全移行済み**

---

## 🚀 クイックスタート

**すぐに試したい:** [QUICKSTART.md](QUICKSTART.md) - 15分で起動 ⚡

### 🏀 大会IDモード（メイン機能）

**大会ID1つで全処理を自動化！**

1. JBA管理画面で大会IDを確認（URLから取得）
2. 大会IDを入力
3. JBAログイン情報を入力
4. 「大会CSVを取得して照合開始」をクリック
5. 進捗画面で待機
6. **PDF（訂正箇所は赤字）** をダウンロード

**特徴:**
- ✅ 全大学のCSVを自動取得
- ✅ JBA照合（完全一致・部分一致・未発見を判定）
- ✅ 訂正箇所を赤字で表示
- ✅ 1大学1ページでPDF生成
- ✅ Excel出力なし（PDFのみ）

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

### 🔐 **2つのログイン情報について**

このシステムは**2種類の認証情報**を使用します：

| 種類 | 用途 | 設定方法 |
|------|------|----------|
| **管理画面** | CSV取得 | **コード内に固定**（`backend/config.py`） |
| **JBA一般** | 選手検索 | **ユーザーが入力**（フロントエンド） |

**管理画面ログイン情報（`kcbf`/`sakura272`）はコード内に固定されているため、環境変数の設定は不要です。**

---

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
# 大会ID処理（全大学のCSV自動取得 + JBA照合 + PDF生成）
POST /tournament
{
  "game_id": "12345",
  "jba_credentials": {"email": "...", "password": "..."}
}

# ジョブステータス確認（進捗ポーリング）
GET /jobs/{job_id}

# PDFダウンロード
GET /pdf/download/{filename}
```

**API ドキュメント:** http://localhost:8000/docs

---

## ⚡ 主な機能

- ✅ 大会ID1つで全大学のCSVを自動取得
- ✅ JBAデータベースと自動照合（完全一致・部分一致・未発見）
- ✅ **訂正箇所を赤字で表示したPDF生成**（1大学1ページ）
- ✅ リアルタイム進捗表示（2秒ポーリング）
- ✅ 並列処理（最大5スレッド）
- ✅ 永続キャッシュ（2回目以降100倍速）

---

## 📁 ディレクトリ構造

```
ddadam/
├── frontend/           # Next.js (Vercel)
│   ├── pages/
│   │   ├── index.tsx    # 大会ID入力（メイン）
│   │   └── result.tsx   # 進捗表示・PDF DL
│   └── package.json
│
├── backend/           # FastAPI (Railway)
│   ├── main.py       # アプリケーション
│   ├── routers/
│   │   ├── tournament.py  # 大会ID処理
│   │   ├── jobs.py        # ジョブステータス
│   │   └── pdf.py         # PDFダウンロード
│   └── worker/       # JBA照合・PDF生成
│       ├── jba_verification_lib.py
│       └── integrated_system.py
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
