import time
import ccxt
import os
from dotenv import load_dotenv
from binance.client import Client
import pandas as pd
from main import (
    check_signal,
    get_market_regime,
    get_stop_loss_take_profit,
    calculate_position_size,
    get_dynamic_trailing_multiplier,
    execute_trade,
    get_data,
    send_alert,
    client
)

# === LOAD ENV VARIABLES ===
load_dotenv()
SYMBOL = 'BTCUSDT'



# === LIVE TRADING ===
position = None
position_size = 0
stop_loss = None
take_profit = None

send_alert('Trading Bot inicialized')
a = False
if a == True:
    data :pd.DataFrame = get_data()
    print(data.head())
else:

    while True:
        try:
            # Fetch market data
            df = get_data(days=7)  # Last 7 days for indicators
            signal = check_signal(df)
            price = df.iloc[-1]['Close']
            atr = df.iloc[-1]['atr']
            atr_mean = df['atr'].mean()
            regime = get_market_regime(df)

            print('data fetched')
            
            # === Entry ===
            if position is None and signal == 'buy':

                print('Entry activated')
                stop_loss, take_profit = get_stop_loss_take_profit(price, atr, regime)
                
                # Fetch account balances
                account_info = client.get_account()
                balances = {asset['asset']: float(asset['free']) for asset in account_info['balances']}
                balance = balances.get('USDT', 0)

                # Calculate position size
                position_size = calculate_position_size(balance, atr, atr_mean, regime)
                position_size = min(position_size, balance / price)  # Ensure it does not exceed available balance
                
                if position_size > 0:
                    execute_trade('buy', price, position_size, stop_loss, take_profit)  # ✅ Pass all required data
                    position = price  # Store entry price
                else:
                    send_alert('Trade not executed due to insufficient balance')

            # === Position Management ===
            elif position is not None:
                print('Managing Position')
                # Trailing Stop (Bull Market Only)
                if regime == 'bull':
                    multiplier = get_dynamic_trailing_multiplier(atr, atr_mean, regime)
                    stop_loss = max(stop_loss, price - multiplier * atr)

                # === Exit Conditions ===
                if price <= stop_loss or (regime != 'bull' and price >= take_profit) or signal == 'sell':
                    execute_trade('sell', price, position_size, stop_loss, take_profit)  # ✅ Pass all required data
                    send_alert(f"[BOT] SELL ORDER executed at {price}\nFinal Balance Updated")
                    print(f'Sold at {price}, Final Balance Updated')
                    position, position_size, stop_loss, take_profit = None, 0, None, None
                else:
                    send_alert('Trade not executed, conditions not met')
            else:
                print('Nothing happens')
            
        except Exception as e:
            error_msg = f'[BOT] ERROR: {str(e)}'
            send_alert(error_msg)
            print(error_msg)
        
        time.sleep(3600)  # Run every hour
