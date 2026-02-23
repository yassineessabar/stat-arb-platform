import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function GET() {
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