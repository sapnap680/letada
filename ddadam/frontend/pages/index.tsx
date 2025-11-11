// frontend/pages/index.tsx
import { useState } from "react";
import { useRouter } from "next/router";

export default function Home() {
  const router = useRouter();
  const [gameId, setGameId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleStart = async () => {
    setLoading(true);
    setError("");

    if (!gameId) {
      setError("大会IDを入力してください");
      setLoading(false);
      return;
    }

    if (!email || !password) {
      setError("JBAログイン情報を入力してください");
      setLoading(false);
      return;
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      console.log("API URL:", apiUrl); // デバッグ用
      
      const res = await fetch(`${apiUrl}/tournament`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_id: gameId,
          jba_credentials: {
            email,
            password,
          },
          generate_pdf: true,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
      }

      const data = await res.json();

      if (data.job_id) {
        // ジョブIDを取得したら結果ページに遷移
        router.push(`/result?jobId=${data.job_id}`);
      } else {
        setError("ジョブIDが取得できませんでした");
      }
    } catch (err) {
      console.error("大会処理エラー:", err);
      setError(err instanceof Error ? err.message : "大会処理に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          {/* ヘッダー */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-2 text-gray-800">
              🏀 JBA照合・PDF生成システム
            </h1>
            <p className="text-gray-600">
              大会IDを入力して、全大学のCSVを自動取得・JBA照合・PDF生成
            </p>
          </div>

          {/* 大会ID入力 */}
          <div className="mb-6">
            <label className="block text-lg font-semibold mb-4 text-gray-700">
              🏆 大会ID
            </label>
            <input
              type="text"
              placeholder="例: 12345"
              value={gameId}
              onChange={(e) => setGameId(e.target.value)}
              className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg"
            />
            <p className="text-sm text-gray-500 mt-2">
              JBA管理画面のURL内にある数字です（例: game_category_id/12345）
            </p>
          </div>

          {/* JBAログイン情報 */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-700">
              🔐 JBAログイン情報
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                type="email"
                placeholder="JBAメールアドレス"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              <input
                type="password"
                placeholder="JBAパスワード"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* エラー表示 */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              ❌ {error}
            </div>
          )}

          {/* 実行ボタン */}
          <button
            onClick={handleStart}
            disabled={loading}
            className={`w-full py-4 px-6 rounded-lg font-bold text-white text-lg transition-all ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-purple-600 hover:bg-purple-700 shadow-lg hover:shadow-xl"
            }`}
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                処理中...
              </span>
            ) : (
              "🚀 大会CSVを取得して照合開始"
            )}
          </button>

          {/* 説明 */}
          <div className="mt-8 p-4 bg-purple-50 rounded-lg">
            <h3 className="font-semibold text-purple-900 mb-2">💡 使い方</h3>
            <ol className="list-decimal list-inside text-sm text-purple-800 space-y-1">
              <li>JBA管理画面で大会IDを確認（URLから取得）</li>
              <li>上記フォームに大会IDを入力</li>
              <li>JBAログイン情報（メール・パスワード）を入力</li>
              <li>「大会CSVを取得して照合開始」をクリック</li>
              <li>進捗画面で処理状況を確認</li>
              <li>完了後、PDFをダウンロード</li>
            </ol>
          </div>

          {/* 処理フロー */}
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-semibold text-gray-900 mb-2">📋 処理フロー</h3>
            <div className="text-sm text-gray-700 space-y-2">
              <div className="flex items-center space-x-2">
                <span className="text-purple-600 font-bold">1.</span>
                <span>JBAにログイン</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-purple-600 font-bold">2.</span>
                <span>大会ページから全CSVリンクを取得</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-purple-600 font-bold">3.</span>
                <span>各大学のCSVを自動ダウンロード</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-purple-600 font-bold">4.</span>
                <span>全大学のデータをJBA照合</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-purple-600 font-bold">5.</span>
                <span>訂正箇所を赤字で表示したPDFを生成</span>
              </div>
            </div>
          </div>

          {/* 注意事項 */}
          <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <h3 className="font-semibold text-yellow-900 mb-2">⚠️ 注意事項</h3>
            <ul className="list-disc list-inside text-sm text-yellow-800 space-y-1">
              <li>大会IDはJBA管理画面のURLから確認できます</li>
              <li>処理時間は大学数によって変わります（5〜30分程度）</li>
              <li>進捗画面で処理状況をリアルタイム確認できます</li>
              <li>JBAと異なる情報は赤字で表示されます</li>
            </ul>
          </div>
        </div>

        {/* フッター */}
        <div className="text-center mt-8 text-gray-600 text-sm">
          <p>Powered by FastAPI + Next.js | v2.0.0</p>
        </div>
      </div>
    </main>
  );
}
