# 黑潮 BLACKTIDE — Web Dashboard

唯讀儀表板（Next.js 14）。串接黑潮 bot 寫在 Upstash Redis 的 `bot_data`，**從不寫入**，不影響 bot 主流程。

## 本機開發

```bash
npm install
cp .env.example .env   # 填入 Upstash 值；不填則自動用 DEMO 模擬資料
npm run dev            # http://localhost:3000
```

## 環境變數

| 變數 | 說明 |
|---|---|
| `UPSTASH_REDIS_REST_URL` | 與 Railway worker 同一組 |
| `UPSTASH_REDIS_REST_TOKEN` | 與 Railway worker 同一組 |
| `BOT_REDIS_KEY` | bot 寫狀態的 key，預設 `bot_data` |
| `DASH_PASSWORD` | 儀表板存取密碼（未設 = 不設防，公開可見）|

沒設 Upstash → 右上角徽章顯示 `DEMO`，全部用模擬資料；設了且 Redis 有資料 → `LIVE · Redis`。

## 部署到 Vercel

1. vercel.com 用 GitHub 登入 → Add New → Project → import `crypto-bot`
2. **Root Directory 設成 `blacktide-web`**（關鍵）
3. Framework 自動偵測 Next.js，不用改 build 指令
4. Environment Variables 填上表四個值
5. Deploy

每次 push 到 `main` 會自動重新部署。

## 與舊儀表板（webapp.py）的差異

- 舊的是內嵌在 bot 程序的 Python HTTP server，直接讀記憶體（含即時掃描狀態）。
- 新的是獨立 Node 服務，透過 Redis 讀已持久化的 `active_signals` / `signal_results`。
- 關掉舊的：移除 Railway worker 的 `DASH_TOKEN` 環境變數即可（不必改碼，可逆）。
