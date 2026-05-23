import numpy as np
import pandas as pd


class Indicators:

    @staticmethod
    def ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(close, period=14):
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def stoch_rsi(close, rsi_period=14, stoch_period=14, k_smooth=3, d_smooth=3):
        rsi = Indicators.rsi(close, rsi_period)
        rsi_min = rsi.rolling(stoch_period).min()
        rsi_max = rsi.rolling(stoch_period).max()
        stoch = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
        k = stoch.rolling(k_smooth).mean()
        d = k.rolling(d_smooth).mean()
        return k, d

    @staticmethod
    def atr(high, low, close, period=14):
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def adx(high, low, close, period=14):
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)

        dm_plus = high.diff()
        dm_minus = -low.diff()
        dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0.0)
        dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0.0)

        atr_val = tr.rolling(period).mean()
        di_plus = 100 * dm_plus.rolling(period).mean() / (atr_val + 1e-10)
        di_minus = 100 * dm_minus.rolling(period).mean() / (atr_val + 1e-10)
        dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-10)
        return dx.rolling(period).mean(), di_plus, di_minus

    @staticmethod
    def vwap(high, low, close, volume):
        typical = (high + low + close) / 3
        return (typical * volume).cumsum() / (volume.cumsum() + 1e-10)

    @staticmethod
    def bollinger_bands(close, period=20, num_std=2.0):
        mid = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = mid + num_std * std
        lower = mid - num_std * std
        return upper, mid, lower

    @staticmethod
    def bb_squeeze(close, period=20, bb_std=2.0, kc_mult=1.5):
        upper, mid, lower = Indicators.bollinger_bands(close, period, bb_std)
        high_val = close.rolling(2).max()
        low_val = close.rolling(2).min()
        tr = pd.concat([
            high_val - low_val,
            (high_val - close.shift()).abs(),
            (low_val - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr_val = tr.rolling(period).mean()
        kc_upper = mid + kc_mult * atr_val
        kc_lower = mid - kc_mult * atr_val
        squeeze = (upper < kc_upper) & (lower > kc_lower)
        bandwidth = (upper - lower) / (mid + 1e-10)
        return squeeze, bandwidth, upper, lower, mid

    @staticmethod
    def rsi_divergence(close, rsi_series, lookback=20):
        if len(close) < lookback + 2:
            return None, 0.0
        recent_close = close.iloc[-lookback:]
        recent_rsi = rsi_series.iloc[-lookback:]
        close_min_idx = recent_close.idxmin()
        close_max_idx = recent_close.idxmax()
        rsi_min_idx = recent_rsi.idxmin()
        rsi_max_idx = recent_rsi.idxmax()
        if close_min_idx == close.iloc[-1] or close_max_idx == close.iloc[-1]:
            return None, 0.0
        if recent_rsi.iloc[-1] < 35:
            if close_min_idx == recent_close.idxmin() and rsi_min_idx != close_min_idx:
                if recent_rsi.iloc[-1] > recent_rsi.loc[close_min_idx]:
                    return 'bullish', 0.3
        if recent_rsi.iloc[-1] > 65:
            if close_max_idx == recent_close.idxmax() and rsi_max_idx != close_max_idx:
                if recent_rsi.iloc[-1] < recent_rsi.loc[close_max_idx]:
                    return 'bearish', 0.3
        return None, 0.0


def check_mtf_trend(df_htf, direction='long'):
    if df_htf is None or len(df_htf) < 30:
        return True, 0.0
    close = df_htf['close']
    ema8 = Indicators.ema(close, 8)
    ema21 = Indicators.ema(close, 21)
    ema50 = Indicators.ema(close, 50)
    c = close.iloc[-2]
    e8, e21, e50 = ema8.iloc[-2], ema21.iloc[-2], ema50.iloc[-2]
    if direction == 'long':
        aligned = c > e8 > e21 > e50
        strength = (e8 - e21) / e21 + (e21 - e50) / e50 if e21 > 0 and e50 > 0 else 0
    else:
        aligned = c < e8 < e21 < e50
        strength = (e21 - e8) / e21 + (e50 - e21) / e21 if e21 > 0 and e50 > 0 else 0
    return aligned, abs(strength)


def analyze_momentum(df, params, direction='long', df_htf=None):
    close = df['close']
    high = df['high']
    low = df['low']
    vol = df['volume']

    ema5 = Indicators.ema(close, 5)
    ema10 = Indicators.ema(close, 10)
    ema21 = Indicators.ema(close, 21)

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rsi = 100 - (100 / (1 + gain / (loss + 1e-10)))
    rsi_min = rsi.rolling(7).min()
    rsi_max = rsi.rolling(7).max()
    stoch = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    stoch_k = stoch.rolling(3).mean()

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(7).mean()
    atr_avg = atr.rolling(50).mean()

    ema20 = Indicators.ema(close, 20)

    hd = high.diff()
    ld = (-low.diff())
    dm_plus = pd.Series(np.where((hd > ld) & (hd > 0), hd, 0), index=df.index)
    dm_minus = pd.Series(np.where((ld > hd) & (ld > 0), ld, 0), index=df.index)
    atr14 = tr.rolling(14).sum()
    di_plus = 100 * dm_plus.rolling(14).sum() / (atr14 + 1e-10)
    di_minus = 100 * dm_minus.rolling(14).sum() / (atr14 + 1e-10)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-10)
    adx_line = dx.rolling(14).mean()

    squeeze, bb_width, bb_upper, bb_lower, bb_mid = Indicators.bb_squeeze(close, 20, 2.0, 1.5)
    div_type, div_score = Indicators.rsi_divergence(close, rsi)

    IDX = -2
    price = close.iloc[IDX]
    c1 = close.pct_change(1).iloc[IDX]
    c5 = close.pct_change(5).iloc[IDX]
    atr_now = atr.iloc[IDX]
    atr_base = atr_avg.iloc[IDX]
    rsi_now = rsi.iloc[IDX]
    stoch_now = stoch_k.iloc[IDX]
    adx_now = adx_line.iloc[IDX]

    vwap_now = ema20.iloc[IDX]
    vwap_slope = ema20.iloc[IDX] - ema20.iloc[IDX - 5]

    ema_bull = (ema5.iloc[IDX] > ema10.iloc[IDX] > ema21.iloc[IDX])
    ema_bear = (ema5.iloc[IDX] < ema10.iloc[IDX] < ema21.iloc[IDX])
    atr_ok = atr_now <= atr_base * params['atr_mult'] if not np.isnan(atr_base) else True

    vol_now = vol.iloc[IDX]
    vol_avg = vol.rolling(20).mean().iloc[IDX]
    vol_ratio = float(vol_now / vol_avg) if vol_avg and not np.isnan(vol_avg) and vol_avg > 0 else 1.0
    vol_ok = vol_ratio >= params.get('vol_min_ratio', 1.5)

    adx_ok = np.isnan(adx_now) or adx_now > params.get('adx_thresh', 22)

    mtf_aligned, mtf_strength = check_mtf_trend(df_htf, direction) if df_htf is not None else (True, 0.0)
    mtf_bonus = mtf_strength * 0.5 if mtf_aligned else 0.0

    squeeze_active = bool(squeeze.iloc[IDX]) if not np.isnan(squeeze.iloc[IDX]) else False
    bb_w_now = float(bb_width.iloc[IDX]) if not np.isnan(bb_width.iloc[IDX]) else 0.0

    if direction == 'long':
        long_mom = c1 > params['c1_thresh'] and c5 > params['c5_thresh']
        long_ema = ema_bull if params.get('use_ema', True) else True
        long_fomo = (np.isnan(rsi_now) or rsi_now < params.get('rsi_max', 70)) and \
            (np.isnan(stoch_now) or stoch_now < params.get('stoch_max', 80))
        long_vwap = (price > vwap_now and vwap_slope > 0) if not np.isnan(vwap_now) else True

        if long_mom and long_ema and atr_ok and vol_ok and long_fomo and long_vwap and adx_ok:
            signal = 'buy'
            score = float(c5) + float(c1) * 0.5
            if ema_bull: score += 0.002
            if not np.isnan(adx_now) and adx_now > 30: score += 0.001
            score += mtf_bonus
            if mtf_aligned: score += 0.002
            if div_type == 'bullish': score += div_score
        elif long_mom and long_fomo and atr_ok and not mtf_aligned and not squeeze_active:
            signal = 'buy'
            score = float(c5) + float(c1) * 0.5
            score *= 0.6
        else:
            signal = 'neutral'
            score = 0.0
    else:
        short_mom = c1 < -params['c1_thresh'] and c5 < -params['c5_thresh']
        short_ema = ema_bear if params.get('use_ema', True) else True
        short_not_ob = np.isnan(rsi_now) or rsi_now > params.get('rsi_short_min', 40)
        short_not_ob_st = np.isnan(stoch_now) or stoch_now > params.get('stoch_short_min', 40)
        short_vwap = (price < vwap_now and vwap_slope < 0) if not np.isnan(vwap_now) else True
        not_oversold = np.isnan(rsi_now) or rsi_now > 25

        if (short_mom and short_ema and atr_ok and vol_ok
            and short_not_ob and short_not_ob_st
            and short_vwap and adx_ok and not_oversold):
            signal = 'sell'
            score = float(-c5) + float(-c1) * 0.5
            if ema_bear: score += 0.002
            if not np.isnan(adx_now) and adx_now > 30: score += 0.001
            score += mtf_bonus
            if mtf_aligned: score += 0.002
            if div_type == 'bearish': score += div_score
        elif short_mom and short_not_ob and atr_ok and not mtf_aligned and not squeeze_active:
            signal = 'sell'
            score = float(-c5) + float(-c1) * 0.5
            score *= 0.6
        else:
            signal = 'neutral'
            score = 0.0

    return signal, score, {
        'price': price, 'c1': c1, 'c5': c5,
        'vol_ratio': vol_ratio, 'rsi': rsi_now, 'stoch': stoch_now,
        'adx': adx_now, 'ema20': vwap_now,
        'mtf_aligned': mtf_aligned, 'mtf_strength': mtf_strength,
        'squeeze': squeeze_active, 'bb_width': bb_w_now,
        'divergence': div_type,
    }