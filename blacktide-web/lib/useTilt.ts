"use client";
import { useEffect, useRef } from "react";

/** 桌機滑鼠卡片 3D 傾斜：perspective + rotateX/Y，幅度 ±maxDeg。
 *  用 matchMedia(hover:hover)+(pointer:fine) 排除觸控裝置，完全不掛 touch 事件，不吃手機效能。
 *  尊重 prefers-reduced-motion。 */
export function useTilt<T extends HTMLElement>(maxDeg = 6) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      const rx = (0.5 - py) * maxDeg * 2;
      const ry = (px - 0.5) * maxDeg * 2;
      el.style.transform = `perspective(900px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
    };
    const onLeave = () => { el.style.transform = "perspective(900px) rotateX(0deg) rotateY(0deg)"; };
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [maxDeg]);
  return ref;
}
