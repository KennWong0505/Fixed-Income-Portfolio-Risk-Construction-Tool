import pandas as pd
from src.bond import Bond

class Portfolio:
    def __init__(self, holdings, risk_free_curve, credit_spread):
        self.holdings = holdings
        self.risk_free_curve = risk_free_curve
        self.credit_spread = credit_spread
        self._assign_effective_yields()

    def _interpolated_rate(self, maturity):
        curve = self.risk_free_curve
        if maturity in curve.index:
            return curve.loc[maturity]
        return curve.reindex(curve.index.union([maturity])).interpolate(method='index').loc[maturity]

    def _assign_effective_yields(self):
        for b in self.holdings:
            rf = self._interpolated_rate(b['maturity'])
            spread = self.credit_spread[b['rating']].iloc[-1] if b['rating'] in self.credit_spread.columns else 0
            b['risk_free_rate'] = rf
            b['credit_spread'] = spread
            b['effective_yield'] = rf + spread   # rates already in decimal form

    def _bond_obj(self, b):
        return Bond(b['face_value'], b['coupon_rate'], b['maturity'])

    def market_values(self):
        values = []
        for b in self.holdings:
            bond = self._bond_obj(b)
            price = bond.price(b['effective_yield'])
            values.append({"name": b['name'], "price": price})
        total = sum(v["price"] for v in values)
        return values, total

    def weighted_duration(self):
        _, total = self.market_values()
        weighted = 0
        for b in self.holdings:
            bond = self._bond_obj(b)
            price = bond.price(b['effective_yield'])
            dur = bond.modified_duration(b['effective_yield'])
            weighted += dur * price / total
        return weighted

    def weighted_convexity(self):
        _, total = self.market_values()
        weighted = 0
        for b in self.holdings:
            bond = self._bond_obj(b)
            price = bond.price(b['effective_yield'])
            conv = bond.convexity(b['effective_yield'])
            weighted += conv * price / total
        return weighted

    def dv01(self):
        total_dv01 = 0
        for b in self.holdings:
            bond = self._bond_obj(b)
            price = bond.price(b['effective_yield'])
            mod_dur = bond.modified_duration(b['effective_yield'])
            total_dv01 += mod_dur * price * 0.0001
        return total_dv01

    def risk_decomposition(self, rate_vol=0.0005, spread_vol=0.0003):
        """
        rate_vol, spread_vol: typical daily volatility of each factor (decimal, e.g. 5bps/day for rates)
        Returns dollar DV01 to each factor AND volatility-weighted risk contribution.
        """
        results = []
        for b in self.holdings:
            bond = self._bond_obj(b)
            base_price = bond.price(b['effective_yield'])
            bump = 0.0001

            price_rate_bump = bond.price((b['risk_free_rate'] + bump) + b['credit_spread'])
            rate_dv01 = base_price - price_rate_bump

            price_spread_bump = bond.price(b['risk_free_rate'] + (b['credit_spread'] + bump))
            spread_dv01 = base_price - price_spread_bump

            results.append({
                "name": b['name'],
                "rate_dv01": rate_dv01,
                "spread_dv01": spread_dv01,
                "rate_risk_contribution": rate_dv01 * (rate_vol / bump),
                "spread_risk_contribution": spread_dv01 * (spread_vol / bump),
            })
        return results