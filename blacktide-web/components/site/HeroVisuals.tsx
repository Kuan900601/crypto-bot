"use client";
import { useEffect, useRef } from "react";
import { C } from "@/lib/theme";
import Corner from "@/components/site/Corner";

/** 純裝飾性視覺（燈塔、海浪、飄光），不帶任何數據，禁止在這裡塞任何統計數字。 */

/** 視差景深 hook：依 scrollY * speed 設定 translateY，純 transform，不影響 layout。
 *  speed 負值代表遠景（慢於捲動，往反方向飄），正值代表近景。
 *  尊重 prefers-reduced-motion；用 rAF 節流，passive scroll listener。 */
export function useParallax<T extends HTMLElement>(speed: number) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const apply = () => {
      el.style.transform = `translate3d(0, ${window.scrollY * speed}px, 0)`;
      raf = 0;
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(apply); };
    window.addEventListener("scroll", onScroll, { passive: true });
    apply();
    return () => { window.removeEventListener("scroll", onScroll); cancelAnimationFrame(raf); };
  }, [speed]);
  return ref;
}

export function GodRays() {
  const ref = useParallax<HTMLDivElement>(-0.06);
  return (
    <div ref={ref} className="parallax-layer" style={{ position: "absolute", inset: 0, zIndex: 1, overflow: "hidden", pointerEvents: "none" }}>
      {[16, 32, 50, 68, 84].map((left, i) => (
        <div key={i} className="gpu" style={{
          position: "absolute", top: "-10%", left: left + "%", width: 110, height: "95%",
          background: `linear-gradient(180deg, ${i % 2 ? "rgba(0,212,255,0.07)" : "rgba(0,212,255,0.08)"}, transparent 72%)`,
          transform: "skewX(-8deg)", filter: "blur(7px)", animation: `rayShift ${9 + i * 1.6}s ease-in-out ${-i * 1.3}s infinite`,
        }} />
      ))}
    </div>
  );
}

export function SoftRays() {
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 0, overflow: "hidden", pointerEvents: "none" }}>
      {[22, 48, 74].map((left, i) => (
        <div key={i} className="gpu" style={{
          position: "absolute", top: "-15%", left: left + "%", width: 150, height: "130%",
          background: `linear-gradient(180deg, ${i % 2 ? "rgba(0,212,255,0.05)" : "rgba(0,212,255,0.055)"}, transparent 68%)`,
          transform: "skewX(-9deg)", filter: "blur(10px)", animation: `rayShift ${11 + i * 2.2}s ease-in-out ${-i * 1.8}s infinite`,
        }} />
      ))}
    </div>
  );
}

/** 燈塔 v2「現代信標」（2026-07 重做）：純 SVG 剪影 + conic-gradient 旋轉光束。
 *  效能原則：只用 transform rotate / opacity 動畫，零 blur、零 filter、零 clip-path 動畫
 *  ——舊版 520px blur(10px) 光束層是手機卡頓主因之一。色彩全青色系，無金/奶油殘留。 */
export function Lighthouse() {
  return (
    <div style={{ position: "absolute", bottom: 44, right: "5%", zIndex: 1, pointerEvents: "none", width: 96, height: 216 }}>
      {/* 旋轉光束：兩道對向光的 conic 漸層，radial mask 淡出邊緣，transform-only */}
      <div className="lh-beam gpu" style={{
        position: "absolute", left: "50%", top: 26, width: 340, height: 340,
        marginLeft: -170, marginTop: -170, borderRadius: "50%",
        background: "conic-gradient(from 0deg, transparent 0deg, rgba(0,212,255,0.28) 14deg, rgba(186,243,255,0.36) 22deg, rgba(0,212,255,0.28) 30deg, transparent 44deg, transparent 180deg, rgba(0,212,255,0.16) 196deg, rgba(0,212,255,0.22) 202deg, transparent 216deg)",
        WebkitMask: "radial-gradient(circle, #000 8%, rgba(0,0,0,.55) 40%, transparent 68%)",
        mask: "radial-gradient(circle, #000 8%, rgba(0,0,0,.55) 40%, transparent 68%)",
      }} />
      {/* 燈室靜態光暈（不動畫） */}
      <div style={{ position: "absolute", left: "50%", top: 26, width: 88, height: 88, marginLeft: -44, marginTop: -44, borderRadius: "50%", background: "radial-gradient(circle, rgba(186,243,255,0.5), rgba(0,212,255,0.18) 45%, transparent 70%)" }} />
      {/* 塔身剪影 */}
      <svg width="96" height="216" viewBox="0 0 96 216" style={{ position: "relative", display: "block" }}>
        <defs>
          <linearGradient id="lh2Body" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#0B1117" />
            <stop offset="46%" stopColor="#1E293B" />
            <stop offset="54%" stopColor="#22303F" />
            <stop offset="100%" stopColor="#0B1117" />
          </linearGradient>
        </defs>
        {/* 塔身 */}
        <path d="M39,58 L57,58 L64,204 L32,204 Z" fill="url(#lh2Body)" />
        {/* 塔身青色條紋（信標塗裝） */}
        <path d="M37.4,88 L58.6,88 L59.5,104 L36.6,104 Z" fill="rgba(0,212,255,0.4)" />
        <path d="M35.4,140 L60.9,140 L61.8,156 L34.5,156 Z" fill="rgba(0,212,255,0.3)" />
        {/* 燈室平台 + 護欄 */}
        <rect x="33" y="52" width="30" height="5" rx="2" fill="#1E293B" />
        <rect x="35" y="44" width="26" height="3" rx="1.5" fill="rgba(0,212,255,0.35)" />
        {/* 燈室玻璃 */}
        <rect x="38" y="22" width="20" height="26" rx="3" fill="rgba(11,17,23,0.9)" stroke="rgba(0,212,255,0.5)" strokeWidth="1.2" />
        {/* 燈芯 */}
        <circle cx="48" cy="35" r="5.5" fill="#BAF3FF" className="lh-lamp" />
        {/* 塔頂 */}
        <path d="M36,22 L60,22 L48,8 Z" fill="#1E293B" stroke="rgba(0,212,255,0.35)" strokeWidth="1" />
        <circle cx="48" cy="7" r="2" fill="rgba(0,212,255,0.9)" />
        {/* 基座礁石 */}
        <ellipse cx="48" cy="207" rx="42" ry="9" fill="#0B1117" />
      </svg>
    </div>
  );
}

export function HeroWaves() {
  const ref = useParallax<HTMLDivElement>(0.08);
  const layers = [
    { fill: "rgba(0,212,255,0.12)", h: 130, dur: 11, y: 48, blur: 0 },
    { fill: "rgba(0,163,204,0.2)", h: 150, dur: 15, y: 24, blur: 0 },
    { fill: "rgba(9,20,38,0.9)", h: 180, dur: 21, y: 0, blur: 0 },
  ];
  return (
    <div ref={ref} className="parallax-layer" style={{ position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 2, pointerEvents: "none", height: 200, overflow: "hidden", maskImage: "linear-gradient(180deg, transparent, #000 20%)", WebkitMaskImage: "linear-gradient(180deg, transparent, #000 20%)" }}>
      {layers.map((w, i) => (
        <div key={i} className="gpu" style={{ position: "absolute", left: 0, bottom: w.y, width: "200%", height: w.h, animation: `waveMove ${w.dur}s linear infinite`, filter: w.blur ? `blur(${w.blur}px)` : "none" }}>
          <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
            <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40 L1200,120 L0,120 Z" fill={w.fill} />
          </svg>
        </div>
      ))}
      <div className="gpu" style={{ position: "absolute", left: 0, bottom: 140, width: "200%", height: 50, animation: "waveMove 15s linear infinite" }}>
        <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
          <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40" fill="none" stroke="rgba(0,212,255,0.3)" strokeWidth="2" />
        </svg>
      </div>
    </div>
  );
}

export interface FloatCardData { symbol: string; direction: "long" | "short"; statusLabel: string }
/** 純裝飾浮動卡：symbol/方向/狀態文字皆由呼叫端傳入真實信號資料，這裡不寫死任何幣種或數字。 */
export function FloatCard({ data, style, delay }: { data: FloatCardData; style: React.CSSProperties; delay: number }) {
  const sc = data.direction === "long" ? C.green : C.rose;
  return (
    <div className="gpu" style={{ position: "absolute", padding: "11px 14px", borderRadius: 13, background: "rgba(6,16,30,0.72)", border: `1px solid ${C.linePrimary}`, backdropFilter: "blur(8px)", animation: `drift ${7 + delay}s ease-in-out ${-delay}s infinite`, minWidth: 148, ...style }}>
      <Corner pos="tl" /><Corner pos="br" />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span style={{ fontFamily: "ui-monospace,SF Mono,Menlo,monospace", fontWeight: 800, fontSize: 15, color: C.ink }}>{data.symbol}</span>
        <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 99, color: sc, background: sc + "1A" }}>{data.direction === "long" ? "做多" : "做空"}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
        <span style={{ fontFamily: "ui-monospace,SF Mono,Menlo,monospace", fontSize: 12, color: C.dim, letterSpacing: 1 }}>$●●●.●</span>
        <span style={{ fontSize: 10, color: C.teal }}>🔒 {data.statusLabel}</span>
      </div>
    </div>
  );
}
