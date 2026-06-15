import LegalLayout, { Clause } from "@/components/LegalLayout";
export default function Page() {
  return (
    <LegalLayout title="風險揭露聲明" updated="2026-06">
      <Clause title="一、高風險商品"><p>加密貨幣與衍生性（合約、槓桿）商品價格波動劇烈，可能於短時間內大幅漲跌，您可能損失全部本金。</p></Clause>
      <Clause title="二、槓桿風險"><p>使用槓桿會同時放大獲利與虧損，並可能因價格不利變動而遭強制平倉（爆倉），損失超出預期。</p></Clause>
      <Clause title="三、流動性與滑價"><p>於特定時段或劇烈行情時，市場可能出現流動性不足、跳空或滑價，導致成交價與預期不符。</p></Clause>
      <Clause title="四、技術與平台風險"><p>交易所或第三方系統可能發生延遲、當機、API 變更、資料錯誤或遭受攻擊，影響資料與下單。</p></Clause>
      <Clause title="五、訊號與分析之侷限"><p>任何技術指標、評分與訊號皆基於歷史資料與假設，無法預測未來。連續虧損為任何策略的必然可能。</p></Clause>
      <Clause title="六、非保證獲利"><p>本服務不對任何標的之漲跌、訊號之成敗或整體績效作出任何保證或承諾。</p></Clause>
      <Clause title="七、法規與稅務"><p>不同地區對加密貨幣與金融商品之法規與稅務規定不同，請自行了解並遵循當地規範。</p></Clause>
      <Clause title="八、量力而為"><p>請僅以您可承受全部損失之閒置資金參與，並做好風險與資金管理；必要時請諮詢專業人士。</p></Clause>
      <Clause title="九、確認與同意"><p>使用本服務即表示您已充分理解上述風險，並願自行承擔一切交易結果。</p></Clause>
    </LegalLayout>
  );
}
