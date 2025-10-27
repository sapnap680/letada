// frontend/pages/result.tsx
import { useEffect, useState } from "react";
import { useRouter } from "next/router";

interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  output_path?: string;
  error?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: {
    universities?: string[];
    total_count?: number;
  };
}

export default function Result() {
  const router = useRouter();
  const { jobId } = router.query;
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId || typeof jobId !== "string") return;

    let intervalId: NodeJS.Timeout;

    const pollJobStatus = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/jobs/${jobId}`);

        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }

        const data: JobStatus = await res.json();
        setJobStatus(data);

        // 完了またはエラー時はポーリングを停止
        if (data.status === "done" || data.status === "error") {
          if (intervalId) {
            clearInterval(intervalId);
          }
        }
      } catch (err) {
        console.error("ジョブステータス取得エラー:", err);
        setError(err instanceof Error ? err.message : "ステータス取得に失敗しました");
      }
    };

    // 初回実行
    pollJobStatus();

    // 2秒ごとにポーリング
    intervalId = setInterval(pollJobStatus, 2000);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [jobId]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "done":
        return "text-green-600";
      case "error":
        return "text-red-600";
      case "processing":
        return "text-blue-600";
      case "queued":
        return "text-yellow-600";
      default:
        return "text-gray-600";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "done":
        return "✅";
      case "error":
        return "❌";
      case "processing":
        return "⏳";
      case "queued":
        return "⏰";
      default:
        return "❓";
    }
  };

  const getFilename = (path: string | undefined) => {
    if (!path) return "";
    return path.split("/").pop() || path.split("\\").pop() || "";
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-xl p-8">
          <h1 className="text-4xl font-bold mb-2 text-gray-800">
            📊 処理状況
          </h1>
          <p className="text-gray-600 mb-8">
            ジョブID: <code className="bg-gray-100 px-2 py-1 rounded">{jobId}</code>
          </p>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              ❌ {error}
            </div>
          )}

          {jobStatus && (
            <>
              {/* ステータス表示 */}
              <div className="mb-8">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="text-4xl">{getStatusIcon(jobStatus.status)}</span>
                    <div>
                      <p className={`text-2xl font-semibold ${getStatusColor(jobStatus.status)}`}>
                        {jobStatus.status.toUpperCase()}
                      </p>
                      <p className="text-sm text-gray-500">
                        {jobStatus.updated_at && new Date(jobStatus.updated_at).toLocaleString("ja-JP")}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-700">
                      {Math.round(jobStatus.progress * 100)}%
                    </p>
                    <p className="text-sm text-gray-500">進捗</p>
                  </div>
                </div>

                {/* プログレスバー */}
                <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${
                      jobStatus.status === "done"
                        ? "bg-green-500"
                        : jobStatus.status === "error"
                        ? "bg-red-500"
                        : "bg-blue-500"
                    }`}
                    style={{ width: `${jobStatus.progress * 100}%` }}
                  ></div>
                </div>

                {/* メッセージ */}
                <p className="mt-4 text-gray-700 text-center">
                  {jobStatus.message}
                </p>
              </div>

              {/* メタデータ */}
              {jobStatus.metadata && (
                <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-semibold text-gray-700 mb-2">📋 処理詳細</h3>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {jobStatus.metadata.universities && (
                      <li>対象大学: {jobStatus.metadata.universities.join(", ")}</li>
                    )}
                    {jobStatus.metadata.total_count && (
                      <li>大学数: {jobStatus.metadata.total_count}校</li>
                    )}
                  </ul>
                </div>
              )}

              {/* 完了時のダウンロードボタン */}
              {jobStatus.status === "done" && jobStatus.output_path && (
                <div className="p-6 bg-green-50 border border-green-200 rounded-lg">
                  <h3 className="text-xl font-semibold text-green-800 mb-4">
                    🎉 処理が完了しました！
                  </h3>
                  <a
                    href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${
                      getFilename(jobStatus.output_path).endsWith('.xlsx') 
                        ? '/csv/download/' 
                        : '/pdf/download/'
                    }${encodeURIComponent(getFilename(jobStatus.output_path))}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition-all"
                  >
                    📥 {getFilename(jobStatus.output_path).endsWith('.xlsx') ? 'Excelをダウンロード' : 'PDFをダウンロード'}
                  </a>
                  <p className="mt-4 text-sm text-gray-600">
                    ファイル名: {getFilename(jobStatus.output_path)}
                  </p>
                </div>
              )}

              {/* エラー時の表示 */}
              {jobStatus.status === "error" && jobStatus.error && (
                <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
                  <h3 className="text-xl font-semibold text-red-800 mb-4">
                    ❌ エラーが発生しました
                  </h3>
                  <pre className="text-sm text-red-700 whitespace-pre-wrap bg-red-100 p-4 rounded overflow-auto">
                    {jobStatus.error}
                  </pre>
                </div>
              )}

              {/* 処理中の自動更新メッセージ */}
              {(jobStatus.status === "processing" || jobStatus.status === "queued") && (
                <div className="mt-6 p-4 bg-blue-50 rounded-lg text-center">
                  <p className="text-blue-800">
                    <span className="animate-pulse">🔄</span> 2秒ごとに自動更新しています...
                  </p>
                </div>
              )}
            </>
          )}

          {!jobStatus && !error && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">ジョブ情報を取得中...</p>
            </div>
          )}

          {/* 戻るボタン */}
          <div className="mt-8 text-center">
            <button
              onClick={() => router.push("/")}
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              ← トップページに戻る
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

