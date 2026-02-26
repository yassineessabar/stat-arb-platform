import { NextResponse, NextRequest } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET(request: NextRequest) {
  try {
    // Check query parameter for trading mode (paper = testnet, live = live API)
    const { searchParams } = new URL(request.url);
    const tradingMode = searchParams.get('mode') || 'paper';
    const isLive = tradingMode === 'live';

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

    // Return empty trades - will be populated when real trades are made
    // In production, would fetch from /fapi/v1/userTrades for each symbol

    return NextResponse.json({
      trades: []
    });

  } catch (error) {
    console.error('Binance trades fetch error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to fetch trades'
    }, { status: 500 });
  }
}