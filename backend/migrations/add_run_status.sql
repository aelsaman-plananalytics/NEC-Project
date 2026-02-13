-- Run lifecycle status: processing | completed | failed | timed_out
ALTER TABLE analysis_runs
ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'completed';

COMMENT ON COLUMN analysis_runs.status IS 'processing | completed | failed | timed_out';
