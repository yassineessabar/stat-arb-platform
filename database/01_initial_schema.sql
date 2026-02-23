-- Statistical Arbitrage Platform Database Schema
-- This creates all necessary tables for the trading platform

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table for authentication and user management
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'pro', 'enterprise'))
);

-- API Keys table for storing encrypted Binance credentials
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Default',
    encrypted_api_key TEXT NOT NULL,
    encrypted_secret_key TEXT NOT NULL,
    exchange TEXT DEFAULT 'binance' CHECK (exchange IN ('binance', 'bybit', 'okx')),
    is_testnet BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, name)
);

-- Strategy Deployments table
CREATE TABLE IF NOT EXISTS strategy_deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    process_id TEXT UNIQUE NOT NULL,
    strategy_name TEXT NOT NULL,
    trading_mode TEXT NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'stopped', 'paused', 'error')),

    -- Strategy Parameters
    symbol_1 TEXT NOT NULL,
    symbol_2 TEXT NOT NULL,
    lookback_period INTEGER DEFAULT 24,
    entry_z_score DECIMAL(5,2) DEFAULT 2.0,
    exit_z_score DECIMAL(5,2) DEFAULT 0.5,
    stop_loss_z_score DECIMAL(5,2) DEFAULT 3.0,
    position_size DECIMAL(15,2) DEFAULT 1000,
    max_positions INTEGER DEFAULT 3,
    rebalance_frequency INTEGER DEFAULT 5,

    -- Execution Details
    api_key_id UUID REFERENCES api_keys(id),
    system_pid INTEGER,
    config_file_path TEXT,
    log_file_path TEXT,

    -- Timestamps
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    stopped_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Performance Tracking
    total_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0,
    current_positions INTEGER DEFAULT 0
);

-- Positions table for tracking open and closed positions
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Position Details
    position_id TEXT NOT NULL, -- From strategy (e.g., "LONG_1771834110")
    symbol_1 TEXT NOT NULL,
    symbol_2 TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'closed', 'partial')),

    -- Entry Information
    entry_price_1 DECIMAL(15,6) NOT NULL,
    entry_price_2 DECIMAL(15,6) NOT NULL,
    entry_z_score DECIMAL(8,4) NOT NULL,
    position_size DECIMAL(15,2) NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Exit Information (nullable for open positions)
    exit_price_1 DECIMAL(15,6),
    exit_price_2 DECIMAL(15,6),
    exit_z_score DECIMAL(8,4),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_reason TEXT, -- 'mean_reversion', 'stop_loss', 'manual', 'emergency'

    -- P&L Tracking
    unrealized_pnl DECIMAL(15,2) DEFAULT 0,
    realized_pnl DECIMAL(15,2) DEFAULT 0,
    commission DECIMAL(15,6) DEFAULT 0,
    net_pnl DECIMAL(15,2) DEFAULT 0,

    -- Additional Data
    metadata JSONB DEFAULT '{}', -- For storing additional position data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique position IDs per deployment
    UNIQUE(deployment_id, position_id)
);

-- Trades table for detailed trade execution history
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    position_id UUID REFERENCES positions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Trade Details
    external_order_id TEXT, -- Binance order ID
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    trade_type TEXT DEFAULT 'market' CHECK (trade_type IN ('market', 'limit', 'stop')),

    -- Execution Details
    quantity DECIMAL(15,6) NOT NULL,
    price DECIMAL(15,6) NOT NULL,
    quote_quantity DECIMAL(15,2),
    commission DECIMAL(15,6) DEFAULT 0,
    commission_asset TEXT DEFAULT 'USDT',

    -- Timing
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- P&L Impact
    realized_pnl DECIMAL(15,2) DEFAULT 0,

    -- Additional Data
    slippage DECIMAL(8,4), -- In basis points
    is_maker BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Strategy Performance table for daily/hourly aggregated stats
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Time Period
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type TEXT DEFAULT 'daily' CHECK (period_type IN ('hourly', 'daily', 'weekly', 'monthly')),

    -- Performance Metrics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0,
    total_commission DECIMAL(15,6) DEFAULT 0,
    net_pnl DECIMAL(15,2) DEFAULT 0,

    -- Statistical Metrics
    win_rate DECIMAL(5,2) DEFAULT 0, -- Percentage
    avg_trade_pnl DECIMAL(15,2) DEFAULT 0,
    max_win DECIMAL(15,2) DEFAULT 0,
    max_loss DECIMAL(15,2) DEFAULT 0,
    profit_factor DECIMAL(8,4) DEFAULT 0,

    -- Risk Metrics
    max_drawdown DECIMAL(15,2) DEFAULT 0,
    sharpe_ratio DECIMAL(8,4) DEFAULT 0,
    sortino_ratio DECIMAL(8,4) DEFAULT 0,

    -- Position Metrics
    max_concurrent_positions INTEGER DEFAULT 0,
    avg_position_duration INTERVAL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique periods per deployment
    UNIQUE(deployment_id, period_start, period_type)
);

-- Market Data table for storing price history (optional, for backtesting)
CREATE TABLE IF NOT EXISTS market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL CHECK (interval IN ('1m', '5m', '15m', '1h', '4h', '1d')),

    -- OHLCV Data
    open_time TIMESTAMP WITH TIME ZONE NOT NULL,
    close_time TIMESTAMP WITH TIME ZONE NOT NULL,
    open_price DECIMAL(15,6) NOT NULL,
    high_price DECIMAL(15,6) NOT NULL,
    low_price DECIMAL(15,6) NOT NULL,
    close_price DECIMAL(15,6) NOT NULL,
    volume DECIMAL(20,6) NOT NULL,
    quote_volume DECIMAL(20,6),
    trade_count INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique data points
    UNIQUE(symbol, interval, open_time)
);

-- System Logs table for platform monitoring
CREATE TABLE IF NOT EXISTS system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES strategy_deployments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Log Details
    log_level TEXT DEFAULT 'info' CHECK (log_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    log_type TEXT DEFAULT 'strategy' CHECK (log_type IN ('strategy', 'api', 'risk', 'system', 'deployment')),
    message TEXT NOT NULL,

    -- Context Data
    context JSONB DEFAULT '{}',
    stack_trace TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategy_deployments_user_id ON strategy_deployments(user_id);
CREATE INDEX IF NOT EXISTS idx_strategy_deployments_status ON strategy_deployments(status);
CREATE INDEX IF NOT EXISTS idx_strategy_deployments_deployed_at ON strategy_deployments(deployed_at);

CREATE INDEX IF NOT EXISTS idx_positions_deployment_id ON positions(deployment_id);
CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time);

CREATE INDEX IF NOT EXISTS idx_trades_deployment_id ON trades(deployment_id);
CREATE INDEX IF NOT EXISTS idx_trades_position_id ON trades(position_id);
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_execution_time ON trades(execution_time);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_deployment_id ON strategy_performance(deployment_id);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_period ON strategy_performance(period_start, period_type);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_interval ON market_data(symbol, interval);
CREATE INDEX IF NOT EXISTS idx_market_data_open_time ON market_data(open_time);

CREATE INDEX IF NOT EXISTS idx_system_logs_deployment_id ON system_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_system_logs_log_level ON system_logs(log_level);

-- Create updated_at triggers for tables that need them
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Sample data insertion function
CREATE OR REPLACE FUNCTION insert_sample_user()
RETURNS UUID AS $$
DECLARE
    user_uuid UUID;
BEGIN
    INSERT INTO users (email, username, full_name)
    VALUES ('demo@statarib.com', 'demo_user', 'Demo User')
    RETURNING id INTO user_uuid;

    RETURN user_uuid;
END;
$$ LANGUAGE plpgsql;