import copy
import numpy as np
from src.portfolio import Portfolio


def _reprice_under_shock(portfolio, shocked_curve, shocked_spread):
    """Shared helper: clone holdings, build a shocked Portfolio, compare market values."""
    shocked_holdings = copy.deepcopy(portfolio.holdings)
    shocked_portfolio = Portfolio(shocked_holdings, shocked_curve, shocked_spread)

    _, base_value = portfolio.market_values()
    _, shocked_value = shocked_portfolio.market_values()

    return {
        "base_value": base_value,
        "shocked_value": shocked_value,
        "pnl": shocked_value - base_value,
        "pnl_pct": (shocked_value - base_value) / base_value,
    }


def parallel_shock(portfolio, rate_bps, spread_bps_by_rating):
    """
    Shift every maturity on the risk-free curve by rate_bps,
    and each rating bucket's spread by its own bps amount.
    Tests overall duration/level risk.
    """
    shocked_curve = portfolio.risk_free_curve + (rate_bps / 10000)

    shocked_spread = portfolio.credit_spread.copy()
    for rating, bps in spread_bps_by_rating.items():
        if rating in shocked_spread.columns:
            shocked_spread[rating] = shocked_spread[rating] + (bps / 10000)

    return _reprice_under_shock(portfolio, shocked_curve, shocked_spread)


def curve_twist(portfolio, short_end_bps, long_end_bps, short_anchor=2, long_anchor=30):
    """
    Smoothly interpolate the shock size between short_anchor and long_anchor maturities,
    instead of an abrupt step. Maturities below short_anchor get short_end_bps,
    maturities above long_anchor get long_end_bps, and everything in between is
    linearly interpolated. Tests curve-shape (steepening/flattening) risk.
    """
    shocked_curve = portfolio.risk_free_curve.copy()
    maturities = shocked_curve.index.to_numpy(dtype=float)

    shock_bps = np.interp(maturities, [short_anchor, long_anchor], [short_end_bps, long_end_bps])
    shocked_curve = shocked_curve + (shock_bps / 10000)

    return _reprice_under_shock(portfolio, shocked_curve, portfolio.credit_spread)


def credit_widening(portfolio, spread_bps_by_rating):
    """
    Leave risk_free_curve untouched; shock only credit spreads by rating.
    Isolates pure credit stress.
    """
    shocked_spread = portfolio.credit_spread.copy()
    for rating, bps in spread_bps_by_rating.items():
        if rating in shocked_spread.columns:
            shocked_spread[rating] = shocked_spread[rating] + (bps / 10000)

    return _reprice_under_shock(portfolio, portfolio.risk_free_curve, shocked_spread)


def compare_to_duration_approximation(portfolio, rate_bps):
    """
    Compare full-repricing P&L (parallel_shock) against the duration+convexity
    formula estimate, using base-case duration/convexity as the starting point.
    """
    shocked_curve = portfolio.risk_free_curve + (rate_bps / 10000)
    result = _reprice_under_shock(portfolio, shocked_curve, portfolio.credit_spread)

    dur = portfolio.weighted_duration()
    conv = portfolio.weighted_convexity()
    delta_y = rate_bps / 10000

    approx_pnl_pct = -dur * delta_y + 0.5 * conv * (delta_y ** 2)
    approx_pnl = approx_pnl_pct * result["base_value"]

    return {
        "base_value": result["base_value"],
        "actual_shocked_value": result["shocked_value"],
        "actual_pnl": result["pnl"],
        "actual_pnl_pct": result["pnl_pct"],
        "approx_pnl": approx_pnl,
        "approx_pnl_pct": approx_pnl_pct,
        "pnl_gap": result["pnl"] - approx_pnl,
        "pnl_gap_pct": result["pnl_pct"] - approx_pnl_pct,
    }