import time
import json
import os
import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from urllib.parse import urlencode, unquote_plus
from cryptography.hazmat.primitives.asymmetric import ed25519

# Replace with your API Key and Secret Key provided by CoinSwitch Kuber
api_key = ""
secret_key = ""

symbols = ["BTC/INR", "ETH/INR", "XRP/INR"]
quantityMap = {
    "BTC/INR":0.00001,
     "ETH/INR":0.001
}


# File to store positions
POSITIONS_FILE = 'crypto_position.json'

# Base URL for API endpoints
BASE_URL = "https://coinswitch.co"

# Load positions from JSON file
def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save positions to JSON file
def save_positions(positions):
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f, indent=4)

# Update a position in the JSON file
def update_position(symbol, position_data):
    positions = load_positions()
    positions[symbol] = position_data
    save_positions(positions)

# Remove a position from the JSON file
def remove_position(symbol):
    positions = load_positions()
    if symbol in positions:
        del positions[symbol]
        save_positions(positions)

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
def get_historical_data(symbol, exchange='coinswitchx', interval=1, days=1):
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

# Function to place an order
def place_order(symbol, side, quantity, price=None):
    endpoint = "/trade/api/v2/order"
    method = "POST"
    data = {
        "side": side.lower(),
        "symbol": symbol.lower(),
        "type": "limit",  # or "market" if supported
        "quantity": str(quantity),
        "exchange": "coinswitchx"
    }
    if price:
        data["price"] = str(price)

    response = make_request(method, endpoint, data=data)
    if response and 'orderId' in response:
        print(f"Order placed successfully. Order ID: {response['orderId']}")
        return response['orderId']
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
    positions = load_positions()  # Load the current positions at startup

    while True:
        current_time = datetime.now()
        # Run every 1 minute
        if current_time.second == 0:
            for symbol in symbols:
                print(f"Processing symbol: {symbol}")
                df = get_historical_data(symbol, exchange='coinswitchx', interval=5, days=4)
                if df.empty or len(df) < 200:
                    print(f"Not enough data for {symbol}")
                    continue

                df = calculate_indicators(df)

                # Get the latest data point
                latest = df.iloc[-1]
                previous = df.iloc[-2]

                # Entry Conditions
                if symbol not in positions:
                    entry_condition = (
                        latest['close'] > latest['DEMA_200'] and
                        previous['MACD'] < previous['MACD_signal'] and
                        latest['MACD'] > latest['MACD_signal']
                    )
                    if entry_condition:
                        # Place Buy Order
                        quantity =  quantityMap[symbol]  # Adjust quantity as per your requirements
                        order_id = place_order(symbol, 'BUY', quantity, price=latest['close'])
                        if order_id:
                            position_data = {
                                'entry_price': latest['close'],
                                'quantity': quantity,
                                'entry_time': current_time.isoformat(),
                                'order_id': order_id
                            }
                            update_position(symbol, position_data)  # Save position to JSON file
                            print(f"Entered position for {symbol} at {latest['close']}")

                # Exit Conditions
                else:
                    position = positions[symbol]
                    entry_price = position['entry_price']
                    target_price = entry_price * 1.02  # Target Profit of 2%
                    stop_loss_price = entry_price * 0.98  # Stop Loss of 2%

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
                            save_positions(positions)

            # Sleep for 10 seconds before checking again

# Run the trading bot
if __name__ == "__main__":
    try:
        trading_bot()
    except KeyboardInterrupt:
        print("Trading bot stopped manually.")
    except Exception as e:
        print(f"An error occurred: {e}")
