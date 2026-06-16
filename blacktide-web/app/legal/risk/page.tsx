import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="風險揭露聲明" updated="2026-06">
      <Clause title="一、總則"><p>加密貨幣與其衍生性商品之交易具高度風險，未必適合所有人。於使用本服務或進行任何交易前，請確認您已充分理解相關風險。</p></Clause>
      <Clause title="二、可能損失全部本金"><p>市場價格可能於短時間內劇烈且不可預測地變動，您可能損失部分或全部本金。</p></Clause>
      <Clause title="三、槓桿與強制平倉"><p>合約與槓桿交易會同時放大獲利與虧損，並可能因價格不利變動而遭強制平倉（爆倉），損失可能超出原始投入。</p></Clause>
      <Clause title="四、流動性與滑價"><p>於特定時段或劇烈行情時，市場可能出現流動性不足、跳空或滑價，導致成交價與預期不符。</p></Clause>
      <Clause title="五、技術與平台風險"><p>交易所或第三方系統可能發生延遲、當機、API 變更、資料錯誤、網路中斷或遭受攻擊，影響資料、報價與下單。</p></Clause>
      <Clause title="六、訊號與分析之侷限"><p>任何技術指標、評分與訊號皆基於歷史資料與既定假設，無法預測未來。連續虧損為任何策略的必然可能。</p></Clause>
      <Clause title="七、過往表現與不保證"><p>過往表現（含回測與歷史訊號）不代表未來結果。本服務不對任何標的或訊號之成敗作任何保證。</p></Clause>
      <Clause title="八、無代操關係"><p>本服務僅提供資訊工具，不代您操作帳戶、不保管資金。所有交易決策與執行均由您自行為之。</p></Clause>
      <Clause title="九、法規與稅務"><p>不同地區對加密貨幣與金融商品之法規與稅務規定不同且可能變動，您應自行了解並遵循當地規範。</p></Clause>
      <Clause title="十、風險管理"><p>請務必做好部位控制與資金管理，設定合理之停損與風險上限，切勿投入無法承受損失之資金。</p></Clause>
      <Clause title="十一、確認與同意"><p>使用本服務即表示您已閱讀並充分理解上述風險，並同意自行承擔一切交易結果。</p></Clause>
    </LegalLayout>
  );
}
