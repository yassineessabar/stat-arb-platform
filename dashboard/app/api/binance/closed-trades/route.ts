import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET(request: Request) {
  try {
    const apiKey = process.env.BINANCE_TESTNET_API_KEY;
    const secretKey = process.env.BINANCE_TESTNET_API_SECRET;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        error: 'Binance API credentials not configured'
      }, { status: 401 });
    }

    const binanceClient = new BinanceTestnetClient({
      apiKey,
      secretKey
    });

    // Get URL parameters
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get('limit') || '50');

    // Fetch user trades from multiple symbols
    // In production, you'd want to fetch from all traded symbols
    const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']; // Common symbols
    const allTrades = [];

    for (const symbol of symbols) {
      try {
        const trades = await binanceClient.makeRequest('/fapi/v1/userTrades', {
          symbol,
          limit: Math.min(limit, 100)
        });

        if (Array.isArray(trades)) {
          allTrades.push(...trades);
        }
      } catch (error) {
        // Symbol might not have trades, continue
        console.log(`No trades for ${symbol}`);
      }
    }

    // Process and format trades
    const processedTrades = allTrades.map(trade => {
      const qty = parseFloat(trade.qty || '0');
      const price = parseFloat(trade.price || '0');
      const realizedPnl = parseFloat(trade.realizedPnl || '0');
      const commission = parseFloat(trade.commission || '0');
      const quoteQty = parseFloat(trade.quoteQty || '0');

      // Calculate net P&L (after commission)
      const netPnl = realizedPnl - commission;

      return {
        id: trade.id,
        orderId: trade.orderId,
        symbol: trade.symbol,
        side: trade.side,
        positionSide: trade.positionSide || 'BOTH',
        price: price,
        qty: qty,
        quoteQty: quoteQty,
        realizedPnl: realizedPnl,
        commission: commission,
        commissionAsset: trade.commissionAsset || 'USDT',
        netPnl: netPnl,
        time: trade.time,
        buyer: trade.buyer,
        maker: trade.maker
      };
    });

    // Sort by time (most recent first)
    processedTrades.sort((a, b) => b.time - a.time);

    // Calculate summary statistics
    const totalRealizedPnl = processedTrades.reduce((sum, trade) => sum + trade.realizedPnl, 0);
    const totalCommission = processedTrades.reduce((sum, trade) => sum + trade.commission, 0);
    const totalNetPnl = processedTrades.reduce((sum, trade) => sum + trade.netPnl, 0);

    // Group trades by position (for closed positions view)
    const closedPositions = groupTradesByPosition(processedTrades);

    return NextResponse.json({
      trades: processedTrades.slice(0, limit),
      closedPositions: closedPositions.slice(0, 20), // Last 20 closed positions
      summary: {
        totalTrades: processedTrades.length,
        totalRealizedPnl,
        totalCommission,
        totalNetPnl,
        avgCommissionRate: processedTrades.length > 0
          ? (totalCommission / processedTrades.reduce((sum, t) => sum + t.quoteQty, 0)) * 100
          : 0
      }
    });

  } catch (error) {
    console.error('Closed trades fetch error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch closed trades'
    }, { status: 500 });
  }
}

// Group individual trades into closed positions
function groupTradesByPosition(trades: any[]): any[] {
  const positions: Map<string, any> = new Map();

  trades.forEach(trade => {
    const key = `${trade.symbol}-${trade.orderId}`;

    if (!positions.has(key)) {
      positions.set(key, {
        symbol: trade.symbol,
        entryTime: trade.time,
        exitTime: trade.time,
        side: trade.side,
        totalQty: 0,
        avgEntryPrice: 0,
        avgExitPrice: 0,
        realizedPnl: 0,
        commission: 0,
        netPnl: 0,
        trades: []
      });
    }

    const position = positions.get(key);
    position.trades.push(trade);
    position.totalQty += trade.qty;
    position.realizedPnl += trade.realizedPnl;
    position.commission += trade.commission;
    position.netPnl += trade.netPnl;
    position.exitTime = Math.max(position.exitTime, trade.time);
  });

  // Calculate averages and return as array
  return Array.from(positions.values()).map(pos => {
    const totalValue = pos.trades.reduce((sum: number, t: any) => sum + (t.qty * t.price), 0);
    pos.avgPrice = pos.totalQty > 0 ? totalValue / pos.totalQty : 0;
    return pos;
  });
}