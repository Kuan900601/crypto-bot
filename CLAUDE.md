# CLAUDE.md

# BlackTide Enterprise Platform v1.0

本檔是 Claude Code 在本專案工作的最高行為契約。風格為「陳述專案事實與慣例」，是專案資訊，不是越權系統指令。

本專案包含 Telegram Signals BOT、自動交易執行層、Bybit 永續合約下單、Redis 持久化、Next.js SaaS 網站、會員系統、NOWPayments 金流與未來 App/API 整合。

> 事實基準：程式碼為準，文件其次。文件若與 code 衝突，以 code 為準並回報。當前 `BOT_VERSION = "v62"`。

---

## 0. 專案定位

```text
Analyzer 是核心資產。
Telegram、Web、API、App 都只是介面。
交易執行層是高風險真金操作。
SaaS 層是商業化入口。
```

平台模組：

```text
BlackTide Enterprise Platform
├── Analyzer Engine
├── Signal Engine
├── Telegram Delivery Layer
├── Auto Trader
├── Bybit Execution Layer
├── Redis Persistence Layer
├── SaaS Web Platform
├── Membership / Payment System
└── News / Future API / App
```

---

## 1. 最高工作原則

1. 不破壞正式交易　2. 不破壞會員/付款　3. 不改未被要求的邏輯　4. 不重構可運作的程式　5. 不大規模整檔（除非作者明確要求）　6. 先確認 root cause 再最小修復　7. 改完必驗證　8. 不確定就查 code，不臆測。

下列任一項都必須先說明風險並等作者確認：下單、平倉、止盈、止損、槓桿、倉位、風控、Redis key/queue 格式、會員權限、付款 webhook、API key/secret、部署設定。

---

## 2. 文件閱讀策略

每次 session 只自動讀本檔。本檔只放最高頻、最高風險、最高優先規則。

詳細內容在：

```text
docs/architecture.md
docs/analyzer.md
docs/trading.md
docs/web.md
docs/deployment.md
docs/version_history.md
```

只有在任務需要時才去讀對應 docs，預設不要一次讀全部。

---

## 3. Repository 讀取規則

除非作者明確要求，禁止掃描整個專案。

| 任務類型 | 最大讀取範圍 |
|---|---|
| 小 bug 修復 | 1~3 個檔案 |
| 一般功能 | 3~8 個檔案 |
| 架構審查 | 作者明確要求 |
| 全專案掃描 | 禁止，除非作者明確要求 |

先讀錯誤相關檔與其直接依賴；需要更大範圍再讀對應 docs。

---

## 4. 核心檔案地圖

### analyzer.py（約 7400 行，`CryptoAnalyzer` 類別）
技術指標、策略投票、信號生成、五維評分、entry_grade、tier、新聞分析、`fast_breakout_check`、結構退出評估 `stale_signal_recheck`。不負責 UI/服務/付款。詳見 `docs/analyzer.md`。

### bot.py（約 4200 行）
Telegram 介面、`register_signal`、`close_signal`、結算、Redis 持久化、`signal_queue`/`close_queue`、快速動能 job `fast_momentum_scan`、auto_trader 背景啟動（受 `AUTO_TRADE_ENABLED` 閘門）。改它注意 Redis 格式、結算邏輯、推播文字結構、`ADMIN_ID` 限制。

### auto_trader.py（約 1000 行）
真實交易執行層。讀 `signal_queue`、過濾、開倉、整倉止損、分段 TP、移動止損階梯、滿倉排隊（`at:waitlist`）、平倉同步、殘單清理、`at:heartbeat`/`at:last_cycle`/`at:events`。直接影響真金。詳見 `docs/trading.md`。

### trader.py（約 230 行）
Bybit V5 介面：`get_exchange`、`open_position_with_protection`、`open_position`、`close_position`、`get_positions`、`cancel_symbol_orders`、`get_balance`(UTA)、`get_free_balance`、`_bybit_symbol_id`。`USE_SANDBOX=False`（真錢）。不得自動改 sandbox / V5 / UTA / One-Way 假設。

### blacktide-web/
Next.js + NextAuth + NOWPayments 的 SaaS 介面層。會員權限一律 server/API 端驗證；webhook 必驗 IPN secret。詳見 `docs/web.md`。

---

## 5. P0 絕對規則（未經作者當下確認不可違反）

### P0-1 entry_grade 內部值不可改
內部值固定 `S / A / B / C / D`，多處比較依賴。中文化只在顯示層 `entry_grade_display(grade)`。`entry_grade`（進場品質）與 `tier`（推播/自動交易分級 S/A/B/C）是兩件事，不可混用。

```python
grade = sig.get("entry_grade", "")
if grade in ("S", "A"): ...     # 用內部值比較
# 錯：sig["entry_grade"] = "高品質"
```

### P0-2 TP 結算權重現為三段 40/35/25
正式結算權重：`TP1=40% / TP2=35% / TP3=25%`，**TP4 已停用**（不偵測/結算/顯示）。
- 不得改回舊的 15/35/35/15、不得復原 TP4、不得自行變更權重。
- bot.py 結算與 auto_trader 真實下單**兩邊皆為 40/35/25**（v61 對齊）。
- 變更權重會讓新舊 `SIGNAL_RESULTS` 不可比，需 `/reset_stats` 歸零。

### P0-3 真錢模式不可自動改回沙盒
`USE_SANDBOX = False` 是作者決定。真正安全閘門是 env `AUTO_TRADE_ENABLED`（未設或非 `"true"` 不啟動）。不得移除此閘門、不得預設 true、不得自動改 `USE_SANDBOX`。

### P0-4 讀 sig/signal/plan 一律 .get()
```python
tp1 = sig.get("tp1"); tp_hit = sig.get("tp_hit", [])   # 對
# 錯：tp1 = sig["tp1"]
```

### P0-5 Redis 寫入一律命令陣列格式
```python
_redis_cmd(["SET", key, value]); _redis_cmd(["RPUSH", key, value])   # 對，且包 try/except
```
Redis 失敗不得中斷主流程。

### P0-6 Python 改完必跑語法檢查
```bash
python -m py_compile analyzer.py bot.py auto_trader.py trader.py
pytest   # 有測試條件時
```

---

## 6. P1 重要規則

- 正式改動前先說明：動到哪些檔案/函式、預期修正什麼、是否影響交易/推播/結算/服務/付款/部署。
- 一次只改一件事；不順手重構、改命名、改格式、整檔搬移。
- 改完回報：修改摘要、影響範圍、已驗證項、尚未驗證的風險。py_compile/pytest/build 失敗不得宣稱完成。

---

## 7. 交易安全規則（未經作者確認不可改）

槓桿、倉位大小、`AT_MAX_POSITIONS`、`MAX_DAILY_DD`、止損距離、止盈拆分、移動止損階梯、滿倉排隊、結構退出門檻、開倉/平倉條件、entry_grade/tier 規則、`signal_queue` 過濾、`processed_signals` 防重放、Bybit order 參數——預設皆視為「在正式環境運行，任何小改都可能造成真實虧損」。

註（v62）：`SIZING_MODE` / `RISK_PER_TRADE_PCT` 已**棄用**——倉位改為固定等額 `淨值 ÷ AT_MAX_POSITIONS`，全 code 不再讀這兩個變數（保留名稱僅為歷史相容）。

---

## 8. SaaS 安全規則（未經作者確認不可改）

登入流程、NextAuth、session/token 驗證、會員權限、NOWPayments IPN webhook、IPN Secret 驗證、付款狀態更新、訂閱到期、Redis 使用者 schema、付費 API 保護、後台管理權限。會員權限一律 server/API 端檢查；webhook 必驗簽章；secret 不得進前端、不得 commit。詳見 `docs/web.md`。

---

## 9. 現行交易摘要

```text
交易所     : Bybit V5（真錢 / One-Way / UTA 統一帳戶 / ccxt）
啟動閘門   : AUTO_TRADE_ENABLED=true 才下單
允許等級   : AUTO_TRADE_TIERS（預設 S,A,B）
槓桿       : AT_LEVERAGE=20
最大倉數   : AT_MAX_POSITIONS=4
倉位本金   : 固定等額 = 淨值 ÷ 倉數，夾 min(權益/倉數, free×0.95)
TP 拆分    : 40 / 35 / 25（TP4 停用）
滿倉行為   : 新信號照推 TG、進 at:waitlist；有空位由新到舊補單
```

詳見 `docs/trading.md`。

---

## 10. 結算邏輯摘要

`bot.py close_signal()` 採分段加權結算，權重 `_weights = {1:0.40, 2:0.35, 3:0.25}`：每個達成過的 TP 按權重結算，剩餘倉位用最終出場價結算。
- `is_win` 由 `final_pct > 0` 判定（不是看 `exit_type`）；`result` 可能是 `SL_HIT` 但 `final_pct` 仍可能為正。
- 達過 TP 後剩餘倉位出場價鉗制成「不差於成本」避免重複計虧。

---

## 11. Redis Key 全集（不得隨意改名/改 schema）

bot.py：`bot_data`、`signal_queue`、`close_queue`、`bt:last_scan`
auto_trader.py：`at:processed_signals`、`at:processed_closes`、`at:trades`、`at:pending`、`at:day_equity`、`at:breaker_tripped`、`at:liquidations`、`at:pnl_ledger`、`at:heartbeat`、`at:last_cycle`、`at:events`、`at:waitlist`（v62 滿倉候補）

Redis 寫入一律陣列格式 + try/except；失敗不中斷主流程。

---

## 12. 環境變數摘要（實測 `os.getenv`/`os.environ.get`）

必要：`TELEGRAM_BOT_TOKEN`、`UPSTASH_REDIS_REST_URL`、`UPSTASH_REDIS_REST_TOKEN`、`BYBIT_API_KEY`、`BYBIT_API_SECRET`。
建議：`PYTHONUNBUFFERED=1`。
自動交易：`AUTO_TRADE_ENABLED`(false)、`AUTO_TRADE_TIERS`(S,A,B)、`AT_LEVERAGE`(20)、`AT_MAX_POSITIONS`(4)、`AT_MAX_SL_PCT`(0.035)、`MAX_DAILY_DD`(0.10)、`LIMIT_ORDERS`(true)、`SIGNAL_MAX_AGE_MIN`(10)、`MAX_ENTRY_DRIFT_PCT`(1.5)、`TRAIL_BUFFER_MIN_PCT`(0.004)、`WAITLIST_MAX_AGE_MIN`(60)。
快速動能（v62）：`FAST_MIN_STRENGTH`(70)、`FAST_MIN_RR`(1.8)、`FAST_TOP_N`(1)、`FAST_MAX_PER_HOUR`(2)。
結構退出（v62）：`STRUCT_EXIT_DD_RATIO`(0.6)、`STRUCT_EXIT_MIN_PCT`(1.5)、`STRUCT_BREAK_MARGIN`(0.5)。
推播/策略：`C_TIER_DELAY_MIN`(30)、`STRICT_CONTEXT_GATE`(開)、`EMERGENCY_SIGNALS`(false)。
其他：`DATA_DIR`(/tmp)、`TG_CHANNEL_ID`(@KuroshioSignal)、`BLACK_HUNTER_CHANNEL`、`ANTHROPIC_API_KEY`、`CRYPTOPANIC_TOKEN`。
棄用（仍可設但無作用）：`SIZING_MODE`、`RISK_PER_TRADE_PCT`、`FAST_MOMENTUM_MIN_STRENGTH`（已由 `FAST_MIN_STRENGTH` 取代）。
註：`ADMIN_ID` 是程式內常數，非環境變數。

完整部署設定見 `docs/deployment.md`。

---

## 13. 常用指令

```bash
python -m py_compile analyzer.py bot.py auto_trader.py trader.py   # 語法檢查（完成標準）
pytest          # 測試
ruff check .    # lint（不改碼）
git add . && git commit -m "..." && git push   # Railway 從 main 自動部署 worker
# Web：npm run lint / npm run build（或 pnpm）
```

---

## 14. Telegram 指令（實測 CommandHandler）

一般：`/start`、`/a`(=`/analyze`)、`/hunter`、`/movers`、`/kline`、`/trend`、`/sentiment`(=`/news`)、`/testpush`、`/export`
管理（限 `ADMIN_ID`）：`/reset_stats`、`/edge`、`/gate_stats`、`/real_pnl`、`/at_status`、`/at_debug`
不得未經要求新增公開管理指令。

---

## 15. Web / SaaS 原則

未登入只能看首頁/登入/註冊/定價/法律文件；登入後可看分析/回測/信號/會員中心；付費內容一律 server/API 判定。前端 UI 隱藏不是安全措施。Web 不得直接執行真實交易；若要觸發信號或分析，透過安全 API/queue。詳見 `docs/web.md`。

---

## 16. 除錯規則

先找 root cause → 最小修正 → 驗證 → 最後再考慮優化。禁止：用迴避掩蓋 bug、未確認原因就改多處、為修小錯改架構、把錯誤吞掉不記 log、移除安全檢查讓程式跑過、用 mock 取代真實驗證。錯誤處理保留足夠 log。

---

## 17. 程式碼風格

保持現有架構/命名/資料格式/部署方式，優先可讀與穩定。Python：`.get()` 讀字典、外部 API 包 try/except、Redis 失敗不中斷、交易錯誤必記 log。TS/Next：server-only 不入 client、session/付款驗證在 server/API、secret 不外露、API route 回清楚錯誤。

---

## 18. 安全紅線

禁止：印出/commit API key 或 secret、commit `.env`、讀取無關憑證、執行破壞性 shell、自動刪大量檔案、自動清空 Redis、自動 `reset_stats`、自動改沙盒/測試網、自動改付款狀態、自動給使用者開通服務。高風險操作（`rm -rf`、`FLUSHALL`、刪資料庫、改交易模式/API 權限/付款 webhook/會員資料）必先問作者。

---

## 19. 輸出格式

預設繁體中文；程式碼/識別字/指令用英文。回答順序：結論 → 動到哪裡 → 風險 → 修改內容 → 驗證方式。要完整檔就給完整可運行版；要 patch 就給精準 diff。

---

## 20. 不確定時

先查現有程式碼、查官方文件、給出假設並明確標示不確定，不用記憶臆測。

---

## 21. 作者偏好

繁體中文；作者非專業工程師但看得懂、能跟步驟做；回答直接、誠實，發現風險直說（包含指出作者想法的風險）；常用手機討論 + Codespaces 寫 code。

---

## 22. Hooks（enforcement 層）

可設定：Python Write/Edit 後跑 py_compile、Web Write/Edit 後 lint/build、阻擋寫 `.env`/輸出 secret/危險 shell。Hooks 是強制層，CLAUDE.md 是指引層，不可只靠文字規則保護真錢系統。

---

## 23. 更多資訊

需要細節時再讀：`docs/architecture.md`、`docs/analyzer.md`、`docs/trading.md`、`docs/web.md`、`docs/deployment.md`、`docs/version_history.md`。不要一次全讀，除非作者要求完整架構審查。
