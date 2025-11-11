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
        return "text-green-400";
      case "error":
        return "text-red-400";
      case "processing":
        return "text-blue-400";
      case "queued":
        return "text-yellow-400";
      default:
        return "text-slate-400";
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
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-3xl">
          {/* ヘッダー */}
          <div className="text-center mb-8">
            <h1 className="text-4xl sm:text-5xl font-bold mb-2 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
              処理状況
            </h1>
            <p className="text-slate-300">
              ジョブID: <code className="bg-slate-800/50 px-3 py-1 rounded-lg text-purple-300 font-mono text-sm">{jobId}</code>
            </p>
          </div>

          {/* メインカード */}
          <div className="bg-slate-800/50 backdrop-blur-lg rounded-2xl shadow-2xl border border-slate-700/50 p-8 sm:p-10">
            {error && (
              <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-xl text-red-200 backdrop-blur-sm">
                <div className="flex items-center">
                  <span className="mr-2">❌</span>
                  <span>{error}</span>
                </div>
              </div>
            )}

            {jobStatus && (
              <>
                {/* ステータス表示 */}
                <div className="mb-8">
                  <div className="flex flex-col sm:flex-row items-center justify-between mb-6 gap-4">
                    <div className="flex items-center space-x-4">
                      <span className="text-5xl">{getStatusIcon(jobStatus.status)}</span>
                      <div>
                        <p className={`text-3xl font-bold ${getStatusColor(jobStatus.status)}`}>
                          {jobStatus.status.toUpperCase()}
                        </p>
                        <p className="text-sm text-slate-400 mt-1">
                          {jobStatus.updated_at && new Date(jobStatus.updated_at).toLocaleString("ja-JP")}
                        </p>
                      </div>
                    </div>
                    <div className="text-center sm:text-right">
                      <p className="text-7xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                        {Math.round(jobStatus.progress * 100)}%
                      </p>
                      <p className="text-lg text-slate-400 mt-2">進捗</p>
                    </div>
                  </div>

                  {/* プログレスバー */}
                  <div className="w-full bg-slate-700/50 rounded-full h-12 overflow-hidden backdrop-blur-sm shadow-inner">
                    <div
                      className={`h-full transition-all duration-500 rounded-full flex items-center justify-end pr-4 ${
                        jobStatus.status === "done"
                          ? "bg-gradient-to-r from-green-500 to-emerald-500"
                          : jobStatus.status === "error"
                          ? "bg-gradient-to-r from-red-500 to-rose-500"
                          : "bg-gradient-to-r from-blue-500 to-purple-500"
                      }`}
                      style={{ width: `${jobStatus.progress * 100}%` }}
                    >
                      <span className="text-white font-bold text-2xl">
                        {Math.round(jobStatus.progress * 100)}%
                      </span>
                    </div>
                  </div>

                  {/* メッセージ */}
                  <p className="mt-6 text-slate-200 text-center text-lg">
                    {jobStatus.message}
                  </p>
                </div>


                {/* 完了時のダウンロードボタン */}
                {jobStatus.status === "done" && jobStatus.output_path && (
                  <div className="p-6 bg-gradient-to-br from-green-900/30 to-emerald-900/30 border border-green-500/50 rounded-xl backdrop-blur-sm">
                    <h3 className="text-2xl font-semibold text-green-300 mb-4 flex items-center">
                      <span className="mr-2">🎉</span>
                      処理が完了しました！
                    </h3>
                    <a
                      href={
                        jobStatus.output_path.startsWith("http://") || jobStatus.output_path.startsWith("https://")
                          ? jobStatus.output_path
                          : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/pdf/download/${encodeURIComponent(getFilename(jobStatus.output_path))}`
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-bold py-4 px-8 rounded-xl shadow-lg hover:shadow-green-500/50 transition-all transform hover:scale-105 active:scale-95"
                    >
                      <span className="flex items-center">
                        <span className="mr-2">📥</span>
                        PDFをダウンロード
                      </span>
                    </a>
                    <p className="mt-4 text-sm text-slate-300">
                      ファイル名: <code className="bg-slate-800/50 px-2 py-1 rounded text-green-300">{getFilename(jobStatus.output_path)}</code>
                    </p>
                  </div>
                )}

                {/* エラー時の表示 */}
                {jobStatus.status === "error" && jobStatus.error && (
                  <div className="p-6 bg-gradient-to-br from-red-900/30 to-rose-900/30 border border-red-500/50 rounded-xl backdrop-blur-sm">
                    <h3 className="text-2xl font-semibold text-red-300 mb-4 flex items-center">
                      <span className="mr-2">❌</span>
                      エラーが発生しました
                    </h3>
                    <div className="text-sm text-red-200 mb-4">
                      <strong>エラー:</strong> {jobStatus.error}
                    </div>
                    {(jobStatus as any).error_detail && (
                      <details className="mt-4">
                        <summary className="cursor-pointer text-red-300 font-semibold mb-2 hover:text-red-200 transition-colors">
                          詳細を表示（開発者向け）
                        </summary>
                        <pre className="text-xs text-red-200 whitespace-pre-wrap bg-slate-900/50 p-4 rounded-lg overflow-auto max-h-96 border border-red-500/30 mt-2">
                          {(jobStatus as any).error_detail}
                        </pre>
                      </details>
                    )}
                  </div>
                )}

              </>
            )}

            {!jobStatus && !error && (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-16 w-16 border-4 border-purple-500 border-t-transparent mx-auto mb-4"></div>
                <p className="text-slate-300">ジョブ情報を取得中...</p>
              </div>
            )}

            {/* 戻るボタン */}
            <div className="mt-8 text-center">
              <button
                onClick={() => router.push("/")}
                className="text-purple-400 hover:text-purple-300 font-semibold transition-colors flex items-center justify-center mx-auto"
              >
                <span className="mr-2">←</span>
                トップページに戻る
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

