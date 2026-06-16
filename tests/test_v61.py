"""
v61 回歸測試：fast_breakout_check（快速動能突破偵測）。

跑法：在專案根目錄執行 pytest
"""
import pandas as pd
from analyzer import CryptoAnalyzer


def _df15_flat(n=30, hi=101.0, lo=99.0, c=100.0):
    return pd.DataFrame({
        "open": [c] * n, "high": [hi] * n, "low": [lo] * n,
        "close": [c] * n, "volume": [1000.0] * n,
    })


def test_fast_breakout_long():
    a = CryptoAnalyzer()
    df15 = _df15_flat()
    m = 40
    close5 = [100.0] * (m - 3) + [101.5, 102.0, 103.0]
    open5 = [100.0] * (m - 3) + [101.0, 101.5, 102.0]
    vol5 = [1000.0] * (m - 1) + [3000.0]  # 末根放量 ~2.7x
    df5 = pd.DataFrame({
        "open": open5, "high": [x + 0.2 for x in close5],
        "low": [x - 0.2 for x in open5], "close": close5, "volume": vol5,
    })
    direction, strength, reason = a.fast_breakout_check(df5, df15)
    assert direction == "LONG"
    assert strength > 0
    assert "突破" in reason


def test_fast_breakout_none_when_flat():
    a = CryptoAnalyzer()
    df15 = _df15_flat()
    df5 = _df15_flat(n=40)  # 完全持平、無放量
    direction, strength, _ = a.fast_breakout_check(df5, df15)
    assert direction is None
    assert strength == 0


def test_fast_breakout_none_without_volume():
    """突破但沒有放量 → 不應觸發（避免假突破）。"""
    a = CryptoAnalyzer()
    df15 = _df15_flat()
    m = 40
    close5 = [100.0] * (m - 3) + [101.5, 102.0, 103.0]
    open5 = [100.0] * (m - 3) + [101.0, 101.5, 102.0]
    vol5 = [1000.0] * m  # 無量能放大
    df5 = pd.DataFrame({
        "open": open5, "high": [x + 0.2 for x in close5],
        "low": [x - 0.2 for x in open5], "close": close5, "volume": vol5,
    })
    direction, _, _ = a.fast_breakout_check(df5, df15)
    assert direction is None
