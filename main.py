import ccxt
import pandas as pd
import time
import requests
import os
from dotenv import load_dotenv

# === LOAD ENV VARIABLES ===
load_dotenv()
API_KEY = 'vino6wn77bt8CqT7KsKBncxV1nfdXy4hfPXdnTbCme9p4TsfpQz3BOLTj82paekU'
API_SECRET = 'wEs7pjD0uBvLvmsK88a7jr2xMNUwZPktVGclkKkqKElMfSBiLCzarGMN3Dy8b15C'
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# === CONFIG ===
SYMBOL = 'BTC/USDT'
POSITION_SIZE = 0.001  # Adjust to your risk
ATR_PERIOD = 14
EMA_SHORT = 50
EMA_LONG = 200
VOLATILITY_THRESHOLD = 0.75  # Example threshold for ATR filter

# === EXCHANGE SETUP ===
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True
})

# === ALERTS ===
def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# === DATA FETCH ===
def get_data(days=90):  # default = 90 days
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000  # ms
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe='1h', since=since)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['ema_short'] = df['close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=EMA_LONG, adjust=False).mean()
    df['atr'] = df['high'].rolling(ATR_PERIOD).max() - df['low'].rolling(ATR_PERIOD).min()
    return df

def get_market_regime(df):
    ema_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
    if ema_50 > ema_200:
        return 'bull'
    elif ema_50 < ema_200:
        return 'bear'
    else:
        return 'sideways'
    


# === TRADING LOGIC ===
def check_signal(df):
    last = df.iloc[-1]
    atr_mean = df['atr'].mean()
    regime = get_market_regime(df)

    if regime == 'bull':
        atr_is_calm = last['atr'] < atr_mean * 3  # looser filter
    else:
        atr_is_calm = last['atr'] < atr_mean  # stricter

    if last['ema_short'] > last['ema_long'] and atr_is_calm:
        return 'buy'
    elif last['ema_short'] < last['ema_long'] and atr_is_calm:
        return 'sell'
    return None

def get_stop_loss_take_profit(entry_price, atr, regime, base_risk=2, base_rr=2):
    if regime == 'bull':
        stop_loss = entry_price - 3 * atr  # wider SL
        take_profit = entry_price + 3 * atr * base_rr
    elif regime == 'bear':
        stop_loss = entry_price - 2 * atr
        take_profit = entry_price + 2 * atr * base_rr
    else:  # sideways
        stop_loss = entry_price - 1.5 * atr
        take_profit = entry_price + 1.5 * atr * base_rr
    return stop_loss, take_profit

def calculate_position_size(balance, entry_price, stop_loss, risk_percent=0.02):
    """
    Calculates dynamic position size based on account balance and stop loss distance.

    Parameters:
        balance (float): Current available balance.
        entry_price (float): The price you are buying at.
        stop_loss (float): The stop loss price.
        risk_percent (float): The % of balance you are willing to risk (default 2%).

    Returns:
        float: Position size (number of units to buy).
    """
    risk_amount = balance * risk_percent
    stop_loss_distance = abs(entry_price - stop_loss)
    if stop_loss_distance == 0:
        return 0  # Avoid division by zero
    position_size = risk_amount / stop_loss_distance
    return position_size

def get_dynamic_trailing_stop(price, atr, ema_slope, base_multiplier=3):
    """
    Adjust trailing stop dynamically based on EMA50 slope.
    
    Parameters:
        price (float): Current price.
        atr (float): Current ATR.
        ema_slope (float): The slope (momentum) of EMA50.
        base_multiplier (float): Base multiplier for trailing stop.
        
    Returns:
        float: New trailing stop price.
    """
    # Normalize slope effect
    slope_factor = min(max(abs(ema_slope) / 0.0005, 0.5), 2.0)  # between 0.5x and 2x
    trailing_multiplier = base_multiplier * slope_factor
    return price - trailing_multiplier * atr


# === ORDER EXECUTION ===
def execute_trade(signal):
    try:
        if signal == 'buy':
            exchange.create_market_buy_order(SYMBOL, POSITION_SIZE)
            send_alert("[BOT] BUY ORDER executed.")
        elif signal == 'sell':
            exchange.create_market_sell_order(SYMBOL, POSITION_SIZE)
            send_alert("[BOT] SELL ORDER executed.")
    except Exception as e:
        send_alert(f"[BOT] ERROR: {str(e)}")

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        df = get_data()
        signal = check_signal(df)
        if signal:
            execute_trade(signal)
        time.sleep(3600)  # Wait 1 hour'
