"use client";
import { useEffect, useRef, useState } from "react";

/** 進入可視範圍時，數字從 0 滾到 to。給 Hero 統計數字用。
 *  正確性保底：動畫只是加分項——IO 沒觸發（舊瀏覽器/省電模式/hydration 延遲）
 *  或 prefers-reduced-motion 時，直接顯示最終值，絕不讓真實數字卡在 0。 */
export default function Counter({ to, dur = 1400 }: { to: number; dur?: number }) {
  const [v, setV] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const done = useRef(false);
  useEffect(() => {
    done.current = false; // to 變化時（如非同步資料載入後）允許重新執行
    const el = ref.current;
    const finish = () => { done.current = true; setV(to); };
    if (!el || typeof IntersectionObserver === "undefined" ||
        (typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      finish();
      return;
    }
    setV(0);
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
    }, { threshold: 0.1 });
    io.observe(el);
    // 保底：2 秒內動畫沒被觸發就直接顯示最終值
    const fallback = setTimeout(() => { if (!done.current) finish(); }, 2000);
    return () => { io.disconnect(); clearTimeout(fallback); };
  }, [to, dur]);
  return <span ref={ref}>{v}</span>;
}
