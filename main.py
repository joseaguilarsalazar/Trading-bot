import pandas as pd
import time
import requests
import os
from dotenv import load_dotenv
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
#client = Client('IW4Ap8Dt8ykhNsNNmpJkbr29wniP1cbDG7kxjWHDo8a2sbuQQ5e0DPNJzl2fAhFh',
#                 'C87G8ymR6Ae3mHMtXiHu8YLo14CLmAV5MjfX7oZsqVkVLr79wHBGv40dNBnkm8eI',
#                 testnet=True)

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

# === DATA FETCH ===
# def get_data(days=90):
#     """Fetches historical OHLCV data using python-binance."""
    
#     # Calculate the timestamp for the start date
#     since = int(time.time() * 1000) - days * 24 * 60 * 60 * 1000

#     # Fetch historical K-line (candlestick) data
#     bars = client.get_historical_klines(SYMBOL, Client.KLINE_INTERVAL_1HOUR, since)

#     # Convert data into a Pandas DataFrame
#     df = pd.DataFrame(bars, columns=[
#         'Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
#         'CloseTime', 'QuoteAssetVolume', 'NumberOfTrades', 
#         'TakerBuyBaseAssetVolume', 'TakerBuyQuoteAssetVolume', 'Ignore'
#     ])
    
#     # Convert relevant columns to numeric
#     df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    
#     # Convert Timestamp to readable datetime
#     df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')

#     # Calculate indicators
#     df['ema_short'] = df['Close'].ewm(span=EMA_SHORT, adjust=False).mean()
#     df['ema_long'] = df['Close'].ewm(span=EMA_LONG, adjust=False).mean()


#     df['high_prev_close'] = abs(df['High'] - df['Close'].shift(1))
#     df['low_prev_close'] = abs(df['Low'] - df['Close'].shift(1))

#     df['TR'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)

#     # Calculate ATR (14-period is common)
#     df['atr'] = df['TR'].rolling(window=ATR_PERIOD).mean()

#     # ✅ Add ATR mean calculation
#     df['atr_mean'] = df['atr'].rolling(window=ATR_PERIOD).mean()  # Smoothed ATR

#     return df

# === MARKET REGIME ===
import pandas as pd

def get_market_regime(df, window=5, ema_fast=50, ema_slow=200, adx_thresholds=(15, 25), atr_threshold=0.02):
    """
    Identifies market regimes based on trend strength, momentum, and volatility.
    
    Returns:
        regime (str): The identified market regime.
        avg_diff (float): The smoothed EMA difference.
        trend_strength (float): ADX value.
        atr_pct (float): ATR as a percentage of price.
    """
    df = df.copy()
    
    # Compute Moving Averages
    df['ema_fast'] = df['Close'].ewm(span=ema_fast, adjust=False).mean()
    df['ema_slow'] = df['Close'].ewm(span=ema_slow, adjust=False).mean()
    
    # Compute EMA Difference (Trend Indicator)
    ema_diff = df['ema_fast'] - df['ema_slow']
    avg_diff = ema_diff.rolling(window=window).mean().iloc[-1]

    # Compute ADX (Trend Strength)
    df['adx'] = df['atr'].rolling(window=window).mean()  # Placeholder for ADX, replace with real calculation
    trend_strength = df['adx'].iloc[-1]

    # Compute ATR % (Volatility Indicator)
    df['atr_pct'] = df['atr'] / df['Close']
    atr_pct = df['atr_pct'].iloc[-1]

    # === Market Regime Classification ===
    if avg_diff > 0:  # Bull Market Conditions
        if trend_strength > adx_thresholds[1]:
            return "strong_bull", avg_diff, trend_strength, atr_pct
        else:
            return "bull", avg_diff, trend_strength, atr_pct

    elif avg_diff < 0:  # Bear Market Conditions
        if trend_strength > adx_thresholds[1]:
            return "strong_bear", avg_diff, trend_strength, atr_pct
        else:
            return "weak_bear", avg_diff, trend_strength, atr_pct

    else:  # Sideways Market
        return "sideways", avg_diff, trend_strength, atr_pct

    
# === TREND STRENGTH FILTER ===
def trend_is_strong(df):
    ema50 = df['ema_short'].iloc[-1]
    ema200 = df['ema_long'].iloc[-1]
    ema200_slope = ema200 - df['ema_long'].iloc[-5]
    return ema50 > ema200 and ema200_slope > 0

def calculate_trend_strength(df):
    ema_50 = df['Close'].ewm(span=50, adjust=False).mean()
    ema_200 = df['Close'].ewm(span=200, adjust=False).mean()

    ema_diff = ema_50 - ema_200  # Distance between EMAs
    max_diff = ema_diff.rolling(window=50).max()  # Normalize

    trend_strength = ema_diff / max_diff  # Scale between 0 - 1
    return trend_strength.iloc[-1]  # Get latest value

def get_stop_loss_take_profit(price, atr, regime, trend_strength, position, entry_price, last_support=None, last_resistance=None):
    """
    Dynamically calculates Stop-Loss (SL) and Take-Profit (TP) based on market conditions.
    - Uses ATR-based dynamic levels.
    - Considers trend strength for more adaptive SL/TP.
    - Uses support/resistance for added security.
    - Includes a trailing stop mechanism.
    """
    # ATR-based dynamic multipliers
    if regime == 'bull':
        stop_multiplier = 3 + 1.5 * trend_strength  
        take_profit_multiplier = 8 + 4 * trend_strength  
    elif regime == 'strong_bull':
        stop_multiplier = 2.5 + 1.5 * trend_strength  
        take_profit_multiplier = 12 + 4 * trend_strength  
    elif regime == 'weak_bear':
        stop_multiplier = 2  
        take_profit_multiplier = 3  
    elif regime == 'strong_bear':
        stop_multiplier = 2.5  
        take_profit_multiplier = 2  
    else:  # Sideways Market
        stop_multiplier = 2  
        take_profit_multiplier = 3  

    # Calculate ATR-based SL/TP
    if position == "long":
        stop_loss = entry_price - stop_multiplier * atr  
        take_profit = entry_price + take_profit_multiplier * atr  

        # Adjust SL if recent support is near
        if last_support and last_support > stop_loss:
            stop_loss = last_support  # Use support as a safer SL

        # Trailing stop logic: If price moves significantly up, adjust SL
        if price > entry_price + (atr * 2):
            stop_loss = max(stop_loss, price - 1.5 * atr)  

    elif position == "short":
        stop_loss = entry_price + stop_multiplier * atr  
        take_profit = entry_price - take_profit_multiplier * atr  

        # Adjust SL if recent resistance is near
        if last_resistance and last_resistance < stop_loss:
            stop_loss = last_resistance  # Use resistance as a safer SL

        # Trailing stop logic: If price moves significantly down, adjust SL
        if price < entry_price - (atr * 2):
            stop_loss = min(stop_loss, price + 1.5 * atr)  

    else:
        return None, None  # No position, no SL/TP

    return stop_loss, take_profit


# === POSITION SIZE ===
def calculate_position_size(balance, atr, atr_mean, regime):
    base_risk = 0.02  # 2% risk
    volatility_factor = max(0.5, min(2, atr_mean / atr)) if regime == 'bull' else 1
    position_size = (balance * base_risk) / (atr * 2)
    return position_size * volatility_factor

# === EXECUTE TRADE ===
# def execute_trade(signal, price, position_size, stop_loss, take_profit):
#     try:
#         if signal == 'buy':
#             order = client.order_market_buy(
#                 symbol=SYMBOL,
#                 quantity=position_size
#             )

#         elif signal == 'sell':
#             order = client.order_market_sell(
#                 symbol=SYMBOL,
#                 quantity=position_size
#             )

#         # Fetch updated balances
#         account_info = client.get_account()
#         balances = {asset['asset']: float(asset['free']) for asset in account_info['balances']}
#         usdt_balance = balances.get('USDT', 0)
#         btc_balance = balances.get('BTC', 0)

#         # Send trade confirmation alert
#         send_alert(f"[BOT] ✅ {signal.upper()} ORDER executed.\n"
#                    f"📌 Price: {price:.2f} USDT\n"
#                    f"📈 Position Size: {position_size:.6f} BTC\n"
#                    f"🛑 Stop Loss: {stop_loss:.2f} USDT\n"
#                    f"🎯 Take Profit: {take_profit:.2f} USDT\n"
#                    f"💰 New Balance: {usdt_balance:.2f} USDT | {btc_balance:.6f} BTC")

#     except Exception as e:
#         send_alert(f"[BOT] ❌ ERROR: {str(e)}")


#     except Exception as e:
#         send_alert(f"[BOT] ❌ ERROR: {str(e)}")


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

    elif regime == 'strong_bull':
        if atr_ratio > 1.5:
            multiplier = 10.0  # Even looser trailing for strong bull
        elif atr_ratio > 1.0:
            multiplier = 8.0
        elif atr_ratio > 0.7:
            multiplier = 6.5
        else:
            multiplier = 3.5  # Still looser than normal bull

    elif regime == 'bear':
        if atr_ratio > 1.5:
            multiplier = 2.0
        elif atr_ratio > 1.0:
            multiplier = 1.5
        else:
            multiplier = 1.0

    elif regime == 'strong_bear':
        if atr_ratio > 1.5:
            multiplier = 3.0  # Slightly looser for extreme downtrends
        elif atr_ratio > 1.0:
            multiplier = 2.0
        else:
            multiplier = 1.5

    else:  # Sideways market
        multiplier = 1.0  # Keep it tight in uncertain conditions

    return multiplier



