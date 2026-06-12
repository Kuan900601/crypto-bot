"use client";

import { useEffect, useRef, useState } from "react";

// 輪詢式取資料：定時 refetch（預設 15 秒），SSR 安全。
export function useFetch<T>(url: string, intervalMs = 15000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    async function tick() {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const j = (await res.json()) as T;
        if (mounted.current) {
          setData(j);
          setError(null);
        }
      } catch (e) {
        if (mounted.current) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (mounted.current) setLoading(false);
      }
    }
    tick();
    const id = intervalMs > 0 ? setInterval(tick, intervalMs) : undefined;
    return () => {
      mounted.current = false;
      if (id) clearInterval(id);
    };
  }, [url, intervalMs]);

  return { data, error, loading };
}
