"use client";

import { useEffect, useRef, useState } from "react";
import { Ticker, MarketStats, MarketResponse } from "./types";
import { COINS, BYBIT_WS, coinByBybit } from "./bybit";

// REST 快照（量/OI/費率/spark/總經）+ Bybit 公共 WebSocket 即時價。WS 斷線自動重連。
export function useMarket() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [src, setSrc] = useState<MarketResponse["source"]>({ crypto: "mock", macro: "mock" });
  const live = useRef<Record<string, { price?: number; pct?: number }>>({});

  // REST 快照 + 每 60 秒慢輪詢兜底
  useEffect(() => {
    let stop = false;
    const load = () =>
      fetch("/api/market", { cache: "no-store" })
        .then((r) => r.json() as Promise<MarketResponse>)
        .then((d) => {
          if (stop) return;
          setTickers(d.tickers);
          setStats(d.stats);
          if (d.source) setSrc(d.source);
        })
        .catch(() => {});
    load();
    const poll = window.setInterval(load, 60_000);
    return () => { stop = true; window.clearInterval(poll); };
  }, []);

  // Bybit 公共 WebSocket：tickers 即時推送，斷線 3 秒重連
  useEffect(() => {
    let ws: WebSocket | null = null;
    let ping: number | undefined;
    let retry: number | undefined;
    let dead = false;

    const connect = () => {
      try { ws = new WebSocket(BYBIT_WS); } catch { return; }
      ws.onopen = () => {
        ws?.send(JSON.stringify({ op: "subscribe", args: COINS.map((c) => "tickers." + c.bybit) }));
        ping = window.setInterval(() => { if (ws?.readyState === 1) ws.send(JSON.stringify({ op: "ping" })); }, 20_000);
      };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data as string);
          if (!m.topic || !String(m.topic).startsWith("tickers.")) return;
          const c = coinByBybit(m.data?.symbol);
          if (!c) return;
          const slot = (live.current[c.symbol] = live.current[c.symbol] || {});
          if (m.data.lastPrice) slot.price = +m.data.lastPrice / c.div;
          if (m.data.price24hPcnt) slot.pct = +m.data.price24hPcnt * 100;
        } catch { /* 單則訊息壞掉不影響 */ }
      };
      ws.onclose = () => { if (ping) window.clearInterval(ping); if (!dead) retry = window.setTimeout(connect, 3000); };
      ws.onerror = () => { try { ws?.close(); } catch { /* noop */ } };
    };
    connect();

    // 每 1.2 秒把 WS 最新值刷進 state（節流，避免每則訊息都 re-render）
    const flush = window.setInterval(() => {
      const upd = live.current;
      if (!Object.keys(upd).length) return;
      setTickers((ts) =>
        ts.map((t) => {
          const u = upd[t.symbol];
          if (!u || u.price === undefined) return t;
          return { ...t, price: u.price, changePct: u.pct ?? t.changePct, spark: [...t.spark.slice(1), u.price] };
        })
      );
    }, 1200);

    return () => {
      dead = true;
      if (retry) window.clearTimeout(retry);
      if (ping) window.clearInterval(ping);
      window.clearInterval(flush);
      try { ws?.close(); } catch { /* noop */ }
    };
  }, []);

  return { tickers, stats, src };
}
