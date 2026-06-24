export type Tier = "free" | "air" | "pro";
export const RANK: Record<Tier, number> = { free: 0, air: 1, pro: 2 };
export const TIER_LABEL: Record<Tier, string> = { free: "免費會員", air: "Plus 會員", pro: "Pro 會員" };
export const TIER_SHORT: Record<Tier, string> = { free: "FREE", air: "PLUS", pro: "PRO" };
// 路由所需的最低方案（未列出者為公開）
const ROUTE_TIER: { prefix: string; tier: Tier }[] = [
  { prefix: "/signals", tier: "pro" },
  { prefix: "/backtest", tier: "pro" },
  { prefix: "/analysis", tier: "air" },
  { prefix: "/news", tier: "air" },
  { prefix: "/monitor", tier: "air" },
];
export function requiredTier(path: string): Tier | null {
  const hit = ROUTE_TIER.find((r) => path === r.prefix || path.startsWith(r.prefix + "/"));
  return hit ? hit.tier : null;
}
export function canAccess(path: string, tier: Tier): boolean {
  const req = requiredTier(path);
  if (!req) return true;
  return RANK[tier] >= RANK[req];
}
export const PRICING = {
  air: { monthly: 9.99, yearly: 99.99, off: 17 },
  pro: { monthly: 29.99, yearly: 299.99, off: 17 },
} as const;
export const FOUNDER = {
  price: 199.99,
  slots: 100,
  originalPrice: 359.88,   // pro monthly × 12
  save: 159.89,
  offPct: 44,
  monthlyEq: 16.67,
} as const;
export function priceOf(tier: "air" | "pro", cycle: "monthly" | "yearly"): number {
  return cycle === "yearly" ? PRICING[tier].yearly : PRICING[tier].monthly;
}
export function monthlyEquivalent(tier: "air" | "pro", cycle: "monthly" | "yearly"): number {
  return cycle === "yearly" ? Math.round(PRICING[tier].yearly / 12) : PRICING[tier].monthly;
}
export interface FeatureRow { name: string; air: boolean; pro: boolean; }
export const FEATURES: FeatureRow[] = [
  { name: "市場總覽（Bybit 即時行情）", air: true, pro: true },
  { name: "全幣種 / 美股搜尋與圖表", air: true, pro: true },
  { name: "AI 智能分析（即時技術指標）", air: true, pro: true },
  { name: "即時新聞 + 情緒分析", air: true, pro: true },
  { name: "異常監控 / 巨鯨警報", air: true, pro: true },
  { name: "黑潮船長即時訊號", air: false, pro: true },
  { name: "策略回測", air: false, pro: true },
  { name: "Telegram 即時推播", air: false, pro: true },
  { name: "黑潮 VIP 私密群（Pro 專屬）", air: false, pro: true },
];
