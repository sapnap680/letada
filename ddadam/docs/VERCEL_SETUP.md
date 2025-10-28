# 🌐 Vercel セットアップガイド

このガイドでは、Next.js フロントエンドを Vercel にデプロイする手順を説明します。

---

## 📋 前提条件

- [x] Railway で Backend がデプロイ済み
- [x] Backend の公開URLを確認済み（例: `https://letada-production.up.railway.app`）
- [x] GitHub にプロジェクトを push 済み

---

## 🚀 デプロイ手順

### Step 1: プロジェクト作成

1. [Vercel Dashboard](https://vercel.com/dashboard) にアクセス
2. **"New Project"** をクリック
3. GitHub アカウントで認証
4. リポジトリを選択

### Step 2: ビルド設定

```
┌─────────────────────────────────────────────────┐
│ Configure Project                                │
├─────────────────────────────────────────────────┤
│ Framework Preset                                 │
│ ● Next.js                  ← 自動検出される      │
│                                                  │
│ Root Directory                                   │
│ frontend/                  ← 必ず設定！         │
│                                                  │
│ Build Command                                    │
│ npm run build              ← デフォルトでOK      │
│                                                  │
│ Output Directory                                 │
│ .next                      ← デフォルトでOK      │
│                                                  │
│ Install Command                                  │
│ npm install                ← デフォルトでOK      │
└─────────────────────────────────────────────────┘
```

**重要:** Root Directory を **`frontend/`** に設定してください！

### Step 3: 環境変数を設定

**Environment Variables セクションで設定:**

```bash
# Key（全て大文字）
NEXT_PUBLIC_API_URL

# Value（Railway の公開URL）
https://letada-production.up.railway.app

# Environment（必ず All を選択）
● All
```

**設定例:**
```
┌─────────────────────────────────────────────────┐
│ Environment Variables                            │
├─────────────────────────────────────────────────┤
│ Key                                              │
│ NEXT_PUBLIC_API_URL                              │
│                                                  │
│ Value                                            │
│ https://letada-production.up.railway.app        │
│                                                  │
│ Environment                                      │
│ ○ Production  ○ Preview  ● All                  │
│                                                  │
│ [ Add ]                                          │
└─────────────────────────────────────────────────┘
```

### Step 4: デプロイ

1. **"Deploy"** をクリック
2. ビルド完了まで待機（2-3分）
3. デプロイされたURLにアクセス

---

## ✅ 動作確認

### 1. ブラウザで確認

```
https://your-project.vercel.app
```

### 2. 開発者ツールで環境変数を確認

```javascript
// ブラウザの開発者ツール（F12）> Console
console.log(process.env.NEXT_PUBLIC_API_URL)

// 期待される出力:
// "https://letada-production.up.railway.app"
```

### 3. API 接続を確認

1. トップページで大学名を入力
2. JBA ログイン情報を入力
3. "PDF生成を開始" をクリック
4. 進捗画面に遷移すれば成功 ✅

---

## 🐛 トラブルシューティング

### エラー 1: `NEXT_PUBLIC_API_URL` が undefined

**原因:**
- 環境変数が設定されていない
- または Environment が "All" になっていない

**解決方法:**
1. Settings > Environment Variables を開く
2. `NEXT_PUBLIC_API_URL` を確認
3. Environment: **All** を選択
4. Save して Redeploy

---

### エラー 2: "references Secret" エラー

```
Environment Variable "NEXT_PUBLIC_API_URL" references Secret "next_public_api_url"
```

**原因:**
`next.config.js` の `env` セクションが問題

**解決済み（2025-10-27）:**
```javascript
// 修正後の next.config.js
const nextConfig = {
  reactStrictMode: true,
  // env セクションは削除
}
```

**確認方法:**
```bash
git pull  # 最新のコードを取得
# Vercel が自動的に再デプロイ
```

---

### エラー 3: Root Directory が間違っている

```
Error: Could not find a valid build in the ".next" directory
```

**原因:**
Root Directory が設定されていない

**解決方法:**
1. Vercel Dashboard > Project > **Settings** を開く
2. **General** セクション
3. **Root Directory** を `frontend/` に変更
4. **Save** をクリック
5. **Deployments** から Redeploy

---

### エラー 4: API に接続できない

```
Failed to fetch
```

**チェックリスト:**
1. Railway の Backend が正常に動作しているか確認:
   ```bash
   curl https://letada-production.up.railway.app/health
   ```

2. Vercel の環境変数が正しいか確認:
   ```bash
   # Settings > Environment Variables
   NEXT_PUBLIC_API_URL=https://letada-production.up.railway.app
   ```

3. CORS エラーの場合、Backend の `main.py` を確認:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # 本番では制限すべき
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

---

## 🔧 カスタムドメイン設定（オプション）

### 独自ドメインを設定する

1. Vercel Dashboard > Project > **Settings** を開く
2. **Domains** セクションを選択
3. ドメイン名を入力（例: `jba.yourdomain.com`）
4. **Add** をクリック
5. DNS レコードを設定:
   ```
   Type: CNAME
   Name: jba
   Value: cname.vercel-dns.com
   ```

---

## 📊 環境変数の管理

### 環境ごとに異なる値を設定

```bash
# Production（本番）
NEXT_PUBLIC_API_URL=https://letada-production.up.railway.app

# Preview（プレビュー - PR作成時）
NEXT_PUBLIC_API_URL=https://letada-staging.up.railway.app

# Development（ローカル開発）
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 設定方法:
1. Settings > Environment Variables で変数を追加
2. Environment で適切な環境を選択:
   - **Production**: 本番デプロイのみ
   - **Preview**: PR プレビューのみ
   - **Development**: ローカル開発のみ
   - **All**: 全ての環境

---

## 🚨 セキュリティのベストプラクティス

### 1. CORS 設定を制限（本番環境）

```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-project.vercel.app",
        "https://jba.yourdomain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. 環境変数の命名規則

- **クライアント側で使う:** `NEXT_PUBLIC_` プレフィックス必須
- **サーバー側のみ:** プレフィックスなし

```bash
# ✅ ブラウザで使用可能
NEXT_PUBLIC_API_URL=https://...

# ❌ ブラウザでは undefined
API_URL=https://...
```

---

## 📚 参考リンク

- [Vercel Documentation](https://vercel.com/docs)
- [Next.js Environment Variables](https://nextjs.org/docs/app/building-your-application/configuring/environment-variables)
- [Vercel CLI](https://vercel.com/docs/cli)

---

## ✅ デプロイチェックリスト

デプロイ前に確認：

- [ ] GitHub にコードを push 済み
- [ ] `frontend/next.config.js` から `env` セクションを削除
- [ ] Railway で Backend がデプロイ済み
- [ ] Backend の公開URLを確認
- [ ] Vercel で Root Directory を `frontend/` に設定
- [ ] Vercel で `NEXT_PUBLIC_API_URL` を設定（Environment: All）
- [ ] デプロイ完了後、ブラウザで動作確認
- [ ] 開発者ツールで環境変数を確認

---

**Vercel デプロイが完了したら [RAILWAY_QUICKSTART.md](./RAILWAY_QUICKSTART.md) に戻って全体の動作確認をしてください。**

