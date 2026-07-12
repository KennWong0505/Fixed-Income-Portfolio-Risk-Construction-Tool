import pytest
import pandas as pd
from src.portfolio import Portfolio

@pytest.fixture
def sample_portfolio():
    holdings = [
        {"name": "TestBond", "face_value": 1_000_000, "coupon_rate": 0.04, "maturity": 5, "rating": "AAA"},
    ]
    risk_free_curve = pd.Series({1: 0.03, 2: 0.035, 5: 0.04, 10: 0.045, 30: 0.05})
    credit_spread = pd.DataFrame({"AAA": [0.005]}, index=[pd.Timestamp("2026-01-01")])
    return Portfolio(holdings, risk_free_curve, credit_spread)

def test_market_value_near_face_value(sample_portfolio):
    _, total = sample_portfolio.market_values()
    assert 900_000 < total < 1_100_000

def test_dv01_positive(sample_portfolio):
    assert sample_portfolio.dv01() > 0