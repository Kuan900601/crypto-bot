"use client";
import { useEffect, useRef, useState } from "react";

const THRESHOLD = 70;
const MAX_PULL = 110;

/** 行動版下拉刷新手勢。純 touch 事件，桌機（無 touch）完全不掛監聽，零開銷。
 *  監聽掛在最近的 <main>（Shell.tsx 裡唯一的滾動容器），只在捲到頂端時才攔截下拉手勢，
 *  不影響一般往下滑動瀏覽。回傳 pullDistance/refreshing 給呼叫端自己畫指示器。 */
export function usePullToRefresh(onRefresh: () => void | Promise<void>) {
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const dragging = useRef(false);
  const pullRef = useRef(0);
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    if (typeof window === "undefined" || !("ontouchstart" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const main = document.querySelector("main");
    if (!main) return;

    const onTouchStart = (e: TouchEvent) => {
      if (main.scrollTop > 4) { dragging.current = false; return; }
      startY.current = e.touches[0].clientY;
      dragging.current = true;
    };
    const onTouchMove = (e: TouchEvent) => {
      if (!dragging.current || startY.current == null) return;
      if (main.scrollTop > 4) { dragging.current = false; setPullDistance(0); pullRef.current = 0; return; }
      const delta = e.touches[0].clientY - startY.current;
      const next = delta > 0 ? Math.min(MAX_PULL, delta * 0.5) : 0;
      pullRef.current = next;
      setPullDistance(next);
    };
    const onTouchEnd = async () => {
      if (!dragging.current) return;
      dragging.current = false;
      startY.current = null;
      if (pullRef.current >= THRESHOLD) {
        setRefreshing(true);
        try { await onRefreshRef.current(); } finally { setRefreshing(false); }
      }
      pullRef.current = 0;
      setPullDistance(0);
    };
    main.addEventListener("touchstart", onTouchStart, { passive: true });
    main.addEventListener("touchmove", onTouchMove, { passive: true });
    main.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      main.removeEventListener("touchstart", onTouchStart);
      main.removeEventListener("touchmove", onTouchMove);
      main.removeEventListener("touchend", onTouchEnd);
    };
  }, []);

  return { pullDistance, refreshing, threshold: THRESHOLD };
}
