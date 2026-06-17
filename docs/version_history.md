# docs/version_history.md

# Version History / Legacy Notes

保留 BlackTide 重要版本與修復史。CLAUDE.md 不放完整歷史；需查歷史或修復細節時看本檔。

---

## 1. 目前版本

```text
BOT_VERSION = v62
```

（版本字串曾落後：v56 時實際已 v60、v61 時實際已 v62；現已補正為 v62。）

---

## 2. 已知重要規則

- **entry_grade** 內部值固定 `S/A/B/C/D`，不可改中文。
- **TP split** 正式為 `40/35/25`，TP4 停用；舊 `15/35/35/15` 已停用、不得回復。
- **真錢模式** `USE_SANDBOX = False`（作者決定）；真正安全閘門是 env `AUTO_TRADE_ENABLED`。

---

## 3. v53~v55（沿用）

真實勝率校準、盈虧比硬門檻、保護模式不靜音、結算 bug 修正（分段止盈正確計入）、TP 階梯 1.5/2.5/3.5/5R、波動自適應止損、大盤閘門、文字反解析重構（結構化 `_last_plans` + regex fallback）、進場品質中文化、信心分數夾 0~100、Redis 持久化（陣列格式）、全面 `.get()` 容錯。

---

## 4. v57（沿用）

`funding_extreme` 單位二次轉換 bug 修正（輸入即百分比，不再 ×100）、低價幣精度 `px_round`、`stale_signal_recheck` 餵 1h K 線、量價票方向化、情境閘門 `entry_context_gate`、`/edge`、`/gate_stats`、`EMERGENCY_SIGNALS` 預設關。

---

## 5. 結算/交易所遷移

結算權重 2026-06 由 15/35/35/15 改為 **40/35/25 三段**（作者核准、覆蓋舊規則、TP4 移除）；交易所由 BingX 全面遷移到 **Bybit 真錢 One-Way**；執行層改 `trader.py` / `auto_trader.py`。

---

## 6. v61 重點

- 開倉止損改 Bybit 原生附帶式 `open_position_with_protection`；V5 trading-stop fallback；只有真裸倉才緊急平倉。auto_trader TP_SPLIT 對齊三段 40/35/25。
- 移動止損改階梯緩衝版（TP1 後 entry−緩衝、TP2 後 entry、TP3 後 TP1）。
- 警告降噪：`check_signal_reversal`/`early_exit_signal` 15m→1h；`kline_reversal_check` 強 K 門檻 0.7→0.8 且需並立破 EMA20；反向警告冷卻 1h→2h、最多 2 次、只發 watchers。
- 延遲改善：C 級延遲 4.5h→`C_TIER_DELAY_MIN`(30 分)；新增快速動能搶先偵測；批次間隔 0.5→0.3s、掃描鎖 300→180s、`bt:last_scan`；`adaptive_threshold` 上調上限 +5。
- `get_balance` 改讀 UTA；可觀測性 `at:heartbeat`/`at:last_cycle`/`at:events`、`/at_debug` 強化。
- 選單去重（藏「即時動能」「今日 TOP1」入口、callback 保留）；BingX 連結產生器標 deprecated（`bingx_swap_url` 改回傳 Bybit URL，仍在用）。

---

## 7. v62 重點（本輪）

- **快速動能改「精選 Top N」**：候選收集 → 綜合分（強度×量能×RR×趨勢）排序 → 每輪只推 `FAST_TOP_N`(1)；加 `FAST_MIN_STRENGTH`(70)/`FAST_MIN_RR`(1.8)/同幣2h/`FAST_MAX_PER_HOUR`(2) 閘門；`fast_breakout_check` 回 0~100 強度；新增 `_fast_rr`/`_fast_trend_consistency`；標「⚡精選動能」。（舊 `FAST_MOMENTUM_MIN_STRENGTH` 由 `FAST_MIN_STRENGTH` 取代。）
- **倉位固定等額**：`淨值 ÷ AT_MAX_POSITIONS`，夾 `min(權益/倉數, free×0.95)`；移除 `SIZING_MODE=risk` 風險定額（`SIZING_MODE`/`RISK_PER_TRADE_PCT` 成棄用變數，全 code 不再讀、`/at_status` 不再顯示）。
- **滿倉排隊**：滿倉信號進 `at:waitlist`（不丟棄、不 mark processed），有空位由新到舊補單（年齡 `WAITLIST_MAX_AGE_MIN`、漂移、同幣、空位檢查）；`_commit_open_record` 共用；`/at_debug` 增列 ⑤c 候補。
- **結構退出收緊**：`stale_signal_recheck` 的 `close_now` 改「已收盤 1h + 深虧(`STRUCT_EXIT_DD_RATIO`/`STRUCT_EXIT_MIN_PCT` 取較嚴者) + 結構破壞雙確認(`STRUCT_BREAK_MARGIN` + 連2根收盤或爆量)」，否則 HOLD 交給硬止損；`early_exit_signal` 只警告不平倉。
- **TP1 後移動止損更小心**：緩衝 `0.6×ATR`、TP1 取 `min(entry−緩衝, swing_low−0.3×ATR)`、全段夾 `MIN_SL_GAP=max(0.8×ATR%,0.006)` 離現價、只往有利方向移、絕不越過現價；新增 `_trail_levels` 取代舊 `_atr_pct`/`_trail_buffer_pct`。
- `BOT_VERSION` 補正 v61→v62；`/at_status` 移除已失效的 `SIZING_MODE`/`RISK` 顯示。

---

## 8. 已停用且不要回復

- TP4 結算　- 15/35/35/15 TP split　- EMA20 連續移動止損（會砍贏單）
- `smart_tp_extend`（排序 bug）　- BingX 交易主流程　- 緊急保底單預設開
- `SIZING_MODE=risk` 風險定額　- 在死保本價死鉤 TP1 後止損

---

## 9. 未來方向（現在一律不做，等驗證通過）

funding / 多空比 / OI 進決策、歷史位階百分位過濾、數據驅動調票權重（需 30~50 筆）、時段分析、進階大盤閘門（BTC.D）、自適應學習（需 100+ 筆）、Web Dashboard / App 強化。
提醒：未達足夠樣本驗證前，不要為追求功能大改策略核心。

---

## 10. 驗證標準

- `final_pct` 是毛價格 %，未扣成本（成本約 0.15~0.2%/筆）。
- `/edge` 是 SIM 毛價格 %；`/real_pnl` 是含手續費真實數據，才是最終答案。
- 預設判斷：約 50 筆乾淨交易、毛期望值 ≥ +0.4%、平均盈 > 平均虧、零爆倉 → 視為通過。30 筆只是第一眼。20x 槓桿下必須接近零爆倉。
