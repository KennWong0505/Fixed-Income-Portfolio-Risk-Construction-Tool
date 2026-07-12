import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import plotly.graph_objects as go

from src.data_loader import get_yield_curve_history, get_credit_spreads, get_latest_curve_by_maturity
from src.portfolio import Portfolio
from src.stress_test import parallel_shock
from src.var_es import historical_simulation_pnl, historical_var_es
from src.factor_attribution import compute_factor_exposures, compute_covariance_matrix, factor_risk_contributions

app = FastAPI(
    title="Fixed Income Portfolio Risk Tool API",
    description="An API for calculating risk metrics and performing stress tests on fixed income portfolios.",
    version="1.0.0",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Step 1: Build the portfolio once, cache it at module load time ---
curve_history_pct = get_yield_curve_history()
spread_history_pct = get_credit_spreads() * 100  # percent scale, for historical P&L bps conversion

risk_free_curve = get_latest_curve_by_maturity(curve_history_pct)
credit_spread = spread_history_pct / 100  # decimal scale, for Portfolio pricing

holdings = [
    {"name": "UST_2Y",  "face_value": 1_000_000, "coupon_rate": 0.04, "maturity": 2,  "rating": "AAA"},
    {"name": "UST_10Y", "face_value": 500_000,   "coupon_rate": 0.045,"maturity": 10, "rating": "AAA"},
    {"name": "Corp_A_5Y",  "face_value": 300_000, "coupon_rate": 0.05, "maturity": 5,  "rating": "A"},
    {"name": "Corp_BBB_7Y","face_value": 400_000, "coupon_rate": 0.06, "maturity": 7,  "rating": "BBB"},
    {"name": "HY_3Y",      "face_value": 200_000, "coupon_rate": 0.08, "maturity": 3,  "rating": "HY"},
]

portfolio = Portfolio(holdings, risk_free_curve, credit_spread)

rate_changes_bps = curve_history_pct.diff().dropna() * 100
spread_changes_bps = spread_history_pct.diff().dropna() * 100


# --- Step 2: Plotly chart builder (explained below) ---
def build_factor_chart(factor_names, rc_percentage):
    fig = go.Figure(data=[
        go.Bar(x=factor_names, y=[p * 100 for p in rc_percentage])
    ])
    fig.update_layout(
        title="Factor Risk Contribution (% of Total Portfolio Variance)",
        xaxis_title="Risk Factor",
        yaxis_title="% of Total Risk",
        template="plotly_white",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


# --- Step 3: main dashboard route ---
@app.get("/")
def dashboard(request: Request):
    values, total_market_value = portfolio.market_values()
    weighted_duration = portfolio.weighted_duration()
    weighted_convexity = portfolio.weighted_convexity()
    dv01 = portfolio.dv01()

    moderate = parallel_shock(portfolio, rate_bps=50, spread_bps_by_rating={"AAA": 11, "A": 13, "BBB": 15, "HY": 70})

    hist_pnl_df = historical_simulation_pnl(portfolio, curve_history_pct, spread_history_pct, lookback_days=250)
    hist_var, hist_es = historical_var_es(hist_pnl_df["pnl"].values, confidence=0.99)

    exposures = compute_factor_exposures(portfolio)
    cov_matrix = compute_covariance_matrix(rate_changes_bps, spread_changes_bps)
    RC_dollar, RC_pct = factor_risk_contributions(exposures, cov_matrix)

    factor_names = [str(m) for m in portfolio.risk_free_curve.index] + list(portfolio.credit_spread.columns)
    factor_chart_html = build_factor_chart(factor_names, RC_pct)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "holdings_values": values,
            "total_market_value": total_market_value,
            "weighted_duration": weighted_duration,
            "weighted_convexity": weighted_convexity,
            "dv01": dv01,
            "moderate": moderate,
            "hist_var": hist_var,
            "hist_es": hist_es,
            "factor_chart_html": factor_chart_html,
        },
    )