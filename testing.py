import pandas as pd
import os
from dotenv import load_dotenv
from main import (check_signal, 
                  EMA_LONG, 
                  ATR_PERIOD, 
                  EMA_SHORT, 
                  get_stop_loss_take_profit, 
                  calculate_position_size, 
                  get_market_regime,
                  trend_is_strong,
                  get_dynamic_trailing_multiplier,
                  )

# === LOAD ENV VARIABLES ===
load_dotenv()

# === CONFIG ===
SYMBOL = 'BTC/USDT'
INITIAL_BALANCE = 10000  # <<< You can adjust this manually



def get_data_from_csv(csv_path, start_date, end_date):
    df = pd.read_csv(csv_path)
    
    # Parse datetime and filter date range
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
    
    # Resample to 1-hour intervals (take the first available candle of each hour)
    df = df.set_index('datetime').resample('1h').first().dropna().reset_index()
    
    # Recalculate indicators
    df['ema_short'] = df['Close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['Close'].ewm(span=EMA_LONG, adjust=False).mean()
    df['atr'] = df['High'].rolling(ATR_PERIOD).max() - df['Low'].rolling(ATR_PERIOD).min()
    
    return df


# === CLEAN & MODULAR BACKTEST ===
def backtest(csv_path, start_date, end_date):
    # Load Data
    df = get_data_from_csv(csv_path, start_date, end_date)

    # Initialize Portfolio
    balance = INITIAL_BALANCE
    position = None
    position_size = 0
    stop_loss = None
    take_profit = None

    # Tracking lists
    signals = []
    portfolio_values = []

    # === MAIN LOOP ===
    for i in range(len(df)):

        # Wait until indicators are ready
        if i < max(EMA_LONG, ATR_PERIOD) or df['atr'].iloc[i] == 0:
            signals.append(None)
            portfolio_values.append(balance)
            continue

        # Prepare data window
        last = df.iloc[:i+1]
        price = df.iloc[i]['Close']
        atr = df.iloc[i]['atr']
        atr_mean = df['atr'].iloc[:i+1].mean()
        regime = get_market_regime(last)

        # Get Signal
        signal = check_signal(last)
        signals.append(signal)
        

        # === Entry ===
        if position is None and signal == 'buy' and balance > 0 and trend_is_strong(last):
            stop_loss, take_profit = get_stop_loss_take_profit(price, atr, regime)

            position_size = calculate_position_size(balance, atr, atr_mean, regime)
            position_size = min(position_size, balance / price)  # Cap to available balance

            if position_size > 0:
                position = price
                balance -= position_size * price

        # === Position Management ===
        elif position is not None:
            

            # Trailing Stop (Bull Only)
            if regime == 'bull':
                multiplier = get_dynamic_trailing_multiplier(atr, atr_mean, regime)
                stop_loss = max(stop_loss, price - multiplier * atr)

                

            # === Exit Conditions ===
            if price <= stop_loss or (regime != 'bull' and price >= take_profit) or signal == 'sell':
                balance += position_size * price
                position, position_size, stop_loss, take_profit = None, 0, None, None

        # === Record Portfolio Value ===
        current_value = balance + (position_size * price if position is not None else 0)
        portfolio_values.append(current_value)

    # === Save Results ===
    df['signal'] = signals
    df['portfolio_value'] = portfolio_values
    df.to_csv('backtest_result.csv', index=False)

    # === Metrics ===
    calculate_and_print_stats(df)


# === Metrics Function ===
def calculate_and_print_stats(df):
    years = (df['datetime'].iloc[-1] - df['datetime'].iloc[0]).days / 365.0
    final_value = df['portfolio_value'].iloc[-1]
    total_return = ((final_value / INITIAL_BALANCE) - 1) * 100
    cagr = ((final_value / INITIAL_BALANCE) ** (1 / years) - 1) * 100 if years > 0 else 0

    hold_return = ((df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1) * 100
    hold_cagr = ((df['Close'].iloc[-1] / df['Close'].iloc[0]) ** (1 / years) - 1) * 100 if years > 0 else 0

    trades_count = df['signal'].value_counts().get('buy', 0)

    print("\n========== BACKTEST RESULT ==========")
    print(f"Period: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    print(f"Total Years: {years:.2f}")
    print(f"Final Portfolio Value: {final_value:.2f} USD")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Average Annual Growth Rate (CAGR): {cagr:.2f}%")
    print(f"\nHOLD Total Return: {hold_return:.2f}%")
    print(f"HOLD CAGR: {hold_cagr:.2f}%")
    print(f"Total Trades: {trades_count}")
    print("====================================\n")



if __name__ == "__main__":
    start_date = '2021-12-01'
    end_date = '2024-04-01'
    backtest('btcusd_1-min_data.csv', start_date, end_date)
