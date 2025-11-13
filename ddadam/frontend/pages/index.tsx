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
    <main className="min-h-screen" style={{ backgroundColor: '#4f46e5' }}>
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-3xl">
          {/* ヘッダー */}
          <div className="text-center mb-10">
            <h1 className="text-4xl sm:text-5xl font-black mb-4 text-white tracking-tight">
              JBA照合システム
            </h1>
          </div>

          {/* フォームカード */}
          <div className="rounded-3xl shadow-2xl p-8 sm:p-10 border border-gray-100" style={{ backgroundColor: '#4f46e5' }}>
            {/* 大会ID入力 */}
            <div className="mb-6">
              <label className="block text-2xl font-bold mb-3 text-white">
                大会ID
              </label>
              <input
                type="text"
                placeholder="例: 12345"
                value={gameId}
                onChange={(e) => setGameId(e.target.value)}
                style={{
                  paddingTop: '3rem',
                  paddingBottom: '3rem',
                  paddingLeft: '2rem',
                  paddingRight: '2rem',
                }}
                className="w-full bg-white border-4 border-gray-300 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-yellow-400 focus:ring-4 focus:ring-yellow-200 transition-all text-3xl font-medium"
              />
            </div>

            {/* JBAログイン情報 */}
            <div className="mb-6">
              <label className="block text-2xl font-bold mb-3 text-white">
                JBAログイン情報
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <input
                  type="email"
                  placeholder="JBAメールアドレス"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{
                    paddingTop: '3rem',
                    paddingBottom: '3rem',
                    paddingLeft: '2rem',
                    paddingRight: '2rem',
                  }}
                  className="w-full bg-white border-4 border-gray-300 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-yellow-400 focus:ring-4 focus:ring-yellow-200 transition-all text-3xl font-medium"
                />
                <input
                  type="text"
                  placeholder="JBAパスワード"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{
                    paddingTop: '3rem',
                    paddingBottom: '3rem',
                    paddingLeft: '2rem',
                    paddingRight: '2rem',
                  }}
                  className="w-full bg-white border-4 border-gray-300 rounded-2xl text-gray-900 placeholder-gray-400 focus:outline-none focus:border-yellow-400 focus:ring-4 focus:ring-yellow-200 transition-all text-3xl font-medium"
                />
              </div>
            </div>

            {/* エラー表示 */}
            {error && (
              <div className="mb-6 p-4 bg-red-100 border-4 border-red-400 rounded-2xl">
                <div className="flex items-center">
                  <span className="mr-3 text-2xl">❌</span>
                  <span className="text-red-900 text-xl font-bold">{error}</span>
                </div>
              </div>
            )}

            {/* 実行ボタン */}
            <button
              onClick={handleStart}
              disabled={loading}
              style={loading ? {} : {
                background: 'linear-gradient(to right, #facc15, #f97316, #ef4444)',
                paddingTop: '3rem',
                paddingBottom: '3rem',
                paddingLeft: '2rem',
                paddingRight: '2rem',
              }}
              className={`w-full rounded-2xl font-black text-white text-3xl transition-all transform shadow-xl ${
                loading
                  ? "bg-gray-400 cursor-not-allowed py-12 px-8"
                  : "hover:scale-105 active:scale-95 hover:shadow-2xl"
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-10 w-10 text-white"
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
                  <span className="text-3xl">処理中...</span>
                </span>
              ) : (
                <span className="flex items-center justify-center">
                  <span className="mr-3 text-4xl">🚀</span>
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
