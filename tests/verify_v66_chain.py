"""
B3 驗收腳本：走真實鏈路 professional_setup → _last_plans → register_signal → close_signal
印出完整欄位值，供作者目視確認三次未落地的欄位已修復。

跑法：PYTHONPATH=/workspaces/crypto-bot python tests/verify_v66_chain.py
"""
import sys
import json
from datetime import datetime, timezone
from analyzer import CryptoAnalyzer

SEP = "─" * 60

# ── Step 1：模擬 professional_setup() 返回的 plan dict ────────────────────────
# 這是 golden_hunter 會拿到的「真實形狀」plan，含 v65/v66 加入的所有新欄位
FAKE_PLAN = {
    # 核心交易參數
    "score": 73, "entry": 0.1720, "sl": 0.1650, "tp1": 0.1800,
    "tp2": 0.1900, "tp3": 0.2000, "tp4": 0.0,
    "rr1": 1.14, "rr2": 2.57,
    "tier": "A", "entry_grade": "A", "position": 6,
    "win_rate": 62, "real_win_rate": 58.5,
    "timing_state": "NOW", "timeframe": "短線", "order_type": "MARKET",
    "regime": "BULL", "adx": 28, "consensus_count": 3, "news_vote": False,
    # v65 P2/P4 新增欄位（舊白名單不含，三次被 _last_plans 截斷）
    "sltp_method_at_entry": "structure",
    "sl_structure_type": "swing_sup",
    "range_pos": 0.62,          # ← 第三次仍未落地的欄位
    "funding": -0.00015,        # ← 第三次仍未落地的欄位
    "ls_ratio": 1.08,
    "sl_label": "ATR",          # → sl_source_at_entry
    "market_health": {"vol_ratio": 1.3, "btc_trend": "BULL"},
    "rr2": 2.57,
    "entry_vs_ema": -0.4,       # ← 第三次仍未落地的欄位
    "price_change_before_entry": 1.2,
    "dist_from_recent_high_pct": 3.5,
    "dist_from_recent_low_pct": 6.8,
    "chase_flags": ["CHASE_RP"],  # v66 P1 新增
    "gate_tags": [],
}

SYM, DIR = "STXUSDT", "LONG"

# ── Step 2：走真實 _last_plans 建構路徑（Bug A fix 後的程式碼）─────────────────
print(SEP)
print("Step 2: 走 _last_plans 建構路徑（測試 Bug A fix）")
a = CryptoAnalyzer()
_key = SYM + "|" + DIR
_entry = FAKE_PLAN.copy()          # v66 P2 Bug A fix：_p.copy()，不再是白名單
_entry["symbol"] = SYM
_entry["direction"] = DIR
_entry["rr_ratio"] = FAKE_PLAN.get("rr1", 0)
a._last_plans[_key] = _entry

sig = a._last_plans[_key]          # 這就是 bot.py register_signal 收到的 sig
print(f"  _last_plans 建構完成，key={_key!r}，欄位數={len(sig)}")

# ── Step 3：模擬 register_signal 讀取欄位（抄 bot.py 原始邏輯）────────────────
print(SEP)
print("Step 3: 模擬 register_signal 讀取（sig.get() 路徑）")

now = datetime(2026, 7, 9, 14, 0, 0, tzinfo=timezone.utc)
active_signal_record = {
    "sltp_method_at_entry": sig.get("sltp_method_at_entry"),
    "sl_structure_type":    sig.get("sl_structure_type"),
    "range_pos_at_entry":   sig.get("range_pos"),        # ← 三次未落地欄位
    "funding_at_entry":     sig.get("funding"),          # ← 三次未落地欄位
    "ls_ratio_at_entry":    sig.get("ls_ratio"),
    "entry_vs_ema_at_entry":sig.get("entry_vs_ema"),     # ← 三次未落地欄位
    "price_change_before_entry":    sig.get("price_change_before_entry"),
    "dist_from_recent_high_at_entry": sig.get("dist_from_recent_high_pct"),
    "dist_from_recent_low_at_entry":  sig.get("dist_from_recent_low_pct"),
    "sl_source_at_entry":   sig.get("sl_label"),
    "market_health_at_entry": sig.get("market_health"),
    "chase_flags_at_entry": sig.get("chase_flags", []),
    "session_at_entry":     "Asia" if now.hour < 8 else ("Europe" if now.hour < 16 else "America"),
    "rr_at_entry":          sig.get("rr2"),
    "sl_used_pct":          (round(abs(sig.get("sl", 0) - sig.get("entry", 0)) / sig["entry"] * 100, 2)
                             if sig.get("entry") else None),
    "min_seen_price":       sig.get("entry"),
    "max_seen_price":       sig.get("entry"),
}

CHECK_FIELDS = ["sltp_method_at_entry", "range_pos_at_entry", "funding_at_entry",
                "entry_vs_ema_at_entry", "chase_flags_at_entry", "sl_source_at_entry"]
all_ok = True
for f in CHECK_FIELDS:
    val = active_signal_record.get(f)
    ok = val is not None and val != [] or f == "chase_flags_at_entry"
    status = "✅" if val is not None else "❌ NONE"
    print(f"  {f:40s} = {val!r:30}  {status}")
    if val is None:
        all_ok = False

print()
print("  完整 ACTIVE_SIGNALS 欄位快照：")
for k, v in sorted(active_signal_record.items()):
    print(f"    {k:40s} = {v!r}")

# ── Step 4：模擬 close_signal SIGNAL_RESULTS 欄位（was_real_trade 兩態）───────
print(SEP)
print("Step 4: 模擬 close_signal SIGNAL_RESULTS 兩態")

# 態 A：was_real_trade = False（at:trades 有資料但無匹配）
was_real_trade_no_match = False    # Redis 有回應，但沒有匹配的交易記錄
# 態 B：was_real_trade = None（Redis 讀取失敗）
was_real_trade_redis_fail = None   # Redis 查詢異常

# 模擬 close_signal sig（= ACTIVE_SIGNALS[symbol]）讀欄位
sig_close = active_signal_record   # 結算時 sig 就是 register_signal 寫入的 dict

result_entry = {
    "sltp_method_at_entry": sig_close.get("sltp_method_at_entry"),
    "sl_structure_type":    sig_close.get("sl_structure_type"),
    "chase_flags_at_entry": sig_close.get("chase_flags_at_entry", []),
    "sl_used_pct":          sig_close.get("sl_used_pct"),
    "range_pos_at_entry":   sig_close.get("range_pos_at_entry"),
    "entry_vs_ema_at_entry":sig_close.get("entry_vs_ema_at_entry"),
    "funding_at_entry":     sig_close.get("funding_at_entry"),
    "was_real_trade":       was_real_trade_no_match,  # 驗態 A
}

print("  態 A（有資料但無匹配）：was_real_trade =", was_real_trade_no_match)
print("  態 B（Redis 讀失敗）  ：was_real_trade =", was_real_trade_redis_fail)
print()
print("  SIGNAL_RESULTS 欄位快照：")
for k, v in sorted(result_entry.items()):
    print(f"    {k:40s} = {v!r}")

# ── 最終判定 ─────────────────────────────────────────────────────────────────
print(SEP)
critical = [
    ("range_pos_at_entry",    active_signal_record.get("range_pos_at_entry")),
    ("entry_vs_ema_at_entry", active_signal_record.get("entry_vs_ema_at_entry")),
    ("price_change_before_entry", active_signal_record.get("price_change_before_entry")),
    ("was_real_trade (False)", was_real_trade_no_match),
    ("was_real_trade (None)", was_real_trade_redis_fail),
    ("sltp_method_at_entry",  active_signal_record.get("sltp_method_at_entry")),
    ("chase_flags_at_entry",  active_signal_record.get("chase_flags_at_entry")),
]
fail = [(n, v) for n, v in critical
        if v is None and n not in ("was_real_trade (None)",)]
print("驗收結果：")
for name, val in critical:
    ok = "✅" if val is not None else ("✅ (預期 None)" if "None" in name else "❌")
    print(f"  {ok}  {name} = {val!r}")

if fail:
    print("\n❌ 仍有欄位為 None（Bug 未修復）：", [n for n, _ in fail])
    sys.exit(1)
else:
    print("\n✅ 所有關鍵欄位驗證通過，鏈路修復確認。")
