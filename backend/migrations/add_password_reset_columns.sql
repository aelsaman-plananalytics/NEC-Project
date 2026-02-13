-- Password reset: token and expiry on users.
-- Run after deploying: psql -U your_user -d nec_db -f migrations/add_password_reset_columns.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_users_password_reset_token ON users (password_reset_token);
