-- Migration 02: Indexes for Logs (REQ-44)

-- Performance indexes for auth_logs (REQ-42, REQ-44)
CREATE INDEX IF NOT EXISTS idx_auth_logs_timestamp ON auth_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_auth_logs_username ON auth_logs(username);
CREATE INDEX IF NOT EXISTS idx_auth_logs_method ON auth_logs(method);

-- Performance indexes for access_logs (REQ-43, REQ-44)
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_username ON access_logs(username);
CREATE INDEX IF NOT EXISTS idx_access_logs_floor ON access_logs(floor);
