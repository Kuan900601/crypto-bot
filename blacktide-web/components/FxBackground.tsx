"use client";
import { useEffect, useRef } from "react";
export default function FxBackground() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let w = (cv.width = window.innerWidth);
    let h = (cv.height = window.innerHeight);
    let raf = 0;
    const N = 70;
    const pts = Array.from({ length: N }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
    }));
    const onResize = () => { w = cv.width = window.innerWidth; h = cv.height = window.innerHeight; };
    window.addEventListener("resize", onResize);
    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "rgba(212,175,55,0.4)";
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        ctx.fillRect(p.x, p.y, 1.4, 1.4);
      }
      ctx.strokeStyle = "rgba(212,175,55,0.06)";
      for (let i = 0; i < N; i++) for (let k = i + 1; k < N; k++) {
        const a = pts[i], b = pts[k], dx = a.x - b.x, dy = a.y - b.y;
        if (dx * dx + dy * dy < 12100) {
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); };
  }, []);
  return <canvas ref={ref} className="pointer-events-none fixed inset-0 -z-10 opacity-60" />;
}
