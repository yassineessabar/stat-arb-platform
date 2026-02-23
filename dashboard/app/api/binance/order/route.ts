import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';

export async function POST(request: Request) {
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

    const body = await request.json();
    const { symbol, side, type, quantity, price, timeInForce } = body;

    // Validate required parameters
    if (!symbol || !side || !type || !quantity) {
      return NextResponse.json({
        error: 'Missing required parameters: symbol, side, type, quantity'
      }, { status: 400 });
    }

    // Place the order
    const order = await binanceClient.placeOrder({
      symbol,
      side,
      type,
      quantity,
      price,
      timeInForce
    });

    return NextResponse.json({
      success: true,
      order
    });

  } catch (error) {
    console.error('Order placement error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Failed to place order'
    }, { status: 500 });
  }
}