# 黑潮 BLACKTIDE — 設計系統規格（Design System）

> 這份文件定義全站視覺語言。所有頁面、所有元件都必須遵守，確保整站風格一致。
> 來源範本：`reference/landing-v8.jsx`（首頁），這份文件是它的抽象化規格。

---

## 1. 色彩 Tokens

```
abyss   #03060E   最深背景（頁面底色）
deep    #06101E   次深背景（區塊）
navy    #0A1A2E   卡片底
current #13355A   洋流藍（光暈、漸層）
ink     #EEF4F2   主文字（近白）
mut     #8FA6B5   次文字（灰藍）
dim     #566B7C   弱文字（標籤、註解）
gold    #E8C66E   主金（品牌色、CTA、重點）
gold2   #C9A24B   暗金（漸層下緣）
goldDk  #8A6E22   最暗金（漸層起點）
teal    #37D6C4   螢光綠（深海生物光、次強調、做多）
tealDk  #1B8A82   暗螢光綠
green   #46D6A0   獲利/做多/成功
rose    #F0697C   虧損/做空/失敗
line     rgba(120,180,200,0.12)   一般分隔線
lineGold rgba(232,198,110,0.16)   金色分隔線
```

漸層慣例：
- 金色文字漸層 `.gold-text`：linear-gradient(92deg,#8A6E22,#E8C66E 38%,#FFF6D6 50%,#E8C66E 62%,#8A6E22) + shimmer 動畫
- 螢光綠文字漸層 `.teal-text`：同上換 teal 色系
- CTA 按鈕底：linear-gradient(135deg,#FFF4D2,#E8C66E 45%,#C9A24B)

---

## 2. 字型

```
SANS  -apple-system,"PingFang TC","Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif
SERIF "Cinzel","Noto Serif TC",Georgia,serif   （品牌名、logo 文字、標題裝飾）
MONO  ui-monospace,"SF Mono",Menlo,monospace   （數字、價格、代號、戰績）
```
- 數字一律用 MONO（價格、損益%、統計數字、幣種代號）。
- 品牌名「黑潮 BLACKTIDE」「SIGNALS · PRO TERMINAL」用 SERIF。
- **務必含 Microsoft JhengHei**，否則台灣 Windows 會變新細明體。

---

## 3. Logo

- 站內 logo 用動態 SVG 波浪標誌（見 landing-v8.jsx 的 `LogoMark` 元件）：圓形深海底 + 三道金色波浪線 + 一道螢光綠細浪 + 旋轉刻度環 + 內圈金弧 + 掃光 + hover 加速。不需圖檔，向量、會動、各尺寸清晰。
- favicon / 社群分享 / PWA 圖示：用 `public/brand/blacktide-logo-1024.png`（已提供）。

---

## 4. 核心視覺母題（Motifs，全站共用）

1. **全頁洋流 Canvas**（`GlobalCurrent`）：固定背景，金+綠粒子沿向量場流動。手機降載（dpr≤1.4、粒子≤90、隱藏時暫停）。
2. **生物螢光浮游點**（`Plankton`）：固定背景漂浮光點。
3. **燈塔**（`Lighthouse`）：站在海浪線上、塔基沒入浪中、柔和球狀燈光、光束掃動。僅首頁 Hero 使用，其他頁可選用較小版本或省略。
4. **海浪**（`HeroWaves`）：頁面/區塊底部多層流動浪，金色浪頂高光。
5. **聲納漣漪 / ping**：圓形擴散，金綠交替。用於分析、五維、強調區。
6. **HUD 邊角框**（`Corner`）：卡片四角的金色直角括號。
7. **掃描光條**（`scanline`）：資料卡上下掃動，像在讀取。
8. **毛玻璃卡**：rgba 深色底 + backdrop-blur + 金色細框 + 四角 HUD。
9. **滾動進度條**（`ScrollBar`）：頁頂金綠漸層細條。
10. **區塊半透明遮罩**（`veil`，0.4–0.9）：讓固定洋流透出，達成上下一體感。下方區塊用較低值（0.4–0.55）+ `SoftRays` 飄光，避免單調。

---

## 5. 元件規範

### 導覽列 Nav
- sticky top，滾動時：背景變深+毛玻璃、padding 縮小、logo 縮小、底部浮現流動金綠光線。
- 左：選單按鈕（☰，開左側抽屜）+ logo + 品牌名。
- 右：免費註冊按鈕（CSS `@media(max-width:380px)` 隱藏，**不要用 JS 判斷寬度**）+ 個人資料頭像按鈕。
- 已登入時：頭像按鈕進個人資料；未登入進登入/註冊。

### 側邊抽屜 Drawer（全站共用導覽）
- 從左滑出、背景模糊遮罩、ESC/點外關閉。
- 選單項：市場總覽 / 黑潮船長 PRO / AI 分析 PLUS / 新聞中心 PLUS / 事件行事曆 / 美股分析 / 異常監控 PLUS / 策略回測 PRO；其他：會員中心 / 福利中心 / 使用教學 / 常見問題。
- 徽章：PLUS=金色描邊膠囊，PRO=金色實心膠囊。
- 底部：Telegram 社群頻道按鈕 + ● 行情：Bybit 即時 + © 2026。
- active 項：金色漸層底 + 左側金條 + 右側箭頭。
- 每項連到真實路由。

### 按鈕
- 主 CTA：金漸層底、深色字、掃光、呼吸脈衝（`ctaPulse`）、hover 放大。
- 震撼 CTA（轉換頁/結尾）：更強脈衝（`ctaBigPulse`）+ 背後爆發光圈。
- 次要按鈕：透明底 + 金/綠細框，hover 變色上移。

### 卡片
- 毛玻璃底 + 金色細框 + 四角 HUD（`Corner`）。
- hover：上浮 + 邊框轉金 + 陰影/光暈。
- 頂部常加一道 `linear-gradient(90deg,transparent,gold/teal,transparent)` 細光條。

### 資料列表（信號、行情等）
- 左側彩色強調條（做多綠/做空紅，發光）。
- hover：背景微亮 + 右移。
- 行掃光（`row-sweep`）。
- 數字 MONO。
- 鎖定內容：模糊閃爍的 `$●●●` + 🔒；已公開內容顯示真實值。

### 標籤 / Badge
- 品質：高品質=金、一般=灰。
- 方向：做多=green 底、做空=rose 底。
- 會員：PLUS/PRO 如上。

---

## 6. 動態與效能規範

- 所有 transform 動畫元件加 `will-change:transform`（海浪、漣漪、掃光、logo 旋轉）。
- Canvas：手機 dpr≤1.4、粒子減半、`visibilitychange` 隱藏時暫停 rAF、dt 上限防卡頓爆衝、`will-change:transform`。
- 一律支援 `@media(prefers-reduced-motion:reduce)`：關閉所有動畫。
- 響應式顯示/隱藏一律用 CSS `@media`，**禁止用 `window.innerWidth` 在 render 時判斷**（內建瀏覽器會破圖閃爍）。
- 手機優先：所有頁面在 375–414px 寬正常、文字不被切（標題行高≥1.15）、不破版。

---

## 7. 內容與合規原則（全站適用）

- **不捏造、不美化績效。** 任何戰績、勝率、損益數字必須來自真實資料，有賺有賠照實呈現，不挑漂亮的。真實樣本不足時，改為呈現「方向、結果、品質、監測廣度」等過程資訊，不強調損益數字。
- 行情/信號的「即時跳動」若非真實資料更新，不可用假隨機跳動冒充（價格會誤導）。改為真實值 + 定期刷新。
- 信號付費牆：只有「已結算」信號可公開價位（已結束、非可操作）；「進行中」信號價位依現有 tier 邏輯對未付費者隱藏。
- 每頁底部保留法律資訊：服務條款 / 免責聲明 / 隱私權政策 / 風險揭露聲明（點擊開彈窗）+ 免責聲明文字。
- 風險與免責用語保留，加密貨幣高風險、不構成投資建議。
```
