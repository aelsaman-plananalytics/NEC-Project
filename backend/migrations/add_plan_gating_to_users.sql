-- Plan gating: free tier run limits, no Stripe yet.
-- Run: psql -U your_user -d nec_db -f migrations/add_plan_gating_to_users.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_type VARCHAR(64) NOT NULL DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_run_limit INTEGER NOT NULL DEFAULT 10;
ALTER TABLE users ADD COLUMN IF NOT EXISTS runs_this_month INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS runs_reset_date DATE;

COMMENT ON COLUMN users.plan_type IS 'free | enterprise (enterprise = no limit)';
COMMENT ON COLUMN users.runs_reset_date IS 'Next date when runs_this_month is reset to 0';
