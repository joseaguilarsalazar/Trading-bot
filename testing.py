import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from main import (
                  EMA_LONG, 
                  ATR_PERIOD, 
                  EMA_SHORT, 
                  get_stop_loss_take_profit, 
                  get_market_regime,
                  get_dynamic_trailing_multiplier,
                  calculate_trend_strength,
                  )
from check_signal import check_signal
from testClient import TestClient

# === LOAD ENV VARIABLES ===
load_dotenv()

# === CONFIG ===
INITIAL_BALANCE = 10000  # <<< You can adjust this manually



def get_data_from_csv(csv_path, start_date, end_date):
    df = pd.read_csv(csv_path)
    
    # Parse datetime and filter date range
    df['datetime'] = pd.to_datetime(df['Open time'])
    df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
    
    # Recalculate indicators
    df['ema_short'] = df['Close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['Close'].ewm(span=EMA_LONG, adjust=False).mean()
    df['high_low'] = df['High'] - df['Low']
    df['high_prev_close'] = abs(df['High'] - df['Close'].shift(1))
    df['low_prev_close'] = abs(df['Low'] - df['Close'].shift(1))

    df['TR'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)

    # Calculate ATR (14-period is common)
    df['atr'] = df['TR'].rolling(window=ATR_PERIOD).mean()

    # ✅ Add ATR mean calculation
    df['atr_mean'] = df['atr'].rolling(window=ATR_PERIOD).mean()  # Smoothed ATR
    
    return df


# === CLEAN & MODULAR BACKTEST ===
def backtest(csv_path, start_date, end_date):
    # Load Data
    df = get_data_from_csv(csv_path, start_date, end_date)

    initial_price = float(df.iloc[0]['Open'])
    end_price = float(df.iloc[-1]['Close'])

    # Initialize Portfolio
    client = TestClient(INITIAL_BALANCE)
    signalCount = 0
    s_cound = 0
    b_count = 0
    sb = 0
    # === MAIN LOOP ===
    for i in range(len(df)):

        # Prepare data window
        previousTrades = df.iloc[:i+1]
        last = previousTrades.iloc[-1] 
        price = df.iloc[i]['Close']
        atr = df.iloc[i]['atr']
        atr_mean = df.iloc[i]['atr_mean']
        regime, avg_diff, trend_strength, atr_pct = get_market_regime(previousTrades)

        if client.check_margin(price) == False:
            print('El bot se quedo sin fondos')
            print(f'Fecha: {last[datetime]}')
            print(client.USDT)
            print(client.BTC)
            print(price)

        # Get Signal
        result = check_signal(last, regime, trend_strength, atr_pct, client.position)
        if result:
            signal = result['action']
            signalCount += 1
        else:
            signal = None
        
        # === Entry ===
        if client.position is None and (signal == 'open_long' or signal == 'open_short') and client.USDT > 0:
            trend_strength = calculate_trend_strength(previousTrades)
            print(signal)
            client.open_position('long' if signal == 'open_long' else 'short', price, regime, trend_strength, df.iloc[i]['datetime'])
            client.stop_loss, client.take_profit = get_stop_loss_take_profit(price, atr, regime, trend_strength, client.position, client.entry_price, client.stop_loss, client.stop_loss)
            
        # === Position Management ===
        elif client.position is not None and (signal == 'close_long' or signal == 'close_short'): 
            # Trailing Stop (Bull and Strong Bull Only)
            if regime in ['bull', 'strong_bull']:
                multiplier = get_dynamic_trailing_multiplier(atr, atr_mean, regime)
                client.stop_loss = max(client.stop_loss, price - multiplier * atr)

            # === Exit Conditions ===
            exit_condition = (
                price <= client.stop_loss or  # Hit stop loss
                price >= client.take_profit or  
                (signal == 'close_long' or signal == 'close_short')  # Sell signal
            )
            if client.position == 'long':
                if exit_condition:
                    client.close_position(price, regime, trend_strength, df.iloc[i]['datetime'])
            else:
                exit_condition = (
                price >= client.stop_loss or  # Hit stop loss
                price <= client.take_profit or  
                (signal == 'close_long' or signal == 'close_short')  # Sell signal
            )
                if exit_condition:
                    client.close_position(price, regime, trend_strength, df.iloc[i]['datetime'])


    # === Metrics ===
        

    print(f'Sideways: {s_cound}')
    print(f'Weak Bear: {b_count}')
    print(f'Strong bear: {sb}')
    calculate_and_print_stats(client, INITIAL_BALANCE, start_date, end_date, initial_price, end_price)
    print(signalCount)
    print(client.get_summary())
    client.export_trade_log_to_csv()


# === Metrics Function ===
def calculate_and_print_stats(client: TestClient, initial_balance, start_date, end_date, initial_price, end_price):
    trade_log = client.trade_log

    prices = [trade[1] for trade in trade_log]  # BTC Prices
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # Calculate the number of years
    years = (end_dt - start_dt).days / 365.0

    # Final balance
    final_value = client.USDT + (client.BTC * float(end_price))  # Cash + BTC value
    total_return = ((final_value / initial_balance) - 1) * 100
    cagr = ((final_value / initial_balance) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Calculate Buy & Hold performance
    hold_return = ((end_price / initial_price) - 1) * 100
    hold_cagr = ((end_price / initial_price) ** (1 / years) - 1) * 100 if years > 0 else 0

    # === Print Results ===
    print("\n========== BACKTEST RESULT ==========")
    print(f"Period: {start_date} to {end_date}")
    print(f"Total Years: {years:.2f}")
    print(f"Final Portfolio Value: {final_value:.2f} USD")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Average Annual Growth Rate (CAGR): {cagr:.2f}%")
    print(f"\nHOLD Total Return: {hold_return:.2f}%")
    print(f"HOLD CAGR: {hold_cagr:.2f}%")
    print("====================================\n")




if __name__ == "__main__":
    a = {
        'bull' : {
            'start_date' : '2022-12-10',
            'end_date' : '2025-01-22'
        },
        'bear' : {
            'start_date' : '2021-11-13',
            'end_date' : '2022-12-16'
        },
        'sideways' : {
            'start_date' : '2018-09-22',
            'end_date' : '2019-05-11'
        }
    }
    start_date = '2018-09-22'
    end_date = '2025-01-22'
    backtest('BTCUSD_1h_Binance.csv', start_date, end_date)

