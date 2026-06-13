"use client";
import { useEffect, useRef, useState } from "react";
import { Ticker, MarketStats } from "./types";
import { COINS, BYBIT_WS } from "./bybit";
export function useMarket() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [src, setSrc] = useState<{ crypto: string; stocks: string }>({ crypto: "mock", stocks: "demo" });
  const live = useRef<Record<string, { price?: number; pct?: number }>>({});
  useEffect(() => {
    let stop = false;
    const load = () =>
      fetch("/api/market").then((r) => r.json()).then((d) => {
        if (stop) return;
        setTickers(d.tickers); setStats(d.stats);
        if (d.source) setSrc(d.source);
      }).catch(() => {});
    load();
    const poll = setInterval(load, 60000);
    return () => { stop = true; clearInterval(poll); };
  }, []);
  useEffect(() => {
    let ws: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let dead = false;
    const connect = () => {
      try { ws = new WebSocket(BYBIT_WS); } catch { return; }
      ws.onopen = () => {
        ws?.send(JSON.stringify({ op: "subscribe", args: COINS.map((c) => "tickers." + c.bybit) }));
        ping = setInterval(() => { if (ws?.readyState === 1) ws.send(JSON.stringify({ op: "ping" })); }, 20000);
      };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data as string);
          if (!m.topic || !String(m.topic).startsWith("tickers.")) return;
          const c = COINS.find((x) => x.bybit === m.data?.symbol);
          if (!c) return;
          const slot = (live.current[c.symbol] = live.current[c.symbol] || {});
          if (m.data.lastPrice) slot.price = +m.data.lastPrice / c.div;
          if (m.data.price24hPcnt) slot.pct = +m.data.price24hPcnt * 100;
        } catch {}
      };
      ws.onclose = () => { if (ping) clearInterval(ping); if (!dead) retry = setTimeout(connect, 3000); };
      ws.onerror = () => { try { ws?.close(); } catch {} };
    };
    connect();
    const flush = setInterval(() => {
      const upd = live.current;
      if (!Object.keys(upd).length) return;
      setTickers((ts) => ts.map((t) => {
        const u = upd[t.symbol];
        if (!u || u.price === undefined) return t;
        return { ...t, price: u.price, changePct: u.pct ?? t.changePct, spark: [...t.spark.slice(1), u.price] };
      }));
    }, 1200);
    return () => {
      dead = true;
      if (retry) clearTimeout(retry);
      if (ping) clearInterval(ping);
      clearInterval(flush);
      try { ws?.close(); } catch {}
    };
  }, []);
  return { tickers, stats, src };
}
