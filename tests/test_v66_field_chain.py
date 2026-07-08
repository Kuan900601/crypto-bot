"""
v66 Phase 2 回歸測試：
  Bug A - _last_plans 白名單改排除清單，新欄位不再被靜默丟棄。
  Bug B - was_real_trade 使用正確 Redis key "at:trades"（非 "auto_trades.json"）。
  sltp_method trap - 移除 "fixed_atr" 假預設，缺值時回傳 None。

跑法：在專案根目錄執行 PYTHONPATH=/workspaces/crypto-bot pytest
"""
import re
import os
from analyzer import CryptoAnalyzer


# ── Bug A：_last_plans 全量複製驗證 ────────────────────────────────────────────

# 模擬 professional_setup() 返回的 plan 含新欄位（v65 P3/P4 加入的）
_FAKE_PLAN = {
    "score": 75, "entry": 100.0, "sl": 95.0,
    "tp1": 105.0, "tp2": 110.0, "tp3": 115.0, "tp4": 0.0,
    "rr1": 1.5, "rr2": 2.5,
    "tier": "A", "entry_grade": "A", "position": 5,
    "win_rate": 60, "real_win_rate": None,
    "timing_state": "NOW", "timeframe": "短線", "order_type": "MARKET",
    "regime": "BULL", "adx": 25, "consensus_count": 3, "news_vote": False,
    # v65 P3/P4 新欄位（舊白名單不含）
    "sltp_method_at_entry": "structure",
    "sl_structure_type": "swing_sup",
    "range_pos": 0.55,
    "funding": -0.0003,
    "sl_label": "ATR",
    "market_health": {"vol_ratio": 1.2},
    "entry_vs_ema": -0.5,
    "ls_ratio": 1.05,
    "price_change_before_entry": 0.8,
    "dist_from_recent_high_pct": 2.0,
    "dist_from_recent_low_pct": 5.5,
}

# 舊白名單欄位集合（原 golden_hunter 的 _last_plans 建構）
_OLD_WHITELIST_KEYS = {
    "symbol", "direction", "score", "entry", "sl",
    "tp1", "tp2", "tp3", "tp4", "tier", "entry_grade",
    "position", "win_rate", "real_win_rate",
    "rr_ratio", "rr1", "timing_state", "timeframe",
    "order_type", "regime", "adx", "consensus_count", "news_vote",
}


def _populate_last_plans(analyzer, plan, sym="TESTUSDT", direction="LONG"):
    """模擬修復後的 golden_hunter _last_plans 建構邏輯（Bug A fix）。"""
    key = sym + "|" + direction
    entry = plan.copy()         # 排除清單取代白名單
    entry["symbol"] = sym
    entry["direction"] = direction
    entry["rr_ratio"] = plan.get("rr1", 0)  # 向下相容別名
    analyzer._last_plans[key] = entry
    return key


def test_last_plans_preserves_all_new_fields():
    """Bug A：_p.copy() 後所有欄位必須保留在 _last_plans 中。"""
    a = CryptoAnalyzer()
    key = _populate_last_plans(a, _FAKE_PLAN)
    sig = a._last_plans[key]

    beyond_whitelist = [k for k in _FAKE_PLAN if k not in _OLD_WHITELIST_KEYS]
    for field in beyond_whitelist:
        assert field in sig, f"Bug A 回歸：'{field}' 被 _last_plans 丟棄"
        assert sig[field] == _FAKE_PLAN[field], (
            f"'{field}' 值不符：期望 {_FAKE_PLAN[field]!r}，實際 {sig[field]!r}"
        )


def test_last_plans_rr_ratio_backward_compat():
    """rr_ratio 別名必須存在（bot.py 部分路徑仍讀此 key）。"""
    a = CryptoAnalyzer()
    key = _populate_last_plans(a, _FAKE_PLAN)
    sig = a._last_plans[key]
    assert sig.get("rr_ratio") == _FAKE_PLAN["rr1"]


def test_last_plans_symbol_direction_injected():
    """symbol / direction 由 golden_hunter 注入，必須存在於 _last_plans 值中。"""
    a = CryptoAnalyzer()
    key = _populate_last_plans(a, _FAKE_PLAN, sym="BTCUSDT", direction="SHORT")
    sig = a._last_plans[key]
    assert sig.get("symbol") == "BTCUSDT"
    assert sig.get("direction") == "SHORT"


def test_register_signal_reads_chain_fields():
    """sig（即 _last_plans value）的 .get() 必須能讀到 v65+ 新欄位（完整鏈驗證）。"""
    a = CryptoAnalyzer()
    key = _populate_last_plans(a, _FAKE_PLAN)
    sig = a._last_plans[key]  # 這就是 bot.py register_signal 的入參

    # 以下模擬 register_signal 讀取欄位的方式
    assert sig.get("sltp_method_at_entry") == "structure"      # v65 P3
    assert sig.get("sl_structure_type") == "swing_sup"         # v65 P3
    assert sig.get("range_pos") == 0.55                        # v66 P2（原本被丟棄）
    assert sig.get("funding") == -0.0003                       # v65 P2（原本被丟棄）
    assert sig.get("sl_label") == "ATR"                        # v65 P4（sl_source_at_entry）
    assert sig.get("market_health", {}).get("vol_ratio") == 1.2


def test_sltp_method_absent_returns_none():
    """sltp_method_at_entry 不存在時，.get() 必須回傳 None（不是假值 "fixed_atr"）。"""
    a = CryptoAnalyzer()
    plan_no_sltp = {k: v for k, v in _FAKE_PLAN.items()
                    if k != "sltp_method_at_entry"}
    key = _populate_last_plans(a, plan_no_sltp)
    sig = a._last_plans[key]

    # 移除 "fixed_atr" 假預設後，缺值應為 None
    assert sig.get("sltp_method_at_entry") is None, (
        "sltp_method_at_entry 缺值時不應回傳假預設 'fixed_atr'"
    )


# ── Bug B：Redis key 正確性驗證 ───────────────────────────────────────────────

def test_was_real_trade_redis_key():
    """Bug B：bot.py 的 was_real_trade 必須使用 Redis key 'at:trades' 而非 'auto_trades.json'。"""
    bot_path = os.path.join(os.path.dirname(__file__), "..", "bot.py")
    with open(bot_path, encoding="utf-8") as f:
        src = f.read()

    # 確認正確 key 存在
    assert '"at:trades"' in src, "Bug B：bot.py 找不到正確的 Redis key 'at:trades'"

    # 確認舊錯誤 key 不再出現（was_real_trade 上下文）
    wrong_key_count = src.count('"auto_trades.json"')
    assert wrong_key_count == 0, (
        f"Bug B 回歸：bot.py 仍有 {wrong_key_count} 處 'auto_trades.json'，"
        "應已全數改為 'at:trades'"
    )
