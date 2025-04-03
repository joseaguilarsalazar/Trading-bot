def check_signal(last, regime, trend_strength, atr_pct, position=None):
    """
    Determines trading actions based on market regime and technical indicators.
    
    Parameters:
    - last: Dict containing latest indicator values (ema_short, ema_long, atr, atr_mean)
    - regime: String indicating market regime ("strong_bull", "bull", "sideways", "weak_bear", "strong_bear")
    - avg_diff: Average difference between EMAs (unused in current implementation but kept for future use)
    - trend_strength: Float between 0-1 indicating trend strength
    - atr_pct: ATR as percentage of its mean (volatility measure)
    - position: String indicating current position ("long", "short", or None for no position)
    
    Returns:
    - Dict containing action details or None if no action required
    """
    # Input validation
    if last is None or last.empty or trend_strength is None or atr_pct is None:
        return None
    
    # Extract technical indicators
    atr_mean = last.get('atr_mean', 0)
    atr = last.get('atr', 0)
    atr_is_calm = atr < atr_mean  # Checks for low volatility
    
    momentum_up = last.get('ema_short', 0) > last.get('ema_long', 0)
    momentum_down = last.get('ema_short', 0) < last.get('ema_long', 0)
    
    # Calculate position size based on volatility (inverse relationship)
    position_size = min(1.0, 1.5 / atr_pct) if atr_pct > 0 else 0.5
    
    # Result template
    result = {
        "action": None,
        "regime": regime,
        "strength": trend_strength,
        "volatility": atr_pct,
        "size": position_size
    }


    # === 🚀 Strong Bull Market ===
    if regime == "strong_bull":
        if position is None:
            # Buy aggressively on trend confirmation
            if momentum_up and trend_strength > 0.8:
                result["action"] = "open_long"
                return result
        elif position == "long":
            # Take partial profits in extreme volatility
            if atr_pct > 2.0 and trend_strength > 0.9:
                result["action"] = "close_long"
                result["size"] = 0.3
                return result
            # Exit only on **strong** bearish signals
            elif momentum_down and trend_strength < 0.5:
                result["action"] = "close_long"
                return result
        elif position == "short":
            # Cover shorts quickly in strong bull market
            if momentum_up or atr_is_calm:
                result["action"] = "close_short"
                return result
    
    # === 📈 Normal Bull Market ===
    if regime == "bull":
        if position is None:
            # Buy **only on pullbacks**, avoiding overbought conditions
            if momentum_up and trend_strength > 0.6 and atr_pct < 1.5:
                result["action"] = "open_long"
                return result
        elif position == "long":
            # Take partial profits when volatility spikes
            if atr_pct > 1.8:
                result["action"] = "close_long"
                result["size"] = 0.5  # Reduce by 50%
                return result
            # Sell on **weaker bearish signs** than in strong bull
            elif momentum_down and trend_strength < 0.4:
                result["action"] = "close_long"
                return result
        elif position == "short":
            # Close shorts in bullish conditions
            if momentum_up:
                result["action"] = "close_short"
                return result
    
    # === 📊 Sideways Market ===
    if regime == "sideways":
        if position is None:
            # Buy **only if ATR is calm** (avoid choppy markets)
            if momentum_up and atr_is_calm:
                result["action"] = "open_long"
                # Smaller position in sideways market
                result["size"] = position_size * 0.7
                return result
            # Consider shorting on significant breakdowns in sideways markets
            elif momentum_down and atr_pct > 1.2:
                result["action"] = "open_short"
                result["size"] = position_size * 0.5  # More conservative sizing for shorts
                return result
        elif position == "long":
            # Sell **as soon as momentum weakens**
            if momentum_down:
                result["action"] = "close_long"
                return result
        elif position == "short":
            # Cover shorts when momentum shifts up
            if momentum_up:
                result["action"] = "close_short"
                return result
    
    # === 📉 Weak Bear Market ===
    if regime == "weak_bear":
        if position is None:
            # Only short when momentum confirms and ATR is rising (volatility increasing)
            if momentum_down and atr_pct > 1.0:
                result["action"] = "open_short"
                return result
            # Potentially look for counter-trend long opportunities
            elif momentum_up and atr_is_calm and trend_strength > 0.7:
                result["action"] = "open_long"
                result["size"] = position_size * 0.6  # Smaller position for counter-trend
                return result
        elif position == "long":
            # Exit longs on weakening uptrend
            if momentum_down:
                result["action"] = "close_long"
                return result
        elif position == "short":
            # Take profits on shorts when volatility extreme
            if atr_pct > 2.0:
                result["action"] = "close_short"
                result["size"] = 0.4  # Reduce by 40%
                return result
            # Exit on weakening downtrend
            elif momentum_up:
                result["action"] = "close_short"
                return result
    
    # === ⚠️ Strong Bear Market ===
    if regime == "strong_bear":
        if position is None:
            # Short aggressively when short EMA confirms breakdown
            if momentum_down:  # ATR > 150% of avg means strong move
                result["action"] = "open_short"
                return result
        elif position == "long":
            # Exit longs quickly in strong bear market
            if momentum_down or atr_pct > 1.3:
                result["action"] = "close_long"
                return result
        elif position == "short":
            # Take partial profits on strong moves down
            if momentum_down and atr_pct > 2.5:
                result["action"] = "close_short"
                result["size"] = 0.5  # Take half profits
                return result
            # Exit only if clear trend shift occurs (momentum reversal)
            elif momentum_up and atr_pct < 1.0:  # ATR cooling down signals potential reversal
                result["action"] = "close_short"
                return result
        return None

    # Default - no action
    return None