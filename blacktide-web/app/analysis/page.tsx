"use client";
import { useEffect, useState } from "react";
import { ANALYSES } from "@/lib/mock";
import { fmtPrice } from "@/lib/format";
import { C, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import { Skeleton } from "@/components/ui";
import { X } from "lucide-react";
interface RA {
  symbol: string; price: number; change24h: number; rsi: number; ma20: number; ma50: number;
  atrPct: number; momentum: number; fundingPct: number; trend: string; bias: string;
  confidence: number; risk: number; sentiment: number; support: number[]; resistance: number[];
  basis: string[]; action: string;
}
const biasLabel = (b: string) => (b === "long" ? "看多" : b === "short" ? "看空" : "中性");
const biasColor = (b: string) => (b === "long" ? C.green : b === "short" ? C.rose : C.mut);
const trendZh = (t: string) => (t === "up" ? "多頭排列" : t === "down" ? "空頭排列" : "均線糾纏");
// 把展示資料(ANALYSES)補成完整 RA，讓詳情彈窗在 fallback 也能用
function toRA(a: (typeof ANALYSES)[number]): RA {
  const mid = a.support?.length && a.resistance?.length ? (a.support[0] + a.resistance[0]) / 2 : 0;
  const trend = a.bias === "long" ? "up" : a.bias === "short" ? "down" : "flat";
  const rsi = a.bias === "long" ? 62 : a.bias === "short" ? 38 : 50;
  const mom = a.bias === "long" ? 1.8 : a.bias === "short" ? -1.8 : 0.2;
  return {
    symbol: a.symbol, price: mid, change24h: mom, rsi, ma20: mid, ma50: mid,
    atrPct: 2.0, momentum: mom, fundingPct: 0.01, trend, bias: a.bias,
    confidence: a.confidence, risk: a.risk, sentiment: a.sentiment,
    support: a.support, resistance: a.resistance, basis: a.basis, action: a.action,
  };
}

function EnergyBar({ value, tone = C.gold }: { value: number; tone?: string }) {
  return (
    <div style={{ height: 6, width: "100%", borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
      <div style={{ height: "100%", width: Math.min(100, Math.max(0, value)) + "%", borderRadius: 99, background: `linear-gradient(90deg, ${tone}88, ${tone})`, boxShadow: `0 0 8px ${tone}66`, transition: "width .5s" }} />
    </div>
  );
}

function DetailModal({ a, demo, onClose }: { a: RA; demo: boolean; onClose: () => void }) {
  const cell = (label: string, value: string, color?: string) => (
    <div className="rounded-lg p-2.5 text-center" style={{ background: "rgba(255,255,255,0.03)" }}>
      <div style={{ fontSize: 10, color: C.dim }}>{label}</div>
      <div style={{ marginTop: 2, fontFamily: MONO, fontSize: 13, color: color || C.ink }}>{value}</div>
    </div>
  );
  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-4" style={{ background: "rgba(2,4,9,0.7)", backdropFilter: "blur(5px)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="pop-in relative max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-2xl p-5 sm:rounded-2xl" style={{
        background: "linear-gradient(180deg, rgba(10,20,34,0.98), rgba(4,9,16,0.98))", border: `1px solid ${C.lineGold}`,
      }}>
        <Corner pos="tl" /><Corner pos="tr" /><Corner pos="bl" /><Corner pos="br" />
        <div className="flex items-center gap-2">
          <span style={{ fontFamily: MONO, fontSize: 17, fontWeight: 800, color: C.ink }}>{a.symbol}</span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 9px", borderRadius: 99, color: biasColor(a.bias), background: biasColor(a.bias) + "1A" }}>{biasLabel(a.bias)}</span>
          {!demo && <span style={{ fontFamily: MONO, fontSize: 13, color: C.mut }}>${fmtPrice(a.price)}</span>}
          {!demo && <span style={{ fontFamily: MONO, fontSize: 11.5, color: a.change24h >= 0 ? C.green : C.rose }}>{a.change24h >= 0 ? "+" : ""}{a.change24h}%</span>}
          <button onClick={onClose} className="ham ml-auto rounded-lg p-1.5" style={{ color: C.mut }}><X size={18} /></button>
        </div>
        {!demo && (
          <div className="mt-4 grid grid-cols-3 gap-2">
            {cell("RSI(14)", String(a.rsi), a.rsi >= 70 ? C.rose : a.rsi <= 30 ? C.green : undefined)}
            {cell("趨勢", trendZh(a.trend), a.trend === "up" ? C.green : a.trend === "down" ? C.rose : undefined)}
            {cell("ATR 波動", a.atrPct + "%")}
            {cell("MA20", fmtPrice(a.ma20))}
            {cell("MA50", fmtPrice(a.ma50))}
            {cell("24h 動能", (a.momentum >= 0 ? "+" : "") + a.momentum + "%", a.momentum >= 0 ? C.green : C.rose)}
            {cell("資金費率", a.fundingPct + "%")}
            {cell("情緒", a.sentiment + "/100")}
            {cell("風險", String(a.risk), a.risk >= 60 ? C.rose : undefined)}
          </div>
        )}
        <div className="mt-4 space-y-2.5">
          <EnergyRow label="信心" value={a.confidence} tone={C.gold} />
          <EnergyRow label="風險" value={a.risk} tone={a.risk >= 60 ? C.rose : C.teal} />
          <EnergyRow label="情緒" value={a.sentiment} tone={a.sentiment >= 55 ? C.green : a.sentiment <= 45 ? C.rose : C.teal} />
        </div>
        <div className="mt-4 flex flex-wrap gap-1.5" style={{ fontSize: 11 }}>
          {a.support.map((v, i) => <span key={"s" + i} className="rounded px-1.5 py-0.5" style={{ fontFamily: MONO, color: C.green, background: "rgba(70,214,160,0.1)" }}>支 {fmtPrice(v)}</span>)}
          {a.resistance.map((v, i) => <span key={"r" + i} className="rounded px-1.5 py-0.5" style={{ fontFamily: MONO, color: C.rose, background: "rgba(240,105,124,0.1)" }}>壓 {fmtPrice(v)}</span>)}
        </div>
        <div className="mt-4 rounded-lg p-3" style={{ background: "rgba(255,255,255,0.03)", fontSize: 12.5, lineHeight: 1.7 }}>
          <span style={{ fontWeight: 700, color: C.teal }}>操作建議：</span><span style={{ color: C.mut }}>{a.action}</span>
        </div>
        <div className="mt-3">
          <div style={{ fontSize: 12, fontWeight: 700, color: C.mut }}>判讀依據</div>
          <ul className="mt-1.5 space-y-1" style={{ fontSize: 11, color: C.dim }}>
            {a.basis.map((b, i) => <li key={i} className="flex gap-1.5"><span style={{ color: C.gold2 }}>·</span>{b}</li>)}
          </ul>
        </div>
        <div className="mt-3" style={{ fontSize: 10.5, lineHeight: 1.7, color: C.dim }}>{demo ? "目前為展示資料（即時指標暫時無法取得）。" : "以上為技術指標即時計算結果，僅供參考，不構成投資建議。"}</div>
      </div>
    </div>
  );
}

function EnergyRow({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex items-center gap-2" style={{ fontSize: 11.5 }}>
      <span style={{ width: 48, flexShrink: 0, color: C.dim }}>{label}</span>
      <div className="flex-1"><EnergyBar value={value} tone={tone} /></div>
      <span style={{ width: 32, textAlign: "right", fontFamily: MONO, color: C.ink }}>{value}</span>
    </div>
  );
}

export default function AnalysisPage() {
  const [ra, setRa] = useState<RA[] | null>(null);
  const [sel, setSel] = useState<RA | null>(null);
  useEffect(() => {
    fetch("/api/analysis").then((r) => r.json()).then((d) => setRa(d.analyses || [])).catch(() => setRa([]));
  }, []);
  const loading = ra === null;
  const real = ra && ra.length > 0 ? ra : null;
  const demo = !real;
  const display: RA[] = real || ANALYSES.map(toRA);
  const avg = Math.round(display.reduce((a, x) => a + x.sentiment, 0) / Math.max(1, display.length));
  const avgTone = avg >= 55 ? C.green : avg <= 45 ? C.rose : C.teal;
  return (
    <div className="space-y-5">
      <div>
        <h1 style={{ fontSize: 16, fontWeight: 700, color: C.ink }}>AI 智能分析</h1>
        <p className="mt-0.5" style={{ fontSize: 11.5, color: C.dim }}>
          {demo ? "技術指標分析 · 點任一卡片看完整分析 · 非投資建議" : "技術指標即時計算（Bybit）· 點任一卡片看完整分析 · 非投資建議"}
        </p>
      </div>

      <div className="rounded-2xl p-4" style={{ border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.02)" }}>
        <div className="flex items-center justify-between" style={{ fontSize: 13.5 }}>
          <span style={{ fontWeight: 700, color: C.ink }}>市場綜合情緒</span>
          <span style={{ fontFamily: MONO, color: C.ink }}>{avg}/100</span>
        </div>
        <div className="mt-2"><EnergyBar value={avg} tone={avgTone} /></div>
        <div className="mt-1.5" style={{ fontSize: 11.5, color: C.dim }}>{avg >= 55 ? "偏多" : avg <= 45 ? "偏空" : "中性"}</div>
      </div>

      {demo && !loading && (
        <div className="rounded-xl px-4 py-2.5" style={{ border: `1px solid ${C.gold}33`, background: "rgba(232,198,110,0.06)", fontSize: 12, color: C.gold }}>
          即時指標暫時無法取得，以下為展示資料（仍可點開查看範例分析）。
        </div>
      )}

      {loading
        ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl p-4" style={{ border: `1px solid ${C.line}`, background: "rgba(255,255,255,0.02)" }}>
                <Skeleton className="h-4 w-20" />
                <div className="mt-3 space-y-2"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-4/5" /></div>
                <div className="mt-3 grid grid-cols-3 gap-2">{[0, 1, 2].map((j) => <Skeleton key={j} className="h-10" />)}</div>
              </div>
            ))}
          </div>
        )
        : (
          <div className="grid gap-4 lg:grid-cols-2">
            {display.map((a) => (
              <div key={a.symbol} onClick={() => setSel(a)} className="sigrow cursor-pointer relative overflow-hidden rounded-2xl p-4" style={{ border: `1px solid ${C.line}`, background: "linear-gradient(180deg, rgba(16,30,48,0.7), rgba(6,16,30,0.55))" }}>
                <span className="accent-bar" style={{ background: `linear-gradient(${biasColor(a.bias)},transparent)`, boxShadow: `0 0 6px ${biasColor(a.bias)}` }} />
                <div className="row-sweep" />
                <Corner pos="tr" /><Corner pos="br" />
                <div className="flex flex-wrap items-center gap-2" style={{ position: "relative", zIndex: 1 }}>
                  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 15, color: C.ink }}>{a.symbol}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, color: biasColor(a.bias), background: biasColor(a.bias) + "1A" }}>{biasLabel(a.bias)}</span>
                  {!demo && <span style={{ fontFamily: MONO, fontSize: 11.5, color: C.mut }}>${fmtPrice(a.price)}</span>}
                  {!demo && <span style={{ fontFamily: MONO, fontSize: 11.5, color: a.change24h >= 0 ? C.green : C.rose }}>{a.change24h >= 0 ? "+" : ""}{a.change24h}%</span>}
                  <span style={{ marginLeft: "auto", fontSize: 10.5, color: C.teal }}>詳情 →</span>
                </div>
                {!demo && (
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center" style={{ position: "relative", zIndex: 1, fontSize: 11 }}>
                    <div className="rounded-lg p-2" style={{ background: "rgba(255,255,255,0.03)" }}><div style={{ color: C.dim }}>RSI</div><div style={{ marginTop: 2, fontFamily: MONO, color: C.ink }}>{a.rsi}</div></div>
                    <div className="rounded-lg p-2" style={{ background: "rgba(255,255,255,0.03)" }}><div style={{ color: C.dim }}>ATR%</div><div style={{ marginTop: 2, fontFamily: MONO, color: C.ink }}>{a.atrPct}</div></div>
                    <div className="rounded-lg p-2" style={{ background: "rgba(255,255,255,0.03)" }}><div style={{ color: C.dim }}>費率%</div><div style={{ marginTop: 2, fontFamily: MONO, color: C.ink }}>{a.fundingPct}</div></div>
                  </div>
                )}
                <div className="mt-3 space-y-2" style={{ position: "relative", zIndex: 1 }}>
                  <EnergyRow label="信心" value={a.confidence} tone={C.gold} />
                  <EnergyRow label="風險" value={a.risk} tone={a.risk >= 60 ? C.rose : C.teal} />
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5" style={{ position: "relative", zIndex: 1, fontSize: 11 }}>
                  {a.support.map((v, i) => <span key={"s" + i} className="rounded px-1.5 py-0.5" style={{ fontFamily: MONO, color: C.green, background: "rgba(70,214,160,0.1)" }}>支 {fmtPrice(v)}</span>)}
                  {a.resistance.map((v, i) => <span key={"r" + i} className="rounded px-1.5 py-0.5" style={{ fontFamily: MONO, color: C.rose, background: "rgba(240,105,124,0.1)" }}>壓 {fmtPrice(v)}</span>)}
                </div>
              </div>
            ))}
          </div>
        )}
      {sel && <DetailModal a={sel} demo={demo} onClose={() => setSel(null)} />}
    </div>
  );
}
