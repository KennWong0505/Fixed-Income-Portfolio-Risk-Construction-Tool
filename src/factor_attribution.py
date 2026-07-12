"""
factor_attribution.py

MSCI Barra-style factor risk attribution for a fixed income portfolio.

Decomposes total portfolio variance into contributions from individual
risk factors: each point on the risk-free yield curve, and each credit
rating's spread level. This extends the single-bond rate/spread
decomposition attempted in Phase 2 (which was structurally limited by
the additive-yield Bond model) to the portfolio level using a proper
factor covariance matrix, rather than 1bp-for-both bump comparisons.

Units convention (IMPORTANT):
- All exposures (betas) are denominated as "dollar P&L per 1bp move"
  in the corresponding factor, i.e. DV01-style sensitivities.
- The covariance matrix is denominated in bps^2 (since it is computed
  directly from historical daily changes measured in bps).
- Because both exposures and the covariance matrix use "1bp" as the
  common unit of factor movement, the formula Var = beta^T @ Sigma @ beta
  is unit-consistent: the result is in dollars^2, representing portfolio
  P&L variance attributable to 1bp-scale co-movements in the factors.
- Do NOT mix a bps-scale covariance matrix with a decimal-scale exposure
  vector (or vice versa) -- this exact bug caused the Phase 2 market
  value error and the Phase 4 Monte Carlo scaling error. Always confirm
  both inputs share the same "1bp" unit convention before calling
  factor_risk_contributions().
"""

import numpy as np
import pandas as pd
from src.stress_test import _reprice_under_shock


def compute_factor_exposures(portfolio, bump=0.0001):
    """
    Compute the portfolio's dollar sensitivity (DV01-style exposure) to
    each individual risk factor, by bumping one factor at a time while
    holding all others fixed, then repricing the full portfolio.

    Parameters
    ----------
    portfolio : Portfolio
        The portfolio instance to evaluate, exposing risk_free_curve
        (indexed by maturity in years) and credit_spread (columns by rating).
    bump : float
        Size of the shock applied to a single factor, in decimal terms
        (default 0.0001 = 1bp).

    Returns
    -------
    list[float]
        Dollar P&L for a 1bp bump in each factor, ordered as:
        [rate_factor_1, rate_factor_2, ..., rate_factor_n,
         spread_factor_1, ..., spread_factor_m]
        matching the order of portfolio.risk_free_curve.index followed
        by portfolio.credit_spread.columns. This same ordering must be
        used when building the covariance matrix, or the two will be
        silently misaligned.
    """
    exposure_vector = []
    risk_free_curve = portfolio.risk_free_curve

    for maturity in risk_free_curve.index:
        shocked_curve = risk_free_curve.copy()
        shocked_curve[maturity] += bump
        result = _reprice_under_shock(portfolio, shocked_curve, portfolio.credit_spread)
        exposure_vector.append(result["pnl"])

    spread_curve = portfolio.credit_spread
    for rating in spread_curve.columns:
        shocked_spread = spread_curve.copy()
        shocked_spread[rating] += bump
        result = _reprice_under_shock(portfolio, portfolio.risk_free_curve, shocked_spread)
        exposure_vector.append(result["pnl"])

    return exposure_vector


def compute_covariance_matrix(rate_changes_bps, spread_changes_bps):
    """
    Compute the factor covariance matrix from historical daily changes.

    Parameters
    ----------
    rate_changes_bps : pd.DataFrame
        Daily changes in each yield curve maturity, in bps
        (e.g., rate_history_pct.diff().dropna() * 100).
    spread_changes_bps : pd.DataFrame
        Daily changes in each rating's credit spread, in bps.

    Returns
    -------
    pd.DataFrame
        Covariance matrix (n_factors x n_factors), in bps^2 units.

    CAUTION -- units and alignment:
    1. This function assumes both input DataFrames are already scaled to
       bps (not decimal, not percent). If either input is passed in a
       different scale, the resulting covariance matrix will silently be
       off by a scaling factor, which will NOT raise an error -- it will
       just produce a wrong (over- or under-stated) risk contribution.
    2. The column order of the returned matrix follows the column order
       of the concatenated [rate_changes_bps, spread_changes_bps] input.
       This order MUST match the order of the exposures vector returned
       by compute_factor_exposures() exactly, or the matrix multiplication
       in factor_risk_contributions() will pair the wrong exposure with
       the wrong factor variance/covariance.
    3. pd.concat aligns on the DataFrame index (dates). If rate_changes_bps
       and spread_changes_bps have different date ranges or missing dates,
       rows with any NaN will need to be dropped (via .dropna()) before
       calling .cov(), otherwise pandas' pairwise NaN handling in .cov()
       can produce a covariance matrix estimated from inconsistent sample
       sizes across factor pairs.
    """
    combined_changes = pd.concat([rate_changes_bps, spread_changes_bps], axis=1).dropna()
    cov_matrix = combined_changes.cov()
    return cov_matrix


def factor_risk_contributions(exposures, cov_matrix):
    """
    Decompose total portfolio variance into per-factor risk contributions.

    Implements: Var(Portfolio) = beta^T @ Sigma @ beta
    with each factor's contribution: RC_k = beta_k * (Sigma @ beta)_k

    These contributions sum exactly to total portfolio variance, so
    RC_percentage sums to 1.0 (100%) across all factors.

    Parameters
    ----------
    exposures : list[float] or np.ndarray
        Dollar P&L per 1bp move in each factor, from compute_factor_exposures().
    cov_matrix : pd.DataFrame or np.ndarray
        Factor covariance matrix in bps^2, from compute_covariance_matrix().
        Row/column order must match the order of `exposures` exactly.

    Returns
    -------
    tuple(list[float], list[float])
        RC_raw_dollar: dollar-variance contribution of each factor.
        RC_percentage: each factor's share of total portfolio variance (sums to 1.0).
    """
    exposures = np.asarray(exposures, dtype=float)
    cov_values = cov_matrix.values if hasattr(cov_matrix, "values") else np.asarray(cov_matrix)

    if cov_values.shape[0] != len(exposures):
        raise ValueError(
            f"Dimension mismatch: exposures has {len(exposures)} factors, "
            f"cov_matrix has {cov_values.shape[0]} -- check factor ordering."
        )

    sigma_beta = cov_values @ exposures          # (Sigma @ beta), computed once
    total_variance = exposures @ sigma_beta      # beta^T Sigma beta, scalar

    RC_raw_dollar = exposures * sigma_beta       # elementwise: beta_i * (Sigma @ beta)_i for all i at once
    RC_percentage = RC_raw_dollar / total_variance

    return RC_raw_dollar.tolist(), RC_percentage.tolist()