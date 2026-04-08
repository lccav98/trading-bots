"""
TimesFM Integration for Trading Bots
Google's Time Series Foundation Model for price forecasting
"""

import os
import numpy as np

TIMESFM_AVAILABLE = False

def load_timesfm():
    """Load TimesFM model (requires 32GB RAM minimum)"""
    global timesfm, TIMESFM_AVAILABLE
    
    try:
        import timesfm
        from timesfm import TimesFm, TimesFmHparams, TimesFmCheckpoint
        
        print("[TimesFM] Loading model (may take 1-2 minutes)...")
        
        # Load smaller model first (200M)
        tfm = TimesFm(
            hparams=TimesFmHparams(
                backend="cpu",
                per_core_batch_size=32,
                horizon_len=12,  # 12 periods ahead
                context_len=512,  # 512 periods of history
            ),
            checkpoint=TimesFmCheckpoint(
                huggingface_repo_id="google/timesfm-1.0-200m-pytorch"
            )
        )
        
        timesfm = tfm
        TIMESFM_AVAILABLE = True
        print("[TimesFM] Model loaded successfully!")
        return True
        
    except ImportError as e:
        print(f"[TimesFM] Not installed: {e}")
        print("[TimesFM] Install with: pip install timesfm[torch]")
        return False
    except Exception as e:
        print(f"[TimesFM] Error loading model: {e}")
        return False

def forecast_prices(prices, horizon=12, freq=0):
    """
    Use TimesFM to forecast next prices
    
    Args:
        prices: List or array of historical prices
        horizon: Number of periods to forecast
        freq: 0=high (daily/minutely), 1=medium (weekly/monthly), 2=low (quarterly)
    
    Returns:
        List of forecasted prices
    """
    if not TIMESFM_AVAILABLE:
        return None
    
    try:
        # Prepare input
        input_series = [np.array(prices[-512:], dtype=float)]  # Use last 512 points
        freq_input = [freq]  # High frequency for intraday
        
        # Forecast
        point_forecast, _ = timesfm.forecast(
            input_series,
            freq=freq_input,
            horizon_len=horizon
        )
        
        return point_forecast[0].tolist()
        
    except Exception as e:
        print(f"[TimesFM] Forecast error: {e}")
        return None

def get_trend_signal(prices, threshold=0.001):
    """
    Get trend direction from TimesFM forecast
    
    Returns:
        "BUY" if trend up, "SELL" if trend down, "HOLD" if unclear
    """
    if not TIMESFM_AVAILABLE:
        return "HOLD"
    
    forecasts = forecast_prices(prices, horizon=6, freq=0)
    
    if forecasts is None or len(forecasts) < 3:
        return "HOLD"
    
    # Calculate average trend
    avg_forecast = sum(forecasts[:3]) / 3
    current_price = prices[-1]
    
    change_pct = (avg_forecast - current_price) / current_price
    
    if change_pct > threshold:
        return "BUY"
    elif change_pct < -threshold:
        return "SELL"
    else:
        return "HOLD"

# Auto-load on import
if __name__ != "__main__":
    pass  # Don't auto-load, requires explicit call