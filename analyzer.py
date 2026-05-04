import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone


class CryptoAnalyzer:

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=300):
        pair = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        if isinstance(data, dict) and data.get("code"):
            raise ValueError(f"幣種不存在：{symbol}")
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","quote_volume","trades","tbb","tbq","ignore"
        ])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    async def fetch_ticker(self, symbol):
        pair = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                return await r.json()

    async def fetch_orderbook(self, symbol):
        pair = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/depth?symbol={pair}&limit=20"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    data = await r.json()
            bids = sum(float(b[1]) for b in data.get("bids", []))
            asks = sum(float(a[1]) for a in data.get("asks", []))
            ratio = bids / asks if asks > 0 else 1
            if ratio > 1.3:   return f"📗 買
