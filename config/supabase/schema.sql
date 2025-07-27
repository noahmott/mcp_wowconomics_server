-- Supabase Database Schema for WoW Guild Analytics Activity Monitoring
-- 
-- This schema creates tables for real-time activity monitoring while keeping
-- guild data in Redis for performance.

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Activity Logs Table
-- Stores all MCP server activities, requests, and responses
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    activity_type VARCHAR(100) NOT NULL, -- 'connection', 'request', 'response', 'error', 'disconnect'
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tool_name VARCHAR(255),
    request_data JSONB,
    response_data JSONB,
    error_message TEXT,
    duration_ms NUMERIC,
    reasoning TEXT,
    metadata JSONB,
    
    -- Indexes for performance
    CONSTRAINT activity_logs_activity_type_check 
        CHECK (activity_type IN ('connection', 'request', 'response', 'error', 'disconnect', 'mcp_access'))
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_activity_logs_session_id ON activity_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_activity_logs_activity_type ON activity_logs(activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_logs_tool_name ON activity_logs(tool_name) WHERE tool_name IS NOT NULL;

-- Enable real-time for activity_logs table
ALTER PUBLICATION supabase_realtime ADD TABLE activity_logs;

-- Row Level Security (RLS) policies
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;

-- Policy to allow authenticated users to read all activity logs
CREATE POLICY "Allow authenticated users to read activity logs"
ON activity_logs
FOR SELECT
TO authenticated
USING (true);

-- Policy to allow service role to insert activity logs
CREATE POLICY "Allow service role to insert activity logs"
ON activity_logs
FOR INSERT
TO service_role
WITH CHECK (true);

-- Policy to allow authenticated users to insert activity logs (for client-side logging)
CREATE POLICY "Allow authenticated users to insert activity logs"
ON activity_logs
FOR INSERT
TO authenticated
WITH CHECK (true);

-- Function to automatically clean up old activity logs (older than 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_activity_logs()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM activity_logs 
    WHERE timestamp < NOW() - INTERVAL '30 days';
END;
$$;

-- Create a scheduled job to clean up old logs daily (if pg_cron is available)
-- This will run daily at midnight to clean up logs older than 30 days
-- Note: pg_cron needs to be enabled in Supabase project settings
-- SELECT cron.schedule('cleanup-activity-logs', '0 0 * * *', 'SELECT cleanup_old_activity_logs();');

-- View for activity log statistics
CREATE OR REPLACE VIEW activity_log_stats AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    activity_type,
    tool_name,
    COUNT(*) as count,
    AVG(duration_ms) as avg_duration_ms,
    MAX(duration_ms) as max_duration_ms,
    COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as error_count
FROM activity_logs
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', timestamp), activity_type, tool_name
ORDER BY hour DESC;

-- View for session statistics
CREATE OR REPLACE VIEW session_stats AS
SELECT 
    session_id,
    MIN(timestamp) as session_start,
    MAX(timestamp) as session_end,
    MAX(timestamp) - MIN(timestamp) as session_duration,
    COUNT(*) as total_activities,
    COUNT(DISTINCT tool_name) as unique_tools_used,
    COUNT(CASE WHEN activity_type = 'error' THEN 1 END) as error_count,
    AVG(duration_ms) as avg_response_time
FROM activity_logs
WHERE session_id IS NOT NULL
GROUP BY session_id
ORDER BY session_start DESC;

-- Function to get real-time activity summary
CREATE OR REPLACE FUNCTION get_activity_summary(hours_back INTEGER DEFAULT 1)
RETURNS TABLE (
    total_activities BIGINT,
    unique_sessions BIGINT,
    error_rate NUMERIC,
    avg_response_time NUMERIC,
    most_used_tool TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_activities,
        COUNT(DISTINCT session_id) as unique_sessions,
        ROUND(
            (COUNT(CASE WHEN activity_type = 'error' THEN 1 END)::NUMERIC / COUNT(*)) * 100, 2
        ) as error_rate,
        ROUND(AVG(duration_ms), 2) as avg_response_time,
        (
            SELECT tool_name 
            FROM activity_logs 
            WHERE timestamp >= NOW() - (hours_back || ' hours')::INTERVAL
              AND tool_name IS NOT NULL
            GROUP BY tool_name 
            ORDER BY COUNT(*) DESC 
            LIMIT 1
        ) as most_used_tool
    FROM activity_logs
    WHERE timestamp >= NOW() - (hours_back || ' hours')::INTERVAL;
END;
$$;

-- Grant permissions for the views and functions
GRANT SELECT ON activity_log_stats TO authenticated;
GRANT SELECT ON session_stats TO authenticated;
GRANT EXECUTE ON FUNCTION get_activity_summary(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION cleanup_old_activity_logs() TO service_role;

-- Comments for documentation
COMMENT ON TABLE activity_logs IS 'Stores all MCP server activity logs for real-time monitoring';
COMMENT ON VIEW activity_log_stats IS 'Hourly statistics for activity logs over the last 24 hours';
COMMENT ON VIEW session_stats IS 'Session-level statistics showing user engagement patterns';
COMMENT ON FUNCTION get_activity_summary(INTEGER) IS 'Returns activity summary for the specified number of hours back';
COMMENT ON FUNCTION cleanup_old_activity_logs() IS 'Removes activity logs older than 30 days';