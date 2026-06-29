"use client";
import { C, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import CTA from "@/components/site/CTA";
import { Signal } from "@/lib/types";
import Link from "next/link";
import { Skeleton, EmptyState } from "@/components/ui";
import { Radio } from "lucide-react";

function fmtPrice(n?: number) {
  if (n == null) return "—";
  return n >= 1000 ? n.toLocaleString("en-US", { maximumFractionDigits: 0 }) : n >= 1 ? n.toFixed(2) : n.toFixed(4);
}

/** 信號戰績流：完全沿用 /api/signals 既有授權結果渲染，不在前端猜測 tier。
 *  entryLow 是否存在即代表後端 sanitizeSignal() 是否已對這個瀏覽者放行價位 —
 *  free / 未登入會是 undefined（一律鎖），Plus / Pro 會是真實數字（直接顯示）。
 *  finalPct（已結算損益%）對 free 也是公開欄位，所以即使鎖價也照實顯示真實輸贏。 */
export default function SignalShowcase({ signals }: { signals: Signal[] | null }) {
  const rows = (signals || []).slice(0, 8);
  return (
    <section style={{ padding: "60px 18px", position: "relative", overflow: "hidden" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative", zIndex: 1 }}>
        <div className="reveal in" style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 12, letterSpacing: 4, color: C.gold2, fontWeight: 700, marginBottom: 14, display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: C.green, boxShadow: `0 0 8px ${C.green}`, animation: "pulseDot 1.4s infinite" }} />
            LIVE · 黑潮船長信號流
          </div>
          <h2 style={{ fontFamily: "inherit", fontSize: "clamp(28px,4.6vw,46px)", fontWeight: 800, color: C.ink, margin: 0, letterSpacing: "-1px", lineHeight: 1.1 }}>
            照實呈現每一筆<span className="gold-text">輸贏</span>
          </h2>
          <p style={{ color: C.mut, fontSize: 15, marginTop: 14, maxWidth: 460, margin: "14px auto 0", lineHeight: 1.6 }}>
            已結算信號的損益％為真實數據，有賺有賠照實顯示。進場 / 止損 / TP 價位依方案開放，<br />未付費僅能看方向與結果。
          </p>
        </div>

        <div className="reveal in glass-sheen" style={{ maxWidth: 600, margin: "0 auto", borderRadius: 20, padding: 20, position: "relative", overflow: "hidden", background: "linear-gradient(180deg, rgba(16,30,48,0.9), rgba(6,16,30,0.78))", border: `1px solid ${C.lineGold}`, boxShadow: "0 20px 60px rgba(0,0,0,.4)" }}>
          <div className="scanline" />
          <Corner pos="tl" /><Corner pos="tr" /><Corner pos="bl" /><Corner pos="br" />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, position: "relative", zIndex: 1 }}>
            <span style={{ fontSize: 11, letterSpacing: 2, color: C.dim }}>● 黑潮信號流</span>
            <span style={{ fontSize: 11, color: C.teal, display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 5, height: 5, borderRadius: 99, background: C.teal, boxShadow: `0 0 6px ${C.teal}`, animation: "pulseDot 1.4s infinite" }} />
              即時資料
            </span>
          </div>

          {signals === null && (
            <div style={{ position: "relative", zIndex: 1 }}>
              {[0, 1, 2, 3].map((i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 8px 13px 14px", borderBottom: `1px solid ${C.line}`, gap: 10 }}>
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-3 w-14 flex-1" />
                  <Skeleton className="h-3 w-16" />
                </div>
              ))}
            </div>
          )}
          {signals !== null && rows.length === 0 && (
            <EmptyState icon={<Radio size={22} />} title="目前沒有信號資料" desc="AI 持續掃描 52 幣種中，有新信號會立即顯示在這裡。" />
          )}

          {rows.map((s) => {
            const sc = s.direction === "long" ? C.green : C.rose;
            const unlocked = s.entryLow != null;
            const closed = s.status !== "active";
            const win = (s.finalPct ?? 0) >= 0;
            return (
              <div key={s.id} className="sigrow" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 8px 13px 14px", borderBottom: `1px solid ${C.line}` }}>
                <span className="accent-bar" style={{ background: `linear-gradient(${sc},transparent)`, boxShadow: `0 0 6px ${sc}` }} />
                <div className="row-sweep" />
                <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative", zIndex: 1, minWidth: 0 }}>
                  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 15, color: C.ink, width: 44 }}>{s.symbol}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, color: sc, background: sc + "1A" }}>{s.direction === "long" ? "做多" : "做空"}</span>
                  <span className="grade-pill" style={{ fontSize: 9.5, fontWeight: 700, padding: "2px 7px", borderRadius: 6, color: s.entryGrade === "S" || s.entryGrade === "A" ? C.gold : C.dim, border: `1px solid ${s.entryGrade === "S" || s.entryGrade === "A" ? C.gold + "55" : C.line}` }}>{s.entryGrade}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 9, position: "relative", zIndex: 1 }}>
                  {unlocked ? (
                    <span style={{ fontFamily: MONO, fontSize: 11, color: C.dim, whiteSpace: "nowrap" }}>${fmtPrice(s.entryLow)}</span>
                  ) : (
                    <span className="locked-px" style={{ fontFamily: MONO, fontSize: 12, letterSpacing: 1.5, userSelect: "none" }}>$●●●.●●</span>
                  )}
                  {closed ? (
                    <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 800, color: win ? C.green : C.rose, minWidth: 48, textAlign: "right" }}>
                      {win ? "+" : ""}{(s.finalPct ?? 0).toFixed(1)}%
                    </span>
                  ) : (
                    <span style={{ fontSize: 11, color: C.teal, whiteSpace: "nowrap" }}>進行中</span>
                  )}
                  {!unlocked && <span style={{ fontSize: 12 }}>🔒</span>}
                </div>
              </div>
            );
          })}

          <div style={{ marginTop: 14, textAlign: "center", position: "relative", zIndex: 1 }}>
            <Link href="/login?register=1">
              <CTA>免費註冊 · 查看今日信號</CTA>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
