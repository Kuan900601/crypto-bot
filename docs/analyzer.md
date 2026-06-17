# docs/analyzer.md

# Analyzer Engine 文件

`analyzer.py` 是 BlackTide 的核心資產（`CryptoAnalyzer` 類別；`bot.py` 以 `analyzer = CryptoAnalyzer()` 實例化）。

---

## 1. 定位

Analyzer 負責產生交易判斷，不負責 UI、不負責服務、不負責付款、不負責下單。

核心職責：技術指標、策略投票、五維評分、entry_grade、tier、TP/SL 設立、新聞情緒、快速動能偵測、結構退出評估。

---

## 2. 核心概念

### 2.1 strategy_consensus（7+1 投票）
7 個技術策略（趨勢追隨、動量、量價、均線排列、支撐阻力、BOS 突破、訂單流）+ 第 8 票新聞情緒（強度 ≥3 同方向加票）。需至少 2 票。量價票方向化（量增需搭配近 3 根淨變動同向）。
- 未經作者確認不得改票權重、票數門檻、為提高信號量降低品質門檻。

### 2.2 五維評分（滿分 100）
趨勢 + 動量 + 結構 + 量能 + 風險。是策略核心；不得隨意加減權重、不得為了多信號放寬、不得用 UI 顯示值回寫內部欄位。

### 2.3 entry_grade（內部值 `S/A/B/C/D`）
不得改中文、不得與 tier 混用；中文只在顯示層 `entry_grade_display()` 翻譯；交易邏輯只看內部值。

### 2.4 tier（推播 / 自動交易分級 `S/A/B/C`）
與 entry_grade 不同，會疊加，不可混為一談。

---

## 3. TP / SL 設立

Analyzer 內部仍算多段 TP（含 tp4），但**正式結算與真實下單以三段為準**：

```text
TP1 = 40%
TP2 = 35%
TP3 = 25%
TP4 = 停用（analyzer 內部殘留不顯示/不結算/不偵測）
```

TP 階梯（R 倍數）：1.5 / 2.5 / 3.5 / 5.0R（analyzer 內部仍算 tp4，bot 只用前三段）。
不得因 analyzer 內部殘留 tp4 就恢復 TP4 結算或顯示。盈虧比硬門檻 TP1 ≥ 1.2R。

---

## 4. 快速動能（v62「精選 Top N」）

### 4.1 fast_breakout_check(df5m, df15m)
回傳 `(direction, strength, reason)`，strength 為 **0~100**。觸發條件：5m 最新收盤放量突破 15m 近期高/低 + 5m 近 3 根連續同向 + 量 > 均量 1.8x。

### 4.2 fast_momentum_scan（bot.py 背景 job，interval 90s）
用途：降低「噴一段才推」的延遲。流程：
1. 抓 ticker 選 24h 漲跌幅前 12（不重抓全 52 幣 K 線）。
2. 對候選抓 5m / 15m / 1h。
3. 候選需「同時」滿足：強度 ≥ `FAST_MIN_STRENGTH`(70)、RR ≥ `FAST_MIN_RR`(1.8)、1h 趨勢不逆向（`_fast_trend_consistency`）、無活躍信號。
4. 綜合分 = 強度 × 量能倍數 × RR × 趨勢一致性，排序後**每輪只推 `FAST_TOP_N`(1) 個**。
5. 頻率閘門：同幣 2h 不重複、全體每小時 `FAST_MAX_PER_HOUR`(2) 上限。
6. 命中走正常 `register_signal` + 推播 + 佇列，標「⚡精選動能」、tier=B、order_type=MARKET，受連虧/熔斷管制。

相關函式：`_fast_rr`（用 swing_sr 結構位或 3×ATR 投射算 RR）、`_fast_trend_consistency`、`_build_fast_sig`。
規則：快速動能仍受連虧、熔斷、信號年齡、風控管制；不得繞過 register_signal；不得直接繞過 auto_trader 風控下單。
（舊 env `FAST_MOMENTUM_MIN_STRENGTH` 已由 `FAST_MIN_STRENGTH` 取代。）

---

## 5. 結構退出評估（stale_signal_recheck，v62 收緊）

`check_active_signals` → `stale_signal_recheck(sig, price, df1h)` 回傳 `close_now / reduce / hold / add`。
唯一會「因結構破壞主動平倉」的路徑：`close_now` → bot `close_signal(RECHECK_EXIT)` → `close_queue`。
v62 起 `close_now` 需「同時」滿足：
- (a) 深度浮虧 ≥ `max(STRUCT_EXIT_DD_RATIO × SL距離, STRUCT_EXIT_MIN_PCT)`（取較嚴者）。
- (b) 用**已收盤** 1h K（排除未收盤當根），收盤破前段結構低/高 ≥ `STRUCT_BREAK_MARGIN`，且第二確認：連 2 根收盤都破 或 破壞當根爆量(>均量1.8x)。
任一不滿足 → HOLD，交給進場附帶的硬止損。`early_exit_signal` 只發警告、不平倉。

---

## 6. 其他

- C 級延遲推播：只有 C 級時，距上次 B+ 推播須過 `C_TIER_DELAY_MIN`(30 分) 才推。
- 緊急保底單：低質觀察單，由 `EMERGENCY_SIGNALS` 控制，預設關。
- 情境閘門 `entry_context_gate`（`STRICT_CONTEXT_GATE`，預設開）、自適應門檻 `adaptive_threshold`（上調上限 +5）。
- `funding_extreme` 單位已修（輸入即百分比，不再 ×100）；低價幣精度 `px_round`。
- 已抓未進決策：funding rate、多空比。

---

## 7. 修改 analyzer.py 的規矩

改前說明：影響哪些策略、是否影響信號數、entry_grade、tier、TP/SL、auto_trader。
改後必跑 `python -m py_compile analyzer.py bot.py auto_trader.py trader.py`；有測試跑 `pytest`。

禁止：大規模重構、為修小 bug 改動策略框架、複製 analyzer 邏輯到 web、用 UI 顯示文字回寫策略內部欄位、未經確認改 entry_grade/策略投票/風控/TP-SL 生成邏輯。

---

## 8. Web / API 重用原則

Web/API/App 未來需要分析功能時：應呼叫 analyzer 或建立安全 API 封裝 analyzer；不應在 Web 端重寫一份分析策略（會導致結果不一致、維護成本翻倍、與 BOT 信號不同步）。
