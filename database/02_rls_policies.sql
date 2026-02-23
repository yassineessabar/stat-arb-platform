-- Row Level Security (RLS) Policies for Statistical Arbitrage Platform
-- This ensures users can only access their own data

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_logs ENABLE ROW LEVEL SECURITY;

-- Users table policies
CREATE POLICY "Users can view own profile" ON users
    FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = id);

-- API Keys table policies
CREATE POLICY "Users can manage own API keys" ON api_keys
    FOR ALL USING (auth.uid() = user_id);

-- Strategy Deployments table policies
CREATE POLICY "Users can manage own deployments" ON strategy_deployments
    FOR ALL USING (auth.uid() = user_id);

-- Positions table policies
CREATE POLICY "Users can view own positions" ON positions
    FOR ALL USING (auth.uid() = user_id);

-- Trades table policies
CREATE POLICY "Users can view own trades" ON trades
    FOR ALL USING (auth.uid() = user_id);

-- Strategy Performance table policies
CREATE POLICY "Users can view own performance" ON strategy_performance
    FOR ALL USING (auth.uid() = user_id);

-- Market Data table policies (public read-only)
CREATE POLICY "Market data is publicly readable" ON market_data
    FOR SELECT USING (true);

-- Only service role can insert market data
CREATE POLICY "Only service role can manage market data" ON market_data
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- System Logs table policies
CREATE POLICY "Users can view own logs" ON system_logs
    FOR SELECT USING (auth.uid() = user_id);

-- Service role can insert logs
CREATE POLICY "Service role can manage logs" ON system_logs
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

-- Create a function to get current user ID (helper for policies)
CREATE OR REPLACE FUNCTION auth.get_user_id()
RETURNS UUID AS $$
BEGIN
    RETURN auth.uid();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create a function to check if user owns deployment
CREATE OR REPLACE FUNCTION auth.user_owns_deployment(deployment_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM strategy_deployments
        WHERE id = deployment_uuid AND user_id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;