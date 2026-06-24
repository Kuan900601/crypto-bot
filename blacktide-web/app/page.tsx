"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Lock } from "lucide-react";
import { useSession } from "next-auth/react";
import { useMarket } from "@/lib/useMarket";
import { Signal } from "@/lib/types";
import TickerTape from "@/components/TickerTape";
import { C, SANS, MONO } from "@/lib/theme";
import Corner from "@/components/site/Corner";
import CTA from "@/components/site/CTA";
import Counter from "@/components/site/Counter";
import SignalShowcase from "@/components/site/SignalShowcase";
import { GodRays, SoftRays, Lighthouse, HeroWaves, FloatCard, useParallax } from "@/components/site/HeroVisuals";
import { useTilt } from "@/lib/useTilt";

// 監測幣種數固定為 52（analyzer.py 實際掃描的幣種數，與站內既有文案一致，非首頁自行估算）
const MONITORED_COINS = 52;

function isToday(iso?: string) {
  if (!iso) return false;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

export default function Home() {
  const { tickers } = useMarket();
  const { data: session } = useSession();
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const heroContentRef = useParallax<HTMLDivElement>(0.04);
  const previewTiltRef = useTilt<HTMLDivElement>(6);
  const perfTiltRef = useTilt<HTMLDivElement>(4);

  useEffect(() => {
    fetch("/api/signals").then((r) => r.json()).then((d) => setSignals(d.signals ?? null)).catch(() => {});
  }, []);

  const todaySignalCount = (signals || []).filter((s) => isToday(s.openedAt)).length;
  const previewSignal = (signals || []).find((s) => s.status === "active") || (signals || [])[0] || null;
  const floatSignals = (signals || []).slice(0, 3);

  // 真實已結算信號績效（依 finalPct 計算；entry/sl/tp 價位不在這裡用，僅算勝率/報酬/回撤）
  const closedSignals = (signals || []).filter((s) => s.status !== "active" && typeof s.finalPct === "number");
  const chronological = [...closedSignals].reverse(); // API 回傳新到舊，轉成舊到新才能算回撤
  const perfWins = chronological.filter((s) => (s.finalPct ?? 0) > 0).length;
  const perfWinRate = chronological.length ? Math.round((perfWins / chronological.length) * 100) : 0;
  const perfAvgPct = chronological.length ? chronological.reduce((a, s) => a + (s.finalPct ?? 0), 0) / chronological.length : 0;
  let perfPeak = 0, perfCum = 0, perfMaxDD = 0;
  for (const s of chronological) {
    perfCum += s.finalPct ?? 0;
    if (perfCum > perfPeak) perfPeak = perfCum;
    const dd = perfPeak - perfCum;
    if (dd > perfMaxDD) perfMaxDD = dd;
  }
  const perfSampleOk = chronological.length >= 5;

  return (
    <div>
      {/* ============ Hero ============ */}
      <section style={{
        position: "relative", overflow: "hidden", minHeight: "min(86vh, 760px)",
        display: "flex", alignItems: "center", borderRadius: 20,
        background: "radial-gradient(1100px 640px at 72% 18%, rgba(19,53,90,0.5), transparent 55%), radial-gradient(800px 560px at 10% 85%, rgba(27,138,130,0.12), transparent 60%)",
      }}>
        <GodRays /><Lighthouse /><HeroWaves />

        {floatSignals.length > 0 && (
          <div className="hidden lg:block" style={{ position: "absolute", inset: 0, zIndex: 3 }}>
            {floatSignals.map((s, i) => (
              <FloatCard key={s.id} delay={i * 1.2} data={{
                symbol: s.symbol, direction: s.direction,
                statusLabel: s.status === "active" ? "進行中" : (s.finalPct ?? 0) >= 0 ? "已止盈" : "已止損",
              }} style={[{ right: "8%", top: "18%" }, { right: "18%", top: "44%" }, { right: "5%", top: "58%" }][i] || {}} />
            ))}
          </div>
        )}

        <div ref={heroContentRef} className="parallax-layer" style={{ position: "relative", zIndex: 5, maxWidth: 1180, margin: "0 auto", padding: "48px 22px", width: "100%" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 32, alignItems: "flex-start" }}>
            <div style={{ maxWidth: 600, flex: "1 1 360px" }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 22, padding: "7px 15px", borderRadius: 999, fontSize: 12, fontWeight: 600, color: C.gold, border: `1px solid ${C.gold}45`, background: `${C.gold}10`, backdropFilter: "blur(4px)" }}>
                <span style={{ width: 6, height: 6, borderRadius: 99, background: C.teal, boxShadow: `0 0 8px ${C.teal}`, animation: "pulseDot 2s infinite" }} />
                {MONITORED_COINS} 幣種 · 24/7 AI 盯盤
              </div>
              <h1 style={{ fontFamily: SANS, fontWeight: 800, lineHeight: 1.32, margin: 0, fontSize: "clamp(36px,6vw,64px)", letterSpacing: "-1.2px", color: C.ink, textShadow: "0 2px 40px rgba(0,0,0,.6)", wordBreak: "keep-all", overflowWrap: "break-word" }}>
                AI 24 小時盯盤<br /><span className="gold-text">幫你抓加密貨幣交易信號</span>
              </h1>
              <p style={{ fontFamily: SANS, fontSize: "clamp(15px,1.8vw,18px)", lineHeight: 1.65, color: C.mut, margin: "22px 0 0", maxWidth: 480, wordBreak: "keep-all", overflowWrap: "break-word" }}>
                {session
                  ? <>歡迎回來，下面是今日 AI 分析與信號戰績。<br />付費方案可解鎖完整進出場價位。</>
                  : <>登入即可查看今日 AI 分析、方向判斷與部分交易信號。<br />升級 Pro 解鎖進場、止損與 TP 點位。</>}
              </p>
              <div style={{ display: "flex", gap: 14, marginTop: 32, flexWrap: "wrap", alignItems: "center" }}>
                {session ? (
                  <Link href="/signals"><CTA big>前往黑潮船長信號 <ArrowRight size={16} style={{ display: "inline", marginLeft: 4 }} /></CTA></Link>
                ) : (
                  <Link href="/login?register=1"><CTA big>免費註冊 · 送 3 日 Plus 體驗</CTA></Link>
                )}
              </div>
              <div style={{ display: "flex", gap: 30, marginTop: 44, flexWrap: "wrap" }}>
                {[[MONITORED_COINS, "監測幣種"], [todaySignalCount, "今日信號"]].map(([n, l]) => (
                  <div key={l as string}>
                    <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 800, color: C.gold }}><Counter to={n as number} /></div>
                    <div style={{ fontSize: 11, color: C.dim, marginTop: 2, letterSpacing: 1 }}>{l}</div>
                  </div>
                ))}
                <div>
                  <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 800, color: C.gold }}>24/7</div>
                  <div style={{ fontSize: 11, color: C.dim, marginTop: 2, letterSpacing: 1 }}>AI 盯盤</div>
                </div>
              </div>
            </div>

            {/* 今日 AI 信號預覽（真實資料；信心為模型評分，非已實現歷史勝率） */}
            {previewSignal && (
              <div ref={previewTiltRef} className="glass-sheen tilt-card" style={{ flex: "0 1 280px", minWidth: 240, borderRadius: 18, padding: 18, position: "relative", background: "rgba(6,16,30,0.78)", border: `1px solid ${C.lineGold}`, backdropFilter: "blur(10px)" }}>
                <Corner pos="tl" /><Corner pos="tr" /><Corner pos="bl" /><Corner pos="br" />
                <div style={{ fontSize: 10, letterSpacing: 2, color: C.dim, marginBottom: 8 }}>今日 AI 信號預覽</div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 18, color: C.ink }}>{previewSignal.symbol}/USDT</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "3px 9px", borderRadius: 99, color: previewSignal.direction === "long" ? C.green : C.rose, background: (previewSignal.direction === "long" ? C.green : C.rose) + "1A" }}>
                    {previewSignal.direction === "long" ? "做多" : "做空"}
                  </span>
                </div>
                <div style={{ marginTop: 6, fontSize: 12, color: C.mut }}>
                  AI 信心評分：<b style={{ color: C.gold }}>{Math.round(previewSignal.winRate ?? 0)}%</b>
                  <span style={{ display: "block", fontSize: 10, color: C.dim, marginTop: 2 }}>模型評分，非已實現歷史勝率</span>
                </div>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
                  {previewSignal.entryLow != null ? (
                    <Row label="進場價" value={"$" + previewSignal.entryLow} />
                  ) : (
                    <LockedRow label="進場價" />
                  )}
                  {previewSignal.stopLoss != null ? (
                    <Row label="止損價" value={"$" + previewSignal.stopLoss} color={C.rose} />
                  ) : (
                    <LockedRow label="止損價" />
                  )}
                  {previewSignal.tps?.[0]?.price != null ? (
                    <Row label="TP1" value={"$" + previewSignal.tps[0].price} color={C.green} />
                  ) : (
                    <LockedRow label="TP1" />
                  )}
                </div>
                {!session && (
                  <Link href="/login?register=1" style={{ display: "block", marginTop: 14 }}>
                    <CTA style={{ width: "100%", padding: "11px 0", fontSize: 13 }}>免費註冊 · 查看完整信號</CTA>
                  </Link>
                )}
              </div>
            )}
          </div>

          {/* 近 N 筆已結算信號績效（樣本不足不強調具體數字，見 design-system §7） */}
          <div ref={perfTiltRef} className="glass-sheen tilt-card" style={{ marginTop: 36, maxWidth: 520, borderRadius: 16, padding: 16, position: "relative", background: "rgba(255,255,255,0.02)", border: `1px solid ${C.line}` }}>
            <div style={{ fontSize: 11, letterSpacing: 2, color: C.dim, marginBottom: 10 }}>
              {perfSampleOk ? `近 ${chronological.length} 筆已結算信號` : "信號績效"}
            </div>
            {perfSampleOk ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, textAlign: "center" }}>
                <div><div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 800, color: C.green }}>{perfWinRate}%</div><div style={{ fontSize: 10, color: C.dim }}>勝率</div></div>
                <div><div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 800, color: perfAvgPct >= 0 ? C.green : C.rose }}>{perfAvgPct >= 0 ? "+" : ""}{perfAvgPct.toFixed(1)}%</div><div style={{ fontSize: 10, color: C.dim }}>平均報酬</div></div>
                <div><div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 800, color: C.rose }}>-{perfMaxDD.toFixed(1)}%</div><div style={{ fontSize: 10, color: C.dim }}>最大回撤</div></div>
              </div>
            ) : (
              <div style={{ fontSize: 12.5, color: C.mut, lineHeight: 1.6, wordBreak: "keep-all", overflowWrap: "break-word" }}>
                樣本仍在累積中，待已結算信號足量後將公開實際績效數字。目前可確認：{MONITORED_COINS} 幣種監測、7+1 策略投票、分批止盈紀律、24/7 AI 盯盤。
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ============ 行情跑馬燈（真實 /api/market，每 60 秒刷新） ============ */}
      <div style={{ marginTop: 28 }}>
        <TickerTape tickers={tickers} />
      </div>

      {/* ============ 信號戰績流 ============ */}
      <SignalShowcase signals={signals} />

      {/* ============ 震撼轉換區 ============ */}
      <section style={{ padding: "70px 22px 80px", position: "relative", overflow: "hidden", textAlign: "center" }}>
        <SoftRays />
        {[0, 1, 2].map((i) => (
          <div key={i} style={{
            position: "absolute", top: "38%", left: "50%", width: 180 + i * 150, height: 180 + i * 150,
            marginLeft: -(90 + i * 75), marginTop: -(90 + i * 75), borderRadius: "50%",
            border: `1.5px solid ${i % 2 ? C.teal : C.gold}`, opacity: 0.14, animation: `sonarPing 5s ease-out ${i * 1}s infinite`,
            pointerEvents: "none",
          }} />
        ))}
        <div style={{ position: "relative", zIndex: 2, maxWidth: 760, margin: "0 auto" }}>
          <div style={{ fontSize: 12, letterSpacing: 5, color: C.tealDk, fontWeight: 700, marginBottom: 22 }}>WHY BLACK TIDE</div>
          <h2 style={{ fontFamily: SANS, fontSize: "clamp(26px,4.6vw,46px)", fontWeight: 800, color: C.ink, margin: 0, lineHeight: 1.32, letterSpacing: "-0.5px", wordBreak: "keep-all", overflowWrap: "break-word" }}>
            這裡能看<span className="teal-text">方向、信號、進場、止損、TP</span>。
          </h2>
          <p style={{ fontSize: "clamp(15px,2vw,18px)", color: C.mut, margin: "16px 0 0", wordBreak: "keep-all" }}>免費註冊即可開始查看今日信號。</p>
          <div style={{ position: "relative", marginTop: 40, display: "inline-block" }}>
            {!session && (
              <Link href="/login?register=1"><CTA big>免費註冊 · 送 3 日 Plus 體驗</CTA></Link>
            )}
            {session && (
              <Link href="/signals"><CTA big>前往黑潮船長信號</CTA></Link>
            )}
          </div>
          <div style={{ fontSize: 12, color: C.dim, marginTop: 16 }}>不需信用卡 · 隨時可取消</div>
        </div>
      </section>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: C.mut }}>{label}</span>
      <span style={{ fontFamily: MONO, color: color || C.ink, fontWeight: 700 }}>{value}</span>
    </div>
  );
}
function LockedRow({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: C.mut }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 4, color: C.dim }}><Lock size={11} />登入解鎖</span>
    </div>
  );
}
