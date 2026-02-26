import { NextResponse, NextRequest } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET(request: NextRequest) {
  try {
    // Check query parameter for trading mode (paper = testnet, live = live API)
    const { searchParams } = new URL(request.url);
    const tradingMode = searchParams.get('mode') || 'paper';
    const isLive = tradingMode === 'live';
    const limit = parseInt(searchParams.get('limit') || '500'); // Increased default
    const symbol = searchParams.get('symbol') || ''; // Optional specific symbol
    const getAllHistory = searchParams.get('all') === 'true'; // Get all history flag

    const apiKey = isLive
      ? process.env.BINANCE_LIVE_API_KEY
      : process.env.BINANCE_TESTNET_API_KEY;
    const secretKey = isLive
      ? process.env.BINANCE_LIVE_API_SECRET
      : process.env.BINANCE_TESTNET_API_SECRET;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        error: `Binance ${isLive ? 'Live' : 'Testnet'} API credentials not configured`
      }, { status: 401 });
    }

    const binanceClient = new BinanceTestnetClient({
      apiKey,
      secretKey,
      isLive
    });

    // Fetch actual trade history from Binance Futures
    // Get account trades for all symbols or specific symbol
    const allTrades: any[] = [];

    if (symbol) {
      // Fetch trades for specific symbol
      const trades = await binanceClient.getUserTrades(symbol, limit);
      allTrades.push(...trades);
    } else {
      // First, get account info to see which symbols have positions or history
      const accountInfo = await binanceClient.getAccountInfo();

      // Get unique symbols from positions
      const tradedSymbols = new Set<string>();

      if (accountInfo.positions) {
        accountInfo.positions.forEach((pos: any) => {
          if (parseFloat(pos.positionAmt || '0') !== 0 || parseFloat(pos.realizedPnl || '0') !== 0) {
            tradedSymbols.add(pos.symbol);
          }
        });
      }

      // Also try common symbols if no positions found or if getting all history
      if (tradedSymbols.size === 0 || getAllHistory) {
        ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT'].forEach(s => tradedSymbols.add(s));
      }

      console.log(`Checking trades for symbols: ${Array.from(tradedSymbols).join(', ')}`);

      // Fetch trades for each symbol
      for (const sym of tradedSymbols) {
        try {
          // Get more trades per symbol when fetching all history
          const tradesPerSymbol = getAllHistory ? 1000 : 100;
          const trades = await binanceClient.getUserTrades(sym, tradesPerSymbol);
          if (trades && trades.length > 0) {
            console.log(`Found ${trades.length} trades for ${sym}`);
            allTrades.push(...trades);
          }
        } catch (err: any) {
          // Only log if it's not a "no trades" error
          if (!err.message?.includes('Invalid symbol')) {
            console.log(`No trades for ${sym}`);
          }
        }
      }
    }

    console.log(`Total trades fetched: ${allTrades.length}`);

    // Sort trades by time (most recent first)
    allTrades.sort((a, b) => (b.time || 0) - (a.time || 0));

    // Format trades for frontend
    const formattedTrades = allTrades.slice(0, limit).map(trade => ({
      symbol: trade.symbol,
      orderId: trade.orderId,
      side: trade.side,
      price: parseFloat(trade.price || '0'),
      qty: parseFloat(trade.qty || '0'),
      quoteQty: parseFloat(trade.quoteQty || '0'),
      realizedPnl: parseFloat(trade.realizedPnl || '0'),
      commission: parseFloat(trade.commission || '0'),
      commissionAsset: trade.commissionAsset,
      time: trade.time,
      positionSide: trade.positionSide,
      buyer: trade.buyer,
      maker: trade.maker
    }));

    return NextResponse.json({
      trades: formattedTrades,
      count: formattedTrades.length
    });

  } catch (error) {
    console.error('Binance trades fetch error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch trades',
      trades: [] // Return empty array on error
    }, { status: 200 }); // Return 200 to avoid breaking frontend
  }
}