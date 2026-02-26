// Binance Testnet API Client for real trading integration
import crypto from 'crypto';

interface BinanceCredentials {
  apiKey: string;
  secretKey: string;
  isLive?: boolean;
}

interface BinanceAccountInfo {
  makerCommission: number;
  takerCommission: number;
  buyerCommission: number;
  sellerCommission: number;
  canTrade: boolean;
  canWithdraw: boolean;
  canDeposit: boolean;
  balances: Array<{
    asset: string;
    free: string;
    locked: string;
  }>;
}

interface BinanceOrder {
  symbol: string;
  orderId: number;
  orderListId: number;
  clientOrderId: string;
  price: string;
  origQty: string;
  executedQty: string;
  cummulativeQuoteQty: string;
  status: string;
  timeInForce: string;
  type: string;
  side: string;
  stopPrice: string;
  icebergQty: string;
  time: number;
  updateTime: number;
  isWorking: boolean;
  origQuoteOrderQty: string;
}

export class BinanceTestnetClient {
  private baseUrl: string;
  private credentials: BinanceCredentials;

  constructor(credentials: BinanceCredentials) {
    // Use live API if isLive is true, otherwise use testnet
    this.baseUrl = credentials.isLive ? 'https://fapi.binance.com' : 'https://demo-fapi.binance.com';
    this.credentials = credentials;
  }

  // Create signed request signature
  private createSignature(queryString: string): string {
    return crypto
      .createHmac('sha256', this.credentials.secretKey)
      .update(queryString)
      .digest('hex');
  }

  // Create authenticated request headers
  private getHeaders(): HeadersInit {
    return {
      'Content-Type': 'application/json',
      'X-MBX-APIKEY': this.credentials.apiKey,
    };
  }

  // Make authenticated API request
  private async makeRequest(endpoint: string, params: Record<string, any> = {}, method: string = 'GET'): Promise<any> {
    // Add timestamp for authentication
    const timestamp = Date.now();

    // Build query string manually to ensure exact format
    const queryParams: string[] = [];

    // Add all params except timestamp first
    Object.keys(params).forEach(key => {
      queryParams.push(`${key}=${params[key]}`);
    });

    // Add timestamp last
    queryParams.push(`timestamp=${timestamp}`);

    // Join to create query string
    const queryString = queryParams.join('&');

    // Create signature
    const signature = this.createSignature(queryString);

    // Full URL with signature
    const url = `${this.baseUrl}${endpoint}?${queryString}&signature=${signature}`;

    try {
      const response = await fetch(url, {
        method,
        headers: this.getHeaders(),
        signal: AbortSignal.timeout(10000),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Binance API Error (${response.status}): ${errorText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Binance API request failed:', error);
      throw error;
    }
  }

  // Test API connectivity and permissions
  async testConnection(): Promise<{ connected: boolean; latency?: number; error?: string; account?: any }> {
    const startTime = Date.now();

    try {
      // Test basic connectivity first
      const pingResponse = await fetch(`${this.baseUrl}/fapi/v1/ping`, {
        signal: AbortSignal.timeout(5000),
      });

      if (!pingResponse.ok) {
        throw new Error('Binance testnet not reachable');
      }

      // Test authenticated endpoint - futures account has different structure
      const accountInfo = await this.getAccountInfo();
      const latency = Date.now() - startTime;

      // Futures account response structure
      return {
        connected: true,
        latency,
        account: {
          canTrade: accountInfo.canTrade !== false,
          totalInitialMargin: accountInfo.totalInitialMargin || '0',
          totalMaintMargin: accountInfo.totalMaintMargin || '0',
          totalWalletBalance: accountInfo.totalWalletBalance || '0',
          totalUnrealizedProfit: accountInfo.totalUnrealizedProfit || '0',
          totalMarginBalance: accountInfo.totalMarginBalance || '0',
          positionsCount: accountInfo.positions ? accountInfo.positions.length : 0,
          assetsCount: accountInfo.assets ? accountInfo.assets.length : 0
        }
      };
    } catch (error) {
      const latency = Date.now() - startTime;
      return {
        connected: false,
        latency,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }

  // Get account information
  async getAccountInfo(): Promise<BinanceAccountInfo> {
    return this.makeRequest('/fapi/v2/account');
  }

  // Get account balances (non-zero only) - Futures account structure
  async getBalances(): Promise<Array<{ asset: string; free: number; locked: number; total: number }>> {
    const accountInfo = await this.getAccountInfo();

    // Futures account uses 'assets' array instead of 'balances'
    if (accountInfo.assets) {
      return accountInfo.assets
        .filter((asset: any) => parseFloat(asset.walletBalance) > 0)
        .map((asset: any) => ({
          asset: asset.asset,
          free: parseFloat(asset.availableBalance || asset.walletBalance),
          locked: parseFloat(asset.walletBalance) - parseFloat(asset.availableBalance || asset.walletBalance),
          total: parseFloat(asset.walletBalance)
        }));
    }

    // Fallback to spot structure if needed
    if (accountInfo.balances) {
      return accountInfo.balances
        .filter(balance => parseFloat(balance.free) > 0 || parseFloat(balance.locked) > 0)
        .map(balance => ({
          asset: balance.asset,
          free: parseFloat(balance.free),
          locked: parseFloat(balance.locked),
          total: parseFloat(balance.free) + parseFloat(balance.locked)
        }));
    }

    return [];
  }

  // Get open orders
  async getOpenOrders(symbol?: string): Promise<BinanceOrder[]> {
    const params = symbol ? { symbol } : {};
    return this.makeRequest('/fapi/v1/openOrders', params);
  }

  // Get recent trades
  async getMyTrades(symbol: string, limit: number = 10): Promise<any[]> {
    return this.makeRequest('/fapi/v1/userTrades', { symbol, limit });
  }

  // Place a futures order
  async placeOrder(params: {
    symbol: string;
    side: 'BUY' | 'SELL';
    type: 'MARKET' | 'LIMIT';
    quantity: number;
    price?: number;
    timeInForce?: 'GTC' | 'IOC' | 'FOK';
  }): Promise<any> {
    const orderParams: any = {
      symbol: params.symbol,
      side: params.side,
      type: params.type,
      quantity: params.quantity
    };

    if (params.type === 'LIMIT' && params.price) {
      orderParams.price = params.price;
      orderParams.timeInForce = params.timeInForce || 'GTC';
    }

    return this.makeRequest('/fapi/v1/order', orderParams, 'POST');
  }

  // Close a position (market order in opposite direction)
  async closePosition(symbol: string): Promise<any> {
    const accountInfo = await this.getAccountInfo();
    const position = accountInfo.positions?.find((p: any) =>
      p.symbol === symbol && parseFloat(p.positionAmt) !== 0
    );

    if (!position) {
      throw new Error(`No open position for ${symbol}`);
    }

    const positionAmt = parseFloat(position.positionAmt);
    return this.placeOrder({
      symbol: symbol,
      side: positionAmt > 0 ? 'SELL' : 'BUY',
      type: 'MARKET',
      quantity: Math.abs(positionAmt)
    });
  }

  // Get exchange info for trading pairs
  async getExchangeInfo(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/fapi/v1/exchangeInfo`, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch exchange info');
    }

    return response.json();
  }

  // Get 24hr ticker statistics
  async get24hrStats(symbol?: string): Promise<any> {
    const url = symbol
      ? `${this.baseUrl}/fapi/v1/ticker/24hr?symbol=${symbol}`
      : `${this.baseUrl}/fapi/v1/ticker/24hr`;

    const response = await fetch(url, {
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch ticker stats');
    }

    return response.json();
  }
}