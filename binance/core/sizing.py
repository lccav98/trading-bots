def position_size_kelly(balance, base_fraction, score, max_fraction=0.45, min_size=1.0):
    multipliers = {1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.0}
    mult = multipliers.get(min(score, 5), 1.0)
    size = balance * base_fraction * mult
    size = min(size, balance * max_fraction)
    return max(min_size, round(size, 2))


def position_size_risk(balance, risk_pct, entry_price, stop_loss_pct, max_fraction=0.95):
    risk_amount = balance * risk_pct
    size_from_risk = risk_amount / (stop_loss_pct + 1e-10)
    size = min(size_from_risk, balance * max_fraction)
    return max(1.0, round(size, 2))