-- Add user settings columns to existing users table.
-- Run this if you see: column users.organisation_logo_url does not exist
-- Example: psql -U your_user -d nec_db -f migrations/add_user_settings_columns.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS report_naming_preference VARCHAR(64) NOT NULL DEFAULT 'contract_date_validation';
ALTER TABLE users ADD COLUMN IF NOT EXISTS data_retention_days INTEGER NOT NULL DEFAULT 365;
ALTER TABLE users ADD COLUMN IF NOT EXISTS organisation_logo_url VARCHAR(512);
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB;
