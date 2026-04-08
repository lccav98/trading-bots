"""
Prophet Integration for Trading Bots
Facebook's Prophet - works on regular PCs (4GB+ RAM)
"""

PROPHET_AVAILABLE = False
model = None

def load_prophet():
    """Load Prophet model"""
    global model, PROPHET_AVAILABLE
    
    try:
        from prophet import Prophet
        import pandas as pd
        
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05
        )
        
        PROPHET_AVAILABLE = True
        print("[Prophet] Model ready!")
        return True
        
    except Exception as e:
        print(f"[Prophet] Load error: {e}")
        return False

def forecast_prices(prices_list, periods=6):
    """
    Forecast next prices using Prophet
    
    Args:
        prices_list: List of historical close prices
        periods: Number of periods to forecast
    
    Returns:
        List of forecasted prices
    """
    if not PROPHET_AVAILABLE:
        return None
    
    try:
        import pandas as pd
        from prophet import Prophet
        
        # Prepare data for Prophet
        df = pd.DataFrame({
            'ds': pd.date_range(start='2024-01-01', periods=len(prices_list), freq='5min'),
            'y': prices_list
        })
        
        # Fit model
        m = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False
        )
        m.fit(df)
        
        # Make forecast
        future = m.make_future_dataframe(periods=periods, freq='5min')
        forecast = m.predict(future)
        
        # Return only the forecasted values
        predictions = forecast['yhat'].iloc[-periods:].tolist()
        return predictions
        
    except Exception as e:
        print(f"[Prophet] Forecast error: {e}")
        return None

def get_trend_direction(prices_list, threshold=0.0005):
    """
    Get trend direction from Prophet forecast
    
    Returns: "BUY", "SELL", or "HOLD"
    """
    forecasts = forecast_prices(prices_list, periods=6)
    
    if forecasts is None:
        return "HOLD"
    
    # Calculate average predicted change
    current = prices_list[-1]
    predicted_avg = sum(forecasts[:3]) / 3
    
    change_pct = (predicted_avg - current) / current
    
    if change_pct > threshold:
        return "BUY"
    elif change_pct < -threshold:
        return "SELL"
    return "HOLD"

# Quick test
if __name__ == "__main__":
    print("Prophet Integration Module")
    print("Install: pip install prophet")
    load_prophet()
    
    if PROPHET_AVAILABLE:
        # Test with sample data
        import numpy as np
        test_prices = np.random.uniform(5800, 5900, 50).tolist()
        trend = get_trend_direction(test_prices)
        print(f"Test trend: {trend}")