import { NEWS as MOCK } from "@/lib/mock";
import { redisGet } from "@/lib/redis";
export const dynamic = "force-dynamic";

// Chinese-first feeds; English as fallback
const FEEDS: { url: string; source: string; lang: "zh" | "en" }[] = [
  { url: "https://www.8btc.com/feed", source: "巴比特", lang: "zh" },
  { url: "https://jinse.cn/rss.xml", source: "金色財經", lang: "zh" },
  { url: "https://www.odaily.news/rss", source: "Odaily 星球日報", lang: "zh" },
  { url: "https://www.theblockbeats.info/rss", source: "律動 BlockBeats", lang: "zh" },
  { url: "https://panewslab.com/zh/rss/index.xml", source: "PANews", lang: "zh" },
  { url: "https://cointelegraph.com/rss", source: "Cointelegraph", lang: "en" },
  { url: "https://www.coindesk.com/arc/outboundfeeds/rss/", source: "CoinDesk", lang: "en" },
];

const TICKERS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "SUI", "TON", "TRX", "PEPE", "SHIB", "ARB", "OP", "比特幣", "以太", "以太坊", "索拉納"];

function decode(s: string) {
  return s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&apos;/g, "'").replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/\s+/g, " ").trim();
}
function tag(block: string, name: string) {
  const m = block.match(new RegExp("<" + name + "[^>]*>([\\s\\S]*?)</" + name + ">", "i"));
  return m ? m[1] : "";
}
function sentimentOf(t: string): "bull" | "bear" | "neutral" {
  const s = t.toLowerCase();
  // English
  if (/(surge|soar|rally|jump|gain|high|bullish|approve|adopt|inflow|breakout|record|pump|ath)/.test(s)) return "bull";
  if (/(crash|plunge|drop|fall|hack|exploit|bearish|lawsuit|ban|liquidat|outflow|dump|sell-?off|warning|risk)/.test(s)) return "bear";
  // Chinese
  if (/(上漲|漲|突破|新高|增長|回升|看漲|做多|暴漲|拉升|利好|反彈|創新|ETF通過|機構買入)/.test(t)) return "bull";
  if (/(下跌|跌|暴跌|崩盤|閃崩|做空|拋售|危機|清算|爆倉|被盜|監管|禁止|限制|警告|風險)/.test(t)) return "bear";
  return "neutral";
}
function rel(ts: number) {
  if (!ts) return "";
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return "剛剛";
  if (m < 60) return m + " 分鐘前";
  const h = Math.floor(m / 60);
  if (h < 24) return h + " 小時前";
  const d = Math.floor(h / 24);
  return d + " 天前";
}
interface Item { id: string; title: string; source: string; time: string; sentiment: "bull" | "bear" | "neutral"; impact: 1 | 2 | 3 | 4 | 5; summary: string; tags: string[]; url: string; ts: number; lang?: string; }

function parseFeed(xml: string, source: string, lang: "zh" | "en"): Item[] {
  const out: Item[] = [];
  const blocks = xml.split(/<item[\s>]/i).slice(1);
  const items = blocks.length ? blocks : xml.split(/<entry[\s>]/i).slice(1);
  for (let i = 0; i < items.length; i++) {
    const b = items[i];
    const title = decode(tag(b, "title"));
    if (!title) continue;
    let link = decode(tag(b, "link"));
    if (!link) { const m = b.match(/<link[^>]*href="([^"]+)"/i); if (m) link = m[1]; }
    const pub = decode(tag(b, "pubDate") || tag(b, "published") || tag(b, "updated") || tag(b, "dc:date"));
    const ts = pub ? Date.parse(pub) : 0;
    const desc = decode(tag(b, "description") || tag(b, "summary") || tag(b, "content:encoded"));
    const tags = TICKERS.filter((t) => {
      const pat = t.length <= 3 ? new RegExp("\\b" + t + "\\b") : new RegExp(t);
      return pat.test(title.toUpperCase()) || pat.test(title);
    }).slice(0, 4);
    out.push({
      id: source + "-" + i + "-" + (ts || 0), title, source, time: rel(ts),
      sentiment: sentimentOf(title + " " + desc),
      impact: (/(hack|exploit|sec|etf|fed|approve|ban|lawsuit|halving|liquidat|清算|監管|ETF|美聯儲|暴跌|暴漲)/i.test(title) ? 4 : 2) as 1 | 2 | 3 | 4 | 5,
      summary: desc || "（點擊閱讀原文）", tags, url: link, ts: ts || 0, lang,
    });
  }
  return out;
}
async function fetchFeed(f: { url: string; source: string; lang: "zh" | "en" }): Promise<Item[]> {
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 7000);
    const r = await fetch(f.url, { cache: "no-store", signal: ctrl.signal, headers: { "User-Agent": "Mozilla/5.0 (compatible; BlackTideBot/v13)" } });
    clearTimeout(to);
    if (!r.ok) return [];
    return parseFeed(await r.text(), f.source, f.lang);
  } catch { return []; }
}
let cache: { ts: number; body: unknown } | null = null;
export async function GET() {
  if (cache && Date.now() - cache.ts < 30000) return Response.json(cache.body);
  // 1) RSS 即時（中文優先）
  const settled = await Promise.allSettled(FEEDS.map(fetchFeed));
  let zhItems: Item[] = [];
  let enItems: Item[] = [];
  for (const s of settled) {
    if (s.status !== "fulfilled") continue;
    for (const item of s.value) {
      if (item.lang === "zh") zhItems.push(item);
      else enItems.push(item);
    }
  }
  // Sort each by timestamp
  zhItems = zhItems.filter((x) => x.ts > 0).sort((a, b) => b.ts - a.ts);
  enItems = enItems.filter((x) => x.ts > 0).sort((a, b) => b.ts - a.ts);
  // Deduplicate
  const seen = new Set<string>();
  const dedup = (arr: Item[]) => arr.filter((x) => {
    const k = x.title.toLowerCase().slice(0, 60);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  zhItems = dedup(zhItems);
  enItems = dedup(enItems);
  // Merge: 70% Chinese, 30% English (take up to 21 zh + 9 en = 30 total)
  const all = [...zhItems.slice(0, 21), ...enItems.slice(0, 9)];
  if (all.length >= 3) {
    const news = all.slice(0, 30).map(({ ts, lang, ...n }) => ({ ...n, isZh: lang === "zh" }));
    const body = { news, source: "rss", zhCount: zhItems.slice(0, 21).length };
    cache = { ts: Date.now(), body };
    return Response.json(body);
  }
  // 2) bot 分析新聞（備援）
  try {
    const raw = await redisGet("web:news:analyzed");
    if (raw) { const arr = JSON.parse(raw); if (Array.isArray(arr) && arr.length) return Response.json({ news: arr.slice(0, 30), source: "bot" }); }
  } catch {}
  // 3) 假資料（最後手段）
  return Response.json({ news: MOCK, source: "mock" });
}
