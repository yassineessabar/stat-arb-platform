#!/usr/bin/env python3
"""
Close All Positions on Binance Futures Testnet
"""

import requests
import hmac
import hashlib
import time
from urllib.parse import urlencode
import json

API_KEY = "UigdoIwOPHWFIvkjhrGvL1aqJwd4p88J7IQhkfMVrD8zmvjBCD0rhXdWqlAjMr5I"
API_SECRET = "XMg47ARX09YFUel64EdMxngYcXSz2iuyi81uATO7jsshhos9NIh3XwvSRYwovvKN"
BASE_URL = "https://testnet.binancefuture.com"

def sign_request(params):
    """Sign request with HMAC SHA256"""
    query_string = urlencode(params)
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    return params

def get_positions():
    """Get all positions with non-zero amounts"""
    params = {'timestamp': int(time.time() * 1000)}
    params = sign_request(params)

    response = requests.get(
        f"{BASE_URL}/fapi/v2/account",
        params=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        account = response.json()
        positions = []

        if 'positions' in account:
            for pos in account['positions']:
                amt = float(pos.get('positionAmt', 0))
                if amt != 0:
                    positions.append({
                        'symbol': pos['symbol'],
                        'amount': amt,
                        'side': 'LONG' if amt > 0 else 'SHORT',
                        'entry_price': pos.get('entryPrice', 0),
                        'unrealized_pnl': pos.get('unrealizedProfit', 0)
                    })
        return positions
    return []

def close_position(symbol, amount):
    """Close a position by placing opposite market order"""
    # Determine side (opposite of position)
    side = 'SELL' if amount > 0 else 'BUY'
    quantity = abs(amount)

    # Get symbol precision
    precisions = {
        'BTCUSDT': 3,
        'ETHUSDT': 3,
        'BNBUSDT': 2,
    }
    precision = precisions.get(symbol, 3)

    params = {
        'symbol': symbol,
        'side': side,
        'type': 'MARKET',
        'quantity': f"{quantity:.{precision}f}",
        'timestamp': int(time.time() * 1000)
    }

    params = sign_request(params)

    response = requests.post(
        f"{BASE_URL}/fapi/v1/order",
        data=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        order = response.json()
        print(f"✅ Closed {symbol}: {side} {quantity:.{precision}f}")
        print(f"   Order ID: {order['orderId']}")
        return True
    else:
        print(f"❌ Failed to close {symbol}: {response.text}")
        return False

def cancel_all_orders():
    """Cancel all open orders"""
    params = {'timestamp': int(time.time() * 1000)}
    params = sign_request(params)

    # Get all open orders
    response = requests.get(
        f"{BASE_URL}/fapi/v1/openOrders",
        params=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        orders = response.json()
        if orders:
            print(f"\n📋 Found {len(orders)} open orders to cancel")
            for order in orders:
                cancel_params = {
                    'symbol': order['symbol'],
                    'orderId': order['orderId'],
                    'timestamp': int(time.time() * 1000)
                }
                cancel_params = sign_request(cancel_params)

                cancel_response = requests.delete(
                    f"{BASE_URL}/fapi/v1/order",
                    params=cancel_params,
                    headers={'X-MBX-APIKEY': API_KEY}
                )

                if cancel_response.status_code == 200:
                    print(f"  ✅ Cancelled order {order['orderId']} for {order['symbol']}")
                else:
                    print(f"  ❌ Failed to cancel order {order['orderId']}")
        else:
            print("\n✅ No open orders to cancel")
    else:
        print(f"❌ Failed to get open orders: {response.text}")

def main():
    print("=" * 60)
    print("🧹 CLOSING ALL POSITIONS ON BINANCE FUTURES TESTNET")
    print("=" * 60)

    # First, cancel all open orders
    print("\n1️⃣ CANCELLING OPEN ORDERS...")
    cancel_all_orders()

    # Get current positions
    print("\n2️⃣ GETTING CURRENT POSITIONS...")
    positions = get_positions()

    if not positions:
        print("✅ No positions to close")
        return

    print(f"\n📊 Found {len(positions)} positions to close:")
    for pos in positions:
        print(f"  {pos['symbol']}: {pos['amount']} ({pos['side']}) | PnL: ${float(pos['unrealized_pnl']):.2f}")

    # Auto-confirm for automation
    print("\n⚠️  WARNING: Closing ALL positions!")
    print("Auto-confirming in 3 seconds...")
    time.sleep(3)

    # Close all positions
    print("\n3️⃣ CLOSING POSITIONS...")
    success_count = 0
    for pos in positions:
        if close_position(pos['symbol'], pos['amount']):
            success_count += 1
        time.sleep(0.5)  # Small delay between orders

    print(f"\n✅ Successfully closed {success_count}/{len(positions)} positions")

    # Final check
    print("\n4️⃣ FINAL CHECK...")
    time.sleep(2)  # Wait for orders to settle
    final_positions = get_positions()

    if not final_positions:
        print("✅ All positions closed successfully!")
    else:
        print(f"⚠️  {len(final_positions)} positions still open:")
        for pos in final_positions:
            print(f"  {pos['symbol']}: {pos['amount']}")

if __name__ == "__main__":
    main()