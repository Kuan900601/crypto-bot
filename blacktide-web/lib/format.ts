export function fmtPrice(p: number): string {
  if (!isFinite(p)) return "-";
  if (p >= 1000) return p.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (p >= 1) return p.toFixed(2);
  if (p >= 0.01) return p.toFixed(4);
  return p.toPrecision(3);
}

export function fmtPct(x: number): string {
  return `${x >= 0 ? "+" : ""}${x.toFixed(2)}%`;
}

export function compactZh(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + "億";
  if (abs >= 1e4) return (n / 1e4).toFixed(0) + "萬";
  return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

// 進場品質：只在顯示層翻譯，內部值（S/A/B/C/D）絕不變動 —— 與 bot 同規則
export function entryGradeDisplay(g: string): string {
  if (g === "S" || g === "A") return "高品質";
  if (g === "B" || g === "C") return "一般品質";
  return "低品質";
}

// 確定性偽隨機（mulberry32）：mock 資料用，避免 SSR/CSR 不一致
export function makeRng(seed: number) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function timeAgoZh(iso: string): string {
  if (!iso) return "-";
  const t = Date.parse(iso);
  if (isNaN(t)) return "-";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return Math.floor(s) + " 秒前";
  if (s < 3600) return Math.floor(s / 60) + " 分前";
  if (s < 86400) return Math.floor(s / 3600) + " 小時前";
  return Math.floor(s / 86400) + " 天前";
}
