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
            if ratio > 1.3:
                return f"📗 買壓強 ({ratio:.2f})", ratio
            elif ratio < 0.77:
                return f"📕 賣壓強 ({ratio:.2f})", ratio
            else:
                return f"📒 買賣平衡 ({ratio:.2f})", ratio
        except Exception:
            return "📒 不可用", 1.0

    async def fetch_fear_greed(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.alternative.me/fng/?limit=1",
                                  timeout=aiohttp.ClientTimeout(total=6)) as r:
                    data = await r.json()
            val = int(data["data"][0]["value"])
            label = data["data"][0]["value_classification"]
            if val >= 75:
                icon = "🟠"
            elif val >= 55:
                icon = "🟡"
            elif val >= 45:
                icon = "⚪"
            elif val >= 25:
                icon = "🔵"
            else:
                icon = "🔴"
            return f"{icon} {val}/100 ({label})", val
        except Exception:
            return "⚪ 不可用", 50

    async def fetch_news(self):
        url = "https://cryptopanic.com/api/free/v1/posts/?auth_token=public&kind=news&public=true"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    data = await r.json()
                    return data.get("results", [])[:15]
        except Exception:
            return []

    def rsi(self, df, p=14):
        d = df["close"].diff()
        g = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
        return 100 - 100/(1 + g/l.replace(0, np.nan))

    def stoch_rsi(self, df, rp=14, sp=14, k=3, d=3):
        r = self.rsi(df, rp)
        lo = r.rolling(sp).min()
        hi = r.rolling(sp).max()
        kl = ((r - lo) / (hi - lo + 1e-9) * 100).rolling(k).mean()
        dl = kl.rolling(d).mean()
        return kl, dl

    def macd(self, df, f=12, sl=26, sig=9):
        fast = df["close"].ewm(span=f, adjust=False).mean()
        slow = df["close"].ewm(span=sl, adjust=False).mean()
        m = fast - slow
        s = m.ewm(span=sig, adjust=False).mean()
        return m, s, m - s

    def bollinger(self, df, p=20, std=2.0):
        sma = df["close"].rolling(p).mean()
        s = df["close"].rolling(p).std()
        return sma + std*s, sma, sma - std*s, s.iloc[-1]*2

    def atr(self, df, p=14):
        h, l, pc = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()], axis=1).max(axis=1)
        return tr.ewm(span=p, adjust=False).mean()

    def ema(self, df, p):
        return df["close"].ewm(span=p, adjust=False).mean()

    def obv(self, df):
        direction = np.sign(df["close"].diff()).fillna(0)
        return (direction * df["volume"]).cumsum()

    def fibonacci_levels(self, df, lookback=100):
        r = df.tail(lookback)
        hi, lo = r["high"].max(), r["low"].min()
        diff = hi - lo
        return {
            "0.236": round(hi - 0.236*diff, 4),
            "0.382": round(hi - 0.382*diff, 4),
            "0.5":   round(hi - 0.5*diff, 4),
            "0.618": round(hi - 0.618*diff, 4),
            "0.786": round(hi - 0.786*diff, 4),
        }, round(hi, 4), round(lo, 4)

    def adx(self, df, p=14):
        h, l = df["high"], df["low"]
        up, down = h.diff(), -l.diff()
        pdm = up.where((up > down) & (up > 0), 0)
        mdm = down.where((down > up) & (down > 0), 0)
        av = self.atr(df, p)
        pdi = 100 * pdm.ewm(span=p).mean() / av
        mdi = 100 * mdm.ewm(span=p).mean() / av
        dx = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-9)
        return dx.ewm(span=p).mean(), pdi, mdi

    def volume_trend(self, df, p=20):
        avg = df["volume"].rolling(p).mean().iloc[-1]
        curr = df["volume"].iloc[-1]
        r = curr/avg if avg > 0 else 1
        if r > 2.0:
            return f"🔥 極度爆量({r:.1f}x)", r
        elif r > 1.5:
            return f"🔴 爆量({r:.1f}x)", r
        elif r > 1.2:
            return f"🟡 放量({r:.1f}x)", r
        else:
            return f"🟢 縮量({r:.1f}x)", r

    def market_regime(self, df):
        e20 = self.ema(df, 20).iloc[-1]
        e50 = self.ema(df, 50).iloc[-1]
        e200 = self.ema(df, 200).iloc[-1]
        p = df["close"].iloc[-1]
        adx_v = self.adx(df)[0].iloc[-1]
        if p > e20 > e50 > e200 and adx_v > 25:
            return "強多頭 🚀", "STRONG_BULL", adx_v
        elif p > e50 > e200:
            return "多頭 📈", "BULL", adx_v
        elif p < e20 < e50 < e200 and adx_v > 25:
            return "強空頭 💥", "STRONG_BEAR", adx_v
        elif p < e50 < e200:
            return "空頭 📉", "BEAR", adx_v
        else:
            return "震盪整理 ↔️", "RANGING", adx_v

    BULL_W = {"bull","rally","surge","gain","pump","breakout","ath","adoption",
              "buy","rise","recover","bullish","etf","approve","institutional","moon"}
    BEAR_W = {"bear","crash","dump","drop","sell","ban","hack","lawsuit",
              "fear","decline","bearish","sec","liquidat","collapse","warning","fraud"}

    def sentiment(self, news):
        score, heads = 0, []
        for item in news[:12]:
            t = item.get("title","").lower()
            heads.append(item.get("title","")[:75])
            score += (sum(1 for w in self.BULL_W if w in t) -
                      sum(1 for w in self.BEAR_W if w in t)) * 0.1
        score = max(-1.0, min(1.0, score))
        label = "📗 偏多" if score > 0.3 else ("📕 偏空" if score < -0.3 else "📒 中性")
        return score, label, heads[:5]

    def generate_signal(self, df, news_score, fg_val=50):
        p = df["close"].iloc[-1]
        rv = self.rsi(df).iloc[-1]
        kv, dv = [x.iloc[-1] for x in self.stoch_rsi(df)]
        ml, sl_, hist = self.macd(df)
        hv = hist.iloc[-1]
        bbu, _, bbl, bbw = self.bollinger(df)
        av = self.atr(df).iloc[-1]
        obv_slope = self.obv(df).diff(5).iloc[-1]
        adx_v, pdi, mdi = self.adx(df)
        adx_now = adx_v.iloc[-1]
        e20 = self.ema(df, 20).iloc[-1]
        e50 = self.ema(df, 50).iloc[-1]
        e200 = self.ema(df, 200).iloc[-1]
        regime_label, regime, _ = self.market_regime(df)
        score, reasons = 0, []
        if rv < 30:
            score += 2.5
            reasons.append(f"RSI超賣({rv:.1f})")
        elif rv < 40:
            score += 1.0
            reasons.append(f"RSI偏低({rv:.1f})")
        elif rv > 70:
            score -= 2.5
            reasons.append(f"RSI超買({rv:.1f})")
        elif rv > 60:
            score -= 1.0
            reasons.append(f"RSI偏高({rv:.1f})")
        if kv < 20 and kv > dv:
            score += 1.5
            reasons.append("StochRSI底部金叉")
        elif kv > 80 and kv < dv:
            score -= 1.5
            reasons.append("StochRSI頂部死叉")
        if ml.iloc[-1] > sl_.iloc[-1] and hv > 0:
            score += 2
            reasons.append("MACD金叉")
        elif ml.iloc[-1] < sl_.iloc[-1] and hv < 0:
            score -= 2
            reasons.append("MACD死叉")
        if p < bbl.iloc[-1]:
            score += 2
            reasons.append("跌破布林下軌")
        elif p > bbu.iloc[-1]:
            score -= 2
            reasons.append("突破布林上軌")
        if p > e20 > e50 > e200:
            score += 2.5
            reasons.append("EMA多頭排列")
        elif p < e20 < e50 < e200:
            score -= 2.5
            reasons.append("EMA空頭排列")
        if obv_slope > 0:
            score += 1
            reasons.append("OBV量能遞增")
        elif obv_slope < 0:
            score -= 1
            reasons.append("OBV量能遞減")
        if adx_now < 20:
            score *= 0.6
        elif adx_now > 35:
            score *= 1.2
        if fg_val <= 20:
            score += 1.5
            reasons.append("極度恐懼(逆向做多)")
        elif fg_val >= 80:
            score -= 1.5
            reasons.append("極度貪婪(逆向做空)")
        total = score + news_score * 2
        if total >= 4:
            direction, den = "做多 🟢", "LONG"
        elif total <= -4:
            direction, den = "做空 🔴", "SHORT"
