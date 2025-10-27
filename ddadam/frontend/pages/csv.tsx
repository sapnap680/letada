// frontend/pages/csv.tsx
import { useState } from "react";
import { useRouter } from "next/router";

export default function CsvUpload() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [universityName, setUniversityName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      
      if (!selectedFile.name.endsWith('.csv')) {
        setError("CSVファイルのみアップロード可能です");
        return;
      }
      
      setFile(selectedFile);
      setError("");
      
      // ファイル名から大学名を推測
      if (!universityName) {
        const name = selectedFile.name
          .replace('.csv', '')
          .replace(/_/g, ' ');
        setUniversityName(name);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("CSVファイルを選択してください");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      
      const formData = new FormData();
      formData.append("file", file);
      if (universityName) {
        formData.append("university_name", universityName);
      }

      const res = await fetch(`${apiUrl}/csv/upload`, {
        method: "POST",
        body: formData,
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
      console.error("CSVアップロードエラー:", err);
      setError(err instanceof Error ? err.message : "CSVアップロードに失敗しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-green-50 to-teal-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          {/* ヘッダー */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-2 text-gray-800">
              📊 CSVファイルアップロード
            </h1>
            <p className="text-gray-600">
              選手名簿CSVをアップロードしてJBA照合を実行
            </p>
          </div>

          {/* ナビゲーション */}
          <div className="mb-8 flex flex-wrap gap-4">
            <button
              onClick={() => router.push("/")}
              className="px-4 py-2 text-gray-600 hover:text-blue-600 transition-colors"
            >
              ← 大学名入力モード
            </button>
            <button
              onClick(() => router.push("/tournament")}
              className="px-4 py-2 text-gray-600 hover:text-purple-600 transition-colors"
            >
              🏀 大会IDモード
            </button>
          </div>

          {/* ファイル選択 */}
          <div className="mb-6">
            <label className="block text-lg font-semibold mb-4 text-gray-700">
              📄 CSVファイルを選択
            </label>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-3 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100
                cursor-pointer"
            />
            {file && (
              <p className="mt-2 text-sm text-gray-600">
                選択: <span className="font-semibold">{file.name}</span> ({(file.size / 1024).toFixed(2)} KB)
              </p>
            )}
          </div>

          {/* 大学名入力 */}
          <div className="mb-6">
            <label className="block text-lg font-semibold mb-4 text-gray-700">
              🎓 大学名（オプション）
            </label>
            <input
              type="text"
              placeholder="例: 白鴎大学"
              value={universityName}
              onChange={(e) => setUniversityName(e.target.value)}
              className="border border-gray-300 rounded-lg p-3 w-full focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            <p className="text-sm text-gray-500 mt-2">
              未入力の場合、ファイル名から自動取得します
            </p>
          </div>

          {/* エラー表示 */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              ❌ {error}
            </div>
          )}

          {/* アップロードボタン */}
          <button
            onClick={handleUpload}
            disabled={loading || !file}
            className={`w-full py-4 px-6 rounded-lg font-bold text-white text-lg transition-all ${
              loading || !file
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-green-600 hover:bg-green-700 shadow-lg hover:shadow-xl"
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
                アップロード中...
              </span>
            ) : (
              "🚀 CSVをアップロードして照合開始"
            )}
          </button>

          {/* 説明 */}
          <div className="mt-8 p-4 bg-green-50 rounded-lg">
            <h3 className="font-semibold text-green-900 mb-2">💡 CSVファイルの形式</h3>
            <ul className="list-disc list-inside text-sm text-green-800 space-y-1">
              <li>選手名、生年月日などの情報が含まれていること</li>
              <li>エンコーディング: UTF-8 または Shift_JIS</li>
              <li>ファイルサイズ: 10MB以下を推奨</li>
              <li>背番号列は自動的に除外されます</li>
            </ul>
          </div>

          {/* CSVサンプル */}
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-semibold text-gray-900 mb-2">📋 CSVサンプル</h3>
            <pre className="text-xs text-gray-700 overflow-x-auto">
{`氏名,氏名カナ,生年月日,学年
田中 太郎,タナカ タロウ,2003-04-15,2年
佐藤 次郎,サトウ ジロウ,2002-08-22,3年
鈴木 花子,スズキ ハナコ,2004-01-10,1年`}
            </pre>
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

