# 📚 ドキュメント一覧

JBA照合・PDF生成システムの全ドキュメント

---

## 🚀 デプロイ（本番環境）

### メインガイド
- **[Railway デプロイ完全ガイド](DEPLOY_RAILWAY.md)** - 詳細な手順（30分）
- **[Railway クイックスタート](RAILWAY_QUICKSTART.md)** ⚡ - 15分で完了
- **[Vercel セットアップ](VERCEL_SETUP.md)** - フロントエンドデプロイ

### トラブルシューティング
- **[デプロイエラー対処法](DEPLOYMENT_TROUBLESHOOTING.md)** 🐛 - よくあるエラーと解決方法
- **[環境変数設定ガイド](ENV_SETUP.md)** 🔐 - 本番・開発環境の設定

---

## 📊 機能ガイド

### 各モードの使い方
- **[CSV機能ガイド](CSV_FEATURE.md)** - CSVアップロード・大会ID取得

---

## 🔄 開発情報

- **[移行ステータス](MIGRATION_STATUS.md)** - Streamlit→FastAPIの移行状況
- **[プロジェクト構造](PROJECT_STRUCTURE.md)** 📁 - ディレクトリ構造とファイル説明

---

## 📖 クイックリファレンス

### デプロイフロー

```
1. Supabase
   ├─ プロジェクト作成
   ├─ supabase_init.sql 実行
   └─ Storage バケット作成

2. Upstash
   └─ Redis データベース作成

3. Railway
   ├─ リポジトリ連携
   ├─ Web Service 作成
   ├─ Worker Service 作成
   └─ 環境変数設定

4. Vercel
   ├─ リポジトリ連携
   └─ 環境変数設定
```

### 必要な環境変数

**Railway (Backend):**
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxx...
OUTPUT_BUCKET=outputs
REDIS_URL=redis://default:xxxxx@...
```

**Vercel (Frontend):**
```bash
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
```

---

## 🆘 サポート

問題が発生した場合:

1. まず [DEPLOYMENT_TROUBLESHOOTING.md](DEPLOYMENT_TROUBLESHOOTING.md) を確認
2. Railway/Vercel のログを確認
3. [GitHub Issues](https://github.com/YOUR_USERNAME/jba-system/issues) で質問

---

**[← README に戻る](../README.md)**

