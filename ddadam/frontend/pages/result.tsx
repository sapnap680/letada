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
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900">
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 lg:p-12">
        <div className="w-full max-w-5xl">
          {/* ヘッダー */}
          <div className="text-center mb-8 sm:mb-10 lg:mb-12">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold mb-4 sm:mb-6 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
              処理状況
            </h1>
            <p className="text-slate-300 text-lg sm:text-xl">
              ジョブID: <code className="bg-slate-800/50 px-4 py-2 rounded-lg text-purple-300 font-mono text-base sm:text-lg">{jobId}</code>
            </p>
          </div>

          {/* メインカード */}
          <div className="bg-slate-800/50 backdrop-blur-lg rounded-2xl shadow-2xl border border-slate-700/50 p-8 sm:p-10 lg:p-12">
            {error && (
              <div className="mb-6 p-6 bg-red-900/30 border-2 border-red-500/50 rounded-xl text-red-200 backdrop-blur-sm">
                <div className="flex items-center">
                  <span className="mr-3 text-3xl">❌</span>
                  <span className="text-xl font-semibold">{error}</span>
                </div>
              </div>
            )}

            {jobStatus && (
              <>
                {/* ステータス表示 */}
                <div className="mb-8 sm:mb-10 lg:mb-12">
                  <div className="flex flex-col sm:flex-row items-center justify-between mb-6 sm:mb-8 gap-4 sm:gap-6">
                    <div className="flex items-center space-x-4 sm:space-x-6">
                      <span className="text-5xl sm:text-6xl lg:text-7xl">{getStatusIcon(jobStatus.status)}</span>
                      <div>
                        <p className={`text-3xl sm:text-4xl lg:text-5xl font-bold ${getStatusColor(jobStatus.status)}`}>
                          {jobStatus.status.toUpperCase()}
                        </p>
                        <p className="text-base sm:text-lg text-slate-400 mt-2">
                          {jobStatus.updated_at && new Date(jobStatus.updated_at).toLocaleString("ja-JP")}
                        </p>
                      </div>
                    </div>
                    <div className="text-center sm:text-right">
                      <p className="text-6xl sm:text-7xl lg:text-8xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                        {Math.round(jobStatus.progress * 100)}%
                      </p>
                      <p className="text-xl sm:text-2xl text-slate-400 mt-2">進捗</p>
                    </div>
                  </div>

                  {/* プログレスバー */}
                  <div 
                    className="w-full rounded-full overflow-hidden shadow-2xl border-4 relative"
                    style={{
                      backgroundColor: 'rgba(51, 65, 85, 0.5)',
                      height: '4rem',
                      borderColor: 'rgba(71, 85, 105, 0.5)',
                    }}
                  >
                    {/* 背景のアニメーション効果 */}
                    {(jobStatus.status === "processing" || jobStatus.status === "queued") && (
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer"></div>
                    )}
                    <div
                      className="h-full transition-all duration-700 ease-out rounded-full flex items-center justify-end relative z-10"
                      style={{
                        width: `${Math.max(jobStatus.progress * 100, 3)}%`,
                        background: jobStatus.status === "done"
                          ? 'linear-gradient(to right, #10b981, #34d399, #10b981)'
                          : jobStatus.status === "error"
                          ? 'linear-gradient(to right, #ef4444, #fb7185, #ef4444)'
                          : 'linear-gradient(to right, #3b82f6, #a855f7, #3b82f6)',
                        paddingRight: '1.5rem',
                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
                      }}
                    >
                      {jobStatus.progress > 0.05 && (
                        <span 
                          className="text-white font-black drop-shadow-lg"
                          style={{ fontSize: '1.5rem' }}
                        >
                          {Math.round(jobStatus.progress * 100)}%
                        </span>
                      )}
                    </div>
                    {/* 進捗テキスト（バーの外側にも表示） */}
                    {jobStatus.progress <= 0.05 && (
                      <div className="absolute inset-0 flex items-center justify-center z-20">
                        <span 
                          className="text-slate-200 font-bold"
                          style={{ fontSize: '1.5rem' }}
                        >
                          {Math.round(jobStatus.progress * 100)}%
                        </span>
                      </div>
                    )}
                  </div>

                  {/* メッセージ */}
                  <p className="mt-6 sm:mt-8 lg:mt-10 text-slate-200 text-center text-xl sm:text-2xl lg:text-3xl font-semibold">
                    {jobStatus.message}
                  </p>
                </div>

                {/* 完了時のダウンロードボタン */}
                {jobStatus.status === "done" && jobStatus.output_path && (
                  <div className="p-6 sm:p-8 lg:p-10 bg-gradient-to-br from-green-900/30 to-emerald-900/30 border-2 border-green-500/50 rounded-xl backdrop-blur-sm">
                    <h3 className="text-3xl sm:text-4xl lg:text-5xl font-semibold text-green-300 mb-6 sm:mb-8 flex items-center">
                      <span className="mr-3 sm:mr-4 text-4xl sm:text-5xl">🎉</span>
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
                      className="inline-block bg-gradient-to-r from-yellow-400 via-orange-500 to-red-500 hover:from-yellow-300 hover:via-orange-400 hover:to-red-400 text-white font-black py-16 sm:py-20 lg:py-24 px-20 sm:px-24 lg:px-28 rounded-2xl shadow-2xl hover:shadow-yellow-500/50 transition-all transform hover:scale-105 active:scale-95 text-4xl sm:text-5xl lg:text-6xl border-4 border-yellow-300"
                    >
                      <span className="flex items-center">
                        <span className="mr-6 sm:mr-8 text-5xl sm:text-6xl lg:text-7xl">📥</span>
                        PDFをダウンロード
                      </span>
                    </a>
                    <p className="mt-6 sm:mt-8 text-lg sm:text-xl text-slate-300">
                      ファイル名: <code className="bg-slate-800/50 px-3 sm:px-4 py-2 rounded text-green-300 text-base sm:text-lg">{getFilename(jobStatus.output_path)}</code>
                    </p>
                  </div>
                )}

                {/* エラー時の表示 */}
                {jobStatus.status === "error" && jobStatus.error && (
                  <div className="p-6 sm:p-8 lg:p-10 bg-gradient-to-br from-red-900/30 to-rose-900/30 border-2 border-red-500/50 rounded-xl backdrop-blur-sm">
                    <h3 className="text-3xl sm:text-4xl lg:text-5xl font-semibold text-red-300 mb-6 sm:mb-8 flex items-center">
                      <span className="mr-3 sm:mr-4 text-4xl sm:text-5xl">❌</span>
                      エラーが発生しました
                    </h3>
                    <div className="text-lg sm:text-xl text-red-200 mb-4 sm:mb-6">
                      <strong>エラー:</strong> {jobStatus.error}
                    </div>
                    {(jobStatus as any).error_detail && (
                      <details className="mt-4 sm:mt-6">
                        <summary className="cursor-pointer text-red-300 font-semibold mb-2 sm:mb-4 hover:text-red-200 transition-colors text-lg sm:text-xl">
                          詳細を表示（開発者向け）
                        </summary>
                        <pre className="text-sm sm:text-base text-red-200 whitespace-pre-wrap bg-slate-900/50 p-4 sm:p-6 rounded-lg overflow-auto max-h-96 border border-red-500/30 mt-2 sm:mt-4">
                          {(jobStatus as any).error_detail}
                        </pre>
                      </details>
                    )}
                  </div>
                )}

              </>
            )}

            {!jobStatus && !error && (
              <div className="text-center py-12 sm:py-16 lg:py-20">
                <div className="animate-spin rounded-full h-20 sm:h-24 lg:h-32 w-20 sm:w-24 lg:w-32 border-4 border-purple-500 border-t-transparent mx-auto mb-6 sm:mb-8"></div>
                <p className="text-slate-300 text-xl sm:text-2xl lg:text-3xl">ジョブ情報を取得中...</p>
              </div>
            )}

            {/* 戻るボタン */}
            <div className="mt-8 sm:mt-10 lg:mt-12 text-center">
              <button
                onClick={() => router.push("/")}
                className="text-purple-400 hover:text-purple-300 font-semibold transition-colors flex items-center justify-center mx-auto text-lg sm:text-xl lg:text-2xl"
              >
                <span className="mr-2 sm:mr-3 text-2xl sm:text-3xl">←</span>
                トップページに戻る
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
