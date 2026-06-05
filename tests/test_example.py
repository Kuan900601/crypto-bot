"""
範例測試：示範 pytest 怎麼用，並把「分段加權結算」的邏輯鎖成回歸測試。

說明：
這裡用一個獨立的純函式 weighted_final_pct 複製 bot.py 裡 close_signal 的結算數學，
方便單獨測試（直接 import bot.py 會觸發 Telegram / Redis 等副作用，不適合測試）。
未來若想直接測真實程式碼，建議把這類純計算從 bot.py 抽成獨立函式再 import 進來測。

跑法：在專案根目錄執行  pytest
"""

WEIGHTS = {1: 0.15, 2: 0.35, 3: 0.35, 4: 0.15}


def weighted_final_pct(direction, entry, tp_prices, tp_hit, exit_price):
    """複製 close_signal 的分段加權結算：每個達成的 TP 按權重結算，剩餘倉位用出場價結算。"""
    d = 1 if direction == "LONG" else -1
    realized = 0.0
    realized_w = 0.0
    for lvl in tp_hit:
        tp = tp_prices.get(lvl)
        if tp:
            seg = (tp - entry) / entry * 100 * d
            realized += seg * WEIGHTS.get(lvl, 0)
            realized_w += WEIGHTS.get(lvl, 0)
    remaining_w = max(0.0, 1.0 - realized_w)
    # 達過 TP 後，剩餘倉位的出場價不應比成本還差（保本鉗制）
    if tp_hit:
        exit_price = max(exit_price, entry) if direction == "LONG" else min(exit_price, entry)
    remaining = (exit_price - entry) / entry * 100 * d
    return realized + remaining * remaining_w


def test_short_hits_tp3_then_stops_at_tp2_is_a_win():
    """XRP 做空：達 TP1/2/3，止損移到 TP2，之後回落到 TP2 出場 —— 必須記成大勝，不是虧損。"""
    entry = 1.2367
    tps = {1: 1.1757, 2: 1.1362, 3: 1.0943, 4: 1.0357}
    result = weighted_final_pct("SHORT", entry, tps, tp_hit=[1, 2, 3], exit_price=tps[2])
    assert result > 0                 # 是贏單
    assert round(result, 1) == 8.8    # 達 TP3 的利潤有正確計入


def test_plain_stop_loss_is_a_loss():
    """沒達任何 TP，直接觸發止損 —— 記成虧損。"""
    entry = 100.0
    tps = {1: 103.0, 2: 105.0, 3: 107.0, 4: 110.0}
    result = weighted_final_pct("LONG", entry, tps, tp_hit=[], exit_price=97.0)
    assert result < 0