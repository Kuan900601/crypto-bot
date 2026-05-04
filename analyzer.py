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

    def generate_signal(self, df, fg_val=50):
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
        total = score
        if total >= 4:
            direction, den = "做多 🟢", "LONG"
        elif total <= -4:
            direction, den = "做空 🔴", "SHORT"
        else:
            direction, den = "觀望 🟡", "NEUTRAL"
        strength = min(abs(total)/10*100, 100)
        if regime in ("STRONG_BULL","STRONG_BEAR"):
            tp1m, tp2m, slm = 2.0, 4.0, 1.2
        elif regime in ("BULL","BEAR"):
            tp1m, tp2m, slm = 1.5, 3.0, 1.5
        else:
            tp1m, tp2m, slm = 1.0, 2.0, 1.0
        if den == "LONG":
            entry = round(p*0.999, 4)
            tp1 = round(p+av*tp1m, 4)
            tp2 = round(p+av*tp2m, 4)
            sl = round(p-av*slm, 4)
        elif den == "SHORT":
            entry = round(p*1.001, 4)
            tp1 = round(p-av*tp1m, 4)
            tp2 = round(p-av*tp2m, 4)
            sl = round(p+av*slm, 4)
        else:
            entry = tp1 = tp2 = sl = p
        rr = round(abs(tp1-entry)/abs(sl-entry+1e-9), 2)
        wr = 0.55 if strength > 70 else 0.50 if strength > 50 else 0.45
        kelly = max(0, (wr-(1-wr)/rr))*100 if rr > 0 else 0
        return {
            "price": p, "direction": direction, "direction_en": den,
            "strength": strength, "reasons": reasons[:5],
            "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr,
            "position_size": round(min(kelly, 10), 1),
            "rsi": round(rv, 1), "stoch_k": round(kv, 1), "stoch_d": round(dv, 1),
            "macd_hist": round(hv, 6), "adx": round(adx_now, 1),
            "bb_upper": round(bbu.iloc[-1], 4), "bb_lower": round(bbl.iloc[-1], 4),
            "bb_width": round(bbw, 4),
            "ema20": round(e20, 4), "ema50": round(e50, 4), "ema200": round(e200, 4),
            "atr": round(av, 4), "regime": regime, "regime_label": regime_label,
            "obv_trend": "🟢 遞增" if obv_slope > 0 else "🔴 遞減"
        }

    async def full_analysis(self, symbol):
        try:
            df1h, df4h, ticker, (obl, obr) = await asyncio.gather(
                self.fetch_ohlcv(symbol, "1h", 300),
                self.fetch_ohlcv(symbol, "4h", 200),
                self.fetch_ticker(symbol),
                self.fetch_orderbook(symbol),
            )
            sig = self.generate_signal(df1h)
            sig4h = self.generate_signal(df4h)
            fibs, fhi, flo = self.fibonacci_levels(df1h)
            vtl, _ = self.volume_trend(df1h)
