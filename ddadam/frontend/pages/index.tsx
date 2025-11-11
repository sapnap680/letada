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
    <main className="min-h-screen bg-gray-50">
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-3xl">
          {/* ヘッダー */}
          <div className="text-center mb-16">
            <h1 className="text-6xl sm:text-7xl font-black mb-6 text-gray-900 tracking-tight">
              JBA照合システム
            </h1>
          </div>

          {/* フォームカード */}
          <div className="bg-white rounded-3xl shadow-2xl p-10 sm:p-12 border border-gray-100">
            {/* 大会ID入力 */}
            <div className="mb-10">
              <label className="block text-xl font-bold mb-5 text-gray-800">
                大会ID
              </label>
              <input
                type="text"
                placeholder="例: 12345"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                className="w-full bg-gray-50 border-2 border-gray-200 rounded-2xl px-8 py-8 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all text-2xl font-medium"
              />
            </div>

            {/* JBAログイン情報 */}
            <div className="mb-10">
              <label className="block text-xl font-bold mb-5 text-gray-800">
                JBAログイン情報
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <input
                  type="email"
                  placeholder="JBAメールアドレス"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-gray-50 border-2 border-gray-200 rounded-2xl px-8 py-8 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all text-2xl font-medium"
                />
                <input
                  type="password"
                  placeholder="JBAパスワード"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-gray-50 border-2 border-gray-200 rounded-2xl px-8 py-8 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all text-2xl font-medium"
                />
              </div>
            </div>

            {/* エラー表示 */}
            {error && (
              <div className="mb-8 p-6 bg-red-50 border-2 border-red-200 rounded-2xl">
                <div className="flex items-center">
                  <span className="mr-3 text-2xl">❌</span>
                  <span className="text-red-800 text-xl font-semibold">{error}</span>
                </div>
              </div>
            )}

            {/* 実行ボタン */}
            <button
              onClick={handleStart}
              disabled={loading}
              className={`w-full py-10 px-8 rounded-2xl font-black text-white text-3xl transition-all transform shadow-xl ${
                loading
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 hover:scale-[1.01] active:scale-[0.99] hover:shadow-2xl"
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-4 h-8 w-8 text-white"
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
                <span className="flex items-center justify-center">
                  <span className="mr-3 text-3xl">🚀</span>
                  大会CSVを取得して照合開始
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
