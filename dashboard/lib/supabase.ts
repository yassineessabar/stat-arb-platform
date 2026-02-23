import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Database Types
export interface User {
  id: string
  email: string
  username?: string
  full_name?: string
  created_at: string
  is_active: boolean
}

export interface StrategyDeployment {
  id: string
  user_id: string
  process_id: string
  strategy_name: string
  trading_mode: 'paper' | 'live'
  status: 'running' | 'stopped' | 'paused' | 'error'

  // Strategy Parameters
  symbol_1: string
  symbol_2: string
  entry_z_score: number
  exit_z_score: number
  position_size: number
  max_positions: number

  // Execution Details
  deployed_at: string
  stopped_at?: string
  total_trades: number
  total_pnl: number
}

export interface Position {
  id: string
  deployment_id: string
  user_id: string

  // Position Details
  position_id: string
  symbol_1: string
  symbol_2: string
  direction: 'LONG' | 'SHORT'
  status: 'open' | 'closed'

  // Entry Information
  entry_price_1: number
  entry_price_2: number
  entry_z_score: number
  position_size: number
  entry_time: string

  // Exit Information
  exit_price_1?: number
  exit_price_2?: number
  exit_z_score?: number
  exit_time?: string
  exit_reason?: string

  // P&L Tracking
  realized_pnl: number
  net_pnl: number

  created_at: string
}

export interface Trade {
  id: string
  deployment_id: string
  position_id: string
  user_id: string

  // Trade Details
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  commission: number

  // Timing
  execution_time: string
  realized_pnl: number

  created_at: string
}

export interface SystemLog {
  id: string
  deployment_id?: string
  user_id?: string

  log_level: string
  log_type: string
  message: string
  created_at: string
}

// Database operations
export class DatabaseService {
  // Strategy Deployments
  static async createDeployment(deployment: Omit<StrategyDeployment, 'id' | 'user_id' | 'deployed_at' | 'total_trades' | 'total_pnl'>) {
    const { data, error } = await supabase
      .from('strategy_deployments')
      .insert([deployment])
      .select()

    return { data: data?.[0], error }
  }

  static async getActiveDeployments() {
    const { data, error } = await supabase
      .from('strategy_deployments')
      .select('*')
      .eq('status', 'running')
      .order('deployed_at', { ascending: false })

    return { data, error }
  }

  static async stopDeployment(processId: string) {
    const { data, error } = await supabase
      .from('strategy_deployments')
      .update({ status: 'stopped', stopped_at: new Date().toISOString() })
      .eq('process_id', processId)
      .select()

    return { data: data?.[0], error }
  }

  // Positions
  static async createPosition(position: Omit<Position, 'id' | 'user_id' | 'created_at'>) {
    const { data, error } = await supabase
      .from('positions')
      .insert([position])
      .select()

    return { data: data?.[0], error }
  }

  static async getOpenPositions(deploymentId: string) {
    const { data, error } = await supabase
      .from('positions')
      .select('*')
      .eq('deployment_id', deploymentId)
      .eq('status', 'open')
      .order('entry_time', { ascending: false })

    return { data, error }
  }

  static async closePosition(positionId: string, exitData: {
    exit_price_1: number
    exit_price_2: number
    exit_z_score: number
    exit_reason: string
    realized_pnl: number
    net_pnl: number
  }) {
    const { data, error } = await supabase
      .from('positions')
      .update({
        ...exitData,
        status: 'closed',
        exit_time: new Date().toISOString()
      })
      .eq('position_id', positionId)
      .select()

    return { data: data?.[0], error }
  }

  // Trades
  static async createTrade(trade: Omit<Trade, 'id' | 'user_id' | 'created_at'>) {
    const { data, error } = await supabase
      .from('trades')
      .insert([trade])
      .select()

    return { data: data?.[0], error }
  }

  static async getTradeHistory(deploymentId: string, limit = 100) {
    const { data, error } = await supabase
      .from('trades')
      .select('*')
      .eq('deployment_id', deploymentId)
      .order('execution_time', { ascending: false })
      .limit(limit)

    return { data, error }
  }

  // System Logs
  static async createLog(log: Omit<SystemLog, 'id' | 'created_at'>) {
    const { data, error } = await supabase
      .from('system_logs')
      .insert([log])
      .select()

    return { data: data?.[0], error }
  }

  static async getLogs(deploymentId: string, limit = 100) {
    const { data, error } = await supabase
      .from('system_logs')
      .select('*')
      .eq('deployment_id', deploymentId)
      .order('created_at', { ascending: false })
      .limit(limit)

    return { data, error }
  }

  // Performance Analytics
  static async getPerformanceMetrics(deploymentId: string) {
    // Get total trades
    const { data: trades } = await supabase
      .from('trades')
      .select('realized_pnl')
      .eq('deployment_id', deploymentId)

    // Get open positions
    const { data: openPositions } = await supabase
      .from('positions')
      .select('*')
      .eq('deployment_id', deploymentId)
      .eq('status', 'open')

    // Get closed positions
    const { data: closedPositions } = await supabase
      .from('positions')
      .select('realized_pnl, net_pnl')
      .eq('deployment_id', deploymentId)
      .eq('status', 'closed')

    const totalTrades = trades?.length || 0
    const totalPnl = closedPositions?.reduce((sum, pos) => sum + pos.net_pnl, 0) || 0
    const openPositionsCount = openPositions?.length || 0

    return {
      totalTrades,
      totalPnl,
      openPositionsCount,
      winningTrades: closedPositions?.filter(p => p.net_pnl > 0).length || 0,
      losingTrades: closedPositions?.filter(p => p.net_pnl < 0).length || 0,
      winRate: closedPositions?.length ?
        (closedPositions.filter(p => p.net_pnl > 0).length / closedPositions.length) * 100 : 0
    }
  }
}