from scipy.optimize import newton

class Bond:
    def __init__(self, face_value, coupon_rate, years_to_maturity, freq=2):
        self.face_value = face_value
        self.coupon_rate = coupon_rate
        self.years_to_maturity = years_to_maturity
        self.freq = freq

    def price(self, ytm):
        coupon_payment = self.face_value * self.coupon_rate / self.freq
        periods = int(round(self.years_to_maturity * self.freq))
        df = 1 / (1 + ytm / self.freq)
        price = sum(coupon_payment * df**t for t in range(1, periods + 1))
        price += self.face_value * df**periods
        return price

    def ytm(self, market_price, guess=0.05):
        return newton(lambda y: self.price(y) - market_price, guess)

    def macaulay_duration(self, ytm):
        coupon_payment = self.face_value * self.coupon_rate / self.freq
        periods = int(round(self.years_to_maturity * self.freq))
        df = 1 / (1 + ytm / self.freq)
        price = self.price(ytm)

        weighted_sum = sum(t * coupon_payment * df**t for t in range(1, periods + 1))
        weighted_sum += periods * self.face_value * df**periods

        return (weighted_sum / price) / self.freq

    def modified_duration(self, ytm):
        return self.macaulay_duration(ytm) / (1 + ytm / self.freq)

    def convexity(self, ytm):
        coupon_payment = self.face_value * self.coupon_rate / self.freq
        periods = int(round(self.years_to_maturity * self.freq))
        df = 1 / (1 + ytm / self.freq)
        price = self.price(ytm)

        weighted_sum = sum(t * (t + 1) * coupon_payment * df**t for t in range(1, periods + 1))
        weighted_sum += periods * (periods + 1) * self.face_value * df**periods

        return (weighted_sum / price) / (self.freq**2) / (1 + ytm / self.freq)**2