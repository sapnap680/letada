// frontend/pages/index.tsx
import { useState } from "react";
import { useRouter } from "next/router";

export default function Home() {
  const router = useRouter();
  const [universities, setUniversities] = useState<string>("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    setLoading(true);
    setError("");

    const universityList = universities
      .split(",")
      .map(s => s.trim())
      .filter(Boolean);

    if (universityList.length === 0) {
      setError("大学名を入力してください");
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
      const res = await fetch(`${apiUrl}/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          universities: universityList,
          jba_credentials: {
            email,
            password,
          },
          include_photos: true,
          format: "A4",
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();

      if (data.job_id) {
        // ジョブIDを取得したら結果ページに遷移
        router.push(`/result?jobId=${data.job_id}`);
      } else {
        setError("ジョブIDが取得できませんでした");
      }
    } catch (err) {
      console.error("PDF生成エラー:", err);
      setError(err instanceof Error ? err.message : "PDF生成に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <h1 className="text-4xl font-bold mb-2 text-gray-800">
            🏀 JBA照合・PDF生成システム
          </h1>
          <p className="text-gray-600 mb-8">
            大学バスケットボール部のメンバー表を自動生成
          </p>

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
                className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <input
                type="password"
                placeholder="JBAパスワード"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* 大学名入力 */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-4 text-gray-700">
              🎓 大学名を入力
            </h2>
            <textarea
              placeholder="大学名を入力（カンマ区切り）&#10;例: 白鴎大学, 筑波大学, 早稲田大学"
              value={universities}
              onChange={(e) => setUniversities(e.target.value)}
              className="border border-gray-300 rounded-lg p-3 w-full h-32 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-sm text-gray-500 mt-2">
              複数の大学を指定する場合はカンマで区切ってください
            </p>
          </div>

          {/* エラー表示 */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              ❌ {error}
            </div>
          )}

          {/* 生成ボタン */}
          <button
            onClick={handleGenerate}
            disabled={loading}
            className={`w-full py-4 px-6 rounded-lg font-bold text-white text-lg transition-all ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 shadow-lg hover:shadow-xl"
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
                生成中...
              </span>
            ) : (
              "🚀 PDF生成を開始"
            )}
          </button>

          {/* 説明 */}
          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">💡 使い方</h3>
            <ol className="list-decimal list-inside text-sm text-blue-800 space-y-1">
              <li>JBAのログイン情報を入力</li>
              <li>PDF化したい大学名を入力（複数可）</li>
              <li>「PDF生成を開始」ボタンをクリック</li>
              <li>処理が完了するまで待機（進捗画面に自動遷移）</li>
              <li>完了後、PDFをダウンロード</li>
            </ol>
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

