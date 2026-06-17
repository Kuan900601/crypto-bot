# docs/web.md

# BlackTide Web / SaaS 文件

描述 `blacktide-web`（Next.js）、會員系統與 NOWPayments 規則。Web 是介面層，不是策略核心。

---

## 1. Web 定位

blacktide-web 是 BlackTide 的 SaaS 商業化入口。功能：首頁、登入、註冊、會員中心、付費方案、分析頁、回測頁、付款、Webhook、Dashboard。

---

## 2. 技術棧

已知：Next.js、TypeScript、NextAuth、NOWPayments、Redis、Vercel。
可能包含：Resend、API routes、Server actions、Protected pages。

---

## 3. 權限原則

- 未登入：可看首頁/登入/註冊/定價/法律文件；不可看付費分析內容、不可看會員 Dashboard。
- 已登入未付費：可看會員中心/付款頁/有限試用內容；不可看完整分析/回測/信號。
- 已付費：可看對應方案內容；權限由 membership 決定。

---

## 4. 重要安全原則

前端隱藏不是安全。會員權限必須在 `API route / server component / server action / middleware` 等 server 端檢查。

禁止：只用 CSS hidden 保護付費內容、只用 client state 判定會員、把付費資料一次性傳給前端再隱藏、把 secret 放 `NEXT_PUBLIC`、在 client component 呼叫敏感 secret API。

---

## 5. NextAuth 規則

需要：`NEXTAUTH_URL`、`NEXTAUTH_SECRET`。
規則：production `NEXTAUTH_URL` 必須是正式網域；不得在程式碼寫死 secret；session 檢查必在 server/API 層；權限資料避免只信任 client 傳入值。

---

## 6. NOWPayments 規則

必要：`NOWPAYMENTS_API_KEY`、`NOWPAYMENTS_IPN_SECRET`。IPN callback：`/api/webhooks/nowpayments`。
規則：webhook 必驗 IPN Secret；未驗證不得開通服務；payment pending 不等於 paid；failed/expired 不得開通；重複 webhook 必須 idempotent；金流錯誤要記清楚 log，不要吞掉。

---

## 7. Redis 使用者資料規則

可能欄位：`user email`、`subscription status`、`plan`、`expires_at`、`payment_id`、`invoice_id`、`created_at`、`updated_at`。
規則：schema 不得隨意改；改 schema 要寫 migration 或相容處理；會員態不能只存在前端；對應期間用一致格式；payment id 要可追蹤。

---

## 8. Web 與 Analyzer 的關係

```text
Web API → server-side auth check → analyzer / bot data / Redis → response
```
禁止：`Client → 直接重寫策略`。原因：策略分裂、結果不一致、付費內容不可控、維護成本翻倍。

---

## 9. Web 與 Auto Trader 的關係

預設：Web 不直接執行真實交易。若未來要加入「使用者觸發真實交易」，必須另行設計：二次確認、風險揭露、使用者權限、API 簽章、下單額度、audit log、錯誤處理、法律風險。未經作者明確要求，不得新增 Web 直接下單功能。

---

## 10. Web 修改後驗證

```bash
npm run lint && npm run build      # 或 pnpm lint / pnpm build
```
改 API 要檢查：未登入 response、未付費 response、已付費 response、錯誤訊息、secret 沒進前端 bundle。

---

## 11. 法律與風險頁

SaaS 平台應保有：Terms of Service、Disclaimer、Privacy Policy、Risk Disclosure。
規則：不得承諾獲利、不得宣稱保證準確、不得暗示無風險、回測數據明確標示僅供參考、真實交易風險須清楚揭露。
