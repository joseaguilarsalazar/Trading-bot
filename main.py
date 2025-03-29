import ccxt
import pandas as pd
import time
import requests
import os
from dotenv import load_dotenv
from binance.client import Client
TEST =True

# === LOAD ENV VARIABLES ===
load_dotenv()
API_KEY = 'vino6wn77bt8CqT7KsKBncxV1nfdXy4hfPXdnTbCme9p4TsfpQz3BOLTj82paekU'
API_SECRET = 'wEs7pjD0uBvLvmsK88a7jr2xMNUwZPktVGclkKkqKElMfSBiLCzarGMN3Dy8b15C'
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# === CONFIG ===
SYMBOL = 'BTCUSDT'
POSITION_SIZE = 0.001  # Adjust to your risk
ATR_PERIOD = 14
EMA_SHORT = 50
EMA_LONG = 200
VOLATILITY_THRESHOLD = 0.75  # Example threshold for ATR filter

# === EXCHANGE SETUP ===
client = Client('IW4Ap8Dt8ykhNsNNmpJkbr29wniP1cbDG7kxjWHDo8a2sbuQQ5e0DPNJzl2fAhFh',
                'C87G8ymR6Ae3mHMtXiHu8YLo14CLmAV5MjfX7oZsqVkVLr79wHBGv40dNBnkm8eI',
                testnet=True)

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# === DATA FETCH ===
def get_data(days=90):
    """Fetches historical OHLCV data using python-binance."""
    
    # Calculate the timestamp for the start date
    since = int(time.time() * 1000) - days * 24 * 60 * 60 * 1000

    # Fetch historical K-line (candlestick) data
    bars = client.get_historical_klines(SYMBOL, Client.KLINE_INTERVAL_1HOUR, since)

    # Convert data into a Pandas DataFrame
    df = pd.DataFrame(bars, columns=[
        'Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
        'CloseTime', 'QuoteAssetVolume', 'NumberOfTrades', 
        'TakerBuyBaseAssetVolume', 'TakerBuyQuoteAssetVolume', 'Ignore'
    ])
    
    # Convert relevant columns to numeric
    df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    
    # Convert Timestamp to readable datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')

    # Calculate indicators
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
    
# === TREND STRENGTH FILTER ===
def trend_is_strong(df):
    ema50 = df['ema_short'].iloc[-1]
    ema200 = df['ema_long'].iloc[-1]
    ema200_slope = ema200 - df['ema_long'].iloc[-5]
    return ema50 > ema200 and ema200_slope > 0

def check_signal(df):
    last = df.iloc[-1]
    atr_mean = df['atr'].mean()
    regime = get_market_regime(df)

    # === Bull Market Condition ===
    if regime == 'bull':
        if last['ema_short'] > last['ema_long']:  # Less strict
            return 'buy'
        elif last['ema_short'] < last['ema_long']:
            return 'sell'
        return None

    # === Bear or Sideways (keep strict) ===
    atr_is_calm = last['atr'] < atr_mean
    if last['ema_short'] > last['ema_long'] and atr_is_calm:
        return 'buy'
    elif last['ema_short'] < last['ema_long'] and atr_is_calm:
        return 'sell'
    return None


# === STOP LOSS & TAKE PROFIT ===
def get_stop_loss_take_profit(price, atr, regime):
    if regime == 'bull':
        stop_loss = price - 3 * atr
        take_profit = price + 6 * atr
    else:
        stop_loss = price - 2 * atr
        take_profit = price + 3 * atr
    return stop_loss, take_profit

# === POSITION SIZE ===
def calculate_position_size(balance, atr, atr_mean, regime):
    base_risk = 0.02  # 2% risk
    volatility_factor = max(0.5, min(2, atr_mean / atr)) if regime == 'bull' else 1
    position_size = (balance * base_risk) / (atr * 2)
    return position_size * volatility_factor

# === EXECUTE TRADE ===
def execute_trade(signal, price, position_size, stop_loss, take_profit):
    try:
        if signal == 'buy':
            order = client.order_market_buy(
                symbol=SYMBOL,
                quantity=position_size
            )

        elif signal == 'sell':
            order = client.order_market_sell(
                symbol=SYMBOL,
                quantity=position_size
            )

        # Fetch updated balances
        account_info = client.get_account()
        balances = {asset['asset']: float(asset['free']) for asset in account_info['balances']}
        usdt_balance = balances.get('USDT', 0)
        btc_balance = balances.get('BTC', 0)

        # Send trade confirmation alert
        send_alert(f"[BOT] ✅ {signal.upper()} ORDER executed.\n"
                   f"📌 Price: {price:.2f} USDT\n"
                   f"📈 Position Size: {position_size:.6f} BTC\n"
                   f"🛑 Stop Loss: {stop_loss:.2f} USDT\n"
                   f"🎯 Take Profit: {take_profit:.2f} USDT\n"
                   f"💰 New Balance: {usdt_balance:.2f} USDT | {btc_balance:.6f} BTC")

    except Exception as e:
        send_alert(f"[BOT] ❌ ERROR: {str(e)}")


    except Exception as e:
        send_alert(f"[BOT] ❌ ERROR: {str(e)}")





def get_dynamic_trailing_multiplier(atr, atr_mean, regime):
    """
    Dynamically adjust trailing stop multiplier based on volatility and trend regime
    """
    atr_ratio = atr / atr_mean if atr_mean != 0 else 1.0

    if regime == 'bull':
        if atr_ratio > 1.5:
            multiplier = 8.0  # Strong trend, loose trailing
        elif atr_ratio > 1.0:
            multiplier = 6.5
        elif atr_ratio > 0.7:
            multiplier = 5.0
        else:
            multiplier = 2.5  # Weak trend, tighter trailing
    else:  # Non-bull regimes
        if atr_ratio > 1.5:
            multiplier = 2
        elif atr_ratio > 1.0:
            multiplier = 1.5
        else:
            multiplier = 1.0

    return multiplier

# === MAIN LOOP ===
if __name__ == "__main__":
    while True:
        df = get_data()
        signal = check_signal(df)
        if signal:
            execute_trade(signal)
        time.sleep(3600)  # Wait 1 hour'
