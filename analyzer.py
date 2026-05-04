import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone


class CryptoAnalyzer:

    def safe_val(self, series, default=0):
        try:
            v = series.dropna()
            if len(v) == 0:
                return float(default)
            val = float(v.iloc[-1])
            if pd.isna(val) or np.isinf(val):
                return float(default)
            return val
        except Exception:
            return float(default)

    async def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/klines?symbol=" + pair + "&interval=" + timeframe + "&limit=" + str(limit)
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
        if isinstance(data, dict):
            raise ValueError("幣種錯誤：" + symbol)
        cols = ["timestamp","open","high","low","close","volume","close_time","qv","tr","tbb","tbq","ig"]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def fetch_ticker(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=" + pair
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                return await r.json()

    async def fetch_orderbook(self, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/depth?symbol=" + pair + "&limit=20"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
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

    async def fetch_fear_greed(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.alternative.me/fng/?limit=1",
                                  timeout=aiohttp.ClientTimeout(total=5)) as r:
                    data = await r.json()
            val = int(data["data"][0]["value"])
            if val >= 75:
                return "🟠 " + str(val) + " 貪婪", val
            elif val >= 55:
                return "🟡 " + str(val) + " 偏貪", val
            elif val >= 45:
                return "⚪ " + str(val) + " 中性", val
            elif val >= 25:
                return "🔵 " + str(val) + " 偏恐", val
            else:
                return "🔴 " + str(val) + " 恐懼", val
        except Exception:
            return "⚪ 不可用", 50

    async def fetch_btc_dominance(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://api.coingecko.com/api/v3/global",
                                  timeout=aiohttp.ClientTimeout(total=5)) as r:
                    data = await r.json()
            return round(data["data"]["market_cap_percentage"]["btc"], 2)
        except Exception:
            return None

    async def fetch_news(self):
        url = "https://cryptopanic.com/api/free/v1/posts/?auth_token=public&kind=news&public=true"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    data = await r.json()
                    return data.get("results", [])[:10]
        except Exception:
            return []

    def rsi(self, df, p=14):
        d = df["close"].diff()
        g = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
        rs = g / l.replace(0, np.nan)
        return 100 - 100 / (1 + rs)

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
        return sma + std * s, sma, sma - std * s

    def atr(self, df, p=14):
        h, l, pc = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
        return tr.ewm(span=p, adjust=False).mean()

    def ema(self, df, p):
        return df["close"].ewm(span=p, adjust=False).mean()

    def obv(self, df):
        return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()

    def adx(self, df, p=14):
        h, l = df["high"], df["low"]
        up, down = h.diff(), -l.diff()
        pdm = up.where((up > down) & (up > 0), 0)
        mdm = down.where((down > up) & (down > 0), 0)
        av = self.atr(df, p)
        pdi = 100 * pdm.ewm(span=p).mean() / av
        mdi = 100 * mdm.ewm(span=p).mean() / av
        dx = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-9)
        return dx.ewm(span=p).mean()

    def volume_trend(self, df, p=20):
        try:
            avg = float(df["volume"].rolling(p).mean().iloc[-1])
            curr = float(df["volume"].iloc[-1])
            r = curr / avg if avg > 0 else 1
            if r > 2.0:
                return "🔥 極度爆量"
            elif r > 1.5:
                return "🔴 爆量"
            elif r > 1.2:
                return "🟡 放量"
            else:
                return "🟢 縮量"
        except Exception:
            return "📒 一般"

    def fibonacci(self, df, lookback=100):
        r = df.tail(lookback)
        hi = float(r["high"].max())
        lo = float(r["low"].min())
        diff = hi - lo
        return {
            "0.236": round(hi - 0.236*diff, 4),
            "0.382": round(hi - 0.382*diff, 4),
            "0.5": round(hi - 0.5*diff, 4),
            "0.618": round(hi - 0.618*diff, 4),
            "0.786": round(hi - 0.786*diff, 4),
        }

    def market_regime(self, df):
        e20 = self.safe_val(self.ema(df, 20))
        e50 = self.safe_val(self.ema(df, 50))
        e200 = self.safe_val(self.ema(df, 200))
        p = float(df["close"].iloc[-1])
        adx_v = self.safe_val(self.adx(df), 20)
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
              "buy","rise","recover","bullish","etf","approve","institutional","moon","launch"}
    BEAR_W = {"bear","crash","dump","drop","sell","ban","hack","lawsuit",
              "fear","decline","bearish","sec","liquidat","collapse","warning","fraud","ponzi"}

    def sentiment(self, news):
        score, heads = 0, []
        for item in news[:10]:
            t = item.get("title", "").lower()
            heads.append(item.get("title", "")[:75])
            score += (sum(1 for w in self.BULL_W if w in t)
                      - sum(1 for w in self.BEAR_W if w in t)) * 0.1
        score = max(-1.0, min(1.0, score))
        if score > 0.3:
            label = "📗 偏多"
        elif score < -0.3:
            label = "📕 偏空"
        else:
            label = "📒 中性"
        return score, label, heads[:5]

    def generate_signal(self, df, news_score=0, fg_val=50):
        p = float(df["close"].iloc[-1])
        rv = self.safe_val(self.rsi(df), 50)
        kv = self.safe_val(self.stoch_rsi(df)[0], 50)
        dv = self.safe_val(self.stoch_rsi(df)[1], 50)
        ml, sl_, hist = self.macd(df)
        hv = self.safe_val(hist, 0)
        ml_v = self.safe_val(ml, 0)
        sl_v = self.safe_val(sl_, 0)
        bbu, _, bbl = self.bollinger(df)
        bbu_v = self.safe_val(bbu, p * 1.02)
        bbl_v = self.safe_val(bbl, p * 0.98)
        av = self.safe_val(self.atr(df), p * 0.01)
        obv_slope = self.safe_val(self.obv(df).diff(5), 0)
        adx_now = self.safe_val(self.adx(df), 20)
        e20 = self.safe_val(self.ema(df, 20), p)
        e50 = self.safe_val(self.ema(df, 50), p)
        e200 = self.safe_val(self.ema(df, 200), p)
        rl, regime, _ = self.market_regime(df)
        score = 0
        reasons = []
        if rv < 30:
            score += 2.5
            reasons.append("RSI超賣(" + str(round(rv, 1)) + ")")
        elif rv < 40:
            score += 1.0
            reasons.append("RSI偏低")
        elif rv > 70:
            score -= 2.5
            reasons.append("RSI超買(" + str(round(rv, 1)) + ")")
        elif rv > 60:
            score -= 1.0
            reasons.append("RSI偏高")
        if kv < 20 and kv > dv:
            score += 1.5
            reasons.append("StochRSI底部金叉")
        elif kv > 80 and kv < dv:
            score -= 1.5
            reasons.append("StochRSI頂部死叉")
        if ml_v > sl_v and hv > 0:
            score += 2
            reasons.append("MACD金叉")
        elif ml_v < sl_v and hv < 0:
            score -= 2
            reasons.append("MACD死叉")
        if p < bbl_v:
            score += 2
            reasons.append("跌破布林下軌")
        elif p > bbu_v:
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
        if fg_val <= 20:
            score += 1.5
            reasons.append("極度恐懼(逆向做多)")
        elif fg_val >= 80:
            score -= 1.5
            reasons.append("極度貪婪(逆向做空)")
        total = score + news_score * 2
        if total >= 4:
            direction = "做多 🟢"
            den = "LONG"
        elif total <= -4:
            direction = "做空 🔴"
            den = "SHORT"
        else:
            direction = "觀望 🟡"
            den = "NEUTRAL"
        strength = min(abs(total) / 10 * 100, 100)
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
        rr = round(abs(tp1 - entry) / (abs(sl - entry) + 1e-9), 2)
        wr = 0.55 if strength > 70 else 0.50 if strength > 50 else 0.45
        kelly = max(0, (wr - (1 - wr) / rr)) * 100 if rr > 0 else 0
        return {
            "price": p, "direction": direction, "direction_en": den,
            "strength": strength, "reasons": reasons[:5],
            "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr,
            "pos": round(min(kelly, 10), 1),
            "rsi": round(rv, 1), "sk": round(kv, 1), "sd": round(dv, 1),
            "mh": round(hv, 6), "adx": round(adx_now, 1),
            "bbu": round(bbu_v, 4), "bbl": round(bbl_v, 4),
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
                return_exceptions=True
            )
            if isinstance(results[0], Exception):
                return "❌ 抓取失敗：" + str(results[0])
            df1h = results[0]
            df4h = results[1] if not isinstance(results[1], Exception) else df1h
            ticker = results[2] if not isinstance(results[2], Exception) else {}
            obl = results[3][0] if not isinstance(results[3], Exception) else "📒 不可用"
            sig = self.generate_signal(df1h)
            sig4h = self.generate_signal(df4h)
            fibs = self.fibonacci(df1h)
            vtl = self.volume_trend(df1h)
            chg = float(ticker.get("priceChangePercent", 0))
            icon = "📈" if chg >= 0 else "📉"
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            p = sig["price"]
            fib_sup = max(((k, v) for k, v in fibs.items() if v < p),
                          key=lambda x: x[1], default=None)
            fib_res = min(((k, v) for k, v in fibs.items() if v > p),
                          key=lambda x: x[1], default=None)
            r = "🔍 *" + symbol + "* | " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━\n"
            r += "💰 現價 `" + str(p) + "` " + icon + " `" + str(round(chg, 2)) + "%`\n"
            r += "🌊 結構 " + sig["rl"] + " | ADX `" + str(sig["adx"]) + "`\n"
            r += "📊 訂單簿 " + obl + " | 量能 " + vtl + "\n\n"
            r += "*━━ 📊 指標 ━━*\n"
            r += "• RSI `" + str(sig["rsi"]) + "` | StochRSI `" + str(sig["sk"]) + "/" + str(sig["sd"]) + "`\n"
            r += "• MACD柱 `" + str(sig["mh"]) + "` | OBV " + sig["obv"] + "\n"
            r += "• 布林 `" + str(sig["bbu"]) + " / " + str(sig["bbl"]) + "`\n"
            r += "• EMA20/50/200 `" + str(sig["e20"]) + "/" + str(sig["e50"]) + "/" + str(sig["e200"]) + "`\n"
            r += "• ATR `" + str(sig["atr"]) + "`\n\n"
            r += "*━━ 🎯 Fibonacci ━━*\n"
            if fib_sup:
                r += "• 支撐 " + fib_sup[0] + " `" + str(fib_sup[1]) + "`\n"
            if fib_res:
                r += "• 阻力 " + fib_res[0] + " `" + str(fib_res[1]) + "`\n"
            r += "\n━━━━━━━━━━━━━━━━━━\n"
            if sig["direction_en"] != "NEUTRAL":
                if sig["direction_en"] == sig4h["direction_en"]:
                    conf = "✅ 1H+4H一致"
                else:
                    conf = "⚠️ 週期分歧"
                r += "🎯 *" + sig["direction"] + "* | 強度 `" + str(round(sig["strength"])) + "%`\n"
                r += "📋 " + " | ".join(sig["reasons"][:3]) + "\n\n"
                r += "🎯 進場 `" + str(sig["entry"]) + "`\n"
                r += "🏁 止盈1 `" + str(sig["tp1"]) + "`\n"
                r += "🏆 止盈2 `" + str(sig["tp2"]) + "`\n"
                r += "🛑 止損 `" + str(sig["sl"]) + "`\n"
                r += "⚖️ 風報 `1:" + str(sig["rr"]) + "` | 倉位 `" + str(sig["pos"]) + "%`\n\n"
                r += "📅 4H " + sig4h["direction"] + " | " + conf
            else:
                r += "🟡 *建議觀望* (強度 " + str(round(sig["strength"])) + "%)\n"
                r += "📋 " + " | ".join(sig["reasons"][:3])
            r += "\n\n⚠️ _僅供參考，非投資建議_"
            return r
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    async def get_market_sentiment(self):
        try:
            results = await asyncio.gather(
                self.fetch_news(),
                self.fetch_fear_greed(),
                self.fetch_btc_dominance(),
                self.fetch_ohlcv("BTC/USDT", "1h", 100),
                self.fetch_ohlcv("ETH/USDT", "1h", 100),
                return_exceptions=True
            )
            news = results[0] if not isinstance(results[0], Exception) else []
            fgl, fgv = results[1] if not isinstance(results[1], Exception) else ("⚪ 不可用", 50)
            btc_dom = results[2] if not isinstance(results[2], Exception) else None
            btc_df = results[3] if not isinstance(results[3], Exception) else None
            eth_df = results[4] if not isinstance(results[4], Exception) else None
            score, label, headlines = self.sentiment(news)
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            r = "🌐 *加密市場情緒總覽*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━\n\n"
            r += "*━━ 🌡 整體溫度 ━━*\n"
            r += "• 恐懼貪婪指數: " + fgl + "\n"
            r += "• 新聞情緒: " + label + " (`" + str(round(score, 2)) + "`)\n"
            if btc_dom:
                r += "• BTC 市占率: `" + str(btc_dom) + "%`\n"
            r += "\n*━━ 📊 市場龍頭 ━━*\n"
            if btc_df is not None:
                rl, _, _ = self.market_regime(btc_df)
                p = float(btc_df["close"].iloc[-1])
                r += "• BTC `" + str(round(p, 2)) + "` " + rl + "\n"
            if eth_df is not None:
                rl, _, _ = self.market_regime(eth_df)
                p = float(eth_df["close"].iloc[-1])
                r += "• ETH `" + str(round(p, 2)) + "` " + rl + "\n"
            r += "\n*━━ 📰 最新時事 ━━*\n"
            if headlines:
                for i, h in enumerate(headlines[:6], 1):
                    r += str(i) + ". " + h + "\n"
            else:
                r += "_暫時無法取得新聞_\n"
            r += "\n━━━━━━━━━━━━━━━━━━\n"
            r += "💡 *判讀建議：*\n"
            if fgv <= 25 and score < -0.2:
                r += "🟢 市場恐慌，可逢低分批佈局"
            elif fgv >= 75 and score > 0.2:
                r += "🔴 市場過熱，建議獲利了結"
            elif fgv <= 40:
                r += "🔵 偏冷靜，可關注突破信號"
            elif fgv >= 60:
                r += "🟡 偏熱，謹慎追高"
            else:
                r += "⚪ 中性，等待方向"
            return r
        except Exception as e:
            return "❌ 情緒分析失敗：" + str(e)

    async def trend_watch(self, symbols):
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        r = "🔭 *趨勢總覽* | " + now + "\n"
        r += "━━━━━━━━━━━━━━━━━━\n"
        for symbol in symbols:
            try:
                results = await asyncio.gather(
                    self.fetch_ohlcv(symbol, "1h", 200),
                    self.fetch_ticker(symbol),
                    return_exceptions=True
                )
                if isinstance(results[0], Exception):
                    r += "❌ " + symbol + "\n"
                    continue
                df = results[0]
                ticker = results[1] if not isinstance(results[1], Exception) else {}
                rl, _, adx_v = self.market_regime(df)
                chg = float(ticker.get("priceChangePercent", 0))
                price = float(df["close"].iloc[-1])
                icon = "📈" if chg >= 0 else "📉"
                r += icon + " *" + symbol + "* `" + str(round(price, 2)) + "` `" + str(round(chg, 1)) + "%`\n"
                r += "   " + rl + " ADX:`" + str(round(adx_v)) + "`\n"
            except Exception:
                r += "❌ " + symbol + "\n"
        return r