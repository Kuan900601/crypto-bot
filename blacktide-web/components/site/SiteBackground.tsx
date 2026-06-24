"use client";
import { useEffect, useRef, useState } from "react";
import { C } from "@/lib/theme";

/** 全頁洋流粒子背景（取代 FxBackground，全站僅掛載一次，包在 layout 裡）。
 *  手機降載：dpr<=1.4、粒子數減半；分頁切走時暫停 rAF；尊重 prefers-reduced-motion。 */
function GlobalCurrent() {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef(0);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const mobile = window.innerWidth < 768;
    let W = 0, H = 0;
    const dpr = Math.min(mobile ? 1.4 : 2, window.devicePixelRatio || 1);
    const resize = () => {
      W = window.innerWidth; H = window.innerHeight;
      cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + "px"; cv.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);
    const N = Math.min(mobile ? 90 : 180, Math.floor(W / (mobile ? 9 : 7)));
    const parts = Array.from({ length: N }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      sp: 0.5 + Math.random() * 1.3,
      hue: Math.random() < 0.72 ? "g" : "t",
      a: 0.3 + Math.random() * 0.55,
    }));
    // 點按/觸碰漣漪：上限數量，隱藏分頁時不累積（running=false 時不繪製）
    const MAX_RIPPLES = mobile ? 4 : 7;
    const ripples: { x: number; y: number; born: number }[] = [];
    const addRipple = (x: number, y: number) => {
      ripples.push({ x, y, born: performance.now() });
      if (ripples.length > MAX_RIPPLES) ripples.shift();
    };
    const onPointer = (e: PointerEvent) => addRipple(e.clientX, e.clientY);
    window.addEventListener("pointerdown", onPointer);
    const field = (x: number, y: number, t: number) => {
      const s = 0.0015;
      // 緩慢水波扭曲：再疊一層極低頻、大波長的相位偏移，模擬整體水面慢速起伏
      const swell = Math.sin(x * 0.0006 + t * 8e-5) * Math.cos(y * 0.0006 - t * 6e-5) * 0.35;
      return (Math.sin(x * s + t * 3e-4) * 0.8 + Math.cos(y * s * 1.4 - t * 4e-4) * 0.7 + Math.sin((x + y) * s * 0.6 + t * 2e-4) * 0.5) * 0.9 - 0.15 + swell;
    };
    let t0 = performance.now();
    let running = true;
    const RIPPLE_LIFE = 1400, RIPPLE_MAX_R = mobile ? 90 : 140;
    const draw = (t: number) => {
      if (!running) return;
      const dt = Math.min(40, t - t0); t0 = t;
      ctx.fillStyle = "rgba(3,6,14,0.085)";
      ctx.fillRect(0, 0, W, H);
      for (const p of parts) {
        const a = field(p.x, p.y, t), vx = Math.cos(a) * p.sp, vy = Math.sin(a) * p.sp - 0.25;
        const nx = p.x + vx * dt * 0.06, ny = p.y + vy * dt * 0.06;
        ctx.strokeStyle = p.hue === "g" ? `rgba(235,200,115,${p.a})` : `rgba(70,224,205,${p.a})`;
        ctx.lineWidth = p.hue === "g" ? 1.8 : 1.4;
        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); ctx.stroke();
        p.x = nx; p.y = ny;
        if (p.x < -20 || p.x > W + 20 || p.y < -20 || p.y > H + 20) { p.x = Math.random() * W * 0.4 - 20; p.y = H * 0.3 + Math.random() * H * 0.7; }
      }
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i];
        const age = t - r.born;
        if (age > RIPPLE_LIFE) { ripples.splice(i, 1); continue; }
        const k = age / RIPPLE_LIFE;
        const rad = k * RIPPLE_MAX_R;
        ctx.strokeStyle = `rgba(70,224,205,${0.32 * (1 - k)})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(r.x, r.y, rad, 0, Math.PI * 2); ctx.stroke();
      }
      raf.current = requestAnimationFrame(draw);
    };
    raf.current = requestAnimationFrame(draw);
    const onVis = () => {
      if (document.hidden) { running = false; cancelAnimationFrame(raf.current); }
      else if (!running) { running = true; t0 = performance.now(); raf.current = requestAnimationFrame(draw); }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      running = false;
      cancelAnimationFrame(raf.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", inset: 0, width: "100%", height: "100%", zIndex: -20, pointerEvents: "none", willChange: "transform", transform: "translateZ(0)" }} />;
}

function Plankton({ count = 24 }: { count?: number }) {
  const dots = useRef(Array.from({ length: count }, () => ({
    left: Math.random() * 100, top: Math.random() * 100,
    size: 2 + Math.random() * 3, dur: 7 + Math.random() * 11, delay: -Math.random() * 12,
    teal: Math.random() < 0.5,
  }))).current;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: -20, overflow: "hidden", pointerEvents: "none" }}>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: "absolute", left: d.left + "%", top: d.top + "%", width: d.size, height: d.size,
          borderRadius: "50%", background: d.teal ? C.teal : C.gold,
          boxShadow: `0 0 ${d.size * 4}px ${d.teal ? C.teal : C.gold}`,
          animation: `bob ${d.dur}s ease-in-out ${d.delay}s infinite, glowPulse ${d.dur * 0.6}s ease-in-out ${d.delay}s infinite`,
          opacity: 0.75,
        }} />
      ))}
    </div>
  );
}

function ScrollBar() {
  const [p, setP] = useState(0);
  useEffect(() => {
    const on = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      setP(h > 0 ? window.scrollY / h : 0);
    };
    window.addEventListener("scroll", on, { passive: true });
    on();
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <div style={{ position: "fixed", top: 0, left: 0, right: 0, height: 2.5, zIndex: 100 }}>
      <div style={{ height: "100%", width: p * 100 + "%", background: `linear-gradient(90deg,${C.teal},${C.gold})`, boxShadow: `0 0 10px ${C.gold}`, transition: "width .1s" }} />
    </div>
  );
}

export default function SiteBackground() {
  return (
    <>
      <GlobalCurrent />
      <Plankton />
      <ScrollBar />
    </>
  );
}
