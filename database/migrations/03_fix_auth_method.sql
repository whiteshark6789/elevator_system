-- Migration 03: Fix auth_logs method check constraint to allow 'password'
ALTER TABLE auth_logs DROP CONSTRAINT auth_logs_method_check;
ALTER TABLE auth_logs ADD CONSTRAINT auth_logs_method_check CHECK (method IN ('face', 'rfid', 'otp', 'password'));
