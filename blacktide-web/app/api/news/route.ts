import { NEWS as MOCK } from "@/lib/mock";
import { redisGet } from "@/lib/redis";
export const dynamic = "force-dynamic";
const FEEDS: { url: string; source: string }[] = [
  { url: "https://cointelegraph.com/rss", source: "Cointelegraph" },
  { url: "https://decrypt.co/feed", source: "Decrypt" },
  { url: "https://www.coindesk.com/arc/outboundfeeds/rss/", source: "CoinDesk" },
  { url: "https://cryptoslate.com/feed/", source: "CryptoSlate" },
  { url: "https://bitcoinmagazine.com/feed", source: "Bitcoin Magazine" },
];
const TICKERS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "SUI", "TON", "TRX", "DOT", "NEAR", "PEPE", "SHIB", "LTC", "BCH", "ARB", "OP", "APT", "SEI"];
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
  if (/(surge|soar|rally|jump|gain|high|bullish|approve|adopt|inflow|breakout|record)/.test(s)) return "bull";
  if (/(crash|plunge|drop|fall|hack|exploit|bearish|lawsuit|ban|liquidat|outflow|dump|sell-?off)/.test(s)) return "bear";
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
interface Item { id: string; title: string; source: string; time: string; sentiment: "bull" | "bear" | "neutral"; impact: 1 | 2 | 3 | 4 | 5; summary: string; tags: string[]; url: string; ts: number; }
function parseFeed(xml: string, source: string): Item[] {
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
    const tags = TICKERS.filter((t) => new RegExp("\\b" + t + "\\b").test(title.toUpperCase())).slice(0, 4);
    out.push({
      id: source + "-" + i + "-" + (ts || 0), title, source, time: rel(ts),
      sentiment: sentimentOf(title + " " + desc),
      impact: (/(hack|exploit|sec|etf|fed|approve|ban|lawsuit|halving|liquidat)/i.test(title) ? 4 : 2) as 1 | 2 | 3 | 4 | 5,
      summary: desc || "（點擊閱讀原文）", tags, url: link, ts: ts || 0,
    });
  }
  return out;
}
async function fetchFeed(f: { url: string; source: string }): Promise<Item[]> {
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 6000);
    const r = await fetch(f.url, { cache: "no-store", signal: ctrl.signal, headers: { "User-Agent": "Mozilla/5.0 (compatible; BlackTideBot/1.0)" } });
    clearTimeout(to);
    if (!r.ok) return [];
    return parseFeed(await r.text(), f.source);
  } catch { return []; }
}
let cache: { ts: number; body: unknown } | null = null;
export async function GET() {
  if (cache && Date.now() - cache.ts < 120000) return Response.json(cache.body);
  // 1) RSS 即時（主來源）
  const settled = await Promise.allSettled(FEEDS.map(fetchFeed));
  let all: Item[] = [];
  for (const s of settled) if (s.status === "fulfilled") all = all.concat(s.value);
  all = all.filter((x) => x.ts > 0).sort((a, b) => b.ts - a.ts);
  // 去重（標題）
  const seen = new Set<string>();
  all = all.filter((x) => { const k = x.title.toLowerCase().slice(0, 60); if (seen.has(k)) return false; seen.add(k); return true; });
  if (all.length >= 5) {
    /* eslint-disable @typescript-eslint/no-unused-vars */
    const news = all.slice(0, 30).map(({ ts, ...n }) => n);
    const body = { news, source: "rss" };
    cache = { ts: Date.now(), body };
    return Response.json(body);
  }
  // 2) bot 分析新聞（僅當存在）
  try {
    const raw = await redisGet("web:news:analyzed");
    if (raw) { const arr = JSON.parse(raw); if (Array.isArray(arr) && arr.length) return Response.json({ news: arr.slice(0, 30), source: "bot" }); }
  } catch {}
  // 3) 假資料（最後手段）
  return Response.json({ news: MOCK, source: "mock" });
}
