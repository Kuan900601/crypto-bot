# CLAUDE.md — 黑潮 Signals BOT 專案規則手冊

> 這份文件是 Claude Code 在本專案工作的最高指引，每次 session 都會讀到。
> 撰寫風格說明：本文以「陳述專案事實與慣例」的方式書寫，是專案資訊，不是對 AI 的越權系統指令。
> 
> **規則優先級：**
> 
> - **【P0｜絕對規則】** 違反會破壞系統或違背核心原則。任何情況都不可違反，除非作者在當下對話中明確、具體地要求豁免。
> - **【P1｜重要規則】** 預設一律遵守；只有作者明確指示時才可偏離。
> - **【P2｜慣例與偏好】** 風格與習慣，盡量遵守。

-----

## 最重要的五條（細節見下文，先記這五條）

1. **【P0】先驗證，再加功能**：策略未被數據證明為正期望（目標約 50 筆乾淨交易）之前，不新增任何產品功能。
1. **【P0】不動兩樣東西**：結算權重（TP1=15%、TP2=35%、TP3=35%、TP4=15%）與 `entry_grade` 內部值（S/A/B/C/D）。
1. **【P0】兩個鐵律**：讀 sig 字典一律用 `.get()`；任何改動完成後必跑 `python -m py_compile analyzer.py bot.py`。
1. **【P0】安全**：預設一律 BingX 模擬盤、假錢；不在未經作者明確同意下切到真錢/實盤。
1. **【P1】流程**：改動前先說明會動到什麼並等作者確認、給 diff 再 push、一次只改一件事、偏好給「完整可運行檔案」而非零碎 patch。

-----

## 0. 一句話定位

黑潮 Signals BOT 是一個 Telegram 加密貨幣交易信號機器人。語言為 Python，部署在 Railway，使用 Upstash Redis 持久化。它掃描多個幣種、用技術指標產生進出場信號、推播到 Telegram；另有一個 BingX 自動下單模組（目前暫停、且僅在模擬盤）。

-----

## 1. 最高原則【P0】：先驗證，再加功能

這是整個專案的靈魂，凌駕一切其他規則。

1.1 專案目前處於「策略驗證期」。核心策略**尚未**被足夠數據證明為正期望值（+EV）。
1.2 在策略以足夠樣本（目標約 50 筆乾淨交易）證明為正期望之前，**不新增任何產品功能**。包括但不限於：新聞情緒權重上線、自動下單功能擴充、手機 App、訂閱收費、新增指標來源、新增策略票。
1.3 若作者提出加新功能：可以禮貌地引用本原則提醒一次，但**最終決定權在作者**；提醒後若作者仍要做，就照做。
1.4 評估策略的唯一依據是**期望值**，不是勝率。33% 勝率配正賠率可能賺，80% 勝率配爛賠率可能賠。
1.5 不美化數據。小樣本就是雜訊，誠實呈現。連敗是任何正期望策略的必然，不追求「無連敗」。
1.6 「寫程式」和「驗證策略」是兩件事。把執行層（auto_trader）做到完美，對一個還沒被證明會賺的策略沒有意義——那是驗證之後才做的事。

為什麼這條最重要：歷史回測在多個月份、多個策略上一再顯示負或樣本外為負的期望值。在數據翻正之前，任何「加料」都只是把一個可能在賠錢的系統包裝得更複雜。

-----

## 2. 架構與關鍵檔案

- `analyzer.py`（約 7000 行）：策略、技術指標計算、信號生成、新聞分析模組。系統的「大腦」。
- `bot.py`（約 3300 行）：Telegram 介面、推播、**結算**、Redis 持久化。`main()` 是進入點；auto_trader 以背景執行緒在 `main()` 末段啟動。
- `auto_trader.py`：BingX 自動下單（執行層）。目前**暫停**，由環境變數 `AUTO_TRADE_ENABLED` 控制（未設或非 `"true"` 不啟動）。僅在 BingX 模擬盤（VST 假錢）運行。
- `requirements.txt`：正式依賴（python-telegram-bot[job-queue]==21.6、aiohttp>=3.10.11、pandas==2.1.4、numpy==1.26.4、matplotlib==3.8.2、ccxt==4.5.56）。
- `requirements-dev.txt`：開發工具（ruff、pytest），與部署無關。
- `pyproject.toml`：ruff 與 pytest 設定（刻意不含 build-system / project，不影響部署）。
- `tests/`：pytest 測試。
- `.claude/settings.json`：Claude Code hooks（改完 `.py` 自動 py_compile）。
- `.gitignore`、`CLAUDE.md`（本檔）。

**資料如何流動（信號 → 下單）：**
`bot.py` 產生信號 → 推進 Redis 隊列（`signal_queue`，RPUSH + LTRIM）→ `auto_trader.py` 背景執行緒讀隊列 → BingX 下單。

**狀態如何持久化：**
所有狀態（favorites、active_signals、signal_results、symbol_losses）打包進**單一** Upstash Redis key `bot_data`（由 `save_data` / `load_data` 處理）。沒設 Redis 時退回 `/tmp/bot_data.json`（重啟會丟）。

**環境變數：**

- `TELEGRAM_BOT_TOKEN`：Telegram bot 金鑰（必要）。
- `UPSTASH_REDIS_REST_URL`、`UPSTASH_REDIS_REST_TOKEN`：Redis（沒設退回 /tmp 本地檔）。
- `ANTHROPIC_API_KEY`、`CRYPTOPANIC_TOKEN`：新聞分析用（可選，沒設則新聞功能靜默關閉）。
- `AUTO_TRADE_ENABLED`：自動下單開關（未設或非 “true” 不啟動，預設關）。

-----

## 3. 絕對規則【P0】（違反會壞事）

3.1 **結算權重固定**：TP1=15%、TP2=35%、TP3=35%、TP4=15%。歷史 `SIGNAL_RESULTS` 依賴此設定，變更會讓所有舊數據不可比、毀掉驗證基礎。不更動。

3.2 **`entry_grade` 內部值（S/A/B/C/D）不可動**。全系統有 **7 處**依賴它做比較判斷。需要顯示給人看時，**只**在顯示層用 `entry_grade_display()` 翻成中文（S/A→高品質、B/C→一般品質、D→低品質）。內部值與顯示值是兩回事。

3.3 **`tier` 與 `entry_grade` 是不同的東西**，會疊加，不可混為一談。tier=S/A/B/C 是推播分級；entry_grade=S/A/B/C/D 是進場時機品質。

3.4 **讀 sig 字典一律用 `.get()` 加預設值**，絕不直接索引 `sig["xxx"]`。缺字段在歷史資料與重啟情境下很常見，直接索引會讓整個結算/監控迴圈崩潰。

3.5 **任何程式改動完成後，必須跑** `python -m py_compile analyzer.py bot.py` 確認無語法錯誤，才算完成。（已設 hook 自動跑，但仍以此為「完成」的標準。）

3.6 **不可在未經作者當下明確同意的情況下，把系統切到真錢/實盤。** 具體：不動沙盒開關使其連到實盤、不把 `AUTO_TRADE_ENABLED` 預設改成啟用、不移除模擬盤限制。預設一律模擬盤、假錢。

3.7 **不重新引入、也不重複修已經修過的問題**（見第 9 節修復史）。改動前先確認該問題是否已處理。

3.8 **一次只改一件事。** 驗證期間把多個改動混在一起，會讓「哪個改動造成數據變化」無法歸因。除非作者要求批次處理，否則一個改動、一次驗證。

-----

## 4. 重要規則【P1】（預設遵守）

4.1 **開發流程**：(a) 改動前先用文字說明會動到哪些檔案、哪些函式、為什麼；(b) 等作者確認；(c) 才動手改；(d) 跑 py_compile；(e) 提供 diff 讓作者審查；(f) 作者同意後才 push。不要擅自連續改一堆。

4.2 **偏好完整可運行的檔案版本**，而非零碎 patch。作者已驗證這樣對他最有效。改大段時，給整個函式或整個檔案的完整版本。

4.3 **環境變數**：優先讀 Railway 環境變數，本地 Codespaces 退回讀 `.env`，兩種環境都要支援。

4.4 **Redis 寫入**：用 Upstash REST 機制，命令採**陣列格式** `["SET", key, value]`（這個格式很關鍵），包在 `if _USE_REDIS` 與 try/except 內，失敗不影響主流程。

4.5 **部署**：`git add . && git commit -m "..." && git push`。Railway 從 `main` 分支自動部署，service 名為 `worker`。

4.6 **改動要可逆、要有 fallback**。新功能用環境變數開關（像 `AUTO_TRADE_ENABLED`），預設安全值。沒設 API key 的模組要靜默關閉、不影響主流程（新聞模組就是這樣設計）。

4.7 **不引入新的第三方依賴**，除非必要且先告知作者（會影響 requirements.txt 與部署）。

-----

## 5. 指令參考

- 語法檢查（完成標準）：`python -m py_compile analyzer.py bot.py`
- 測試：`pytest`
- Lint（不改碼，只報告）：`ruff check .`
- 格式化（會改碼，作者習慣審 diff，斟酌使用）：`ruff format .`
- 安裝開發工具：`pip install -r requirements-dev.txt`（或 `pip install ruff pytest`）
- 部署：`git add . && git commit -m "..." && git push`

hooks 已設定：Claude Code 每次 Write/Edit `.py` 檔後會自動 `py_compile`，有語法錯會回報並要求修正。

-----

## 6. BingX 雷區【P0／P1】（接交易所時必看）

6.1 BingX 對沖模式（Hedge Mode）：`reduceOnly` 會回傳 **error 109400**，必須改用 `positionSide`。
6.2 止盈/止損**不能**與開倉同一張單下。必須先市價開倉，再分別各下一張 `STOP_MARKET` 與 `TAKE_PROFIT_MARKET`（兩步法）。
6.3 沙盒連線用 ccxt 的 `set_sandbox_mode(True)`，**不要**手動覆寫 API URL。
6.4 aiohttp 需 ≥3.10.11 才與 ccxt 相容。

-----

## 7. 結算邏輯詳解（理解資料怎麼來）

`bot.py` 的 `close_signal()` 採用**分段加權結算**：

- 每個達成過的 TP（記在 `sig["tp_hit"]`）按其權重結算該段利潤。
- 剩餘倉位用最終出場價（SL / TP4 / 現價）結算。
- 加總為 `final_pct`。
- 加固：若 `tp_hit` 非空，剩餘倉位出場價會被鉗制成「不差於成本」，避免重複計虧。

**關鍵結論**：一筆「達到 TP3 後，止損移到 TP2、之後回落到 TP2 出場」的交易，已實現的 TP1/TP2/TP3 利潤仍**正確計入**，會記成大勝（實測某 XRP 空單算出 +8.83%），不是虧損。

- `is_win` 由 `final_pct > 0` 判定（不是看 exit_type）。
- `result` 欄位會寫 `SL_HIT`，但那只是出場機制，利潤與 `tp_hit_count` 是正確的。

其他重點：

- `win_rate` 是公式推估值（×0.82 校準），不是真實回測；當真實樣本 ≥10 才用真實值覆蓋。
- 「帳面浮盈」（全倉現價）和「歷史結算值」（分段加權）會不同，這是正常的。

-----

## 8. 策略邏輯概覽（動策略前必讀）

開單要過三道關卡：
8.1 **7+1 策略投票**（`strategy_consensus`）：7 個技術策略（趨勢追隨、動量、量價、均線排列、支撐阻力、BOS 突破、訂單流）+ 第 8 票新聞情緒（情緒看多/看空且強度 ≥3 時加同方向票）。需至少 2 票。
8.2 **五維評分**（`score_dimensions`，滿分 100）：趨勢 + 動量 + 結構 + 量能 + 風險。
8.3 **進場品質分級 + tier 分級**：entry_grade（S/A/B/C/D）、tier（S/A/B/C）。

之後還要過：盈虧比硬門檻（TP1 ≥ 1.2R）、冷卻、保護模式（連敗時 DEFENSIVE / CIRCUIT_BREAK）、大盤閘門（BTC 無趨勢高波動時暫停）、自適應門檻、Kelly 倉位。

其他事實：

- TP 階梯：1.5 / 2.5 / 3.5 / 5.0 R。
- 約 52 個幣的掃描池。系統偏多（LONG-biased）。
- **緊急保底單**：盤整期硬擠的低質觀察單（score 26、進場品質 D），已加嚴觸發條件（ADX>15 + RSI>60/<40）。結構上偏負期望，未來可能作為「過濾掉」的候選。
- 已抓但**尚未用進決策**的資料：funding rate、多空比。（屬未來強化，現在別接。）

-----

## 9. 目前狀態（驗證期）與修復史【P0：別重複改、別回退】

**目前的「乾淨靜態 base」狀態：**

- **已停用**：EMA20 連續移動止損（會砍贏單）、`smart_tp_extend`（智能 TP 延伸；它有「只改 TP2/TP3、漏改 TP4」的排序 bug）。
- **保留**：TP 觸發的止損階梯（達某 TP 後止損移到前一個 TP）——這是刻意保留的合理鎖利機制，**不是**要拔掉的東西。
- `auto_trader` 暫停中（`AUTO_TRADE_ENABLED` 未設）。
- 正在累積乾淨的 SIM CSV 數據以評估期望值。

**已完成、不要重做或回退的修復：**

- v53～v55：真實勝率校準、盈虧比硬門檻、保護模式不靜音、結算 bug 修正（分段止盈正確計入）、TP 階梯重設 1.5/2.5/3.5/5R、波動自適應止損、大盤閘門、TP1 後保本改「鎖 30%」、文字反解析重構（結構化 `_last_plans` 為主、regex 為 fallback）、進場品質中文化（顯示層）、信心分數夾 0~100、Redis 持久化（SET 陣列格式）、全面字段容錯（.get）。
- 改動 1：停用 EMA20 移動止損（bot 不再變動 `sig["sl"]`、不推「止損智能上移」）。
- 改動 2：結算訊息依 `final_pct` 正負顯示「獲利/虧損」、數字取絕對值。
- 改動 3：連虧計數加 `and final_pct < 0` 條件。
- 改動 4：`datetime.fromisoformat(created)` 加 try/except 容錯。
- 改動 5：新增 `/reset_stats` 指令（限 ADMIN_ID）。
- 改動 6：停用 `smart_tp_extend`（`if tp_level == 1:` → `if False:`）。
- 改動 7：`auto_trader` 啟動改由 `AUTO_TRADE_ENABLED` 控制（預設關）。

-----

## 10. 驗證門檻（什麼叫「策略被證明」）

- bot 的 `final_pct` 是**毛價格 %**，沒扣成本。
- 成本門檻約 0.15~0.2%/筆（手續費 + 資金費 + 滑點）。
- 淨損益打平 ≈ 毛期望值 +0.15~0.2%。
- 可交易最低標 ≈ 毛 +0.3~0.4%；「好」≈ 毛 ≥ +0.5%，且平均盈最好 ≥ 約 2× 平均虧。
- 15x 槓桿下：除了期望值，還必須**接近零爆倉**（一次爆倉 = 該倉 −100% 保證金）。
- 預設判斷標準：約 **50 筆**乾淨交易、毛期望值明確 ≥ +0.4%、平均盈 > 平均虧、零爆倉 → 視為「通過」。30 筆只是「第一眼」（誤差很大）。
- CSV 是 SIM，不是真錢。正期望的 SIM 是**必要、非充分**；通過後仍要先驗證真實執行對得上，才談真錢。

-----

## 11. 未來方向（現在一律不做，等驗證通過）

按優先序（純記錄，**現在別碰**）：

1. 用資金流數據（funding rate、多空比、OI）進決策。
1. 歷史位階（價格/波動率百分位）當過濾器。
1. 數據驅動調策略票權重（需 30~50 筆）。
1. 時段分析（亞/歐/美時段、週末）納入決策。
1. 進階大盤閘門（BTC.D、關鍵價位）。
1. 自適應學習（需 100+ 筆，否則過擬合）。

其他擱置項：

- 新聞模組上線（需設 ANTHROPIC_API_KEY、CRYPTOPANIC_TOKEN）。
- 自動下單執行層修復（同幣去重、bot 平倉同步到 BingX、下新 TP/SL 前先撤舊單）——驗證通過後才做。
- 網頁 Dashboard / App / 訂閱收費。提醒：對外收費在台灣涉《證券投資信託及顧問法》監管，需查證/諮詢專業人士；核心邏輯（analyzer.py）未來可改成 API 重用，界面層需重寫。

-----

## 12. 程式範例：對的寫法 vs 錯的寫法

**讀 sig 字典**

```python
# 對
tp2 = sig.get("tp2")
tp_hit = sig.get("tp_hit", [])
if sig.get("direction") and sig.get("entry"):
    ...
# 錯（缺字段會崩潰）
tp2 = sig["tp2"]
```

**entry_grade（內部值不動，只翻譯顯示）**

```python
# 對
grade = sig.get("entry_grade", "")     # 內部值維持 S/A/B/C/D
if grade in ("S", "A"):                # 用內部值做比較
    ...
msg += entry_grade_display(grade)      # 顯示時才翻成中文
# 錯（把內部值改成中文 → 7 處比較全壞）
sig["entry_grade"] = "高品質"
```

**新功能用開關 + 安全預設**

```python
# 對
import os
if os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true":
    start_auto_trader()
# 預設關，要開才開
```

**Redis 寫入（陣列格式 + 容錯）**

```python
# 對
if _USE_REDIS:
    try:
        _redis_cmd(["SET", key, value])   # 陣列格式
    except Exception as e:
        logger.error("redis set 失敗: " + str(e))
```

-----

## 13. 溝通與協作【P2】

- 語言：繁體中文。程式碼/識別字/指令用英文。
- 作者在台灣，不是專業工程師，但看得懂程式、能跟著步驟做。
- 作者重視**誠實的回饋**，不喜歡空泛的恭維。發現問題直說，包括指出作者的想法可能有風險。
- 作者常用手機（討論）+ 電腦 Codespaces（寫 code）。
- 解釋先講重點/結論，需要時再展開細節。
- 不確定的事先查證（看程式碼、看官方文件），不要用記憶猜。