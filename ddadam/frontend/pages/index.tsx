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
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50">
      <div className="min-h-screen flex items-center justify-center p-8 sm:p-12 lg:p-16">
        <div className="w-full max-w-6xl">
          {/* ヘッダー */}
          <div className="text-center mb-16 sm:mb-20 lg:mb-24">
            <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-black mb-8 sm:mb-10 lg:mb-12 text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 tracking-tight">
              JBA照合システム
            </h1>
          </div>

          {/* フォームカード */}
          <div className="bg-white/90 backdrop-blur-lg rounded-3xl shadow-2xl p-8 sm:p-12 lg:p-16 border-4 border-white/50">
            {/* 大会ID入力 */}
            <div className="mb-10 sm:mb-12 lg:mb-16">
              <label className="block text-3xl sm:text-4xl lg:text-5xl font-bold mb-4 sm:mb-6 lg:mb-8 text-gray-800">
                大会ID
              </label>
              <input
                type="text"
                placeholder="例: 12345"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                className="w-full bg-gray-50 border-4 border-gray-300 rounded-2xl px-8 sm:px-12 lg:px-16 py-8 sm:py-12 lg:py-16 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-200 transition-all text-3xl sm:text-4xl lg:text-5xl font-medium"
              />
            </div>

            {/* JBAログイン情報 */}
            <div className="mb-10 sm:mb-12 lg:mb-16">
              <label className="block text-3xl sm:text-4xl lg:text-5xl font-bold mb-4 sm:mb-6 lg:mb-8 text-gray-800">
                JBAログイン情報
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8 lg:gap-10">
                <input
                  type="email"
                  placeholder="JBAメールアドレス"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-gray-50 border-4 border-gray-300 rounded-2xl px-8 sm:px-12 lg:px-16 py-8 sm:py-12 lg:py-16 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-200 transition-all text-3xl sm:text-4xl lg:text-5xl font-medium"
                />
                <input
                  type="password"
                  placeholder="JBAパスワード"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-gray-50 border-4 border-gray-300 rounded-2xl px-8 sm:px-12 lg:px-16 py-8 sm:py-12 lg:py-16 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-200 transition-all text-3xl sm:text-4xl lg:text-5xl font-medium"
                />
              </div>
            </div>

            {/* エラー表示 */}
            {error && (
              <div className="mb-8 sm:mb-10 lg:mb-12 p-6 sm:p-8 lg:p-10 bg-red-50 border-4 border-red-300 rounded-2xl">
                <div className="flex items-center">
                  <span className="mr-4 sm:mr-6 text-4xl sm:text-5xl lg:text-6xl">❌</span>
                  <span className="text-red-800 text-2xl sm:text-3xl lg:text-4xl font-bold">{error}</span>
                </div>
              </div>
            )}

            {/* 実行ボタン */}
            <button
              onClick={handleStart}
              disabled={loading}
              className={`w-full py-12 sm:py-16 lg:py-20 px-8 sm:px-12 lg:px-16 rounded-2xl font-black text-white text-4xl sm:text-5xl lg:text-6xl transition-all transform shadow-2xl border-4 ${
                loading
                  ? "bg-gray-400 border-gray-500 cursor-not-allowed"
                  : "bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 border-white/50 hover:from-blue-500 hover:via-purple-500 hover:to-pink-500 active:from-blue-700 active:via-purple-700 active:to-pink-700 hover:scale-[1.02] active:scale-[0.98] hover:shadow-2xl"
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-6 sm:mr-8 h-16 sm:h-20 lg:h-24 w-16 sm:w-20 lg:w-24 text-white"
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
                  <span>処理中...</span>
                </span>
              ) : (
                <span className="flex items-center justify-center">
                  <span className="mr-4 sm:mr-6 text-5xl sm:text-6xl lg:text-7xl">🚀</span>
                  <span>大会CSVを取得して照合開始</span>
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
