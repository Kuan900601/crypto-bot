# docs/architecture.md

# BlackTide Enterprise Platform 架構文件

描述整體系統架構、資料流與模組邊界。

---

## 1. 平台總覽

```text
BlackTide Enterprise Platform
├── Analyzer Engine
├── Signal Engine
├── Telegram Bot
├── Auto Trader
├── Bybit Execution Layer
├── Redis Persistence Layer
├── SaaS Web Platform
├── Membership System
├── Payment System
└── Future API / App Layer
```

核心原則：

```text
Analyzer 是核心資產。
介面層可以換，但策略核心不可複製、不可分裂。
```

---

## 2. 核心資料流

### 2.1 信號產生
```text
Market Data → analyzer.py → strategy_consensus → scoring
→ entry_grade / tier → signal object
→ bot.py register_signal → Telegram push → Redis signal_queue
```

### 2.2 自動交易
```text
Redis signal_queue → auto_trader.py → filters / risk checks
→ 滿倉則進 at:waitlist；有空位補單
→ trader.py → Bybit V5 → position / TP / SL → at:events / at:heartbeat
```

### 2.3 平倉同步
```text
bot.py close_signal → Redis close_queue → auto_trader.py process_closes
→ cancel_symbol_orders → close_position → Redis at:trades / at:events
```

### 2.4 Web SaaS
```text
User → blacktide-web → NextAuth → membership check
→ protected API → analyzer / signal data → paid dashboard
```

### 2.5 付款
```text
User Payment → NOWPayments → IPN Callback → verify IPN Secret
→ update user membership → Redis / DB user state
```

---

## 3. 模組邊界

- **Analyzer Engine**：分析、評分、策略投票、生成交易設立。不負責 UI/服務/付款。
- **Telegram Bot Layer**：指令、推播、結算、Queue 寫入、管理指令。不負責 Web 服務/金流/前端。
- **Auto Trader Layer**：從 queue 消費信號、風控過濾、下單、TP/SL、滿倉排隊、平倉同步、事件回報。不產策略、不做評分、不做 UI。
- **Trader Layer**：Bybit API 封裝、下單原語、倉位/餘額查詢、撤單。不做策略/風控決策/UI。
- **Web SaaS Layer**：登入、註冊、會員權限、付款、Dashboard、付費牆、API 串接。不得複製 analyzer 策略、不得直接執行真實交易（除非設計安全 API 並 server 端驗證）。

---

## 4. Redis 架構

需要的 key：

```text
bot_data
signal_queue
close_queue
bt:last_scan
at:processed_signals
at:processed_closes
at:trades
at:pending
at:day_equity
at:breaker_tripped
at:liquidations
at:pnl_ledger
at:heartbeat
at:last_cycle
at:events
at:waitlist        # v62 滿倉候補
```

規則：不得隨意改 key 名稱、不得改 value schema、寫入一律陣列格式 + try/except、失敗不中斷主流程、交易 queue 格式不可未經確認改動。

---

## 5. 部署架構

BOT：`GitHub main → Railway worker → Python Telegram Bot → Upstash Redis → Bybit`
Web：`GitHub main → Vercel → Next.js → NextAuth → NOWPayments → Redis`

---

## 6. 高風險邊界

以下對接介面改動須謹慎：`register_signal` ↔ `signal_queue` 格式、`close_signal` ↔ `close_queue` 格式、auto_trader ↔ trader 下單參數、TP/SL schema、Redis key/JSON value 格式、NextAuth session ↔ API 權限、NOWPayments IPN 驗證、Web 會員態 ↔ Redis user schema。

---

## 7. 擴充原則

新增功能優先序：先重用 analyzer → 再封裝 API → 再提供 Web/Telegram/App 介面 → 最後才考慮改策略核心。
禁止：為 Web 重寫一份策略、為 UI 改 trading schema、為短期功能破壞資料流、把真實交易操作直接給未驗證使用者。
