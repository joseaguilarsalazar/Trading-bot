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

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# === DATA FETCH ===
def get_data(days=90):
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe='1h', since=since)
    df = pd.DataFrame(bars, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['ema_short'] = df['Close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['Close'].ewm(span=EMA_LONG, adjust=False).mean()
    df['atr'] = df['High'].rolling(ATR_PERIOD).max() - df['Low'].rolling(ATR_PERIOD).min()
    return df

# === MARKET REGIME ===
def get_market_regime(df):
    ema_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
    if ema_50 > ema_200:
        return 'bull'
    elif ema_50 < ema_200:
        return 'bear'
    else:
        return 'sideways'

# === SIGNAL ===
def check_signal(df):
    last = df.iloc[-1]
    atr_mean = df['atr'].mean()
    atr_is_calm = last['atr'] < atr_mean

    if last['ema_short'] > last['ema_long'] and atr_is_calm:
        return 'buy'
    elif last['ema_short'] < last['ema_long'] and atr_is_calm:
        return 'sell'
    return None

def get_dynamic_atr_multiplier(atr, atr_mean, base=2.0):
    """
    Calculate dynamic ATR multiplier based on volatility.
    More volatile = wider stops.
    """
    volatility_ratio = atr / atr_mean if atr_mean > 0 else 1
    multiplier = base + volatility_ratio  # base=2 means default is 2x ATR
    return multiplier

# === STOP LOSS & TAKE PROFIT ===
def get_stop_loss_take_profit(entry_price, atr, atr_mean, regime):
    """
    Dynamically adjusts stop loss and take profit based on volatility and regime.
    """
    multiplier = get_dynamic_atr_multiplier(atr, atr_mean)
    
    if regime == 'bull':
        stop_loss = entry_price - multiplier * atr * 2
        take_profit = entry_price + multiplier * atr * 3
    elif regime == 'bear':
        stop_loss = entry_price - multiplier * atr
        take_profit = entry_price + multiplier * atr * 1.5
    else:  # sideways
        stop_loss = entry_price - multiplier * atr * 0.75
        take_profit = entry_price + multiplier * atr * 1.0

    return stop_loss, take_profit, multiplier

# === DYNAMIC TRAILING STOP ===
def get_dynamic_trailing_stop(price, atr, ema_slope, base_multiplier=3):
    slope_factor = min(max(abs(ema_slope) / 0.0005, 0.5), 2.0)
    trailing_multiplier = base_multiplier * slope_factor
    return price - trailing_multiplier * atr

# === POSITION SIZE ===
def calculate_position_size(balance, atr, multiplier, risk_percent=0.02):
    """
    Adjusts position size based on volatility and risk %.
    """
    risk_amount = balance * risk_percent
    stop_loss_distance = atr * multiplier
    if stop_loss_distance == 0:
        return 0
    position_size = risk_amount / stop_loss_distance
    return position_size

# === EXECUTE TRADE ===
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

def get_dynamic_trailing_stop(price, atr, regime, ema_slope):
    """
    Dynamically adjusts the trailing stop multiplier based on the market regime and EMA slope (momentum).

    Parameters:
        price (float): Current price.
        atr (float): Current ATR value.
        regime (str): Market regime ('bull', 'bear', 'sideways').
        ema_slope (float): The slope of the EMA.

    Returns:
        float: The new trailing stop price.
    """

    if regime == 'bull':
        if ema_slope > 0.1:  # strong momentum
            multiplier = 4
        elif ema_slope > 0.05:
            multiplier = 3
        else:
            multiplier = 2
    elif regime == 'bear':
        multiplier = 2
    else:  # sideways
        multiplier = 1.5

    return price - multiplier * atr


def get_partial_sell_targets(entry_price, atr, regime, base_rr=2):
    """
    Calculates two profit targets for partial position selling.

    Parameters:
        entry_price (float): The price at which the position is opened.
        atr (float): The current ATR value.
        regime (str): Market regime ('bull', 'bear', 'sideways').
        base_rr (float): Base risk-reward ratio.

    Returns:
        tuple: (first_target, final_target)
    """

    if regime == 'bull':
        rr1, rr2 = 2, 4  # Bull markets aim for higher second targets
    elif regime == 'bear':
        rr1, rr2 = 1.5, 2.5
    else:  # sideways
        rr1, rr2 = 1, 2

    first_target = entry_price + rr1 * atr
    final_target = entry_price + rr2 * atr

    return first_target, final_target


# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        df = get_data()
        signal = check_signal(df)
        if signal:
            execute_trade(signal)
        time.sleep(3600)  # Wait 1 hour'
