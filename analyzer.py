import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from config import Config

class CryptoAnalyzer:

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> pd.DataFrame:
        pair = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    async def fetch_price(self, symbol: str) -> dict:
        pair = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={pair}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return await resp.json()

    async def fetch_news(self) -> list:
        url = "https://cryptopanic.com/api/free/v1/posts/?auth_token=public&kind=news&public=true"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    data = await resp.json()
                    return data.get("results", [])[:15]
        except Exception:
            return []

    def calc_rsi(self, df, period=14):
        delta = df["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def calc_macd(self, df, fast=12, slow=26, signal=9):
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line, macd_line - signal_line

    def calc_bollinger(self, df, period=20, std=2.0):
        sma = df["close"].rolling(period).mean()
        std_dev = df["close"].rolling(period).std()
        return sma + std * std_dev, sma, sma - std * std_dev

    def calc_atr(self, df, period=14):
        high, low, prev = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat([(high-low), (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    def calc_ema(self, df, period):
        return df["close"].ewm(span=period, adjust=False).mean()

    def calc_volume_trend(self, df, period=20):
        avg = df["volume"].rolling(period).mean().iloc[-1]
        curr = df["volume"].iloc[-1]
        ratio = curr / avg if avg > 0 else 1
        if ratio > 1.5: return f"🔴 爆量 ({ratio:.1f}x)"
        elif ratio > 1.2: return f"🟡 放量 ({ratio:.1f}x)"
        else: return f"🟢 縮量 ({ratio:.1f}x)"

    def support_resistance(self, df, lookback=50):
        r = df.tail(lookback)
        pivot = (r["high"].max() + r["low"].min() + r["close"].iloc[-1]) / 3
        r1 = 2*pivot - r["low"].min()
        s1 = 2*pivot - r["high"].max()
        r2 = pivot + (r["high"].max() - r["low"].min())
        s2 = pivot - (r["high"].max() - r["low"].min())
        return round(s2,4), round(s1,4), round(r1,4), round(r2,4)

    BULLISH = {"bull","rally","surge","gain","pump","breakout","ath","adoption","buy","rise","recover","bullish","ETF","moon"}
    BEARISH = {"bear","crash","dump","drop","sell","ban","hack","lawsuit","fear","decline","bearish","SEC","liquidat","collapse"}

    def analyze_news_sentiment(self, news_list):
        score = 0
        headlines = []
        for item in news_list[:10]:
            title = item.get("title","").lower()
            headlines.append(item.get("title","")[:80])
            score += (sum(1 for w in self.BULLISH if w in title) - sum(1 for w in self.BEARISH if w in title)) * 0.1
        score = max(-1.0, min(1.0, score))
        label = "📗 偏多" if score > 0.3 else ("📕 偏空" if score < -0.3 else "📒 中性")
        return score, label, headlines[:5]

    def generate_signal(self, df, news_score):
        rsi = self.calc_rsi(df)
        macd, sig_line, hist = self.calc_macd(df)
        bb_upper, bb_mid, bb_lower = self.calc_bollinger(df)
        atr = self.calc_atr(df)
        ema20 = self.calc_ema(df, 20)
        ema50 = self.calc_ema(df, 50)
        ema200 = self.calc_ema(df, 200)
        price = df["close"].iloc[-1]
        rsi_val = rsi.iloc[-1]
        hist_val = hist.iloc[-1]
        atr_val = atr.iloc[-1]
        tech_score = 0
        reasons = []
        if rsi_val < 30: tech_score += 2; reasons.append(f"RSI超賣({rsi_val:.1f})")
        elif rsi_val < 45: tech_score += 1; reasons.append(f"RSI偏低({rsi_val:.1f})")
        elif rsi_val > 70: tech_score -= 2; reasons.append(f"RSI超買({rsi_val:.1f})")
        elif rsi_val > 55: tech_score -= 1; reasons.append(f"RSI偏高({rsi_val:.1f})")
        if macd.iloc[-1] > sig_line.iloc[-1] and hist_val > 0: tech_score += 2; reasons.append("MACD金叉")
        elif macd.iloc[-1] < sig_line.iloc[-1] and hist_val < 0: tech_score -= 2; reasons.append("MACD死叉")
        if price < bb_lower.iloc[-1]: tech_score += 1.5; reasons.append("跌破布林下軌")
        elif price > bb_upper.iloc[-1]: tech_score -= 1.5; reasons.append("突破布林上軌")
        if price > ema20.iloc[-1] > ema50.iloc[-1] > ema200.iloc[-1]: tech_score += 2; reasons.append("EMA多頭排列")
        elif price < ema20.iloc[-1] < ema50.iloc[-1] < ema200.iloc[-1]: tech_score -= 2; reasons.append("EMA空頭排列")
        total = tech_score + news_score * 2
        if total >= 3: direction, d_en = "做多 🟢", "LONG"
        elif total <= -3: direction, d_en = "做空 🔴", "SHORT"
        else: direction, d_en = "觀望 🟡", "NEUTRAL"
        strength = min(abs(total) / 7 * 100, 100)
        if d_en == "LONG":
            entry = round(price * 0.998, 4)
            tp1 = round(price + atr_val * 1.5, 4)
            tp2 = round(price + atr_val * 3.0, 4)
            sl  = round(price - atr_val * 1.5, 4)
        elif d_en == "SHORT":
            entry = round(price * 1.002, 4)
            tp1 = round(price - atr_val * 1.5, 4)
            tp2 = round(price - atr_val * 3.0, 4)
            sl  = round(price + atr_val * 1.5, 4)
        else:
            entry = tp1 = tp2 = sl = price
        rr = round(abs(tp1-entry)/abs(sl-entry), 2) if abs(sl-entry) > 0 else 0
        return {"price":price,"direction":direction,"direction_en":d_en,"strength":strength,
                "reasons":reasons,"entry":entry,"tp1":tp1,"tp2":tp2,"sl":sl,"rr":rr,
                "rsi":round(rsi_val,1),"macd_hist":round(hist_val,6),"atr":round(atr_val,4),
                "bb_upper":round(bb_upper.iloc[-1],4),"bb_lower":round(bb_lower.iloc[-1],4),
                "ema20":round(ema20.iloc[-1],4),"ema50":round(ema50.iloc[-1],4),"ema200":round(ema200.iloc[-1],4)}

    async def full_analysis(self, symbol: str) -> str:
        try:
            df, df4h, ticker, news_list = await asyncio.gather(
                self.fetch_ohlcv(symbol,"1h",200),
                self.fetch_ohlcv(symbol,"4h",100),
                self.fetch_price(symbol),
                self.fetch_news()
            )
            news_score, news_label, headlines = self.analyze_news_sentiment(news_list)
            sig = self.generate_signal(df, news_score)
            sig4h = self.generate_signal(df4h, news_score)
            s2,s1,r1,r2 = self.support_resistance(df)
            vol =
