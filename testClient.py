import csv
class TestClient:
    def __init__(self, USDT, atr_multiplier=1.5):
        self.USDT = USDT
        self.BTC = 0
        self.tradeCount = 0
        self.profitableTrades = 0
        self.unprofitableTrades = 0
        self.brakeEvenTrades = 0
        self.trade_log = []
        
        self.position = None  # "long" or "short"
        self.position_size = 0
        self.entry_price = None #price were the current position started
        self.stop_loss = None
        self.take_profit = None
        self.atr_multiplier = atr_multiplier

    
    def modify_position(self, action, price, size_percentage=1.0):
        size = (self.USDT * size_percentage) / price  # BTC amount to trade
        
        if action == "buy":
            if self.position == "short":
                self.reduce_position(price, size)
            else:
                self.open_position("long", price, size)
        
        elif action == "sell":
            if self.position == "long":
                self.close_position(price, size)
            else:
                self.open_position("short", price, size)
    
    def check_margin(self, price):
        total_margin = self.USDT + (self.BTC * price)
        
        if self.position == 'long':
            unrealized_loss = (self.entry_price - price) * abs(self.BTC)  # Loss in USDT
            return unrealized_loss <= total_margin
        
        elif self.position == 'short':
            unrealized_loss = (price - self.entry_price) * abs(self.BTC)  # Loss in USDT
            return unrealized_loss <= total_margin

        return True  # No position, so no margin issues


    def open_position(self, direction, price, regime, strenght, dateTime):
        if self.USDT <= 0 or self.position is not None:
            return  # No money to open or already in a position
        
        size = self.USDT / price  # Use all USDT to determine position size
        
        if size < 0.001:
            return  # Prevent opening if size is too small
        
        cost = size * price
        
        if direction == "long":
            self.BTC += size
            self.USDT -= cost
        else:  # Short position
            self.BTC -= size  # Simulating borrowed BTC
            self.USDT += cost  # Selling borrowed BTC
        
        self.position = direction
        self.position_size = size
        self.entry_price = price
        self.tradeCount += 1
        self.trade_log.append((dateTime, direction, price, size, self.USDT, self.BTC, regime, strenght, self.stop_loss, self.take_profit))

    def close_position(self, price, regime, strength, dateTime):
        if self.position is None:
            return  # No position to close
        
        size = self.position_size
        cost = size * price  # Total cost to close position
        
        if self.position == "long":
            self.BTC -= size  # Sell all BTC
            self.USDT += cost  # Receive USDT

            if price > self.entry_price:
                self.profitableTrades += 1
            elif price < self.entry_price:
                self.unprofitableTrades += 1
            else:
                self.brakeEvenTrades += 1
        else:  # Short position
            self.BTC += size  # Buy back BTC
            self.USDT -= cost  # Pay USDT to buy BTC back

            if price < self.entry_price:
                self.profitableTrades += 1
            elif price > self.entry_price:
                self.unprofitableTrades += 1
            else:
                self.brakeEvenTrades += 1
        
        # Reset position
        self.position = None
        self.position_size = 0
        self.entry_price = None
        
        self.trade_log.append((dateTime, "close", price, size, self.USDT, self.BTC, regime, strength))


    def register_trade(self, action, BTC_value, datetime):
        row = [datetime, BTC_value, action, self.USDT, self.BTC]
        self.trade_log.append(row)  # Save trade
    
    def get_summary(self):
        totalTrades = self.profitableTrades + self.unprofitableTrades + self.brakeEvenTrades
        winRate = (self.profitableTrades / totalTrades) * 100 if totalTrades > 0 else 0
        final_balance = self.USDT
        final_btc = self.BTC  # Assuming BTC is always sold at the end
        return {
            "Final Balance (USDT)": int(final_balance),
            'BTC': float(final_btc),
            "Total Trades": totalTrades,
            "Profitable Trades": self.profitableTrades,
            "Unprofitable Trades": self.unprofitableTrades,
            "Win Rate (%)": round(winRate, 2),
        }
    
    def export_trade_log_to_csv(self, filename="trade_log.csv"):
        # Writing the trade log to a CSV file
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            # Write the header
            writer.writerow(['DateTime', 'Direction', 'Price', 'Size', 'USDT', 'BTC', 'Regime', 'Strength', 'StopLoss', 'TakeProfit'])
            
            # Write each trade log entry
            for log in self.trade_log:
                writer.writerow(log)

        print(f"Trade log has been exported to {filename}")