"use client";
import { useEffect, useRef, useState } from "react";

/** 進入可視範圍時，數字從 0 滾到 to。給 Hero 統計數字用。 */
export default function Counter({ to, dur = 1400 }: { to: number; dur?: number }) {
  const [v, setV] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const done = useRef(false);
  useEffect(() => {
    done.current = false; // to 變化時（如非同步資料載入後）允許動畫重新執行
    setV(0);
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => {
      if (es[0].isIntersecting && !done.current) {
        done.current = true;
        const t0 = performance.now();
        const tick = (t: number) => {
          const p = Math.min(1, (t - t0) / dur);
          setV(Math.round(to * (1 - Math.pow(1 - p, 3))));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, [to, dur]);
  return <span ref={ref}>{v}</span>;
}
