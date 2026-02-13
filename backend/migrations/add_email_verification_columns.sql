-- Email verification for NEC Engineering Analysis (SMTP-based).
-- Run after deploying: psql -U your_user -d nec_db -f migrations/add_email_verification_columns.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_expires TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_users_email_verification_token ON users (email_verification_token);
