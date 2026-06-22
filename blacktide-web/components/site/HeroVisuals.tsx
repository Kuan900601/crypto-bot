import { C } from "@/lib/theme";
import Corner from "@/components/site/Corner";

/** 純裝飾性視覺（燈塔、海浪、飄光），不帶任何數據，禁止在這裡塞任何統計數字。 */

export function GodRays() {
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 1, overflow: "hidden", pointerEvents: "none" }}>
      {[16, 32, 50, 68, 84].map((left, i) => (
        <div key={i} className="gpu" style={{
          position: "absolute", top: "-10%", left: left + "%", width: 110, height: "95%",
          background: `linear-gradient(180deg, ${i % 2 ? "rgba(55,214,196,0.07)" : "rgba(232,198,110,0.08)"}, transparent 72%)`,
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
          background: `linear-gradient(180deg, ${i % 2 ? "rgba(55,214,196,0.05)" : "rgba(232,198,110,0.055)"}, transparent 68%)`,
          transform: "skewX(-9deg)", filter: "blur(10px)", animation: `rayShift ${11 + i * 2.2}s ease-in-out ${-i * 1.8}s infinite`,
        }} />
      ))}
    </div>
  );
}

export function Lighthouse() {
  return (
    <div style={{ position: "absolute", bottom: 60, right: "4%", zIndex: 1, pointerEvents: "none", opacity: 0.9 }}>
      <div className="gpu" style={{
        position: "absolute", bottom: 130, left: 30, width: 520, height: 230,
        background: "linear-gradient(108deg, rgba(255,246,214,.22) 0%, rgba(232,198,110,.1) 30%, transparent 62%)",
        clipPath: "polygon(0 42%, 0 58%, 100% 100%, 100% 0)", filter: "blur(10px)",
        animation: "beamSweep 8s ease-in-out infinite", transformOrigin: "left center",
      }} />
      <div style={{ position: "absolute", bottom: 0, left: -4, width: 88, height: 188, borderRadius: "50% 50% 35% 35%", background: "radial-gradient(ellipse at 50% 28%, rgba(232,198,110,.2), transparent 62%)", filter: "blur(10px)" }} />
      <svg width="80" height="200" viewBox="0 0 80 200" style={{ position: "relative", display: "block", filter: "drop-shadow(0 0 20px rgba(232,198,110,.32))" }}>
        <defs>
          <linearGradient id="lhBody" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgba(150,120,50,.15)" />
            <stop offset="18%" stopColor="rgba(232,198,110,.42)" />
            <stop offset="50%" stopColor="rgba(255,248,224,.62)" />
            <stop offset="82%" stopColor="rgba(232,198,110,.42)" />
            <stop offset="100%" stopColor="rgba(150,120,50,.15)" />
          </linearGradient>
          <linearGradient id="lhFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(255,255,255,.75)" />
            <stop offset="100%" stopColor="rgba(255,255,255,.85)" />
          </linearGradient>
          <mask id="lhMask"><rect width="80" height="200" fill="url(#lhFade)" /></mask>
          <radialGradient id="lhLamp" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(255,252,235,1)" />
            <stop offset="55%" stopColor="rgba(255,238,190,.95)" />
            <stop offset="100%" stopColor="rgba(232,198,110,.2)" />
          </radialGradient>
        </defs>
        <g mask="url(#lhMask)">
          <path d="M30,52 L50,52 L58,200 L22,200 Z" fill="url(#lhBody)" />
          <rect x="26" y="46" width="28" height="6" rx="2" fill="rgba(255,246,214,.5)" />
          <rect x="31" y="28" width="18" height="18" rx="2.5" fill="rgba(40,32,16,.6)" stroke="rgba(232,198,110,.4)" strokeWidth="1" />
          <rect x="34" y="31" width="12" height="13" rx="1.5" fill="url(#lhLamp)" opacity="0.95" />
          <path d="M28,28 Q40,11 52,28 Z" fill="rgba(232,198,110,.6)" />
        </g>
        <circle cx="40" cy="11" r="1.8" fill="rgba(232,198,110,.8)" />
      </svg>
      <div style={{ position: "absolute", top: 36, left: 40, width: 38, height: 38, borderRadius: "50%", background: "radial-gradient(circle, rgba(255,246,214,.5), transparent 70%)", animation: "beaconPulse 3.4s ease-in-out infinite" }} />
    </div>
  );
}

export function HeroWaves() {
  const layers = [
    { fill: "rgba(232,198,110,0.13)", h: 130, dur: 11, y: 48, blur: 1 },
    { fill: "rgba(27,138,130,0.24)", h: 150, dur: 15, y: 24, blur: 1.5 },
    { fill: "rgba(9,20,38,0.9)", h: 180, dur: 21, y: 0, blur: 0 },
  ];
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 2, pointerEvents: "none", height: 200, overflow: "hidden", maskImage: "linear-gradient(180deg, transparent, #000 20%)", WebkitMaskImage: "linear-gradient(180deg, transparent, #000 20%)" }}>
      {layers.map((w, i) => (
        <div key={i} className="gpu" style={{ position: "absolute", left: 0, bottom: w.y, width: "200%", height: w.h, animation: `waveMove ${w.dur}s linear infinite`, filter: w.blur ? `blur(${w.blur}px)` : "none" }}>
          <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
            <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40 L1200,120 L0,120 Z" fill={w.fill} />
          </svg>
        </div>
      ))}
      <div className="gpu" style={{ position: "absolute", left: 0, bottom: 140, width: "200%", height: 50, animation: "waveMove 15s linear infinite" }}>
        <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
          <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40" fill="none" stroke="rgba(255,244,210,0.42)" strokeWidth="2" />
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
    <div className="gpu" style={{ position: "absolute", padding: "11px 14px", borderRadius: 13, background: "rgba(6,16,30,0.72)", border: `1px solid ${C.lineGold}`, backdropFilter: "blur(8px)", animation: `drift ${7 + delay}s ease-in-out ${-delay}s infinite`, minWidth: 148, ...style }}>
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
