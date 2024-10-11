import time
import hmac
import hashlib
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, unquote_plus
from cryptography.hazmat.primitives.asymmetric import ed25519

# Replace with your API Key and Secret Key provided by CoinSwitch Kuber
api_key = ""
secret_key = ""

# Trading parameters
symbols = [
    "BTC/INR",
    "ETH/INR",
]
quantityMap = {
    "BTC/INR":0.0001,
     "ETH/INR":0.001
}

# Positions dictionary to keep track of open positions
positions = {}

# Base URL for API endpoints
BASE_URL = "https://coinswitch.co"

# Function to create the signature required for authentication
def get_signature(method, endpoint, params, epoch_time):
    if method == "GET" and params:
        query_string = urlencode(params)
        unquote_query_string = unquote_plus(query_string)
        signature_msg = method + endpoint + '?' + unquote_query_string + str(epoch_time)
    else:
        signature_msg = method + endpoint + str(epoch_time)

    request_string = signature_msg.encode('utf-8')
    secret_key_bytes = bytes.fromhex(secret_key)
    secret_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
    signature_bytes = secret_key_obj.sign(request_string)
    signature = signature_bytes.hex()
    return signature

# Function to make API requests
def make_request(method, endpoint, params=None, data=None):
    if params is None:
        params = {}
    if data is None:
        data = {}

    epoch_time = str(int(time.time() * 1000))
    signature = get_signature(method, endpoint, params, epoch_time)

    url = BASE_URL + endpoint

    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-SIGNATURE': signature,
        'X-AUTH-APIKEY': api_key,
        'X-AUTH-EPOCH': epoch_time
    }

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=data)
        else:
            print(f"Unsupported HTTP method: {method}")
            return None

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

# Function to get historical data for a symbol
def get_historical_data(symbol, exchange='coinswitchx', interval=1, days=10):
    endpoint = "/trade/api/v2/candles"
    method = "GET"
    
    end_time = int(time.time() * 1000)  # Current time in milliseconds
    start_time = end_time - (days * 24 * 60 * 60 * 1000)  # Start time in milliseconds
    
    params = {
        "exchange": exchange,
        "symbol": symbol.upper(),
        "interval": str(interval),
        "start_time": str(start_time),
        "end_time": str(end_time)
    }

    data = make_request(method, endpoint, params)
    if data and 'data' in data:
        candles = data['data']
        if not candles:
            print(f"No candle data available for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['close_time'], unit='ms')
        df['open'] = pd.to_numeric(df['o'], errors='coerce')
        df['high'] = pd.to_numeric(df['h'], errors='coerce')
        df['low'] = pd.to_numeric(df['l'], errors='coerce')
        df['close'] = pd.to_numeric(df['c'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df.dropna(inplace=True)
        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
    else:
        print(f"Failed to fetch candle data for {symbol}")
        return pd.DataFrame()


def get_open_orders(count=100, from_time=None, to_time=None, side=None, symbols=None, exchanges=None, type=None):
    endpoint = "/trade/api/v2/orders"
    method = "GET"
    params = {
        "count": count,
        "open": True  # We set open=True to get only open orders
    }
    if from_time:
        params["from_time"] = str(from_time)
    if to_time:
        params["to_time"] = str(to_time)
    if side:
        params["side"] = side.lower()
    if symbols:
        params["symbols"] = ",".join(symbols)
    if exchanges:
        params["exchanges"] = ",".join(exchanges)
    if type:
        params["type"] = type.lower()
    
    data = make_request(method, endpoint, params=params)
    if data and 'data' in data:
        orders = data['data']
        return orders
    else:
        print("Failed to fetch open orders.")
        return []


def cancel_order(order_id):
    endpoint = "/trade/api/v2/order"
    method = "DELETE"
    data = {
        "order_id": order_id
    }
    response = make_request(method, endpoint, data=data)
    if response and response.get('message') == 'Order cancelled successfully':
        print(f"Order {order_id} cancelled successfully.")
        return True
    else:
        print(f"Failed to cancel order {order_id}.")
        return False


# Function to place an order
def place_order(symbol, side, quantity, price=None):
    endpoint = "/trade/api/v2/order"
    method = "POST"
    data = {
        "side": side.lower(),
        "symbol": symbol.lower(),
        "type": "limit",  # or "market" if supported
        "quantity": quantity,
        "exchange": "coinswitchx"
    }
    if price:
        data["price"] = price

    response = make_request(method, endpoint, data=data)
    if response and 'data' in response:
        print(f"Order placed successfully. Order ID: {response['data']}")
        return response['data']
    else:
        print(f"Failed to place order for {symbol}")
        return None

# Function to calculate technical indicators
def calculate_indicators(df):
    # DEMA (Double Exponential Moving Average)
    df['DEMA_200'] = ta.dema(df['close'], length=200)

    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_signal'] = macd['MACDs_12_26_9']

    # Supertrend
    supertrend = ta.supertrend(df['high'], df['low'], df['close'], length=7, multiplier=3.0)
    df['Supertrend'] = supertrend['SUPERT_7_3.0']

    return df

# Main trading loop
def trading_bot():
    while True:
        current_time = datetime.now()
        # Run every 10 seconds
        if current_time.second % 10 == 0:
            for symbol in symbols:
                print(f"Processing symbol: {symbol}")
                df = get_historical_data(symbol, exchange='coinswitchx', interval=5, days=2)
                if df.empty or len(df) < 200:
                    print(f"Not enough data for {symbol}")
                    continue

                df = calculate_indicators(df)

                # Get the latest data point
                latest = df.iloc[-1]
                previous = df.iloc[-2]
                print(f"{symbol} at {latest['close']} at {current_time}")

                # Entry Conditions
                if symbol not in positions:
                    entry_condition = (
                        latest['close'] > latest['DEMA_200'] and
                        previous['MACD'] < previous['MACD_signal'] and
                        latest['MACD'] > latest['MACD_signal']
                    )
                    open_orders=get_open_orders();
                    print(open_orders);
                    # for order in open_orders['orders']:
                    #     cancel_order(order['order_id'])
                    if entry_condition:
                        # Place Buy Order
                        quantity = quantityMap[symbol]  # Adjust quantity as per your requirements
                        order_id = place_order(symbol, 'BUY', quantity, price=latest['close'])
                        if order_id:
                            positions[symbol] = {
                                'entry_price': latest['close'],
                                'quantity': quantity,
                                'entry_time': current_time,
                                'order_id': order_id
                            }
                            print(f"Entered position for {symbol} at {latest['close']}")

                # Exit Conditions
                else:
                    position = positions[symbol]
                    entry_price = position['entry_price']
                    target_price = entry_price * 1.10  # Target Profit of 10%
                    stop_loss_price = entry_price * 0.95  # Stop Loss of 5%

                    exit_condition = (
                        (previous['close'] > previous['Supertrend'] and latest['close'] < latest['Supertrend']) or
                        latest['close'] <= stop_loss_price or
                        latest['close'] >= target_price
                    )

                    if exit_condition:
                        # Place Sell Order
                        quantity = position['quantity']
                        order_id = place_order(symbol, 'SELL', quantity, price=latest['close'])
                        if order_id:
                            print(f"Exited position for {symbol} at {latest['close']}")
                            del positions[symbol]

            # Sleep for 10 seconds before checking again

# Run the trading bot
if __name__ == "__main__":
    try:
        trading_bot()
    except KeyboardInterrupt:
        print("Trading bot stopped manually.")
    except Exception as e:
        print(f"An error occurred: {e}")
