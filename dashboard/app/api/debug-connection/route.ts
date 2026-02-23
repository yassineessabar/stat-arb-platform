import { NextResponse } from 'next/server';

export async function GET() {
  const apiKey = process.env.BINANCE_TESTNET_API_KEY;
  const secretKey = process.env.BINANCE_TESTNET_API_SECRET;

  return NextResponse.json({
    hasApiKey: !!apiKey,
    hasSecretKey: !!secretKey,
    apiKeyPreview: apiKey ? `${apiKey.substring(0, 10)}...${apiKey.slice(-6)}` : 'MISSING',
    secretKeyPreview: secretKey ? `${secretKey.substring(0, 10)}...${secretKey.slice(-6)}` : 'MISSING',
    keyLengths: {
      apiKey: apiKey?.length || 0,
      secretKey: secretKey?.length || 0
    },
    timestamp: new Date().toISOString()
  });
}