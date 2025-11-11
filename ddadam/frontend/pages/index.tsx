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
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-2xl">
          {/* ヘッダー */}
          <div className="text-center mb-12">
            <h1 className="text-5xl sm:text-6xl font-bold mb-4 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
              JBA照合システム
            </h1>
          </div>

          {/* フォームカード */}
          <div className="bg-slate-800/50 backdrop-blur-lg rounded-2xl shadow-2xl border border-slate-700/50 p-8 sm:p-10">
            {/* 大会ID入力 */}
            <div className="mb-8">
              <label className="block text-lg font-semibold mb-4 text-slate-300 uppercase tracking-wide">
                大会ID
              </label>
              <input
                type="text"
                placeholder="例: 12345"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-6 py-6 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all text-xl"
              />
            </div>

            {/* JBAログイン情報 */}
            <div className="mb-8">
              <label className="block text-lg font-semibold mb-4 text-slate-300 uppercase tracking-wide">
                JBAログイン情報
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <input
                  type="email"
                  placeholder="JBAメールアドレス"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-6 py-6 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all text-xl"
                />
                <input
                  type="password"
                  placeholder="JBAパスワード"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-600 rounded-xl px-6 py-6 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all text-xl"
                />
              </div>
            </div>

            {/* エラー表示 */}
            {error && (
              <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-xl text-red-200 backdrop-blur-sm">
                <div className="flex items-center">
                  <span className="mr-2">❌</span>
                  <span>{error}</span>
                </div>
              </div>
            )}

            {/* 実行ボタン */}
            <button
              onClick={handleStart}
              disabled={loading}
              className={`w-full py-6 px-8 rounded-xl font-bold text-white text-2xl transition-all transform ${
                loading
                  ? "bg-slate-600 cursor-not-allowed"
                  : "bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 shadow-lg hover:shadow-purple-500/50 hover:scale-[1.02] active:scale-[0.98]"
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
                <span className="flex items-center justify-center">
                  <span className="mr-2">🚀</span>
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
