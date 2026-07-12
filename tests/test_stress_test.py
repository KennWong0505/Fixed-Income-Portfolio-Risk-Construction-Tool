import pytest
import pandas as pd
from src.portfolio import Portfolio
from src.stress_test import parallel_shock, compare_to_duration_approximation

@pytest.fixture
def sample_portfolio():
    holdings = [
        {"name": "TestBond", "face_value": 1_000_000, "coupon_rate": 0.04, "maturity": 5, "rating": "AAA"},
    ]
    risk_free_curve = pd.Series({1: 0.03, 2: 0.035, 5: 0.04, 10: 0.045, 30: 0.05})
    credit_spread = pd.DataFrame({"AAA": [0.005]}, index=[pd.Timestamp("2026-01-01")])
    return Portfolio(holdings, risk_free_curve, credit_spread)

def test_shock_increases_with_size(sample_portfolio):
    mild = parallel_shock(sample_portfolio, 5, {"AAA": 1})
    severe = parallel_shock(sample_portfolio, 100, {"AAA": 20})
    assert abs(severe["pnl"]) > abs(mild["pnl"])

def test_convexity_gap_grows(sample_portfolio):
    mild_gap = compare_to_duration_approximation(sample_portfolio, 5)
    severe_gap = compare_to_duration_approximation(sample_portfolio, 100)
    assert abs(severe_gap["pnl_gap_pct"]) > abs(mild_gap["pnl_gap_pct"])