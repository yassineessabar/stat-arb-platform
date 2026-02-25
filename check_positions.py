#!/usr/bin/env python3
"""
Check Binance Futures Testnet Positions and Orders
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

def get_account():
    """Get account info"""
    params = {'timestamp': int(time.time() * 1000)}
    params = sign_request(params)

    response = requests.get(
        f"{BASE_URL}/fapi/v2/account",
        params=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        account = response.json()
        print("=" * 60)
        print("ACCOUNT INFO")
        print("=" * 60)
        print(f"Total Balance: {account.get('totalWalletBalance', '0')} USDT")
        print(f"Available Balance: {account.get('availableBalance', '0')} USDT")
        print(f"Total Unrealized PnL: {account.get('totalUnrealizedProfit', '0')} USDT")
        print(f"Total Margin Used: {account.get('totalMarginBalance', '0')} USDT")

        # Show positions with non-zero amounts
        if 'positions' in account:
            active_positions = [p for p in account['positions'] if float(p.get('positionAmt', 0)) != 0]
            if active_positions:
                print("\n" + "=" * 60)
                print("ACTIVE POSITIONS")
                print("=" * 60)
                for pos in active_positions:
                    print(f"\n{pos['symbol']}:")
                    print(f"  Amount: {pos['positionAmt']}")
                    print(f"  Entry Price: {pos.get('entryPrice', 'N/A')}")
                    print(f"  Mark Price: {pos.get('markPrice', 'N/A')}")
                    print(f"  Unrealized PnL: {pos.get('unrealizedProfit', 'N/A')}")
            else:
                print("\n✅ No active positions")
    else:
        print(f"Error: {response.text}")

def get_open_orders():
    """Get open orders"""
    params = {'timestamp': int(time.time() * 1000)}
    params = sign_request(params)

    response = requests.get(
        f"{BASE_URL}/fapi/v1/openOrders",
        params=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        orders = response.json()
        print("\n" + "=" * 60)
        print("OPEN ORDERS")
        print("=" * 60)
        if orders:
            for order in orders:
                print(f"\n{order['symbol']}:")
                print(f"  Order ID: {order['orderId']}")
                print(f"  Side: {order['side']}")
                print(f"  Type: {order['type']}")
                print(f"  Quantity: {order['origQty']}")
                print(f"  Price: {order.get('price', 'MARKET')}")
                print(f"  Status: {order['status']}")
        else:
            print("✅ No open orders")
    else:
        print(f"Error: {response.text}")

def get_order_history():
    """Get recent order history"""
    params = {
        'timestamp': int(time.time() * 1000),
        'limit': 10
    }
    params = sign_request(params)

    response = requests.get(
        f"{BASE_URL}/fapi/v1/allOrders",
        params=params,
        headers={'X-MBX-APIKEY': API_KEY}
    )

    if response.status_code == 200:
        orders = response.json()
        print("\n" + "=" * 60)
        print("RECENT ORDER HISTORY (Last 10)")
        print("=" * 60)
        if orders:
            # Get orders for our symbols
            our_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
            relevant_orders = [o for o in orders if o['symbol'] in our_symbols]

            if relevant_orders:
                for order in relevant_orders[-10:]:  # Last 10 orders
                    print(f"\n{order['symbol']}:")
                    print(f"  Order ID: {order['orderId']}")
                    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(order['time']/1000))}")
                    print(f"  Side: {order['side']}")
                    print(f"  Quantity: {order['origQty']}")
                    print(f"  Executed Qty: {order.get('executedQty', '0')}")
                    print(f"  Status: {order['status']}")
                    print(f"  Type: {order['type']}")
            else:
                print("No recent orders for BTC, ETH, or BNB")
        else:
            print("No order history found")
    else:
        print(f"Error: {response.text}")

def check_specific_order(order_id):
    """Check a specific order by ID"""
    params = {
        'orderId': order_id,
        'symbol': 'BTCUSDT',  # Try each symbol
        'timestamp': int(time.time() * 1000)
    }

    for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
        params['symbol'] = symbol
        signed_params = sign_request(params.copy())

        response = requests.get(
            f"{BASE_URL}/fapi/v1/order",
            params=signed_params,
            headers={'X-MBX-APIKEY': API_KEY}
        )

        if response.status_code == 200:
            order = response.json()
            print(f"\nFound Order {order_id} in {symbol}:")
            print(f"  Status: {order['status']}")
            print(f"  Executed Qty: {order.get('executedQty', '0')}")
            print(f"  Side: {order['side']}")
            return

    print(f"Order {order_id} not found")

if __name__ == "__main__":
    print("\n🔍 CHECKING BINANCE FUTURES TESTNET STATUS\n")

    get_account()
    get_open_orders()
    get_order_history()

    # Check specific orders from your bot
    print("\n" + "=" * 60)
    print("CHECKING SPECIFIC ORDERS FROM BOT")
    print("=" * 60)
    check_specific_order(12547887792)  # BTC order
    check_specific_order(8430110137)   # ETH order
    check_specific_order(1274317768)   # BNB order