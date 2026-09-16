-- Migration 05: Add admin_action to auth_logs method check constraint
ALTER TABLE auth_logs DROP CONSTRAINT auth_logs_method_check;
ALTER TABLE auth_logs ADD CONSTRAINT auth_logs_method_check CHECK (method IN ('face', 'rfid', 'otp', 'password', 'admin_action'));
