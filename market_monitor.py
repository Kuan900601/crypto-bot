"""
market_monitor.py — 全市場異常監控（v65 新增，獨立模組）

只負責訂閱 Bybit 公開 WebSocket、把全市場爆倉/資金費率異常/巨量成交寫進 Redis，
給網站 /api/alerts 讀。完全不 import、不呼叫 auto_trader.py / bot.py 的任何下單、
平倉、風控函式，純觀察、純讀取，跟交易執行緒之間沒有任何共用狀態。

隔離原則：
- 整個模組在獨立 daemon thread 跑，由 start() 啟動；start() 本身包 try/except，
  即使 thread 建立失敗也只 log，絕不讓例外往呼叫端（bot.py）傳。
- WS 連線迴圈外層有斷線重連（固定 10 秒後重試），內層逐筆訊息處理也包 try/except，
  單筆訊息解析失敗只跳過，不會讓整個連線掛掉。
- 缺套件（websockets 未安裝）或缺 Redis 環境變數時直接不啟動、只 log 一行，不報錯。
"""
import json
import os
import logging
import threading
import time
import asyncio
import urllib.request as _urlreq
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger("market_monitor")

try:
    import websockets
    _HAS_WS = True
except ImportError:
    _HAS_WS = False

_REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
_REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
_USE_REDIS = bool(_REDIS_URL and _REDIS_TOKEN)

BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear"

# 門檻全部可用環境變數調整，不用重新部署改 code
LIQ_MIN_USD = float(os.getenv("MARKET_LIQ_MIN_USD", "50000"))
FUNDING_ABS_THRESHOLD = float(os.getenv("MARKET_FUNDING_ABS_THRESHOLD", "0.005"))  # 0.5%
VOLUME_WINDOW_SEC = int(os.getenv("MARKET_VOLUME_WINDOW_SEC", "300"))  # 5 分鐘窗口
VOLUME_MIN_USD = float(os.getenv("MARKET_VOLUME_MIN_USD", "3000000"))  # 窗口內累計門檻

_RECONNECT_DELAY_SEC = 10


def _redis_cmd(args):
    if not _USE_REDIS:
        return None
    try:
        body = json.dumps(args).encode("utf-8")
        req = _urlreq.Request(_REDIS_URL, data=body, headers={
            "Authorization": "Bearer " + _REDIS_TOKEN,
            "Content-Type": "application/json",
        })
        with _urlreq.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("market_monitor Redis 命令失敗: %s", str(e)[:120])
        return None


def _push_list(key, value_dict, max_len=200):
    try:
        _redis_cmd(["RPUSH", key, json.dumps(value_dict, ensure_ascii=False)])
        _redis_cmd(["LTRIM", key, -max_len, -1])
    except Exception as e:
        logger.warning("market_monitor 寫入 %s 失敗: %s", key, str(e)[:120])


def _scan_symbols():
    """重用 analyzer.py 現有的掃描幣種清單（SCAN_POOL），不重複定義一份新的。
    任何原因拿不到就退回一個小清單，至少模組能跑起來。"""
    try:
        from analyzer import CryptoAnalyzer
        pool = list(getattr(CryptoAnalyzer, "SCAN_POOL", []))
    except Exception as e:
        logger.warning("market_monitor 讀不到 analyzer.SCAN_POOL，用預設小清單: %s", str(e)[:100])
        pool = []
    if not pool:
        pool = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    return [s.replace("/USDT", "USDT") for s in pool]


class _VolumeTracker:
    """每個幣種維護一個 (時間, 金額) 的滑動窗口，超過門檻才寫 Redis，避免洗版。"""
    def __init__(self, window_sec, min_usd):
        self.window_sec = window_sec
        self.min_usd = min_usd
        self._buckets = {}  # symbol -> deque[(ts, amount)]
        self._last_alert_ts = {}  # symbol -> ts，同一幣種至少間隔一個窗口才再報一次

    def add_trade(self, symbol, amount):
        now = time.time()
        dq = self._buckets.setdefault(symbol, deque())
        dq.append((now, amount))
        cutoff = now - self.window_sec
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        total = sum(a for _, a in dq)
        if total < self.min_usd:
            return None
        last = self._last_alert_ts.get(symbol, 0)
        if now - last < self.window_sec:
            return None
        self._last_alert_ts[symbol] = now
        return total


async def _handle_liquidation(it):
    try:
        price = float(it.get("price", 0) or 0)
        qty = float(it.get("size", it.get("qty", 0)) or 0)
        amount = price * qty
        if amount < LIQ_MIN_USD:
            return
        _push_list("market:liquidations", {
            "symbol": str(it.get("symbol", "")).replace("USDT", ""),
            "side": it.get("side", ""),
            "qty": qty, "amount": round(amount, 2), "price": price,
            "time": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def _handle_ticker(it):
    try:
        funding = it.get("fundingRate")
        if funding is None:
            return
        funding = float(funding)
        if abs(funding) < FUNDING_ABS_THRESHOLD:
            return
        _push_list("market:funding", {
            "symbol": str(it.get("symbol", "")).replace("USDT", ""),
            "fundingRate": funding,
            "time": datetime.now(timezone.utc).isoformat(),
        }, max_len=100)
    except Exception:
        pass


async def _handle_trade(items, tracker):
    if not isinstance(items, list):
        items = [items]
    for it in items:
        try:
            symbol = str(it.get("s", it.get("symbol", "")))
            price = float(it.get("p", it.get("price", 0)) or 0)
            qty = float(it.get("v", it.get("size", 0)) or 0)
            amount = price * qty
            if amount <= 0:
                continue
            total = tracker.add_trade(symbol, amount)
            if total is not None:
                _push_list("market:volume", {
                    "symbol": symbol.replace("USDT", ""),
                    "windowSec": VOLUME_WINDOW_SEC,
                    "totalUsd": round(total, 0),
                    "time": datetime.now(timezone.utc).isoformat(),
                }, max_len=100)
        except Exception:
            continue


async def _run_stream():
    symbols = _scan_symbols()
    topics = (
        ["allLiquidation." + s for s in symbols]
        + ["tickers." + s for s in symbols]
        + ["publicTrade." + s for s in symbols]
    )
    tracker = _VolumeTracker(VOLUME_WINDOW_SEC, VOLUME_MIN_USD)
    while True:
        try:
            async with websockets.connect(BYBIT_WS_URL, ping_interval=20, ping_timeout=10) as ws:
                # Bybit 單次訂閱上限約 10 個 topic，分批送出避免被拒
                for i in range(0, len(topics), 10):
                    await ws.send(json.dumps({"op": "subscribe", "args": topics[i:i + 10]}))
                    await asyncio.sleep(0.2)
                logger.info("✅ market_monitor 已連上 Bybit，訂閱 %d 個幣種 × 3 種 topic", len(symbols))
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        topic = msg.get("topic", "")
                        data = msg.get("data")
                        if not topic or data is None:
                            continue
                        if topic.startswith("allLiquidation."):
                            items = data if isinstance(data, list) else [data]
                            for it in items:
                                await _handle_liquidation(it)
                        elif topic.startswith("tickers."):
                            await _handle_ticker(data)
                        elif topic.startswith("publicTrade."):
                            await _handle_trade(data, tracker)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("⚠️ market_monitor WS 斷線，%s 秒後重連: %s", _RECONNECT_DELAY_SEC, str(e)[:120])
            await asyncio.sleep(_RECONNECT_DELAY_SEC)


def _worker():
    if not _HAS_WS:
        logger.warning("⚠️ market_monitor 未啟動：缺少 websockets 套件（pip install websockets）")
        return
    if not _USE_REDIS:
        logger.warning("⚠️ market_monitor 未啟動：缺少 UPSTASH_REDIS_REST_URL/TOKEN 環境變數")
        return
    while True:
        try:
            asyncio.run(_run_stream())
        except Exception as e:
            logger.error("🔴 market_monitor 主迴圈異常退出，%s 秒後重啟（不影響交易）: %s",
                         _RECONNECT_DELAY_SEC, str(e)[:200])
            time.sleep(_RECONNECT_DELAY_SEC)


def start():
    """在獨立 daemon thread 啟動全市場異常監控。
    失敗只 log，絕不拋出例外、不影響呼叫端（bot.py 主流程/交易執行緒）。"""
    try:
        t = threading.Thread(target=_worker, daemon=True, name="market_monitor")
        t.start()
        logger.info("🟢 market_monitor 背景執行緒已啟動")
    except Exception as e:
        logger.error("🔴 market_monitor 啟動失敗（不影響主程式）: %s", str(e)[:200])
