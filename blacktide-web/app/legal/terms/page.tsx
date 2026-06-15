import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="服務條款" updated="2026-06">
      <Clause title="一、服務內容"><p>黑潮 BLACKTIDE（以下稱「本服務」）提供加密貨幣與美股之即時行情、技術分析、訊號彙整、回測示範與新聞資訊等功能，屬資訊與教育性質之工具平台。</p></Clause>
      <Clause title="二、非投資建議"><p>本服務不提供個別化投資建議，不代客操作、不保證任何獲利。任何交易決策與後果均由會員自行承擔。</p></Clause>
      <Clause title="三、帳號與資格"><p>會員須提供正確之註冊資料並妥善保管帳號密碼，不得共享、轉售或冒用他人身分。</p></Clause>
      <Clause title="四、訂閱與付費"><p>本服務提供 Air、Pro 兩種方案，依所選計費週期收費。線上金流接通後將於結帳頁顯示金額與週期。</p></Clause>
      <Clause title="五、方案權限"><p>各方案可使用之功能，以訂閱頁面之功能對照表為準。本服務得視營運需要新增、調整功能與權限。</p></Clause>
      <Clause title="六、使用限制"><p>會員不得對本服務進行逆向工程、自動化大量擷取、干擾或破壞系統、散布惡意程式或從事違法行為。</p></Clause>
      <Clause title="七、智慧財產權"><p>本服務之介面、程式、文字及彙整成果之權利，屬本服務或其授權人所有；行情與第三方資料之權利歸原權利人。</p></Clause>
      <Clause title="八、第三方資料"><p>本服務之行情、新聞與圖表來自第三方（例如 Bybit、TradingView、CryptoPanic 等），其正確性與可用性由來源方負責。</p></Clause>
      <Clause title="九、服務變更與中斷"><p>本服務得隨時新增、修改或暫停部分或全部功能，並就維護、故障、網路或不可抗力所致之中斷不負保證之責。</p></Clause>
      <Clause title="十、責任限制"><p>在法律允許之最大範圍內，對於使用或無法使用本服務所致之任何直接或間接損失，本服務不負賠償責任。</p></Clause>
      <Clause title="十一、條款修改"><p>本服務得不時修訂本條款，修訂內容於本頁公告後生效；會員繼續使用視為同意。</p></Clause>
      <Clause title="十二、準據法"><p>本條款之解釋與適用以中華民國法律為準據法。</p></Clause>
    </LegalLayout>
  );
}
