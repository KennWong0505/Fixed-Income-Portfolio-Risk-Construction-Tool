import pandas as pd
import numpy as np
from src.stress_test import _reprice_under_shock

MATURITY_MAP = {"1M": 1/12, "3M": 3/12, "6M": 6/12, "1Y": 1, "2Y": 2, "5Y": 5, "10Y": 10, "30Y": 30}

def historical_simulation_pnl(portfolio, rate_history, spread_history, lookback_days=250):
    pnl_records = []
    n = min(lookback_days, len(rate_history) - 1)
    for i in range(1, n + 1):
        rate_bps = (rate_history.iloc[i] - rate_history.iloc[i - 1]) * 100
        rate_bps.index = rate_bps.index.map(MATURITY_MAP)   # <-- fix: string labels -> maturity years

        spread_bps = (spread_history.iloc[i] - spread_history.iloc[i - 1]) * 100

        shocked_curve = portfolio.risk_free_curve + (rate_bps / 10000)
        shocked_spread = portfolio.credit_spread.copy()
        for rating in shocked_spread.columns:
            shocked_spread[rating] = shocked_spread[rating] + (spread_bps[rating] / 10000)

        result = _reprice_under_shock(portfolio, shocked_curve, shocked_spread)
        pnl_records.append(result)

    return pd.DataFrame(pnl_records)


def historical_var_es(pnl_array, confidence=0.99):
    sorted_pnl = np.sort(pnl_array)
    var_index = max(int((1 - confidence) * len(sorted_pnl)), 1)
    var_value = sorted_pnl[var_index - 1]
    es_value = sorted_pnl[:var_index].mean()
    return var_value, es_value


def monte_carlo_pnl(portfolio, rate_vol_by_maturity, spread_vol_by_rating, n_simulations=10000, correlation=None):
    maturities = portfolio.risk_free_curve.index.to_numpy(dtype=float)
    ratings = portfolio.credit_spread.columns
    n_factors = len(maturities) + len(ratings)

    if correlation is not None:
        std_devs = np.concatenate([rate_vol_by_maturity, spread_vol_by_rating])
        D = np.diag(std_devs)
        cov_matrix = D @ correlation @ D
        mean = np.zeros(n_factors)
        shocks = np.random.multivariate_normal(mean, cov_matrix, n_simulations)
    else:
        rate_shocks = np.random.normal(0, rate_vol_by_maturity, (n_simulations, len(maturities)))
        spread_shocks = np.random.normal(0, spread_vol_by_rating, (n_simulations, len(ratings)))
        shocks = np.hstack((rate_shocks, spread_shocks))

    pnl_records = []
    for i in range(n_simulations):
        rate_bps = shocks[i, :len(maturities)]
        spread_bps = shocks[i, len(maturities):]

        shocked_curve = portfolio.risk_free_curve + (rate_bps / 10000)
        shocked_spread = portfolio.credit_spread.copy()
        for j, rating in enumerate(ratings):
            shocked_spread[rating] = shocked_spread[rating] + (spread_bps[j] / 10000)

        result = _reprice_under_shock(portfolio, shocked_curve, shocked_spread)
        pnl_records.append(result)

    return pd.DataFrame(pnl_records)


def monte_carlo_var_es(pnl_array, confidence=0.99):
    return historical_var_es(pnl_array, confidence)