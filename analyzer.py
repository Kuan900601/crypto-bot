import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta


class CryptoAnalyzer:

    # ── 安全取值 ──
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

    # ── 數據抓取（並行優化）──
    # Binance 多端點備援（解決地區限制）
    BINANCE_HOSTS = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://data-api.binance.vision",
    ]

    async def fetch_ohlcv(self, session, symbol, timeframe="1h", limit=200):
        pair = symbol.replace("/", "")
        last_err = None
        for host in self.BINANCE_HOSTS:
            try:
                url = host + "/api/v3/klines?symbol=" + pair + "&interval=" + timeframe + "&limit=" + str(limit)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 451 or r.status == 403:
                        last_err = "地區限制 " + str(r.status)
                        continue
                    data = await r.json()
                if isinstance(data, dict):
                    code = data.get("code", 0)
                    msg = data.get("msg", "未知錯誤")
                    if code == -1121 or "Invalid symbol" in str(msg):
                        raise ValueError("幣種不存在於 Binance：" + symbol)
                    last_err = str(msg)
                    continue
                cols = ["timestamp","open","high","low","close","volume","close_time","qv","tr","tbb","tbq","ig"]
                df = pd.DataFrame(data, columns=cols)
                for c in ["open","high","low","close","volume"]:
                    df[c] = df[c].astype(float)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                return df
            except ValueError:
                raise
            except Exception as e:
                last_err = str(e)
                continue
        raise ValueError("無法取得數據：" + (last_err or "所有端點失敗"))

    async def fetch_ticker(self, session, symbol):
        pair = symbol.replace("/", "")
        for host in self.BINANCE_HOSTS:
            try:
                url = host + "/api/v3/ticker/24hr?symbol=" + pair
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status >= 400:
                        continue
                    return await r.json()
            except Exception:
                continue
        return {}

    async def fetch_orderbook(self, session, symbol):
        pair = symbol.replace("/", "")
        for host in self.BINANCE_HOSTS:
            try:
                url = host + "/api/v3/depth?symbol=" + pair + "&limit=50"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status >= 400:
                        continue
                    data = await r.json()
                bids = sum(float(b[1]) for b in data.get("bids", []))
                asks = sum(float(a[1]) for a in data.get("asks", []))
                ratio = bids / asks if asks > 0 else 1
                if ratio > 1.5:
                    return "💚 強力買壓 (" + str(round(ratio, 2)) + "x)", ratio
                elif ratio > 1.2:
                    return "📗 買壓較強 (" + str(round(ratio, 2)) + "x)", ratio
                elif ratio < 0.67:
                    return "💔 強力賣壓 (" + str(round(ratio, 2)) + "x)", ratio
                elif ratio < 0.83:
                    return "📕 賣壓較強 (" + str(round(ratio, 2)) + "x)", ratio
                else:
                    return "📒 多空均衡 (" + str(round(ratio, 2)) + "x)", ratio
            except Exception:
                continue
        return "📒 不可用", 1.0

    async def fetch_fear_greed(self, session):
        try:
            async with session.get("https://api.alternative.me/fng/?limit=2",
                                    timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
            now_val = int(data["data"][0]["value"])
            yesterday = int(data["data"][1]["value"])
            label = data["data"][0]["value_classification"]
            change = now_val - yesterday
            arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
            if now_val >= 75:
                icon = "🟠"
            elif now_val >= 55:
                icon = "🟡"
            elif now_val >= 45:
                icon = "⚪"
            elif now_val >= 25:
                icon = "🔵"
            else:
                icon = "🔴"
            txt = icon + " " + str(now_val) + "/100 " + arrow + str(abs(change)) + " (" + label + ")"
            return txt, now_val
        except Exception:
            return "⚪ 不可用", 50

    async def fetch_global(self, session):
        try:
            async with session.get("https://api.coingecko.com/api/v3/global",
                                    timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
            d = data["data"]
            btc_dom = round(d["market_cap_percentage"]["btc"], 2)
            eth_dom = round(d["market_cap_percentage"]["eth"], 2)
            mcap_change = round(d.get("market_cap_change_percentage_24h_usd", 0), 2)
            total_mcap = d["total_market_cap"]["usd"] / 1e9
            return {
                "btc_dom": btc_dom,
                "eth_dom": eth_dom,
                "mcap_change": mcap_change,
                "total_mcap": round(total_mcap, 1)
            }
        except Exception:
            return None

    async def fetch_news(self, session):
        url = "https://cryptopanic.com/api/free/v1/posts/?auth_token=public&kind=news&public=true"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
                return data.get("results", [])[:15]
        except Exception:
            return []

    # ── 技術指標 ──
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

    # ── 多重支撐阻力分析 ──
    def pivot_sr(self, df, lookback=50):
        """經典樞軸點"""
        r = df.tail(lookback)
        high = float(r["high"].max())
        low = float(r["low"].min())
        close = float(r["close"].iloc[-1])
        pivot = (high + low + close) / 3
        return {
            "R3": round(high + 2*(pivot - low), 4),
            "R2": round(pivot + (high - low), 4),
            "R1": round(2*pivot - low, 4),
            "P": round(pivot, 4),
            "S1": round(2*pivot - high, 4),
            "S2": round(pivot - (high - low), 4),
            "S3": round(low - 2*(high - pivot), 4),
        }

    def swing_sr(self, df, window=5):
        """擺動高低點 - 真實壓力位"""
        try:
            r = df.tail(150).reset_index(drop=True)
            highs, lows = [], []
            for i in range(window, len(r) - window):
                h = r["high"].iloc[i]
                l = r["low"].iloc[i]
                if h == r["high"].iloc[i-window:i+window+1].max():
                    highs.append(round(float(h), 4))
                if l == r["low"].iloc[i-window:i+window+1].min():
                    lows.append(round(float(l), 4))
            current = float(r["close"].iloc[-1])
            res = sorted([h for h in highs if h > current])[:3]
            sup = sorted([l for l in lows if l < current], reverse=True)[:3]
            return res, sup
        except Exception:
            return [], []

    def fib_sr(self, df, lookback=100):
        """Fibonacci"""
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

    def volume_trend(self, df, p=20):
        try:
            avg = float(df["volume"].rolling(p).mean().iloc[-1])
            curr = float(df["volume"].iloc[-1])
            r = curr / avg if avg > 0 else 1
            if r > 2.5:
                return "🔥🔥 異常爆量 (" + str(round(r, 1)) + "x)"
            elif r > 1.8:
                return "🔥 爆量 (" + str(round(r, 1)) + "x)"
            elif r > 1.3:
                return "🟡 放量 (" + str(round(r, 1)) + "x)"
            elif r > 0.7:
                return "🟢 正常 (" + str(round(r, 1)) + "x)"
            else:
                return "⚪ 縮量 (" + str(round(r, 1)) + "x)"
        except Exception:
            return "📒 一般"

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
              "buy","rise","recover","bullish","etf","approve","institutional",
              "moon","launch","upgrade","partnership","investment"}
    BEAR_W = {"bear","crash","dump","drop","sell","ban","hack","lawsuit",
              "fear","decline","bearish","sec","liquidat","collapse","warning",
              "fraud","ponzi","exploit","vulnerability","scam"}

    def sentiment(self, news):
        score, items = 0, []
        for item in news[:15]:
            title = item.get("title", "")
            t = title.lower()
            published = item.get("published_at", "")
            domain = item.get("source", {}).get("domain", "") if isinstance(item.get("source"), dict) else ""
            bull_count = sum(1 for w in self.BULL_W if w in t)
            bear_count = sum(1 for w in self.BEAR_W if w in t)
            item_score = (bull_count - bear_count) * 0.1
            score += item_score
            if item_score > 0.05:
                emoji = "📗"
            elif item_score < -0.05:
                emoji = "📕"
            else:
                emoji = "📒"
            items.append({
                "title": title[:80],
                "emoji": emoji,
                "domain": domain,
                "published": published
            })
        score = max(-1.0, min(1.0, score))
        if score > 0.3:
            label = "📗 偏多"
        elif score < -0.3:
            label = "📕 偏空"
        else:
            label = "📒 中性"
        return score, label, items[:8]

    def format_published(self, iso):
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            diff = now - dt
            mins = int(diff.total_seconds() / 60)
            if mins < 60:
                return str(mins) + "分鐘前"
            hrs = mins // 60
            if hrs < 24:
                return str(hrs) + "小時前"
            return str(hrs // 24) + "天前"
        except Exception:
            return ""

    # ── 信號生成 ──
    def generate_signal(self, df, fg_val=50):
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
        elif rv > 70:
            score -= 2.5
            reasons.append("RSI超買(" + str(round(rv, 1)) + ")")
        elif rv > 60:
            score -= 1.0
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
        elif obv_slope < 0:
            score -= 1
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

    # ── 完整分析 ──
    async def full_analysis(self, symbol):
        try:
            async with aiohttp.ClientSession() as session:
                results = await asyncio.gather(
                    self.fetch_ohlcv(session, symbol, "1h", 250),
                    self.fetch_ohlcv(session, symbol, "4h", 150),
                    self.fetch_ticker(session, symbol),
                    self.fetch_orderbook(session, symbol),
                    self.fetch_fear_greed(session),
                    return_exceptions=True
                )
            if isinstance(results[0], Exception):
                return "❌ 抓取失敗：" + str(results[0])
            df1h = results[0]
            df4h = results[1] if not isinstance(results[1], Exception) else df1h
            ticker = results[2] if not isinstance(results[2], Exception) else {}
            obl, ob_ratio = results[3] if not isinstance(results[3], Exception) else ("📒 不可用", 1.0)
            fgl, fgv = results[4] if not isinstance(results[4], Exception) else ("⚪", 50)
            sig = self.generate_signal(df1h, fgv)
            sig4h = self.generate_signal(df4h, fgv)
            piv = self.pivot_sr(df1h)
            sw_res, sw_sup = self.swing_sr(df1h)
            fibs = self.fib_sr(df1h)
            vtl = self.volume_trend(df1h)
            chg = float(ticker.get("priceChangePercent", 0))
            high24 = float(ticker.get("highPrice", 0))
            low24 = float(ticker.get("lowPrice", 0))
            vol24 = float(ticker.get("quoteVolume", 0)) / 1e6
            icon = "📈" if chg >= 0 else "📉"
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            p = sig["price"]
            r = "🔍 *" + symbol + " 深度分析* | " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💰 現價 `" + str(p) + "` " + icon + " `" + str(round(chg, 2)) + "%`\n"
            r += "📊 24H 區間 `" + str(low24) + " - " + str(high24) + "`\n"
            r += "💵 24H 成交額 `$" + str(round(vol24, 1)) + "M`\n"
            r += "🌊 結構 " + sig["rl"] + " | ADX `" + str(sig["adx"]) + "`\n"
            r += "📖 訂單簿 " + obl + "\n"
            r += "📦 量能 " + vtl + "\n"
            r += "😱 市場情緒 " + fgl + "\n\n"
            r += "*━━ 📊 技術指標 ━━*\n"
            r += "• RSI(14) `" + str(sig["rsi"]) + "`"
            if sig["rsi"] > 70:
                r += " ⚠️超買"
            elif sig["rsi"] < 30:
                r += " ⚠️超賣"
            r += "\n"
            r += "• StochRSI K/D `" + str(sig["sk"]) + "/" + str(sig["sd"]) + "`\n"
            r += "• MACD柱 `" + str(sig["mh"]) + "`\n"
            r += "• 布林通道 `" + str(sig["bbu"]) + " / " + str(sig["bbl"]) + "`\n"
            r += "• EMA 20/50/200 `" + str(sig["e20"]) + "/" + str(sig["e50"]) + "/" + str(sig["e200"]) + "`\n"
            r += "• OBV " + sig["obv"] + " | ATR `" + str(sig["atr"]) + "`\n\n"
            r += "*━━ 🎯 支撐阻力（樞軸點）━━*\n"
            r += "• R3 `" + str(piv["R3"]) + "` | R2 `" + str(piv["R2"]) + "` | R1 `" + str(piv["R1"]) + "`\n"
            r += "• Pivot `" + str(piv["P"]) + "`\n"
            r += "• S1 `" + str(piv["S1"]) + "` | S2 `" + str(piv["S2"]) + "` | S3 `" + str(piv["S3"]) + "`\n\n"
            if sw_res or sw_sup:
                r += "*━━ 🎯 擺動高低點（實際阻力）━━*\n"
                if sw_res:
                    r += "• 阻力 `" + " / ".join(str(x) for x in sw_res) + "`\n"
                if sw_sup:
                    r += "• 支撐 `" + " / ".join(str(x) for x in sw_sup) + "`\n"
                r += "\n"
            r += "*━━ 🔢 Fibonacci 回撤 ━━*\n"
            for k, v in fibs.items():
                marker = " ⭐" if abs(v - p) / p < 0.005 else ""
                r += "• " + k + " `" + str(v) + "`" + marker + "\n"
            r += "\n━━━━━━━━━━━━━━━━━━━━\n"
            if sig["direction_en"] != "NEUTRAL":
                if sig["direction_en"] == sig4h["direction_en"]:
                    conf = "✅ 1H+4H 一致 (信號可靠)"
                else:
                    conf = "⚠️ 多空週期分歧 (謹慎)"
                r += "🎯 *方向：" + sig["direction"] + "*\n"
                r += "💪 信號強度 `" + str(round(sig["strength"])) + "%`\n"
                r += "📋 " + " | ".join(sig["reasons"][:3]) + "\n\n"
                r += "🎯 進場 `" + str(sig["entry"]) + "`\n"
                r += "🏁 止盈 1 `" + str(sig["tp1"]) + "`\n"
                r += "🏆 止盈 2 `" + str(sig["tp2"]) + "`\n"
                r += "🛑 止損 `" + str(sig["sl"]) + "`\n"
                r += "⚖️ 風報比 `1 : " + str(sig["rr"]) + "`\n"
                r += "💼 建議倉位 `" + str(sig["pos"]) + "%` 資金\n\n"
                r += "📅 4H 確認 " + sig4h["direction"] + "\n"
                r += conf
            else:
                r += "🟡 *建議觀望* (強度 " + str(round(sig["strength"])) + "%)\n"
                if sig["reasons"]:
                    r += "📋 " + " | ".join(sig["reasons"][:3])
                else:
                    r += "📋 信號不明確，等待方向確認"
            r += "\n\n⚠️ _僅供參考，非投資建議_"
            return r
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    # ── K線支撐阻力（多時間框架）──
    async def kline_sr_analysis(self, symbol):
        try:
            async with aiohttp.ClientSession() as session:
                results = await asyncio.gather(
                    self.fetch_ohlcv(session, symbol, "1m", 200),
                    self.fetch_ohlcv(session, symbol, "15m", 200),
                    self.fetch_ohlcv(session, symbol, "1h", 200),
                    self.fetch_ohlcv(session, symbol, "4h", 200),
                    self.fetch_ohlcv(session, symbol, "1d", 200),
                    self.fetch_ticker(session, symbol),
                    return_exceptions=True
                )
            if isinstance(results[0], Exception):
                return "❌ 抓取失敗"
            timeframes = [
                ("1分K", results[0], 30),
                ("15分K", results[1], 50),
                ("1小時K", results[2], 50),
                ("4小時K", results[3], 50),
                ("日K", results[4], 50),
            ]
            ticker = results[5] if not isinstance(results[5], Exception) else {}
            chg = float(ticker.get("priceChangePercent", 0))
            current_price = float(results[2]["close"].iloc[-1]) if not isinstance(results[2], Exception) else 0
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            r = "📊 *" + symbol + " 多週期支撐阻力分析*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💰 現價 `" + str(current_price) + "` "
            r += "📈" if chg >= 0 else "📉"
            r += " `" + str(round(chg, 2)) + "%`\n\n"
            for name, df, lookback in timeframes:
                if isinstance(df, Exception):
                    r += "❌ " + name + " 失敗\n\n"
                    continue
                piv = self.pivot_sr(df, lookback)
                sw_res, sw_sup = self.swing_sr(df)
                regime, _, adx_v = self.market_regime(df)
                r += "*━━ ⏰ " + name + " ━━*\n"
                r += "趨勢 " + regime + " | ADX `" + str(round(adx_v)) + "`\n"
                r += "🔴 阻力 R1 `" + str(piv["R1"]) + "` | R2 `" + str(piv["R2"]) + "`\n"
                r += "⚪ Pivot `" + str(piv["P"]) + "`\n"
                r += "🟢 支撐 S1 `" + str(piv["S1"]) + "` | S2 `" + str(piv["S2"]) + "`\n"
                if sw_res:
                    r += "🎯 關鍵阻力 `" + " / ".join(str(x) for x in sw_res[:2]) + "`\n"
                if sw_sup:
                    r += "🎯 關鍵支撐 `" + " / ".join(str(x) for x in sw_sup[:2]) + "`\n"
                r += "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💡 *判讀建議*\n"
            r += "• 多週期支撐重疊 → 強支撐\n"
            r += "• 多週期阻力重疊 → 強阻力\n"
            r += "• 短週期突破日K阻力 → 強勢\n"
            r += "• 跌破日K支撐 → 弱勢"
            return r
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    # ── 市場情緒（強化版）──
    async def get_market_sentiment(self):
        try:
            async with aiohttp.ClientSession() as session:
                results = await asyncio.gather(
                    self.fetch_news(session),
                    self.fetch_fear_greed(session),
                    self.fetch_global(session),
                    self.fetch_ohlcv(session, "BTC/USDT", "1h", 100),
                    self.fetch_ohlcv(session, "ETH/USDT", "1h", 100),
                    self.fetch_ticker(session, "BTC/USDT"),
                    self.fetch_ticker(session, "ETH/USDT"),
                    return_exceptions=True
                )
            news = results[0] if not isinstance(results[0], Exception) else []
            fgl, fgv = results[1] if not isinstance(results[1], Exception) else ("⚪ 不可用", 50)
            global_data = results[2] if not isinstance(results[2], Exception) else None
            btc_df = results[3] if not isinstance(results[3], Exception) else None
            eth_df = results[4] if not isinstance(results[4], Exception) else None
            btc_ticker = results[5] if not isinstance(results[5], Exception) else {}
            eth_ticker = results[6] if not isinstance(results[6], Exception) else {}
            score, label, items = self.sentiment(news)
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            r = "🌐 *加密市場情緒總覽*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n\n"
            r += "*━━ 🌡 市場溫度 ━━*\n"
            r += "• 恐懼貪婪 " + fgl + "\n"
            r += "• 新聞情緒 " + label + " (`" + str(round(score, 2)) + "`)\n"
            if global_data:
                r += "• 總市值 `$" + str(global_data["total_mcap"]) + "B`"
                ch = global_data["mcap_change"]
                r += " " + ("📈" if ch >= 0 else "📉") + " `" + str(ch) + "%`\n"
                r += "• BTC 市占 `" + str(global_data["btc_dom"]) + "%`"
                r += " | ETH 市占 `" + str(global_data["eth_dom"]) + "%`\n"
            r += "\n*━━ 📊 龍頭走勢 ━━*\n"
            if btc_df is not None:
                rl, _, _ = self.market_regime(btc_df)
                p = float(btc_df["close"].iloc[-1])
                bchg = float(btc_ticker.get("priceChangePercent", 0))
                ic = "📈" if bchg >= 0 else "📉"
                r += "• BTC `" + str(round(p, 2)) + "` " + ic + " `" + str(round(bchg, 2)) + "%` " + rl + "\n"
            if eth_df is not None:
                rl, _, _ = self.market_regime(eth_df)
                p = float(eth_df["close"].iloc[-1])
                echg = float(eth_ticker.get("priceChangePercent", 0))
                ic = "📈" if echg >= 0 else "📉"
                r += "• ETH `" + str(round(p, 2)) + "` " + ic + " `" + str(round(echg, 2)) + "%` " + rl + "\n"
            r += "\n*━━ 📰 即時新聞時事 ━━*\n"
            if items:
                for i, item in enumerate(items[:8], 1):
                    time_ago = self.format_published(item.get("published", ""))
                    line = item["emoji"] + " " + item["title"]
                    if time_ago:
                        line += " _(" + time_ago + ")_"
                    r += str(i) + ". " + line + "\n"
            else:
                r += "_暫時無法取得新聞_\n"
            r += "\n━━━━━━━━━━━━━━━━━━━━\n"
            r += "💡 *市場判讀*\n"
            if fgv <= 25 and score < -0.2:
                r += "🟢 市場恐慌，逢低分批佈局機會\n"
                r += "策略：價值幣種定投，等反彈"
            elif fgv >= 75 and score > 0.2:
                r += "🔴 市場過熱，獲利了結\n"
                r += "策略：減倉至 30%，留現金"
            elif fgv <= 40 and score > 0:
                r += "🔵 偏冷靜，可關注突破信號\n"
                r += "策略：突破關鍵阻力時跟進"
            elif fgv >= 60 and score < 0:
                r += "🟡 情緒分歧，謹慎觀察\n"
                r += "策略：減倉觀望，等方向明確"
            else:
                r += "⚪ 中性盤整\n"
                r += "策略：等突破關鍵價位再行動"
            return r
        except Exception as e:
            return "❌ 情緒分析失敗：" + str(e)

    # ── 趨勢總覽（專業版）──
    async def trend_watch(self, symbols):
        try:
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            r = "🔭 *市場趨勢總覽 — 專業掃描*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n\n"
            async with aiohttp.ClientSession() as session:
                tasks = []
                for s in symbols:
                    tasks.append(self.fetch_ohlcv(session, s, "1h", 200))
                    tasks.append(self.fetch_ticker(session, s))
                results = await asyncio.gather(*tasks, return_exceptions=True)
            strong_bull = []
            bull = []
            bear = []
            strong_bear = []
            ranging = []
            for i, sym in enumerate(symbols):
                df = results[i*2]
                ticker = results[i*2+1]
                if isinstance(df, Exception):
                    continue
                ticker = ticker if not isinstance(ticker, Exception) else {}
                rl, regime, adx_v = self.market_regime(df)
                chg = float(ticker.get("priceChangePercent", 0))
                price = float(df["close"].iloc[-1])
                rsi_v = self.safe_val(self.rsi(df), 50)
                vol = float(ticker.get("quoteVolume", 0)) / 1e6
                info = {
                    "symbol": sym,
                    "price": price,
                    "chg": chg,
                    "adx": round(adx_v),
                    "rsi": round(rsi_v, 1),
                    "vol": round(vol, 1),
                    "rl": rl,
                }
                if regime == "STRONG_BULL":
                    strong_bull.append(info)
                elif regime == "BULL":
                    bull.append(info)
                elif regime == "STRONG_BEAR":
                    strong_bear.append(info)
                elif regime == "BEAR":
                    bear.append(info)
                else:
                    ranging.append(info)
            def fmt(coin):
                line = "• *" + coin["symbol"] + "* `" + str(coin["price"]) + "` "
                line += ("📈" if coin["chg"] >= 0 else "📉") + " `" + str(round(coin["chg"], 1)) + "%`\n"
                line += "  ADX:`" + str(coin["adx"]) + "` RSI:`" + str(coin["rsi"]) + "` Vol:`$" + str(coin["vol"]) + "M`\n"
                return line
            if strong_bull:
                r += "🚀 *強多頭*\n"
                for c in strong_bull:
                    r += fmt(c)
                r += "\n"
            if bull:
                r += "📈 *多頭*\n"
                for c in bull:
                    r += fmt(c)
                r += "\n"
            if ranging:
                r += "↔️ *震盪整理*\n"
                for c in ranging:
                    r += fmt(c)
                r += "\n"
            if bear:
                r += "📉 *空頭*\n"
                for c in bear:
                    r += fmt(c)
                r += "\n"
            if strong_bear:
                r += "💥 *強空頭*\n"
                for c in strong_bear:
                    r += fmt(c)
                r += "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💡 *操作建議*\n"
            if len(strong_bull) > len(strong_bear):
                r += "🟢 市場偏強：以做多為主，回調進場"
            elif len(strong_bear) > len(strong_bull):
                r += "🔴 市場偏弱：以做空為主，反彈進空"
            else:
                r += "⚪ 多空分歧：嚴選強勢標的"
            return r
        except Exception as e:
            return "❌ 趨勢分析失敗：" + str(e)