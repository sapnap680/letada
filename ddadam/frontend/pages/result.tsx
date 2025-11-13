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

    // 0.5秒ごとにポーリング（より細かく更新）
    intervalId = setInterval(pollJobStatus, 500);

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
    <main className="min-h-screen" style={{ backgroundColor: '#4f46e5' }}>
      <div className="min-h-screen flex items-center justify-center p-4 sm:p-8">
        <div className="w-full max-w-3xl">
          {/* ヘッダー */}
          <div className="text-center mb-16">
            <h1 className="text-6xl sm:text-7xl font-black mb-6 text-white tracking-tight">
              処理状況
            </h1>
            <p className="text-white text-xl">
              ジョブID: <code className="bg-white/20 px-4 py-2 rounded-lg text-white font-mono text-lg">{jobId}</code>
            </p>
          </div>

          {/* メインカード */}
          <div className="rounded-3xl shadow-2xl p-10 sm:p-12 border border-gray-100" style={{ backgroundColor: '#4f46e5' }}>
            {error && (
              <div className="mb-8 p-6 bg-red-100 border-4 border-red-400 rounded-2xl">
                <div className="flex items-center">
                  <span className="mr-3 text-4xl">❌</span>
                  <span className="text-red-900 text-3xl font-bold">{error}</span>
                </div>
              </div>
            )}

            {jobStatus && (
              <>
                {/* ステータス表示 */}
                <div className="mb-10">
                  <div className="flex flex-col sm:flex-row items-center justify-between mb-6 gap-4">
                    <div className="flex items-center space-x-4">
                      <span className="text-5xl">{getStatusIcon(jobStatus.status)}</span>
                      <div>
                        <p className={`text-3xl font-bold ${getStatusColor(jobStatus.status)}`}>
                          {jobStatus.status.toUpperCase()}
                        </p>
                        <p className="text-base text-white/70 mt-1">
                          {jobStatus.updated_at && new Date(jobStatus.updated_at).toLocaleString("ja-JP")}
                        </p>
                      </div>
                    </div>
                    <div className="text-center sm:text-right">
                      <p className="text-7xl font-bold text-white">
                        {Math.round(jobStatus.progress * 100)}%
                      </p>
                      <p className="text-lg text-white/70 mt-1">進捗</p>
                    </div>
                  </div>

                  {/* プログレスバー */}
                  <div 
                    className="w-full rounded-full overflow-hidden shadow-2xl border-4 relative"
                    style={{
                      backgroundColor: 'rgba(255, 255, 255, 0.2)',
                      height: '3rem',
                      borderColor: 'rgba(255, 255, 255, 0.3)',
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
                          : 'linear-gradient(to right, #facc15, #f97316, #ef4444)',
                        paddingRight: '1rem',
                        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
                      }}
                    >
                      {jobStatus.progress > 0.05 && (
                        <span 
                          className="text-white font-black drop-shadow-lg"
                          style={{ fontSize: '1.25rem' }}
                        >
                          {Math.round(jobStatus.progress * 100)}%
                        </span>
                      )}
                    </div>
                    {/* 進捗テキスト（バーの外側にも表示） */}
                    {jobStatus.progress <= 0.05 && (
                      <div className="absolute inset-0 flex items-center justify-center z-20">
                        <span 
                          className="text-white font-bold"
                          style={{ fontSize: '1.25rem' }}
                        >
                          {Math.round(jobStatus.progress * 100)}%
                        </span>
                      </div>
                    )}
                  </div>

                  {/* メッセージ */}
                  <p className="mt-6 text-white text-center text-xl font-semibold">
                    {jobStatus.message}
                  </p>
                </div>

                {/* 完了時のダウンロードボタン */}
                {jobStatus.status === "done" && jobStatus.output_path && (
                  <div className="p-8 bg-white/10 border-2 border-white/20 rounded-2xl">
                    <h3 className="text-3xl font-semibold text-white mb-6 flex items-center">
                      <span className="mr-3 text-4xl">🎉</span>
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
                      style={{
                        background: 'linear-gradient(to right, #facc15, #f97316, #ef4444)',
                        paddingTop: '5rem',
                        paddingBottom: '5rem',
                        paddingLeft: '3rem',
                        paddingRight: '3rem',
                      }}
                      className="inline-block text-white font-black rounded-2xl shadow-2xl hover:shadow-yellow-500/50 transition-all transform hover:scale-105 active:scale-95 text-5xl border-4 border-yellow-300"
                    >
                      <span className="flex items-center">
                        <span className="mr-4 text-6xl">📥</span>
                        PDFをダウンロード
                      </span>
                    </a>
                    <p className="mt-6 text-lg text-white/80">
                      ファイル名: <code className="bg-white/20 px-3 py-2 rounded text-white text-base">{getFilename(jobStatus.output_path)}</code>
                    </p>
                  </div>
                )}

                {/* エラー時の表示 */}
                {jobStatus.status === "error" && jobStatus.error && (
                  <div className="p-8 bg-red-100 border-4 border-red-400 rounded-2xl">
                    <h3 className="text-3xl font-semibold text-red-900 mb-6 flex items-center">
                      <span className="mr-3 text-4xl">❌</span>
                      エラーが発生しました
                    </h3>
                    <div className="text-xl text-red-900 mb-4">
                      <strong>エラー:</strong> {jobStatus.error}
                    </div>
                    {(jobStatus as any).error_detail && (
                      <details className="mt-4">
                        <summary className="cursor-pointer text-red-900 font-semibold mb-2 hover:text-red-700 transition-colors text-lg">
                          詳細を表示（開発者向け）
                        </summary>
                        <pre className="text-sm text-red-900 whitespace-pre-wrap bg-white/50 p-4 rounded-lg overflow-auto max-h-96 border border-red-400 mt-2">
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
                <div className="animate-spin rounded-full h-16 w-16 border-4 border-white border-t-transparent mx-auto mb-4"></div>
                <p className="text-white text-2xl">ジョブ情報を取得中...</p>
              </div>
            )}

            {/* 戻るボタン */}
            <div className="mt-8 text-center">
              <button
                onClick={() => router.push("/")}
                className="text-white hover:text-white/80 font-semibold transition-colors flex items-center justify-center mx-auto text-xl"
              >
                <span className="mr-2 text-2xl">←</span>
                トップページに戻る
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
