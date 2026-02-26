import { NextResponse } from 'next/server';
import { BinanceTestnetClient } from '@/lib/binance-client';
import crypto from 'crypto';

export async function GET(request: Request) {
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
        connected: false,
        error: `Binance ${isLive ? 'Live' : 'Testnet'} API credentials not configured`
      });
    }

    const binanceClient = new BinanceTestnetClient({
      apiKey,
      secretKey,
      isLive
    });

    const result = await binanceClient.testConnection();
    return NextResponse.json(result);

  } catch (error) {
    console.error('Binance test connection error:', error);
    return NextResponse.json({
      connected: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { apiKey, secretKey, testnet } = body;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        connected: false,
        error: 'API credentials required'
      });
    }

    // Test connection with provided credentials
    const baseUrl = testnet
      ? 'https://testnet.binancefuture.com'
      : 'https://fapi.binance.com';

    const timestamp = Date.now();
    const queryString = `timestamp=${timestamp}`;

    // Generate signature
    const signature = crypto
      .createHmac('sha256', secretKey)
      .update(queryString)
      .digest('hex');

    // Test account endpoint
    const response = await fetch(`${baseUrl}/fapi/v2/account?${queryString}&signature=${signature}`, {
      headers: {
        'X-MBX-APIKEY': apiKey
      }
    });

    if (response.ok) {
      const data = await response.json();

      // Store credentials in environment for subsequent requests
      process.env.BINANCE_TESTNET_API_KEY = apiKey;
      process.env.BINANCE_TESTNET_API_SECRET = secretKey;

      return NextResponse.json({
        connected: true,
        testnet,
        totalBalance: data.totalWalletBalance || 0,
        availableBalance: data.availableBalance || 0
      });
    } else {
      const error = await response.text();
      return NextResponse.json({
        connected: false,
        error: `Connection failed: ${error}`
      });
    }

  } catch (error) {
    console.error('Connection test error:', error);
    return NextResponse.json({
      connected: false,
      error: error instanceof Error ? error.message : 'Connection test failed'
    });
  }
}