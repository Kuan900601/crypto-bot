import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="隱私權政策" updated="2026-06">
      <Clause title="一、適用範圍"><p>本政策說明黑潮 BLACKTIDE（以下稱「本服務」）如何蒐集、處理、利用及保護您的個人資料，適用於您使用本服務之各項功能。</p></Clause>
      <Clause title="二、蒐集之資料"><p>(1) 您主動提供：姓名、電話、電子郵件、頭像、密碼（以雜湊保存）、意見反饋內容；(2) 系統自動產生：使用者識別碼、登入與操作紀錄、必要之技術資訊。</p></Clause>
      <Clause title="三、蒐集目的與法律依據"><p>用於：帳號註冊與識別、提供與維護服務、會員權限與訂閱管理、客戶服務與意見處理，以及必要之安全與營運分析。</p></Clause>
      <Clause title="四、付款資料"><p>線上付款由第三方金流服務商（NOWPayments）處理。我們不會蒐集或儲存您完整之付款工具資訊，僅保留訂單與付款狀態以開通服務。</p></Clause>
      <Clause title="五、資料儲存與保護"><p>會員資料儲存於雲端資料庫服務（Upstash Redis）。密碼以單向雜湊保存，我們不以明文儲存。我們採取合理之技術與管理措施保護您的資料。</p></Clause>
      <Clause title="六、第三方處理者"><p>為提供服務，部分功能由第三方協助處理（例如 NextAuth／Google 之登入、Bybit／TradingView／CryptoPanic 之行情與新聞、NOWPayments 之金流），其處理依其各自之政策。</p></Clause>
      <Clause title="七、資料分享與揭露"><p>除為提供服務所必須、經您同意、或依法令或主管機關／司法機關之要求外，我們不對外販售或任意揭露您的個人資料。</p></Clause>
      <Clause title="八、Cookie 與工作階段"><p>為維持您的登入狀態與服務正常運作，本服務使用必要之工作階段（session）與 Cookie。</p></Clause>
      <Clause title="九、保存期間與刪除"><p>我們於提供服務及法令要求之必要期間內保存您的資料。您可於會員中心更新資料，或透過意見反饋請求刪除帳號及相關資料。</p></Clause>
      <Clause title="十、跨境傳輸"><p>因本服務使用之雲端與第三方服務可能位於境外，您的資料可能被傳輸並儲存於您所在地以外之地區。</p></Clause>
      <Clause title="十一、您的權利"><p>就您的個人資料，您得依適用之個人資料保護法令，行使查詢、閱覽、製給複製本、補充或更正、停止處理或刪除等權利。</p></Clause>
      <Clause title="十二、未成年人"><p>本服務不以未滿 18 歲者為對象。若您未達所在地法律之完全行為能力年齡，請於法定代理人同意下使用。</p></Clause>
      <Clause title="十三、政策修改與聯絡"><p>本政策修訂後於本頁公告即生效。如有任何隱私相關問題或欲行使權利，請透過會員中心之意見反饋與我們聯繫。</p></Clause>
    </LegalLayout>
  );
}
