import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="免責聲明" updated="2026-06">
      <Clause title="一、僅供參考"><p>本服務所有行情、指標、評分、訊號、回測與分析內容，均屬資訊與教育用途，不構成投資建議、招攬或要約。</p></Clause>
      <Clause title="二、不保證準確"><p>資料多來自第三方並經程式運算，可能因延遲、來源錯誤、運算假設或系統問題而與實際不符。</p></Clause>
      <Clause title="三、不保證獲利"><p>過往表現（含回測與歷史訊號）不代表未來結果。任何「勝率」「期望值」等數據僅為統計估算。</p></Clause>
      <Clause title="四、回測為模擬"><p>回測頁所呈現者為模擬結果，僅供示範資料流與指標計算，並非真實交易績效。</p></Clause>
      <Clause title="五、自行決策"><p>是否進場、加碼、減碼、停損或停利，均由會員自行判斷，並承擔全部風險與後果。</p></Clause>
      <Clause title="六、無代操關係"><p>本服務不接受委託代為操作任何帳戶或資金，亦不經手會員於交易所之資金。</p></Clause>
      <Clause title="七、第三方連結"><p>站內可能連結至第三方網站或工具，其內容與政策與本服務無涉，請自行評估。</p></Clause>
      <Clause title="八、損失免責"><p>在法律允許之範圍內，對於因信賴或使用本服務內容所生之任何損失，本服務及其團隊不負賠償責任。</p></Clause>
    </LegalLayout>
  );
}
