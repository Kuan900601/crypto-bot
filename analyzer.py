import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone

class CryptoAnalyzer:

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/klines?symbol=" + pair + "&interval=" + timeframe + "&limit=" + str(limit)
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        cols = ["timestamp","open","high","low","close","volume","close_time","quote_volume","trades","tbb","tbq","ignore"]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def fetch_ticker(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=" + pair
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                return await r.json()

    async def fetch_orderbook(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/depth?symbol=" + pair + "&limit=20"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    data = await r.json()
            bids = sum(float(b[1]) for b in data.get("bids", []))
            asks = sum(float(a[1]) for a in data.get("asks", []))
            ratio = bids / asks if asks > 0 else 1
            if ratio > 1.3:
                return "📗 買壓強", ratio
            elif ratio < 0.77:
                return "📕 賣壓強", ratio
            else:
                return "📒 平衡", ratio
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
        h = df["high"]
        l = df["low"]
        pc = df["close"].shift(1)
        tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
        return tr.ewm(span=p, adjust=False).mean()

    def ema(self, df, p):
        return df["close"].ewm(span=p, adjust=False).mean()

    def obv(self, df):
        direction = np.sign(df["close"].diff()).fillna(0)
        return (direction * df["volume"]).cumsum()

    def adx(self, df, p=14):
        h = df["high"]
        l = df["low"]
        up = h.diff()
        down = -l.diff()
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
        r = curr / avg if avg > 0 else 1
        if r > 2.0:
            return "🔥 極度爆量", r
        elif r > 1.5:
            return "🔴 爆量", r
        elif r > 1.2:
            return "🟡 放量", r
        else:
            return "🟢 縮量", r

    def fibonacci(self, df, lookback=100):
        r = df.tail(lookback)
        hi = r["high"].max()
        lo = r["low"].min()
        diff = hi - lo
        return {
            "0.236": round(hi - 0.236*diff, 4),
            "0.382": round(hi - 0.382*diff, 4),
            "0.5": round(hi - 0.5*diff, 4),
            "0.618": round(hi - 0.618*diff, 4),
            "0.786": round(hi - 0.786*diff, 4),
        }, round(hi, 4), round(lo, 4)

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

    def generate_signal(self, df):
        p = df["close"].iloc[-1]
        rv = self.rsi(df).iloc[-1]
        kv = self.stoch_rsi(df)[0].iloc[-1]
        dv = self.stoch_rsi(df)[1].iloc[-1]
        ml, sl_, hist = self.macd(df)
        hv = hist.iloc[-1]
        bbu, _, bbl, bbw = self.bollinger(df)
        av = self.atr(df).iloc[-1]
        obv_slope = self.obv(df).diff(5).iloc[-1]
        adx_now = self.adx(df)[0].iloc[-1]
        e20 = self.ema(df, 20).iloc[-1]
        e50 = self.ema(df, 50).iloc[-1]
        e200 = self.ema(df, 200).iloc[-1]
        rl, regime, _ = self.market_regime(df)
        score = 0
        reasons = []
        if rv < 30:
            score += 2.5
            reasons.append("RSI超賣(" + str(round(rv, 1)) + ")")
        elif rv < 40:
            score += 1.0
            reasons.append("RSI偏低(" + str(round(rv, 1)) + ")")
        elif rv > 70:
            score -= 2.5
            reasons.append("RSI超買(" + str(round(rv, 1)) + ")")
        elif rv > 60:
            score -= 1.0
            reasons.append("RSI偏高(" + str(round(rv, 1)) + ")")
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
            reasons.append("OBV遞增")
        elif obv_slope < 0:
            score -= 1
            reasons.append("OBV遞減")
        if adx_now < 20:
            score = score * 0.6
        elif adx_now > 35:
            score = score * 1.2
        if score >= 4:
            direction = "做多 🟢"
            den = "LONG"
        elif score <= -4:
            direction = "做空 🔴"
            den = "SHORT"
        else:
            direction = "觀望 🟡"
            den = "NEUTRAL"
        strength = min(abs(score) / 10 * 100, 100)
        if regime in ("STRONG_BULL", "STRONG_BEAR"):
            tp1m, tp2m, slm = 2.0, 4.0, 1.2
        elif regime in ("BULL", "BEAR"):
            tp1m, tp2m, slm = 1.5, 3.0, 1.5
        else:
            tp1m, tp2m, slm = 1.0, 2.0, 1.0
        if den == "LONG":
            entry = round(p * 0.999, 4)
            tp1 = round(p + av * tp1m, 4)
            tp2 = round(p + av * tp2m, 4)
            sl = round(p - av * slm, 4)
        elif den == "SHORT":
            entry = round(p * 1.001, 4)
            tp1 = round(p - av * tp1m, 4)
            tp2 = round(p - av * tp2m, 4)
            sl = round(p + av * slm, 4)
        else:
            entry = tp1 = tp2 = sl = p
        rr = round(abs(tp1 - entry) / abs(sl - entry + 1e-9), 2)
        wr = 0.55 if strength > 70 else 0.50 if strength > 50 else 0.45
        kelly = max(0, (wr - (1 - wr) / rr)) * 100 if rr > 0 else 0
        return {
            "price": p, "direction": direction, "direction_en": den,
            "strength": strength, "reasons": reasons[:5],
            "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr,
            "pos": round(min(kelly, 10), 1),
            "rsi": round(rv, 1), "sk": round(kv, 1), "sd": round(dv, 1),
            "mh": round(hv, 6), "adx": round(adx_now, 1),
            "bbu": round(bbu.iloc[-1], 4), "bbl": round(bbl.iloc[-1], 4),
            "e20": round(e20, 4), "e50": round(e50, 4), "e200": round(e200, 4),
            "atr": round(av, 4), "regime": regime, "rl": rl,
            "obv": "🟢 遞增" if obv_slope > 0 else "🔴 遞減"
        }

    async def full_analysis(self, symbol):
        try:
            results = await asyncio.gather(
                self.fetch_ohlcv(symbol, "1h", 200),
                self.fetch_ohlcv(symbol, "4h", 150),
                self.fetch_ticker(symbol),
                self.fetch_orderbook(symbol),
            )
            df1h = results[0]
            df4h = results[1]
            ticker = results[2]
            obl = results[3][0]
            sig = self.generate_signal(df1h)
            sig4h = self.generate_signal(df4h)
            fibs, fhi, flo = self.fibonacci(df1h)
            vtl, _ = self.volume_trend(df1h)
            chg = float(ticker.get("priceChangePercent", 0))
            icon = "📈" if chg >= 0 else "📉"
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            p = sig["price"]
            fib_sup = max(((k, v) for k, v in fibs.items() if v < p), key=lambda x: x[1], default=None)
            fib_res = min(((k, v) for k, v in fibs.items() if v > p), key=lambda x: x[1], default=None)
            report = "╔══════════════════════╗\n"
            report += "║ 🔍 *" + symbol + " 深度分析*\n"
            report += "║ 🕒 " + now + "\n"
            report += "╚══════════════════════╝\n\n"
            report += "💰 *現價：* `" + str(p) + "` " + icon + " `" + str(round(chg, 2)) + "%`\n"
            report += "🌊 *市場結構：* " + sig["rl"] + "\n"
            report += "📊 *ADX：* `" + str(sig["adx"]) + "`\n\n"
            report += "━━━━ 📊 技術指標 ━━━━\n"
            report += "• RSI: `" + str(sig["rsi"]) + "`\n"
            report += "• StochRSI K/D: `" + str(sig["sk"]) + "/" + str(sig["sd"]) + "`\n"
            report += "• MACD柱: `" + str(sig["mh"]) + "`\n"
            report += "• 布林 上/下: `" + str(sig["bbu"]) + "/" + str(sig["bbl"]) + "`\n"
            report += "• EMA 20/50/200: `" + str(sig["e20"]) + "/" + str(sig["e50"]) + "/" + str(sig["e200"]) + "`\n"
            report += "• OBV: " + sig["obv"] + " | " + vtl + "\n"
            report += "• ATR: `" + str(sig["atr"]) + "`\n\n"
            report += "━━━━ 🎯 Fibonacci ━━━━\n"
            if fib_sup:
                report += "• 支撐(" + str(fib_sup[0]) + "): `" + str(fib_sup[1]) + "`\n"
            if fib_res:
                report += "• 阻力(" + str(fib_res[0]) + "): `" + str(fib_res[1]) + "`\n"
            report += "\n━━━━ 🌐 訂單簿 ━━━━\n"
            report += "• " + obl + "\n"
            report += "\n══════════════════════\n"
            if sig["direction_en"] != "NEUTRAL":
                if sig["direction_en"] == sig4h["direction_en"]:
                    conf = "✅ 1H+4H一致"
                else:
                    conf = "⚠️ 週期分歧謹慎"
                report += "🎯 *方向：" + sig["direction"] + "*\n"
                report += "💪 *強度：" + str(round(sig["strength"])) + "%*\n"
                report += "📋 " + " | ".join(sig["reasons"][:3]) + "\n\n"
                report += "┌──────────────────────┐\n"
                report += "│ 🎯 進場  `" + str(sig["entry"]) + "`\n"
                report += "│ 🏁 止盈1 `" + str(sig["tp1"]) + "`\n"
                report += "│ 🏆 止盈2 `" + str(sig["tp2"]) + "`\n"
                report += "│ 🛑 止損  `" + str(sig["sl"]) + "`\n"
                report += "│ ⚖️ 風報比 `1:" + str(sig["rr"]) + "`\n"
                report += "│ 💼 建議倉位 `" + str(sig["pos"]) + "%`\n"
                report += "└──────────────────────┘\n\n"
                report += "📅 4H：" + sig4h["direction"] + " | " + conf + "\n"
            else:
                report += "🟡 *建議觀望*\n"
                report += "強度不足（" + str(round(sig["strength"])) + "%）\n"
                report += "📋 " + " | ".join(sig["reasons"][:3]) + "\n"
            report += "\n══════════════════════\n"
            report += "⚠️ _僅供參考，非投資建議_"
            return report
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    async def get_news_summary(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return "📰 *市場情緒*\n🕒 " + now + "\n\n新聞功能暫時關閉以提升速度"

    async def trend_watch(self, symbols):
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        report = "🔭 *趨勢總覽* — " + now + "\n"
        report += "──────────────────────\n"
        for symbol in symbols:
            try:
                df, ticker = await asyncio.gather(
                    self.fetch_ohlcv(symbol, "1h", 200),
                    self.fetch_ticker(symbol)
                )
                rl, _, adx_v = self.market_regime(df)
                chg = float(ticker.get("priceChangePercent", 0))
                price = df["close"].iloc[-1]
                icon = "📈" if chg >= 0 else "📉"
                report += icon + " *" + symbol + "*  `" + str(round(price, 2)) + "`  `" + str(round(chg, 1)) + "%`\n"
                report += "   " + rl + "  ADX:`" + str(round(adx_v)) + "`\n\n"
            except Exception:
                report += "❌ " + symbol + " 失敗\n\n"
        return reportimport asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone

class CryptoAnalyzer:

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/klines?symbol=" + pair + "&interval=" + timeframe + "&limit=" + str(limit)
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        cols = ["timestamp","open","high","low","close","volume","close_time","quote_volume","trades","tbb","tbq","ignore"]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def fetch_ticker(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=" + pair
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                return await r.json()

    async def fetch_orderbook(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/depth?symbol=" + pair + "&limit=20"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    data = await r.json()
            bids = sum(float(b[1]) for b in data.get("bids", []))
            asks = sum(float(a[1]) for a in data.get("asks", []))
            ratio = bids / asks if asks > 0 else 1
            if ratio > 1.3:
                return "📗 買壓強", ratio
            elif ratio < 0.77:
                return "📕 賣壓強", ratio
            else:
                return "📒 平衡", ratio
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
        h = df["high"]
        l = df["low"]
        pc = df["close"].shift(1)
        tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
        return tr.ewm(span=p, adjust=False).mean()

    def ema(self, df, p):
        return df["close"].ewm(span=p, adjust=False).mean()

    def obv(self, df):
        direction = np.sign(df["close"].diff()).fillna(0)
        return (direction * df["volume"]).cumsum()

    def adx(self, df, p=14):
        h = df["high"]
        l = df["low"]
        up = h.diff()
        down = -l.diff()
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
        r = curr / avg if avg > 0 else 1
        if r > 2.0:
            return "🔥 極度爆量", r
        elif r > 1.5:
            return "🔴 爆量", r
        elif r > 1.2:
            return "🟡 放量", r
        else:
            return "🟢 縮量", r

    def fibonacci(self, df, lookback=100):
        r = df.tail(lookback)
        hi = r["high"].max()
        lo = r["low"].min()
        diff = hi - lo
        return {
            "0.236": round(hi - 0.236*diff, 4),
            "0.382": round(hi - 0.382*diff, 4),
            "0.5": round(hi - 0.5*diff, 4),
            "0.618": round(hi - 0.618*diff, 4),
            "0.786": round(hi - 0.786*diff, 4),
        }, round(hi, 4), round(lo, 4)

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

    def generate_signal(self, df):
        p = df["close"].iloc[-1]
        rv = self.rsi(df).iloc[-1]
        kv = self.stoch_rsi(df)[0].iloc[-1]
        dv = self.stoch_rsi(df)[1].iloc[-1]
        ml, sl_, hist = self.macd(df)
        hv = hist.iloc[-1]
        bbu, _, bbl, bbw = self.bollinger(df)
        av = self.atr(df).iloc[-1]
        obv_slope = self.obv(df).diff(5).iloc[-1]
        adx_now = self.adx(df)[0].iloc[-1]
        e20 = self.ema(df, 20).iloc[-1]
        e50 = self.ema(df, 50).iloc[-1]
        e200 = self.ema(df, 200).iloc[-1]
        rl, regime, _ = self.market_regime(df)
        score = 0
        reasons = []
        if rv < 30:
            score += 2.5
            reasons.append("RSI超賣(" + str(round(rv, 1)) + ")")
        elif rv < 40:
            score += 1.0
            reasons.append("RSI偏低(" + str(round(rv, 1)) + ")")
        elif rv > 70:
            score -= 2.5
            reasons.append("RSI超買(" + str(round(rv, 1)) + ")")
        elif rv > 60:
            score -= 1.0
            reasons.append("RSI偏高(" + str(round(rv, 1)) + ")")
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
            reasons.append("OBV遞增")
        elif obv_slope < 0:
            score -= 1
            reasons.append("OBV遞減")
        if adx_now < 20:
            score = score * 0.6
        elif adx_now > 35:
            score = score * 1.2
        if score >= 4:
            direction = "做多 🟢"
            den = "LONG"
        elif score <= -4:
            direction = "做空 🔴"
            den = "SHORT"
        else:
            direction = "觀望 🟡"
            den = "NEUTRAL"
        strength = min(abs(score) / 10 * 100, 100)
        if regime in ("STRONG_BULL", "STRONG_BEAR"):
            tp1m, tp2m, slm = 2.0, 4.0, 1.2
        elif regime in ("BULL", "BEAR"):
            tp1m, tp2m, slm = 1.5, 3.0, 1.5
        else:
            tp1m, tp2m, slm = 1.0, 2.0, 1.0
        if den == "LONG":
            entry = round(p * 0.999, 4)
            tp1 = round(p + av * tp1m, 4)
            tp2 = round(p + av * tp2m, 4)
            sl = round(p - av * slm, 4)
        elif den == "SHORT":
            entry = round(p * 1.001, 4)
            tp1 = round(p - av * tp1m, 4)
            tp2 = round(p - av * tp2m, 4)
            sl = round(p + av * slm, 4)
        else:
            entry = tp1 = tp2 = sl = p
        rr = round(abs(tp1 - entry) / abs(sl - entry + 1e-9), 2)
        wr = 0.55 if strength > 70 else 0.50 if strength > 50 else 0.45
        kelly = max(0, (wr - (1 - wr) / rr)) * 100 if rr > 0 else 0
        return {
            "price": p, "direction": direction, "direction_en": den,
            "strength": strength, "reasons": reasons[:5],
            "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr,
            "pos": round(min(kelly, 10), 1),
            "rsi": round(rv, 1), "sk": round(kv, 1), "sd": round(dv, 1),
            "mh": round(hv, 6), "adx": round(adx_now, 1),
            "bbu": round(bbu.iloc[-1], 4), "bbl": round(bbl.iloc[-1], 4),
            "e20": round(e20, 4), "e50": round(e50, 4), "e200": round(e200, 4),
            "atr": round(av, 4), "regime": regime, "rl": rl,
            "obv": "🟢 遞增" if obv_slope > 0 else "🔴 遞減"
        }

    async def full_analysis(self, symbol):
        try:
            results = await asyncio.gather(
                self.fetch_ohlcv(symbol, "1h", 200),
                self.fetch_ohlcv(symbol, "4h", 150),
                self.fetch_ticker(symbol),
                self.fetch_orderbook(symbol),
            )
            df1h = results[0]
            df4h = results[1]
            ticker = results[2]
            obl = results[3][0]
            sig = self.generate_signal(df1h)
            sig4h = self.generate_signal(df4h)
            fibs, fhi, flo = self.fibonacci(df1h)
            vtl, _ = self.volume_trend(df1h)
            chg = float(ticker.get("priceChangePercent", 0))
            icon = "📈" if chg >= 0 else "📉"
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            p = sig["price"]
            fib_sup = max(((k, v) for k, v in fibs.items() if v < p), key=lambda x: x[1], default=None)
            fib_res = min(((k, v) for k, v in fibs.items() if v > p), key=lambda x: x[1], default=None)
            report = "╔══════════════════════╗\n"
            report += "║ 🔍 *" + symbol + " 深度分析*\n"
            report += "║ 🕒 " + now + "\n"
            report += "╚══════════════════════╝\n\n"
            report += "💰 *現價：* `" + str(p) + "` " + icon + " `" + str(round(chg, 2)) + "%`\n"
            report += "🌊 *市場結構：* " + sig["rl"] + "\n"
            report += "📊 *ADX：* `" + str(sig["adx"]) + "`\n\n"
            report += "━━━━ 📊 技術指標 ━━━━\n"
            report += "• RSI: `" + str(sig["rsi"]) + "`\n"
            report += "• StochRSI K/D: `" + str(sig["sk"]) + "/" + str(sig["sd"]) + "`\n"
            report += "• MACD柱: `" + str(sig["mh"]) + "`\n"
            report += "• 布林 上/下: `" + str(sig["bbu"]) + "/" + str(sig["bbl"]) + "`\n"
            report += "• EMA 20/50/200: `" + str(sig["e20"]) + "/" + str(sig["e50"]) + "/" + str(sig["e200"]) + "`\n"
            report += "• OBV: " + sig["obv"] + " | " + vtl + "\n"
            report += "• ATR: `" + str(sig["atr"]) + "`\n\n"
            report += "━━━━ 🎯 Fibonacci ━━━━\n"
            if fib_sup:
                report += "• 支撐(" + str(fib_sup[0]) + "): `" + str(fib_sup[1]) + "`\n"
            if fib_res:
                report += "• 阻力(" + str(fib_res[0]) + "): `" + str(fib_res[1]) + "`\n"
            report += "\n━━━━ 🌐 訂單簿 ━━━━\n"
            report += "• " + obl + "\n"
            report += "\n══════════════════════\n"
            if sig["direction_en"] != "NEUTRAL":
                if sig["direction_en"] == sig4h["direction_en"]:
                    conf = "✅ 1H+4H一致"
                else:
                    conf = "⚠️ 週期分歧謹慎"
                report += "🎯 *方向：" + sig["direction"] + "*\n"
                report += "💪 *強度：" + str(round(sig["strength"])) + "%*\n"
                report += "📋 " + " | ".join(sig["reasons"][:3]) + "\n\n"
                report += "┌──────────────────────┐\n"
                report += "│ 🎯 進場  `" + str(sig["entry"]) + "`\n"
                report += "│ 🏁 止盈1 `" + str(sig["tp1"]) + "`\n"
                report += "│ 🏆 止盈2 `" + str(sig["tp2"]) + "`\n"
                report += "│ 🛑 止損  `" + str(sig["sl"]) + "`\n"
                report += "│ ⚖️ 風報比 `1:" + str(sig["rr"]) + "`\n"
                report += "│ 💼 建議倉位 `" + str(sig["pos"]) + "%`\n"
                report += "└──────────────────────┘\n\n"
                report += "📅 4H：" + sig4h["direction"] + " | " + conf + "\n"
            else:
                report += "🟡 *建議觀望*\n"
                report += "強度不足（" + str(round(sig["strength"])) + "%）\n"
                report += "📋 " + " | ".join(sig["reasons"][:3]) + "\n"
            report += "\n══════════════════════\n"
            report += "⚠️ _僅供參考，非投資建議_"
            return report
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    async def get_news_summary(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return "📰 *市場情緒*\n🕒 " + now + "\n\n新聞功能暫時關閉以提升速度"

    async def trend_watch(self, symbols):
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        report = "🔭 *趨勢總覽* — " + now + "\n"
        report += "──────────────────────\n"
        for symbol in symbols:
            try:
                df, ticker = await asyncio.gather(
                    self.fetch_ohlcv(symbol, "1h", 200),
                    self.fetch_ticker(symbol)
                )
                rl, _, adx_v = self.market_regime(df)
                chg = float(ticker.get("priceChangePercent", 0))
                price = df["close"].iloc[-1]
                icon = "📈" if chg >= 0 else "📉"
                report += icon + " *" + symbol + "*  `" + str(round(price, 2)) + "`  `" + str(round(chg, 1)) + "%`\n"
                report += "   " + rl + "  ADX:`" + str(round(adx_v)) + "`\n\n"
            except Exception:
                report += "❌ " + symbol + " 失敗\n\n"
        return report