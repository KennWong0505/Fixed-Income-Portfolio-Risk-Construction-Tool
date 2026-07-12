import pytest
from src.bond import Bond

def test_par_bond_price():
    b = Bond(face_value=100, coupon_rate=0.07, years_to_maturity=3, freq=1)
    assert abs(b.price(0.07) - 100.0) < 1e-6

def test_zero_coupon_duration_equals_maturity():
    zero = Bond(face_value=100, coupon_rate=0.0, years_to_maturity=5, freq=1)
    assert abs(zero.macaulay_duration(0.05) - 5.0) < 1e-6

def test_ytm_roundtrip():
    b = Bond(face_value=100, coupon_rate=0.07, years_to_maturity=3, freq=1)
    price = b.price(0.05)
    assert abs(b.ytm(price) - 0.05) < 1e-4