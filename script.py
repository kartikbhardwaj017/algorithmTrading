import time
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime, timedelta
from kiteconnect import KiteConnect, KiteTicker

# Replace with your API Key and Secret
api_key = ""
api_secret = ""

POSITIONS_FILE = 'zerodha.json'

# Initialize KiteConnect
kite = KiteConnect(api_key=api_key)

import json

def generate_kite_session():
    print("Please generate your access token:")
    print(f"Login URL: {kite.login_url()}")

    # After login, you will get a request token in the URL
    request_token = input("Enter the request token: ")

    data = kite.generate_session(request_token, api_secret=api_secret)
    kite.set_access_token(data["access_token"])
    print("Access token set successfully!")

    # Save session data to a JSON file
    session_data = {
        "access_token": data["access_token"],
        "public_token": data.get("public_token", ""),  # Add any other relevant data here
        "user_id": data.get("user_id", "")
    }
    
    with open("zerodhaSession.json", "w") as json_file:
        json.dump(session_data, json_file, indent=4)
    print("Session data saved to zerodhaSession.json")


def set_kite_access_token():
    try:
        # Read the session data from the JSON file
        with open("zerodhaSession.json", "r") as json_file:
            session_data = json.load(json_file)
        
        # Set the access token in kite
        if "access_token" in session_data:
            kite.set_access_token(session_data["access_token"])
            print("Access token set successfully from file!")
        else:
            print("Access token not found in the session data.")
    except FileNotFoundError:
        print("zerodhaSession.json file not found. Please generate the session first.")
    except json.JSONDecodeError:
        print("Error reading session data from zerodhaSession.json.")



# def generate_kite_session():
#     print("Please generate your access token:")
#     print(f"Login URL: {kite.login_url()}")

#     # After login, you will get a request token in the URL
#     request_token = input("Enter the request token: ")

#     data = kite.generate_session(request_token, api_secret=api_secret)
#     kite.set_access_token(data["access_token"])
#     print("Access token set successfully!")


# generate_kite_session()

# List of stocks to trade with their respective instrument tokens
stocks = {
    'YESBANK': 3050241,
    'TATAMOTORS':884737,
    'ICICIBANK':1270529,
    'EICHERMOT':232961,
    'BATAINDIA':128011012
}

# Positions dictionary to keep track of open positions
# positions = {}

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save positions to JSON file
def save_positions(positions):
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f, indent=4)

# Function to get 5-minute historical data


def get_historical_data(token, interval='minute', days=5):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    data = kite.historical_data(
        instrument_token=token,
        from_date=start_date,
        to_date=end_date,
        interval=interval
    )
    df = pd.DataFrame(data)
    return df

# Function to place an order


def place_order(tradingsymbol, transaction_type, quantity):
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NSE,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=kite.ORDER_TYPE_MARKET,
            product=kite.PRODUCT_CNC
        )
        print(f"Order placed successfully. Order ID: {order_id}")
    except Exception as e:
        print(f"Failed to place order: {e}")

# Function to calculate technical indicators


def calculate_indicators(df):
    # DEMA (Double Exponential Moving Average)
    df['DEMA_200'] = ta.dema(df['close'], length=200)

    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_signal'] = macd['MACDs_12_26_9']

    # Supertrend
    supertrend = ta.supertrend(
        df['high'], df['low'], df['close'], length=7, multiplier=3.0)
    df['Supertrend'] = supertrend['SUPERT_7_3.0']

    return df

# Main trading loop


def trading_bot():
    while True:
        positions = load_positions()
        set_kite_access_token()
        current_time = datetime.now()
        if current_time.second % 10 == 0:  # Run every 5 minutes
            for symbol, token in stocks.items():
                print(f"Processing stock: {symbol}")
                df = get_historical_data(token)
                df = calculate_indicators(df)

                # Ensure we have enough data points
                if len(df) < 200:
                    print(f"Not enough data for {symbol}")
                    continue

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

                        place_order(symbol, kite.TRANSACTION_TYPE_BUY, 10)
                        positions[symbol] = {
                            'entry_price': latest['close'],
                            'quantity': 10,
                            'entry_time': current_time
                        }
                        save_positions(positions)
                        print(
                            f"Entered position for {symbol} at {latest['close']}")

                # Exit Conditions
                else:
                    position = positions[symbol]
                    entry_price = position['entry_price']
                    target_price = entry_price * 1.2  # Target Profit of 20%
                    stop_loss_price = entry_price * 0.95  # Stop Loss of 5%

                    exit_condition = (
                        (previous['close'] > previous['Supertrend'] and latest['close'] < latest['Supertrend']) or
                        latest['close'] <= stop_loss_price or
                        latest['close'] >= target_price
                    )

                    if exit_condition:
                        # Place Sell Order
                        place_order(symbol, kite.TRANSACTION_TYPE_SELL, 10)
                        print(
                            f"Exited position for {symbol} at {latest['close']}")
                        del positions[symbol]
                        save_positions(positions)


            # Sleep until the next 5-minute interval
            time.sleep(10 - datetime.now().second % 10)
        else:
            # Sleep for a short time before checking again
            time.sleep(1)


# Run the trading bot
if __name__ == "__main__":
    try:
        trading_bot()
    except KeyboardInterrupt:
        print("Trading bot stopped manually.")
    except Exception as e:
        print(f"An error occurred: {e}")
