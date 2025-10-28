-- backend/supabase_init.sql
-- Supabase Postgres テーブル初期化SQL
-- Supabase Dashboard の SQL Editor で実行してください

-- ========================================
-- jobs テーブル: ジョブステータス管理
-- ========================================

CREATE TABLE IF NOT EXISTS jobs (
  job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type text NOT NULL DEFAULT 'pdf_generation',
  status text NOT NULL DEFAULT 'queued',
  progress numeric DEFAULT 0.0 CHECK (progress >= 0 AND progress <= 1),
  message text,
  output_path text,
  error text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- インデックス作成（パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON jobs (job_type);

-- 更新時刻の自動更新トリガー
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = now();
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Storage Bucket 作成
-- ========================================
-- Supabase Dashboard > Storage で手動作成するか、以下のSQLで作成：

-- 1. "outputs" バケットを作成（公開設定）
INSERT INTO storage.buckets (id, name, public)
VALUES ('outputs', 'outputs', true)
ON CONFLICT (id) DO NOTHING;

-- 2. バケットのポリシー設定（全員が読み取り可能、サービスロールが書き込み可能）
-- 注: これは例です。本番環境では適切なポリシーを設定してください

-- 読み取りポリシー（全員）
CREATE POLICY "Public Access" ON storage.objects
FOR SELECT USING (bucket_id = 'outputs');

-- 書き込みポリシー（認証済みユーザー or サービスロール）
CREATE POLICY "Authenticated users can upload files"
ON storage.objects
FOR INSERT
WITH CHECK (bucket_id = 'outputs' AND auth.role() = 'authenticated');

-- サービスロールは全操作可能（自動設定されている場合が多い）

-- ========================================
-- 確認クエリ
-- ========================================

-- テーブルが作成されたか確認
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name = 'jobs';

-- バケットが作成されたか確認
SELECT * FROM storage.buckets WHERE id = 'outputs';

-- ========================================
-- テストデータ挿入（オプション）
-- ========================================

-- テストジョブを作成
INSERT INTO jobs (job_id, job_type, status, progress, message, metadata)
VALUES (
  gen_random_uuid(),
  'pdf_generation',
  'queued',
  0.0,
  'テストジョブ',
  '{"universities": ["テスト大学"]}'::jsonb
);

-- 作成されたジョブを確認
SELECT * FROM jobs ORDER BY created_at DESC LIMIT 5;

-- ========================================
-- クリーンアップ（必要な場合）
-- ========================================

-- 古いジョブを削除（30日以上前）
-- DELETE FROM jobs WHERE created_at < now() - interval '30 days';

-- 全ジョブを削除（注意！）
-- TRUNCATE TABLE jobs;

-- テーブルを削除（注意！）
-- DROP TABLE IF EXISTS jobs CASCADE;


