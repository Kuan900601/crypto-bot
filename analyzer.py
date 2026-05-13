import asyncio
import aiohttp
import pandas as pd
import numpy as np
import re
from datetime import datetime, timezone, timedelta


class CryptoAnalyzer:

    # v27 擴大掃描池：30 → 50（含熱門 meme/AI/L2/L1）
    SCAN_POOL = [
        # 主流
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT",
        "DOT/USDT", "UNI/USDT", "ATOM/USDT", "LTC/USDT", "BCH/USDT",
        # L1/L2 熱門
        "NEAR/USDT", "APT/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT",
        "SUI/USDT", "TIA/USDT", "FIL/USDT", "TRX/USDT", "ICP/USDT",
        # DeFi
        "AAVE/USDT", "MKR/USDT", "ETC/USDT", "CRV/USDT", "LDO/USDT",
        # Meme / 高熱度
        "PEPE/USDT", "SHIB/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT",
        # AI / 新敘事
        "FET/USDT", "RNDR/USDT", "WLD/USDT", "TAO/USDT", "AR/USDT",
        # Solana 生態
        "JUP/USDT", "PYTH/USDT", "JTO/USDT",
        # 其他
        "STX/USDT", "IMX/USDT", "GRT/USDT", "ENS/USDT", "ORDI/USDT",
        "SEI/USDT", "MANTA/USDT",
    ]

    TF_BINANCE = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    TF_BYBIT = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
    TF_OKX = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}



    # ⭐ K 線型態識別
    def detect_candle_pattern(self, df):
        """識別最近 K 線型態"""
        try:
            if len(df) < 3:
                return None, None
            last = df.iloc[-1]
            prev = df.iloc[-2]
            o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
            po, pc = float(prev["open"]), float(prev["close"])
            body = abs(c - o)
            upper_shadow = h - max(c, o)
            lower_shadow = min(c, o) - l
            total_range = h - l + 1e-9
            body_pct = body / total_range
            # 看漲吞噬
            if pc < po and c > o and c > po and o < pc:
                return "看漲吞噬 🔥", "BULL"
            # 看跌吞噬
            if pc > po and c < o and c < po and o > pc:
                return "看跌吞噬 ❄️", "BEAR"
            # 錘子線
            if lower_shadow > 2 * body and upper_shadow < body * 0.5 and body_pct < 0.35:
                return "錘子線 🔨", "BULL"
            # 倒錘線
            if upper_shadow > 2 * body and lower_shadow < body * 0.5 and body_pct < 0.35:
                return "倒錘線 🪓", "BEAR_WARN"
            # 十字星
            if body_pct < 0.1:
                return "十字星 ✚", "INDECISION"
            # 大陽燭
            if body_pct > 0.7 and c > o:
                return "大陽燭 🟢", "BULL_STRONG"
            # 大陰燭
            if body_pct > 0.7 and c < o:
                return "大陰燭 🔴", "BEAR_STRONG"
            return None, None
        except Exception:
            return None, None

    # ⭐ 進場時機判斷
    def entry_timing(self, price, direction, sw_res, sw_sup, rsi, vol_ratio, e20):
        """判斷現在進場還是等回調"""
        try:
            if direction == "LONG":
                if sw_sup and (price - sw_sup[0]) / price < 0.005:
                    return "🟢 立即進場", "已近支撐位"
                if sw_res and price > sw_res[0] and vol_ratio > 1.5:
                    return "🟢 立即進場", "突破阻力+爆量"
                if price > e20 * 1.04:
                    return "🟡 等回調", "脫離EMA過遠 (>4%)"
                if rsi > 72:
                    return "🟡 等回調", "RSI過熱 (>72)"
                if sw_sup and (price - sw_sup[0]) / price > 0.03:
                    return "🟢 可進場", "位置合理"
                return "🟢 可進場", "未過熱"
            else:
                if sw_res and (sw_res[0] - price) / price < 0.005:
                    return "🟢 立即進場", "已近阻力位"
                if sw_sup and price < sw_sup[0] and vol_ratio > 1.5:
                    return "🟢 立即進場", "跌破支撐+爆量"
                if price < e20 * 0.96:
                    return "🟡 等反彈", "脫離EMA過遠 (<4%)"
                if rsi < 28:
                    return "🟡 等反彈", "RSI過冷 (<28)"
                return "🟢 可進場", "未過冷"
        except Exception:
            return "🟢 可進場", "位置合理"

    # ⭐ 多指標重疊買點（精準進場位）
    def confluence_levels(self, price, indicators, threshold=0.008):
        """找出 3+ 指標重疊的價位"""
        try:
            valid = [(k, v) for k, v in indicators.items() if v > 0]
            if len(valid) < 3:
                return []
            valid.sort(key=lambda x: x[1])
            clusters = []
            current = [valid[0]]
            for i in range(1, len(valid)):
                if abs(valid[i][1] - current[-1][1]) / max(current[-1][1], 1e-9) < threshold:
                    current.append(valid[i])
                else:
                    if len(current) >= 3:
                        clusters.append(current)
                    current = [valid[i]]
            if len(current) >= 3:
                clusters.append(current)
            # 只回傳距離現價最近的 2 個
            results = []
            for c in clusters:
                avg = sum(x[1] for x in c) / len(c)
                distance = abs(avg - price) / price
                if distance < 0.05:  # 5% 內才有意義
                    results.append({
                        "price": round(avg, 4),
                        "indicators": [x[0] for x in c],
                        "count": len(c),
                        "type": "support" if avg < price else "resistance"
                    })
            results.sort(key=lambda x: abs(x["price"] - price))
            return results[:3]
        except Exception:
            return []

    # ⭐ 主力資金動向（基於量能 + 訂單簿失衡推導）
    def whale_activity(self, df, ob_ratio, vol_ratio):
        """主力資金動向判讀"""
        signals = []
        # 爆量 + 訂單簿買壓 → 主力買入
        if vol_ratio > 2.0 and ob_ratio > 1.3:
            signals.append("🐋 主力建倉中")
        elif vol_ratio > 2.0 and ob_ratio < 0.77:
            signals.append("🐋 主力出貨中")
        elif vol_ratio < 0.5:
            signals.append("💤 主力觀望")
        elif vol_ratio > 1.5:
            signals.append("📊 量能活躍")
        # 大單成交分析（用最近 K 線的振幅 + 量能）
        try:
            recent = df.tail(5)
            big_moves = ((recent["high"] - recent["low"]) / recent["close"]).mean()
            if big_moves > 0.02 and vol_ratio > 1.5:
                signals.append("⚡ 大單頻繁")
        except Exception:
            pass
        return signals

    # ⭐ ETH 生態幣
    ETH_ECOSYSTEM = ["UNI/USDT", "AAVE/USDT", "MKR/USDT", "LINK/USDT", "ARB/USDT", "OP/USDT"]

    # ⭐ SOL 生態幣
    SOL_ECOSYSTEM = ["JUP/USDT", "PYTH/USDT", "JTO/USDT", "WIF/USDT", "BONK/USDT"]

    # ⭐ 重要經濟事件（自動計算最近的）
    def upcoming_econ_events(self):
        """回傳未來 14 天內的重要經濟事件"""
        now = datetime.now(timezone.utc)
        events = []
        # FOMC 會議大約每 6 週一次（這是 2026 年的部分日期）
        fomc_dates = [
            "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
            "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"
        ]
        # CPI 通常每月 13 號左右
        # PCE 通常每月最後一個週五
        # NFP 通常每月第一個週五
        for d_str in fomc_dates:
            try:
                d = datetime.fromisoformat(d_str + "T18:00:00+00:00")
                if d > now and (d - now).days <= 14:
                    days_left = (d - now).days
                    events.append({
                        "name": "FOMC 利率決議",
                        "date": d_str,
                        "days": days_left,
                        "impact": "🔥 高影響"
                    })
            except Exception:
                pass
        # 自動計算下次 CPI 公布（每月約 13 號）
        try:
            year, month = now.year, now.month
            for offset in range(2):
                m = month + offset
                y = year + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                cpi_date = datetime(y, m, 13, 12, 30, tzinfo=timezone.utc)
                if cpi_date > now and (cpi_date - now).days <= 14:
                    events.append({
                        "name": "美國 CPI 通膨數據",
                        "date": cpi_date.strftime("%Y-%m-%d"),
                        "days": (cpi_date - now).days,
                        "impact": "🔥 高影響"
                    })
        except Exception:
            pass
        # NFP（非農就業，每月第一個週五）
        try:
            for offset in range(2):
                m = now.month + offset
                y = now.year + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                # 找該月第一個週五
                for day in range(1, 8):
                    d = datetime(y, m, day, 12, 30, tzinfo=timezone.utc)
                    if d.weekday() == 4:  # 週五
                        if d > now and (d - now).days <= 14:
                            events.append({
                                "name": "美國非農就業",
                                "date": d.strftime("%Y-%m-%d"),
                                "days": (d - now).days,
                                "impact": "⚡ 中高影響"
                            })
                        break
        except Exception:
            pass
        events.sort(key=lambda x: x["days"])
        return events[:5]

    # ⭐ 加密幣事件日曆（多重容錯）
    async def fetch_crypto_events(self, session):
        """抓取加密幣即將發生的重要事件，多來源容錯"""
        all_events = []

        # 來源 1: CoinGecko Events
        async def try_coingecko():
            try:
                url = "https://api.coingecko.com/api/v3/events?upcoming_events_only=true&per_page=10"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        data = await r.json()
                        events = data.get("data", [])[:6]
                        if events:
                            return [{
                                "title": x.get("title", "")[:60],
                                "date": x.get("start_date", "")[:10],
                                "type": x.get("type", ""),
                                "source": "CoinGecko"
                            } for x in events if x.get("title")]
            except Exception:
                pass
            return None

        # 來源 2: 幣安公告 - 上架/下架/升級
        async def try_binance_listings():
            try:
                url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=10"
                headers = {"User-Agent": "Mozilla/5.0", "lang": "zh-CN"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=6), headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        articles = data.get("data", {}).get("articles", [])[:10]
                        results = []
                        for x in articles:
                            title = x.get("title", "")
                            # 篩選重要事件：上架、下架、升級、空投
                            keywords = ["上架", "下架", "升級", "空投", "Launch", "Listing", "Delisting", "Airdrop", "硬分叉", "主網"]
                            if any(kw in title for kw in keywords):
                                ts = x.get("releaseDate", 0)
                                date_str = ""
                                if ts:
                                    try:
                                        date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                                    except Exception:
                                        pass
                                results.append({
                                    "title": title[:60],
                                    "date": date_str,
                                    "type": "Listing",
                                    "source": "幣安"
                                })
                        if results:
                            return results[:6]
            except Exception:
                pass
            return None

        # 來源 3: CryptoRank 解鎖事件
        async def try_cryptorank_unlocks():
            try:
                url = "https://api.cryptorank.io/v1/unlocks/upcoming?limit=10"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        data = await r.json()
                        unlocks = data.get("data", [])[:6]
                        results = []
                        for u in unlocks:
                            coin = u.get("coin", {}).get("symbol", "")
                            value = u.get("unlockValue", 0)
                            date = u.get("date", "")[:10]
                            if coin:
                                results.append({
                                    "title": coin + " 解鎖 " + ("${:,.0f}".format(value) if value else ""),
                                    "date": date,
                                    "type": "Unlock",
                                    "source": "CryptoRank"
                                })
                        if results:
                            return results
            except Exception:
                pass
            return None

        # 並行抓取
        tasks = [try_coingecko(), try_binance_listings(), try_cryptorank_unlocks()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_events.extend(r)

        # 去重
        seen = set()
        unique = []
        for ev in all_events:
            key = ev.get("title", "")[:30]
            if key and key not in seen:
                seen.add(key)
                unique.append(ev)

        if unique:
            return unique[:8]

        # 兜底：返回近期已知重要事件（硬編碼，定期更新）
        now = datetime.now(timezone.utc)
        hardcoded = []
        # 2026 年已知的重要時程
        upcoming = [
            ("BTC 減半後第 2 年週期高峰預測", "2026-Q2", "Cycle"),
            ("ETH Pectra 升級", "2026-Q2", "Upgrade"),
            ("SOL Firedancer 主網部署", "2026-H2", "Upgrade"),
            ("FTX 債權人賠付持續", "2026", "Event"),
            ("美國加密貨幣監管框架明朗化", "2026", "Regulation"),
        ]
        for title, date, typ in upcoming:
            hardcoded.append({
                "title": title, "date": date, "type": typ, "source": "市場展望"
            })
        return hardcoded

    # ⭐ ETH/SOL 生態快訊
    async def ecosystem_pulse(self, session):
        """ETH 和 SOL 生態幣集體動向"""
        try:
            all_symbols = self.ETH_ECOSYSTEM + self.SOL_ECOSYSTEM
            tasks = [self.fetch_ticker(session, s) for s in all_symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            eth_changes = []
            sol_changes = []
            for i, sym in enumerate(all_symbols):
                if isinstance(results[i], Exception):
                    continue
                chg = float(results[i].get("priceChangePercent", 0))
                if sym in self.ETH_ECOSYSTEM:
                    eth_changes.append((sym.replace("/USDT", ""), chg))
                else:
                    sol_changes.append((sym.replace("/USDT", ""), chg))
            eth_avg = sum(c for _, c in eth_changes) / len(eth_changes) if eth_changes else 0
            sol_avg = sum(c for _, c in sol_changes) / len(sol_changes) if sol_changes else 0
            return {
                "eth_avg": round(eth_avg, 2),
                "eth_coins": eth_changes,
                "sol_avg": round(sol_avg, 2),
                "sol_coins": sol_changes,
            }
        except Exception:
            return None


    # ⭐ Volume Profile（POC/VAH/VAL - 機構真實買賣區）
    def volume_profile(self, df, bins=20):
        try:
            recent = df.tail(100).copy()
            recent["typical"] = (recent["high"] + recent["low"] + recent["close"]) / 3
            price_min = recent["typical"].min()
            price_max = recent["typical"].max()
            if price_max == price_min:
                return None, None, None
            bin_edges = np.linspace(price_min, price_max, bins + 1)
            volume_dist = []
            for i in range(bins):
                mask = (recent["typical"] >= bin_edges[i]) & (recent["typical"] < bin_edges[i+1])
                vol_in_bin = recent.loc[mask, "volume"].sum()
                mid_price = (bin_edges[i] + bin_edges[i+1]) / 2
                volume_dist.append((mid_price, float(vol_in_bin)))
            volume_dist.sort(key=lambda x: x[1], reverse=True)
            poc = volume_dist[0][0]
            total_vol = sum(v for _, v in volume_dist)
            target = total_vol * 0.7
            accumulated = 0
            value_prices = []
            for p, v in volume_dist:
                accumulated += v
                value_prices.append(p)
                if accumulated >= target:
                    break
            vah = max(value_prices) if value_prices else None
            val = min(value_prices) if value_prices else None
            return round(poc, 4), round(vah, 4) if vah else None, round(val, 4) if val else None
        except Exception:
            return None, None, None

    # ⭐ Squeeze 過濾（BB inside Keltner = 盤整不交易）
    def squeeze_state(self, df, period=20, bb_mult=2.0, kc_mult=1.5):
        try:
            close = df["close"]
            sma = close.rolling(period).mean()
            std = close.rolling(period).std()
            bb_upper = sma + bb_mult * std
            bb_lower = sma - bb_mult * std
            h, l, c = df["high"], df["low"], df["close"]
            pc = c.shift(1)
            tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()
            kc_upper = sma + kc_mult * atr
            kc_lower = sma - kc_mult * atr
            squeeze_on = (bb_upper.iloc[-1] < kc_upper.iloc[-1]) and (bb_lower.iloc[-1] > kc_lower.iloc[-1])
            try:
                prev_squeeze = (bb_upper.iloc[-2] < kc_upper.iloc[-2]) and (bb_lower.iloc[-2] > kc_lower.iloc[-2])
                released = prev_squeeze and not squeeze_on
            except Exception:
                released = False
            return bool(squeeze_on), bool(released)
        except Exception:
            return False, False

    # ⭐ Chandelier Exit（吊燈出場 - 動態追蹤止損）
    def chandelier_exit(self, df, period=22, multiplier=3.0):
        try:
            h, l, c = df["high"], df["low"], df["close"]
            pc = c.shift(1)
            tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
            atr = tr.ewm(span=period, adjust=False).mean()
            highest_high = h.rolling(period).max()
            lowest_low = l.rolling(period).min()
            long_exit = float(highest_high.iloc[-1]) - multiplier * float(atr.iloc[-1])
            short_exit = float(lowest_low.iloc[-1]) + multiplier * float(atr.iloc[-1])
            return round(long_exit, 4), round(short_exit, 4)
        except Exception:
            return None, None

    # ⭐ 流動性掃描（止損集中區 - 機構獵殺區）
    def liquidity_zones(self, df, lookback=50):
        try:
            recent = df.tail(lookback)
            highs_local = []
            lows_local = []
            for i in range(2, len(recent) - 2):
                h = recent["high"].iloc[i]
                l = recent["low"].iloc[i]
                if h == recent["high"].iloc[i-2:i+3].max():
                    highs_local.append(round(float(h), 4))
                if l == recent["low"].iloc[i-2:i+3].min():
                    lows_local.append(round(float(l), 4))
            current = float(recent["close"].iloc[-1])
            upside_liq = sorted([round(h * 1.002, 4) for h in highs_local if h > current])[:2]
            downside_liq = sorted([round(l * 0.998, 4) for l in lows_local if l < current], reverse=True)[:2]
            return upside_liq, downside_liq
        except Exception:
            return [], []

    # ⭐ 相對強度 RS（vs BTC，找強勢幣）
    def relative_strength(self, df_alt, df_btc, period=20):
        try:
            if len(df_alt) < period or len(df_btc) < period:
                return None
            alt_chg = (df_alt["close"].iloc[-1] / df_alt["close"].iloc[-period] - 1) * 100
            btc_chg = (df_btc["close"].iloc[-1] / df_btc["close"].iloc[-period] - 1) * 100
            rs = alt_chg - btc_chg
            return round(float(rs), 2)
        except Exception:
            return None

    # ⭐ 市場 Regime 識別（趨勢市 vs 震盪市 - 影響策略選擇）
    def market_type(self, df):
        try:
            adx_v = self.safe_val(self.adx(df), 20)
            bbu, _, bbl = self.bollinger(df)
            bb_width = (self.safe_val(bbu) - self.safe_val(bbl)) / self.safe_val(df["close"])
            if adx_v >= 25:
                return "TRENDING", "趨勢市（順勢策略）"
            elif bb_width < 0.04:
                return "SQUEEZE", "盤整壓縮（即將突破）"
            elif adx_v < 20:
                return "RANGING", "震盪市（反轉策略）"
            else:
                return "MIXED", "混合行情（謹慎）"
        except Exception:
            return "MIXED", "未知"

    # ⭐ 動態 ATR 倍數（v22 加寬，減少被洗）
    def dynamic_atr_mult(self, df):
        try:
            atr_v = self.safe_val(self.atr(df))
            price = float(df["close"].iloc[-1])
            atr_pct = atr_v / price * 100
            # v22：整體加寬 0.3-0.5，避免假突破被洗
            if atr_pct > 4:
                return 3.0, "極高波動"
            elif atr_pct > 2.5:
                return 2.3, "高波動"
            elif atr_pct > 1.5:
                return 1.8, "中等波動"
            elif atr_pct > 0.8:
                return 1.5, "低波動"
            else:
                return 1.3, "極低波動"
        except Exception:
            return 1.8, "中等波動"

    # ⭐ 信號指紋（用於去重）
    def signal_fingerprint(self, symbol, direction, entry, sl, tp1):
        import hashlib
        # 進場/止損/止盈價位四捨五入到合理精度
        price_round = lambda p: round(p, 2) if p > 100 else round(p, 4)
        s = symbol + "|" + direction + "|" + str(price_round(entry)) + "|" + str(price_round(sl)) + "|" + str(price_round(tp1))
        return hashlib.md5(s.encode()).hexdigest()[:12]


    # ⭐ Order Block（訂單塊 - SMC 核心）
    def find_order_blocks(self, df, lookback=50, min_move=0.015):
        """找出未測試的訂單塊（機構真實進出區）"""
        try:
            recent = df.tail(lookback).reset_index(drop=True)
            bullish_ob = []
            bearish_ob = []
            for i in range(2, len(recent) - 3):
                future_move = (recent["close"].iloc[i+3] - recent["close"].iloc[i]) / recent["close"].iloc[i]
                c, o = recent["close"].iloc[i], recent["open"].iloc[i]
                if c < o and future_move > min_move:
                    bullish_ob.append({
                        "high": round(float(recent["high"].iloc[i]), 4),
                        "low": round(float(recent["low"].iloc[i]), 4),
                    })
                elif c > o and future_move < -min_move:
                    bearish_ob.append({
                        "high": round(float(recent["high"].iloc[i]), 4),
                        "low": round(float(recent["low"].iloc[i]), 4),
                    })
            return bullish_ob[-2:], bearish_ob[-2:]
        except Exception:
            return [], []

    # ⭐ Fair Value Gap（公允價值缺口 - 高勝率回補區）
    def find_fvg(self, df, lookback=30):
        """找出未填補的價格缺口"""
        try:
            recent = df.tail(lookback).reset_index(drop=True)
            bullish_fvg = []
            bearish_fvg = []
            for i in range(2, len(recent)):
                h1 = float(recent["high"].iloc[i-2])
                l3 = float(recent["low"].iloc[i])
                if h1 < l3:
                    bullish_fvg.append({"top": round(l3, 4), "bottom": round(h1, 4)})
                l1 = float(recent["low"].iloc[i-2])
                h3 = float(recent["high"].iloc[i])
                if l1 > h3:
                    bearish_fvg.append({"top": round(l1, 4), "bottom": round(h3, 4)})
            return bullish_fvg[-2:], bearish_fvg[-2:]
        except Exception:
            return [], []

    # ⭐ Break of Structure（BOS - 結構突破，真正的趨勢確認）
    def detect_bos(self, df, lookback=30):
        """偵測結構突破"""
        try:
            recent = df.tail(lookback).reset_index(drop=True)
            swing_highs = []
            swing_lows = []
            for i in range(2, len(recent) - 2):
                if recent["high"].iloc[i] == recent["high"].iloc[i-2:i+3].max():
                    swing_highs.append(float(recent["high"].iloc[i]))
                if recent["low"].iloc[i] == recent["low"].iloc[i-2:i+3].min():
                    swing_lows.append(float(recent["low"].iloc[i]))
            current = float(recent["close"].iloc[-1])
            if swing_highs and current > swing_highs[-1] * 1.001:
                return "BULL_BOS", round(swing_highs[-1], 4)
            if swing_lows and current < swing_lows[-1] * 0.999:
                return "BEAR_BOS", round(swing_lows[-1], 4)
            return None, None
        except Exception:
            return None, None

    # ⭐ BTC 主導性切換偵測
    async def fetch_btc_dominance(self, session):
        """BTC.D 變化 - 山寨季 vs BTC 季"""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    btc_d = data["data"]["market_cap_percentage"]["btc"]
                    # 沒有歷史值對比，但可以用閾值判斷
                    if btc_d > 60:
                        return round(btc_d, 2), "🟠 BTC 主導，山寨疲弱"
                    elif btc_d > 55:
                        return round(btc_d, 2), "🟡 BTC 偏強"
                    elif btc_d < 45:
                        return round(btc_d, 2), "🚀 山寨季強勢"
                    else:
                        return round(btc_d, 2), "⚪ 平衡狀態"
        except Exception:
            pass
        return None, None

    # ⭐ 倉位風險計算器（嚴格控制單筆風險）
    def calculate_position(self, capital, risk_pct, entry, sl, leverage=1):
        """根據資金量和止損計算建議倉位"""
        try:
            max_risk_dollar = capital * (risk_pct / 100)
            risk_per_coin = abs(entry - sl)
            if risk_per_coin == 0:
                return None
            coins_to_buy = max_risk_dollar / risk_per_coin
            position_value = coins_to_buy * entry
            margin_required = position_value / leverage
            return {
                "coins": round(coins_to_buy, 4),
                "position_value": round(position_value, 2),
                "margin": round(margin_required, 2),
                "max_loss": round(max_risk_dollar, 2),
                "leverage": leverage
            }
        except Exception:
            return None

    # ⭐ 「不要交易」警示（避開常見虧損時段）
    def should_avoid_trading(self):
        """判斷現在是否應該避免新倉"""
        warnings = []
        now = datetime.now(timezone.utc)
        weekday = now.weekday()
        hour = now.hour
        if weekday == 5 or weekday == 6:
            warnings.append("⚠️ 週末流動性差")
        if 13 <= hour <= 14:
            warnings.append("⚡ 美股開盤時段，波動劇烈")
        if 20 <= hour <= 21:
            warnings.append("⚡ 美股收盤時段，波動劇烈")
        if 2 <= hour <= 5:
            warnings.append("💤 亞洲深夜，流動性低")
        return warnings


    # ⭐ 進場品質評分（A/B/C/D）- 不只信號好，進場時機也要對
    def entry_quality_grade(self, direction, current_price, sig1h, sw_res, sw_sup,
                              vol_ratio, has_confirmation_candle):
        """
        評估「現在進場」的品質
        - A 級：已近支撐 + 確認訊號 + 量能配合
        - B 級：位置合理 + 部分確認
        - C 級：可進場但有風險
        - D 級：不建議進場（追高或脫離支撐）
        """
        grade_score = 0
        grade_reasons = []

        if direction == "LONG":
            # 1. 是否近支撐（最重要）
            if sw_sup:
                dist_to_sup = (current_price - sw_sup[0]) / current_price * 100
                if dist_to_sup < 0.5:
                    grade_score += 30
                    grade_reasons.append("✅ 已測支撐位（距離<0.5%）")
                elif dist_to_sup < 1.5:
                    grade_score += 20
                    grade_reasons.append("✅ 接近支撐位（距離<1.5%）")
                elif dist_to_sup < 3:
                    grade_score += 10
                    grade_reasons.append("📊 位置可接受（距支撐<3%）")
                else:
                    grade_score -= 10
                    grade_reasons.append("⚠️ 距支撐過遠（>3%）")
            # 2. 是否脫離 EMA 過遠（追高風險）
            ema20 = sig1h.get("e20", current_price)
            distance_pct = (current_price - ema20) / ema20 * 100
            if -1 < distance_pct < 3:
                grade_score += 15
                grade_reasons.append("✅ 距EMA20合理")
            elif distance_pct > 5:
                grade_score -= 15
                grade_reasons.append("⚠️ 脫離EMA20過遠（追高風險）")
            # 3. RSI 是否過熱
            rsi = sig1h.get("rsi", 50)
            if rsi > 75:
                grade_score -= 20
                grade_reasons.append("🔴 RSI過熱(>75)，反轉風險")
            elif rsi < 40:
                grade_score += 15
                grade_reasons.append("✅ RSI低位有上漲空間")
            elif rsi < 60:
                grade_score += 10
                grade_reasons.append("📊 RSI中性區")
            # 4. 量能配合
            if vol_ratio > 1.5:
                grade_score += 15
                grade_reasons.append("✅ 量能爆發")
            elif vol_ratio > 1.2:
                grade_score += 8
                grade_reasons.append("📊 量能正常")
            elif vol_ratio < 0.7:
                grade_score -= 10
                grade_reasons.append("⚠️ 縮量警示")
            # 5. 確認 K 線
            if has_confirmation_candle:
                grade_score += 15
                grade_reasons.append("✅ 有確認 K 線")
        else:  # SHORT
            if sw_res:
                dist_to_res = (sw_res[0] - current_price) / current_price * 100
                if dist_to_res < 0.5:
                    grade_score += 30
                    grade_reasons.append("✅ 已測阻力位")
                elif dist_to_res < 1.5:
                    grade_score += 20
                    grade_reasons.append("✅ 接近阻力位")
                elif dist_to_res < 3:
                    grade_score += 10
                    grade_reasons.append("📊 位置可接受")
                else:
                    grade_score -= 10
                    grade_reasons.append("⚠️ 距阻力過遠")
            ema20 = sig1h.get("e20", current_price)
            distance_pct = (ema20 - current_price) / ema20 * 100
            if -1 < distance_pct < 3:
                grade_score += 15
                grade_reasons.append("✅ 距EMA20合理")
            elif distance_pct > 5:
                grade_score -= 15
                grade_reasons.append("⚠️ 脫離EMA20過遠（殺低風險）")
            rsi = sig1h.get("rsi", 50)
            if rsi < 25:
                grade_score -= 20
                grade_reasons.append("🔴 RSI過冷(<25)，反彈風險")
            elif rsi > 60:
                grade_score += 15
                grade_reasons.append("✅ RSI高位有下跌空間")
            elif rsi > 40:
                grade_score += 10
                grade_reasons.append("📊 RSI中性區")
            if vol_ratio > 1.5:
                grade_score += 15
                grade_reasons.append("✅ 量能爆發")
            elif vol_ratio > 1.2:
                grade_score += 8
                grade_reasons.append("📊 量能正常")
            elif vol_ratio < 0.7:
                grade_score -= 10
                grade_reasons.append("⚠️ 縮量警示")
            if has_confirmation_candle:
                grade_score += 15
                grade_reasons.append("✅ 有確認 K 線")

        # v25：加入 S 級（極佳機會）
        if grade_score >= 80:
            grade, pos_mult, desc = "S", 1.2, "💎 極佳進場時機（重倉）"
        elif grade_score >= 60:
            grade, pos_mult, desc = "A", 1.0, "🟢 完美進場時機"
        elif grade_score >= 40:
            grade, pos_mult, desc = "B", 0.7, "🟡 良好進場時機"
        elif grade_score >= 20:
            grade, pos_mult, desc = "C", 0.4, "🟠 可進場但風險較高"
        else:
            grade, pos_mult, desc = "D", 0.0, "🔴 不建議進場（等更好時機）"

        return {
            "grade": grade,
            "score": grade_score,
            "pos_mult": pos_mult,
            "desc": desc,
            "reasons": grade_reasons
        }

    # ⭐ 確認 K 線檢測（避免假突破）
    def has_confirmation_candle(self, df, direction, ref_level):
        """檢查最近 1-2 根 K 線是否確認方向"""
        try:
            recent = df.tail(3)
            last = recent.iloc[-1]
            prev = recent.iloc[-2]
            o, h, l, c = float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"])
            po, pc = float(prev["open"]), float(prev["close"])
            if direction == "LONG":
                # 看漲確認：陽線收盤且高於前一根
                if c > o and c > pc and c > ref_level:
                    return True
                # 強烈反轉：錘子線在支撐
                body = abs(c - o)
                lower_shadow = min(c, o) - l
                if lower_shadow > body * 2 and c > o:
                    return True
            else:
                if c < o and c < pc and c < ref_level:
                    return True
                body = abs(c - o)
                upper_shadow = h - max(c, o)
                if upper_shadow > body * 2 and c < o:
                    return True
            return False
        except Exception:
            return False

    # ⭐ BTC 健康度檢查（避免逆勢開單）
    def btc_health_check(self, btc_df, btc_ticker):
        """評估 BTC 當前是否健康，決定是否適合開新單"""
        try:
            if btc_df is None or len(btc_df) < 50:
                return "UNKNOWN", "BTC 數據缺失"
            chg = float(btc_ticker.get("priceChangePercent", 0)) if btc_ticker else 0
            rl, regime, adx_v = self.market_regime(btc_df)
            rsi_v = self.safe_val(self.rsi(btc_df), 50)
            # BTC 急跌：不開新多
            if chg < -3:
                return "BAD_FOR_LONG", "BTC 大跌中 (" + str(round(chg, 1)) + "%)，避開做多"
            if chg > 3:
                return "BAD_FOR_SHORT", "BTC 大漲中 (" + str(round(chg, 1)) + "%)，避開做空"
            # BTC 趨勢確認
            if regime == "STRONG_BULL":
                return "GOOD_FOR_LONG", "BTC 強多頭，有利做多"
            elif regime == "STRONG_BEAR":
                return "GOOD_FOR_SHORT", "BTC 強空頭，有利做空"
            elif regime == "RANGING":
                return "NEUTRAL", "BTC 震盪，謹慎"
            return "OK", "BTC 狀態正常"
        except Exception:
            return "UNKNOWN", "BTC 檢查失敗"

    # ⭐ Smart Stop Loss（多重保護止損）
    def smart_stop_loss(self, direction, entry, df, atr_v, sw_res, sw_sup,
                        chandelier_long, chandelier_short, atr_mult=1.5):
        """
        智能止損 - 取最寬鬆的保護位
        """
        candidates = []
        labels = []
        if direction == "LONG":
            # 1. ATR 止損
            atr_sl = entry - atr_v * atr_mult
            candidates.append(atr_sl)
            labels.append(("ATR", atr_sl))
            # 2. 最近結構性低點下方
            if sw_sup:
                struct_sl = sw_sup[0] * 0.995
                candidates.append(struct_sl)
                labels.append(("結構", struct_sl))
            # 3. Chandelier
            if chandelier_long:
                candidates.append(chandelier_long)
                labels.append(("Chandelier", chandelier_long))
            # 4. 最近 20 根 K 線最低點
            recent_low = float(df.tail(20)["low"].min()) * 0.997
            candidates.append(recent_low)
            labels.append(("近期低點", recent_low))
            # 取最寬鬆但合理（不能超過進場價 5%）
            valid = [c for c in candidates if c < entry and (entry - c) / entry < 0.05]
            if valid:
                sl = min(valid)  # 取最寬鬆
            else:
                sl = entry * 0.97  # 兜底 3%
        else:
            atr_sl = entry + atr_v * atr_mult
            candidates.append(atr_sl)
            labels.append(("ATR", atr_sl))
            if sw_res:
                struct_sl = sw_res[0] * 1.005
                candidates.append(struct_sl)
                labels.append(("結構", struct_sl))
            if chandelier_short:
                candidates.append(chandelier_short)
                labels.append(("Chandelier", chandelier_short))
            recent_high = float(df.tail(20)["high"].max()) * 1.003
            candidates.append(recent_high)
            labels.append(("近期高點", recent_high))
            valid = [c for c in candidates if c > entry and (c - entry) / entry < 0.05]
            if valid:
                sl = max(valid)
            else:
                sl = entry * 1.03
        # 找出實際採用的標籤
        chosen_label = "智能"
        for lbl, val in labels:
            if abs(val - sl) / sl < 0.001:
                chosen_label = lbl
                break
        return round(sl, 4), chosen_label

    # ⭐ 進場理由深度分析（為什麼選這裡）
    def entry_reasoning(self, direction, sig1h, sig4h, sw_res, sw_sup,
                         vol_ratio, funding, ls_ratio, fg_val,
                         has_bos, has_ob, has_fvg, rs_btc, btc_health):
        """產生詳細的進場理由 + 風險"""
        pros = []  # 支持理由
        cons = []  # 風險點

        # === 方向理由 ===
        if direction == "LONG":
            # 趨勢
            if sig1h.get("regime") == "STRONG_BULL":
                pros.append("🎯 1H 強多頭結構（趨勢明確）")
            elif sig1h.get("regime") == "BULL":
                pros.append("📈 1H 多頭結構")
            if sig4h.get("regime") in ("STRONG_BULL", "BULL"):
                pros.append("📈 4H 同向確認")
            elif sig4h.get("regime") in ("STRONG_BEAR", "BEAR"):
                cons.append("⚠️ 4H 趨勢與 1H 相反")

            # 動能
            if sig1h.get("adx", 0) >= 30:
                pros.append("⚡ ADX " + str(int(sig1h["adx"])) + " 趨勢強勁")
            elif sig1h.get("adx", 0) < 20:
                cons.append("⚠️ ADX 偏低，趨勢可能轉震盪")
            if sig1h.get("st_dir") == 1:
                pros.append("🟢 SuperTrend 看多")
            if sig1h.get("rsi", 50) < 60 and sig1h.get("rsi", 50) > 40:
                pros.append("📊 RSI " + str(int(sig1h["rsi"])) + " 中性區（有上漲空間）")
            elif sig1h.get("rsi", 50) > 75:
                cons.append("🔴 RSI " + str(int(sig1h["rsi"])) + " 過熱，回調風險")

            # 位置
            if sw_sup:
                p = sig1h["price"]
                dist = (p - sw_sup[0]) / p * 100
                if dist < 1:
                    pros.append("🎯 緊鄰支撐位 `" + str(sw_sup[0]) + "`")
                elif dist > 3:
                    cons.append("⚠️ 距支撐 " + str(round(dist, 1)) + "%，回調空間大")

            # SMC
            if has_bos:
                pros.append("🏗 1H 結構突破上行（BOS）")
            if has_ob:
                pros.append("📦 在機構訂單塊（OB）進場區")
            if has_fvg:
                pros.append("🕳 在公允價值缺口（FVG）回補區")

            # 量能
            if vol_ratio >= 1.5:
                pros.append("🔥 量能爆發 " + str(round(vol_ratio, 1)) + "x（買盤積極）")
            elif vol_ratio < 0.7:
                cons.append("📉 量能萎縮（缺乏支撐）")

            # 反向指標（資金費率/多空比）
            if funding is not None and funding < -0.02:
                pros.append("🔄 資金費率 " + str(funding) + "% 偏負（空頭擁擠，逆向）")
            elif funding is not None and funding > 0.08:
                cons.append("⚠️ 資金費率過高 " + str(funding) + "%（多頭擁擠）")
            if ls_ratio is not None and ls_ratio < 0.7:
                pros.append("🔄 多空比 " + str(round(ls_ratio, 2)) + " 散戶看空（逆向）")

            # 情緒
            if fg_val <= 25:
                pros.append("😨 極度恐懼區（逆向買點）")
            elif fg_val >= 75:
                cons.append("🤑 極度貪婪區（追高風險）")

            # 相對 BTC
            if rs_btc is not None and rs_btc > 5:
                pros.append("💪 強於 BTC " + str(round(rs_btc, 1)) + "%（領漲）")
            elif rs_btc is not None and rs_btc < -5:
                cons.append("📉 弱於 BTC " + str(abs(round(rs_btc, 1))) + "%（落後）")

            # BTC 健康度
            if btc_health == "GOOD_FOR_LONG":
                pros.append("👍 BTC 同步多頭")
            elif btc_health == "BAD_FOR_LONG":
                cons.append("🚨 BTC 大跌中，做多風險極高")

        else:  # SHORT
            if sig1h.get("regime") == "STRONG_BEAR":
                pros.append("🎯 1H 強空頭結構")
            elif sig1h.get("regime") == "BEAR":
                pros.append("📉 1H 空頭結構")
            if sig4h.get("regime") in ("STRONG_BEAR", "BEAR"):
                pros.append("📉 4H 同向確認")
            elif sig4h.get("regime") in ("STRONG_BULL", "BULL"):
                cons.append("⚠️ 4H 趨勢與 1H 相反")
            if sig1h.get("adx", 0) >= 30:
                pros.append("⚡ ADX " + str(int(sig1h["adx"])) + " 趨勢強勁")
            elif sig1h.get("adx", 0) < 20:
                cons.append("⚠️ ADX 偏低")
            if sig1h.get("st_dir") == -1:
                pros.append("🔴 SuperTrend 看空")
            if sig1h.get("rsi", 50) > 40 and sig1h.get("rsi", 50) < 60:
                pros.append("📊 RSI " + str(int(sig1h["rsi"])) + " 中性區")
            elif sig1h.get("rsi", 50) < 25:
                cons.append("🔴 RSI 過冷，反彈風險")
            if sw_res:
                p = sig1h["price"]
                dist = (sw_res[0] - p) / p * 100
                if dist < 1:
                    pros.append("🎯 緊鄰阻力位 `" + str(sw_res[0]) + "`")
                elif dist > 3:
                    cons.append("⚠️ 距阻力 " + str(round(dist, 1)) + "%")
            if has_bos:
                pros.append("🏗 1H 結構跌破下行（BOS）")
            if has_ob:
                pros.append("📦 在看跌訂單塊區")
            if has_fvg:
                pros.append("🕳 在看跌 FVG 區")
            if vol_ratio >= 1.5:
                pros.append("💥 量能爆發 " + str(round(vol_ratio, 1)) + "x（賣壓集中）")
            elif vol_ratio < 0.7:
                cons.append("📉 量能萎縮")
            if funding is not None and funding > 0.02:
                pros.append("🔄 資金費率 " + str(funding) + "% 偏正（多頭擁擠，逆向）")
            elif funding is not None and funding < -0.08:
                cons.append("⚠️ 資金費率過負（空頭擁擠）")
            if ls_ratio is not None and ls_ratio > 2.5:
                pros.append("🔄 多空比 " + str(round(ls_ratio, 2)) + " 散戶看多（逆向）")
            if fg_val >= 75:
                pros.append("🤑 極度貪婪區（逆向賣點）")
            elif fg_val <= 25:
                cons.append("😨 極度恐懼區（殺低風險）")
            if rs_btc is not None and rs_btc < -5:
                pros.append("📉 弱於 BTC " + str(abs(round(rs_btc, 1))) + "%（領跌）")
            elif rs_btc is not None and rs_btc > 5:
                cons.append("💪 強於 BTC，做空風險")
            if btc_health == "GOOD_FOR_SHORT":
                pros.append("👍 BTC 同步空頭")
            elif btc_health == "BAD_FOR_SHORT":
                cons.append("🚨 BTC 大漲中，做空風險極高")

        return pros, cons


    # ⭐ 假突破偵測（最近 3-5 根 K 線是否曾突破又被打回）
    def fake_breakout_check(self, df, direction, lookback=5):
        """
        檢查最近 K 線是否有假突破
        - 做多：曾突破前高，但收盤回到下方 → 假突破
        - 做空：曾跌破前低，但收盤回到上方 → 假突破
        """
        try:
            if len(df) < lookback + 2:
                return False, ""
            recent = df.tail(lookback + 2)
            # 之前的高低點（不含最後 lookback 根）
            prev_high = float(recent.iloc[:-lookback]["high"].max())
            prev_low = float(recent.iloc[:-lookback]["low"].min())
            # 最近幾根 K 線
            recent_bars = recent.tail(lookback)
            last_close = float(recent_bars["close"].iloc[-1])
            highest_in_recent = float(recent_bars["high"].max())
            lowest_in_recent = float(recent_bars["low"].min())

            if direction == "LONG":
                # 假突破：曾觸及阻力上方，但現價回到下方
                if highest_in_recent > prev_high * 1.001 and last_close < prev_high * 0.998:
                    return True, "近期突破 " + str(round(prev_high, 4)) + " 失敗回落"
            else:
                # 做空假突破：曾跌破支撐，但現價回到上方
                if lowest_in_recent < prev_low * 0.999 and last_close > prev_low * 1.002:
                    return True, "近期跌破 " + str(round(prev_low, 4)) + " 失敗回升"
            return False, ""
        except Exception:
            return False, ""

    # ⭐ 進場後 K 線反向偵測（用於追蹤後警告）
    def kline_reversal_check(self, df, direction, entry_price):
        """
        檢查進場後是否出現強烈反向訊號
        - 強反向 K 線
        - 連續 3 根反向 K 線
        - 跌破/突破關鍵 EMA20
        """
        try:
            if len(df) < 10:
                return False, ""
            last3 = df.tail(3)
            ema20_v = self.safe_val(self.ema(df, 20), entry_price)
            last_close = float(last3["close"].iloc[-1])
            warnings = []

            if direction == "LONG":
                # 1. 強陰線
                last = last3.iloc[-1]
                body = float(last["close"]) - float(last["open"])
                full_range = float(last["high"]) - float(last["low"]) + 1e-9
                if body < 0 and abs(body) / full_range > 0.7:
                    warnings.append("出現強陰線")
                # 2. 連 3 紅變綠
                reds = sum(1 for i in range(3) if float(last3.iloc[i]["close"]) < float(last3.iloc[i]["open"]))
                if reds >= 3:
                    warnings.append("連續 3 根陰線")
                # 3. 跌破 EMA20
                if last_close < ema20_v * 0.997:
                    warnings.append("跌破 EMA20")
            else:
                last = last3.iloc[-1]
                body = float(last["close"]) - float(last["open"])
                full_range = float(last["high"]) - float(last["low"]) + 1e-9
                if body > 0 and abs(body) / full_range > 0.7:
                    warnings.append("出現強陽線")
                greens = sum(1 for i in range(3) if float(last3.iloc[i]["close"]) > float(last3.iloc[i]["open"]))
                if greens >= 3:
                    warnings.append("連續 3 根陽線")
                if last_close > ema20_v * 1.003:
                    warnings.append("突破 EMA20")
            return len(warnings) > 0, " + ".join(warnings)
        except Exception:
            return False, ""


    # ⭐ 多時間框架嚴格共振（v23：1H + 4H 必須同向，加 1D 趨勢確認）
    def mtf_alignment(self, df1h, df4h, df_d):
        """檢查多時間框架是否一致"""
        try:
            rl_1h, regime_1h, _ = self.market_regime(df1h)
            rl_4h, regime_4h, _ = self.market_regime(df4h)
            # 1D 用 EMA 簡單判斷
            d_ema20 = self.safe_val(self.ema(df_d, 20))
            d_ema50 = self.safe_val(self.ema(df_d, 50))
            d_price = float(df_d["close"].iloc[-1])
            if d_price > d_ema20 > d_ema50:
                regime_d = "BULL"
            elif d_price < d_ema20 < d_ema50:
                regime_d = "BEAR"
            else:
                regime_d = "NEUTRAL"
            # 共振判斷
            bullish_count = sum(1 for r in [regime_1h, regime_4h, regime_d]
                                if r in ("STRONG_BULL", "BULL"))
            bearish_count = sum(1 for r in [regime_1h, regime_4h, regime_d]
                                 if r in ("STRONG_BEAR", "BEAR"))
            if bullish_count >= 3:
                return "STRONG_BULL_MTF", "三週期強多共振"
            elif bullish_count >= 2:
                return "BULL_MTF", "雙週期多頭"
            elif bearish_count >= 3:
                return "STRONG_BEAR_MTF", "三週期強空共振"
            elif bearish_count >= 2:
                return "BEAR_MTF", "雙週期空頭"
            return "MIXED", "週期分歧"
        except Exception:
            return "UNKNOWN", "未知"

    # ⭐ 交易時段判斷（紐約/倫敦/亞洲）
    def trading_session(self):
        """判斷當前交易時段，影響策略選擇"""
        from datetime import datetime, timezone
        hour = datetime.now(timezone.utc).hour
        # 倫敦盤：8-16 UTC（流動性最佳）
        # 紐約盤：13-21 UTC（波動最大）
        # 亞洲盤：0-8 UTC（流動性最差）
        if 13 <= hour <= 16:
            return "NY_LONDON_OVERLAP", "🔥 紐倫重疊（最佳）", 1.1  # 評分加成
        elif 8 <= hour <= 12:
            return "LONDON", "📊 倫敦盤（良好）", 1.05
        elif 17 <= hour <= 21:
            return "NY", "📊 紐約盤（良好）", 1.0
        elif 0 <= hour <= 7:
            return "ASIA", "💤 亞洲盤（流動性弱）", 0.85
        else:
            return "OFF", "🌙 收盤時段", 0.9

    # ⭐ 異常波動偵測（黑天鵝事件保護）
    def extreme_volatility_check(self, df, threshold=7.0):
        """檢查最近 K 線是否有異常波動"""
        try:
            recent5 = df.tail(5)
            max_change = ((recent5["high"] - recent5["low"]) / recent5["close"]).max() * 100
            if max_change > threshold:
                return True, "最近5根 K 線單根振幅 " + str(round(max_change, 1)) + "% 過大"
            # 檢查連續 3 根同向大漲/大跌
            chgs = []
            for i in range(-3, 0):
                if i == 0:
                    continue
                c = (float(df["close"].iloc[i]) - float(df["close"].iloc[i-1])) / float(df["close"].iloc[i-1]) * 100
                chgs.append(c)
            if all(c > 1.5 for c in chgs):
                return True, "連續 3 根大漲，可能末端"
            if all(c < -1.5 for c in chgs):
                return True, "連續 3 根大跌，可能恐慌"
            return False, ""
        except Exception:
            return False, ""

    # ⭐ v25 反指標：只拒絕極端違反技術分析的訊號
    def anti_indicator_check(self, direction, sig1h):
        """強趨勢可漲到 RSI 95，給強勢續航留空間"""
        violations = []
        rsi = sig1h.get("rsi", 50)
        adx = sig1h.get("adx", 20)
        regime = sig1h.get("regime", "")

        if direction == "LONG":
            # 只在「弱多頭 + 嚴重過熱」才拒絕
            if rsi > 88 and regime not in ("STRONG_BULL",) and adx < 25:
                violations.append("RSI " + str(int(rsi)) + " 過熱且趨勢弱")
            elif rsi > 95:
                violations.append("RSI " + str(int(rsi)) + " 極端高位")
        else:
            if rsi < 12 and regime not in ("STRONG_BEAR",) and adx < 25:
                violations.append("RSI " + str(int(rsi)) + " 過冷且趨勢弱")
            elif rsi < 5:
                violations.append("RSI " + str(int(rsi)) + " 極端低位")
        return violations

    # ⭐ v25 強勢續航判斷：用動能而非 RSI
    def strong_continuation(self, df, direction):
        """判斷是否處於強勢續航狀態（不受 RSI 過熱限制）"""
        try:
            if len(df) < 30:
                return False, ""
            recent = df.tail(20)
            # 計算近 20 根的趨勢強度
            ups = sum(1 for i in range(len(recent))
                       if float(recent["close"].iloc[i]) > float(recent["open"].iloc[i]))
            downs = len(recent) - ups
            # 計算量能趨勢
            vol_first = float(recent.head(10)["volume"].mean())
            vol_last = float(recent.tail(10)["volume"].mean())
            vol_trend = vol_last / vol_first if vol_first > 0 else 1.0
            # 計算 EMA20 斜率
            ema20 = self.ema(df, 20)
            slope = (float(ema20.iloc[-1]) - float(ema20.iloc[-10])) / float(ema20.iloc[-10])

            if direction == "LONG":
                # 多頭續航：陽多陰少 + 量能持平 + EMA 上升
                if ups >= 14 and slope > 0.005 and vol_trend > 0.7:
                    return True, "強勢續航中（量增配合）"
                if ups >= 16 and slope > 0.003:
                    return True, "極強多頭續航"
            else:
                if downs >= 14 and slope < -0.005 and vol_trend > 0.7:
                    return True, "強勢崩跌續航"
                if downs >= 16 and slope < -0.003:
                    return True, "極強空頭續航"
            return False, ""
        except Exception:
            return False, ""



    # ⭐ 策略類型分類（v24 新增 - 不同策略不同邏輯）
    def classify_strategy(self, direction, sig1h, sig4h, df1h, vol_ratio):
        """
        判斷適合的策略類型：
        - BREAKOUT_RETEST：突破回踩（最高勝率）
        - MOMENTUM：動能突破
        - TREND_FOLLOW：趨勢追隨
        - REVERSAL：反轉抄底
        - RANGE：區間交易
        """
        try:
            rsi = sig1h.get("rsi", 50)
            adx = sig1h.get("adx", 20)
            regime = sig1h.get("regime", "")
            squeeze_released = sig1h.get("squeeze_released", False)
            price = sig1h.get("price", 0)
            ema20 = sig1h.get("e20", price)
            distance_pct = (price - ema20) / ema20 * 100 if ema20 else 0

            # 突破回踩：價格剛突破又回測 EMA20
            if direction == "LONG":
                if regime in ("STRONG_BULL", "BULL") and -1.5 < distance_pct < 1.5 and vol_ratio < 1.3:
                    return "BREAKOUT_RETEST", "🎯 突破回踩進場（最高勝率模式）"
                if squeeze_released and adx > 22:
                    return "MOMENTUM", "🚀 動能爆發進場"
                if regime in ("STRONG_BULL", "BULL") and adx > 25:
                    return "TREND_FOLLOW", "📈 順勢進場"
                if rsi < 32 and regime not in ("STRONG_BEAR", "BEAR"):
                    return "REVERSAL", "🔄 反轉抄底"
                return "RANGE", "↔️ 區間操作"
            else:
                if regime in ("STRONG_BEAR", "BEAR") and -1.5 < distance_pct < 1.5 and vol_ratio < 1.3:
                    return "BREAKOUT_RETEST", "🎯 跌破回測進場（最高勝率模式）"
                if squeeze_released and adx > 22:
                    return "MOMENTUM", "💥 動能崩跌進場"
                if regime in ("STRONG_BEAR", "BEAR") and adx > 25:
                    return "TREND_FOLLOW", "📉 順勢進場"
                if rsi > 68 and regime not in ("STRONG_BULL", "BULL"):
                    return "REVERSAL", "🔄 反轉做空"
                return "RANGE", "↔️ 區間操作"
        except Exception:
            return "TREND_FOLLOW", "📊 標準順勢"

    # ⭐ 機構吸籌偵測（v24 新增 - 智錢腳印）
    def smart_money_detect(self, df, direction):
        """偵測機構吸籌/出貨腳印"""
        try:
            if len(df) < 30:
                return False, ""
            recent20 = df.tail(20)
            # 計算量價特徵
            vol_avg = float(recent20["volume"].mean())
            price_range = (float(recent20["high"].max()) - float(recent20["low"].min())) / float(recent20["close"].iloc[-1])
            # 高量低波動 → 吸籌特徵
            high_vol_bars = sum(1 for i in range(len(recent20))
                                  if float(recent20["volume"].iloc[i]) > vol_avg * 1.3)
            if direction == "LONG":
                # 吸籌：高量 + 小波動 + 價格在中樞上方
                if high_vol_bars >= 5 and price_range < 0.05:
                    return True, "🐋 機構吸籌跡象（高量低波動）"
                # OBV 上升但價格盤整
                obv = self.obv(df)
                obv_recent = obv.tail(20)
                obv_slope = (obv_recent.iloc[-1] - obv_recent.iloc[0]) / abs(obv_recent.iloc[0] + 1e-9)
                price_slope = (float(recent20["close"].iloc[-1]) - float(recent20["close"].iloc[0])) / float(recent20["close"].iloc[0])
                if obv_slope > 0.05 and abs(price_slope) < 0.02:
                    return True, "🐋 OBV 暗示機構買入"
            else:
                if high_vol_bars >= 5 and price_range < 0.05:
                    return True, "🐋 機構出貨跡象"
            return False, ""
        except Exception:
            return False, ""

    # ⭐ 動態止盈（v24 - 基於 Fibonacci 擴展 + 阻力強度）
    def dynamic_take_profits(self, direction, entry, sl, df, ref_res, ref_sup, atr_v):
        """根據實際價格結構動態計算止盈位"""
        risk = abs(entry - sl)
        try:
            if direction == "LONG":
                # 找最近 30 根 K 線的高點作為 swing high
                recent_high = float(df.tail(30)["high"].max())
                # 計算 Fibonacci 擴展
                fib_1618 = entry + risk * 2.0  # 黃金比例擴展
                fib_2618 = entry + risk * 3.2  # 瘋狂擴展
                # TP1: 1:1 風報（保本）
                tp1 = round(entry + risk * 1.0, 4)
                # TP2: 最近的阻力或 1:1.8（取近者）
                if ref_res and ref_res[0] > entry:
                    tp2_candidates = [ref_res[0], entry + risk * 1.8]
                    tp2 = min([t for t in tp2_candidates if t > tp1])
                else:
                    tp2 = round(entry + risk * 1.8, 4)
                # TP3: Fib 1.618 或第二阻力
                if ref_res and len(ref_res) >= 2:
                    tp3 = max(ref_res[1], fib_1618)
                else:
                    tp3 = round(fib_1618, 4)
                # TP4: Fib 2.618 或近期高點 + ATR
                tp4_candidates = [fib_2618, recent_high + atr_v]
                tp4 = round(max(tp4_candidates), 4)
            else:
                recent_low = float(df.tail(30)["low"].min())
                fib_1618 = entry - risk * 2.0
                fib_2618 = entry - risk * 3.2
                tp1 = round(entry - risk * 1.0, 4)
                if ref_sup and ref_sup[0] < entry:
                    tp2_candidates = [ref_sup[0], entry - risk * 1.8]
                    tp2 = max([t for t in tp2_candidates if t < tp1])
                else:
                    tp2 = round(entry - risk * 1.8, 4)
                if ref_sup and len(ref_sup) >= 2:
                    tp3 = min(ref_sup[1], fib_1618)
                else:
                    tp3 = round(fib_1618, 4)
                tp4_candidates = [fib_2618, recent_low - atr_v]
                tp4 = round(min(tp4_candidates), 4)
            return round(tp1, 4), round(tp2, 4), round(tp3, 4), round(tp4, 4)
        except Exception:
            if direction == "LONG":
                return (round(entry + risk * 1.0, 4),
                        round(entry + risk * 2.0, 4),
                        round(entry + risk * 3.0, 4),
                        round(entry + risk * 5.0, 4))
            else:
                return (round(entry - risk * 1.0, 4),
                        round(entry - risk * 2.0, 4),
                        round(entry - risk * 3.0, 4),
                        round(entry - risk * 5.0, 4))



    # ⭐ alt 幣 vs BTC 不同標準（alt 波動更大，閾值要寬）
    def get_volatility_profile(self, symbol):
        """根據幣種類型決定參數"""
        if symbol in ("BTC/USDT", "ETH/USDT"):
            return {"atr_mult_bonus": 0, "rsi_overheat": 75, "rsi_oversold": 25}
        elif symbol in ("SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"):
            return {"atr_mult_bonus": 0.2, "rsi_overheat": 78, "rsi_oversold": 22}
        else:
            return {"atr_mult_bonus": 0.4, "rsi_overheat": 80, "rsi_oversold": 20}


    # ⭐ v25 即時動能掃描：尋找 5-15 分鐘級別的爆發機會
    async def momentum_scan(self):
        """掃描所有幣種，找出最近 5-15 分鐘有大動作的"""
        try:
            now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            async with aiohttp.ClientSession() as session:
                tasks = []
                for sym in self.SCAN_POOL:
                    tasks.append(self.fetch_ticker(session, sym))
                    tasks.append(self.fetch_ohlcv(session, sym, "5m", 30))
                results = await asyncio.gather(*tasks, return_exceptions=True)

            opportunities = []
            for i, sym in enumerate(self.SCAN_POOL):
                ticker = results[i * 2]
                df5m = results[i * 2 + 1]
                if isinstance(ticker, Exception) or isinstance(df5m, Exception):
                    continue
                if df5m is None or len(df5m) < 20:
                    continue
                try:
                    current_price = float(ticker.get("lastPrice", 0))
                    if not current_price:
                        continue
                    # 5 分鐘級動量
                    chg_5m = (current_price - float(df5m["close"].iloc[-2])) / float(df5m["close"].iloc[-2]) * 100
                    chg_15m = (current_price - float(df5m["close"].iloc[-4])) / float(df5m["close"].iloc[-4]) * 100
                    chg_30m = (current_price - float(df5m["close"].iloc[-7])) / float(df5m["close"].iloc[-7]) * 100
                    # 量能變化
                    recent_vol = float(df5m["volume"].iloc[-1])
                    avg_vol = float(df5m["volume"].tail(20).mean())
                    vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
                    # 找出有意義的動作
                    if abs(chg_5m) >= 1.0 and vol_ratio >= 1.5:
                        signal_type = "🚀 即時爆發" if chg_5m > 0 else "💥 即時崩跌"
                        opportunities.append({
                            "symbol": sym,
                            "chg_5m": round(chg_5m, 2),
                            "chg_15m": round(chg_15m, 2),
                            "chg_30m": round(chg_30m, 2),
                            "vol_ratio": round(vol_ratio, 1),
                            "price": current_price,
                            "signal": signal_type,
                            "intensity": abs(chg_5m) * vol_ratio
                        })
                except Exception:
                    continue
            # 排序：強度最大的在前
            opportunities.sort(key=lambda x: x["intensity"], reverse=True)

            r = "⚡ *即時動能掃描*｜" + now + "\n"
            r += "━━━━━━━━━━━━━━━\n"
            if not opportunities:
                r += "📡 目前沒有顯著爆發信號\n"
                r += "_市場處於穩定狀態_"
                return r
            r += "🔥 偵測到 " + str(len(opportunities)) + " 個動能異動：\n\n"
            for opp in opportunities[:8]:
                sym_short = opp["symbol"].replace("/USDT", "")
                r += opp["signal"] + " *" + sym_short + "*\n"
                r += "   5分 `" + ("+" if opp["chg_5m"] >= 0 else "") + str(opp["chg_5m"]) + "%`"
                r += " | 15分 `" + ("+" if opp["chg_15m"] >= 0 else "") + str(opp["chg_15m"]) + "%`"
                r += " | 30分 `" + ("+" if opp["chg_30m"] >= 0 else "") + str(opp["chg_30m"]) + "%`\n"
                r += "   價格 `" + str(opp["price"]) + "` | 量爆 `" + str(opp["vol_ratio"]) + "x`\n\n"
            r += "━━━━━━━━━━━━━━━\n"
            r += "💡 *使用建議*\n"
            r += "• 動能信號是短線機會，請務必設止損\n"
            r += "• 量爆+價漲 = 可能延續\n"
            r += "• 量爆+價跌 = 可能反轉\n"
            r += "• 短打建議倉位 ≤ 2%"
            return r
        except Exception as e:
            return "❌ 動能掃描失敗：" + str(e)

    # ⭐ v25 凱利公式：基於勝率和盈虧比計算最佳倉位
    def kelly_position(self, win_rate_pct, avg_win_pct, avg_loss_pct, capital, max_risk=2.0):
        """
        凱利公式：f = (bp - q) / b
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        實際使用「半凱利」（更保守）
        """
        try:
            p = win_rate_pct / 100
            q = 1 - p
            if avg_loss_pct == 0:
                return None
            b = avg_win_pct / avg_loss_pct
            kelly_f = (b * p - q) / b
            # 半凱利
            half_kelly = max(0, kelly_f * 0.5)
            # 限制最大 max_risk%
            recommended_pct = min(half_kelly * 100, max_risk * 5)  # 不超過 5x max_risk
            return {
                "kelly_pct": round(kelly_f * 100, 2),
                "half_kelly_pct": round(half_kelly * 100, 2),
                "recommended_pct": round(recommended_pct, 2),
                "position_value": round(capital * recommended_pct / 100, 2),
            }
        except Exception:
            return None

    # ⭐ VWAP（成交量加權平均價 - 機構進出場位）
    def vwap(self, df):
        try:
            tp = (df["high"] + df["low"] + df["close"]) / 3
            v = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
            return self.safe_val(v)
        except Exception:
            return float(df["close"].iloc[-1])

    # ⭐ SuperTrend（趨勢反轉確認）
    def supertrend(self, df, period=10, multiplier=3.0):
        try:
            h, l, c = df["high"], df["low"], df["close"]
            pc = c.shift(1)
            tr = pd.concat([(h-l), (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
            atr = tr.ewm(span=period, adjust=False).mean()
            hl2 = (h + l) / 2
            upper = hl2 + multiplier * atr
            lower = hl2 - multiplier * atr
            direction = pd.Series(1, index=df.index)
            for i in range(1, len(df)):
                if c.iloc[i] > upper.iloc[i-1]:
                    direction.iloc[i] = 1
                elif c.iloc[i] < lower.iloc[i-1]:
                    direction.iloc[i] = -1
                else:
                    direction.iloc[i] = direction.iloc[i-1]
            st_line = lower.where(direction == 1, upper)
            return int(direction.iloc[-1]), round(float(st_line.iloc[-1]), 4)
        except Exception:
            return 1, float(df["close"].iloc[-1])

    # ⭐ BTC 相關性（alt 跟漲跟跌分析）
    def btc_correlation(self, df_alt, df_btc, window=24):
        try:
            btc_ret = df_btc["close"].pct_change()
            alt_ret = df_alt["close"].pct_change()
            corr = btc_ret.rolling(window).corr(alt_ret)
            val = float(corr.iloc[-1])
            if pd.isna(val):
                return None
            return round(val, 2)
        except Exception:
            return None

    # ⭐ 信號有效期（根據持有時間自動計算）
    def signal_expiry(self, timeframe_str):
        now = datetime.now(timezone.utc)
        if "中線" in timeframe_str:
            expire = now + timedelta(hours=72)
            hours = 72
        else:
            expire = now + timedelta(hours=8)
            hours = 8
        return expire.strftime("%m-%d %H:%M UTC"), hours

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

    # ── K 線抓取 ──
    async def _fetch_binance_klines(self, session, symbol, timeframe, limit):
        pair = symbol.replace("/", "")
        tf = self.TF_BINANCE.get(timeframe, "1h")
        url = "https://api.binance.com/api/v3/klines?symbol=" + pair + "&interval=" + tf + "&limit=" + str(limit)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        if not isinstance(data, list):
            raise ValueError("err")
        cols = ["timestamp","open","high","low","close","volume","close_time","qv","tr","tbb","tbq","ig"]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def _fetch_bybit_klines(self, session, symbol, timeframe, limit):
        pair = symbol.replace("/", "")
        tf = self.TF_BYBIT.get(timeframe, "60")
        url = "https://api.bybit.com/v5/market/kline?category=spot&symbol=" + pair + "&interval=" + tf + "&limit=" + str(limit)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        if data.get("retCode") != 0:
            raise ValueError("err")
        rows = list(reversed(data["result"]["list"]))
        df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume","turnover"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def _fetch_okx_klines(self, session, symbol, timeframe, limit):
        pair = symbol.replace("/", "-")
        tf = self.TF_OKX.get(timeframe, "1H")
        url = "https://www.okx.com/api/v5/market/candles?instId=" + pair + "&bar=" + tf + "&limit=" + str(min(limit, 300))
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        if data.get("code") != "0":
            raise ValueError("err")
        rows = list(reversed(data["data"]))
        df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume","volCcy","volCcyQuote","confirm"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df

    async def fetch_ohlcv(self, session, symbol, timeframe="1h", limit=200):
        for fetcher in [self._fetch_binance_klines, self._fetch_bybit_klines, self._fetch_okx_klines]:
            try:
                df = await fetcher(session, symbol, timeframe, limit)
                if df is not None and len(df) > 0:
                    return df
            except Exception:
                continue
        raise ValueError("無法抓取 " + symbol)

    # ── Ticker ──
    async def _ticker_binance(self, session, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=" + pair
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        return {
            "lastPrice": float(data.get("lastPrice", 0)),
            "priceChangePercent": float(data.get("priceChangePercent", 0)),
            "highPrice": float(data.get("highPrice", 0)),
            "lowPrice": float(data.get("lowPrice", 0)),
            "quoteVolume": float(data.get("quoteVolume", 0)),
        }

    async def _ticker_bybit(self, session, symbol):
        pair = symbol.replace("/", "")
        url = "https://api.bybit.com/v5/market/tickers?category=spot&symbol=" + pair
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        if data.get("retCode") != 0 or not data["result"]["list"]:
            raise ValueError("err")
        d = data["result"]["list"][0]
        return {
            "lastPrice": float(d.get("lastPrice", 0)),
            "priceChangePercent": float(d.get("price24hPcnt", 0)) * 100,
            "highPrice": float(d.get("highPrice24h", 0)),
            "lowPrice": float(d.get("lowPrice24h", 0)),
            "quoteVolume": float(d.get("turnover24h", 0)),
        }

    async def _ticker_okx(self, session, symbol):
        pair = symbol.replace("/", "-")
        url = "https://www.okx.com/api/v5/market/ticker?instId=" + pair
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                raise ValueError("HTTP")
            data = await r.json()
        if data.get("code") != "0" or not data["data"]:
            raise ValueError("err")
        d = data["data"][0]
        last = float(d.get("last", 0))
        opn = float(d.get("open24h", last))
        chg = ((last - opn) / opn * 100) if opn > 0 else 0
        return {
            "lastPrice": last,
            "priceChangePercent": chg,
            "highPrice": float(d.get("high24h", 0)),
            "lowPrice": float(d.get("low24h", 0)),
            "quoteVolume": float(d.get("volCcy24h", 0)),
        }

    async def fetch_ticker(self, session, symbol):
        for fetcher in [self._ticker_binance, self._ticker_bybit, self._ticker_okx]:
            try:
                t = await fetcher(session, symbol)
                if t["lastPrice"] > 0:
                    return t
            except Exception:
                continue
        raise ValueError("Ticker 失敗")

    # ── 訂單簿 ──
    async def fetch_orderbook(self, session, symbol):
        pair = symbol.replace("/", "")
        try:
            url = "https://api.binance.com/api/v3/depth?symbol=" + pair + "&limit=100"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    data = await r.json()
                    bids = sum(float(b[1]) for b in data.get("bids", []))
                    asks = sum(float(a[1]) for a in data.get("asks", []))
                    if bids > 0 and asks > 0:
                        return self._format_ob(bids / asks), bids / asks
        except Exception:
            pass
        try:
            url = "https://api.bybit.com/v5/market/orderbook?category=spot&symbol=" + pair + "&limit=50"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("retCode") == 0:
                        bids = sum(float(b[1]) for b in data["result"].get("b", []))
                        asks = sum(float(a[1]) for a in data["result"].get("a", []))
                        if bids > 0 and asks > 0:
                            return self._format_ob(bids / asks), bids / asks
        except Exception:
            pass
        try:
            okx_pair = symbol.replace("/", "-")
            url = "https://www.okx.com/api/v5/market/books?instId=" + okx_pair + "&sz=50"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("code") == "0" and data.get("data"):
                        d = data["data"][0]
                        bids = sum(float(b[1]) for b in d.get("bids", []))
                        asks = sum(float(a[1]) for a in d.get("asks", []))
                        if bids > 0 and asks > 0:
                            return self._format_ob(bids / asks), bids / asks
        except Exception:
            pass
        return "📒 不可用", 1.0

    def _format_ob(self, ratio):
        if ratio > 1.5:
            return "💚 強力買壓 (" + str(round(ratio, 2)) + "x)"
        elif ratio > 1.2:
            return "📗 買壓較強 (" + str(round(ratio, 2)) + "x)"
        elif ratio < 0.67:
            return "💔 強力賣壓 (" + str(round(ratio, 2)) + "x)"
        elif ratio < 0.83:
            return "📕 賣壓較強 (" + str(round(ratio, 2)) + "x)"
        else:
            return "📒 多空均衡 (" + str(round(ratio, 2)) + "x)"

    async def fetch_funding_rate(self, session, symbol):
        pair = symbol.replace("/", "")
        try:
            url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=" + pair
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    data = await r.json()
                    return round(float(data.get("lastFundingRate", 0)) * 100, 4)
        except Exception:
            pass
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=" + pair
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                data = await r.json()
            if data.get("retCode") == 0 and data["result"]["list"]:
                return round(float(data["result"]["list"][0].get("fundingRate", 0)) * 100, 4)
        except Exception:
            pass
        return None

    async def fetch_long_short_ratio(self, session, symbol):
        pair = symbol.replace("/", "")
        try:
            url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=" + pair + "&period=1h&limit=1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    data = await r.json()
                    if data and len(data) > 0:
                        return float(data[0].get("longShortRatio", 1))
        except Exception:
            pass
        return None

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
            # 中文翻譯標籤
            label_zh = {
                "Extreme Greed": "極度貪婪",
                "Greed": "貪婪",
                "Neutral": "中性",
                "Fear": "恐懼",
                "Extreme Fear": "極度恐懼"
            }.get(label, label)
            return icon + " " + str(now_val) + "/100 " + arrow + str(abs(change)) + " (" + label_zh + ")", now_val
        except Exception:
            return "⚪ 不可用", 50

    async def fetch_global(self, session):
        try:
            async with session.get("https://api.coingecko.com/api/v3/global",
                                    timeout=aiohttp.ClientTimeout(total=5)) as r:
                data = await r.json()
            d = data["data"]
            return {
                "btc_dom": round(d["market_cap_percentage"]["btc"], 2),
                "eth_dom": round(d["market_cap_percentage"]["eth"], 2),
                "mcap_change": round(d.get("market_cap_change_percentage_24h_usd", 0), 2),
                "total_mcap": round(d["total_market_cap"]["usd"] / 1e9, 1)
            }
        except Exception:
            return None

    # ⭐ 中文新聞抓取
    async def fetch_news(self, session):
        """並行抓取多來源新聞，誰先回來用誰"""
        async def try_cryptocompare_zh():
            try:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=ZH&sortOrder=latest"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json()
                        items = data.get("Data", [])[:12]
                        if items:
                            return [{
                                "title": x.get("title", ""),
                                "published_at": datetime.fromtimestamp(
                                    x.get("published_on", 0), tz=timezone.utc
                                ).isoformat() if x.get("published_on") else "",
                                "source": x.get("source", "CC")
                            } for x in items]
            except Exception:
                pass
            return None

        async def try_cryptocompare_en():
            try:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json()
                        items = data.get("Data", [])[:12]
                        if items:
                            return [{
                                "title": x.get("title", ""),
                                "published_at": datetime.fromtimestamp(
                                    x.get("published_on", 0), tz=timezone.utc
                                ).isoformat() if x.get("published_on") else "",
                                "source": x.get("source", "CC")
                            } for x in items]
            except Exception:
                pass
            return None

        async def try_binance_announce():
            try:
                url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=10"
                headers = {"User-Agent": "Mozilla/5.0", "lang": "zh-CN"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        articles = data.get("data", {}).get("articles", [])[:12]
                        if articles:
                            return [{
                                "title": x.get("title", ""),
                                "published_at": datetime.fromtimestamp(
                                    x.get("releaseDate", 0) / 1000, tz=timezone.utc
                                ).isoformat() if x.get("releaseDate") else "",
                                "source": "Binance"
                            } for x in articles]
            except Exception:
                pass
            return None

        async def try_binance_square():
            try:
                url = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=15"
                headers = {"User-Agent": "Mozilla/5.0", "lang": "zh-CN"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        articles = data.get("data", {}).get("articles", [])[:12]
                        if articles:
                            return [{
                                "title": x.get("title", ""),
                                "published_at": datetime.fromtimestamp(
                                    x.get("releaseDate", 0) / 1000, tz=timezone.utc
                                ).isoformat() if x.get("releaseDate") else "",
                                "source": "幣安"
                            } for x in articles]
            except Exception:
                pass
            return None

        async def try_panews():
            try:
                url = "https://www.panewslab.com/zh/rss/index.xml"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        text = await r.text()
                        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                        results = []
                        for item in items[:12]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title:
                                    continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                        from email.utils import parsedate_to_datetime
                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception:
                                        pass
                                results.append({
                                    "title": title, "published_at": pub_iso, "source": "PANews"
                                })
                        if results:
                            return results
            except Exception:
                pass
            return None

        async def try_odaily():
            try:
                url = "https://www.odaily.news/v1/openapi/odailyrss"
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        text = await r.text()
                        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                        results = []
                        for item in items[:12]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title:
                                    continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                        from email.utils import parsedate_to_datetime
                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception:
                                        pass
                                results.append({
                                    "title": title, "published_at": pub_iso, "source": "Odaily"
                                })
                        if results:
                            return results
            except Exception:
                pass
            return None

        # ⭐ 並行抓取，誰先回來用誰
        tasks = [
            try_cryptocompare_zh(),
            try_binance_announce(),
            try_binance_square(),
            try_panews(),
            try_odaily(),
            try_cryptocompare_en(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # 偏好中文來源（前4個），全部彙總後去重
        all_news = []
        seen_titles = set()
        for r in results:
            if isinstance(r, list):
                for n in r:
                    title = n.get("title", "")
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append(n)
        # 按時間排序（新→舊）
        def get_time(n):
            try:
                return datetime.fromisoformat(n.get("published_at", "").replace("Z", "+00:00"))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)
        all_news.sort(key=get_time, reverse=True)
        return all_news[:12]

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

    def detect_divergence(self, df, lookback=30):
        try:
            r = df.tail(lookback).reset_index(drop=True)
            rsi_v = self.rsi(r).fillna(50)
            recent_high = r["high"].iloc[-5:].max()
            prev_high = r["high"].iloc[:-5].max()
            recent_rsi_at_high = rsi_v.iloc[-5:].max()
            prev_rsi_at_high = rsi_v.iloc[:-5].max()
            if recent_high > prev_high and recent_rsi_at_high < prev_rsi_at_high - 3:
                return "BEAR_DIV", "📕 頂背離"
            recent_low = r["low"].iloc[-5:].min()
            prev_low = r["low"].iloc[:-5].min()
            recent_rsi_at_low = rsi_v.iloc[-5:].min()
            prev_rsi_at_low = rsi_v.iloc[:-5].min()
            if recent_low < prev_low and recent_rsi_at_low > prev_rsi_at_low + 3:
                return "BULL_DIV", "📗 底背離"
            return None, None
        except Exception:
            return None, None

    def pivot_sr(self, df, lookback=50):
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
                return "🔥🔥 異常爆量 (" + str(round(r, 1)) + "x)", r
            elif r > 1.8:
                return "🔥 爆量 (" + str(round(r, 1)) + "x)", r
            elif r > 1.3:
                return "🟡 放量 (" + str(round(r, 1)) + "x)", r
            elif r > 0.7:
                return "🟢 正常 (" + str(round(r, 1)) + "x)", r
            else:
                return "⚪ 縮量 (" + str(round(r, 1)) + "x)", r
        except Exception:
            return "📒 一般", 1.0

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

    BULL_W = {"漲", "突破", "新高", "上漲", "看漲", "牛市", "拉升", "反彈", "ETF", "通過", "批准", "利好", "利多", "暴漲",
              "bull","rally","surge","gain","pump","breakout","ath","adoption","bullish","etf","approve"}
    BEAR_W = {"跌", "下跌", "崩盤", "熊市", "看跌", "拋售", "暴跌", "封禁", "駭客", "詐騙", "利空", "下跌",
              "bear","crash","dump","drop","sell","ban","hack","lawsuit","bearish","collapse","fraud"}

    def sentiment(self, news):
        score, items = 0, []
        for item in news[:15]:
            title = item.get("title", "")
            t = title.lower()
            published = item.get("published_at", "")
            bull_count = sum(1 for w in self.BULL_W if w in title or w in t)
            bear_count = sum(1 for w in self.BEAR_W if w in title or w in t)
            item_score = (bull_count - bear_count) * 0.1
            score += item_score
            emoji = "📗" if item_score > 0.05 else "📕" if item_score < -0.05 else "📒"
            items.append({"title": title[:80], "emoji": emoji, "published": published, "source": item.get("source", "")})
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
            secs = diff.total_seconds()
            if secs < 60:
                return str(int(secs)) + "秒前"
            mins = int(secs / 60)
            if mins < 60:
                return str(mins) + "分鐘前"
            hrs = mins // 60
            if hrs < 24:
                return str(hrs) + "小時前"
            return str(hrs // 24) + "天前"
        except Exception:
            return ""

    def breakout_quality(self, price, sw_res, sw_sup, vol_ratio):
        if sw_res and price > sw_res[0]:
            if vol_ratio > 1.5:
                return "🚀 *突破阻力 + 爆量* (強信號)"
            elif vol_ratio < 0.8:
                return "⚠️ 突破阻力但縮量 (假突破風險)"
        elif sw_sup and price < sw_sup[0]:
            if vol_ratio > 1.5:
                return "💥 *跌破支撐 + 爆量* (強信號)"
            elif vol_ratio < 0.8:
                return "⚠️ 跌破支撐但縮量 (假跌破風險)"
        return None

    def near_key_levels(self, price, sw_res, sw_sup, threshold=0.5):
        alerts = []
        for r in sw_res[:2]:
            dist = (r - price) / price * 100
            if 0 < dist < threshold:
                alerts.append("⚠️ 即將觸及阻力 `" + str(r) + "` (差 " + str(round(dist, 2)) + "%)")
        for s in sw_sup[:2]:
            dist = (price - s) / price * 100
            if 0 < dist < threshold:
                alerts.append("⚠️ 即將觸及支撐 `" + str(s) + "` (差 " + str(round(dist, 2)) + "%)")
        return alerts

    def generate_signal(self, df, fg_val=50, current_price=None):
        p = float(current_price) if current_price else float(df["close"].iloc[-1])
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
        div_type, div_label = self.detect_divergence(df)
        score = 0
        reasons = []
        # ⭐ VWAP 位置判斷
        vwap_v = self.vwap(df)
        # ⭐ SuperTrend 方向
        st_dir, st_line = self.supertrend(df)
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
            reasons.append("StochRSI金叉")
        elif kv > 80 and kv < dv:
            score -= 1.5
            reasons.append("StochRSI死叉")
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
        # ⭐ VWAP 評分（機構進出場位）
        if p > vwap_v * 1.001:
            score += 1.0
            reasons.append("價格在VWAP上方")
        elif p < vwap_v * 0.999:
            score -= 1.0
            reasons.append("價格在VWAP下方")
        # ⭐ SuperTrend 評分（趨勢確認）
        if st_dir == 1:
            score += 1.5
            reasons.append("SuperTrend看多")
        else:
            score -= 1.5
            reasons.append("SuperTrend看空")
        if adx_now < 20:
            score = score * 0.6
        elif adx_now > 35:
            score = score * 1.2
        if div_type == "BULL_DIV":
            score += 2
            reasons.append(div_label)
        elif div_type == "BEAR_DIV":
            score -= 2
            reasons.append(div_label)
        if fg_val <= 20:
            score += 1.5
            reasons.append("極度恐懼(逆向)")
        elif fg_val >= 80:
            score -= 1.5
            reasons.append("極度貪婪(逆向)")
        # ⭐ K 線型態識別（v15：僅參考，不計入評分 - 單根K線勝率僅50%）
        pattern, pattern_type = self.detect_candle_pattern(df)
        # ⭐ Squeeze 釋放（強信號）
        squeeze_on, squeeze_released = self.squeeze_state(df)
        if squeeze_released:
            if score > 0:
                score += 2
                reasons.append("Squeeze釋放看多")
            elif score < 0:
                score -= 2
                reasons.append("Squeeze釋放看空")
        # ⭐ Volume Profile - POC 位置
        poc, vah, val_v = self.volume_profile(df)
        if poc and val_v and vah:
            if p < val_v:
                score += 1
                reasons.append("價格在價值區下方")
            elif p > vah:
                score -= 1
                reasons.append("價格在價值區上方")
        if score >= 2.5:  # 放寬到 2.5
            direction = "做多 🟢"
            den = "LONG"
        elif score <= -2.5:
            direction = "做空 🔴"
            den = "SHORT"
        else:
            direction = "觀望 🟡"
            den = "NEUTRAL"
        strength = min(abs(score) / 8 * 100, 100)
        sw_res, sw_sup = self.swing_sr(df)
        if regime in ("STRONG_BULL", "STRONG_BEAR"):
            tp1m, tp2m, slm = 2.0, 4.0, 1.2
        elif regime in ("BULL", "BEAR"):
            tp1m, tp2m, slm = 1.5, 3.0, 1.5
        else:
            tp1m, tp2m, slm = 1.0, 2.0, 1.0
        if den == "LONG":
            entry = round(p * 0.999, 4)
            if sw_res:
                tp1 = sw_res[0]
                tp2 = sw_res[1] if len(sw_res) > 1 else round(p + av * tp2m, 4)
            else:
                tp1 = round(p + av * tp1m, 4)
                tp2 = round(p + av * tp2m, 4)
            if sw_sup:
                sl = round(sw_sup[0] * 0.998, 4)
            else:
                sl = round(p - av * slm, 4)
        elif den == "SHORT":
            entry = round(p * 1.001, 4)
            if sw_sup:
                tp1 = sw_sup[0]
                tp2 = sw_sup[1] if len(sw_sup) > 1 else round(p - av * tp2m, 4)
            else:
                tp1 = round(p - av * tp1m, 4)
                tp2 = round(p - av * tp2m, 4)
            if sw_res:
                sl = round(sw_res[0] * 1.002, 4)
            else:
                sl = round(p + av * slm, 4)
        else:
            entry = tp1 = tp2 = sl = p
        rr = round(abs(tp1 - entry) / (abs(sl - entry) + 1e-9), 2)
        return {
            "price": p, "direction": direction, "direction_en": den,
            "strength": strength, "reasons": reasons[:5],
            "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr,
            "rsi": round(rv, 1), "sk": round(kv, 1), "sd": round(dv, 1),
            "mh": round(hv, 6), "adx": round(adx_now, 1),
            "bbu": round(bbu_v, 4), "bbl": round(bbl_v, 4),
            "e20": round(e20, 4), "e50": round(e50, 4), "e200": round(e200, 4),
            "atr": round(av, 4), "regime": regime, "rl": rl,
            "obv": "🟢 遞增" if obv_slope > 0 else "🔴 遞減",
            "div": div_label,
            "vwap": round(vwap_v, 4),
            "st_dir": st_dir,
            "st_line": st_line,
            "pattern": pattern,
            "pattern_type": pattern_type,
            "poc": poc,
            "vah": vah,
            "val": val_v,
            "squeeze_on": squeeze_on,
            "squeeze_released": squeeze_released,
        }

    def signal_consensus(self, sigs):
        directions = [s["direction_en"] for s in sigs]
        if all(d == "LONG" for d in directions):
            return "FULL_LONG", "✅ 三週期一致看多", 1.5, "FULL"
        if all(d == "SHORT" for d in directions):
            return "FULL_SHORT", "✅ 三週期一致看空", 1.5, "FULL"
        long_count = sum(1 for d in directions if d == "LONG")
        short_count = sum(1 for d in directions if d == "SHORT")
        if long_count >= 2 and short_count == 0:
            return "PARTIAL_LONG", "📗 偏多 (2/3)", 1.2, "PARTIAL"
        if short_count >= 2 and long_count == 0:
            return "PARTIAL_SHORT", "📕 偏空 (2/3)", 1.2, "PARTIAL"
        if long_count >= 1 and short_count == 0:
            return "WEAK_LONG", "📊 弱多 (1/3)", 1.0, "PARTIAL"
        if short_count >= 1 and long_count == 0:
            return "WEAK_SHORT", "📊 弱空 (1/3)", 1.0, "PARTIAL"
        return "MIXED", "⚠️ 週期分歧", 0.8, "MIXED"

    # ⭐ 平衡版專業設置（目標勝率 60-70%）
    def professional_setup(self, sig1h, sig4h, sig15m, df1h, df4h, df_daily,
                            sw_res_1h, sw_sup_1h, sw_res_4h, sw_sup_4h,
                            vol_ratio, funding, ls_ratio, fg_val, current_price,
                            rs_btc=None, upside_liq=None, downside_liq=None,
                            btc_df=None, btc_ticker=None, symbol=""):
        direction = sig1h["direction_en"]
        if direction == "NEUTRAL":
            return None, "信號中性"

        p = current_price
        atr_1h = sig1h["atr"]
        atr_4h = sig4h["atr"] if sig4h["atr"] > 0 else atr_1h * 4

        # ===== 必要過濾（放寬版）=====
        has_div = bool(sig1h.get("div"))

        # 強逆勢且無背離 → 過濾
        if direction == "LONG" and sig1h["regime"] == "STRONG_BEAR" and not has_div:
            return None, "強空頭逆勢且無背離"
        if direction == "SHORT" and sig1h["regime"] == "STRONG_BULL" and not has_div:
            return None, "強多頭逆勢且無背離"

        # ADX 放寬到 16（v25 - 允許更多機會）
        if sig1h["adx"] < 16:
            return None, "ADX過低 (<16)"

        # ⭐ Squeeze 過濾：BB 在 KC 內 = 盤整，不交易
        if sig1h.get("squeeze_on", False):
            return None, "Squeeze盤整中"

        # ⭐ v25 假突破偵測（強勢續航時跳過）
        is_strong, _ = self.strong_continuation(df1h, direction)
        if not is_strong:
            is_fake, fake_msg = self.fake_breakout_check(df1h, direction)
            if is_fake:
                return None, "假突破：" + fake_msg

        # ⭐ v23：異常波動保護（黑天鵝事件）
        extreme, extreme_msg = self.extreme_volatility_check(df1h)
        if extreme:
            return None, "異常波動：" + extreme_msg

        # ⭐ v24：MTF 共振從「強制過濾」改為「強烈加分」
        mtf_state, mtf_label = self.mtf_alignment(df1h, df4h, df_daily)
        # 只在「完全反向」時拒絕（多週期都反方向）
        if direction == "LONG" and mtf_state == "STRONG_BEAR_MTF":
            return None, "三週期都看空"
        if direction == "SHORT" and mtf_state == "STRONG_BULL_MTF":
            return None, "三週期都看多"

        # ⭐ v23：反指標檢查
        anti_violations = self.anti_indicator_check(direction, sig1h)
        if anti_violations:
            return None, "反指標：" + ", ".join(anti_violations)

        # 風報比門檻提高到 1.5
        if sig1h["rr"] < 1.3:
            return None, "風報比不足 (<1.3)"

        # ⭐ BTC 健康度檢查（避免逆勢開單）
        btc_health = "UNKNOWN"
        btc_health_msg = ""
        if btc_df is not None and btc_ticker is not None:
            btc_health, btc_health_msg = self.btc_health_check(btc_df, btc_ticker)
            if direction == "LONG" and btc_health == "BAD_FOR_LONG":
                return None, btc_health_msg
            if direction == "SHORT" and btc_health == "BAD_FOR_SHORT":
                return None, btc_health_msg

        # ===== 評分（基礎 50） =====
        score = 50
        factors = []
        risks = []

        # 趨勢順勢加分（最高 18 分）
        if direction == "LONG":
            if sig1h["regime"] == "STRONG_BULL":
                score += 18
                factors.append("✅ 強多頭順勢")
            elif sig1h["regime"] == "BULL":
                score += 12
                factors.append("✅ 多頭順勢")
            elif sig1h["regime"] == "RANGING":
                score += 5
                factors.append("📊 震盪偏多")
            elif sig1h["regime"] == "BEAR" and has_div:
                score += 8
                factors.append("✅ 底背離反轉")
        else:
            if sig1h["regime"] == "STRONG_BEAR":
                score += 18
                factors.append("✅ 強空頭順勢")
            elif sig1h["regime"] == "BEAR":
                score += 12
                factors.append("✅ 空頭順勢")
            elif sig1h["regime"] == "RANGING":
                score += 5
                factors.append("📊 震盪偏空")
            elif sig1h["regime"] == "BULL" and has_div:
                score += 8
                factors.append("✅ 頂背離反轉")

        # 4H 確認
        regime_4h = sig4h["regime"]
        if regime_4h == sig1h["regime"]:
            score += 10
            factors.append("✅ 4H週期一致")
        elif regime_4h == "RANGING":
            score += 5
        elif (direction == "LONG" and regime_4h in ("STRONG_BEAR", "BEAR")) or \
             (direction == "SHORT" and regime_4h in ("STRONG_BULL", "BULL")):
            score -= 5
            risks.append("⚠️ 4H趨勢相反")

        # ADX 強度
        if sig1h["adx"] >= 35:
            score += 10
            factors.append("✅ 強趨勢ADX≥35")
        elif sig1h["adx"] >= 25:
            score += 6
            factors.append("✅ 趨勢明確ADX≥25")
        elif sig1h["adx"] >= 20:
            score += 3

        # 量能
        if vol_ratio >= 1.5:
            score += 8
            factors.append("✅ 量能爆發")
        elif vol_ratio >= 1.2:
            score += 5
            factors.append("✅ 放量")
        elif vol_ratio < 0.7:
            score -= 4
            risks.append("⚠️ 縮量")

        # 資金費率反向
        if funding is not None:
            if direction == "LONG" and funding < -0.02:
                score += 8
                factors.append("✅ 負費率反向")
            elif direction == "SHORT" and funding > 0.02:
                score += 8
                factors.append("✅ 正費率反向")
            elif direction == "LONG" and funding > 0.08:
                score -= 5
                risks.append("⚠️ 多頭過熱")
            elif direction == "SHORT" and funding < -0.08:
                score -= 5
                risks.append("⚠️ 空頭過冷")

        # 多空比反向
        if ls_ratio is not None:
            if direction == "LONG" and ls_ratio < 0.7:
                score += 5
                factors.append("✅ 散戶看空逆向")
            elif direction == "SHORT" and ls_ratio > 2.5:
                score += 5
                factors.append("✅ 散戶看多逆向")

        # 恐懼貪婪
        if direction == "LONG" and fg_val <= 30:
            score += 8
            factors.append("✅ 恐懼區逆向做多")
        elif direction == "SHORT" and fg_val >= 70:
            score += 8
            factors.append("✅ 貪婪區逆向做空")

        # 背離信號
        if has_div:
            score += 12
            factors.append("✅ RSI " + sig1h["div"])

        # 15m 入場確認
        if sig15m["direction_en"] == direction:
            score += 5
            factors.append("✅ 15m入場確認")
        elif sig15m["direction_en"] != "NEUTRAL":
            risks.append("⚠️ 15m方向相反")

        # ⭐ Break of Structure（高權重 - 真趨勢確認）
        bos_1h, bos_level = self.detect_bos(df1h)
        if direction == "LONG" and bos_1h == "BULL_BOS":
            score += 10
            factors.append("✅ 1H結構突破上行")
        elif direction == "SHORT" and bos_1h == "BEAR_BOS":
            score += 10
            factors.append("✅ 1H結構跌破下行")
        bos_4h, _ = self.detect_bos(df4h)
        if direction == "LONG" and bos_4h == "BULL_BOS":
            score += 8
            factors.append("✅ 4H結構突破")
        elif direction == "SHORT" and bos_4h == "BEAR_BOS":
            score += 8
            factors.append("✅ 4H結構跌破")

        # ⭐ Order Block 進場（高勝率區）
        bull_ob, bear_ob = self.find_order_blocks(df1h)
        if direction == "LONG" and bull_ob:
            for ob in bull_ob:
                if ob["low"] <= p <= ob["high"] * 1.005:
                    score += 8
                    factors.append("✅ 在看漲OB內進場")
                    break
        elif direction == "SHORT" and bear_ob:
            for ob in bear_ob:
                if ob["low"] * 0.995 <= p <= ob["high"]:
                    score += 8
                    factors.append("✅ 在看跌OB內進場")
                    break

        # ⭐ FVG（公允價值缺口 - 機構回補區）
        bull_fvg, bear_fvg = self.find_fvg(df1h)
        if direction == "LONG" and bull_fvg:
            for fvg in bull_fvg:
                if fvg["bottom"] <= p <= fvg["top"]:
                    score += 6
                    factors.append("✅ 在看漲FVG內")
                    break
        elif direction == "SHORT" and bear_fvg:
            for fvg in bear_fvg:
                if fvg["bottom"] <= p <= fvg["top"]:
                    score += 6
                    factors.append("✅ 在看跌FVG內")
                    break

        # ⭐ 相對強度（強勢幣做多/弱勢幣做空 加分）
        if rs_btc is not None:
            if direction == "LONG" and rs_btc > 3:
                score += 6
                factors.append("✅ 強於BTC " + str(rs_btc) + "%")
            elif direction == "SHORT" and rs_btc < -3:
                score += 6
                factors.append("✅ 弱於BTC " + str(abs(rs_btc)) + "%")
            elif direction == "LONG" and rs_btc < -5:
                score -= 4
                risks.append("⚠️ 弱於BTC " + str(rs_btc) + "%")
            elif direction == "SHORT" and rs_btc > 5:
                score -= 4
                risks.append("⚠️ 強於BTC " + str(rs_btc) + "%")

        # ⭐ Squeeze 釋放（爆破信號）
        if sig1h.get("squeeze_released"):
            score += 8
            factors.append("✅ Squeeze釋放爆破")

        # ⭐ v24：策略類型分類
        strategy_type, strategy_label = self.classify_strategy(direction, sig1h, sig4h, df1h, vol_ratio)
        strategy_bonus = {
            "BREAKOUT_RETEST": 10,  # 最高勝率
            "MOMENTUM": 7,
            "TREND_FOLLOW": 6,
            "REVERSAL": 3,  # 反轉風險高
            "RANGE": -3,
        }.get(strategy_type, 0)
        if strategy_bonus > 0:
            score += strategy_bonus
            factors.append("✅ " + strategy_label + " +" + str(strategy_bonus))
        elif strategy_bonus < 0:
            risks.append("⚠️ " + strategy_label)

        # ⭐ v25：強勢續航加分（即使 RSI 過熱也能繼續漲）
        is_strong_cont, sc_msg = self.strong_continuation(df1h, direction)
        if is_strong_cont:
            score += 10
            factors.append("✅ " + sc_msg)

        # ⭐ v24：機構吸籌偵測
        smart_money, sm_msg = self.smart_money_detect(df1h, direction)
        if smart_money:
            score += 8
            factors.append("✅ " + sm_msg)

        # ⭐ v24：MTF 共振加分（取代強制過濾）
        if direction == "LONG":
            if mtf_state == "STRONG_BULL_MTF":
                score += 10
                factors.append("✅ 三週期強多共振")
            elif mtf_state == "BULL_MTF":
                score += 5
                factors.append("✅ 雙週期多頭")
            elif mtf_state == "MIXED":
                score -= 2
                risks.append("⚠️ 多週期分歧")
            elif mtf_state == "BEAR_MTF":
                score -= 8
                risks.append("⚠️ 雙週期空頭逆風")
        else:
            if mtf_state == "STRONG_BEAR_MTF":
                score += 10
                factors.append("✅ 三週期強空共振")
            elif mtf_state == "BEAR_MTF":
                score += 5
                factors.append("✅ 雙週期空頭")
            elif mtf_state == "MIXED":
                score -= 2
            elif mtf_state == "BULL_MTF":
                score -= 8
                risks.append("⚠️ 雙週期多頭逆風")

        # ⭐ v23：交易時段加成
        session_code, session_label, session_mult = self.trading_session()
        if session_mult > 1.0:
            session_bonus = round((session_mult - 1) * 20, 1)
            score += session_bonus
            factors.append("✅ " + session_label + " +" + str(session_bonus))
        elif session_mult < 0.9:
            session_penalty = round((1 - session_mult) * 15, 1)
            score -= session_penalty
            risks.append("⚠️ " + session_label)



        # ⭐ Volume Profile 確認
        poc = sig1h.get("poc")
        if poc:
            if direction == "LONG" and p > poc:
                score += 3
                factors.append("✅ 站上POC機構區")
            elif direction == "SHORT" and p < poc:
                score += 3
                factors.append("✅ 跌破POC機構區")

        # 過熱扣分
        if direction == "LONG" and sig1h["rsi"] > 78:
            score -= 6
            risks.append("⚠️ RSI過熱(>78)")
        elif direction == "SHORT" and sig1h["rsi"] < 22:
            score -= 6
            risks.append("⚠️ RSI過冷(<22)")

        score = max(0, min(100, score))

        # ===== ⭐ 專業下單規劃 =====
        # 動態 ATR 倍數
        atr_mult, atr_label = self.dynamic_atr_mult(df1h)
        # Chandelier Exit（吊燈追蹤止損）
        chand_long, chand_short = self.chandelier_exit(df1h)
        # 評分高用中線（4H 阻力支撐），評分低用短線（1H）
        if score >= 75:
            timeframe = "中線（2-7天）"
            ref_res = sw_res_4h if sw_res_4h else sw_res_1h
            ref_sup = sw_sup_4h if sw_sup_4h else sw_sup_1h
            ref_atr = atr_4h
        else:
            timeframe = "短線（4-24小時）"
            ref_res = sw_res_1h
            ref_sup = sw_sup_1h
            ref_atr = atr_1h

        # ⭐ 智能進場價（多種策略）
        if direction == "LONG":
            # 進場：優先看支撐位
            if ref_sup and (p - ref_sup[0]) / p < 0.005:
                entry = round(p * 0.999, 4)
                entry_note = "立即進場（已測支撐）"
            elif ref_sup and (p - ref_sup[0]) / p < 0.015:
                entry = round(ref_sup[0] * 1.002, 4)
                entry_note = "限價單等回測支撐"
            else:
                entry = round(p * 0.997, 4)
                entry_note = "等回調 0.3% 進場"

            # ⭐ Smart Stop Loss（多重保護）
            sl, sl_label = self.smart_stop_loss(
                "LONG", entry, df1h, ref_atr, sw_res_1h, sw_sup_1h,
                chand_long, chand_short, atr_mult
            )

            # ⭐ v24：動態止盈（Fibonacci 擴展 + 阻力強度）
            tp1, tp2, tp3, tp4 = self.dynamic_take_profits(
                "LONG", entry, sl, df1h, ref_res, ref_sup, ref_atr
            )
        else:
            if ref_res and (ref_res[0] - p) / p < 0.005:
                entry = round(p * 1.001, 4)
                entry_note = "立即進場（已測阻力）"
            elif ref_res and (ref_res[0] - p) / p < 0.015:
                entry = round(ref_res[0] * 0.998, 4)
                entry_note = "限價單等反彈阻力"
            else:
                entry = round(p * 1.003, 4)
                entry_note = "等反彈 0.3% 進場"

            # ⭐ Smart Stop Loss
            sl, sl_label = self.smart_stop_loss(
                "SHORT", entry, df1h, ref_atr, sw_res_1h, sw_sup_1h,
                chand_long, chand_short, atr_mult
            )

            # ⭐ v24：動態止盈
            tp1, tp2, tp3, tp4 = self.dynamic_take_profits(
                "SHORT", entry, sl, df1h, ref_res, ref_sup, ref_atr
            )

        risk = abs(entry - sl)
        rr1 = round(abs(tp1 - entry) / risk, 2) if risk > 0 else 0
        rr2 = round(abs(tp2 - entry) / risk, 2) if risk > 0 else 0
        rr3 = round(abs(tp3 - entry) / risk, 2) if risk > 0 else 0
        rr4 = round(abs(tp4 - entry) / risk, 2) if risk > 0 else 0

        if rr2 < 1.5:
            return None, "TP2風報比過低"

        # 勝率：50→50%, 70→60%, 85→70%, 95→75%
        win_rate = 50 + (score - 50) * 0.5
        win_rate = round(min(78, max(50, win_rate)))

        # Kelly 倉位（保守）
        avg_rr = (rr1 + rr2) / 2
        kelly = max(0, (win_rate/100 - (1 - win_rate/100) / avg_rr)) * 100
        position = round(min(kelly * 0.5, 8), 1)

        # 風險等級
        if score >= 80:
            risk_level = "🟢 低風險"
        elif score >= 65:
            risk_level = "🟡 中風險"
        else:
            risk_level = "🟠 中高風險"

        # ⭐ 確認 K 線檢測
        ref_level = entry
        has_conf = self.has_confirmation_candle(df1h, direction, ref_level)

        # ⭐ 進場品質評分（A/B/C/D）
        entry_grade = self.entry_quality_grade(
            direction, p, sig1h, sw_res_1h, sw_sup_1h, vol_ratio, has_conf
        )

        # v24：只拒絕 D 級（C 級也是機會，給用戶選）
        if entry_grade["grade"] == "D":
            return None, "進場時機 D 級不達標"

        # ⭐ 進場理由深度分析
        bull_ob_ck, bear_ob_ck = self.find_order_blocks(df1h)
        bull_fvg_ck, bear_fvg_ck = self.find_fvg(df1h)
        bos_dir_ck, _ = self.detect_bos(df1h)
        has_bos = (direction == "LONG" and bos_dir_ck == "BULL_BOS") or (direction == "SHORT" and bos_dir_ck == "BEAR_BOS")
        has_ob = False
        if direction == "LONG":
            for ob in bull_ob_ck:
                if ob["low"] <= p <= ob["high"] * 1.005:
                    has_ob = True
                    break
        else:
            for ob in bear_ob_ck:
                if ob["low"] * 0.995 <= p <= ob["high"]:
                    has_ob = True
                    break
        has_fvg = False
        relevant_fvg_list = bull_fvg_ck if direction == "LONG" else bear_fvg_ck
        for fvg in relevant_fvg_list:
            if fvg["bottom"] <= p <= fvg["top"]:
                has_fvg = True
                break
        pros, cons = self.entry_reasoning(
            direction, sig1h, sig4h, sw_res_1h, sw_sup_1h,
            vol_ratio, funding, ls_ratio, fg_val,
            has_bos, has_ob, has_fvg, rs_btc, btc_health
        )

        # 倉位根據進場品質調整
        adjusted_position = round(position * entry_grade["pos_mult"], 1)

        # ⭐ 訂單類型判斷（限價 vs 市價）
        # 邏輯：
        # - 進場價 ≤ 現價 0.2% → 市價單立即進場
        # - 進場價需要等價格回到位 → 限價單掛單
        price_diff = abs(entry - p) / p
        if direction == "LONG":
            if entry >= p:
                # 進場價 >= 現價，需要追單 → 市價
                order_type = "MARKET"
                order_type_label = "📍 市價單立即進場"
                order_instruction = "現在就用市價單買進，避免追高"
            elif price_diff < 0.002:
                order_type = "MARKET"
                order_type_label = "📍 市價單立即進場"
                order_instruction = "現價接近進場區，市價單即可"
            else:
                order_type = "LIMIT"
                order_type_label = "📋 限價單掛單等候"
                order_instruction = "在 " + str(entry) + " 掛買單，等價格回測"
        else:
            if entry <= p:
                order_type = "MARKET"
                order_type_label = "📍 市價單立即進場"
                order_instruction = "現在就用市價單做空，避免殺低"
            elif price_diff < 0.002:
                order_type = "MARKET"
                order_type_label = "📍 市價單立即進場"
                order_instruction = "現價接近進場區，市價單即可"
            else:
                order_type = "LIMIT"
                order_type_label = "📋 限價單掛單等候"
                order_instruction = "在 " + str(entry) + " 掛空單，等價格反彈"

        # 限價單有效時間
        if "中線" in timeframe:
            order_valid_hours = 24
        else:
            order_valid_hours = 8

        plan = {
            "score": round(score, 1),
            "win_rate": win_rate,
            "risk_level": risk_level,
            "timeframe": timeframe,
            "entry": entry,
            "entry_note": entry_note,
            "order_type": order_type,
            "order_type_label": order_type_label,
            "order_instruction": order_instruction,
            "order_valid_hours": order_valid_hours,
            "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp4": tp4,
            "sl": sl,
            "rr1": rr1, "rr2": rr2, "rr3": rr3, "rr4": rr4,
            "position": adjusted_position,
            "original_position": position,
            "factors": factors, "risks": risks,
            "atr_label": atr_label,
            "chand_exit": chand_long if direction == "LONG" else chand_short,
            "sl_label": sl_label,
            "entry_grade": entry_grade["grade"],
            "entry_grade_desc": entry_grade["desc"],
            "entry_grade_score": entry_grade["score"],
            "entry_grade_reasons": entry_grade["reasons"],
            "has_confirmation": has_conf,
            "pros": pros,
            "cons": cons,
            "btc_health_msg": btc_health_msg,
            "mtf_state": mtf_state,
            "mtf_label": mtf_label,
            "session_label": session_label,
            "strategy_type": strategy_type,
            "strategy_label": strategy_label,
            "smart_money": smart_money,
        }
        return score, plan

    async def full_analysis(self, symbol):
        try:
            async with aiohttp.ClientSession() as session:
                results = await asyncio.gather(
                    self.fetch_ohlcv(session, symbol, "15m", 200),
                    self.fetch_ohlcv(session, symbol, "1h", 250),
                    self.fetch_ohlcv(session, symbol, "4h", 150),
                    self.fetch_ticker(session, symbol),
                    self.fetch_orderbook(session, symbol),
                    self.fetch_fear_greed(session),
                    self.fetch_funding_rate(session, symbol),
                    self.fetch_long_short_ratio(session, symbol),
                    return_exceptions=True
                )
            if isinstance(results[1], Exception):
                return "❌ 抓取失敗：" + str(results[1])
            df15m = results[0] if not isinstance(results[0], Exception) else results[1]
            df1h = results[1]
            df4h = results[2] if not isinstance(results[2], Exception) else df1h
            ticker = results[3] if not isinstance(results[3], Exception) else {}
            obl, _ = results[4] if not isinstance(results[4], Exception) else ("📒 不可用", 1.0)
            fgl, fgv = results[5] if not isinstance(results[5], Exception) else ("⚪", 50)
            funding = results[6] if not isinstance(results[6], Exception) else None
            ls_ratio = results[7] if not isinstance(results[7], Exception) else None
            current_price = float(ticker.get("lastPrice", 0)) if ticker else float(df1h["close"].iloc[-1])
            sig15m = self.generate_signal(df15m, fgv, current_price)
            sig = self.generate_signal(df1h, fgv, current_price)
            sig4h = self.generate_signal(df4h, fgv, current_price)
            consensus_key, consensus_label, multiplier, _ = self.signal_consensus([sig15m, sig, sig4h])
            piv = self.pivot_sr(df1h)
            sw_res, sw_sup = self.swing_sr(df1h)
            fibs = self.fib_sr(df1h)
            vtl, vol_ratio = self.volume_trend(df1h)
            chg = float(ticker.get("priceChangePercent", 0))
            high24 = float(ticker.get("highPrice", 0))
            low24 = float(ticker.get("lowPrice", 0))
            vol24 = float(ticker.get("quoteVolume", 0)) / 1e6
            icon = "📈" if chg >= 0 else "📉"
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S UTC")
            p = current_price
            breakout_msg = self.breakout_quality(p, sw_res, sw_sup, vol_ratio)
            near_alerts = self.near_key_levels(p, sw_res, sw_sup)
            r = "🔍 *" + symbol + " 即時深度分析*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💰 即時價 `" + str(p) + "` " + icon + " `" + str(round(chg, 2)) + "%`\n"
            r += "📊 24H `" + str(low24) + " ~ " + str(high24) + "`\n"
            r += "💵 24H 量 `$" + str(round(vol24, 1)) + "M`\n"
            r += "🌊 結構 " + sig["rl"] + " | ADX `" + str(sig["adx"]) + "`\n"
            r += "📖 訂單簿 " + obl + "\n"
            r += "📦 量能 " + vtl + "\n"
            r += "😱 情緒 " + fgl + "\n"
            if funding is not None:
                fund_emoji = "🔴" if funding > 0.05 else ("🟢" if funding < -0.05 else "⚪")
                r += "💰 資金費率 " + fund_emoji + " `" + str(funding) + "%`\n"
            if ls_ratio is not None:
                ls_emoji = "🟠 多擁擠" if ls_ratio > 2 else ("🔵 空擁擠" if ls_ratio < 0.5 else "⚪")
                r += "⚖️ 多空比 `" + str(round(ls_ratio, 2)) + "` " + ls_emoji + "\n"
            if breakout_msg or near_alerts:
                r += "\n*━━ 🚨 即時警示 ━━*\n"
                if breakout_msg:
                    r += breakout_msg + "\n"
                for a in near_alerts:
                    r += a + "\n"
            r += "\n*━━ 📊 技術指標 ━━*\n"
            r += "• RSI `" + str(sig["rsi"]) + "`"
            if sig["rsi"] > 70:
                r += " ⚠️超買"
            elif sig["rsi"] < 30:
                r += " ⚠️超賣"
            r += "\n"
            r += "• StochRSI K/D `" + str(sig["sk"]) + "/" + str(sig["sd"]) + "`\n"
            r += "• MACD柱 `" + str(sig["mh"]) + "`\n"
            r += "• 布林 `" + str(sig["bbu"]) + " / " + str(sig["bbl"]) + "`\n"
            r += "• EMA `" + str(sig["e20"]) + "/" + str(sig["e50"]) + "/" + str(sig["e200"]) + "`\n"
            r += "• OBV " + sig["obv"] + " | ATR `" + str(sig["atr"]) + "`\n"
            r += "• VWAP `" + str(sig["vwap"]) + "`"
            if p > sig["vwap"]:
                r += " 📈 價格在VWAP上方\n"
            else:
                r += " 📉 價格在VWAP下方\n"
            st_emoji = "🟢" if sig["st_dir"] == 1 else "🔴"
            r += "• SuperTrend " + st_emoji + " `" + str(sig["st_line"]) + "`\n"
            if sig["div"]:
                r += "• 🎯 " + sig["div"] + "\n"
            r += "\n*━━ 🎯 支撐阻力 ━━*\n"
            if sw_res:
                r += "• 阻力 `" + " / ".join(str(x) for x in sw_res[:3]) + "`\n"
            if sw_sup:
                r += "• 支撐 `" + " / ".join(str(x) for x in sw_sup[:3]) + "`\n"
            r += "\n━━━━━━━━━━━━━━━━━━━━\n"
            r += "*━━ ⏰ 多週期共識 ━━*\n"
            r += "15m " + sig15m["direction"] + " | 1H " + sig["direction"] + " | 4H " + sig4h["direction"] + "\n"
            r += consensus_label + "\n\n"
            if sig["direction_en"] != "NEUTRAL":
                r += "🎯 *方向：" + sig["direction"] + "*\n"
                final_strength = round(sig["strength"] * multiplier)
                r += "💪 強度 `" + str(min(final_strength, 100)) + "%`\n"
                r += "📋 " + " | ".join(sig["reasons"][:3]) + "\n\n"
                r += "🎯 進場 `" + str(sig["entry"]) + "`\n"
                r += "🏁 止盈1 `" + str(sig["tp1"]) + "`\n"
                r += "🏆 止盈2 `" + str(sig["tp2"]) + "`\n"
                r += "🛑 止損 `" + str(sig["sl"]) + "`\n"
                r += "⚖️ 風報 `1:" + str(sig["rr"]) + "`"
            else:
                r += "🟡 *建議觀望* (強度 " + str(round(sig["strength"])) + "%)\n"
                if sig["reasons"]:
                    r += "📋 " + " | ".join(sig["reasons"][:3])
            r += "\n\n⚠️ _僅供參考_"
            return r
        except Exception as e:
            return "❌ 分析失敗：" + str(e)

    # ⭐ 平衡版黑潮船長
    async def golden_hunter(self, smart_filter=False, min_score=60):
        try:
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S UTC")
            candidates = []
            async with aiohttp.ClientSession() as session:
                fg_result = await self.fetch_fear_greed(session)
                fg_val = fg_result[1] if not isinstance(fg_result, Exception) else 50
                tasks = []
                # ⭐ 速度優化：移除 daily K 線，節省 30 個請求（快約 20%）
                for sym in self.SCAN_POOL:
                    tasks.append(self.fetch_ohlcv(session, sym, "15m", 100))
                    tasks.append(self.fetch_ohlcv(session, sym, "1h", 200))
                    tasks.append(self.fetch_ohlcv(session, sym, "4h", 150))
                    tasks.append(self.fetch_ticker(session, sym))
                    tasks.append(self.fetch_funding_rate(session, sym))
                    tasks.append(self.fetch_long_short_ratio(session, sym))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                ok_count = 0
                stride = 6
                # ⭐ BTC 數據緩存（用於相關性 + 健康度檢查）
                btc_df_cache = None
                btc_ticker_cache = None
                for idx, sym in enumerate(self.SCAN_POOL):
                    if sym == "BTC/USDT":
                        r1h = results[idx*stride+1]
                        r_ticker = results[idx*stride+3]
                        if not isinstance(r1h, Exception):
                            btc_df_cache = r1h
                        if not isinstance(r_ticker, Exception):
                            btc_ticker_cache = r_ticker
                        break
                for i, sym in enumerate(self.SCAN_POOL):
                    df15m = results[i*stride]
                    df1h = results[i*stride+1]
                    df4h = results[i*stride+2]
                    ticker = results[i*stride+3]
                    funding = results[i*stride+4]
                    ls_ratio = results[i*stride+5]
                    df_d = df1h  # 移除 daily，用 1h 替代
                    if isinstance(df1h, Exception):
                        continue
                    ok_count += 1
                    if isinstance(ticker, Exception):
                        ticker = {}
                    if isinstance(df15m, Exception):
                        df15m = df1h
                    if isinstance(df4h, Exception):
                        df4h = df1h
                    if isinstance(df_d, Exception):
                        df_d = df1h
                    if isinstance(funding, Exception):
                        funding = None
                    if isinstance(ls_ratio, Exception):
                        ls_ratio = None
                    try:
                        current_price = float(ticker.get("lastPrice", 0)) if ticker else float(df1h["close"].iloc[-1])
                        if current_price == 0:
                            continue
                        sig1h = self.generate_signal(df1h, fg_val, current_price)
                        if sig1h["direction_en"] == "NEUTRAL":
                            continue
                        vol24 = float(ticker.get("quoteVolume", 0)) / 1e6
                        if vol24 < 20:
                            continue
                        sig15m = self.generate_signal(df15m, fg_val, current_price)
                        sig4h = self.generate_signal(df4h, fg_val, current_price)
                        sw_res_1h, sw_sup_1h = self.swing_sr(df1h)
                        sw_res_4h, sw_sup_4h = self.swing_sr(df4h)
                        _, vol_ratio = self.volume_trend(df1h)
                        # ⭐ 進場時機
                        rsi_v = sig1h["rsi"]
                        e20_v = sig1h["e20"]
                        direction_for_timing = sig1h["direction_en"]
                        timing_emoji, timing_reason = self.entry_timing(
                            current_price, direction_for_timing,
                            sw_res_1h, sw_sup_1h, rsi_v, vol_ratio, e20_v
                        )
                        # ⭐ 多指標重疊買點
                        fib = self.fib_sr(df1h)
                        piv = self.pivot_sr(df1h)
                        confluence_indicators = {
                            "EMA20": sig1h["e20"], "EMA50": sig1h["e50"], "EMA200": sig1h["e200"],
                            "VWAP": sig1h["vwap"], "BB上": sig1h["bbu"], "BB下": sig1h["bbl"],
                            "Fib0.236": fib["0.236"], "Fib0.382": fib["0.382"],
                            "Fib0.5": fib["0.5"], "Fib0.618": fib["0.618"], "Fib0.786": fib["0.786"],
                            "P": piv["P"], "R1": piv["R1"], "R2": piv["R2"],
                            "S1": piv["S1"], "S2": piv["S2"],
                        }
                        # 加入 swing
                        for i, s in enumerate(sw_sup_1h[:3]):
                            confluence_indicators["支撐" + str(i+1)] = s
                        for i, s in enumerate(sw_res_1h[:3]):
                            confluence_indicators["阻力" + str(i+1)] = s
                        confluence_zones = self.confluence_levels(current_price, confluence_indicators)
                        whale_signals = []  # v15 移除：用量能推導不準
                        # ⭐ 相對強度 vs BTC
                        rs_btc = None
                        if btc_df_cache is not None and sym != "BTC/USDT":
                            rs_btc = self.relative_strength(df1h, btc_df_cache)
                        # ⭐ 流動性區
                        upside_liq, downside_liq = self.liquidity_zones(df1h)
                        result = self.professional_setup(
                            sig1h, sig4h, sig15m, df1h, df4h, df_d,
                            sw_res_1h, sw_sup_1h, sw_res_4h, sw_sup_4h,
                            vol_ratio, funding, ls_ratio, fg_val, current_price,
                            rs_btc=rs_btc, upside_liq=upside_liq, downside_liq=downside_liq,
                            btc_df=btc_df_cache, btc_ticker=btc_ticker_cache,
                            symbol=sym
                        )
                        if result[0] is None:
                            continue
                        score, plan = result
                        # 套用最低分過濾
                        if score < min_score:
                            continue
                        chg = float(ticker.get("priceChangePercent", 0))
                        # ⭐ BTC 相關性
                        btc_corr = None
                        if btc_df_cache is not None and sym != "BTC/USDT":
                            btc_corr = self.btc_correlation(df1h, btc_df_cache)
                        # ⭐ 信號有效期
                        expiry_time, expiry_hours = self.signal_expiry(plan["timeframe"])
                        # ⭐ 信號指紋（用於去重）
                        sig_hash = self.signal_fingerprint(
                            sym, sig1h["direction_en"], plan["entry"], plan["sl"], plan["tp1"]
                        )
                        # ⭐ 市場類型
                        mkt_type, mkt_label = self.market_type(df1h)
                        # ⭐ SMC 分析
                        bull_ob_h, bear_ob_h = self.find_order_blocks(df1h)
                        bull_fvg_h, bear_fvg_h = self.find_fvg(df1h)
                        bos_dir, bos_level = self.detect_bos(df1h)
                        candidates.append({
                            "bull_ob": bull_ob_h, "bear_ob": bear_ob_h,
                            "bull_fvg": bull_fvg_h, "bear_fvg": bear_fvg_h,
                            "bos_dir": bos_dir, "bos_level": bos_level,
                            "symbol": sym,
                            "sig1h": sig1h,
                            "plan": plan,
                            "vol24": vol24,
                            "chg": chg,
                            "current_price": current_price,
                            "funding": funding,
                            "ls_ratio": ls_ratio,
                            "btc_corr": btc_corr,
                            "expiry_time": expiry_time,
                            "expiry_hours": expiry_hours,
                            "timing_emoji": timing_emoji,
                            "timing_reason": timing_reason,
                            "confluence_zones": confluence_zones,
                            "whale_signals": whale_signals,
                            "pattern": sig1h.get("pattern"),
                            "rs_btc": rs_btc,
                            "upside_liq": upside_liq,
                            "downside_liq": downside_liq,
                            "sig_hash": sig_hash,
                            "mkt_label": mkt_label,
                        })
                    except Exception:
                        continue

            if smart_filter:
                # v27 更寬鬆：信心 ≥55 OR 突破回踩 OR 機構吸籌 OR 強勢續航 OR 動能爆發
                high_quality = []
                for c in candidates:
                    p = c["plan"]
                    if p["score"] >= 55:
                        high_quality.append(c)
                        continue
                    strat = p.get("strategy_type", "")
                    if strat in ("BREAKOUT_RETEST", "MOMENTUM"):
                        high_quality.append(c)
                        continue
                    if p.get("smart_money", False):
                        high_quality.append(c)
                        continue
                if not high_quality:
                    return None
                candidates = high_quality

            if not candidates:
                return ("🎯 *黑潮船長 — " + now + "*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "📡 已掃描 " + str(ok_count) + "/" + str(len(self.SCAN_POOL)) + " 幣種\n"
                        "📊 通過過濾後無符合條件機會\n\n"
                        "⏳ 建議等待：\n"
                        "• 趨勢更明確（ADX≥18）\n"
                        "• 風報比 ≥1.3 的設置\n"
                        "• 評分 ≥55 的信號\n\n"
                        "_市場可能盤整或方向不明_")

            candidates.sort(key=lambda x: x["plan"]["score"], reverse=True)
            r = "🌊 *黑潮船長｜交易機會播報*\n"
            r += "_" + now + "_\n"
            r += "━━━━━━━━━━━━━━━\n"
            # ⭐ v24：一句話結論
            if candidates:
                top = candidates[0]
                top_sym = top["symbol"].replace("/USDT", "")
                top_dir = "做多" if top["sig1h"]["direction_en"] == "LONG" else "做空"
                top_strat = top["plan"].get("strategy_label", "順勢進場")
                top_score = top["plan"].get("score", 0)
                top_pos = top["plan"].get("position", 5)
                expected_pct = abs(top["plan"]["tp2"] - top["plan"]["entry"]) / top["plan"]["entry"] * 100
                r += "💡 *建議*：" + top_sym + " " + top_dir + " — " + top_strat + "\n"
                r += "   倉位 " + str(top_pos) + "%、目標 +" + str(round(expected_pct, 1)) + "%、勝率 " + str(top["plan"]["win_rate"]) + "%\n"
            r += "📡 掃描 " + str(len(self.SCAN_POOL)) + " 幣，找到 *" + str(len(candidates)) + "* 個機會\n"
            # 整體市場狀態（簡短摘要）
            if candidates:
                avg_score = sum(c["plan"]["score"] for c in candidates[:3]) / min(3, len(candidates))
                if avg_score >= 80:
                    market_tone = "🟢 *本輪行情品質佳*，建議積極跟進"
                elif avg_score >= 70:
                    market_tone = "🟡 *本輪行情中等*，挑選 A 級進場"
                else:
                    market_tone = "🟠 *本輪行情普通*，建議小倉試水"
                r += market_tone + "\n"
            r += "\n"

            for rank, c in enumerate(candidates[:5], 1):
                sig = c["sig1h"]
                p = c["plan"]
                direction_zh = "做多" if sig["direction_en"] == "LONG" else "做空"
                direction_emoji = "🟢" if sig["direction_en"] == "LONG" else "🔴"
                medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")

                # === 標題區 ===
                r += medal + " *" + c["symbol"].replace("/USDT", "") + " " + direction_zh + " " + direction_emoji + "*\n"

                # === 進場品質徽章（最醒目）===
                grade = p.get("entry_grade", "C")
                grade_text = {
                    "A": "🥇 *A 級機會* — 強烈推薦跟進",
                    "B": "🥈 *B 級機會* — 半倉跟進",
                    "C": "🥉 *C 級機會* — 1/3 倉試水",
                }.get(grade, "")
                r += grade_text + "\n"
                # ⭐ v24：策略類型
                if p.get("strategy_label"):
                    r += "🎯 " + p.get("strategy_label", "") + "\n"
                # MTF + 時段資訊
                if p.get("mtf_label"):
                    r += "📐 " + p.get("mtf_label", "") + " | " + p.get("session_label", "") + "\n"

                # === 一句話總結 ===
                r += "_" + direction_zh + " · " + p["timeframe"] + " · 預估勝率 " + str(p["win_rate"]) + "%_\n"
                r += "─────────────\n"

                # === 為什麼推薦（最重要）===
                r += "💭 *分析師說明*\n"
                # 從 pros 挑最強的 4 個理由，用自然語氣串起來
                if p.get("pros"):
                    top_pros = p["pros"][:4]
                    for pro in top_pros:
                        r += "  " + pro + "\n"
                # 風險點
                if p.get("cons"):
                    r += "\n⚠️ *需要留意*\n"
                    for con in p["cons"][:3]:
                        r += "  " + con + "\n"
                r += "\n"

                # === 下單指令（明確）===
                r += "📝 *下單指令*\n"
                r += "  *訂單類型*：" + p.get("order_type_label", "") + "\n"
                r += "  *執行方式*：" + p.get("order_instruction", "") + "\n"
                if p.get("order_type") == "LIMIT":
                    r += "  *有效時間*：" + str(p.get("order_valid_hours", 8)) + " 小時內未成交請取消\n"
                r += "\n"

                # === 價格規劃（清晰）===
                r += "📊 *價格規劃*\n"
                r += "  • 當前價：`" + str(c["current_price"]) + "`\n"
                r += "  • 進場價：`" + str(p["entry"]) + "`\n"
                r += "  • 止損價：`" + str(p["sl"]) + "` (" + p.get("sl_label", "智能") + ")\n"
                # 計算止損百分比
                if sig["direction_en"] == "LONG":
                    sl_pct = (p["entry"] - p["sl"]) / p["entry"] * 100
                else:
                    sl_pct = (p["sl"] - p["entry"]) / p["entry"] * 100
                r += "  • 止損幅度：`" + str(round(sl_pct, 2)) + "%`\n"
                r += "\n"

                # === 分批止盈計劃 ===
                r += "🎯 *分批止盈計劃*\n"
                if sig["direction_en"] == "LONG":
                    tp1_pct = (p["tp1"] - p["entry"]) / p["entry"] * 100
                    tp2_pct = (p["tp2"] - p["entry"]) / p["entry"] * 100
                    tp3_pct = (p["tp3"] - p["entry"]) / p["entry"] * 100
                    tp4_pct = (p["tp4"] - p["entry"]) / p["entry"] * 100
                else:
                    tp1_pct = (p["entry"] - p["tp1"]) / p["entry"] * 100
                    tp2_pct = (p["entry"] - p["tp2"]) / p["entry"] * 100
                    tp3_pct = (p["entry"] - p["tp3"]) / p["entry"] * 100
                    tp4_pct = (p["entry"] - p["tp4"]) / p["entry"] * 100
                r += "  ① `" + str(p["tp1"]) + "` (+`" + str(round(tp1_pct, 2)) + "%`) 平 25% _保本出場_\n"
                r += "  ② `" + str(p["tp2"]) + "` (+`" + str(round(tp2_pct, 2)) + "%`) 平 35%\n"
                r += "  ③ `" + str(p["tp3"]) + "` (+`" + str(round(tp3_pct, 2)) + "%`) 平 25%\n"
                r += "  ④ `" + str(p["tp4"]) + "` (+`" + str(round(tp4_pct, 2)) + "%`) 移動止損守剩 15%\n"
                r += "\n"

                # === 倉位建議 ===
                r += "💼 *倉位建議*\n"
                r += "  建議使用資金的 *" + str(p["position"]) + "%*"
                orig_pos = p.get("original_position", p["position"])
                if p["position"] < orig_pos:
                    r += " _(根據" + grade + "級調整)_"
                r += "\n"
                r += "  風報比 1:" + str(p["rr2"]) + " 至 1:" + str(p["rr4"]) + "\n"

                # === 確認 K 線提醒 ===
                if not p.get("has_confirmation"):
                    r += "\n⏳ _目前尚未出現確認 K 線，建議等待下根 1H K 收盤後再進場_\n"

                r += "\n"

            # === 整體交易守則 ===
            r += "━━━━━━━━━━━━━━━\n"
            r += "💡 *使用建議*\n"
            r += "• A 級信號可正常倉位跟進\n"
            r += "• B 級信號減半倉跟進\n"
            r += "• C 級信號用 1/3 倉試水\n"
            r += "• 嚴守止損，到價就出場\n"
            r += "• 達 TP1 立即移止損至成本價（保本）\n"

            # === 時段警示 ===
            avoid_warnings = self.should_avoid_trading()
            if avoid_warnings:
                r += "\n⚠️ *當前時段提醒*\n"
                for w in avoid_warnings:
                    r += "  " + w + "\n"

            r += "\n_⚠️ 加密貨幣風險極高，本訊息僅為策略參考_\n"
            r += "_⚠️ 黑潮船長將自動追蹤本輪信號並通知關鍵價位_"
            return r
        except Exception as e:
            return "❌ 黑潮船長失敗：" + str(e)

    async def detect_movers(self):
        """市場異動掃描 — 資深分析師版"""
        try:
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            async with aiohttp.ClientSession() as session:
                tasks = []
                for s in self.SCAN_POOL:
                    tasks.append(self.fetch_ticker(session, s))
                    tasks.append(self.fetch_ohlcv(session, s, "1h", 50))
                results = await asyncio.gather(*tasks, return_exceptions=True)
            data = []
            for i, sym in enumerate(self.SCAN_POOL):
                t = results[i*2]
                df = results[i*2+1]
                if isinstance(t, Exception):
                    continue
                try:
                    chg = float(t.get("priceChangePercent", 0))
                    vol = float(t.get("quoteVolume", 0)) / 1e6
                    price = float(t.get("lastPrice", 0))
                    if price == 0:
                        continue
                    # 計算 1H 波動率（量能異常檢測）
                    vol_ratio = 1.0
                    rsi_v = 50
                    if not isinstance(df, Exception):
                        try:
                            avg_vol = float(df["volume"].rolling(20).mean().iloc[-1])
                            curr_vol = float(df["volume"].iloc[-1])
                            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1
                            rsi_v = self.safe_val(self.rsi(df), 50)
                        except Exception:
                            pass
                    data.append({
                        "symbol": sym.replace("/USDT", ""),
                        "chg": chg, "vol": vol, "price": price,
                        "vol_ratio": vol_ratio, "rsi": round(rsi_v, 0)
                    })
                except Exception:
                    continue
            if not data:
                return "❌ 無法取得任何數據"

            top_gainers = sorted(data, key=lambda x: x["chg"], reverse=True)[:5]
            top_losers = sorted(data, key=lambda x: x["chg"])[:5]
            top_volume = sorted(data, key=lambda x: x["vol"], reverse=True)[:5]
            top_vol_surge = sorted([d for d in data if d["vol_ratio"] > 1.5],
                                    key=lambda x: x["vol_ratio"], reverse=True)[:5]

            r = "⚡ *市場異動掃描* | " + now + "\n"
            r += "━━━━━━━━━━━━━━━\n"
            r += "📡 掃描 " + str(len(data)) + "/" + str(len(self.SCAN_POOL)) + "\n\n"

            r += "*🚀 漲幅榜 TOP 5*\n"
            for c in top_gainers:
                vr = " 量爆`" + str(round(c["vol_ratio"], 1)) + "x`" if c["vol_ratio"] > 1.5 else ""
                rsi_warn = " ⚠️過熱" if c["rsi"] > 75 else ""
                r += "• *" + c["symbol"] + "* `" + str(round(c["price"], 4)) + "` 📈`+" + str(round(c["chg"], 2)) + "%`" + vr + rsi_warn + "\n"

            r += "\n*📉 跌幅榜 TOP 5*\n"
            for c in top_losers:
                vr = " 量爆`" + str(round(c["vol_ratio"], 1)) + "x`" if c["vol_ratio"] > 1.5 else ""
                rsi_warn = " ⚠️過冷" if c["rsi"] < 25 else ""
                r += "• *" + c["symbol"] + "* `" + str(round(c["price"], 4)) + "` 📉`" + str(round(c["chg"], 2)) + "%`" + vr + rsi_warn + "\n"

            if top_vol_surge:
                r += "\n*🔥 量能爆發 TOP 5*\n"
                for c in top_vol_surge:
                    icon = "📈" if c["chg"] >= 0 else "📉"
                    r += "• *" + c["symbol"] + "* " + icon + "`" + str(round(c["chg"], 1)) + "%`"
                    r += " 量`" + str(round(c["vol_ratio"], 1)) + "x` 24H`$" + str(round(c["vol"], 0)) + "M`\n"

            r += "\n*💵 成交量 TOP 5*\n"
            for c in top_volume:
                icon = "📈" if c["chg"] >= 0 else "📉"
                r += "• *" + c["symbol"] + "* `$" + str(round(c["vol"], 0)) + "M` " + icon + "`" + str(round(c["chg"], 1)) + "%`\n"

            # 專業分析
            avg_chg = sum(d["chg"] for d in data) / len(data)
            gainers_count = sum(1 for d in data if d["chg"] > 0)
            losers_count = sum(1 for d in data if d["chg"] < 0)
            vol_surge_count = sum(1 for d in data if d["vol_ratio"] > 1.5)

            r += "━━━━━━━━━━━━━━━\n"
            r += "📊 *市場概況*\n"
            r += "• 平均漲跌 `" + str(round(avg_chg, 2)) + "%`\n"
            r += "• 上漲/下跌 `" + str(gainers_count) + "/" + str(losers_count) + "`\n"
            r += "• 異常爆量幣種 `" + str(vol_surge_count) + "` 個\n\n"

            r += "💡 *分析師判讀*\n"
            if avg_chg > 3 and vol_surge_count >= 5:
                r += "🚀 強勁多頭擴散，山寨輪動\n• 策略：追蹤量爆且未過熱的領漲幣"
            elif avg_chg > 1.5 and gainers_count > losers_count * 2:
                r += "📈 多頭氣氛濃厚\n• 策略：選擇漲幅+量能榜重疊幣種"
            elif avg_chg < -3 and vol_surge_count >= 5:
                r += "💥 恐慌性下跌\n• 策略：避免抄底，等止跌訊號"
            elif avg_chg < -1.5 and losers_count > gainers_count * 2:
                r += "📉 整體偏弱\n• 策略：減倉觀望，反彈做空"
            elif vol_surge_count >= 8:
                r += "⚡ 多幣種異動，可能有大事件\n• 注意關注新聞動向"
            elif abs(avg_chg) < 0.5:
                r += "↔️ 市場膠著，方向未明\n• 策略：減少交易，等突破"
            else:
                r += "⚪ 漲跌互現，輪動為主\n• 策略：個股操作，避免重倉"
            return r
        except Exception as e:
            return "❌ 失敗：" + str(e)


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
            ticker = results[5] if not isinstance(results[5], Exception) else {}
            current_price = float(ticker.get("lastPrice", 0)) if ticker else 0
            if current_price == 0 and not isinstance(results[2], Exception):
                current_price = float(results[2]["close"].iloc[-1])
            chg = float(ticker.get("priceChangePercent", 0))
            timeframes = [
                ("1分K", results[0], 30),
                ("15分K", results[1], 50),
                ("1小時K", results[2], 50),
                ("4小時K", results[3], 50),
                ("日K", results[4], 50),
            ]
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S UTC")
            r = "📊 *" + symbol + " 多週期支撐阻力*\n"
            r += "🕒 " + now + "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💰 即時價 `" + str(current_price) + "` "
            r += "📈" if chg >= 0 else "📉"
            r += " `" + str(round(chg, 2)) + "%`\n\n"
            for name, df, lookback in timeframes:
                if isinstance(df, Exception):
                    r += "❌ " + name + "\n\n"
                    continue
                piv = self.pivot_sr(df, lookback)
                sw_res, sw_sup = self.swing_sr(df)
                regime, _, adx_v = self.market_regime(df)
                r += "*━━ ⏰ " + name + " ━━*\n"
                r += "趨勢 " + regime + " | ADX `" + str(round(adx_v)) + "`\n"
                r += "🔴 R `" + str(piv["R1"]) + " / " + str(piv["R2"]) + "`\n"
                r += "⚪ P `" + str(piv["P"]) + "`\n"
                r += "🟢 S `" + str(piv["S1"]) + " / " + str(piv["S2"]) + "`\n"
                if sw_res:
                    r += "🎯 阻力 `" + " / ".join(str(x) for x in sw_res[:2]) + "`\n"
                if sw_sup:
                    r += "🎯 支撐 `" + " / ".join(str(x) for x in sw_sup[:2]) + "`\n"
                r += "\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n"
            r += "💡 多週期支撐/阻力重疊 → 強位置"
            return r
        except Exception as e:
            return "❌ 失敗：" + str(e)

    async def get_market_sentiment(self):
        """市場情緒總覽 — 資深分析師版"""
        try:
            async with aiohttp.ClientSession() as session:
                results = await asyncio.gather(
                    self.fetch_news(session),
                    self.fetch_fear_greed(session),
                    self.fetch_global(session),
                    self.fetch_ticker(session, "BTC/USDT"),
                    self.fetch_ticker(session, "ETH/USDT"),
                    self.fetch_ticker(session, "SOL/USDT"),
                    self.fetch_ohlcv(session, "BTC/USDT", "1h", 100),
                    self.fetch_ohlcv(session, "ETH/USDT", "1h", 100),
                    self.fetch_ohlcv(session, "SOL/USDT", "1h", 100),
                    self.ecosystem_pulse(session),
                    self.fetch_btc_dominance(session),
                    self.fetch_crypto_events(session),
                    self.fetch_funding_rate(session, "BTC/USDT"),
                    self.fetch_long_short_ratio(session, "BTC/USDT"),
                    return_exceptions=True
                )
                econ_events = self.upcoming_econ_events()

            news = results[0] if not isinstance(results[0], Exception) else []
            fgl, fgv = results[1] if not isinstance(results[1], Exception) else ("⚪", 50)
            global_data = results[2] if not isinstance(results[2], Exception) else None
            btc_ticker = results[3] if not isinstance(results[3], Exception) else {}
            eth_ticker = results[4] if not isinstance(results[4], Exception) else {}
            sol_ticker = results[5] if not isinstance(results[5], Exception) else {}
            btc_df = results[6] if not isinstance(results[6], Exception) else None
            eth_df = results[7] if not isinstance(results[7], Exception) else None
            sol_df = results[8] if not isinstance(results[8], Exception) else None
            eco_pulse = results[9] if not isinstance(results[9], Exception) else None
            btc_dom_data = results[10] if not isinstance(results[10], Exception) else (None, None)
            crypto_events = results[11] if not isinstance(results[11], Exception) else []
            btc_funding = results[12] if not isinstance(results[12], Exception) else None
            btc_ls = results[13] if not isinstance(results[13], Exception) else None

            sent_score, sent_label, news_items = self.sentiment(news)
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")

            # ─── 關鍵指標儀表板（一眼看全局）───
            r = "🌐 *加密市場全景報告* | " + now + "\n"
            r += "━━━━━━━━━━━━━━━\n"

            # 多空力道判斷（綜合多個指標）
            bull_score = 0
            bear_score = 0
            if fgv >= 60: bull_score += 1
            elif fgv <= 40: bear_score += 1
            if sent_score > 0.2: bull_score += 1
            elif sent_score < -0.2: bear_score += 1
            if global_data and global_data["mcap_change"] > 1: bull_score += 1
            elif global_data and global_data["mcap_change"] < -1: bear_score += 1
            if btc_ticker:
                bchg = float(btc_ticker.get("priceChangePercent", 0))
                if bchg > 2: bull_score += 1
                elif bchg < -2: bear_score += 1
            if btc_dom_data and btc_dom_data[0]:
                if btc_dom_data[0] > 58: bear_score += 1  # BTC.D 高對山寨不利
                elif btc_dom_data[0] < 50: bull_score += 1

            if bull_score >= bear_score + 2:
                mkt_signal = "🟢 *偏多*"
            elif bear_score >= bull_score + 2:
                mkt_signal = "🔴 *偏空*"
            else:
                mkt_signal = "🟡 *中性*"

            r += "📊 綜合判讀 " + mkt_signal + " (" + str(bull_score) + "多 vs " + str(bear_score) + "空)\n"

            # ─── 關鍵數據（密集顯示）───
            r += "*━━ 📈 關鍵數據 ━━*\n"
            r += "• 恐懼貪婪 " + fgl + "\n"
            r += "• 新聞情緒 " + sent_label + " `" + str(round(sent_score, 2)) + "`\n"
            if global_data:
                ch = global_data["mcap_change"]
                ch_icon = "📈" if ch >= 0 else "📉"
                r += "• 總市值 `$" + str(global_data["total_mcap"]) + "B` " + ch_icon + " `" + str(ch) + "%`\n"
                r += "• BTC占比 `" + str(global_data["btc_dom"]) + "%` | ETH占比 `" + str(global_data["eth_dom"]) + "%`\n"
            if btc_dom_data and btc_dom_data[0] is not None:
                r += "• BTC.D 走勢 " + btc_dom_data[1] + "\n"
            if btc_funding is not None:
                fund_emoji = "🔴" if btc_funding > 0.05 else ("🟢" if btc_funding < -0.05 else "⚪")
                r += "• BTC 資金費率 " + fund_emoji + " `" + str(btc_funding) + "%`\n"
            if btc_ls is not None:
                ls_emoji = "🟠 多擁擠" if btc_ls > 2 else ("🔵 空擁擠" if btc_ls < 0.5 else "⚪")
                r += "• BTC 多空比 `" + str(round(btc_ls, 2)) + "` " + ls_emoji + "\n"

            # ─── 主流幣快速評分（最重要區塊）───
            r += "*━━ 🚀 主流幣即時評分 ━━*\n"

            def score_coin(symbol, ticker, df):
                if df is None or not ticker:
                    return None
                try:
                    p = float(ticker.get("lastPrice", df["close"].iloc[-1]))
                    chg = float(ticker.get("priceChangePercent", 0))
                    rsi_v = self.safe_val(self.rsi(df), 50)
                    adx_v = self.safe_val(self.adx(df), 20)
                    rl, regime, _ = self.market_regime(df)
                    # 評分（簡化版）
                    score = 50
                    if regime == "STRONG_BULL": score += 20
                    elif regime == "BULL": score += 10
                    elif regime == "STRONG_BEAR": score -= 20
                    elif regime == "BEAR": score -= 10
                    if adx_v >= 30: score += 5 if regime in ("STRONG_BULL", "BULL") else -5
                    if rsi_v >= 70: score -= 5
                    elif rsi_v <= 30: score += 5
                    score = max(0, min(100, score))
                    # 評級
                    if score >= 70: rating = "🟢 強"
                    elif score >= 55: rating = "🟡 偏多"
                    elif score >= 45: rating = "⚪ 中性"
                    elif score >= 30: rating = "🟠 偏空"
                    else: rating = "🔴 弱"
                    icon = "📈" if chg >= 0 else "📉"
                    return {
                        "price": p, "chg": chg, "rsi": round(rsi_v, 0),
                        "adx": round(adx_v, 0), "regime": rl,
                        "score": score, "rating": rating, "icon": icon
                    }
                except Exception:
                    return None

            for sym, ticker, df, label in [
                ("BTC", btc_ticker, btc_df, "BTC"),
                ("ETH", eth_ticker, eth_df, "ETH"),
                ("SOL", sol_ticker, sol_df, "SOL"),
            ]:
                s = score_coin(sym, ticker, df)
                if s:
                    r += "• *" + label + "* `" + str(round(s["price"], 2)) + "` " + s["icon"]
                    r += " `" + str(round(s["chg"], 1)) + "%`\n"
                    r += "  評級 " + s["rating"] + " `" + str(s["score"]) + "/100`"
                    r += " | RSI`" + str(int(s["rsi"])) + "` ADX`" + str(int(s["adx"])) + "`\n"

            # ─── ETH/SOL 生態（密集顯示）───
            if eco_pulse:
                eth_avg = eco_pulse["eth_avg"]
                sol_avg = eco_pulse["sol_avg"]
                eth_emoji = "📈" if eth_avg >= 0 else "📉"
                sol_emoji = "📈" if sol_avg >= 0 else "📉"
                r += "*━━ 🌐 生態脈動 ━━*\n"
                r += "• ETH 系 " + eth_emoji + " `" + str(eth_avg) + "%`"
                if eco_pulse["eth_coins"]:
                    top_eth = sorted(eco_pulse["eth_coins"], key=lambda x: x[1], reverse=True)[:3]
                    r += " 領漲：" + " ".join(s + "`" + str(round(c, 1)) + "%`" for s, c in top_eth)
                r += "\n"
                r += "• SOL 系 " + sol_emoji + " `" + str(sol_avg) + "%`"
                if eco_pulse["sol_coins"]:
                    top_sol = sorted(eco_pulse["sol_coins"], key=lambda x: x[1], reverse=True)[:3]
                    r += " 領漲：" + " ".join(s + "`" + str(round(c, 1)) + "%`" for s, c in top_sol)
                r += "\n"

            # ─── 經濟事件（緊湊版）───
            if econ_events:
                r += "*━━ 📅 重要事件倒數 ━━*\n"
                for ev in econ_events[:3]:
                    r += "• " + ev["impact"] + " " + ev["name"] + " — `" + ev["date"] + "` (" + str(ev["days"]) + "天)\n"

            # ─── 加密幣事件日曆 ───
            if crypto_events:
                r += "*━━ 🗓 加密幣事件 ━━*\n"
                for ev in crypto_events[:5]:
                    title = ev.get("title", "")[:50]
                    date = ev.get("date", "")
                    typ = ev.get("type", "")
                    type_emoji = "🔓" if typ == "Unlock" else ("🚀" if typ == "Listing" else ("⚙️" if typ == "Upgrade" else "📌"))
                    r += "• " + type_emoji + " " + title
                    if date:
                        r += " `" + date + "`"
                    r += "\n"

            # ─── 即時新聞 ───
            if news_items:
                r += "*━━ 📰 即時新聞 ━━*\n"
                for i, item in enumerate(news_items[:6], 1):
                    time_ago = self.format_published(item.get("published", ""))
                    line = item["emoji"] + " " + item["title"][:70]
                    if time_ago:
                        line += " _(" + time_ago + ")_"
                    r += str(i) + ". " + line + "\n"

            # ─── 今日交易建議（核心）───
            r += "━━━━━━━━━━━━━━━\n"
            r += "💡 *今日交易建議*\n"

            if bull_score >= 4 and bear_score <= 1:
                r += "🟢 強烈偏多訊號\n"
                r += "• 策略：順勢做多，加碼領漲幣\n"
                r += "• 重點：強多頭幣種突破回踩進場\n"
                r += "• 風險：避免追高過熱幣（RSI>75）"
            elif bull_score >= 3 and bull_score > bear_score:
                r += "📗 偏多但謹慎\n"
                r += "• 策略：選擇性做多，分批進場\n"
                r += "• 重點：等回調支撐再進場\n"
                r += "• 警示：留意 BTC 走勢是否轉弱"
            elif bear_score >= 4 and bull_score <= 1:
                r += "🔴 強烈偏空訊號\n"
                r += "• 策略：做空反彈位，避免抄底\n"
                r += "• 重點：強空頭幣種反彈進場做空\n"
                r += "• 風險：避免在恐慌底部追空"
            elif bear_score >= 3 and bear_score > bull_score:
                r += "📕 偏空謹慎\n"
                r += "• 策略：減倉觀望，反彈做空\n"
                r += "• 重點：嚴守止損，控制倉位\n"
                r += "• 警示：跌破關鍵支撐加速下跌"
            elif fgv <= 25:
                r += "🔵 極度恐懼區（潛在機會）\n"
                r += "• 策略：分批佈局價值幣\n"
                r += "• 重點：BTC/ETH 定投策略\n"
                r += "• 警示：底部可能延後"
            elif fgv >= 75:
                r += "🟠 極度貪婪區（危險訊號）\n"
                r += "• 策略：減倉至 30%，鎖利為主\n"
                r += "• 重點：嚴格止盈，不追高\n"
                r += "• 警示：隨時可能回調"
            else:
                r += "⚪ 中性盤整\n"
                r += "• 策略：等突破訊號，減少交易\n"
                r += "• 重點：嚴選黑潮船長高分機會\n"
                r += "• 警示：盤整易雙巴，注意止損"

            # 時段警示
            avoid_warnings = self.should_avoid_trading()
            if avoid_warnings:
                r += "\n⚠️ " + " | ".join(avoid_warnings)

            return r
        except Exception as e:
            return "❌ 失敗：" + str(e)

    async def trend_watch(self, symbols):
        """市場趨勢總覽 — 資深分析師版"""
        try:
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")
            async with aiohttp.ClientSession() as session:
                tasks = []
                for s in symbols:
                    tasks.append(self.fetch_ohlcv(session, s, "1h", 200))
                    tasks.append(self.fetch_ohlcv(session, s, "4h", 100))
                    tasks.append(self.fetch_ticker(session, s))
                results = await asyncio.gather(*tasks, return_exceptions=True)
            strong_bull, bull, bear, strong_bear, ranging = [], [], [], [], []
            ok_count = 0
            for i, sym in enumerate(symbols):
                df = results[i*3]
                df4h = results[i*3+1]
                ticker = results[i*3+2]
                if isinstance(df, Exception):
                    continue
                ok_count += 1
                ticker = ticker if not isinstance(ticker, Exception) else {}
                df4h = df4h if not isinstance(df4h, Exception) else df
                rl, regime, adx_v = self.market_regime(df)
                rl_4h, regime_4h, _ = self.market_regime(df4h)
                chg = float(ticker.get("priceChangePercent", 0))
                price = float(ticker.get("lastPrice", 0)) or float(df["close"].iloc[-1])
                rsi_v = self.safe_val(self.rsi(df), 50)
                vol = float(ticker.get("quoteVolume", 0)) / 1e6
                aligned = (regime_4h == regime) or (
                    regime in ("STRONG_BULL", "BULL") and regime_4h in ("STRONG_BULL", "BULL")
                ) or (
                    regime in ("STRONG_BEAR", "BEAR") and regime_4h in ("STRONG_BEAR", "BEAR")
                )
                info = {
                    "symbol": sym.replace("/USDT", ""), "price": price, "chg": chg,
                    "adx": round(adx_v), "rsi": round(rsi_v, 0), "vol": round(vol, 1),
                    "aligned": aligned, "regime_4h": rl_4h
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

            r = "🔭 *市場趨勢總覽* | " + now + "\n"
            r += "━━━━━━━━━━━━━━━\n"
            # 多空力道
            bulls_total = len(strong_bull) * 2 + len(bull)
            bears_total = len(strong_bear) * 2 + len(bear)
            total_w = bulls_total + bears_total + 1
            bull_pct = round(bulls_total / total_w * 100)
            bear_pct = round(bears_total / total_w * 100)
            r += "📡 掃描 " + str(ok_count) + " | 多空力道 多`" + str(bull_pct) + "%` vs 空`" + str(bear_pct) + "%`\n"
            if ok_count == 0:
                return r + "❌ 抓取全部失敗"

            def fmt(coin):
                aligned_mark = "✅" if coin["aligned"] else "⚠️"
                line = "• " + aligned_mark + " *" + coin["symbol"] + "* `" + str(round(coin["price"], 4)) + "` "
                line += ("📈" if coin["chg"] >= 0 else "📉") + "`" + str(round(coin["chg"], 1)) + "%`"
                line += " ADX`" + str(coin["adx"]) + "` RSI`" + str(int(coin["rsi"])) + "`"
                if coin["vol"] >= 100:
                    line += " 量`$" + str(int(coin["vol"])) + "M`"
                line += "\n"
                return line

            if strong_bull:
                r += "*🚀 強多頭 (" + str(len(strong_bull)) + ")*\n"
                for c in sorted(strong_bull, key=lambda x: x["adx"], reverse=True):
                    r += fmt(c)
            if bull:
                r += "*📈 多頭 (" + str(len(bull)) + ")*\n"
                for c in sorted(bull, key=lambda x: x["chg"], reverse=True):
                    r += fmt(c)
            if ranging:
                r += "*↔️ 震盪 (" + str(len(ranging)) + ")*\n"
                shown = sorted(ranging, key=lambda x: abs(x["chg"]), reverse=True)[:6]
                for c in shown:
                    r += fmt(c)
                if len(ranging) > 6:
                    r += "  _還有 " + str(len(ranging) - 6) + " 個震盪中_\n"
            if bear:
                r += "*📉 空頭 (" + str(len(bear)) + ")*\n"
                for c in sorted(bear, key=lambda x: x["chg"]):
                    r += fmt(c)
            if strong_bear:
                r += "*💥 強空頭 (" + str(len(strong_bear)) + ")*\n"
                for c in sorted(strong_bear, key=lambda x: x["adx"], reverse=True):
                    r += fmt(c)

            r += "━━━━━━━━━━━━━━━\n"
            r += "✅ 1H+4H 一致 (高勝率) | ⚠️ 週期分歧\n\n"
            r += "💡 *操作建議*\n"
            # 找出最強和最弱
            best_long = None
            best_short = None
            if strong_bull:
                best_long = sorted(strong_bull, key=lambda x: (-int(x["aligned"]), -x["adx"]))[0]
            elif bull:
                best_long = sorted(bull, key=lambda x: (-int(x["aligned"]), -x["chg"]))[0]
            if strong_bear:
                best_short = sorted(strong_bear, key=lambda x: (-int(x["aligned"]), -x["adx"]))[0]
            elif bear:
                best_short = sorted(bear, key=lambda x: (-int(x["aligned"]), x["chg"]))[0]

            if bull_pct > 60:
                r += "🟢 市場偏多，優先做多\n"
                if best_long:
                    r += "🎯 首選做多：*" + best_long["symbol"] + "* (ADX " + str(best_long["adx"]) + ")\n"
                r += "   進場：回調至支撐位"
            elif bear_pct > 60:
                r += "🔴 市場偏空，優先做空\n"
                if best_short:
                    r += "🎯 首選做空：*" + best_short["symbol"] + "* (ADX " + str(best_short["adx"]) + ")\n"
                r += "   進場：反彈至阻力位"
            elif len(ranging) > (len(strong_bull) + len(strong_bear) + len(bull) + len(bear)):
                r += "↔️ 市場盤整，減少交易\n"
                r += "   策略：等待方向明確再進場"
            else:
                r += "⚪ 多空分歧，嚴選 ✅ 標的\n"
                if best_long:
                    r += "   做多備選：*" + best_long["symbol"] + "*\n"
                if best_short:
                    r += "   做空備選：*" + best_short["symbol"] + "*"
            return r
        except Exception as e:
            return "❌ 失敗：" + str(e)