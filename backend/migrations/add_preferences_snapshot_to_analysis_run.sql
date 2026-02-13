-- Snapshot of user preferences at run creation for consistent report generation.
-- Run: psql -U your_user -d nec_db -f migrations/add_preferences_snapshot_to_analysis_run.sql

ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS preferences_snapshot JSONB;

COMMENT ON COLUMN analysis_runs.preferences_snapshot IS 'User preferences at run creation: confidentiality_mode, default_report_format, organisation_logo_url, auto_download_report, data_retention_days';
