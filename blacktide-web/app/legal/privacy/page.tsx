import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="隱私權政策" updated="2026-06">
      <Clause title="一、蒐集之資料"><p>於註冊與使用本服務時，我們可能蒐集您的姓名、電話、電子郵件、頭像、系統自動產生之識別碼與使用紀錄。</p></Clause>
      <Clause title="二、蒐集目的"><p>用於帳號識別、提供與維護服務、會員權限管理、客戶服務與意見處理，以及必要之安全與營運分析。</p></Clause>
      <Clause title="三、資料儲存與保護"><p>會員資料儲存於雲端資料庫服務（Upstash Redis）。密碼以雜湊方式保存，我們不以明文儲存您的密碼。</p></Clause>
      <Clause title="四、第三方服務"><p>登入、行情、新聞與圖表等功能可能由第三方提供（例如 NextAuth／Google、Bybit、TradingView、CryptoPanic），其處理依其各自之政策。</p></Clause>
      <Clause title="五、Cookie 與工作階段"><p>為維持您的登入狀態，本服務使用必要之工作階段（session）與 Cookie。</p></Clause>
      <Clause title="六、資料分享"><p>除為提供服務所必須、經您同意或法令要求外，我們不對外販售或任意揭露您的個人資料。</p></Clause>
      <Clause title="七、資料保存與刪除"><p>您可於會員中心更新個人資料。如需刪除帳號及相關資料，請透過意見反饋與我們聯繫。</p></Clause>
      <Clause title="八、您的權利"><p>您得查詢、閱覽、更正或請求刪除您的個人資料。</p></Clause>
      <Clause title="九、未成年人"><p>若您未達所在地法律之完全行為能力年齡，請於法定代理人同意下使用本服務。</p></Clause>
      <Clause title="十、政策修改"><p>本政策修訂後於本頁公告即生效。</p></Clause>
      <Clause title="十一、聯絡方式"><p>如有隱私相關問題，請透過會員中心之意見反饋與我們聯繫。</p></Clause>
    </LegalLayout>
  );
}
