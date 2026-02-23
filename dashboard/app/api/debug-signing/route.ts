import { NextResponse } from 'next/server';
import crypto from 'crypto';

export async function GET() {
  try {
    const apiKey = process.env.BINANCE_TESTNET_API_KEY;
    const secretKey = process.env.BINANCE_TESTNET_API_SECRET;

    if (!apiKey || !secretKey) {
      return NextResponse.json({
        error: 'Credentials not found',
        apiKeyExists: !!apiKey,
        secretKeyExists: !!secretKey
      });
    }

    // Test signing logic
    const timestamp = Date.now();
    const queryString = `timestamp=${timestamp}`;
    const signature = crypto
      .createHmac('sha256', secretKey)
      .update(queryString)
      .digest('hex');

    // Try to make the same request as the working curl
    const url = `https://demo-fapi.binance.com/fapi/v2/account?${queryString}&signature=${signature}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-MBX-APIKEY': apiKey,
        'Content-Type': 'application/json'
      }
    });

    const responseText = await response.text();
    let responseData;
    try {
      responseData = JSON.parse(responseText);
    } catch {
      responseData = responseText;
    }

    return NextResponse.json({
      success: response.ok,
      status: response.status,
      timestamp,
      queryString,
      signature,
      apiKeyPrefix: apiKey.substring(0, 10) + '...',
      secretKeyPrefix: secretKey.substring(0, 10) + '...',
      url,
      response: responseData
    });

  } catch (error) {
    console.error('Debug signing error:', error);
    return NextResponse.json({
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined
    }, { status: 500 });
  }
}