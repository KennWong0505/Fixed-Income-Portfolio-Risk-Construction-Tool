import os
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()
api_key = os.getenv("FRED_API_KEY")
fred = Fred(api_key=api_key)

TREASURY_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}

def get_yield_curve_history(start_date="2015-01-01"):
    data = {}
    for label, code in TREASURY_SERIES.items():
        data[label] = fred.get_series(code, observation_start=start_date)
    df = pd.DataFrame(data)
    df.index.name = "date"
    return df.dropna(how="all")

def get_bond_etf_prices(tickers=["LQD", "HYG", "TLT"], start="2015-01-01"):
    data = yf.download(tickers, start=start)["Close"]
    return data.dropna(how="all")

CREDIT_SPREAD_SERIES = {
    "AAA": "BAMLC0A1CAAA",
    "A":   "BAMLC0A3CA",
    "BBB": "BAMLC0A4CBBB",
    "HY":  "BAMLH0A0HYM2",
}

def get_credit_spreads(start_date="2015-01-01"):
    data = {label: fred.get_series(code, observation_start=start_date)
            for label, code in CREDIT_SPREAD_SERIES.items()}
    df = pd.DataFrame(data) / 100   # convert percent to decimal, consistent with yield curve
    df.index.name = "date"
    return df.dropna(how="all")

# The structure of the risk free curve
def get_latest_curve_by_maturity(curve_df):
    latest_row = curve_df.dropna().iloc[-1]
    maturity_map = {"1M": 1/12, "3M": 3/12, "6M": 6/12, "1Y": 1, "2Y": 2, "5Y": 5, "10Y": 10, "30Y": 30}
    curve = pd.Series({maturity_map[label]: val/100 for label, val in latest_row.items()})
    return curve.sort_index()