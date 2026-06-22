# 黑潮 BLACKTIDE — 全站前端重做計畫書（給 Claude Code）

> 目標：把整個 blacktide-web 的**前端視覺**全部重做成首頁（reference/landing-v8.jsx）的風格，並優化整站，最後一次替換上線。
> 鐵則：**只換前端視覺外殼，完全保留後端 / 資料層 / 付費 / 認證邏輯。**

---

## 0. 必讀文件

- `reference/landing-v8.jsx`：新版首頁範本（視覺與互動的標準）。
- `blacktide-design-system.md`：設計系統規格（色彩、字型、元件、母題、效能、合規）。**全站每頁都要遵守。**

---

## 1. 安全鐵則（最重要，違反會弄壞正式站）

1. **不動後端邏輯**：不改 bot.py / analyzer.py / 任何策略；不改認證核心（NextAuth callbacks、tier 計算 tierOf、session）、付費（NOWPayments invoice/IPN webhook）、Redis 資料存取、API 的「資料取得與授權」邏輯。只動「畫面呈現層」。
2. **只換前端視覺**：把每個頁面的 UI 重寫成新風格，但**沿用現有的 data fetching、hooks、API 呼叫、表單提交、路由**。資料怎麼來、權限怎麼擋，維持現狀。
3. **一個分支做完再上線**：開一個新分支（例如 `redesign`），全部頁面在這個分支上做完、本地驗證、build 全過、我看完整 diff 確認後，**才一次 merge 到 main 上線**。過程中 main 維持現有正式站不動。
4. **逐頁驗證**：每改完一頁，跑 `npx tsc --noEmit` + `npm run build`，確認該頁能編譯、能渲染、功能沒壞，再做下一頁。
5. **付費與認證流程零改動驗證**：完成後務必確認——既有用戶能登入、tier（free/Plus/Pro）判斷正確、付費 webhook 路徑沒被動到、信號付費牆仍生效。

---

## 2. 動手前流程（不要直接改檔）

第一步，先做**盤點**，回報給我，等我確認後才開始改：

1. 列出 blacktide-web 的完整路由 / 頁面清單（app/ 底下所有 page.tsx 或 pages/）。
2. 列出現有共用元件（Nav、Layout、Footer、卡片、認證 gating 等）。
3. 列出每個頁面目前的資料來源（呼叫哪些 API / hooks）。
4. 對照下方「頁面清單」，告訴我：哪些頁面存在、哪些缺、你打算怎麼分批做、預計動到哪些檔。
5. 確認 /api/signals、/api/market 等回傳的資料形狀（欄位）。

我確認後，再進入施工。每一批改動合併成一個 diff 給我看。

---

## 3. 共用基礎建設（先做這個，全站才一致）

把 landing-v8.jsx 裡的設計系統抽成**可重用的共用元件 + 全域樣式**，讓每個頁面套用：

- **全域樣式 / tokens**：色彩、字型、keyframes、`.gold-text`/`.teal-text`/`.cta` 等 class，放到全域 CSS 或共用樣式檔。
- **共用背景層**：`GlobalCurrent`（洋流 Canvas）、`Plankton`、`ScrollBar` → 做成一個 `SiteBackground` 包在 Layout，全站共用一套，不要每頁各跑一個 Canvas（效能）。
- **共用導覽**：`Nav`（滾動變化）+ `Drawer`（左側選單，連真實路由）+ 個人資料/登入按鈕（依 session 切換）。放進共用 Layout。
- **共用頁尾**：`Footer` + 四份法律彈窗 `LegalModal`（服務條款/免責聲明/隱私權政策/風險揭露聲明）。法律內容沿用 landing-v8.jsx 裡的版本（或你站上既有官方版本，擇一，與我確認）。
- **共用元件**：`LogoMark`（動態波浪 logo）、`Corner`（HUD 角框）、`Counter`（數字滾動）、`CTA`、卡片殼、`Badge`、聲納/掃光等。
- **共用 Layout**：`SiteBackground` + `Nav` + `{children}` + `Footer`，所有頁面包在裡面，確保一致。

→ 全站必須是同一套背景、同一個 Nav/Drawer/Footer，只有中間內容不同。

---

## 4. 頁面清單與每頁重點

> 每頁：套用設計系統 + 共用 Layout，視覺全換新風格，**資料沿用現有來源**。下面標出每頁的對接重點。先以盤點結果為準，缺的頁再討論。

### 4.1 首頁（行銷著陸 / 市場總覽進入點）
- 直接採用 landing-v8.jsx 的結構：Hero（燈塔+海浪+漂浮信號卡）→ 行情跑馬燈 → 信號戰績流 → 底部震撼轉換區 → 頁尾。
- 跑馬燈接 /api/market 真實幣價（移除假隨機跳動，真實值 + 定期刷新）。
- 信號流接 /api/signals：已結算公開真實進場價+結果+損益%；進行中/最新鎖價。**照實呈現輸贏，不挑漂亮的**；真實樣本不足就不強調損益數字。
- 已登入用戶可導向其儀表板/市場總覽內容。

### 4.2 黑潮船長 信號（/signals，PRO）
- 信號列表用新卡片/列表風格（左側強調條、掃光、MONO 數字、HUD 角框）。
- 沿用現有 tier 付費牆：未付費者鎖進場/止損/止盈價位，付費者看完整。沿用現有 sanitizeSignal 邏輯，不要重寫授權。
- 五維評分用聲納雷達視覺呈現。

### 4.3 AI 分析（/analysis，PLUS）
- 分析內容用毛玻璃卡 + 聲納/雷達 + 能量條視覺。沿用現有資料與 tier gating。

### 4.4 新聞中心（/news，PLUS）
- 新聞列表/卡片新風格。沿用現有新聞資料來源與 gating。

### 4.5 事件行事曆（/calendar）
- 行事曆/時間軸用洋流線串接的時間軸風格。沿用現有資料。

### 4.6 美股分析（/stocks）
- 同信號/分析的卡片與圖表風格。沿用現有資料。

### 4.7 異常監控（/monitor，PLUS）
- 監控儀表板：HUD 終端風（紅黃綠燈頂列、即時跳動用真實資料）。沿用現有資料與 gating。

### 4.8 策略回測（/backtest，PRO）
- 回測結果用終端/資料卡風格。**回測績效照實，不美化。** 沿用現有資料與 gating。

### 4.9 會員中心（/account）
- 個人資料、訂閱方案、tier 狀態、到期日。新風格卡片。沿用現有 session/付費資料，付費升級沿用現有 NOWPayments 流程，不要改金流。

### 4.10 福利中心（/rewards，推薦獎勵）
- 推薦碼/獎勵頁新風格。沿用現有推薦系統邏輯。

### 4.11 使用教學（/tutorial）
- 教學頁新風格（步驟用洋流流程、聲納等母題）。

### 4.12 常見問題（/faq）
- 手風琴問答新風格（毛玻璃卡、金色展開）。

### 4.13 登入 / 註冊（/login、/register）
- 表單用新風格（深海卡、金色輸入框、CTA）。**完全沿用現有認證邏輯與表單提交**（NextAuth、email 驗證、註冊送 3 日 Plus），只換外觀。註冊後流程不變。

### 4.14 法律頁（/legal/*）
- 既有 /legal/terms 等頁保留，套新風格；同時首頁/各頁底部用彈窗版（LegalModal）方便閱讀。兩者內容一致。

---

## 5. 技術要求

- 需用 canvas/hooks/window 的頁面為 Client Component（'use client'）。
- 維持 TypeScript，補上必要型別，`npx tsc --noEmit` 零錯誤。
- 響應式顯示/隱藏一律 CSS `@media`，**禁止 render 時用 window.innerWidth 判斷**。
- 字型含 Microsoft JhengHei。
- 效能：全站共用一套背景 Canvas；手機降載（dpr≤1.4、粒子減半、隱藏暫停）；transform 動畫加 will-change；支援 prefers-reduced-motion。
- favicon / 社群 / PWA 圖示指向 `public/brand/blacktide-logo-1024.png`（我會放進去），更新 manifest 與 metadata。
- Vercel 設定（region hnd1 等）維持現狀不動。

---

## 6. 上線前檢查清單（merge 到 main 前逐項確認）

- [ ] 全站每頁套用統一新風格、共用 Nav/Drawer/Footer/背景。
- [ ] `npx tsc --noEmit` 零錯誤；`npm run build` 全路由正常。
- [ ] 手機（375–414px）每頁不破版、文字不被切、Nav 不擠。
- [ ] 既有用戶可登入；free/Plus/Pro tier 判斷正確。
- [ ] 信號付費牆仍生效（未付費看不到進行中價位）。
- [ ] 付費升級流程（NOWPayments）路徑未被更動、可正常運作。
- [ ] 信號/回測/分析顯示的績效為真實資料、有賺有賠照實、無捏造美化。
- [ ] 行情數字為真實值（非假跳動）。
- [ ] 法律資訊（四份）每頁底部可開、內容正確。
- [ ] 效能：手機滑動順、不發燙掉幀。
- [ ] 我已看過完整 diff 並確認。

全部打勾後，一次 merge 上線。

---

## 7. 流程紀律

- 不動 bot.py / analyzer.py / 後端策略。
- 每批改動一個 paste block / 一個 diff，我先看再決定。
- 有任何「需要動到後端授權或金流」的情況，先停下來問我，不要自己改。
