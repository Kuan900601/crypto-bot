# docs/deployment.md

# Deployment 文件

描述部署、環境變數與驗證流程。

---

## 1. 部署總覽

BOT：`GitHub main → Railway worker → Python Telegram Bot → Upstash Redis → Bybit`
Web：`GitHub main → Vercel → Next.js → NextAuth → NOWPayments → Redis`

---

## 2. BOT 必要環境變數

```text
TELEGRAM_BOT_TOKEN
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
BYBIT_API_KEY
BYBIT_API_SECRET
```

建議：`PYTHONUNBUFFERED=1`（否則 auto_trader 的 print log 會被緩衝、看似沒在跑）。

---

## 3. Auto Trader / 策略環境變數（v62 實測全清單）

自動交易：
```text
AUTO_TRADE_ENABLED        # 預設 false；非 "true" 不啟動
AUTO_TRADE_TIERS          # 預設 S,A,B
AT_LEVERAGE               # 預設 20
AT_MAX_POSITIONS          # 預設 4
AT_MAX_SL_PCT             # 預設 0.035
MAX_DAILY_DD              # 預設 0.10
LIMIT_ORDERS              # 預設 true
SIGNAL_MAX_AGE_MIN        # 預設 10
MAX_ENTRY_DRIFT_PCT       # 預設 1.5
TRAIL_BUFFER_MIN_PCT      # 預設 0.004
WAITLIST_MAX_AGE_MIN      # 預設 60（滿倉候補補單年齡上限）
```

快速動能（v62）：
```text
FAST_MIN_STRENGTH         # 預設 70
FAST_MIN_RR               # 預設 1.8
FAST_TOP_N                # 預設 1（每輪推幾個）
FAST_MAX_PER_HOUR         # 預設 2
```

結構退出（v62）：
```text
STRUCT_EXIT_DD_RATIO      # 預設 0.6
STRUCT_EXIT_MIN_PCT       # 預設 1.5
STRUCT_BREAK_MARGIN       # 預設 0.5（單位 %）
```

推播/策略 / 其他：
```text
C_TIER_DELAY_MIN          # 預設 30
STRICT_CONTEXT_GATE       # 情境閘門，預設開
EMERGENCY_SIGNALS         # 預設 false
DATA_DIR                  # 無 Redis 時本地檔目錄，預設 /tmp
TG_CHANNEL_ID             # 預設 @KuroshioSignal
BLACK_HUNTER_CHANNEL      # 預設空
ANTHROPIC_API_KEY
CRYPTOPANIC_TOKEN         # 新聞模組，沒設靜默關閉
```

棄用（仍可設但無作用）：`SIZING_MODE`、`RISK_PER_TRADE_PCT`、`FAST_MOMENTUM_MIN_STRENGTH`（已由 `FAST_MIN_STRENGTH` 取代）。
註：`ADMIN_ID` 是程式內常數，非環境變數。

重要：`AUTO_TRADE_ENABLED` 未設為 true 不會啟動自動交易。

---

## 4. Web 環境變數

```text
NEXTAUTH_URL
NEXTAUTH_SECRET
NOWPAYMENTS_API_KEY
NOWPAYMENTS_IPN_SECRET
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
RESEND_API_KEY
RESEND_FROM
```

規則：Production `NEXTAUTH_URL` 必須是正式網域；IPN callback 須與 NOWPayments 後台一致；secret 不得用 `NEXT_PUBLIC`；不得 commit `.env`。

---

## 5. Python 驗證

```bash
python -m py_compile analyzer.py bot.py auto_trader.py trader.py   # 改完必跑
pytest
ruff check .
ruff format .   # 會改碼，斟酌
```

---

## 6. Web 驗證

```bash
npm run lint && npm run build      # 或 pnpm lint / pnpm build
```
build 失敗不得部署、不得宣稱完成、先修 build error。

---

## 7. Git 部署流程

```bash
git status && git add . && git commit -m "message" && git push
```
Railway / Vercel 自動部署。不得 commit secret / `.env` / 大型無關檔；commit message 要描述實際改動。

---

## 8. Railway 注意

只啟動 bot.py main；log 可能緩衝（建議 `PYTHONUNBUFFERED=1`）；容器重啟可能丟 `/tmp`，所以狀態要存 Redis。

---

## 9. Vercel 注意

API route 須符合 serverless 限制；webhook route 不可被前端快取；`NEXTAUTH_URL` 要正確；build error 阻止部署；環境變數改完要 redeploy。

---

## 10. 安全部署檢查表

py_compile 通過、Web build 通過、沒有 `.env` 被 commit、沒有 API key 出現在 log、Redis key schema 未破壞、`AUTO_TRADE_ENABLED` 未被預設 true、`USE_SANDBOX` 未被自動改、NOWPayments IPN Secret 驗證存在、付費 API 有 server-side check。
