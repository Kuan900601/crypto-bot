import React, { useState, useEffect, useRef, useCallback } from "react";
import { LayoutGrid, Radio, BrainCircuit, Newspaper, CalendarDays, LineChart, Activity, FlaskConical, UserCircle2, Gift, BookOpen, HelpCircle, Send, X, Menu as MenuIcon, ArrowRight } from "lucide-react";

/* ============ 黑潮 Black Tide — 首頁 v7 ============
   導航選單對照真實網站結構（完整側邊抽屜）+ 精緻 logo + 全站風格範本
================================================ */
const C = {
  abyss: "#03060E", deep: "#06101E", current: "#13355A",
  ink: "#EEF4F2", mut: "#8FA6B5", dim: "#566B7C",
  gold: "#E8C66E", gold2: "#C9A24B", teal: "#37D6C4", tealDk: "#1B8A82",
  green: "#46D6A0", rose: "#F0697C",
  line: "rgba(120,180,200,0.12)", lineGold: "rgba(232,198,110,0.16)",
};
const SERIF = '"Cinzel","Noto Serif TC",Georgia,serif';
const SANS = '-apple-system,"PingFang TC","Microsoft JhengHei","Noto Sans TC",system-ui,sans-serif';
const MONO = 'ui-monospace,"SF Mono",Menlo,monospace';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Archivo+Black&display=swap');
@keyframes waveMove{from{transform:translateX(0);}to{transform:translateX(-50%);}}
@keyframes floatUp{0%{opacity:0;transform:translateY(46px);}100%{opacity:1;transform:translateY(0);}}
@keyframes shimmer{0%{background-position:-200% 0;}100%{background-position:200% 0;}}
@keyframes spinSlow{from{transform:rotate(0);}to{transform:rotate(360deg);}}
@keyframes spinRev{from{transform:rotate(360deg);}to{transform:rotate(0);}}
@keyframes spinFast{from{transform:rotate(0);}to{transform:rotate(360deg);}}
@keyframes pulseDot{0%,100%{opacity:1;}50%{opacity:.2;}}
@keyframes beaconPulse{0%,100%{opacity:1;box-shadow:0 0 26px 7px rgba(232,198,110,.85),0 0 60px 20px rgba(55,214,196,.2);}50%{opacity:.6;box-shadow:0 0 46px 15px rgba(232,198,110,.5);}}
@keyframes beamSweep{0%,100%{opacity:.18;transform:rotate(-20deg);}50%{opacity:.6;transform:rotate(-7deg);}}
@keyframes rayShift{0%,100%{opacity:.35;transform:translateX(0) skewX(-8deg);}50%{opacity:.75;transform:translateX(22px) skewX(-8deg);}}
@keyframes bob{0%,100%{transform:translateY(0);}50%{transform:translateY(-12px);}}
@keyframes drift{0%{transform:translateY(0) rotate(-1deg);}50%{transform:translateY(-16px) rotate(1.5deg);}100%{transform:translateY(0) rotate(-1deg);}}
@keyframes glowPulse{0%,100%{opacity:.5;}50%{opacity:1;}}
@keyframes ctaPulse{0%,100%{box-shadow:0 8px 34px rgba(232,198,110,.4),0 0 0 0 rgba(232,198,110,.5);}50%{box-shadow:0 8px 40px rgba(232,198,110,.6),0 0 0 8px rgba(232,198,110,0);}}
@keyframes feedIn{0%{opacity:0;transform:translateY(-20px) scale(.95);}100%{opacity:1;transform:translateY(0) scale(1);}}
@keyframes sonarPing{0%{transform:scale(.3);opacity:.7;}100%{transform:scale(1);opacity:0;}}
@keyframes riseUp{0%{transform:translateY(0) scale(.5);opacity:0;}12%{opacity:.85;}100%{transform:translateY(-260px) scale(1.15);opacity:0;}}
@keyframes burstPulse{0%{transform:translate(-50%,-50%) scale(.35);opacity:.55;}100%{transform:translate(-50%,-50%) scale(1.7);opacity:0;}}
@keyframes risingGlow{0%,100%{opacity:.45;transform:translateY(0);}50%{opacity:.8;transform:translateY(-12px);}}
@keyframes ctaBigPulse{0%,100%{box-shadow:0 10px 44px rgba(232,198,110,.5),0 0 0 0 rgba(232,198,110,.6);}50%{box-shadow:0 12px 56px rgba(232,198,110,.75),0 0 0 14px rgba(232,198,110,0);}}
@keyframes navGlow{0%{background-position:0% 0;}100%{background-position:200% 0;}}
@keyframes logoGlowPulse{0%,100%{box-shadow:0 0 18px rgba(232,198,110,.3),inset 0 0 14px rgba(55,214,196,.15);}50%{box-shadow:0 0 28px rgba(232,198,110,.5),inset 0 0 18px rgba(55,214,196,.25);}}
@keyframes drawerIn{from{transform:translateX(-100%);}to{transform:translateX(0);}}
@keyframes fadeIn{from{opacity:0;}to{opacity:1;}}
@keyframes rowIn{from{opacity:0;transform:translateX(-12px);}to{opacity:1;transform:translateX(0);}}
@keyframes scanDown{0%{top:-12%;opacity:0;}12%{opacity:1;}88%{opacity:1;}100%{top:108%;opacity:0;}}
@keyframes newFlash{0%{box-shadow:inset 0 0 0 1px rgba(232,198,110,.6),0 0 18px rgba(232,198,110,.25);}100%{box-shadow:inset 0 0 0 1px transparent,0 0 0 transparent;}}
.reveal{opacity:0;}.reveal.in{animation:floatUp .9s cubic-bezier(.2,.7,.2,1) forwards;}
.bt *{box-sizing:border-box;}
.gold-text{background:linear-gradient(92deg,#8A6E22,#E8C66E 38%,#FFF6D6 50%,#E8C66E 62%,#8A6E22);background-size:200% auto;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 6s linear infinite;}
.teal-text{background:linear-gradient(92deg,#1B8A82,#37D6C4 50%,#9DFCF0,#37D6C4,#1B8A82);background-size:200% auto;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 7s linear infinite;}
.cta{position:relative;overflow:hidden;transition:transform .25s;animation:ctaPulse 2.6s ease-in-out infinite;}
.cta:hover{transform:translateY(-3px) scale(1.02);}
.cta::after{content:'';position:absolute;inset:0;background:linear-gradient(110deg,transparent 30%,rgba(255,255,255,.45) 50%,transparent 70%);background-size:200% 100%;animation:shimmer 2.8s linear infinite;}
.cta-big{position:relative;overflow:hidden;transition:transform .25s;animation:ctaBigPulse 2.4s ease-in-out infinite;}
.cta-big:hover{transform:translateY(-3px) scale(1.04);}
.cta-big::after{content:'';position:absolute;inset:0;background:linear-gradient(110deg,transparent 28%,rgba(255,255,255,.5) 50%,transparent 72%);background-size:200% 100%;animation:shimmer 2.6s linear infinite;}
.btn2{transition:transform .2s,border-color .2s,color .2s;}
.btn2:hover{transform:translateY(-2px);border-color:rgba(55,214,196,.6)!important;color:#9DFCF0!important;}
.ghost{font-family:'Archivo Black',sans-serif;-webkit-text-stroke:1.5px rgba(232,198,110,.14);color:transparent;line-height:.8;user-select:none;}
.login-link{transition:color .2s;cursor:pointer;}
.login-link:hover{color:#EEF4F2!important;}
.ham{transition:background .2s,border-color .2s;cursor:pointer;}
.ham:hover{background:rgba(232,198,110,.1)!important;border-color:rgba(232,198,110,.4)!important;}
/* drawer rows */
.mrow{transition:background .2s,padding-left .2s;cursor:pointer;}
.mrow:hover{background:rgba(232,198,110,.07);padding-left:20px!important;}
.tg-btn{transition:transform .2s,border-color .2s,box-shadow .2s;}
.tg-btn:hover{transform:translateY(-2px);border-color:rgba(55,214,196,.55)!important;box-shadow:0 8px 24px rgba(55,214,196,.15);}
/* signal list dynamics */
.sigrow{transition:background .2s,transform .2s;border-radius:9px;position:relative;overflow:hidden;}
.sigrow:hover{background:rgba(232,198,110,.07)!important;transform:translateX(4px);}
.sigrow:hover .row-sweep{opacity:1;}
.row-sweep{position:absolute;inset:0;pointer-events:none;background:linear-gradient(100deg,transparent 30%,rgba(232,198,110,.10) 50%,transparent 70%);background-size:220% 100%;opacity:0;transition:opacity .3s;animation:rowSweep 2.4s linear infinite;}
@keyframes rowSweep{0%{background-position:200% 0;}100%{background-position:-200% 0;}}
.accent-bar{position:absolute;left:0;top:50%;transform:translateY(-50%);width:3px;height:0;border-radius:3px;animation:accentGrow .5s ease-out forwards;}
@keyframes accentGrow{to{height:60%;}}
.locked-px{background:linear-gradient(92deg,#3E4C58,#9FB3C0 50%,#3E4C58);background-size:200% auto;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 2.6s linear infinite;}
.grade-pill{animation:gradeFlash 2.5s ease-in-out infinite;}
@keyframes gradeFlash{0%,100%{opacity:.85;}50%{opacity:1;}}
.scanline{position:absolute;left:0;right:0;height:50px;pointer-events:none;background:linear-gradient(180deg, transparent, rgba(55,214,196,.16) 45%, rgba(55,214,196,.26) 50%, rgba(55,214,196,.16) 55%, transparent);filter:blur(0.5px);animation:scanDown 4s ease-in-out infinite;z-index:2;}
/* logo */
.logo-wrap{position:relative;cursor:pointer;}
.logo-ring{position:absolute;inset:-3px;border-radius:50%;background:repeating-conic-gradient(from 0deg, rgba(232,198,110,.55) 0deg 1.4deg, transparent 1.4deg 14deg);-webkit-mask:radial-gradient(circle, transparent calc(50% - 2.5px), #000 calc(50% - 2.5px), #000 50%, transparent 50%);mask:radial-gradient(circle, transparent calc(50% - 2.5px), #000 calc(50% - 2.5px), #000 50%, transparent 50%);animation:spinSlow 34s linear infinite;}
.logo-body{position:absolute;inset:0;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 50% 38%, #112338, #03060E);border:1px solid rgba(232,198,110,.5);animation:logoGlowPulse 4s ease-in-out infinite;}
.logo-current{position:absolute;inset:-20%;border-radius:50%;background:conic-gradient(from 0deg, transparent 0%, rgba(232,198,110,.45) 18%, transparent 38%, rgba(55,214,196,.4) 62%, transparent 82%, rgba(232,198,110,.3) 100%);animation:spinRev 9s linear infinite;opacity:.7;filter:blur(1px);}
.logo-sweep{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg, rgba(55,214,196,.5) 0deg, rgba(55,214,196,.05) 22deg, transparent 44deg);animation:spinFast 4.5s linear infinite;}
.logo-inring{position:absolute;inset:18%;border-radius:50%;border:1px solid rgba(55,214,196,.25);border-top-color:rgba(232,198,110,.7);animation:spinSlow 16s linear infinite;}
.logo-char{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;z-index:2;}
.logo-wrap:hover .logo-sweep{animation-duration:1.6s;}
.logo-wrap:hover .logo-current{animation-duration:4s;opacity:1;}
.logo-wrap:hover .logo-ring{animation-duration:10s;}
.bt ::-webkit-scrollbar{width:0;height:0;}
.nav-reg{display:block;}
@media(max-width:380px){.nav-reg{display:none;}}
.sig-time{display:inline;}
@media(max-width:440px){.sig-time{display:none;}}
.gpu{will-change:transform;transform:translateZ(0);backface-visibility:hidden;}
.logo-current,.logo-sweep,.logo-ring,.logo-inring{will-change:transform;}
.scanline,.row-sweep{will-change:transform,background-position;}
@media(prefers-reduced-motion:reduce){*{animation:none!important;}}
`;

/* ====== 精緻 logo（抽象黑潮波浪線條）====== */
function LogoMark({ size = 42 }) {
  return (
    <div className="logo-wrap" style={{ width: size, height: size }}>
      <div className="logo-ring" />
      <div className="logo-body">
        <div className="logo-current" />
        <div className="logo-sweep" />
        <div className="logo-inring" />
        {/* 抽象黑潮波浪：三道由細到粗、由淡到亮的金色洋流線 */}
        <svg viewBox="0 0 48 48" style={{ position: "absolute", inset: 0, zIndex: 2 }}>
          <defs>
            <linearGradient id="lgWave" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#8A6E22" />
              <stop offset="45%" stopColor="#E8C66E" />
              <stop offset="55%" stopColor="#FFF6D6" />
              <stop offset="100%" stopColor="#C9A24B" />
            </linearGradient>
            <linearGradient id="lgWave2" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1B8A82" />
              <stop offset="50%" stopColor="#37D6C4" />
              <stop offset="100%" stopColor="#1B8A82" />
            </linearGradient>
          </defs>
          {/* 上方細浪（萤光綠，呼應深海） */}
          <path d="M10,19 Q17,13 24,19 T38,19" fill="none" stroke="url(#lgWave2)" strokeWidth="1.6" strokeLinecap="round" opacity="0.75" />
          {/* 主浪（金，最亮最粗） */}
          <path d="M9,26 Q16.5,18 24,26 T39,26" fill="none" stroke="url(#lgWave)" strokeWidth="3.2" strokeLinecap="round" />
          {/* 下方浪（金，較淡） */}
          <path d="M11,33 Q17.5,27 24,33 T37,33" fill="none" stroke="url(#lgWave)" strokeWidth="2.2" strokeLinecap="round" opacity="0.6" />
        </svg>
      </div>
    </div>
  );
}

/* 全頁洋流 */
function GlobalCurrent() {
  const ref = useRef(null); const raf = useRef(0);
  useEffect(() => {
    const cv = ref.current; if (!cv) return; const ctx = cv.getContext("2d");
    const mobile = window.innerWidth < 768;
    let W = 0, H = 0; const dpr = Math.min(mobile ? 1.4 : 2, window.devicePixelRatio || 1);
    const resize = () => { W = window.innerWidth; H = window.innerHeight; cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px"; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resize(); window.addEventListener("resize", resize);
    const N = Math.min(mobile ? 90 : 180, Math.floor(W / (mobile ? 9 : 7)));
    const parts = Array.from({ length: N }, () => ({ x: Math.random() * W, y: Math.random() * H, sp: 0.5 + Math.random() * 1.3, hue: Math.random() < 0.72 ? "g" : "t", a: 0.3 + Math.random() * 0.55 }));
    const field = (x, y, t) => { const s = 0.0015; return (Math.sin(x * s + t * 3e-4) * 0.8 + Math.cos(y * s * 1.4 - t * 4e-4) * 0.7 + Math.sin((x + y) * s * 0.6 + t * 2e-4) * 0.5) * 0.9 - 0.15; };
    let t0 = performance.now(); let running = true;
    const draw = (t) => {
      if (!running) return;
      const dt = Math.min(40, t - t0); t0 = t; ctx.fillStyle = "rgba(3,6,14,0.085)"; ctx.fillRect(0, 0, W, H);
      for (const p of parts) {
        const a = field(p.x, p.y, t), vx = Math.cos(a) * p.sp, vy = Math.sin(a) * p.sp - 0.25;
        const nx = p.x + vx * dt * 0.06, ny = p.y + vy * dt * 0.06;
        ctx.strokeStyle = p.hue === "g" ? `rgba(235,200,115,${p.a})` : `rgba(70,224,205,${p.a})`;
        ctx.lineWidth = p.hue === "g" ? 1.8 : 1.4;
        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); ctx.stroke();
        p.x = nx; p.y = ny;
        if (p.x < -20 || p.x > W + 20 || p.y < -20 || p.y > H + 20) { p.x = Math.random() * W * 0.4 - 20; p.y = H * 0.3 + Math.random() * H * 0.7; }
      }
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    // 頁面隱藏時暫停，回來再續，省電省效能
    const onVis = () => { if (document.hidden) { running = false; cancelAnimationFrame(raf.current); } else if (!running) { running = true; t0 = performance.now(); raf.current = requestAnimationFrame(draw); } };
    document.addEventListener("visibilitychange", onVis);
    return () => { running = false; cancelAnimationFrame(raf.current); window.removeEventListener("resize", resize); document.removeEventListener("visibilitychange", onVis); };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", inset: 0, width: "100%", height: "100%", zIndex: 0, pointerEvents: "none", willChange: "transform", transform: "translateZ(0)" }} />;
}
function Plankton({ count = 30 }) {
  const dots = useRef(Array.from({ length: count }, () => ({ left: Math.random() * 100, top: Math.random() * 100, size: 2 + Math.random() * 3, dur: 7 + Math.random() * 11, delay: -Math.random() * 12, teal: Math.random() < 0.5 }))).current;
  return <div style={{ position: "fixed", inset: 0, zIndex: 0, overflow: "hidden", pointerEvents: "none" }}>
    {dots.map((d, i) => <div key={i} style={{ position: "absolute", left: d.left + "%", top: d.top + "%", width: d.size, height: d.size, borderRadius: "50%", background: d.teal ? C.teal : C.gold, boxShadow: `0 0 ${d.size * 4}px ${d.teal ? C.teal : C.gold}`, animation: `bob ${d.dur}s ease-in-out ${d.delay}s infinite, glowPulse ${d.dur * 0.6}s ease-in-out ${d.delay}s infinite`, opacity: 0.75 }} />)}
  </div>;
}
function ScrollBar() {
  const [p, setP] = useState(0);
  useEffect(() => { const on = () => { const h = document.documentElement.scrollHeight - window.innerHeight; setP(h > 0 ? window.scrollY / h : 0); }; window.addEventListener("scroll", on, { passive: true }); on(); return () => window.removeEventListener("scroll", on); }, []);
  return <div style={{ position: "fixed", top: 0, left: 0, right: 0, height: 2.5, zIndex: 100 }}><div style={{ height: "100%", width: p * 100 + "%", background: `linear-gradient(90deg,${C.teal},${C.gold})`, boxShadow: `0 0 10px ${C.gold}`, transition: "width .1s" }} /></div>;
}
function GodRays() {
  return <div style={{ position: "absolute", inset: 0, zIndex: 1, overflow: "hidden", pointerEvents: "none" }}>
    {[16, 32, 50, 68, 84].map((left, i) => <div key={i} style={{ position: "absolute", top: "-10%", left: left + "%", width: 110, height: "95%", background: `linear-gradient(180deg, ${i % 2 ? "rgba(55,214,196,0.07)" : "rgba(232,198,110,0.08)"}, transparent 72%)`, transform: "skewX(-8deg)", filter: "blur(7px)", animation: `rayShift ${9 + i * 1.6}s ease-in-out ${-i * 1.3}s infinite` }} />)}
  </div>;
}
/* 區塊用：較淡的飄動光束，保證下方區塊也有背景動態 */
function SoftRays() {
  return <div style={{ position: "absolute", inset: 0, zIndex: 0, overflow: "hidden", pointerEvents: "none" }}>
    {[22, 48, 74].map((left, i) => <div key={i} style={{ position: "absolute", top: "-15%", left: left + "%", width: 150, height: "130%", background: `linear-gradient(180deg, ${i % 2 ? "rgba(55,214,196,0.05)" : "rgba(232,198,110,0.055)"}, transparent 68%)`, transform: "skewX(-9deg)", filter: "blur(10px)", animation: `rayShift ${11 + i * 2.2}s ease-in-out ${-i * 1.8}s infinite` }} />)}
  </div>;
}
function Lighthouse() {
  return <div style={{ position: "absolute", bottom: 100, right: "4%", zIndex: 1, pointerEvents: "none", opacity: 0.9 }}>
    {/* 柔和光束（從燈室往左上，自然散開） */}
    <div style={{ position: "absolute", bottom: 210, left: 30, width: 820, height: 360, background: "linear-gradient(108deg, rgba(255,246,214,.22) 0%, rgba(232,198,110,.1) 30%, transparent 62%)", clipPath: "polygon(0 42%, 0 58%, 100% 100%, 100% 0)", filter: "blur(10px)", animation: "beamSweep 8s ease-in-out infinite", transformOrigin: "left center" }} />
    {/* 整體柔光暈 */}
    <div style={{ position: "absolute", bottom: 0, left: -6, width: 130, height: 280, borderRadius: "50% 50% 35% 35%", background: "radial-gradient(ellipse at 50% 28%, rgba(232,198,110,.2), transparent 62%)", filter: "blur(12px)" }} />
    <svg width="118" height="300" viewBox="0 0 80 200" style={{ position: "relative", display: "block", filter: "drop-shadow(0 0 20px rgba(232,198,110,.32))" }}>
      <defs>
        {/* 塔身左右漸層：邊緣柔化融入，中央亮 */}
        <linearGradient id="lhBody" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgba(150,120,50,.15)" />
          <stop offset="18%" stopColor="rgba(232,198,110,.42)" />
          <stop offset="50%" stopColor="rgba(255,248,224,.62)" />
          <stop offset="82%" stopColor="rgba(232,198,110,.42)" />
          <stop offset="100%" stopColor="rgba(150,120,50,.15)" />
        </linearGradient>
        {/* 底部保持實，頂部稍柔 */}
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
        {/* 塔身（加寬，正常比例：頂窄底寬但不尖細） */}
        <path d="M30,52 L50,52 L58,200 L22,200 Z" fill="url(#lhBody)" />
        {/* 觀景台（比塔身略寬） */}
        <rect x="26" y="46" width="28" height="6" rx="2" fill="rgba(255,246,214,.5)" />
        {/* 燈室外殼（對稱、深色框） */}
        <rect x="31" y="28" width="18" height="18" rx="2.5" fill="rgba(40,32,16,.6)" stroke="rgba(232,198,110,.4)" strokeWidth="1" />
        {/* 燈室內透出的光（柔和、居中） */}
        <rect x="34" y="31" width="12" height="13" rx="1.5" fill="url(#lhLamp)" opacity="0.95" />
        {/* 圓頂屋頂 */}
        <path d="M28,28 Q40,11 52,28 Z" fill="rgba(232,198,110,.6)" />
      </g>
      {/* 頂尖 */}
      <circle cx="40" cy="11" r="1.8" fill="rgba(232,198,110,.8)" />
    </svg>
    {/* 燈光脈動光暈（置中對齊燈室） */}
    <div style={{ position: "absolute", top: 36, left: 40, width: 38, height: 38, borderRadius: "50%", background: "radial-gradient(circle, rgba(255,246,214,.5), transparent 70%)", animation: "beaconPulse 3.4s ease-in-out infinite" }} />
  </div>;
}
function useReveal() {
  const ref = useRef(null);
  useEffect(() => { const el = ref.current; if (!el) return; const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && e.target.classList.add("in")), { threshold: 0.12 }); el.querySelectorAll(".reveal").forEach((n) => io.observe(n)); return () => io.disconnect(); }, []);
  return ref;
}
function Counter({ to, dur = 1400 }) {
  const [v, setV] = useState(0); const ref = useRef(null); const done = useRef(false);
  useEffect(() => { const el = ref.current; if (!el) return; const io = new IntersectionObserver((es) => { if (es[0].isIntersecting && !done.current) { done.current = true; const t0 = performance.now(); const tick = (t) => { const p = Math.min(1, (t - t0) / dur); setV(Math.round(to * (1 - Math.pow(1 - p, 3)))); if (p < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); } }, { threshold: 0.5 }); io.observe(el); return () => io.disconnect(); }, [to, dur]);
  return <span ref={ref}>{v}</span>;
}
function Corner({ pos, c = C.gold2 }) {
  const base = { position: "absolute", width: 15, height: 15, borderColor: c, opacity: 0.55 };
  const m = { tl: { top: 7, left: 7, borderTop: "1.5px solid", borderLeft: "1.5px solid" }, tr: { top: 7, right: 7, borderTop: "1.5px solid", borderRight: "1.5px solid" }, bl: { bottom: 7, left: 7, borderBottom: "1.5px solid", borderLeft: "1.5px solid" }, br: { bottom: 7, right: 7, borderBottom: "1.5px solid", borderRight: "1.5px solid" } };
  return <div style={{ ...base, ...m[pos] }} />;
}
const veil = (op = 0.78) => ({ background: `rgba(4,9,16,${op})` });
function CTA({ children, big }) {
  return <button className="cta" style={{ padding: big ? "17px 42px" : "15px 30px", borderRadius: 13, fontSize: big ? 17 : 16, fontWeight: 800, cursor: "pointer", color: C.abyss, border: "none", fontFamily: SANS, background: `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})` }}>{children}</button>;
}

/* ====== 選單資料（對照真實網站）====== */
const MENU_MAIN = [
  { icon: LayoutGrid, label: "市場總覽", active: true },
  { icon: Radio, label: "黑潮船長", badge: "PRO" },
  { icon: BrainCircuit, label: "AI 分析", badge: "PLUS" },
  { icon: Newspaper, label: "新聞中心", badge: "PLUS" },
  { icon: CalendarDays, label: "事件行事曆" },
  { icon: LineChart, label: "美股分析" },
  { icon: Activity, label: "異常監控", badge: "PLUS" },
  { icon: FlaskConical, label: "策略回測", badge: "PRO" },
];
const MENU_OTHER = [
  { icon: UserCircle2, label: "會員中心" },
  { icon: Gift, label: "福利中心" },
  { icon: BookOpen, label: "使用教學" },
  { icon: HelpCircle, label: "常見問題" },
];
function Badge({ kind }) {
  const pro = kind === "PRO";
  return <span style={{
    fontSize: 9.5, fontWeight: 800, letterSpacing: 1, padding: "3px 9px", borderRadius: 7,
    color: pro ? C.abyss : C.gold,
    background: pro ? `linear-gradient(135deg,${C.gold},${C.gold2})` : "rgba(232,198,110,0.1)",
    border: pro ? "none" : `1px solid ${C.gold}40`,
    boxShadow: pro ? "0 2px 8px rgba(232,198,110,.3)" : "none",
  }}>{kind}</span>;
}
function MenuRow({ item, i }) {
  const Icon = item.icon;
  return <div className="mrow" style={{
    display: "flex", alignItems: "center", gap: 14, padding: "13px 16px", borderRadius: 13, position: "relative",
    animation: `rowIn .4s ease-out ${i * 0.035}s both`,
    background: item.active ? "linear-gradient(100deg, rgba(232,198,110,0.16), rgba(232,198,110,0.04))" : "transparent",
    border: item.active ? `1px solid ${C.gold}33` : "1px solid transparent",
  }}>
    {item.active && <div style={{ position: "absolute", left: 0, top: "50%", transform: "translateY(-50%)", width: 3, height: 20, borderRadius: 3, background: `linear-gradient(${C.gold},${C.teal})` }} />}
    <Icon size={20} strokeWidth={1.8} color={item.active ? C.gold : C.mut} style={{ flexShrink: 0 }} />
    <span style={{ flex: 1, fontSize: 15, fontWeight: item.active ? 700 : 600, color: item.active ? C.ink : "#B9C7D2" }}>{item.label}</span>
    {item.badge && <Badge kind={item.badge} />}
    {item.active && <ArrowRight size={15} color={C.gold} style={{ flexShrink: 0 }} />}
  </div>;
}

/* ====== 側邊抽屜 ====== */
function Drawer({ open, onClose }) {
  return <>
    {/* backdrop */}
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 90, background: "rgba(2,4,9,0.6)", backdropFilter: "blur(3px)",
      opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none", transition: "opacity .3s", animation: open ? "fadeIn .3s" : "none",
    }} />
    {/* panel */}
    <aside style={{
      position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 95, width: 340, maxWidth: "87vw",
      transform: open ? "translateX(0)" : "translateX(-100%)", transition: "transform .38s cubic-bezier(.2,.8,.2,1)",
      background: "rgba(4,9,16,0.97)", backdropFilter: "blur(20px)", borderRight: `1px solid ${C.lineGold}`,
      display: "flex", flexDirection: "column", boxShadow: "16px 0 60px rgba(0,0,0,.6)",
    }}>
      {/* current sheen */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(400px 300px at 20% 10%, rgba(19,53,90,0.4), transparent 60%)", pointerEvents: "none" }} />
      {/* header */}
      <div style={{ position: "relative", padding: "22px 20px 18px", borderBottom: `1px solid ${C.line}`, display: "flex", alignItems: "center", gap: 13 }}>
        <LogoMark size={52} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 19, letterSpacing: 1, color: C.ink, lineHeight: 1.15 }}>黑潮 <span style={{ fontSize: 15 }}>BLACKTIDE</span></div>
          <div style={{ fontFamily: SERIF, fontSize: 9, letterSpacing: 2.5, color: C.gold2, marginTop: 2 }}>SIGNALS · PRO TERMINAL</div>
        </div>
        <div onClick={onClose} className="ham" style={{ width: 34, height: 34, borderRadius: 10, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><X size={18} color={C.mut} /></div>
      </div>
      {/* scroll area */}
      <div style={{ position: "relative", flex: 1, overflowY: "auto", padding: "16px 14px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {MENU_MAIN.map((m, i) => <MenuRow key={m.label} item={m} i={i} />)}
        </div>
        <div style={{ fontSize: 11, letterSpacing: 2, color: C.dim, fontWeight: 700, margin: "22px 16px 8px" }}>其他</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {MENU_OTHER.map((m, i) => <MenuRow key={m.label} item={m} i={i + MENU_MAIN.length} />)}
        </div>
      </div>
      {/* footer */}
      <div style={{ position: "relative", padding: "16px 18px 20px", borderTop: `1px solid ${C.line}` }}>
        <button className="tg-btn" style={{
          width: "100%", padding: "13px 16px", borderRadius: 13, display: "flex", alignItems: "center", gap: 10,
          background: "rgba(55,214,196,0.06)", border: `1px solid ${C.teal}33`, color: C.ink, cursor: "pointer", fontFamily: SANS,
          fontSize: 14.5, fontWeight: 700,
        }}>
          <Send size={17} color={C.teal} /><span style={{ flex: 1, textAlign: "left" }}>Telegram 社群頻道</span><ArrowRight size={16} color={C.teal} />
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 16, fontSize: 11.5, color: C.mut }}>
          <span style={{ width: 7, height: 7, borderRadius: 99, background: C.green, boxShadow: `0 0 6px ${C.green}`, animation: "pulseDot 1.6s infinite" }} />行情：Bybit 即時
        </div>
        <div style={{ fontSize: 10.5, color: C.dim, marginTop: 6 }}>© 2026 黑潮 BLACKTIDE</div>
      </div>
    </aside>
  </>;
}

/* ====== 導航列 ====== */
function Nav({ onMenu }) {
  const [scr, setScr] = useState(false);
  useEffect(() => { const on = () => setScr(window.scrollY > 30); window.addEventListener("scroll", on, { passive: true }); on(); return () => window.removeEventListener("scroll", on); }, []);
  return <nav style={{ position: "sticky", top: 0, zIndex: 60, transition: "all .35s cubic-bezier(.2,.7,.2,1)", background: scr ? "rgba(3,6,14,0.82)" : "rgba(3,6,14,0.3)", backdropFilter: "blur(16px)", borderBottom: `1px solid ${scr ? C.lineGold : "transparent"}`, boxShadow: scr ? "0 6px 30px rgba(0,0,0,.4)" : "none" }}>
    {scr && <div style={{ position: "absolute", bottom: -1, left: 0, right: 0, height: 1, background: `linear-gradient(90deg, transparent, ${C.gold}, ${C.teal}, ${C.gold}, transparent)`, backgroundSize: "200% 100%", animation: "navGlow 6s linear infinite", opacity: 0.6 }} />}
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: scr ? "9px 16px" : "14px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, transition: "padding .35s", flexWrap: "nowrap" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
        <div onClick={onMenu} className="ham" style={{ width: 40, height: 40, borderRadius: 11, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(255,255,255,0.02)", flexShrink: 0 }}>
          <MenuIcon size={20} color={C.gold} />
        </div>
        <LogoMark size={scr ? 36 : 42} />
        <div style={{ transition: "all .35s", minWidth: 0, overflow: "hidden" }}>
          <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: scr ? 15 : 17, letterSpacing: 1.2, color: C.ink, lineHeight: 1.1, whiteSpace: "nowrap" }}>黑潮 BLACKTIDE</div>
          <div style={{ fontFamily: SERIF, fontSize: 7.5, letterSpacing: 2, color: C.gold2, whiteSpace: "nowrap" }}>SIGNALS · PRO TERMINAL</div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <button className="cta nav-reg" style={{ padding: "9px 16px", borderRadius: 11, fontSize: 13.5, fontWeight: 800, cursor: "pointer", color: C.abyss, border: "none", fontFamily: SANS, background: `linear-gradient(135deg,${C.gold},${C.gold2})`, whiteSpace: "nowrap" }}>免費註冊</button>
        <div className="ham" title="個人資料 / 登入" style={{ width: 40, height: 40, borderRadius: "50%", border: `1px solid ${C.lineGold}`, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(232,198,110,0.06)", flexShrink: 0 }}>
          <UserCircle2 size={21} color={C.gold} strokeWidth={1.8} />
        </div>
      </div>
    </div>
  </nav>;
}

/* Hero 底部海浪（明顯但優雅，金色浪頂；蓋住燈塔基座） */
function HeroWaves() {
  const layers = [
    { fill: "rgba(232,198,110,0.13)", h: 130, dur: 11, y: 48, blur: 1 },
    { fill: "rgba(27,138,130,0.24)", h: 150, dur: 15, y: 24, blur: 1.5 },
    { fill: "rgba(9,20,38,0.9)", h: 180, dur: 21, y: 0, blur: 0 },
  ];
  return <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 2, pointerEvents: "none", height: 230, overflow: "hidden", maskImage: "linear-gradient(180deg, transparent, #000 20%)", WebkitMaskImage: "linear-gradient(180deg, transparent, #000 20%)" }}>
    {layers.map((w, i) => <div key={i} className="gpu" style={{ position: "absolute", left: 0, bottom: w.y, width: "200%", height: w.h, animation: `waveMove ${w.dur}s linear infinite`, filter: w.blur ? `blur(${w.blur}px)` : "none" }}>
      <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
        <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40 L1200,120 L0,120 Z" fill={w.fill} />
      </svg>
    </div>)}
    {/* 金色浪頂高光線 */}
    <div style={{ position: "absolute", left: 0, bottom: 158, width: "200%", height: 50, animation: "waveMove 15s linear infinite" }}>
      <svg viewBox="0 0 1200 120" preserveAspectRatio="none" style={{ width: "100%", height: "100%" }}>
        <path d="M0,40 C150,90 350,0 600,40 C850,80 1050,10 1200,40" fill="none" stroke="rgba(255,244,210,0.42)" strokeWidth="2" />
      </svg>
    </div>
  </div>;
}
function FloatCard({ sym, side, result, style, delay }) {
  return <div style={{ position: "absolute", padding: "11px 14px", borderRadius: 13, background: "rgba(6,16,30,0.72)", border: `1px solid ${C.lineGold}`, backdropFilter: "blur(8px)", animation: `drift ${7 + delay}s ease-in-out ${-delay}s infinite`, minWidth: 150, ...style }}>
    <Corner pos="tl" /><Corner pos="br" />
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
      <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 15, color: C.ink }}>{sym}</span>
      <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 99, color: side === "L" ? C.green : C.rose, background: (side === "L" ? C.green : C.rose) + "1A" }}>{side === "L" ? "做多" : "做空"}</span>
    </div>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
      <span style={{ fontFamily: MONO, fontSize: 12, color: C.dim, letterSpacing: 1 }}>$●●●.●</span>
      <span style={{ fontSize: 10, color: C.teal }}>🔒 {result}</span>
    </div>
  </div>;
}

function Hero() {
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const onMove = useCallback((e) => { const cx = window.innerWidth / 2, cy = window.innerHeight / 2; setMouse({ x: (e.clientX - cx) / cx, y: (e.clientY - cy) / cy }); }, []);
  const px = (f) => ({ transform: `translate(${mouse.x * f}px, ${mouse.y * f}px)`, transition: "transform .3s ease-out" });
  const wide = typeof window !== "undefined" && window.innerWidth >= 980;
  return <section onMouseMove={onMove} style={{ position: "relative", overflow: "hidden", minHeight: "100vh", display: "flex", alignItems: "center", background: `radial-gradient(1200px 700px at 72% 22%, rgba(19,53,90,0.55), transparent 55%), radial-gradient(900px 600px at 12% 82%, rgba(27,138,130,0.12), transparent 60%)` }}>
    <GodRays /><Lighthouse /><HeroWaves />
    {wide && <div style={{ position: "absolute", inset: 0, zIndex: 3, ...px(12) }}>
      <FloatCard sym="SOL" side="L" result="TP2 達標" delay={0} style={{ right: "10%", top: "26%" }} />
      <FloatCard sym="ETH" side="S" result="進行中" delay={2.5} style={{ right: "20%", top: "52%" }} />
      <FloatCard sym="BTC" side="L" result="TP1 達標" delay={1.2} style={{ right: "6%", top: "66%" }} />
    </div>}
    <div style={{ position: "relative", zIndex: 5, maxWidth: 1180, margin: "0 auto", padding: "40px 22px", width: "100%" }}>
      <div style={{ maxWidth: 720, ...px(-7) }}>
        <div className="reveal in" style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 28, padding: "7px 15px", borderRadius: 999, fontSize: 12.5, fontWeight: 600, color: C.gold, border: `1px solid ${C.gold}45`, background: `${C.gold}10`, backdropFilter: "blur(4px)" }}>
          <span style={{ width: 6, height: 6, borderRadius: 99, background: C.teal, boxShadow: `0 0 8px ${C.teal}`, animation: "pulseDot 2s infinite" }} />新用戶上船禮 · 免費送 3 日 Plus
        </div>
        <h1 className="reveal in" style={{ fontFamily: SANS, fontWeight: 800, lineHeight: 1.18, margin: 0, paddingTop: 4, fontSize: "clamp(42px,7.6vw,82px)", letterSpacing: "-1.5px", color: C.ink, animationDelay: ".08s", textShadow: "0 2px 40px rgba(0,0,0,.6)" }}>
          乘著<span className="teal-text">黑潮</span><br />比市場<span className="gold-text">早一步</span>
        </h1>
        <p className="reveal in" style={{ fontFamily: SANS, fontSize: "clamp(16px,2.1vw,20px)", lineHeight: 1.65, color: C.mut, margin: "26px 0 0", maxWidth: 500, animationDelay: ".18s" }}>
          黑潮船長 24 小時掃描 52 幣種，合格信號<span style={{ color: C.ink }}>即時送到你手機</span>。<br />你只需要上船。
        </p>
        <div className="reveal in" style={{ display: "flex", gap: 14, marginTop: 40, flexWrap: "wrap", alignItems: "center", animationDelay: ".28s" }}>
          <CTA big>免費上船 · 送 3 日 Plus</CTA>
          <button className="btn2" style={{ padding: "16px 26px", borderRadius: 13, fontSize: 15, fontWeight: 700, cursor: "pointer", color: C.mut, border: `1px solid ${C.line}`, background: "transparent", fontFamily: SANS }}>看黑潮怎麼運作 ↓</button>
        </div>
        <div className="reveal in" style={{ display: "flex", gap: 34, marginTop: 54, flexWrap: "wrap", animationDelay: ".4s" }}>
          {[["52", "監測幣種"], ["7+1", "策略投票"], ["24/7", "不間斷"]].map(([n, l], i) => <div key={l}><div style={{ fontFamily: MONO, fontSize: 28, fontWeight: 800, color: C.gold }}>{i === 0 ? <Counter to={52} /> : n}</div><div style={{ fontSize: 11.5, color: C.dim, marginTop: 2, letterSpacing: 1 }}>{l}</div></div>)}
        </div>
      </div>
    </div>
    <div style={{ position: "absolute", bottom: 22, left: "50%", transform: "translateX(-50%)", zIndex: 6, fontSize: 11, color: C.dim, textAlign: "center" }}>
      <div style={{ width: 1, height: 28, background: `linear-gradient(${C.gold2},transparent)`, margin: "0 auto 6px", animation: "glowPulse 2s infinite" }} />SCROLL
    </div>
  </section>;
}

function Ticker() {
  const [coins, setCoins] = useState([["BTC", 67420, -2.35], ["ETH", 3248, -3.18], ["SOL", 165.4, 1.82], ["BNB", 612.8, -2.02], ["XRP", 0.624, -3.11], ["AVAX", 28.4, 2.1], ["LINK", 14.2, -1.4], ["DOGE", 0.142, 3.2], ["ARB", 0.92, -2.8], ["OP", 1.74, 1.1]]);
  useEffect(() => { const iv = setInterval(() => setCoins((cs) => cs.map(([s, p, c]) => [s, p + (Math.random() - 0.5) * p * 0.001, +(c + (Math.random() - 0.5) * 0.05).toFixed(2)])), 1600); return () => clearInterval(iv); }, []);
  const fmt = (p) => p >= 1000 ? p.toLocaleString("en-US", { maximumFractionDigits: 0 }) : p >= 1 ? p.toFixed(2) : p.toFixed(3);
  const row = (k) => coins.map(([s, p, c], i) => <span key={k + i} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "0 22px" }}>
    <span style={{ fontFamily: MONO, fontWeight: 700, fontSize: 13, color: C.ink }}>{s}</span>
    <span style={{ fontFamily: MONO, fontSize: 13, color: C.mut }}>${fmt(p)}</span>
    <span style={{ fontFamily: MONO, fontSize: 12, color: c >= 0 ? C.green : C.rose }}>{c >= 0 ? "▲" : "▼"}{Math.abs(c)}%</span>
  </span>);
  return <div style={{ ...veil(0.85), borderTop: `1px solid ${C.lineGold}`, borderBottom: `1px solid ${C.lineGold}`, overflow: "hidden", padding: "12px 0", position: "relative", zIndex: 2 }}>
    <div style={{ display: "flex", width: "200%", animation: "waveMove 30s linear infinite", whiteSpace: "nowrap" }}>
      <div style={{ flex: 1 }}>{row("a")}</div><div style={{ flex: 1 }}>{row("b")}</div>
    </div>
  </div>;
}

const POOL = [
  ["SOL", "L", "TP2 達標", 1, "高品質", "138.20", "+4.8%"], ["ETH", "S", "進行中", 0, "一般", "", ""], ["BTC", "L", "TP1 達標", 1, "高品質", "64,200", "+2.1%"], ["AVAX", "L", "進行中", 0, "一般", "", ""],
  ["LINK", "S", "止損出場", -1, "一般", "14.85", "-1.2%"], ["ARB", "L", "止損出場", -1, "一般", "0.952", "-1.8%"], ["DOGE", "S", "進行中", 0, "一般", "", ""], ["OP", "L", "TP3 達標", 1, "高品質", "1.620", "+6.5%"],
  ["SUI", "S", "進行中", 0, "一般", "", ""], ["NEAR", "L", "止損出場", -1, "一般", "5.100", "-0.9%"], ["INJ", "L", "TP2 達標", 1, "高品質", "21.30", "+3.0%"], ["TIA", "S", "進行中", 0, "一般", "", ""],
];
function SignalShowcase() {
  const ref = useReveal();
  const [feed, setFeed] = useState(() => POOL.slice(0, 6).map((s, i) => ({ s, id: i })));
  const [count, setCount] = useState(8);
  const idx = useRef(6); const nid = useRef(100);
  useEffect(() => { const iv = setInterval(() => { const s = POOL[idx.current % POOL.length]; idx.current++; setFeed((f) => [{ s, id: nid.current++ }, ...f].slice(0, 6)); setCount((c) => c + 1); }, 2400); return () => clearInterval(iv); }, []);
  return <section ref={ref} style={{ ...veil(0.42), padding: "90px 22px", position: "relative", overflow: "hidden" }}>
    <SoftRays />
    <div className="ghost" style={{ position: "absolute", top: 10, right: -20, fontSize: "clamp(110px,20vw,240px)", opacity: 0.5, zIndex: 0 }}>LIVE</div>
    <div style={{ maxWidth: 1180, margin: "0 auto", position: "relative", zIndex: 1 }}>
      <div className="reveal" style={{ textAlign: "center", marginBottom: 12 }}>
        <div style={{ fontSize: 12, letterSpacing: 4, color: C.gold2, fontWeight: 700, marginBottom: 14, display: "inline-flex", alignItems: "center", gap: 8 }}><span style={{ width: 7, height: 7, borderRadius: 99, background: C.green, boxShadow: `0 0 8px ${C.green}`, animation: "pulseDot 1.4s infinite" }} />LIVE · 信號即時送出</div>
        <h2 style={{ fontFamily: SANS, fontSize: "clamp(30px,5vw,52px)", fontWeight: 800, color: C.ink, margin: 0, letterSpacing: "-1.5px", lineHeight: 1.05 }}>這就是黑潮船長<br /><span className="gold-text">每天在做的事</span></h2>
        <p style={{ color: C.mut, fontSize: 15.5, marginTop: 16, maxWidth: 480, margin: "16px auto 0", lineHeight: 1.6 }}>已達標訊號<span style={{ color: C.ink }}>公開真實進場價與結果</span>。進行中與最新訊號，上船解鎖。</p>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", gap: 12, margin: "30px 0 24px" }}>
        <span style={{ fontFamily: MONO, fontSize: 52, fontWeight: 800, color: C.gold, lineHeight: 1, textShadow: `0 0 30px ${C.gold}55` }}>{count}</span>
        <span style={{ fontSize: 14, color: C.dim }}>個信號 · 今日已送出</span>
      </div>
      <div className="reveal" style={{ maxWidth: 560, margin: "0 auto", borderRadius: 20, padding: 20, position: "relative", overflow: "hidden", background: "linear-gradient(180deg, rgba(16,30,48,0.9), rgba(6,16,30,0.78))", border: `1px solid ${C.lineGold}`, boxShadow: "0 20px 60px rgba(0,0,0,.4)" }}>
        <div className="scanline" />
        <Corner pos="tl" /><Corner pos="tr" /><Corner pos="bl" /><Corner pos="br" />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, position: "relative", zIndex: 1 }}>
          <span style={{ fontSize: 11, letterSpacing: 2, color: C.dim }}>● 黑潮信號流</span>
          <span style={{ fontSize: 11, color: C.teal, display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 5, height: 5, borderRadius: 99, background: C.teal, boxShadow: `0 0 6px ${C.teal}`, animation: "pulseDot 1.4s infinite" }} />即時接收中</span>
        </div>
        {feed.map(({ s, id }, ri) => { const [sym, side, result, pos, grade, entry, gain] = s; const sc = side === "L" ? C.green : C.rose; const locked = pos === 0 || ri === 0; const dispResult = ri === 0 ? "最新送出" : result; const win = pos === 1; return <div key={id} className="sigrow" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 8px 13px 14px", borderBottom: `1px solid ${C.line}`, animation: ri === 0 ? "feedIn .5s ease-out, newFlash 1.6s ease-out" : "feedIn .5s ease-out" }}>
          <span className="accent-bar" style={{ background: `linear-gradient(${sc},transparent)`, boxShadow: `0 0 6px ${sc}` }} />
          <div className="row-sweep" />
          <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative", zIndex: 1, minWidth: 0 }}>
            <span style={{ fontFamily: MONO, fontWeight: 800, fontSize: 16, color: C.ink, width: 46 }}>{sym}</span>
            <span style={{ fontSize: 10, fontWeight: 700, padding: "3px 9px", borderRadius: 99, color: sc, background: sc + "1A" }}>{side === "L" ? "做多" : "做空"}</span>
            <span className="grade-pill" style={{ fontSize: 9.5, fontWeight: 700, padding: "2px 7px", borderRadius: 6, color: grade === "高品質" ? C.gold : C.dim, border: `1px solid ${grade === "高品質" ? C.gold + "55" : C.line}`, whiteSpace: "nowrap" }}>{grade}</span>
          </div>
          {locked ? (
            <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative", zIndex: 1 }}>
              <span className="sig-time" style={{ fontSize: 9.5, color: ri === 0 ? C.teal : C.dim, whiteSpace: "nowrap", fontWeight: ri === 0 ? 700 : 400 }}>{ri === 0 ? "● 剛剛" : "進行中"}</span>
              <span className="locked-px" style={{ fontFamily: MONO, fontSize: 13, letterSpacing: 2, userSelect: "none" }}>$●●●.●●</span>
              <span style={{ fontSize: 11.5, color: C.gold2, minWidth: 56, textAlign: "right", whiteSpace: "nowrap" }}>{dispResult}</span>
              <span style={{ fontSize: 13 }}>🔒</span>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 9, position: "relative", zIndex: 1 }}>
              <span className="sig-time" style={{ fontFamily: MONO, fontSize: 11, color: C.dim, whiteSpace: "nowrap" }}>${entry}</span>
              <span style={{ fontSize: 11, color: win ? C.green : C.rose, whiteSpace: "nowrap" }}>{result}</span>
              <span style={{ fontFamily: MONO, fontSize: 13.5, fontWeight: 800, color: win ? C.green : C.rose, minWidth: 52, textAlign: "right" }}>{gain}</span>
            </div>
          )}
        </div>; })}
        <div style={{ marginTop: 14, textAlign: "center", position: "relative", zIndex: 1 }}><CTA>免費上船 · 解鎖進場價位</CTA></div>
      </div>
    </div>
  </section>;
}

function Statement() {
  const ref = useReveal();
  const bubbles = useRef(Array.from({ length: 16 }, () => ({ left: 5 + Math.random() * 90, size: 3 + Math.random() * 7, dur: 5 + Math.random() * 6, delay: -Math.random() * 8, teal: Math.random() < 0.5 }))).current;
  return <section ref={ref} style={{ ...veil(0.46), padding: "130px 22px 150px", position: "relative", overflow: "hidden", textAlign: "center" }}>
    {/* 底部升起的光 */}
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "60%", background: "radial-gradient(ellipse at 50% 100%, rgba(232,198,110,0.22), rgba(27,138,130,0.1) 40%, transparent 70%)", animation: "risingGlow 6s ease-in-out infinite", pointerEvents: "none" }} />
    {/* 掃光束橫掃 */}
    <div style={{ position: "absolute", top: "10%", left: "-10%", width: "60%", height: "80%", background: "linear-gradient(100deg, transparent, rgba(232,198,110,.08) 50%, transparent)", transform: "skewX(-12deg)", animation: "rayShift 8s ease-in-out infinite", pointerEvents: "none" }} />

    {/* 多重聲納漣漪（金+綠交替，更大更多） */}
    {[0, 1, 2, 3, 4].map((i) => <div key={i} style={{ position: "absolute", top: "42%", left: "50%", width: 180 + i * 150, height: 180 + i * 150, marginLeft: -(90 + i * 75), marginTop: -(90 + i * 75), borderRadius: "50%", border: `1.5px solid ${i % 2 ? C.teal : C.gold}`, opacity: 0.16, animation: `sonarPing 5s ease-out ${i * 1}s infinite` }} />)}

    {/* 上升氣泡 */}
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      {bubbles.map((b, i) => <div key={i} style={{ position: "absolute", left: b.left + "%", bottom: 40, width: b.size, height: b.size, borderRadius: "50%", background: b.teal ? C.teal : C.gold, boxShadow: `0 0 ${b.size * 2.5}px ${b.teal ? C.teal : C.gold}`, animation: `riseUp ${b.dur}s ease-in ${b.delay}s infinite`, opacity: 0.7 }} />)}
    </div>

    <div className="reveal" style={{ position: "relative", zIndex: 2, maxWidth: 820, margin: "0 auto" }}>
      <div style={{ fontSize: 13, letterSpacing: 5, color: C.tealDk, fontWeight: 700, marginBottom: 26 }}>WHY BLACK TIDE</div>
      <h2 style={{ fontFamily: SANS, fontSize: "clamp(28px,5.2vw,52px)", fontWeight: 800, color: C.ink, margin: 0, lineHeight: 1.3, letterSpacing: "-0.5px", textShadow: "0 0 50px rgba(232,198,110,.25)" }}>
        太平洋最強的洋流，<br />從不喧嘩，<span className="teal-text" style={{ textShadow: "0 0 30px rgba(55,214,196,.5)" }}>卻推動整片海</span>。
      </h2>
      <p style={{ fontSize: "clamp(17px,2.4vw,22px)", fontWeight: 700, color: C.gold, margin: "28px 0 0", letterSpacing: 1, textShadow: "0 0 24px rgba(232,198,110,.4)" }}>
        市場變盤前，黑潮先到。
      </p>
      <p style={{ fontSize: 16, color: C.mut, margin: "10px 0 0" }}>你，要不要在船上？</p>

      {/* CTA + 爆發脈衝 */}
      <div style={{ position: "relative", marginTop: 48, display: "inline-block" }}>
        <div style={{ position: "absolute", top: "50%", left: "50%", width: 260, height: 260, borderRadius: "50%", background: "radial-gradient(circle, rgba(232,198,110,.3), transparent 70%)", animation: "burstPulse 2.4s ease-out infinite", pointerEvents: "none" }} />
        <div style={{ position: "absolute", top: "50%", left: "50%", width: 260, height: 260, borderRadius: "50%", background: "radial-gradient(circle, rgba(55,214,196,.2), transparent 70%)", animation: "burstPulse 2.4s ease-out 1.2s infinite", pointerEvents: "none" }} />
        <button className="cta-big" style={{ position: "relative", zIndex: 1, padding: "19px 50px", borderRadius: 15, fontSize: 19, fontWeight: 800, cursor: "pointer", color: C.abyss, border: "none", fontFamily: SANS, background: `linear-gradient(135deg,#FFF4D2,${C.gold} 45%,${C.gold2})` }}>免費上船 · 送 3 日 Plus</button>
      </div>
      <div style={{ fontSize: 12.5, color: C.dim, marginTop: 18 }}>不需信用卡 · 隨時可取消</div>
    </div>
  </section>;
}
/* ====== 法律文件內容（自製繁中版，可替換成官方版本）====== */
const LEGAL_DOCS = {
  terms: {
    title: "服務條款", updated: "最後更新：2026 年",
    sections: [
      ["一、服務說明", "黑潮 BLACKTIDE（以下稱「本平台」）提供加密貨幣市場行情、技術分析、交易訊號與新聞資訊等服務（以下稱「本服務」）。本服務所提供之一切內容僅供研究與教育參考，不構成任何投資建議、招攬或要約。"],
      ["二、帳號與註冊", "您於註冊時應提供正確、完整之資料，並妥善保管您的帳號與密碼。您須對該帳號下之一切活動負責。如發現帳號遭未經授權使用，請立即通知本平台。"],
      ["三、使用規範", "您同意不以任何自動化程式大量擷取本服務內容，不對本服務進行逆向工程，亦不得轉售、散布或公開本平台之訊號與分析內容予未經授權之第三方。違反者本平台得暫停或終止其帳號。"],
      ["四、訂閱與付費", "本平台提供免費與付費方案。新用戶得享有限期 Plus 試用，試用到期後若未訂閱，將自動回復為免費權限，不會自動扣款。各方案之功能與費用以本平台公告為準。"],
      ["五、智慧財產權", "本平台之商標、介面、程式、分析方法與內容之著作權及其他智慧財產權，均屬本平台或其授權人所有。未經書面同意，您不得重製、修改或為商業利用。"],
      ["六、服務變更與終止", "本平台得隨時新增、修改、暫停或終止全部或部分服務，無須事前個別通知。因服務調整所生之任何損失，本平台不負賠償責任。"],
      ["七、責任限制", "於法律允許之最大範圍內，本平台對於您使用或無法使用本服務所生之任何直接、間接、附隨或衍生之損失，不負任何責任。"],
      ["八、條款修改", "本平台得不定期修改本條款，並公告於本頁面。若您於修改後繼續使用本服務，視為同意修改後之條款。"],
    ],
  },
  disclaimer: {
    title: "免責聲明", updated: "最後更新：2026 年",
    sections: [
      ["一、非投資建議", "本平台提供之所有行情、技術分析、五維評分、交易訊號與新聞資訊，均僅供研究與教育參考，不構成投資建議、財務建議或任何買賣之要約或招攬。"],
      ["二、自負盈虧", "您應就自身之財務狀況與風險承受能力，獨立判斷並自行決定任何交易行為。一切交易之盈虧與後果，概由您自行承擔，與本平台無涉。"],
      ["三、不保證準確性", "本平台雖力求資訊正確，但不保證其行情、分析或訊號之即時性、準確性、完整性或可靠性。資料可能因延遲、來源錯誤或系統因素而與實際情況不符。"],
      ["四、第三方資料", "本平台部分資料來自 Bybit、CoinGecko 等第三方來源。本平台不對第三方資料之正確性負責，亦不對因第三方服務中斷所生之損失負責。"],
      ["五、過往表現", "任何歷史數據或過往訊號表現，均不代表未來結果。加密貨幣市場波動劇烈，過去之績效不應作為未來獲利之保證或預期依據。"],
    ],
  },
  privacy: {
    title: "隱私權政策", updated: "最後更新：2026 年",
    sections: [
      ["一、蒐集之資料", "本平台於您註冊與使用本服務時，可能蒐集您的電子郵件地址、帳號設定、使用紀錄（如功能點擊、登入時間）、裝置與瀏覽器資訊及 IP 位址等。"],
      ["二、利用目的", "所蒐集之資料用於：提供與維護本服務、驗證您的身分、避免未經授權之使用、改善與優化服務、提供客戶支援，以及於必要時與您聯繫重要服務資訊。"],
      ["三、資料分享", "除經您同意或基於法律規定外，本平台不會將您的個人資料提供予第三方。本平台可能與協助提供服務之供應商合作，並要求其依本政策與相關法律處理您的資料。"],
      ["四、Cookie", "為提供最佳體驗並維護服務安全，本平台可能使用 Cookie 記錄您的設定與使用狀態。您可透過瀏覽器設定停用 Cookie，但可能影響部分功能。"],
      ["五、資料安全", "本平台採取合理之技術與管理措施保護您的個人資料，防止未經授權之存取、竄改或洩漏。惟網路傳輸無法保證絕對安全，您須自行承擔傳輸風險。"],
      ["六、您的權利", "您得隨時查詢、閱覽、更正或請求刪除您的個人資料，亦得請求停止蒐集、處理或利用。行使權利請透過本平台所提供之聯繫方式辦理。"],
      ["七、政策修改", "本平台得不定期修改本政策並公告於本頁面。若您於修改後繼續使用本服務，視為同意修改後之內容。"],
    ],
  },
  risk: {
    title: "風險揭露聲明", updated: "最後更新：2026 年",
    sections: [
      ["一、市場波動風險", "加密貨幣為高度波動之資產，價格可能於短時間內大幅漲跌，您可能因此承受重大損失。投資前請充分了解相關風險。"],
      ["二、槓桿風險", "槓桿交易會放大獲利與虧損。在極端行情下，您的損失可能超過初始投入之本金，甚至導致全部資金歸零。請審慎評估後再行使用。"],
      ["三、訊號風險", "本平台之交易訊號係基於技術指標與機率模型產生，並非獲利保證。任何策略都可能出現連續虧損，訊號之結果具有不確定性。"],
      ["四、流動性與技術風險", "部分加密資產流動性不足，可能難以於理想價位成交。交易所、網路或系統亦可能發生中斷、延遲或故障，進而影響您的交易。"],
      ["五、監管風險", "各國對加密貨幣之法律與監管政策仍在變動中，相關規範之改變可能影響資產之價值、流通性或合法性。"],
      ["六、量力而為", "您應僅以可承受全部損失之閒置資金參與加密貨幣交易，切勿使用借貸、生活必需或緊急備用之資金。如有需要，請諮詢專業財務顧問。"],
    ],
  },
};

function LegalModal({ docKey, onClose }) {
  const doc = docKey ? LEGAL_DOCS[docKey] : null;
  useEffect(() => {
    if (!docKey) return;
    const onEsc = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [docKey, onClose]);
  if (!doc) return null;
  return <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, background: "rgba(2,4,9,0.7)", backdropFilter: "blur(5px)", animation: "fadeIn .25s" }}>
    <div onClick={(e) => e.stopPropagation()} style={{ position: "relative", width: "100%", maxWidth: 640, maxHeight: "84vh", display: "flex", flexDirection: "column", borderRadius: 20, background: "linear-gradient(180deg, rgba(10,20,34,0.98), rgba(4,9,16,0.98))", border: `1px solid ${C.lineGold}`, boxShadow: "0 30px 80px rgba(0,0,0,.6)", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${C.gold}, ${C.teal}, transparent)` }} />
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 24px", borderBottom: `1px solid ${C.line}`, flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <LogoMark size={36} />
          <div>
            <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 18, color: C.ink, letterSpacing: 1 }}>{doc.title}</div>
            <div style={{ fontSize: 10.5, color: C.dim, marginTop: 2 }}>{doc.updated}</div>
          </div>
        </div>
        <div onClick={onClose} className="ham" style={{ width: 36, height: 36, borderRadius: 10, border: `1px solid ${C.line}`, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flexShrink: 0 }}><X size={18} color={C.mut} /></div>
      </div>
      {/* body */}
      <div style={{ overflowY: "auto", padding: "20px 24px 28px" }}>
        {doc.sections.map(([h, p], i) => <div key={i} style={{ marginBottom: 20 }}>
          <h3 style={{ fontFamily: SANS, fontSize: 14.5, fontWeight: 800, color: C.gold, margin: "0 0 8px" }}>{h}</h3>
          <p style={{ fontSize: 13.5, lineHeight: 1.85, color: "#B9C7D2", margin: 0 }}>{p}</p>
        </div>)}
        <div style={{ marginTop: 8, paddingTop: 16, borderTop: `1px solid ${C.line}`, fontSize: 11.5, color: C.dim, lineHeight: 1.7 }}>
          本文件為平台服務說明之一部分。加密貨幣與槓桿商品風險極高，請自負盈虧。
        </div>
      </div>
    </div>
  </div>;
}


function Footer({ onLegal }) {
  const legal = [["服務條款", "terms"], ["免責聲明", "disclaimer"], ["隱私權政策", "privacy"], ["風險揭露聲明", "risk"]];
  return <footer style={{ borderTop: `1px solid ${C.line}`, padding: "48px 22px 42px", ...veil(0.9), position: "relative", zIndex: 2 }}>
    <div style={{ maxWidth: 1180, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 24, paddingBottom: 24, borderBottom: `1px solid ${C.line}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <LogoMark size={42} />
          <div>
            <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 16, letterSpacing: 1, color: C.ink }}>黑潮 BLACKTIDE</div>
            <div style={{ fontFamily: SERIF, fontSize: 9, letterSpacing: 2.5, color: C.gold2 }}>SIGNALS · PRO TERMINAL</div>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "12px 24px", alignItems: "center" }}>
          {legal.map(([t, k]) => <span key={t} onClick={() => onLegal(k)} className="login-link" style={{ fontSize: 13, fontWeight: 600, color: C.mut, cursor: "pointer", whiteSpace: "nowrap" }}>{t}</span>)}
        </div>
      </div>
      <div style={{ fontSize: 11.5, color: C.dim, lineHeight: 1.85, marginTop: 22, maxWidth: 780 }}>
        © 2026 黑潮 BLACKTIDE。本平台提供之行情、分析與訊號僅供研究與教育參考，不構成投資建議或要約。加密貨幣與槓桿商品風險極高，請自負盈虧。
      </div>
    </div>
  </footer>;
}

export default function BlackTideLandingV8() {
  const [menu, setMenu] = useState(false);
  const [legal, setLegal] = useState(null);
  return <div className="bt" style={{ background: C.abyss, color: C.ink, fontFamily: SANS, minHeight: "100vh", position: "relative" }}>
    <style>{CSS}</style>
    <GlobalCurrent />
    <Plankton count={30} />
    <ScrollBar />
    <Drawer open={menu} onClose={() => setMenu(false)} />
    <LegalModal docKey={legal} onClose={() => setLegal(null)} />
    <div style={{ position: "relative", zIndex: 2 }}>
      <Nav onMenu={() => setMenu(true)} />
      <Hero />
      <Ticker />
      <SignalShowcase />
      <Statement />
      <Footer onLegal={setLegal} />
    </div>
  </div>;
}