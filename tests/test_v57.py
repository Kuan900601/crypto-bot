"""
v57 回歸測試：funding_extreme 單位修正、px_round 低價幣精度。

跑法：在專案根目錄執行 pytest
"""
from analyzer import CryptoAnalyzer


def test_funding_extreme_units():
    a = CryptoAnalyzer()
    assert a.funding_extreme(0.01)[0] == "BALANCED"
    assert a.funding_extreme(0.05)[0] == "LONG_CROWDED"
    assert a.funding_extreme(0.09)[0] == "EXTREME_LONG_CROWDED"
    assert a.funding_extreme(-0.09)[0] == "EXTREME_SHORT_CROWDED"


def test_px_round():
    a = CryptoAnalyzer()
    assert a.px_round(0.00001234) > 0
    assert a.px_round(123.456789) == 123.46
