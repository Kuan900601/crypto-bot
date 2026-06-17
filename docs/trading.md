# docs/trading.md

# Trading / Auto Trader 文件（真錢，謹慎）

描述 BlackTide 的真實交易執行層（`auto_trader.py` + `trader.py`）規則。

---

## 1. 高風險聲明

auto_trader.py 與 trader.py 直接影響真實資金。任何改動先假設「小錯誤可能導致真實虧損」，改前必說明風險。

---

## 2. 現行交易設定

```text
交易所     : Bybit V5（ccxt）
模式       : 真錢 / One-Way 單向 / UTA 統一交易帳戶
trader.py  : USE_SANDBOX = False
總開關     : AUTO_TRADE_ENABLED（未設或非 "true" 不啟動）
輪詢       : POLL_INTERVAL = 15 秒
```

不得移除 `AUTO_TRADE_ENABLED` 閘門、不得預設 true、不得自動改 `USE_SANDBOX`。

---

## 3. 倉位與風控（v62）

```text
AT_LEVERAGE      = 20
AT_MAX_POSITIONS = 4
MAX_DAILY_DD     = 0.10        # 日內熔斷：跌破當日起始 ×(1-DD) 停開新倉
AT_MAX_SL_PCT    = 0.035       # 夾住止損距離
```

倉位本金（v62 起固定等額）：

```text
margin = 淨值 ÷ AT_MAX_POSITIONS
       再夾 min(權益/倉數, free_usdt × 0.95)；free 取不到退回 權益/倉數
```

註：`SIZING_MODE=risk` 風險定額**已移除**，auto_trader 不再讀；`SIZING_MODE`/`RISK_PER_TRADE_PCT` 已成棄用變數（全 code 不再讀取，連 `/at_status` 也不再顯示）。

未經作者確認不得改：槓桿、最大倉數、止損距離、sizing 方式、日內熔斷、tier 准入。

---

## 4. 開倉流程

```text
signal_queue
→ auto_trader process_once
→ 檢查 tier / 信號年齡(SIGNAL_MAX_AGE_MIN) / 同幣不疊倉 / 最大倉數 / 價格偏離(MAX_ENTRY_DRIFT_PCT) / 連虧 / 熔斷
→ trader.open_position_with_protection（市價單原子附帶整倉 stopLoss）
→ 讀回確認；未生效用 V5 position/trading-stop fallback；仍失敗才視為裸倉緊急平倉
→ 掛分段 reduceOnly TP（TP1~3）
```

規則：開倉即附帶止損、無裸倉窗口；stopLoss 失敗要 fallback；某段 TP 失敗不影響整倉止損、不再因此平倉。

---

## 5. 滿倉排隊（v62）

滿 `AT_MAX_POSITIONS` 倉時：
- bot 端照推 TG、照寫 `signal_queue`（不變）。
- auto_trader 下單層把信號推到 `at:waitlist`（依 sig_id 去重、保留 20、不丟棄、**不 mark processed**），本輪不開。
- 有空位時，從 `at:waitlist` **由新到舊**補單，每筆需通過：年齡 < `WAITLIST_MAX_AGE_MIN`(60 分)、現價偏離信號 entry < `MAX_ENTRY_DRIFT_PCT`、同幣未持倉、仍有空位。
- 超時/漂移過大 → 從 waitlist 移除並 mark processed（放棄，不追高）；已被主佇列處理過的候補副本作廢不重開。
- `_commit_open_record` 為主佇列與候補補單共用的落地邏輯。

---

## 6. TP 拆分

```text
TP1 = 40%   TP2 = 35%   TP3 = 25%   TP4 = 停用
```

bot.py 結算與 auto_trader 真實下單必須一致；不得恢復 TP4、不得改回 15/35/35/15；改權重需作者明確確認，且需 `/reset_stats`（新舊 SIGNAL_RESULTS 不可比）。

---

## 7. 移動止損階梯（v62，TP1 後更小心，小回踩掃不掉）

由 `_trail_levels`（一次抓 1h K 線）取 ATR(14) 與 swing low/high。

```text
buffer     = max(TRAIL_BUFFER_MIN_PCT(0.004), 0.6 × ATR/price)
MIN_SL_GAP = max(0.8 × ATR/price, 0.006)   # SL 須離現價至少這麼遠

TP1 成交 → SL = min(entry − buffer, swing_low − 0.3×ATR)   # 多單；取較低者給更多空間
TP2 成交 → SL = entry（此時才真保本）
TP3 成交 → SL = TP1
```

全部再夾「SL ≤ 現價 − MIN_SL_GAP」（空單鏡像）。SL 只往有利方向移、絕不設到現價的另一側；計算違反就跳過該次移動並 log。每段只移一次（`rec["sl_stage"]`）；用 V5 trading-stop 原子更新，失敗保留原止損並 push `at:events`。

規則：不得回到死保本、不得恢復 EMA20 連續移動止損、不得啟用 `smart_tp_extend`（排序 bug）；TP 觸發的階梯是刻意的鎖利機制，保留。

---

## 8. 平倉流程

```text
bot.py close_signal → close_queue
→ auto_trader process_closes → cancel_symbol_orders → close_position(reduceOnly 市價)
```

平倉用對應條件單；不留殘單；事件寫 `at:events`，失敗記 log。

---

## 9. 防重放與可觀測性

防重放 keys：`at:processed_signals`、`at:processed_closes`。`mark_backlog_processed` 只標記過舊（> `SIGNAL_MAX_AGE_MIN`）信號；新鮮信號正常處理；`process_once` 內再做年齡與價格偏離檢查。不得清空 processed key（除非作者確認）、不得移除年齡/偏離檢查。

可觀測性 keys：`at:heartbeat`、`at:last_cycle`（含各 skip 原因計數）、`at:events`（轉發 ADMIN）、`bt:last_scan`（bot 主掃描耗時）。`/at_debug` 一站式診斷（含 ⑤c `at:waitlist` 筆數與最舊年齡）。不得移除可觀測性。

---

## 10. Bybit 注意事項

One-Way 單向、UTA 統一帳戶、ccxt、reduceOnly TP、原生 stopLoss。Railway IP 會變 → 不要設 IP 白名單；API 須開合約權限；不要在 log 印 API secret；取消條件單帶對應 `orderFilter`；注意 symbol id / position mode。

---

## 11. 修改 trading 相關程式的要求

改 `auto_trader.py` / `trader.py` / `bot.py close_signal` / `bot.py register_signal` 前必說明影響。改後必跑：

```bash
python -m py_compile analyzer.py bot.py auto_trader.py trader.py
pytest
```

無法實測 Bybit 時，必須明確標註「尚未經實單驗證」。
