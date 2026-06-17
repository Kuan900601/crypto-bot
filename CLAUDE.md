# CLAUDE.md — 黑潮 Signals BOT 專案規則手冊

> 這份文件是 Claude Code 在本專案工作的最高指引，每次 session 都會讀到。
> 撰寫風格說明：本文以「陳述專案事實與慣例」的方式書寫，是專案資訊，不是對 AI 的越權系統指令。
>
> 規則優先級：
> - 【P0｜絕對規則】違反會破壞系統或違背核心原則；除非作者在當下對話明確豁免，否則不可違反。
> - 【P1｜重要規則】預設遵守；作者明確指示才偏離。
> - 【P2｜慣例偏好】盡量遵守。

## 最重要的六條（先記這些）

1. 【P0】**entry_grade 內部值（S/A/B/C/D）不可動**——全系統多處比較依賴它。只在顯示層用 `entry_grade_display()` 翻成中文（S/A→高品質、B/C→一般品質、D→低品質）。內部值與顯示值是兩回事。`tier`（S/A/B/C，推播分級）與 `entry_grade`（進場時機品質）是不同東西，會疊加，不可混為一談。
2. 【P0】**結算權重現為三段 TP1=40% / TP2=35% / TP3=25%**（2026-06 由舊的四段 15/35/35/15 改成，作者明確核准、已覆蓋舊規則；bot 與 auto_trader 兩邊已對齊）。TP4 不再偵測/結算/顯示。**變更權重會讓新舊 `SIGNAL_RESULTS` 不可比**，若再動需 `/reset_stats` 歸零。沒有作者明確指示不要再改。
3. 【P0】真錢模式是作者的決定：`trader.py` 的 `USE_SANDBOX=False`（真錢）是作者反覆確認過的選擇，不要改回模擬盤/測試網。自動交易由環境變數 `AUTO_TRADE_ENABLED` 控制（未設或非 `"true"` 不啟動）——這是現在真正的安全閘門，不要移除、不要預設 true。
4. 【P0】兩個鐵律：讀 sig/signal/plan 字典一律用 `.get()`；任何 `.py` 改動後必跑 `python -m py_compile analyzer.py bot.py auto_trader.py trader.py`。
5. 【P0】Redis 寫入一律用命令陣列格式（`["RPUSH", key, value]`、`["SET", key, value]`），包在 try/except 內、失敗不影響主流程；不要改格式。
6. 【P1】流程：改動前先說明會動到哪些檔案/函式並等作者確認、給 diff 再 push、一次只改一件事、偏好給完整可運行檔案而非零碎 patch。先驗證再加功能（見第 1 章）——可引用提醒一次，但最終決定權在作者。

## 0. 一句話定位

黑潮 Signals BOT 是一個 Telegram 加密貨幣交易信號機器人。Python，部署在 Railway（service 名 `worker`），用 Upstash Redis 持久化。它掃描約 52 個幣、用技術指標產生進出場信號、推播到 Telegram；並透過 `auto_trader.py` 在 Bybit 永續合約上自動下單（真錢，由 `AUTO_TRADE_ENABLED` 控制）。交易所為 Bybit（V5 API、ccxt）；歷史上曾用 BingX，已全面遷移（殘留的 BingX 連結產生器已標記 deprecated）。目前 `BOT_VERSION = "v61"`。

## 1. 驗證原則【P1】

1.1 策略仍在驗證期，尚未以足夠樣本（目標約 50 筆乾淨交易）證明為正期望值。
1.2 評估策略的唯一依據是**期望值**，不是勝率。低勝率配正賠率可能賺，高勝率配爛賠率可能賠。
1.3 不美化數據；小樣本就是雜訊。連敗是任何正期望策略的必然，不追求「無連敗」。
1.4 作者已選擇在驗證期間就以真錢小額運行並持續擴充執行層，也另行開發網頁付費 SaaS——這些都是作者明知本原則仍做的決定，法律與財務風險由作者自負。本原則作為長期提醒保留；加功能時可引用一次，最終由作者定。

## 2. 架構與關鍵檔案

- `analyzer.py`（約 7400 行）：策略、技術指標、信號生成、新聞分析模組、快速動能偵測（`fast_breakout_check`）。系統的「大腦」。是 `CryptoAnalyzer` 類別；`bot.py` 以 `analyzer = CryptoAnalyzer()` 實例化使用。
- `bot.py`（約 4200 行）：Telegram 介面、推播、**結算**、Redis 持久化。`main()` 是進入點；auto_trader 以背景執行緒在 `main()` 末段啟動（受 `AUTO_TRADE_ENABLED` 閘門控制）。
- `auto_trader.py`（約 1000 行）：Bybit 自動下單橋接器（執行層）。Redis 隊列輪詢（`POLL_INTERVAL`＝15 秒）。負責開倉、整倉止損、分段 TP、移動止損階梯、平倉同步、殘單清理、心跳與事件回報。
- `trader.py`（約 230 行）：Bybit 連線與下單原語（`get_exchange`、`open_position_with_protection`、`open_position`、`get_positions`、`close_position`、`cancel_symbol_orders`、`get_balance`/`get_free_balance`、`_bybit_symbol_id`）。`USE_SANDBOX=False`（真錢）。
- `requirements.txt`：正式依賴（python-telegram-bot[job-queue]==21.6、aiohttp>=3.10.11、pandas==2.1.4、numpy==1.26.4、matplotlib==3.8.2、ccxt==4.5.56）。
- `requirements-dev.txt`：開發工具（ruff、pytest），與部署無關。
- `pyproject.toml`：ruff 與 pytest 設定（刻意不含 build-system / project，不影響部署）。
- `tests/`：pytest 測試（test_example.py 結算數學、test_v57.py funding/px_round、test_v61.py 快速動能）。
- `webapp.py` / `blacktide-web/`：網頁付費 SaaS（NextAuth + NOWPayments），與 bot 主流程分離。

資料流（信號 → 下單，Bybit）：
`bot.py` 產生信號 → `register_signal` 推進 Redis `signal_queue`（RPUSH+LTRIM，陣列格式；觀察單 / 進場品質 D / score≤26 不進佇列）→ auto_trader 背景執行緒（`AUTO_TRADE_ENABLED=true` 才跑）輪詢 → 過濾（tier、信號年齡、同幣不疊倉、最大倉數、價格偏離、連虧/熔斷）→ `open_position_with_protection`（Bybit 市價單**原子附帶 stopLoss**，再掛分段 reduceOnly TP 單）→ Bybit。

平倉同步：
`bot.py` `close_signal` → 推 `close_queue` → auto_trader `process_closes` → `cancel_symbol_orders` + `close_position`（reduceOnly 市價）。

狀態持久化：
- bot.py：單一 Redis key `bot_data`（`save_data`/`load_data`）。沒設 Redis 退回 `DATA_DIR`（預設 `/tmp`，重啟會丟）。
- auto_trader.py：`at:` 系列 key（實測：`at:processed_signals`、`at:processed_closes`、`at:trades`、`at:pending`、`at:day_equity`、`at:breaker_tripped`、`at:liquidations`、`at:pnl_ledger`、`at:heartbeat`、`at:last_cycle`、`at:events`、`at:waitlist`（v62 滿倉候補））。bot.py 另寫 `bt:last_scan`（主掃描耗時）。狀態存 Redis 以根治「換容器重放 backlog」。

## 3. 自動交易（執行層）詳解【真錢，謹慎】

- 模式：真錢（`USE_SANDBOX=False`，作者決定）。總開關 `AUTO_TRADE_ENABLED`（預設關）。允許等級 `AUTO_TRADE_TIERS`（預設 `S,A,B`）。
- 風險（已知，由作者承擔）：`AT_LEVERAGE`＝20、最多 `AT_MAX_POSITIONS`＝4 倉；極端情況多倉同時觸損可達淨值大幅回撤；日內熔斷 `MAX_DAILY_DD`（預設 0.10）跌破當日起始即停開新倉。帳戶只放可承受全損的金額。
- 倉位本金（v62 起固定等額）：每倉 = `淨值 ÷ AT_MAX_POSITIONS`，再夾 `min(權益/倉數, free_usdt×0.95)`。`SIZING_MODE=risk` 風險定額已移除、auto_trader 不再讀；`SIZING_MODE`/`RISK_PER_TRADE_PCT` 目前僅 `/at_status` 顯示用（殘留，不影響下單）。
- 滿倉排隊（v62）：滿 `AT_MAX_POSITIONS` 倉時，新信號 bot 端照推 TG、照寫 `signal_queue`；只在 auto_trader 下單層擋住——把信號推到 Redis `at:waitlist`（不丟棄、不 mark processed）。有空位時由新到舊補單，需通過 年齡 < `WAITLIST_MAX_AGE_MIN`（預設 60 分）、現價偏離 < `MAX_ENTRY_DRIFT_PCT`、同幣未持倉、仍有空位；超時/漂移過大則棄並 mark processed（不追高）。
- 開倉（v61）：`open_position_with_protection` 在進場市價單上**原子附帶整倉 stopLoss**（開倉即帶止損，無裸倉窗口）；讀回確認，未生效則用 V5 `position/trading-stop` fallback，仍失敗才視為裸倉緊急平倉。之後掛分段 reduceOnly TP 單；某段 TP 失敗不影響整倉止損、不再因此平倉。`AT_MAX_SL_PCT`（預設 0.035）夾止損距離。
- 移動止損階梯（v62，TP1 後更小心、小回踩掃不掉）：緩衝 = `max(TRAIL_BUFFER_MIN_PCT, 0.6×ATR/price)`（`TRAIL_BUFFER_MIN_PCT` 預設 0.004）；TP1 成交後 SL 移到 `min(entry−緩衝, swing_low−0.3×ATR)`（多單；空單鏡像，取更寬鬆者給空間）、TP2 後移到 `entry`（保本）、TP3 後移到 TP1。三段都再夾「SL 須離現價至少 `MIN_SL_GAP = max(0.8×ATR/price, 0.006)`」，且 SL 只往有利方向移、絕不設到現價的另一側。每段只做一次（`sl_stage`），用 V5 trading-stop 原子更新；失敗保留原止損並 push `at:events`。ATR/swing 由 `_trail_levels` 一次抓 1h K 線算出。
- **TP 拆分口徑（v61 已對齊）**：bot.py 結算與 auto_trader 真實下單**皆為三段 40/35/25**（TP1 落袋 40%，無 TP4）。`/edge` 仍是 SIM 的毛價格 %（不扣成本），`/real_pnl` 才是含手續費的真實數據——評估真實績效以 `/real_pnl` 為準。
- 防重放（v61）：backlog 只標記過舊（created 距今 > `SIGNAL_MAX_AGE_MIN`，預設 10 分）的信號為已處理，新鮮信號正常處理；`process_once` 內加信號年齡檢查與開倉前價格偏離檢查（`MAX_ENTRY_DRIFT_PCT`，預設 1.5）。限價單路徑由 `LIMIT_ORDERS`（預設 true）控制。
- 可觀測性（v61）：每輪寫 `at:heartbeat` 與 `at:last_cycle`（含各 skip 原因計數、queue/pending/open 數、last_error）；下單/餘額失敗把交易所原文 push 到 `at:events`，由 bot.py 60 秒 job 轉發 `ADMIN_ID`。`/at_debug` 一站式診斷。
- Bybit 注意事項：帳戶須為 **One-Way 單向模式**（啟動時 `set_position_mode(False)`）；資金須在**統一交易帳戶 UTA**（`get_balance` 讀 unified），API 須開**合約權限**、**不要設 IP 白名單**（Railway IP 會變）；取消條件單要帶對應 `orderFilter`；沙盒連線用 ccxt `set_sandbox_mode`（目前不啟用，真錢）；aiohttp 需 ≥3.10.11 與 ccxt 相容。

## 4. 結算邏輯（理解資料怎麼來）

`bot.py` 的 `close_signal()` 採分段加權結算，權重 `_weights = {1: 0.40, 2: 0.35, 3: 0.25}`：每個達成過的 TP（記在 `sig["tp_hit"]`）按權重結算該段，剩餘倉位用最終出場價結算，加總為 `final_pct`。若 `tp_hit` 非空，剩餘倉位出場價鉗制成「不差於成本」避免重複計虧。
- `is_win` 由 `final_pct > 0` 判定（不是看 exit_type）；`result` 可能寫 `SL_HIT`，但那只是出場機制，已實現 TP 利潤正確計入。最終出場記 `TP3_HIT`（TP3 為最終止盈）。
- `win_rate` 是公式推估值（×0.82 校準），真實樣本 ≥10 才用真實值覆蓋。
- 「帳面浮盈」（全倉現價）和「歷史結算值」（分段加權）會不同，正常。

## 5. 策略邏輯概覽（動策略前必讀）

開單過三道關卡：
5.1 **7+1 策略投票**（`strategy_consensus`）：7 個技術策略（趨勢追隨、動量、量價、均線排列、支撐阻力、BOS 突破、訂單流）+ 第 8 票新聞情緒（強度 ≥3 同方向加票）。需至少 2 票。量價票方向化（量增需搭配近 3 根淨變動同向）。
5.2 **五維評分**（滿分 100）：趨勢+動量+結構+量能+風險。
5.3 **進場品質分級 + tier 分級**：entry_grade（S/A/B/C/D）、tier（S/A/B/C）。
之後還要過：盈虧比硬門檻（TP1≥1.2R）、冷卻、保護模式（連敗 DEFENSIVE/CIRCUIT_BREAK）、大盤閘門（BTC 無趨勢高波動暫停）、情境閘門 `entry_context_gate`（`STRICT_CONTEXT_GATE` 控制，預設開）、自適應門檻（`adaptive_threshold`，v61 上調幅度上限 +5）、Kelly 倉位。
- TP 階梯（R 倍數）：1.5/2.5/3.5/5.0R（analyzer 內部仍算 tp4，但 bot 結算/顯示只用三段）。
- **快速動能「精選」搶先偵測（v62）**：`fast_momentum_scan`（bot.py 背景 job，interval 90s）掃 24h 漲跌幅前 12，抓 5m/15m/1h；`fast_breakout_check`（放量突破近期高/低 + 5m 連續同向 + 量>1.8x）回傳 0~100 強度。候選需同時滿足 強度≥`FAST_MIN_STRENGTH`(預設70)、RR≥`FAST_MIN_RR`(預設1.8)、1h 趨勢不逆向、無活躍信號；以綜合分（強度×量能×RR×趨勢一致性）排序後**每輪只推 `FAST_TOP_N`(預設1) 個**，並受「同幣 2h 不重複」「全體每小時 `FAST_MAX_PER_HOUR`(預設2)」節流。命中走正常 `register_signal`+推播+佇列，標「⚡精選動能」、tier=B、order_type=MARKET，受連虧/熔斷管制。
- **主動退出（結構破壞，v62 收緊）**：唯一會「因結構破壞主動平倉」的是 `analyzer.stale_signal_recheck` 回 `close_now` → bot `close_signal(RECHECK_EXIT)` → `close_queue`。v62 起要「同時」滿足才平：(a) 深虧 ≥ `max(STRUCT_EXIT_DD_RATIO×SL距離, STRUCT_EXIT_MIN_PCT)`（取較嚴者）；(b) 用**已收盤** 1h K，收盤破前段結構低/高 ≥ `STRUCT_BREAK_MARGIN`，且「連 2 根收盤都破」或「破壞當根爆量>均量1.8x」二選一。否則 HOLD，交給進場附帶的硬止損。`early_exit_signal` 只發警告、不平倉。
- C 級延遲推播：只有 C 級（無 B+ 信號）時，距上次 B+ 推播須過 `C_TIER_DELAY_MIN`（預設 30 分，原為 4.5h）才推。
- **緊急保底單**：盤整期硬擠的低質觀察單（score 26、進場品質 D），結構上偏負期望，由 `EMERGENCY_SIGNALS` 控制，**預設關**（`=true` 才啟用）。
- 已抓但尚未用進決策的資料：funding rate、多空比。

## 6. 修復史【P0：別重複改、別回退】

當前 `BOT_VERSION = "v61"`（版本字串一度停在 v56，v61 補正；v62 改動已上線但版本字串未再 bump，仍顯示 v61）。
- v53～v55（沿用）：真實勝率校準、盈虧比硬門檻、保護模式不靜音、結算 bug 修正（分段止盈正確計入）、TP 階梯重設 1.5/2.5/3.5/5R、波動自適應止損、大盤閘門、文字反解析重構（結構化 `_last_plans` 為主、regex fallback）、進場品質中文化、信心分數夾 0~100、Redis 持久化（SET 陣列格式）、全面字段容錯（.get）。
- v57（沿用）：`funding_extreme` 單位二次轉換 bug 已修（輸入已是百分比，`fr_pct = fr`，**不再 ×100**）；低價幣分級精度 `px_round`；`stale_signal_recheck` 餵 1h K 線；量價票方向化；情境閘門 `entry_context_gate`；`/edge`、`/gate_stats` 指令；緊急保底單改 `EMERGENCY_SIGNALS` 控制（預設關）。
- 結算權重 2026-06 由 15/35/35/15 改為 **40/35/25 三段**（作者核准、覆蓋舊 P0；TP4 移除）；交易所由 BingX 全面遷移到 **Bybit 真錢 One-Way**；執行層改 `trader.py`/`auto_trader.py`。
- 已停用且不要回退：EMA20 連續移動止損（會砍贏單）、`smart_tp_extend`（排序 bug）。保留：TP 觸發的止損階梯（刻意的鎖利機制）。
- **v61（本輪重點）**：
  · 開倉止損改 Bybit 原生附帶式（`open_position_with_protection`），根治「開倉後止損掛失敗→立刻自平」；V5 trading-stop fallback；只有真裸倉才緊急平倉。auto_trader TP_SPLIT 對齊三段 40/35/25。
  · 移動止損改階梯緩衝版（TP1 後 `entry−緩衝`、TP2 後 `entry`、TP3 後 TP1），解決「TP1 後被保本止損掃出場、幣再反彈」；bot 端 `notify_tp_hit` 同口徑。
  · 警告系統降噪：`check_signal_reversal`/`early_exit_signal` 由 15m 改 1h；`kline_reversal_check` 強 K 門檻 0.7→0.8 且需並立破 EMA20；反向警告冷卻 1h→2h、同信號最多 2 次、只發 watchers 不發頻道。
  · 延遲改善：C 級延遲由 4.5h 砍到 `C_TIER_DELAY_MIN`（預設 30 分）；新增快速動能搶先偵測；主掃描批次間隔 0.5→0.3s、掃描鎖 timeout 300→180s、記錄掃描耗時 `bt:last_scan`；`adaptive_threshold` 上調上限 +5。
  · `get_balance` 改讀統一帳戶 UTA；`get_free_balance`/清舊單補 log。
  · 可觀測性：`at:heartbeat`/`at:last_cycle`/`at:events` 轉發 ADMIN、`/at_debug` 強化（含掃描耗時）。
  · 選單去重（移除「即時動能」「今日為你挑選 TOP1」按鈕，先藏入口不刪碼，callback 保留）；BingX 連結產生器（`bingx_trade_url`/`bingx_spot_url`，無呼叫點）標記 deprecated；`bingx_swap_url` 已改寫成回傳 Bybit URL（仍在用）。
- **v62（本輪重點）**：
  · 快速動能改「精選 Top N」：候選收集→綜合分（強度×量能×RR×趨勢）排序→每輪只推 `FAST_TOP_N`(預設1)，加 `FAST_MIN_STRENGTH`(70)/`FAST_MIN_RR`(1.8)/同幣2h/`FAST_MAX_PER_HOUR`(2) 閘門；標「⚡精選動能」。新增 `_fast_rr`/`_fast_trend_consistency`。
  · 倉位本金固定等額 `淨值÷AT_MAX_POSITIONS`，移除 `SIZING_MODE=risk` 風險定額（`SIZING_MODE`/`RISK_PER_TRADE_PCT` 僅剩 `/at_status` 顯示）。
  · 滿倉排隊：滿倉信號進 Redis `at:waitlist`（不丟棄），有空位由新到舊補單（年齡 `WAITLIST_MAX_AGE_MIN`、漂移、同幣、空位檢查）；抽出 `_commit_open_record` 共用；`/at_debug` 增列 ⑤c 候補。
  · 結構破壞主動平倉收緊：`stale_signal_recheck` 的 `close_now` 改「已收盤 1h + 深虧(`STRUCT_EXIT_DD_RATIO`/`STRUCT_EXIT_MIN_PCT` 取較嚴者) + 結構破壞雙確認(`STRUCT_BREAK_MARGIN` + 連2根收盤或爆量)」，否則 HOLD 交給硬止損。
  · TP1 後移動止損更小心：緩衝改 `0.6×ATR`、TP1 取 `min(entry−緩衝, swing_low−0.3×ATR)`、全段夾 `MIN_SL_GAP=max(0.8×ATR%,0.006)` 離現價、只往有利方向移、絕不越過現價；新增 `_trail_levels` 取代舊 `_atr_pct`/`_trail_buffer_pct`。

## 7. 驗證門檻（什麼叫「策略被證明」）

- bot 的 `final_pct` 是**毛價格 %**，沒扣成本；成本門檻約 0.15~0.2%/筆（手續費+資金費+滑點）。
- 可交易最低標 ≈ 毛 +0.3~0.4%；「好」≈ 毛 ≥ +0.5% 且平均盈 ≥ 約 2× 平均虧。
- 20x 槓桿下除了期望值，還必須**接近零爆倉**（一次爆倉 = 該倉 −100% 保證金）。
- 預設判斷：約 **50 筆**乾淨交易、毛期望值明確 ≥ +0.4%、平均盈 > 平均虧、零爆倉 → 視為通過。30 筆只是第一眼。
- `/edge` 是 SIM 毛價格 %；`/real_pnl` 是含手續費的真實數據，才是最終答案。SIM 正期望是必要非充分。

## 8. 環境變數（實測 `os.getenv`/`os.environ.get` 全清單）

必要：`TELEGRAM_BOT_TOKEN`、`UPSTASH_REDIS_REST_URL`、`UPSTASH_REDIS_REST_TOKEN`、`BYBIT_API_KEY`、`BYBIT_API_SECRET`。
建議：`PYTHONUNBUFFERED=1`（否則 auto_trader 的 print log 會被緩衝、看起來像沒在跑）。
自動交易：`AUTO_TRADE_ENABLED`（預設 false）、`AUTO_TRADE_TIERS`（預設 `S,A,B`）、`AT_LEVERAGE`（預設 20）、`AT_MAX_POSITIONS`（預設 4）、`AT_MAX_SL_PCT`（預設 0.035）、`MAX_DAILY_DD`（預設 0.10）、`LIMIT_ORDERS`（預設 true）、`SIGNAL_MAX_AGE_MIN`（預設 10）、`MAX_ENTRY_DRIFT_PCT`（預設 1.5）、`TRAIL_BUFFER_MIN_PCT`（預設 0.004）、`WAITLIST_MAX_AGE_MIN`（v62 滿倉候補補單年齡上限，預設 60）。
　（`SIZING_MODE`/`RISK_PER_TRADE_PCT` 仍被讀，但 v62 起只用於 `/at_status` 顯示，不再影響倉位計算。）
快速動能（v62）：`FAST_MIN_STRENGTH`（預設 70）、`FAST_MIN_RR`（預設 1.8）、`FAST_TOP_N`（每輪推幾個，預設 1）、`FAST_MAX_PER_HOUR`（每小時上限，預設 2）。（舊 `FAST_MOMENTUM_MIN_STRENGTH` 已由 `FAST_MIN_STRENGTH` 取代。）
結構退出（v62）：`STRUCT_EXIT_DD_RATIO`（預設 0.6）、`STRUCT_EXIT_MIN_PCT`（預設 1.5）、`STRUCT_BREAK_MARGIN`（預設 0.5，單位 %）。
推播/策略：`C_TIER_DELAY_MIN`（預設 30）、`STRICT_CONTEXT_GATE`（情境閘門，預設開）、`EMERGENCY_SIGNALS`（預設 false）。
其他：`DATA_DIR`（無 Redis 時的本地檔目錄，預設 `/tmp`）、`TG_CHANNEL_ID`（預設 `@KuroshioSignal`）、`BLACK_HUNTER_CHANNEL`（預設空）、`ANTHROPIC_API_KEY`、`CRYPTOPANIC_TOKEN`（新聞模組，沒設靜默關閉）。
註：`ADMIN_ID` 是程式內常數（非環境變數）。

## 9. 指令列表（實測 `CommandHandler` 全清單）

`/start`、`/a`（=`/analyze`）、`/hunter`（手動黑潮掃描）、`/movers`（異動掃描）、`/kline`、`/trend`、`/sentiment`（=`/news`，新聞情緒）、`/testpush`、`/export`、`/reset_stats`、`/edge`（期望值驗證儀表）、`/gate_stats`（情境閘門擋下統計）、`/real_pnl`（含手續費真實損益）、`/at_status`（自動交易狀態）、`/at_debug`（自動交易一站式診斷：env 體檢、心跳、signal_queue、processed 交叉比對、last_cycle、bot 掃描耗時、限價單/熔斷、結論）。
其中 `/reset_stats`、`/edge`、`/gate_stats`、`/real_pnl`、`/at_status`、`/at_debug` 等管理用途指令限 `ADMIN_ID`。

## 10. 指令參考（開發）

- 語法檢查（完成標準）：`python -m py_compile analyzer.py bot.py auto_trader.py trader.py`
- 測試：`pytest`
- Lint（不改碼）：`ruff check .`；格式化（會改碼，斟酌）：`ruff format .`
- 部署：`git add . && git commit -m "..." && git push`（Railway 從 `main` 自動部署 `worker`）
- hooks：Claude Code 每次 Write/Edit `.py` 後自動 `py_compile`。

## 11. 未來方向（現在一律不做，等驗證通過）

按優先序：資金流數據（funding/多空比/OI）進決策、歷史位階百分位過濾、數據驅動調策略票權重（需 30~50 筆）、時段分析、進階大盤閘門（BTC.D/關鍵價位）、自適應學習（需 100+ 筆否則過擬合）。
擱置：自動下單執行層進一步強化（同幣去重已做、平倉同步已做）、網頁 Dashboard / App 擴充。提醒：對外收費在台灣涉《證券投資信託及顧問法》監管，需查證/諮詢專業人士；核心邏輯 `analyzer.py` 未來可改 API 重用，界面層需重寫。

## 12. 程式範例：對的寫法 vs 錯的寫法

讀 sig 字典：
```python
# 對
tp2 = sig.get("tp2")
tp_hit = sig.get("tp_hit", [])
# 錯（缺字段會崩潰）
tp2 = sig["tp2"]
```
entry_grade（內部值不動，只翻譯顯示）：
```python
# 對
grade = sig.get("entry_grade", "")     # 內部值維持 S/A/B/C/D
if grade in ("S", "A"): ...            # 用內部值做比較
msg += entry_grade_display(grade)      # 顯示時才翻成中文
# 錯（把內部值改成中文 → 多處比較全壞）
sig["entry_grade"] = "高品質"
```
新功能用開關 + 安全預設：
```python
if os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true":
    start_auto_trader()   # 預設關，要開才開
```
Redis 寫入（陣列格式 + 容錯）：
```python
if _USE_REDIS:
    try:
        _redis_cmd(["SET", key, value])
    except Exception as e:
        logger.error("redis set 失敗: " + str(e))
```

## 13. 溝通與協作【P2】

- 語言：繁體中文。程式碼/識別字/指令用英文。
- 作者在台灣，不是專業工程師，但看得懂程式、能跟著步驟做。
- 作者重視**誠實的回饋**，不喜歡空泛恭維。發現問題直說，包括指出作者想法可能有風險。
- 作者常用手機（討論）+ 電腦 Codespaces（寫 code）。
- 解釋先講重點/結論，需要時再展開細節。
- 不確定的事先查證（看程式碼、看官方文件），不要用記憶猜。
