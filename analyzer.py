import asyncio
import aiohttp
import pandas as pd
import numpy as np
import re
import os
import json
import hashlib
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


# ===== v55 新聞分析模組（獨立、安全、可關閉）=====
# 設計原則：完全自包含。沒設 API key 或抓取失敗 → 靜默回傳「無數據」，絕不影響主流程。
# 用 CryptoPanic 免費 API 抓新聞 + Claude Haiku 分析市場情緒。
# ⭐ 第一版「零權重觀察模式」：只顯示，不參與開單決策。

_NEWS_CACHE = {"data": None, "ts": 0}  # 快取，避免每次掃描都叫 API 浪費錢
_NEWS_CACHE_TTL = 600  # 10 分鐘內用快取（新聞不會 10 分鐘變很多次）

_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_CRYPTOPANIC_TOKEN = os.environ.get("CRYPTOPANIC_TOKEN", "")  # 可選，沒有也能用免費端點
_NEWS_ENABLED = bool(_ANTHROPIC_KEY)  # 至少要有 Claude key 才啟用


async def _fetch_crypto_news(session, limit=10):
    """抓最近的加密新聞標題。失敗回傳空列表，不拋錯。
    來源優先順序：CryptoPanic → CryptoCompare → PA News RSS
    """
    # 1. CryptoPanic（有 token 優先，無 token 用公開端點）
    try:
        if _CRYPTOPANIC_TOKEN:
            url = "https://cryptopanic.com/api/v1/posts/?auth_token=" + _CRYPTOPANIC_TOKEN + "&public=true&kind=news"
        else:
            url = "https://cryptopanic.com/api/v1/posts/?public=true&kind=news"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                titles = [p.get("title", "") for p in data.get("results", [])[:limit] if p.get("title")]
                if titles:
                    return titles
    except Exception as e:
        logger.warning("CryptoPanic 新聞失敗，嘗試備援: " + str(e))

    # 2. CryptoCompare fallback
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest&categories=Regulation,Trading,Market"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                titles = [x.get("title", "") for x in data.get("Data", [])[:limit] if x.get("title")]
                if titles:
                    return titles
    except Exception as e:
        logger.warning("CryptoCompare 新聞失敗，嘗試備援: " + str(e))

    # 3. PA News RSS fallback
    try:
        url = "https://www.panewslab.com/zh/rss/index.xml"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8),
                               headers={"User-Agent": "Mozilla/5.0"}) as resp:
            if resp.status == 200:
                text = await resp.text()
                titles = []
                for item in re.findall(r"<item>(.*?)</item>", text, re.DOTALL)[:limit]:
                    m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",
                                  item, re.DOTALL)
                    if m:
                        t = (m.group(1) or m.group(2) or "").strip()
                        if t:
                            titles.append(t)
                if titles:
                    return titles
    except Exception as e:
        logger.warning("PA News 新聞失敗: " + str(e))

    logger.error("所有新聞來源均失敗")
    return []


async def _analyze_news_with_claude(session, headlines):
    """用 Claude Haiku 分析新聞情緒。回傳 dict 或 None。"""
    if not headlines or not _ANTHROPIC_KEY:
        return None
    try:
        news_text = "\n".join("- " + h for h in headlines)
        prompt = (
            "你是加密貨幣市場分析助手。以下是最近的加密貨幣新聞標題：\n\n"
            + news_text +
            "\n\n請分析整體市場情緒，並嚴格按以下 JSON 格式回答（不要任何其他文字）：\n"
            '{"sentiment": "看多/看空/中性", "strength": 1-5的整數, '
            '"major_event": true或false, "reason": "一句話理由（繁體中文，30字內）"}\n\n'
            "注意：strength 是情緒強度，5最強。major_event 指有沒有重大事件"
            "（監管、交易所暴雷、大型駭客、宏觀政策等）。"
            "若新聞普通無方向，sentiment 填中性。"
        )
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }
        headers = {
            "x-api-key": _ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        async with session.post("https://api.anthropic.com/v1/messages",
                                json=payload, headers=headers,
                                timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.error("Claude API 回傳 " + str(resp.status))
                return None
            result = await resp.json()
            text = result["content"][0]["text"].strip()
            # 去掉可能的 markdown 圍欄
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
            return parsed
    except Exception as e:
        logger.error("Claude 新聞分析失敗: " + str(e))
        return None


async def get_news_sentiment():
    """
    對外主入口：回傳新聞情緒分析 dict，或 None（未啟用/失敗）。
    帶 10 分鐘快取，避免重複叫 API。
    回傳格式：{"sentiment","strength","major_event","reason","headlines_count"}
    """
    if not _NEWS_ENABLED:
        return None
    # 快取
    now = datetime.now(timezone.utc).timestamp()
    if _NEWS_CACHE["data"] and (now - _NEWS_CACHE["ts"]) < _NEWS_CACHE_TTL:
        return _NEWS_CACHE["data"]
    try:
        async with aiohttp.ClientSession() as session:
            headlines = await _fetch_crypto_news(session)
            if not headlines:
                return None
            analysis = await _analyze_news_with_claude(session, headlines)
            if analysis:
                analysis["headlines_count"] = len(headlines)
                _NEWS_CACHE["data"] = analysis
                _NEWS_CACHE["ts"] = now
                logger.info("✅ 新聞分析: " + str(analysis.get("sentiment")) + " 強度" + str(analysis.get("strength")))
            return analysis
    except Exception as e:
        logger.error("新聞情緒分析失敗: " + str(e))
        return None


def format_news_section(analysis):
    """把新聞分析格式化成顯示文字。零權重觀察模式：標明僅供參考。"""
    if not analysis:
        return ""
    emoji = {"看多": "🟢", "看空": "🔴", "中性": "⚪"}.get(analysis.get("sentiment", "中性"), "⚪")
    try:
        strength = int(analysis.get("strength", 0))
        strength = max(0, min(5, strength))  # 夾在 0~5
    except (ValueError, TypeError):
        strength = 0
    bars = "▮" * strength + "▯" * (5 - strength)
    s = "\n📰 *市場快訊分析* _(觀察中·不影響開單)_\n"
    s += emoji + " 情緒：" + str(analysis.get("sentiment", "中性")) + "  強度 " + bars + "\n"
    if analysis.get("major_event"):
        s += "⚠️ *偵測到重大事件，請特別留意*\n"
    s += "_" + str(analysis.get("reason", "")) + "_\n"
    return s






# ===== K 線圖繪製模組（v28 內嵌，避免漏傳）=====
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Patch
    _CHART_OK = True
except ImportError:
    _CHART_OK = False
    logging.warning("matplotlib 未安裝，圖表功能停用")

from io import BytesIO


# ===== 圖表主題色（全局常數）=====
BG = '#0f1419'
BULL = '#26a69a'
BEAR = '#ef5350'
WHITE = '#ffffff'
GOLD = '#ffd700'
PURPLE = '#ba68c8'
GREEN_ACCENT = '#00e676'
RED_ACCENT = '#ff1744'
YELLOW = '#ffeb3b'


def _style_axis(ax, ylabel=None):
    """統一的軸樣式"""
    ax.set_facecolor(BG)
    ax.tick_params(colors='#aaa', labelsize=9)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']:
        ax.spines[spine].set_color('#444')
        ax.spines[spine].set_linewidth(0.8)
    ax.grid(True, alpha=0.06, color='#888', linewidth=0.5)
    if ylabel:
        ax.set_ylabel(ylabel, color='#aaa', fontsize=9.5)


def plot_signal_chart(df, symbol, timeframe, direction,
                       entry=None, sl=None, tp1=None, tp2=None, tp3=None, tp4=None,
                       support_levels=None, resistance_levels=None,
                       title_suffix="", subtitle=""):
    """v34 專業版：清晰標籤、不重疊、視覺風險回報區、精美樣式"""
    df = df.tail(60).reset_index(drop=True)  # 從 80 → 60，K 線更粗
    n = len(df)

    # 建立 figure，更大的尺寸
    fig = plt.figure(figsize=(13, 8), facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # === K 線（v34 更粗更清晰）===
    for i in range(n):
        row = df.iloc[i]
        o, c, h, l = float(row['open']), float(row['close']), float(row['high']), float(row['low'])
        is_bull = c >= o
        color = BULL if is_bull else BEAR
        # 影線
        ax1.plot([i, i], [l, h], color=color, linewidth=1.5, alpha=0.95, zorder=3)
        # 實體（更粗）
        body_h = abs(c - o) or c * 0.0001
        body_y = min(o, c)
        ax1.add_patch(Rectangle(
            (i - 0.42, body_y), 0.84, body_h,
            facecolor=color, edgecolor=color, linewidth=0.5,
            alpha=0.95, zorder=3
        ))

    # === EMA ===
    if n >= 20:
        ema20 = df['close'].ewm(span=20).mean()
        ax1.plot(range(n), ema20, color=GOLD, linewidth=1.6,
                 label='EMA20', alpha=0.95, zorder=4)
    if n >= 50:
        ema50 = df['close'].ewm(span=50).mean()
        ax1.plot(range(n), ema50, color=PURPLE, linewidth=1.6,
                 label='EMA50', alpha=0.95, zorder=4)

    current = float(df['close'].iloc[-1])

    # === Y 軸範圍計算（含緩衝） ===
    all_prices = [float(df['high'].max()), float(df['low'].min()), current]
    for v in [entry, sl, tp1, tp2, tp3]:
        if v: all_prices.append(v)
    if support_levels: all_prices.extend([s for s in support_levels[:2] if s])
    if resistance_levels: all_prices.extend([r for r in resistance_levels[:2] if r])
    y_min = min(all_prices) * 0.992
    y_max = max(all_prices) * 1.008
    y_range = y_max - y_min
    ax1.set_ylim(y_min, y_max)

    # X 軸：右邊預留 22% 空間給標籤
    label_zone_start = n + 1
    label_zone_end = n + int(n * 0.28)
    ax1.set_xlim(-1, label_zone_end + 1)

    # === 視覺風險回報區（v34 重點優化）===
    if entry and sl:
        if direction == "LONG":
            # 止損區（紅色，從 entry 到 sl，向下）
            ax1.fill_betweenx([sl, entry], -1, n - 0.5,
                              color=RED_ACCENT, alpha=0.10, zorder=1)
            # 止盈區（綠色，從 entry 向上到 tp3）
            if tp3 and tp3 > entry:
                ax1.fill_betweenx([entry, tp3], -1, n - 0.5,
                                  color=GREEN_ACCENT, alpha=0.10, zorder=1)
        else:
            # SHORT：止損區在上方
            ax1.fill_betweenx([entry, sl], -1, n - 0.5,
                              color=RED_ACCENT, alpha=0.10, zorder=1)
            if tp3 and tp3 < entry:
                ax1.fill_betweenx([tp3, entry], -1, n - 0.5,
                                  color=GREEN_ACCENT, alpha=0.10, zorder=1)

    # === 收集要繪製的價位線 ===
    levels = []  # (price, label_text, color, linestyle, linewidth, alpha, importance)
    # importance: 3=主線(ENTRY/SL), 2=止盈, 1=支撐阻力

    # 支撐阻力（低優先）
    if support_levels:
        for i, s in enumerate(support_levels[:2]):
            if s and y_min < s < y_max:
                # 跳過跟 SL 太近的（差距 < 0.3%）
                if sl and abs(s - sl) / sl < 0.003:
                    continue
                levels.append((s, f'S{i+1}', '#4caf50', '--', 1.0, 0.4, 1))

    if resistance_levels:
        for i, r in enumerate(resistance_levels[:2]):
            if r and y_min < r < y_max:
                # 跳過跟 TP 太近的
                skip = False
                for tp in [tp1, tp2, tp3]:
                    if tp and abs(r - tp) / tp < 0.003:
                        skip = True; break
                if skip: continue
                levels.append((r, f'R{i+1}', '#f44336', '--', 1.0, 0.4, 1))

    # 止盈（高優先）
    for tp, lname in [(tp1, 'TP1'), (tp2, 'TP2'), (tp3, 'TP3')]:
        if tp and y_min < tp < y_max:
            levels.append((tp, lname, GREEN_ACCENT, ':', 1.8, 0.9, 2))

    # 進場、止損（最高優先）
    if entry:
        levels.append((entry, 'ENTRY', WHITE, '-', 2.4, 1.0, 3))
    if sl:
        levels.append((sl, 'SL', RED_ACCENT, ':', 2.2, 1.0, 3))

    # 畫橫線
    for price, lname, color, ls, lw, alpha, _ in levels:
        ax1.axhline(y=price, color=color, linestyle=ls, linewidth=lw,
                    alpha=alpha, zorder=2)

    # === v34 智能標籤排布（避免重疊）===
    # 按 Y 從低到高排序
    levels_sorted = sorted(levels, key=lambda x: x[0])
    min_gap = y_range * 0.038  # 標籤間最小垂直距離

    # 計算每個標籤的「目標」Y 位置（避免重疊）
    label_positions = []
    last_y = -float('inf')
    for price, lname, color, ls, lw, alpha, imp in levels_sorted:
        target_y = max(price, last_y + min_gap)
        label_positions.append((target_y, price, lname, color, imp))
        last_y = target_y

    # 繪製標籤（用 boxstyle 包起來，避免被線蓋住）
    label_x = label_zone_start
    for label_y, price, lname, color, imp in label_positions:
        # 文字格式
        if imp == 3:  # ENTRY/SL
            fs = 11; weight = 'bold'
        elif imp == 2:  # TP
            fs = 10; weight = 'bold'
        else:  # S/R
            fs = 8; weight = 'normal'

        # 智能格式化價格
        if price >= 1000:
            price_str = f'{price:,.1f}'
        elif price >= 1:
            price_str = f'{price:.3f}'
        else:
            price_str = f'{price:.6f}'

        full_text = f' {lname}  {price_str} '

        # 連接線：從實際價位到標籤位置
        if abs(label_y - price) > min_gap * 0.5:
            ax1.plot([n - 0.5, label_x - 0.3], [price, label_y],
                     color=color, linewidth=0.7, alpha=0.5, zorder=2)

        # 標籤框
        ax1.text(
            label_x, label_y, full_text,
            color=color, fontsize=fs, va='center', ha='left',
            weight=weight, family='monospace',
            bbox=dict(
                boxstyle='round,pad=0.35',
                facecolor='#1a2230', edgecolor=color,
                linewidth=1.2 if imp >= 2 else 0.8,
                alpha=0.95
            ),
            zorder=6
        )

    # === 現價標記（v34 強化）===
    # 大圓點 + 脈衝外圈
    ax1.scatter([n - 1], [current], s=300, color=YELLOW,
                alpha=0.2, zorder=8, edgecolor='none')
    ax1.scatter([n - 1], [current], s=120, color=YELLOW,
                zorder=9, edgecolor=BG, linewidth=2)

    # 現價標籤（放在 K 線上方，顯眼但不擋路）
    if direction == "LONG":
        ax1.annotate(
            f'NOW {current:,.1f}' if current >= 1000 else f'NOW {current:.4f}',
            xy=(n - 1, current),
            xytext=(n - 8, current),
            color=YELLOW, fontsize=10, va='center', ha='right',
            weight='bold', family='monospace',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a2230',
                      edgecolor=YELLOW, linewidth=1, alpha=0.95),
            zorder=10
        )
    else:
        ax1.annotate(
            f'NOW {current:,.1f}' if current >= 1000 else f'NOW {current:.4f}',
            xy=(n - 1, current),
            xytext=(n - 8, current),
            color=YELLOW, fontsize=10, va='center', ha='right',
            weight='bold', family='monospace',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a2230',
                      edgecolor=YELLOW, linewidth=1, alpha=0.95),
            zorder=10
        )

    # === 風險回報比文字（左上）===
    if entry and sl and tp2:
        risk = abs(entry - sl)
        reward = abs(tp2 - entry)
        rr = reward / risk if risk > 0 else 0
        risk_pct = risk / entry * 100
        reward_pct = reward / entry * 100
        info_text = (
            f'Risk: {risk_pct:.2f}%  |  '
            f'Reward(TP2): {reward_pct:.2f}%  |  '
            f'R/R: 1:{rr:.2f}'
        )
        ax1.text(
            0.015, 0.96, info_text,
            transform=ax1.transAxes, color='#aaa', fontsize=9.5,
            va='top', ha='left', family='monospace',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a2230',
                      edgecolor='#444', linewidth=0.8, alpha=0.85),
            zorder=10
        )

    # === 樣式 ===
    ax1.set_facecolor(BG)
    ax1.tick_params(colors='#aaa', labelsize=9)
    for spine in ['top', 'right']:
        ax1.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']:
        ax1.spines[spine].set_color('#444')
        ax1.spines[spine].set_linewidth(0.8)
    ax1.grid(True, alpha=0.06, color='#888', linewidth=0.5)
    ax1.legend(
        loc='upper left',
        bbox_to_anchor=(0.015, 0.88),
        framealpha=0.6, fontsize=9,
        facecolor='#1a2230', labelcolor='white',
        edgecolor='#444', borderpad=0.4
    )

    # Y 軸價格格式化
    if current >= 1000:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    elif current >= 1:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.3f}'))
    else:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.6f}'))

    # === 標題（v34 增強）===
    direction_arrow = "▲" if direction == "LONG" else "▼"
    direction_text = "LONG" if direction == "LONG" else "SHORT"
    direction_color = BULL if direction == "LONG" else BEAR
    title_main = f'{symbol}   {timeframe}    {direction_arrow} {direction_text}'
    if title_suffix:
        title_main += f'    {title_suffix}'
    ax1.set_title(title_main, color=direction_color, fontsize=15,
                  weight='bold', pad=18, family='sans-serif')

    if subtitle:
        ax1.text(0.5, 1.02, subtitle, transform=ax1.transAxes,
                 ha='center', va='bottom', color='#bbb', fontsize=10,
                 style='italic')

    # === 成交量 ===
    colors_vol = [BULL if df['close'].iloc[i] >= df['open'].iloc[i] else BEAR
                  for i in range(n)]
    ax2.bar(range(n), df['volume'], color=colors_vol,
            alpha=0.8, width=0.8)
    if n >= 20:
        vol_ma = df['volume'].rolling(20).mean()
        ax2.plot(range(n), vol_ma, color=GOLD, linewidth=1.3,
                 alpha=0.85, label='Vol MA20')
        ax2.legend(loc='upper left', framealpha=0.5, fontsize=8.5,
                   facecolor='#1a2230', labelcolor='white',
                   edgecolor='#444', borderpad=0.3)

    ax2.set_facecolor(BG)
    ax2.tick_params(colors='#aaa', labelsize=8.5)
    for spine in ['top', 'right']:
        ax2.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']:
        ax2.spines[spine].set_color('#444')
        ax2.spines[spine].set_linewidth(0.8)
    ax2.grid(True, alpha=0.06, color='#888', axis='y', linewidth=0.5)
    ax2.set_ylabel('Volume', color='#aaa', fontsize=9.5)
    ax2.set_xlim(-1, label_zone_end + 1)
    # 隱藏 ax1 的 x 軸 tick labels
    plt.setp(ax1.get_xticklabels(), visible=False)

    plt.subplots_adjust(left=0.06, right=0.99, top=0.92, bottom=0.06, hspace=0.05)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120,
                bbox_inches='tight', facecolor=BG,
                pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf



def plot_simple_chart(df, symbol, timeframe, title_suffix=""):
    """v35 簡化版 K 線圖（含風險資訊）"""
    # 防呆：空資料
    if df is None or len(df) < 2:
        return _make_empty_chart(f"{symbol} {timeframe}", "No data available")

    df = df.tail(60).reset_index(drop=True)
    n = len(df)

    fig = plt.figure(figsize=(12, 7), facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # K 線
    for i in range(n):
        row = df.iloc[i]
        o, c, h, l = float(row['open']), float(row['close']), float(row['high']), float(row['low'])
        color = BULL if c >= o else BEAR
        ax1.plot([i, i], [l, h], color=color, linewidth=1.5, alpha=0.95)
        body_h = abs(c - o) or c * 0.0001
        ax1.add_patch(Rectangle(
            (i - 0.42, min(o, c)), 0.84, body_h,
            facecolor=color, edgecolor=color, linewidth=0.5, alpha=0.95
        ))

    # EMA
    if n >= 20:
        ema20 = df['close'].ewm(span=20).mean()
        ax1.plot(range(n), ema20, color=GOLD, linewidth=1.6, label='EMA20', alpha=0.95)
    if n >= 50:
        ema50 = df['close'].ewm(span=50).mean()
        ax1.plot(range(n), ema50, color=PURPLE, linewidth=1.6, label='EMA50', alpha=0.95)

    current = float(df['close'].iloc[-1])
    first_close = float(df['close'].iloc[0])
    chg_pct = (current - first_close) / first_close * 100

    # 統計資訊（右上）
    high_60 = float(df['high'].max())
    low_60 = float(df['low'].min())

    def fmt(p):
        if p >= 1000: return f'{p:,.1f}'
        elif p >= 1: return f'{p:.3f}'
        else: return f'{p:.6f}'

    info = (
        f'Now: {fmt(current)}  |  '
        f'Range: {fmt(low_60)} ~ {fmt(high_60)}  |  '
        f'Change: {"+" if chg_pct >= 0 else ""}{chg_pct:.2f}%'
    )
    ax1.text(
        0.015, 0.96, info,
        transform=ax1.transAxes, color='#aaa', fontsize=9.5,
        va='top', ha='left', family='monospace',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a2230',
                  edgecolor='#444', linewidth=0.8, alpha=0.85)
    )

    # 現價點
    ax1.scatter([n - 1], [current], s=120, color=YELLOW,
                zorder=9, edgecolor=BG, linewidth=2)

    _style_axis(ax1)
    if n >= 20:
        ax1.legend(loc='upper left', bbox_to_anchor=(0.015, 0.88),
                   framealpha=0.6, fontsize=9,
                   facecolor='#1a2230', labelcolor='white',
                   edgecolor='#444', borderpad=0.4)

    if current >= 1000:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    elif current >= 1:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.3f}'))
    else:
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.6f}'))

    chg_color = BULL if chg_pct >= 0 else BEAR
    title = f'{symbol}   {timeframe}'
    if title_suffix:
        title += f'   {title_suffix}'
    ax1.set_title(title, color=chg_color, fontsize=14, weight='bold', pad=15)

    # 成交量
    colors_vol = [BULL if df['close'].iloc[i] >= df['open'].iloc[i] else BEAR for i in range(n)]
    ax2.bar(range(n), df['volume'], color=colors_vol, alpha=0.8, width=0.8)
    if n >= 20:
        vol_ma = df['volume'].rolling(20).mean()
        ax2.plot(range(n), vol_ma, color=GOLD, linewidth=1.3, alpha=0.85, label='Vol MA20')
        ax2.legend(loc='upper left', framealpha=0.5, fontsize=8.5,
                   facecolor='#1a2230', labelcolor='white',
                   edgecolor='#444', borderpad=0.3)
    _style_axis(ax2, 'Volume')
    plt.setp(ax1.get_xticklabels(), visible=False)

    plt.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.07, hspace=0.05)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG, pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_empty_chart(title, message):
    """生成「無數據」提示圖（避免空白圖被推播）"""
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG)
    ax.set_facecolor(BG)
    ax.text(0.5, 0.6, title, transform=ax.transAxes,
            ha='center', va='center', color='white',
            fontsize=18, weight='bold')
    ax.text(0.5, 0.4, message, transform=ax.transAxes,
            ha='center', va='center', color='#aaa', fontsize=13)
    ax.axis('off')
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=110, facecolor=BG, pad_inches=0.2)
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_movers_chart(gainers, losers, title="MARKET MOVERS  |  24H"):
    """v56 漲跌榜（視覺強化：名次、強度漸層、漲跌過濾）"""
    if not gainers and not losers:
        return _make_empty_chart("MARKET MOVERS", "No mover data")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.6), facecolor=BG)

    def _panel(ax, rows, color, is_gain):
        rows = [x for x in (rows or []) if (x[1] > 0 if is_gain else x[1] < 0)][:8]
        if not rows:
            ax.text(0.5, 0.5, 'No data', transform=ax.transAxes, ha='center',
                    va='center', color='#666', fontsize=12)
            _style_axis(ax)
            return
        labels = [f"{i+1}. {r[0]}" for i, r in enumerate(rows)]
        values = [r[1] for r in rows]
        y = range(len(labels))
        n = len(values)
        alphas = [0.95 - 0.5 * (i / max(n - 1, 1)) for i in range(n)]
        bars = ax.barh(list(y), values, color=color, edgecolor='#0f1419', linewidth=0.6)
        for b, al in zip(bars, alphas):
            b.set_alpha(al)
        ax.set_yticks(list(y))
        ax.set_yticklabels(labels, color=WHITE, fontsize=11, weight='bold')
        peak = max(values) if is_gain else min(values)
        pad = abs(peak) * 0.02 if peak else 0.1
        for i, v in enumerate(values):
            txt = f' +{v:.2f}%' if is_gain else f'{v:.2f}% '
            ax.text(v + (pad if is_gain else -pad), i, txt, color=color, va='center',
                    ha='left' if is_gain else 'right', fontsize=10.5, weight='bold',
                    family='monospace')
        ax.invert_yaxis()
        if is_gain:
            ax.set_xlim(0, peak * 1.30 if peak else 1)
        else:
            ax.set_xlim(peak * 1.30 if peak else -1, 0)
        ax.axvline(0, color='#888', linewidth=0.8, alpha=0.5)
        ax.set_title('TOP GAINERS' if is_gain else 'TOP LOSERS', color=color,
                     fontsize=13, weight='bold', pad=12)
        _style_axis(ax)
        ax.tick_params(axis='x', colors='#aaa', labelsize=8.5)
        ax.spines['left'].set_visible(False)

    _panel(ax1, gainers, BULL, True)
    _panel(ax2, losers, BEAR, False)
    fig.suptitle(title, color=WHITE, fontsize=15, weight='bold', y=0.975)
    fig.text(0.5, 0.02, 'Top 8 by 24H change  ·  Blacktide Signals',
             color='#667', fontsize=8.5, ha='center')
    plt.subplots_adjust(left=0.07, right=0.97, top=0.87, bottom=0.09, wspace=0.32)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=BG, pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_momentum_chart(opportunities, title="MOMENTUM SCAN"):
    """v35 動能圖（每根條都有數字標籤）"""
    if not opportunities:
        return _make_empty_chart("MOMENTUM SCAN", "No momentum signals")

    fig, ax = plt.subplots(figsize=(13, 6.5), facecolor=BG)

    n = min(len(opportunities), 8)
    labels = [o["symbol"].replace("/USDT", "") for o in opportunities[:n]]
    chg_5m = [o["chg_5m"] for o in opportunities[:n]]
    chg_15m = [o["chg_15m"] for o in opportunities[:n]]
    chg_30m = [o["chg_30m"] for o in opportunities[:n]]

    x = list(range(n))
    width = 0.27

    for i, (cs, cm, cl) in enumerate(zip(chg_5m, chg_15m, chg_30m)):
        c5 = BULL if cs >= 0 else BEAR
        c15 = BULL if cm >= 0 else BEAR
        c30 = BULL if cl >= 0 else BEAR
        ax.bar(i - width, cs, width, color=c5, alpha=1.0, edgecolor='white', linewidth=0.6)
        ax.bar(i,         cm, width, color=c15, alpha=0.8, edgecolor='white', linewidth=0.4)
        ax.bar(i + width, cl, width, color=c30, alpha=0.6, edgecolor='white', linewidth=0.4)

        # 數字標籤
        max_abs = max(abs(cs), abs(cm), abs(cl)) if max(abs(cs), abs(cm), abs(cl)) > 0 else 1
        offset = max_abs * 0.05
        for j, (val, xp) in enumerate([(cs, i-width), (cm, i), (cl, i+width)]):
            ya = val + offset if val >= 0 else val - offset
            va = 'bottom' if val >= 0 else 'top'
            ax.text(xp, ya, f'{val:+.1f}',
                    color='white', fontsize=7.5, ha='center', va=va,
                    weight='bold', alpha=0.85)

    # 圖例（自己畫）
    legend_elements = [
        Patch(facecolor='#888', alpha=1.0, label='5m'),
        Patch(facecolor='#888', alpha=0.8, label='15m'),
        Patch(facecolor='#888', alpha=0.6, label='30m'),
    ]
    ax.legend(handles=legend_elements, loc='upper right',
              framealpha=0.6, fontsize=9.5, facecolor='#1a2230',
              labelcolor='white', edgecolor='#444', borderpad=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color='white', fontsize=11, weight='bold')
    ax.axhline(y=0, color='white', linewidth=0.9, alpha=0.6)
    _style_axis(ax, '% Change')
    ax.tick_params(axis='y', colors='#aaa', labelsize=9)

    ax.set_title(title, color='white', fontsize=14, weight='bold', pad=15)

    plt.subplots_adjust(left=0.06, right=0.98, top=0.92, bottom=0.08)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG, pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_trend_distribution(strong_bull_count, bull_count, ranging_count,
                              bear_count, strong_bear_count):
    """v35 趨勢分布（修正百分比 + 視覺優化）"""
    total = strong_bull_count + bull_count + ranging_count + bear_count + strong_bear_count
    if total == 0:
        return _make_empty_chart("MARKET TREND", "No trend data")

    fig, ax = plt.subplots(figsize=(12, 6.5), facecolor=BG)

    categories = ['Strong\nBull', 'Bull', 'Ranging', 'Bear', 'Strong\nBear']
    counts = [strong_bull_count, bull_count, ranging_count,
              bear_count, strong_bear_count]
    colors = ['#00c853', BULL, '#9e9e9e', BEAR, '#d32f2f']

    bars = ax.bar(categories, counts, color=colors, alpha=0.92,
                  edgecolor='white', linewidth=1.2)

    max_c = max(counts) if counts else 1

    # 每條柱頂顯示數量 + 百分比
    for bar, count in zip(bars, counts):
        if count > 0:
            pct = count / total * 100
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max_c * 0.04,
                    f'{count}',
                    ha='center', color='white',
                    fontsize=16, weight='bold')
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max_c * 0.16,
                    f'({pct:.0f}%)',
                    ha='center', color='#aaa', fontsize=10)

    # 修正百分比計算（強多 + 多 = 多頭陣營）
    bull_total = strong_bull_count + bull_count
    bear_total = strong_bear_count + bear_count
    bull_pct = bull_total / total * 100
    bear_pct = bear_total / total * 100
    range_pct = ranging_count / total * 100

    # 多頭/空頭主導視覺判斷
    if bull_pct > bear_pct + 10:
        dom = ('BULL DOMINATING', BULL)
    elif bear_pct > bull_pct + 10:
        dom = ('BEAR DOMINATING', BEAR)
    else:
        dom = ('MIXED MARKET', '#aaa')

    ax.set_ylim(0, max_c * 1.35)
    ax.set_ylabel('Number of Coins', color='#aaa', fontsize=11)
    _style_axis(ax)
    ax.tick_params(axis='x', colors='white', labelsize=11)
    ax.tick_params(axis='y', colors='#aaa', labelsize=9)

    # 標題（含主導趨勢）
    title_main = f'MARKET TREND  —  Bull {bull_pct:.0f}%   Range {range_pct:.0f}%   Bear {bear_pct:.0f}%'
    ax.set_title(title_main, color='white', fontsize=13.5, weight='bold', pad=20)

    # 主導徽章放右上角（圖內）
    ax.text(0.98, 0.96, dom[0], transform=ax.transAxes,
            ha='right', va='top', color=dom[1],
            fontsize=11, weight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a2230',
                       edgecolor=dom[1], linewidth=1.2, alpha=0.95))

    plt.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.10)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG, pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_dual_chart(df_btc, df_eth):
    """v35 BTC + ETH 雙圖（正確漲跌率 + 容錯）"""
    # 防呆
    if (df_btc is None or len(df_btc) < 2) and (df_eth is None or len(df_eth) < 2):
        return _make_empty_chart("MARKET PULSE", "BTC/ETH data unavailable")

    fig = plt.figure(figsize=(14, 7.5), facecolor=BG)
    gs = fig.add_gridspec(2, 2, height_ratios=[4, 1], hspace=0.05, wspace=0.12)
    ax_btc = fig.add_subplot(gs[0, 0])
    ax_eth = fig.add_subplot(gs[0, 1])
    ax_btc_v = fig.add_subplot(gs[1, 0], sharex=ax_btc)
    ax_eth_v = fig.add_subplot(gs[1, 1], sharex=ax_eth)

    for df, ax_main, ax_vol, name in [
        (df_btc, ax_btc, ax_btc_v, 'BTC/USDT'),
        (df_eth, ax_eth, ax_eth_v, 'ETH/USDT'),
    ]:
        if df is None or len(df) < 2:
            ax_main.text(0.5, 0.5, f'{name}\nData unavailable',
                         transform=ax_main.transAxes, ha='center', va='center',
                         color='#666', fontsize=14)
            ax_main.set_facecolor(BG)
            ax_main.axis('off')
            ax_vol.set_facecolor(BG)
            ax_vol.axis('off')
            continue

        df = df.tail(60).reset_index(drop=True)
        n = len(df)

        for i in range(n):
            row = df.iloc[i]
            o, c, h, l = float(row['open']), float(row['close']), float(row['high']), float(row['low'])
            color = BULL if c >= o else BEAR
            ax_main.plot([i, i], [l, h], color=color, linewidth=1.4)
            body_h = abs(c - o) or c * 0.0001
            ax_main.add_patch(Rectangle(
                (i - 0.4, min(o, c)), 0.8, body_h,
                facecolor=color, edgecolor=color, linewidth=0.5, alpha=0.95
            ))

        if n >= 20:
            ema20 = df['close'].ewm(span=20).mean()
            ax_main.plot(range(n), ema20, color=GOLD, linewidth=1.5, alpha=0.9, label='EMA20')
        if n >= 50:
            ema50 = df['close'].ewm(span=50).mean()
            ax_main.plot(range(n), ema50, color=PURPLE, linewidth=1.5, alpha=0.9, label='EMA50')

        current = float(df['close'].iloc[-1])
        first_close = float(df['open'].iloc[0])
        chg_pct = (current - first_close) / first_close * 100
        chg_color = BULL if chg_pct >= 0 else BEAR
        chg_sign = "+" if chg_pct >= 0 else ""

        # 現價點
        ax_main.scatter([n - 1], [current], s=110, color=YELLOW,
                        zorder=9, edgecolor=BG, linewidth=2)

        # 標題
        def fmt(p):
            if p >= 1000: return f'{p:,.0f}'
            elif p >= 1: return f'{p:.2f}'
            else: return f'{p:.4f}'
        title_text = f'{name}   {fmt(current)}   ({chg_sign}{chg_pct:.2f}%)'
        ax_main.set_title(title_text, color=chg_color, fontsize=13, weight='bold', pad=12)

        # Y 軸格式
        if current >= 1000:
            ax_main.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
        elif current >= 1:
            ax_main.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.2f}'))
        else:
            ax_main.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.4f}'))

        _style_axis(ax_main)
        if n >= 20:
            ax_main.legend(loc='upper left', framealpha=0.5, fontsize=8.5,
                           facecolor='#1a2230', labelcolor='white',
                           edgecolor='#444', borderpad=0.3)

        # 成交量
        colors_vol = [BULL if df['close'].iloc[i] >= df['open'].iloc[i] else BEAR for i in range(n)]
        ax_vol.bar(range(n), df['volume'], color=colors_vol, alpha=0.8, width=0.8)
        if n >= 20:
            vol_ma = df['volume'].rolling(20).mean()
            ax_vol.plot(range(n), vol_ma, color=GOLD, linewidth=1.2, alpha=0.8)
        _style_axis(ax_vol)
        ax_vol.tick_params(axis='y', colors='#aaa', labelsize=8)
        plt.setp(ax_main.get_xticklabels(), visible=False)

    fig.suptitle('MARKET PULSE  |  BTC vs ETH (60 bars)',
                 color='white', fontsize=14, weight='bold', y=0.97)
    plt.subplots_adjust(left=0.05, right=0.98, top=0.90, bottom=0.06)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG, pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    return buf



# ===== 分析引擎 =====
class CryptoAnalyzer:
    """⭐ v38：加入 funding/LSR 快取，避免 1 分鐘掃描被 API 限流"""

    def __init__(self):
        # ⭐ v38 智能快取：funding 和 long_short_ratio 每 5 分鐘更新一次
        self._funding_cache = {}  # {symbol: (value, timestamp)}
        self._lsr_cache = {}  # {symbol: (value, timestamp)}
        self._cache_ttl_sec = 300  # 5 分鐘
        self._oi_cache = {}      # v63：OI 變化率快取 {symbol: (change_pct, timestamp)}
        self._external_results = []  # v53：真實勝率校準用的歷史，由 bot.py 注入
        self._last_plans = {}  # v54：結構化 plan，golden_hunter 每輪填充
        self._last_plans_ready = False  # v54：本輪掛載是否正常完成
        self._news_sentiment = None  # v55：新聞情緒，每輪掃描開始時更新
        self._gate_blocked = []  # v57：entry_context_gate 擋下的信號記錄（記憶體，重啟清空）

    async def fetch_funding_cached(self, session, symbol):
        """v38 帶快取的 funding rate 取得"""
        now_ts = datetime.now(timezone.utc).timestamp()
        cached = self._funding_cache.get(symbol)
        if cached and (now_ts - cached[1]) < self._cache_ttl_sec:
            return cached[0]
        try:
            val = await self.fetch_funding_rate(session, symbol)
            if val is not None and not isinstance(val, Exception):
                self._funding_cache[symbol] = (val, now_ts)
            return val
        except Exception:
            return None

    async def fetch_lsr_cached(self, session, symbol):
        """v38 帶快取的 long-short ratio 取得"""
        now_ts = datetime.now(timezone.utc).timestamp()
        cached = self._lsr_cache.get(symbol)
        if cached and (now_ts - cached[1]) < self._cache_ttl_sec:
            return cached[0]
        try:
            val = await self.fetch_long_short_ratio(session, symbol)
            if val is not None and not isinstance(val, Exception):
                self._lsr_cache[symbol] = (val, now_ts)
            return val
        except Exception:
            return None

    async def fetch_open_interest(self, session, symbol):
        """取 Bybit V5 OI 近兩筆（5min interval），回傳 % 變化率"""
        try:
            bsym = symbol.replace("/", "")
            url = ("https://api.bybit.com/v5/market/open-interest"
                   "?category=linear&symbol=" + bsym + "&intervalTime=5min&limit=3")
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
            lst = data.get("result", {}).get("list", [])
            if len(lst) < 2:
                return None
            oi_now = float(lst[0]["openInterest"])
            oi_prev = float(lst[1]["openInterest"])
            if oi_prev == 0:
                return None
            return round((oi_now - oi_prev) / oi_prev * 100, 4)
        except Exception:
            return None

    async def fetch_oi_cached(self, session, symbol):
        """v63 帶快取的 OI 變化率取得（5 分鐘 TTL）"""
        now_ts = datetime.now(timezone.utc).timestamp()
        cached = self._oi_cache.get(symbol)
        if cached and (now_ts - cached[1]) < self._cache_ttl_sec:
            return cached[0]
        try:
            val = await self.fetch_open_interest(session, symbol)
            if val is not None and not isinstance(val, Exception):
                self._oi_cache[symbol] = (val, now_ts)
            return val
        except Exception:
            return None

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
    def entry_timing_legacy(self, price, direction, sw_res, sw_sup, rsi, vol_ratio, e20):
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
            grade, pos_mult, desc = "S", 1.0, "💎 極佳進場時機"  # v45 職業：S 級不過度加倉
        elif grade_score >= 60:
            grade, pos_mult, desc = "A", 0.8, "🟢 完美進場時機"
        elif grade_score >= 40:
            grade, pos_mult, desc = "B", 0.5, "🟡 良好進場時機"
        elif grade_score >= 20:
            grade, pos_mult, desc = "C", 0.3, "🟠 可進場但風險較高（試水）"
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
        # ⭐ v53 波動自適應止損：高波動放寬、低波動收緊（避免被正常波動掃出場）
        try:
            atr_pct = atr_v / entry * 100
            if atr_pct > 4:        # 高波動幣（如 NEAR/FET 暴動時）
                atr_mult = 2.2
            elif atr_pct > 2.5:
                atr_mult = 1.8
            elif atr_pct < 1.0:    # 低波動幣
                atr_mult = 1.2
        except Exception:
            pass
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
        return self.px_round(sl), chosen_label

    # ⭐ v57 下單價格精度（低價幣避免被 round(x,4) 砍成 0）
    def px_round(self, value):
        try:
            v = float(value)
            if v <= 0:
                return v
            if v >= 100:
                return round(v, 2)
            if v >= 1:
                return round(v, 4)
            if v >= 0.01:
                return round(v, 6)
            return float(("%.8f") % v)
        except Exception:
            return value

    # ⭐ v57 情境閘門
    def entry_context_gate(self, direction, sig1h, sig4h, df1h, df4h,
                           sw_res, sw_sup, current_price):
        """v57 情境閘門：高位不追多/低位不追空、4H強反不逆勢、盤整只做邊緣反轉。
        回傳 (allow, reason, info)；info 含 range_pos 與 tags。閘門自身出錯時放行。"""
        info = {"range_pos": None, "tags": []}
        try:
            p = float(current_price)
            look = df1h.tail(120)
            lo = float(look["low"].min()); hi = float(look["high"].max())
            rng = hi - lo
            range_pos = (p - lo) / rng if rng > 0 else 0.5
            range_pos = max(0.0, min(1.0, range_pos))
            info["range_pos"] = round(range_pos, 3)

            bos4, _ = self.detect_bos(df4h)
            cont_ok, _ = self.strong_continuation(df1h, direction)
            has_div = bool(sig1h.get("div"))
            r4 = sig4h.get("regime", "") if isinstance(sig4h, dict) else ""
            adx = sig1h.get("adx", 0); rsi = sig1h.get("rsi", 50)

            # 1) 區間位階：高位追多/低位追空，除非 4H BOS 同向或強勢續航
            if direction == "LONG" and range_pos > 0.90 and bos4 != "BULL_BOS" and not cont_ok:
                return False, "高位追多 pos=%.2f 無4H突破/續航" % range_pos, info
            if direction == "SHORT" and range_pos < 0.10 and bos4 != "BEAR_BOS" and not cont_ok:
                return False, "低位追空 pos=%.2f 無4H跌破/續航" % range_pos, info

            # 2) 4H 強烈反向且 1H 無背離 → 硬擋
            if direction == "LONG" and r4 == "STRONG_BEAR" and not has_div:
                return False, "4H強空逆勢做多(無背離)", info
            if direction == "SHORT" and r4 == "STRONG_BULL" and not has_div:
                return False, "4H強多逆勢做空(無背離)", info

            # 3) 盤整（ADX<20 且 squeeze）：只允許支撐/阻力邊緣的反轉型進場
            if adx < 20 and sig1h.get("squeeze_on", False):
                sweep, _ = self.liquidity_sweep(df1h)
                if direction == "LONG":
                    near_sup = bool(sw_sup) and 0 <= (p - sw_sup[0]) / p < 0.02
                    if not (near_sup and (rsi < 40 or sweep == "BULL_SWEEP" or has_div)):
                        return False, "盤整中段追多", info
                else:
                    near_res = bool(sw_res) and 0 <= (sw_res[0] - p) / p < 0.02
                    if not (near_res and (rsi > 60 or sweep == "BEAR_SWEEP" or has_div)):
                        return False, "盤整中段追空", info
                info["tags"].append("RANGE_EDGE")
            return True, "", info
        except Exception:
            return True, "", info

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

            # v44 修：假突破必須是「明確失敗」(回穿 0.5% 以上)
            if direction == "LONG":
                # 真假突破：曾觸及阻力上方 + 現價回到阻力下方 1% 以上
                if highest_in_recent > prev_high * 1.005 and last_close < prev_high * 0.99:
                    return True, "近期突破 " + str(round(prev_high, 4)) + " 失敗回落"
            else:
                # 真假突破：曾跌破支撐 + 現價回到支撐上方 1% 以上
                if lowest_in_recent < prev_low * 0.995 and last_close > prev_low * 1.01:
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
                # v61：強 K 警告收緊——需「強陰線(body/range>0.8)」且「收盤跌破 EMA20」兩條件同時成立
                last = last3.iloc[-1]
                body = float(last["close"]) - float(last["open"])
                full_range = float(last["high"]) - float(last["low"]) + 1e-9
                strong_bear = body < 0 and abs(body) / full_range > 0.8
                broke_ema = last_close < ema20_v * 0.997
                if strong_bear and broke_ema:
                    warnings.append("強陰線且跌破 EMA20")
                # 連 3 根陰線（獨立訊號，保留）
                reds = sum(1 for i in range(3) if float(last3.iloc[i]["close"]) < float(last3.iloc[i]["open"]))
                if reds >= 3:
                    warnings.append("連續 3 根陰線")
            else:
                last = last3.iloc[-1]
                body = float(last["close"]) - float(last["open"])
                full_range = float(last["high"]) - float(last["low"]) + 1e-9
                strong_bull = body > 0 and abs(body) / full_range > 0.8
                broke_ema = last_close > ema20_v * 1.003
                if strong_bull and broke_ema:
                    warnings.append("強陽線且突破 EMA20")
                greens = sum(1 for i in range(3) if float(last3.iloc[i]["close"]) > float(last3.iloc[i]["open"]))
                if greens >= 3:
                    warnings.append("連續 3 根陽線")
            return len(warnings) > 0, " + ".join(warnings)
        except Exception:
            return False, ""

    def fast_breakout_check(self, df5m, df15m, lookback=12):
        """v61 P3-2：快速動能突破偵測（輕量）。
        條件：5m 最新收盤放量突破 15m 近期高/低 + 5m 近 3 根連續同向 + 量 > 均量 1.8x。
        回傳 (direction, strength, reason)；無訊號回 (None, 0, "")。"""
        try:
            if df5m is None or df15m is None or len(df5m) < 5 or len(df15m) < lookback + 1:
                return None, 0, ""
            closes5 = df5m["close"].astype(float)
            vols5 = df5m["volume"].astype(float)
            last_close = float(closes5.iloc[-1])
            avg_vol = float(vols5.iloc[-20:].mean()) if len(vols5) >= 20 else float(vols5.mean())
            last_vol = float(vols5.iloc[-1])
            vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0
            # 近期高低（用 15m 排除最後一根，當突破參考）
            recent_high = float(df15m["high"].astype(float).iloc[-(lookback + 1):-1].max())
            recent_low = float(df15m["low"].astype(float).iloc[-(lookback + 1):-1].min())
            # 5m 近 3 根方向
            last3 = df5m.tail(3)
            ups = sum(1 for i in range(len(last3)) if float(last3.iloc[i]["close"]) > float(last3.iloc[i]["open"]))
            downs = len(last3) - ups
            direction = None
            if last_close > recent_high and ups >= 3 and vol_ratio > 1.8:
                direction = "LONG"
                brk = (last_close - recent_high) / recent_high * 100 if recent_high > 0 else 0
            elif last_close < recent_low and downs >= 3 and vol_ratio > 1.8:
                direction = "SHORT"
                brk = (recent_low - last_close) / recent_low * 100 if recent_low > 0 else 0
            if not direction:
                return None, 0, ""
            strength = min(100, int(40 + vol_ratio * 8 + brk * 15))
            reason = "5m 放量突破（量比 " + str(round(vol_ratio, 1)) + "x、突破 " + str(round(brk, 2)) + "%）"
            return direction, strength, reason
        except Exception:
            return None, 0, ""


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
    def extreme_volatility_check(self, df, threshold=12.0):
        """
        v44 大幅放寬：
        - threshold 7→12（單根 12% 才算極端）
        - 不再用「連 3 根同向大漲/跌」（這是最好的趨勢訊號）
        """
        try:
            recent5 = df.tail(5)
            max_change = ((recent5["high"] - recent5["low"]) / recent5["close"]).max() * 100
            if max_change > threshold:
                return True, "最近5根 K 線單根振幅 " + str(round(max_change, 1)) + "% 過大"
            # v44 移除「連 3 根同向」誤判：那是最強的順勢訊號
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

        # v44 進一步放寬：只在極極端值才反指標
        if direction == "LONG":
            if rsi > 92 and regime not in ("STRONG_BULL", "BULL") and adx < 20:
                violations.append("RSI " + str(int(rsi)) + " 極熱且趨勢弱")
        else:
            # SHORT：跌時 RSI 低是正常的，極端才擋
            if rsi < 8 and regime not in ("STRONG_BEAR", "BEAR") and adx < 20:
                violations.append("RSI " + str(int(rsi)) + " 極冷且趨勢弱")
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
                # v44 放寬：14→10, vol 0.7→0.5
                if ups >= 10 and slope > 0.003 and vol_trend > 0.5:
                    return True, "強勢續航中"
                if ups >= 12 and slope > 0.002:
                    return True, "多頭續航"
            else:
                # 空頭同樣放寬
                if downs >= 10 and slope < -0.003 and vol_trend > 0.5:
                    return True, "強勢崩跌續航"
                if downs >= 12 and slope < -0.002:
                    return True, "空頭續航"
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
        """根據實際價格結構動態計算止盈位（保證 TP 嚴格單調）"""
        risk = abs(entry - sl)
        try:
            if direction == "LONG":
                recent_high = float(df.tail(30)["high"].max())
                fib_1618 = entry + risk * 3.5
                fib_2618 = entry + risk * 5.0
                tp1 = self.px_round(entry + risk * 1.5)
                if ref_res and ref_res[0] > entry:
                    tp2_candidates = [ref_res[0], entry + risk * 2.5]
                    valid_tp2 = [t for t in tp2_candidates if t > tp1]
                    tp2 = min(valid_tp2) if valid_tp2 else self.px_round(entry + risk * 2.5)
                else:
                    tp2 = self.px_round(entry + risk * 2.5)
                tp4 = self.px_round(max(fib_2618, recent_high + atr_v))
                tp3 = self.px_round(fib_1618)
                if ref_res and len(ref_res) >= 2 and tp2 < ref_res[1] < tp4:
                    tp3 = self.px_round(ref_res[1])
            else:
                recent_low = float(df.tail(30)["low"].min())
                fib_1618 = entry - risk * 3.5
                fib_2618 = entry - risk * 5.0
                tp1 = self.px_round(entry - risk * 1.5)
                if ref_sup and ref_sup[0] < entry:
                    tp2_candidates = [ref_sup[0], entry - risk * 2.5]
                    valid_tp2 = [t for t in tp2_candidates if t < tp1]
                    tp2 = max(valid_tp2) if valid_tp2 else self.px_round(entry - risk * 2.5)
                else:
                    tp2 = self.px_round(entry - risk * 2.5)
                tp4 = self.px_round(min(fib_2618, recent_low - atr_v))
                tp3 = self.px_round(fib_1618)
                if ref_sup and len(ref_sup) >= 2 and tp4 < ref_sup[1] < tp2:
                    tp3 = self.px_round(ref_sup[1])
            tps = [tp1, tp2, tp3, tp4]
            for i in range(1, 4):
                if direction == "LONG" and tps[i] <= tps[i - 1]:
                    tps[i] = self.px_round(tps[i - 1] + risk * 0.5)
                elif direction != "LONG" and tps[i] >= tps[i - 1]:
                    tps[i] = self.px_round(tps[i - 1] - risk * 0.5)
            tp1, tp2, tp3, tp4 = tps
            return self.px_round(tp1), self.px_round(tp2), self.px_round(tp3), self.px_round(tp4)
        except Exception:
            if direction == "LONG":
                return (self.px_round(entry + risk * 1.5), self.px_round(entry + risk * 2.5),
                        self.px_round(entry + risk * 3.5), self.px_round(entry + risk * 5.0))
            else:
                return (self.px_round(entry - risk * 1.5), self.px_round(entry - risk * 2.5),
                        self.px_round(entry - risk * 3.5), self.px_round(entry - risk * 5.0))



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
            if b <= 0:  # v53 修復：avg_win_pct=0 → b=0 → 下行除零崩潰
                return None
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


    # ⭐ v31 市場結構分析（HH/HL/LH/LL）
    def market_structure(self, df, lookback=20):
        """
        判斷市場結構：上升、下降、震盪、破壞
        Higher High + Higher Low = 上升結構
        Lower High + Lower Low = 下降結構
        混合 = 震盪
        """
        try:
            if len(df) < lookback + 5:
                return "UNKNOWN", "結構不明", 0
            # 找最近的 swing high/low
            highs, lows = [], []
            for i in range(2, len(df) - 2):
                h = float(df["high"].iloc[i])
                l = float(df["low"].iloc[i])
                # swing high: 比左右兩根都高
                if h > float(df["high"].iloc[i-1]) and h > float(df["high"].iloc[i-2]) \
                   and h > float(df["high"].iloc[i+1]) and h > float(df["high"].iloc[i+2]):
                    highs.append((i, h))
                if l < float(df["low"].iloc[i-1]) and l < float(df["low"].iloc[i-2]) \
                   and l < float(df["low"].iloc[i+1]) and l < float(df["low"].iloc[i+2]):
                    lows.append((i, l))
            if len(highs) < 2 or len(lows) < 2:
                return "RANGING", "震盪結構", 0
            recent_highs = highs[-3:]
            recent_lows = lows[-3:]
            # 判斷高點趨勢
            highs_trending_up = all(recent_highs[i][1] > recent_highs[i-1][1] for i in range(1, len(recent_highs)))
            highs_trending_down = all(recent_highs[i][1] < recent_highs[i-1][1] for i in range(1, len(recent_highs)))
            lows_trending_up = all(recent_lows[i][1] > recent_lows[i-1][1] for i in range(1, len(recent_lows)))
            lows_trending_down = all(recent_lows[i][1] < recent_lows[i-1][1] for i in range(1, len(recent_lows)))
            if highs_trending_up and lows_trending_up:
                return "STRONG_UPTREND", "強上升結構 (HH+HL)", 30
            elif highs_trending_down and lows_trending_down:
                return "STRONG_DOWNTREND", "強下降結構 (LH+LL)", -30
            elif lows_trending_up and not highs_trending_down:
                return "UPTREND", "上升結構 (HL)", 15
            elif highs_trending_down and not lows_trending_up:
                return "DOWNTREND", "下降結構 (LH)", -15
            else:
                return "RANGING", "震盪結構", 0
        except Exception:
            return "UNKNOWN", "結構不明", 0

    # ⭐ v31 多週期共振分級（7 種狀態）
    def mtf_resonance_grade(self, sig15m, sig1h, sig4h):
        """
        多週期共振分級：
        TRIPLE_BULL: 三週期皆多
        DOUBLE_BULL_LONG: 1h+4h 多（最強短線）
        DOUBLE_BULL_SHORT: 15m+1h 多
        SINGLE_BULL: 只有一個多
        DIVERGENT: 分歧（高風險）
        SINGLE_BEAR / DOUBLE_BEAR / TRIPLE_BEAR: 同理
        """
        def get_dir(sig):
            if sig.get("regime", "") in ("STRONG_BULL", "BULL"):
                return "BULL"
            elif sig.get("regime", "") in ("STRONG_BEAR", "BEAR"):
                return "BEAR"
            return "NEUTRAL"
        d15 = get_dir(sig15m)
        d1h = get_dir(sig1h)
        d4h = get_dir(sig4h)
        # 計算共振分數
        bulls = sum(1 for d in [d15, d1h, d4h] if d == "BULL")
        bears = sum(1 for d in [d15, d1h, d4h] if d == "BEAR")
        if bulls == 3:
            return "TRIPLE_BULL", "🔥 三週期共振多頭", 25
        elif bears == 3:
            return "TRIPLE_BEAR", "🔥 三週期共振空頭", -25
        elif d1h == "BULL" and d4h == "BULL":
            return "STRONG_BULL", "💪 1H+4H 強多", 18
        elif d1h == "BEAR" and d4h == "BEAR":
            return "STRONG_BEAR", "💪 1H+4H 強空", -18
        elif d15 == "BULL" and d1h == "BULL":
            return "MOMENTUM_BULL", "⚡ 15m+1H 短線多", 10
        elif d15 == "BEAR" and d1h == "BEAR":
            return "MOMENTUM_BEAR", "⚡ 15m+1H 短線空", -10
        elif bulls > bears:
            return "WEAK_BULL", "📈 弱多頭", 5
        elif bears > bulls:
            return "WEAK_BEAR", "📉 弱空頭", -5
        else:
            return "DIVERGENT", "⚠️ 週期分歧", 0

    # ⭐ v31 BTC 相關性檢查
    def btc_correlation(self, df_alt, df_btc, period=30):
        """
        計算 alt 跟 BTC 最近的相關性
        高相關（>0.7）→ 跟 BTC 走，需 BTC 健康才能做
        低相關（<0.3）→ 獨立行情，可靠性高
        負相關（<-0.3）→ 反向，反彈空間
        """
        try:
            if df_alt is None or df_btc is None or len(df_alt) < period or len(df_btc) < period:
                return 0, "UNKNOWN", 0
            # 計算對齊的收益率
            alt_returns = df_alt["close"].pct_change().tail(period).values
            btc_returns = df_btc["close"].pct_change().tail(period).values
                # 簡單相關係數
            mean_a = np.nanmean(alt_returns)
            mean_b = np.nanmean(btc_returns)
            cov = np.nansum((alt_returns - mean_a) * (btc_returns - mean_b))
            std_a = np.sqrt(np.nansum((alt_returns - mean_a) ** 2))
            std_b = np.sqrt(np.nansum((btc_returns - mean_b) ** 2))
            if std_a == 0 or std_b == 0:
                return 0, "UNKNOWN", 0
            corr = cov / (std_a * std_b)
            corr = max(-1, min(1, corr))
            if corr > 0.7:
                return corr, "HIGH_SYNC", 0  # 跟 BTC 同步，無加減分
            elif corr > 0.3:
                return corr, "MODERATE", 5
            elif corr > -0.3:
                return corr, "INDEPENDENT", 12  # 獨立行情，加分
            elif corr > -0.7:
                return corr, "INVERSE", 8
            else:
                return corr, "STRONG_INVERSE", 15
        except Exception:
            return 0, "UNKNOWN", 0

    # ⭐ v31 波動率分位數（vs 歷史）
    def volatility_percentile(self, df, lookback=100):
        """
        當前 ATR 在過去 N 根的分位數
        高分位（>80）→ 過度波動，注意反轉
        低分位（<20）→ 即將爆發
        """
        try:
            if len(df) < lookback:
                return 50, "NORMAL"
            atrs = []
            for i in range(14, len(df)):
                hi = df["high"].iloc[i-14:i].max()
                lo = df["low"].iloc[i-14:i].min()
                atrs.append(hi - lo)
            current_atr = atrs[-1] if atrs else 0
            sorted_atrs = sorted(atrs)
            rank = sum(1 for a in sorted_atrs if a <= current_atr)
            percentile = rank / len(sorted_atrs) * 100
            if percentile >= 85:
                return percentile, "EXTREME_HIGH"  # 極端高
            elif percentile >= 70:
                return percentile, "HIGH"
            elif percentile <= 15:
                return percentile, "EXTREME_LOW"  # 即將爆發
            elif percentile <= 30:
                return percentile, "LOW"
            else:
                return percentile, "NORMAL"
        except Exception:
            return 50, "NORMAL"

    # ⭐ v31 主動退出檢查（結構破壞）
    def early_exit_signal(self, df, direction, entry_price, sl_price):
        """
        檢查是否該主動退場（不等止損）
        破壞訊號：跌破關鍵支撐/突破關鍵阻力 + 量增
        """
        try:
            if len(df) < 30:
                return False, ""
            current = float(df["close"].iloc[-1])
            recent = df.tail(10)
            recent_vol = float(recent["volume"].iloc[-1])
            avg_vol = float(df.tail(30)["volume"].mean())
            vol_spike = recent_vol > avg_vol * 1.5

            ema20_v = self.safe_val(self.ema(df, 20), current)

            if direction == "LONG":
                # 1. 跌破 EMA20 + 量增
                if current < ema20_v * 0.99 and vol_spike:
                    return True, "跌破 EMA20 + 量增"
                # 2. 接近止損 50%（提前警告）
                halfway_sl = entry_price - (entry_price - sl_price) * 0.5
                if current < halfway_sl and vol_spike:
                    return True, "接近止損半距 + 量增"
                # 3. 連續 3 根強陰線
                last3 = df.tail(3)
                strong_bears = sum(
                    1 for i in range(3)
                    if float(last3["close"].iloc[i]) < float(last3["open"].iloc[i])
                    and (float(last3["open"].iloc[i]) - float(last3["close"].iloc[i])) / float(last3["open"].iloc[i]) > 0.005
                )
                if strong_bears >= 3:
                    return True, "連續 3 根強陰線"
            else:
                # SHORT 反向
                if current > ema20_v * 1.01 and vol_spike:
                    return True, "突破 EMA20 + 量增"
                halfway_sl = entry_price + (sl_price - entry_price) * 0.5
                if current > halfway_sl and vol_spike:
                    return True, "接近止損半距 + 量增"
                last3 = df.tail(3)
                strong_bulls = sum(
                    1 for i in range(3)
                    if float(last3["close"].iloc[i]) > float(last3["open"].iloc[i])
                    and (float(last3["close"].iloc[i]) - float(last3["open"].iloc[i])) / float(last3["open"].iloc[i]) > 0.005
                )
                if strong_bulls >= 3:
                    return True, "連續 3 根強陽線"
            return False, ""
        except Exception:
            return False, ""

    # ⭐ v31 分批進場建議
    def scale_in_plan(self, direction, entry, sl, current_price, grade):
        """
        高品質信號可以分批進場降低風險
        S/A 級 → 分 3 批
        B 級 → 分 2 批
        C 級 → 一次進場
        """
        risk = abs(entry - sl)
        if grade in ("S", "A"):
            # 3 批：50% / 30% / 20%
            if direction == "LONG":
                p1 = round(entry, 6)
                p2 = round(entry - risk * 0.25, 6)
                p3 = round(entry - risk * 0.5, 6)
            else:
                p1 = round(entry, 6)
                p2 = round(entry + risk * 0.25, 6)
                p3 = round(entry + risk * 0.5, 6)
            return [
                {"price": p1, "size": 50, "note": "市價 50%"},
                {"price": p2, "size": 30, "note": "限價 30%"},
                {"price": p3, "size": 20, "note": "限價 20%"},
            ]
        elif grade == "B":
            if direction == "LONG":
                p1 = round(entry, 6)
                p2 = round(entry - risk * 0.3, 6)
            else:
                p1 = round(entry, 6)
                p2 = round(entry + risk * 0.3, 6)
            return [
                {"price": p1, "size": 60, "note": "市價 60%"},
                {"price": p2, "size": 40, "note": "限價 40%"},
            ]
        else:
            return [{"price": round(entry, 6), "size": 100, "note": "全倉一次進場"}]

    # ⭐ v31 恐懼貪婪變化率
    def fg_momentum(self, current_fg, lookback_fg=None):
        """
        F&G 變化率分析：
        - 上升中（30→70）= 風險偏好升溫，做多有利
        - 下降中（70→30）= 風險規避，做空有利
        - 極值反轉 = 反向訊號
        """
        if lookback_fg is None:
            # 沒有歷史可比，只用絕對值
            if current_fg <= 25:
                return "EXTREME_FEAR", "極度恐懼", 8  # 反向買點
            elif current_fg <= 45:
                return "FEAR", "恐懼", 3
            elif current_fg >= 75:
                return "EXTREME_GREED", "極度貪婪", -8  # 反向賣點
            elif current_fg >= 55:
                return "GREED", "貪婪", -3
            else:
                return "NEUTRAL", "中性", 0
        diff = current_fg - lookback_fg
        if diff > 15:
            return "RISING_FAST", "快速升溫", 5
        elif diff > 5:
            return "RISING", "升溫中", 3
        elif diff < -15:
            return "FALLING_FAST", "快速降溫", -5
        elif diff < -5:
            return "FALLING", "降溫中", -3
        return "STABLE", "穩定", 0

    # ⭐ v31 動態止損移動計算（給機器人自動執行用）
    def calc_trailing_sl(self, direction, entry, tp1, tp2, tp3, current_price, tp_hit):
        """
        根據已達止盈位，自動計算當前應該的止損價
        達 TP1 → SL 移到成本價（保本）
        達 TP2 → SL 移到 TP1
        達 TP3 → SL 移到 TP2
        """
        if not tp_hit:
            return None
        max_tp = max(tp_hit) if tp_hit else 0
        if max_tp >= 3:
            return tp2
        elif max_tp >= 2:
            return tp1
        elif max_tp >= 1:
            return entry
        return None



    # ============================================================
    # ⭐⭐⭐ v32 頂尖量化分析（接近 Renaissance / Two Sigma 水準）
    # ============================================================

    # ⭐ 訂單流不平衡（Order Flow Imbalance）
    def order_flow_imbalance(self, df, period=20):
        """
        計算主動買賣不平衡度
        Delta = (close - low) - (high - close)  → 簡化版主動方向
        正 delta 強勢 = 主動買盤強
        負 delta 強勢 = 主動賣盤強
        """
        try:
            if len(df) < period + 5:
                return 0, "UNKNOWN", 0
            recent = df.tail(period).copy()
            # 估算每根 K 的主動方向（簡化版）
            # 收盤接近高點 = 主動買盤；接近低點 = 主動賣盤
            deltas = []
            for i in range(len(recent)):
                row = recent.iloc[i]
                h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
                if h == l:
                    deltas.append(0)
                    continue
                # close 位置：1=最高, 0=最低
                pos = (c - l) / (h - l)
                # 加權成交量
                vol = float(row["volume"])
                delta = vol * (2 * pos - 1)  # -vol ~ +vol
                deltas.append(delta)
            total_buy = sum(d for d in deltas if d > 0)
            total_sell = abs(sum(d for d in deltas if d < 0))
            total = total_buy + total_sell
            if total == 0:
                return 0, "BALANCED", 0
            imbalance = (total_buy - total_sell) / total  # -1 ~ +1
            if imbalance > 0.4:
                return imbalance, "STRONG_BUY_FLOW", 15
            elif imbalance > 0.2:
                return imbalance, "BUY_FLOW", 8
            elif imbalance < -0.4:
                return imbalance, "STRONG_SELL_FLOW", -15
            elif imbalance < -0.2:
                return imbalance, "SELL_FLOW", -8
            return imbalance, "BALANCED", 0
        except Exception:
            return 0, "UNKNOWN", 0

    # ⭐ 流動性掃蕩偵測（Liquidity Sweep / Stop Hunt）
    def liquidity_sweep(self, df, lookback=30):
        """
        偵測機構掃蕩止損後反轉的訊號（最高勝率形態之一）
        模式：
        - 跌破前低 → 立刻反彈收回 → 看漲掃蕩
        - 突破前高 → 立刻回落收回 → 看跌掃蕩
        """
        try:
            if len(df) < lookback + 3:
                return None, ""
            # 找最近的 swing high/low
            past = df.iloc[:-3].tail(lookback)
            prev_low = float(past["low"].min())
            prev_high = float(past["high"].max())
            # 看最近 3 根 K 線
            last3 = df.tail(3)
            for i in range(len(last3)):
                bar = last3.iloc[i]
                h, l, c, o = float(bar["high"]), float(bar["low"]), float(bar["close"]), float(bar["open"])
                # 看漲掃蕩：低點刺穿 prev_low 但收盤回到上方
                if l < prev_low and c > prev_low and c > o:
                    return "BULL_SWEEP", "掃蕩低點止損後反彈（看漲）"
                # 看跌掃蕩：高點刺穿 prev_high 但收盤回到下方
                if h > prev_high and c < prev_high and c < o:
                    return "BEAR_SWEEP", "掃蕩高點止損後回落（看跌）"
            return None, ""
        except Exception:
            return None, ""

    # ⭐ 多週期動能背離
    def momentum_divergence(self, df_higher, df_lower):
        """
        高週期創新高但低週期動能未跟上 → 看跌背離
        高週期創新低但低週期動能未跟上 → 看漲背離
        """
        try:
            if df_higher is None or df_lower is None:
                return None, ""
            if len(df_higher) < 30 or len(df_lower) < 50:
                return None, ""
            # 高週期最近 5 根 vs 之前 5 根
            higher_recent = df_higher.tail(5)
            higher_prev = df_higher.iloc[-10:-5]
            recent_high_h = float(higher_recent["high"].max())
            prev_high_h = float(higher_prev["high"].max())
            recent_low_h = float(higher_recent["low"].min())
            prev_low_h = float(higher_prev["low"].min())
            # 低週期動能（用 RSI）
            rsi_low = self.rsi(df_lower).dropna()
            if len(rsi_low) < 30:
                return None, ""
            recent_rsi = rsi_low.tail(20)
            recent_rsi_max = float(recent_rsi.max())
            recent_rsi_min = float(recent_rsi.min())
            prev_rsi = rsi_low.iloc[-40:-20]
            prev_rsi_max = float(prev_rsi.max())
            prev_rsi_min = float(prev_rsi.min())
            # 看跌背離：高週期創新高，低週期 RSI 沒創新高
            if recent_high_h > prev_high_h * 1.005 and recent_rsi_max < prev_rsi_max - 3:
                return "BEAR_DIV", "高週期創新高但低週期動能衰竭"
            # 看漲背離：高週期創新低，低週期 RSI 沒創新低
            if recent_low_h < prev_low_h * 0.995 and recent_rsi_min > prev_rsi_min + 3:
                return "BULL_DIV", "高週期創新低但低週期動能轉強"
            return None, ""
        except Exception:
            return None, ""

    # ⭐ Wyckoff Spring / Upthrust 偵測
    def wyckoff_pattern(self, df, lookback=40):
        """
        偵測 Wyckoff 經典形態
        Spring: 區間下限假突破後快速回升（吸籌完成）
        Upthrust: 區間上限假突破後快速回落（派發完成）
        """
        try:
            if len(df) < lookback + 5:
                return None, ""
            consolidation = df.iloc[:-5].tail(lookback)
            range_high = float(consolidation["high"].quantile(0.9))
            range_low = float(consolidation["low"].quantile(0.1))
            # 確保是真的盤整（高低點差距 < 8%）
            if (range_high - range_low) / range_low > 0.08:
                return None, ""
            recent5 = df.tail(5)
            for i in range(len(recent5)):
                bar = recent5.iloc[i]
                h, l, c = float(bar["high"]), float(bar["low"]), float(bar["close"])
                vol = float(bar["volume"])
                avg_vol = float(consolidation["volume"].mean())
                # Spring：跌破支撐後快速收回 + 量爆
                if l < range_low * 0.995 and c > range_low and vol > avg_vol * 1.3:
                    return "SPRING", "Wyckoff Spring (吸籌完成，看漲)"
                # Upthrust：突破壓力後回落 + 量爆
                if h > range_high * 1.005 and c < range_high and vol > avg_vol * 1.3:
                    return "UPTHRUST", "Wyckoff Upthrust (派發完成，看跌)"
            return None, ""
        except Exception:
            return None, ""

    # ⭐ 高勝率 K 線形態組合（多重確認）
    def candle_combo(self, df, direction):
        """
        偵測強勢 K 線組合（不單看一根）
        看漲：三兵、晨星、錘子+確認、吞噬+量爆
        看跌：三鴉、暮星、流星+確認、吞噬+量爆
        """
        try:
            if len(df) < 5:
                return [], 0
            recent = df.tail(5)
            patterns = []
            bonus = 0
            o = [float(recent["open"].iloc[i]) for i in range(5)]
            c = [float(recent["close"].iloc[i]) for i in range(5)]
            h = [float(recent["high"].iloc[i]) for i in range(5)]
            l = [float(recent["low"].iloc[i]) for i in range(5)]
            v = [float(recent["volume"].iloc[i]) for i in range(5)]
            avg_v = sum(v[:4]) / 4

            if direction == "LONG":
                # 三白兵：連 3 根陽 + 逐步上升
                if c[-1] > o[-1] and c[-2] > o[-2] and c[-3] > o[-3]:
                    if c[-1] > c[-2] > c[-3] and o[-1] > o[-2] and o[-2] > o[-3] * 0.998:
                        patterns.append("三白兵")
                        bonus += 8
                # 看漲吞噬 + 量爆
                if c[-1] > o[-1] and c[-2] < o[-2]:
                    body_curr = c[-1] - o[-1]
                    body_prev = o[-2] - c[-2]
                    if body_curr > body_prev * 1.2 and v[-1] > avg_v * 1.3:
                        patterns.append("看漲吞噬+量爆")
                        bonus += 10
                # 錘子線 + 後續確認
                body = abs(c[-2] - o[-2])
                lower = min(c[-2], o[-2]) - l[-2]
                if body > 0 and lower > body * 2 and c[-1] > c[-2]:
                    patterns.append("錘子+確認")
                    bonus += 7
                # 晨星：陰、十字、陽 三根組合
                if c[-3] < o[-3] and abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3 and c[-1] > o[-1]:
                    if c[-1] > (o[-3] + c[-3]) / 2:
                        patterns.append("晨星反轉")
                        bonus += 9
            else:
                # 三烏鴉
                if c[-1] < o[-1] and c[-2] < o[-2] and c[-3] < o[-3]:
                    if c[-1] < c[-2] < c[-3] and o[-1] < o[-2] and o[-2] < o[-3] * 1.002:
                        patterns.append("三烏鴉")
                        bonus += 8
                # 看跌吞噬 + 量爆
                if c[-1] < o[-1] and c[-2] > o[-2]:
                    body_curr = o[-1] - c[-1]
                    body_prev = c[-2] - o[-2]
                    if body_curr > body_prev * 1.2 and v[-1] > avg_v * 1.3:
                        patterns.append("看跌吞噬+量爆")
                        bonus += 10
                # 流星 + 確認
                body = abs(c[-2] - o[-2])
                upper = h[-2] - max(c[-2], o[-2])
                if body > 0 and upper > body * 2 and c[-1] < c[-2]:
                    patterns.append("流星+確認")
                    bonus += 7
                # 暮星
                if c[-3] > o[-3] and abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3 and c[-1] < o[-1]:
                    if c[-1] < (o[-3] + c[-3]) / 2:
                        patterns.append("暮星反轉")
                        bonus += 9
            return patterns, bonus
        except Exception:
            return [], 0

    # ⭐ 期望值計算（EV = 勝率×平均盈 - 敗率×平均損）
    def expected_value(self, win_rate, avg_win_pct, avg_loss_pct):
        """
        計算每筆交易的期望值
        win_rate: 勝率百分比 (0-100)
        avg_win_pct: 平均盈利百分比
        avg_loss_pct: 平均虧損百分比（正值）
        """
        try:
            p = win_rate / 100
            ev = p * avg_win_pct - (1 - p) * avg_loss_pct
            return round(ev, 3)
        except Exception:
            return 0

    # ⭐ 多策略共識制（Ensemble）
    def strategy_consensus(self, direction, sig1h, df1h, df4h, df15m,
                           vol_ratio, sw_res, sw_sup, current_price):
        """
        要 7 種策略中至少 2 種同意（v51）
        回傳：(consensus_count, total, voting_strategies)
        """
        votes = []
        regime = sig1h.get("regime", "")
        rsi = sig1h.get("rsi", 50)
        adx = sig1h.get("adx", 20)
        macd_hist = sig1h.get("macd_hist", 0)

        e20 = sig1h.get("e20", 0)
        e50 = sig1h.get("e50", 0)
        # v57：量價票方向化 — 量增需搭配近 3 根淨變動同向，避免「量增但價格反向」也算共識
        try:
            _c3 = float(df1h["close"].iloc[-1]) - float(df1h["close"].iloc[-4])
        except Exception:
            _c3 = 0
        if direction == "LONG":
            # 1. 趨勢追隨（v51：ADX 門檻 22→18，與 setup 一致）
            if regime in ("STRONG_BULL", "BULL") and adx > 18:
                votes.append("趨勢追隨")
            # 2. 動量
            if macd_hist > 0 and 45 < rsi < 70:
                votes.append("動量配合")
            # 3. 量價
            if vol_ratio > 1.2 and _c3 > 0:  # v51: 1.3→1.2；v57：須同向
                votes.append("量價齊升")
            # 7. v51 新增：EMA 多頭排列（短均上穿長均，常見且有效）
            if e20 > 0 and e50 > 0 and e20 > e50:
                votes.append("均線多頭")
            # 4. 支撐反彈
            if sw_sup:
                dist = (current_price - sw_sup[0]) / current_price * 100
                if 0 < dist < 2:
                    votes.append("支撐反彈")
            # 5. SMC
            bos, _ = self.detect_bos(df1h)
            if bos == "BULL_BOS":
                votes.append("BOS 突破")
            # 6. 訂單流
            _, ofi_state, _ = self.order_flow_imbalance(df1h)
            if ofi_state in ("STRONG_BUY_FLOW", "BUY_FLOW"):
                votes.append("訂單流偏多")
        else:
            if regime in ("STRONG_BEAR", "BEAR") and adx > 18:  # v51: 22→18
                votes.append("趨勢追隨")
            if macd_hist < 0 and 30 < rsi < 55:
                votes.append("動量配合")
            if vol_ratio > 1.2 and _c3 < 0:  # v51: 1.3→1.2；v57：須同向
                votes.append("量價齊跌")
            # 7. v51 新增：EMA 空頭排列
            if e20 > 0 and e50 > 0 and e20 < e50:
                votes.append("均線空頭")
            if sw_res:
                dist = (sw_res[0] - current_price) / current_price * 100
                if 0 < dist < 2:
                    votes.append("阻力壓制")
            bos, _ = self.detect_bos(df1h)
            if bos == "BEAR_BOS":
                votes.append("BOS 跌破")
            _, ofi_state, _ = self.order_flow_imbalance(df1h)
            if ofi_state in ("STRONG_SELL_FLOW", "SELL_FLOW"):
                votes.append("訂單流偏空")
        return len(votes), 7, votes  # v51: 7 strategies now

    # ⭐ 自適應參數（根據近期勝率調整）
    def adaptive_threshold(self, recent_results):
        """
        根據近 20 筆交易結果調整推播門檻
        連勝 → 放寬 5 分
        連敗 → 收緊 5 分（v61：上調幅度上限 +5，避免近期幾筆虧損就把門檻拉高到一直不推）
        """
        if not recent_results or len(recent_results) < 5:
            return 0  # 中性
        recent = recent_results[-20:]
        wins = sum(1 for r in recent if r.get("final_pct", 0) > 0)
        losses = len(recent) - wins
        win_rate = wins / len(recent)
        # 最近 5 筆
        last5 = recent[-5:]
        last5_wins = sum(1 for r in last5 if r.get("final_pct", 0) > 0)
        # 整體勝率調整
        if win_rate >= 0.7 and last5_wins >= 4:
            return -5  # 表現好 → 放寬門檻（多抓機會）
        elif win_rate <= 0.4 or last5_wins <= 1:
            return 5  # v61：表現差 → 收緊門檻（上限 +5，原 +10 易壓抑到一直不推）
        return 0

    # ⭐ 交易所大額流入流出（簡化版：用成交量異常代替）
    def exchange_flow(self, df, period=30):
        """
        用大成交量 K 線判斷可能的大戶進出
        - 突發大成交量陽線 = 機構買入
        - 突發大成交量陰線 = 機構賣出
        """
        try:
            if len(df) < period:
                return None, ""
            recent = df.tail(10)
            avg_vol = float(df.tail(period).iloc[:-10]["volume"].mean())
            big_bulls = 0
            big_bears = 0
            for i in range(len(recent)):
                bar = recent.iloc[i]
                vol = float(bar["volume"])
                c, o = float(bar["close"]), float(bar["open"])
                if vol > avg_vol * 2:
                    if c > o:
                        big_bulls += 1
                    else:
                        big_bears += 1
            if big_bulls >= 3:
                return "BIG_BUYING", "近期偵測到大資金買入"
            if big_bears >= 3:
                return "BIG_SELLING", "近期偵測到大資金賣出"
            return None, ""
        except Exception:
            return None, ""



    # ============================================================
    # ⭐ v36 進階市場分析（全局視角 + 機構動向）
    # ============================================================

    def market_regime_global(self, df1d, df1h):
        """
        判斷整體市場 regime (v36 升級版)
        - TRENDING_UP: 趨勢上行（順勢做多最佳）
        - TRENDING_DOWN: 趨勢下行
        - RANGING_TIGHT: 窄幅震盪（區間交易）
        - RANGING_WIDE: 寬幅震盪
        - VOLATILE: 高波動（避免新進場）
        - TRANSITIONAL: 轉換期
        """
        try:
            if df1d is None or len(df1d) < 30:
                # 退而求其次用 1h
                df = df1h
            else:
                df = df1d

            if df is None or len(df) < 30:
                return "UNKNOWN", "未知", 0

            # ATR / Price 反映波動
            recent = df.tail(30)
            atr = float(recent["high"].rolling(14).max().iloc[-1] - recent["low"].rolling(14).min().iloc[-1])
            avg_price = float(recent["close"].mean())
            atr_pct = atr / avg_price * 100 if avg_price > 0 else 0

            # 趨勢強度（EMA20 vs EMA50）
            ema20 = recent["close"].ewm(span=20).mean()
            ema50 = recent["close"].ewm(span=50).mean() if len(df) >= 50 else ema20
            slope_20 = (float(ema20.iloc[-1]) - float(ema20.iloc[-5])) / float(ema20.iloc[-5]) * 100
            trend_diff = (float(ema20.iloc[-1]) - float(ema50.iloc[-1])) / float(ema50.iloc[-1]) * 100

            # 高低點距離
            recent_high = float(recent["high"].max())
            recent_low = float(recent["low"].min())
            range_pct = (recent_high - recent_low) / recent_low * 100

            # 判斷
            if atr_pct > 15:
                return "VOLATILE", "高波動期（暫避新單）", -10
            if abs(trend_diff) > 3 and abs(slope_20) > 1.5:
                if trend_diff > 0:
                    return "TRENDING_UP", "牛市趨勢中", 12
                else:
                    return "TRENDING_DOWN", "熊市趨勢中", 12
            if range_pct < 5:
                return "RANGING_TIGHT", "窄幅震盪", 3
            if range_pct < 12:
                return "RANGING_WIDE", "寬幅震盪", 5
            return "TRANSITIONAL", "趨勢轉換期", 0
        except Exception:
            return "UNKNOWN", "未知", 0

    def funding_extreme(self, funding_rate):
        """
        Funding Rate 極端值反向訊號
        輸入單位＝百分比（fetch_funding_rate / fetch_funding_cached 回傳的就是百分比，例 0.01 = 0.01%）
        > 0.08% (8 bps) = 多頭過熱（反轉做空訊號）
        < -0.08% = 空頭過熱（反轉做多訊號）
        """
        try:
            if funding_rate is None:
                return None, "", 0
            fr = float(funding_rate)
            fr_pct = fr  # 輸入已是百分比，不再二次換算
            if fr_pct > 0.08:
                return "EXTREME_LONG_CROWDED", "多單過於擁擠（反向訊號）", 12
            elif fr_pct > 0.04:
                return "LONG_CROWDED", "多單偏擁擠", 5
            elif fr_pct < -0.08:
                return "EXTREME_SHORT_CROWDED", "空單過於擁擠（反向訊號）", 12
            elif fr_pct < -0.04:
                return "SHORT_CROWDED", "空單偏擁擠", 5
            return "BALANCED", "資金費率平衡", 0
        except Exception:
            return None, "", 0

    def ls_ratio_signal(self, ls_ratio):
        """多空比極端值訊號（散戶逆向，鏡像 funding_extreme 邏輯）"""
        try:
            if ls_ratio is None:
                return None, "", 0
            r = float(ls_ratio)
            if r > 2.5:
                return "EXTREME_LONG_CROWDED", "散戶大量看多（反向警示）", 10
            elif r > 1.8:
                return "LONG_CROWDED", "散戶偏多擁擠", 5
            elif r < 0.7:
                return "EXTREME_SHORT_CROWDED", "散戶大量看空（反向訊號）", 10
            elif r < 1.0:
                return "SHORT_CROWDED", "散戶偏空擁擠", 5
            return "BALANCED", "多空比平衡", 0
        except Exception:
            return None, "", 0

    def oi_signal(self, oi_change_pct, direction):
        """OI 變化率 + 價格方向一致性訊號
        OI 上升 + 方向一致 = 真實建倉確認（加分）
        OI 下降 + 方向一致 = 了結/回補（減分）
        """
        try:
            if oi_change_pct is None or direction not in ("LONG", "SHORT"):
                return None, "", 0
            c = float(oi_change_pct)
            if direction == "LONG":
                if c > 3:
                    return "OI_LONG_CONFIRM", "OI 強勁增加（多頭建倉確認）", 12
                elif c > 1:
                    return "OI_LONG_MILD", "OI 溫和增加（多頭入場）", 6
                elif c < -3:
                    return "OI_LONG_WARN", "OI 大幅減少（多頭了結警示）", -8
                elif c < -1:
                    return "OI_LONG_CAUTION", "OI 微幅減少（注意獲利了結）", -3
            else:  # SHORT
                if c > 3:
                    return "OI_SHORT_CONFIRM", "OI 強勁增加（空頭建倉確認）", 12
                elif c > 1:
                    return "OI_SHORT_MILD", "OI 溫和增加（空頭入場）", 6
                elif c < -3:
                    return "OI_SHORT_WARN", "OI 大幅減少（空頭回補警示）", -8
                elif c < -1:
                    return "OI_SHORT_CAUTION", "OI 微幅減少（注意空頭回補）", -3
            return "OI_NEUTRAL", "OI 無顯著變化", 0
        except Exception:
            return None, "", 0

    def stale_signal_recheck(self, sig, current_price, df1h):
        """
        對已註冊的信號重新評估
        如果環境變化 → 給出新建議
        - close_now: 應該立刻平倉
        - reduce: 應該減倉
        - hold: 維持原計畫
        - add: 可以加倉（更好機會）
        """
        try:
            if df1h is None or len(df1h) < 32:
                return "hold", ""
            direction = sig.get("direction", "")
            entry = sig.get("entry", 0)
            sl = sig.get("sl", 0)
            if not entry or not sl:
                return "hold", ""

            # 當前損益 %
            if direction == "LONG":
                pnl_pct = (current_price - entry) / entry * 100
            else:
                pnl_pct = (entry - current_price) / entry * 100

            # v62 P3：結構判斷一律用「已收盤」1h K（排除未收盤當根），避免半根 K 假突破
            closed = df1h.iloc[:-1]
            ema20 = closed["close"].ewm(span=20).mean()
            current_ema20 = float(ema20.iloc[-1])
            rsi_now = float(self.rsi(closed).iloc[-1])

            # 動能轉弱但有獲利 → 建議減倉（沿用，不平倉）
            if direction == "LONG" and current_price < current_ema20 * 0.995 and rsi_now < 45 and pnl_pct > 1:
                return "reduce", "結構轉弱，建議減倉鎖利"
            if direction == "SHORT" and current_price > current_ema20 * 1.005 and rsi_now > 55 and pnl_pct > 1:
                return "reduce", "結構轉強，建議減倉鎖利"
            # 強勢續航 → 持有（沿用）
            if direction == "LONG" and rsi_now > 60 and current_price > current_ema20 * 1.01 and pnl_pct > 0:
                return "hold", "趨勢延續，繼續持有"
            if direction == "SHORT" and rsi_now < 40 and current_price < current_ema20 * 0.99 and pnl_pct > 0:
                return "hold", "趨勢延續，繼續持有"

            # === v62 P3：結構性主動平倉「雙確認 + 深虧」才動手，否則交給硬止損 ===
            dd_ratio = float(os.getenv("STRUCT_EXIT_DD_RATIO", "0.6"))
            min_pct = float(os.getenv("STRUCT_EXIT_MIN_PCT", "1.5"))
            margin = float(os.getenv("STRUCT_BREAK_MARGIN", "0.5")) / 100.0
            sl_dist_pct = abs(entry - sl) / entry * 100
            loss_pct = -pnl_pct  # 虧損為正
            # (a) 深度浮虧：取較嚴者（較大門檻）
            if loss_pct < max(dd_ratio * sl_dist_pct, min_pct):
                return "hold", ""
            # (b) 結構確認破壞（已收盤 1h；前段結構低/高被收盤價破 margin 以上）
            if len(closed) < 22:
                return "hold", ""
            last_close = float(closed["close"].iloc[-1])
            prev_close = float(closed["close"].iloc[-2])
            vol = float(closed["volume"].iloc[-1])
            avg_vol = float(closed["volume"].iloc[-20:].mean())
            vol_spike = avg_vol > 0 and vol > avg_vol * 1.8
            if direction == "LONG":
                struct_low = float(closed["low"].iloc[-12:-2].min())
                broke = last_close < struct_low * (1 - margin)
                two_closes = broke and prev_close < struct_low * (1 - margin)
            else:
                struct_high = float(closed["high"].iloc[-12:-2].max())
                broke = last_close > struct_high * (1 + margin)
                two_closes = broke and prev_close > struct_high * (1 + margin)
            # 第二確認：連續 2 根收盤都在破壞側，或破壞當根爆量
            if broke and (two_closes or vol_spike):
                return "close_now", "深度浮虧 + 1h 收盤結構破壞（雙確認），停損"
            return "hold", ""
        except Exception:
            return "hold", ""

    def adaptive_sl_adjust(self, df, direction, entry, current_sl, current_price):
        """
        智能止損調整：根據 ATR 收縮/擴張動態調整
        - ATR 收縮 = 行情變穩 = 可以收緊止損
        - ATR 擴張 = 行情變動大 = 維持寬鬆止損
        """
        try:
            if df is None or len(df) < 30:
                return current_sl, ""
            # 近 14 根 vs 前 14 根 ATR
            recent_atr = float((df["high"].tail(14).max() - df["low"].tail(14).min()))
            prev_atr = float((df["high"].iloc[-28:-14].max() - df["low"].iloc[-28:-14].min()))
            if prev_atr <= 0:
                return current_sl, ""
            atr_change = recent_atr / prev_atr

            # 已有獲利時才考慮（避免虧損中亂動止損）
            if direction == "LONG":
                profit_pct = (current_price - entry) / entry * 100
                if profit_pct < 0.5:
                    return current_sl, ""
                # ATR 收縮 30% 以上 → 可以拉近止損到 EMA20 下方
                if atr_change < 0.7:
                    ema20 = float(df["close"].ewm(span=20).mean().iloc[-1])
                    new_sl = ema20 * 0.998
                    if new_sl > current_sl and new_sl < current_price:
                        return new_sl, "ATR 收縮，止損上移至 EMA20"
            else:
                profit_pct = (entry - current_price) / entry * 100
                if profit_pct < 0.5:
                    return current_sl, ""
                if atr_change < 0.7:
                    ema20 = float(df["close"].ewm(span=20).mean().iloc[-1])
                    new_sl = ema20 * 1.002
                    if new_sl < current_sl and new_sl > current_price:
                        return new_sl, "ATR 收縮，止損下移至 EMA20"
            return current_sl, ""
        except Exception:
            return current_sl, ""

    def portfolio_concentration_risk(self, active_signals, new_sig):
        """
        檢查新信號是否會造成倉位集中風險
        - 同方向 ≥ 5 個 → 警告
        - 同類型幣（meme/AI/L1）≥ 3 個 → 警告
        """
        if not active_signals:
            return False, ""

        new_dir = new_sig.get("direction", "")
        new_sym = new_sig.get("symbol", "")

        # 同方向計數
        same_dir = sum(1 for s in active_signals.values()
                       if s.get("direction") == new_dir)
        if same_dir >= 5:
            return True, "倉位集中：已有 " + str(same_dir) + " 個 " + new_dir + " 單"

        # 同類型偵測（簡化版：分類前綴）
        meme = ["PEPE", "SHIB", "DOGE", "WIF", "BONK", "FLOKI"]
        ai = ["FET", "RNDR", "WLD", "TAO", "AR"]
        l1 = ["BTC", "ETH", "SOL", "BNB", "AVAX", "NEAR", "APT", "SUI"]

        def cat(sym):
            short = sym.replace("/USDT", "")
            if short in meme: return "meme"
            if short in ai: return "ai"
            if short in l1: return "l1"
            return "other"

        new_cat = cat(new_sym)
        same_cat = sum(1 for s in active_signals.values()
                       if cat(s.get("symbol", "") if isinstance(s, dict) else "") == new_cat)
        if same_cat >= 3 and new_cat != "other":
            return True, "同類型集中：已有 " + str(same_cat) + " 個 " + new_cat + " 幣"

        return False, ""

    def score_dimensions(self, plan, sig1h, direction, vol_ratio):
        """
        v38 核心改進：把 30+ 個因子歸納為 5 大維度（0-20 分）
        散戶一眼能看懂信號強度
        """
        try:
            # === 1. 趨勢力（Trend Power）0-20 ===
            trend = 10  # 中性起點
            regime_state = plan.get("regime_state", "")
            if regime_state == "TRENDING_UP" and direction == "LONG":
                trend += 6
            elif regime_state == "TRENDING_DOWN" and direction == "SHORT":
                trend += 6
            elif regime_state == "VOLATILE":
                trend -= 4
            adx = sig1h.get("adx", 0)
            if adx > 30:
                trend += 4
            elif adx > 22:
                trend += 2
            elif adx < 16:
                trend -= 3
            struct_state = plan.get("struct_state", "")
            if "STRONG_UPTREND" in struct_state and direction == "LONG":
                trend += 3
            elif "STRONG_DOWNTREND" in struct_state and direction == "SHORT":
                trend += 3
            trend = max(0, min(20, trend))

            # === 2. 動能（Momentum）0-20 ===
            momentum = 10
            rsi = sig1h.get("rsi", 50)
            macd_h = sig1h.get("macd_hist", 0)
            if direction == "LONG":
                if 50 < rsi < 70:
                    momentum += 5
                elif rsi >= 70:
                    momentum += 2
                if macd_h > 0:
                    momentum += 3
                else:
                    momentum -= 3
            else:
                if 30 < rsi < 50:
                    momentum += 5
                elif rsi <= 30:
                    momentum += 2
                if macd_h < 0:
                    momentum += 3
                else:
                    momentum -= 3
            # 動能背離
            div_type = plan.get("div_type", "")
            if (div_type == "BULL_DIV" and direction == "LONG") or \
               (div_type == "BEAR_DIV" and direction == "SHORT"):
                momentum += 4
            momentum = max(0, min(20, momentum))

            # === 3. 結構（Structure）0-20 ===
            structure = 10
            # 流動性掃蕩 / Wyckoff（最強結構訊號）
            sweep_type = plan.get("sweep_type", "")
            if (sweep_type == "BULL_SWEEP" and direction == "LONG") or \
               (sweep_type == "BEAR_SWEEP" and direction == "SHORT"):
                structure += 6
            wyckoff_type = plan.get("wyckoff_type", "")
            if (wyckoff_type == "SPRING" and direction == "LONG") or \
               (wyckoff_type == "UPTHRUST" and direction == "SHORT"):
                structure += 6
            # MTF 共振
            mtf_grade = plan.get("mtf_grade", "")
            if "TRIPLE_BULL" in mtf_grade and direction == "LONG":
                structure += 4
            elif "TRIPLE_BEAR" in mtf_grade and direction == "SHORT":
                structure += 4
            elif "STRONG" in mtf_grade:
                structure += 2
            elif "DIVERGENT" in mtf_grade:
                structure -= 3
            structure = max(0, min(20, structure))

            # === 4. 量能（Volume）0-20 ===
            volume = 10
            if vol_ratio > 2:
                volume += 6
            elif vol_ratio > 1.5:
                volume += 4
            elif vol_ratio > 1.2:
                volume += 2
            elif vol_ratio < 0.7:
                volume -= 4
            # 訂單流
            ofi = plan.get("ofi_state", "")
            if (ofi in ("STRONG_BUY_FLOW", "BUY_FLOW") and direction == "LONG"):
                volume += 3
            elif (ofi in ("STRONG_SELL_FLOW", "SELL_FLOW") and direction == "SHORT"):
                volume += 3
            # 大資金流
            flow = plan.get("flow_state", "")
            if (flow == "BIG_BUYING" and direction == "LONG") or \
               (flow == "BIG_SELLING" and direction == "SHORT"):
                volume += 2
            volume = max(0, min(20, volume))

            # === 5. 風險（Risk Quality）0-20 ===
            # 風險維度的高分代表「風險可控」
            risk = 10
            ev = plan.get("expected_value", 0)
            if ev >= 1.5:
                risk += 6
            elif ev >= 1.0:
                risk += 4
            elif ev >= 0.5:
                risk += 2
            elif ev < 0:
                risk -= 4
            # 進場品質
            grade = plan.get("entry_grade", "C")
            risk += {"S": 5, "A": 3, "B": 1, "C": 0, "D": -3}.get(grade, 0)
            # 共識
            cons = plan.get("consensus_count", 0)
            if cons >= 5: risk += 3
            elif cons >= 3: risk += 1
            elif cons <= 1: risk -= 2
            risk = max(0, min(20, risk))

            total = trend + momentum + structure + volume + risk
            return {
                "trend": int(trend),
                "momentum": int(momentum),
                "structure": int(structure),
                "volume": int(volume),
                "risk": int(risk),
                "total": int(total),
            }
        except Exception:
            return {"trend": 10, "momentum": 10, "structure": 10,
                    "volume": 10, "risk": 10, "total": 50}

    # ⭐ v38 真實勝率自校準
    def real_winrate_stats(self, signal_results, tier=None, strategy_type=None,
                            direction=None, lookback=50):
        """
        從歷史 SIGNAL_RESULTS 計算真實勝率
        - 可按 tier / strategy_type / direction 篩選
        - 至少 5 筆才有意義，否則回傳 None
        """
        try:
            if not signal_results:
                return None
            # 篩選
            filtered = signal_results[-lookback:]
            if tier:
                filtered = [r for r in filtered if r.get("tier") == tier]
            if strategy_type:
                filtered = [r for r in filtered if r.get("strategy_type") == strategy_type]
            if direction:
                filtered = [r for r in filtered if r.get("direction") == direction]

            if len(filtered) < 5:
                return None

            wins = sum(1 for r in filtered if r.get("is_win", False) or r.get("final_pct", 0) > 0)
            total = len(filtered)
            win_rate = round(wins / total * 100, 1)
            avg_win = 0
            avg_loss = 0
            win_pcts = [r.get("final_pct", 0) for r in filtered if r.get("final_pct", 0) > 0]
            loss_pcts = [abs(r.get("final_pct", 0)) for r in filtered if r.get("final_pct", 0) < 0]
            if win_pcts:
                avg_win = round(sum(win_pcts) / len(win_pcts), 2)
            if loss_pcts:
                avg_loss = round(sum(loss_pcts) / len(loss_pcts), 2)
            ev = round(win_rate / 100 * avg_win - (1 - win_rate / 100) * avg_loss, 2)
            return {
                "win_rate": win_rate,
                "total": total,
                "wins": wins,
                "losses": total - wins,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "real_ev": ev,
            }
        except Exception:
            return None

    # ⭐ v38 連勝/連敗自動調節
    def auto_protection_mode(self, signal_results, lookback=10):
        """
        v53：保護模式不再靜音
        - 連虧 4-7 → DEFENSIVE：只推 B 級以上、倉位減半（仍持續運作）
        - 連虧 8+  → CIRCUIT_BREAK：暫停 6 小時後自動恢復（真的很糟才全停）
        - 連勝 3+  → AGGRESSIVE
        """
        return "NORMAL", "正常模式"  # 暫時停用保護模式 — 恢復時移除此行
        try:
            if not signal_results or len(signal_results) < 5:
                return "NORMAL", "正常模式"
            recent = signal_results[-lookback:]
            consecutive_loss = 0
            consecutive_win = 0
            for r in reversed(recent):
                if r.get("is_win", False) or r.get("final_pct", 0) > 0:
                    if consecutive_loss == 0:
                        consecutive_win += 1
                    else:
                        break
                else:
                    if consecutive_win == 0:
                        consecutive_loss += 1
                    else:
                        break
            if consecutive_loss >= 8:
                return "DEFENSIVE", "連虧 " + str(consecutive_loss) + " 次（熔斷暫停，以防守模式運作）"
            if consecutive_loss >= 4:
                return "DEFENSIVE", "連虧 " + str(consecutive_loss) + " 次，僅推 B 級以上、倉位減半"
            if consecutive_win >= 3:
                return "AGGRESSIVE", "連勝 " + str(consecutive_win) + " 次，放寬門檻"
            return "NORMAL", "正常模式"
        except Exception:
            return "NORMAL", "正常模式"

    def one_line_thesis(self, plan, direction):
        """
        產生「為什麼推這個」的一句話核心理由（3 個最強因子）
        """
        try:
            # 收集所有正向因子
            top_reasons = []

            # 1. Tier 等級（最重要）
            tier = plan.get("tier", "C")
            if tier == "S":
                top_reasons.append("💎 S 級稀有信號")
            elif tier == "A":
                top_reasons.append("🥇 A 級重點推薦")

            # 2. 策略 + 共識
            strat = plan.get("strategy_label", "")
            consensus = plan.get("consensus_count", 0)
            _total_votes = 8 if plan.get("news_vote") else 7
            if consensus >= 4 and strat:
                top_reasons.append(strat + " · " + str(consensus) + "/" + str(_total_votes) + " 共識")

            # 3. 流動性掃蕩/Wyckoff（最高勝率訊號）
            if plan.get("sweep_msg"):
                top_reasons.append(plan["sweep_msg"])
            elif plan.get("wyckoff_msg"):
                top_reasons.append(plan["wyckoff_msg"])

            # 4. 機構動向
            ofi = plan.get("ofi_state", "")
            if ofi == "STRONG_BUY_FLOW" and direction == "LONG":
                top_reasons.append("機構主動買盤強")
            elif ofi == "STRONG_SELL_FLOW" and direction == "SHORT":
                top_reasons.append("機構主動賣盤強")

            # 5. 市場結構
            struct = plan.get("struct_label", "")
            if "強" in struct and (
                ("UPTREND" in plan.get("struct_state", "") and direction == "LONG") or
                ("DOWNTREND" in plan.get("struct_state", "") and direction == "SHORT")
            ):
                top_reasons.append(struct)

            # 取前 3
            return "  ·  ".join(top_reasons[:3]) if top_reasons else "綜合多項技術指標"
        except Exception:
            return "綜合多項技術指標"



    # ============================================================
    # ⭐ v37 頂尖交易員等級分析
    # ============================================================

    def entry_timing(self, sig1h, df1h, current_price, entry, direction):
        """
        進場時機分析：判斷現在進場 vs 等回踩
        Returns: ("NOW" / "WAIT_PULLBACK" / "WAIT_BREAKOUT", reason, optimal_zone)
        """
        try:
            if df1h is None or len(df1h) < 20:
                return "NOW", "資料不足", None

            rsi = sig1h.get("rsi", 50)
            ema20 = float(df1h["close"].ewm(span=20).mean().iloc[-1])

            # 距離 entry 的偏離
            entry_dev = abs(current_price - entry) / entry * 100

            if direction == "LONG":
                # 已突破上方 → 等回踩 EMA20 或進場價
                if current_price > entry * 1.005 and rsi > 65:
                    pullback_zone = max(ema20, entry * 0.998)
                    return ("WAIT_PULLBACK",
                            f"目前已偏離進場 {entry_dev:.1f}%，等回踩 {pullback_zone:.4g}",
                            pullback_zone)
                # 還沒到進場 + RSI 弱 → 等突破
                if current_price < entry * 0.998 and rsi < 50:
                    return ("WAIT_BREAKOUT",
                            f"等突破 {entry:.4g} 確認方向", entry)
                # 正合適
                return "NOW", "目前價位適合進場", current_price
            else:
                if current_price < entry * 0.995 and rsi < 35:
                    pullback_zone = min(ema20, entry * 1.002)
                    return ("WAIT_PULLBACK",
                            f"目前已偏離進場 {entry_dev:.1f}%，等回踩 {pullback_zone:.4g}",
                            pullback_zone)
                if current_price > entry * 1.002 and rsi > 50:
                    return ("WAIT_BREAKOUT",
                            f"等跌破 {entry:.4g} 確認方向", entry)
                return "NOW", "目前價位適合進場", current_price
        except Exception:
            return "NOW", "", None

    def volume_anomaly(self, df, period=50):
        """
        異常成交量區域識別（機構聚集地）
        找出 vol > 平均 2 倍 的價格區間
        """
        try:
            if df is None or len(df) < period:
                return []
            recent = df.tail(period)
            avg_vol = float(recent["volume"].mean())
            anomalies = []
            for i in range(len(recent)):
                vol = float(recent["volume"].iloc[i])
                if vol > avg_vol * 2:
                    price = float(recent["close"].iloc[i])
                    anomalies.append({
                        "price": price,
                        "vol_ratio": round(vol / avg_vol, 1),
                        "bars_ago": len(recent) - 1 - i
                    })
            # 按時間最近排序
            anomalies.sort(key=lambda x: x["bars_ago"])
            return anomalies[:3]
        except Exception:
            return []

    def smart_tp_extend(self, df, direction, entry, tp1, tp2, tp3, current_price):
        """
        TP 智能調整：達 TP1 後若動能仍強，把 TP2/TP3 拉更遠
        """
        try:
            if df is None or len(df) < 20:
                return None, None, None, ""
            rsi = float(self.rsi(df).iloc[-1])
            ema20 = float(df["close"].ewm(span=20).mean().iloc[-1])

            if direction == "LONG":
                # 強勢條件：RSI > 60 + 站上 EMA20 + 現價已過 TP1
                if current_price > tp1 and rsi > 60 and current_price > ema20:
                    # 把 TP2 拉到原本 TP3，TP3 拉更遠 8%
                    new_tp2 = tp3
                    new_tp3 = round(entry * 1.10, 6)
                    return new_tp2, new_tp3, None, "動能強勁，目標拉遠"
            else:
                if current_price < tp1 and rsi < 40 and current_price < ema20:
                    new_tp2 = tp3
                    new_tp3 = round(entry * 0.90, 6)
                    return new_tp2, new_tp3, None, "動能強勁，目標拉遠"
            return None, None, None, ""
        except Exception:
            return None, None, None, ""

    def alt_season_indicator(self, btc_df, eth_df):
        """
        判斷當前是 BTC 季還是 alt 季
        BTC 強勢 + alt 弱 = BTC 季（做 BTC）
        BTC 橫盤 + alt 強 = Alt 季（做小幣）
        """
        try:
            if btc_df is None or len(btc_df) < 30:
                return "UNKNOWN", "未知"
            if eth_df is None:
                eth_df = btc_df

            # 30 根 K 線變化
            btc_chg = (float(btc_df["close"].iloc[-1]) - float(btc_df["close"].iloc[-30])) / float(btc_df["close"].iloc[-30]) * 100
            eth_chg = (float(eth_df["close"].iloc[-1]) - float(eth_df["close"].iloc[-30])) / float(eth_df["close"].iloc[-30]) * 100

            diff = eth_chg - btc_chg

            if diff > 5:
                return "ALT_SEASON", "Alt 季（小幣更強）"
            elif diff > 2:
                return "ALT_LEANING", "偏 Alt（小幣略強）"
            elif diff < -5:
                return "BTC_SEASON", "BTC 季（主流更強）"
            elif diff < -2:
                return "BTC_LEANING", "偏 BTC（主流略強）"
            return "BALANCED", "BTC/Alt 平衡"
        except Exception:
            return "UNKNOWN", "未知"

    def market_health_score(self, sig1h, vol_ratio, regime_state, fg_val,
                              consensus_count, btc_health):
        """
        全局市場健康分（0-100）
        綜合多項指標的「總體建議信心」
        """
        try:
            score = 50  # 中性起點

            # ADX 趨勢強度
            adx = sig1h.get("adx", 0)
            if adx > 30: score += 10
            elif adx > 22: score += 5
            elif adx < 15: score -= 8

            # 量能
            if vol_ratio > 1.8: score += 8
            elif vol_ratio > 1.3: score += 4
            elif vol_ratio < 0.7: score -= 5

            # Regime
            regime_bonus = {
                "TRENDING_UP": 10,
                "TRENDING_DOWN": 10,
                "RANGING_TIGHT": 0,
                "RANGING_WIDE": -3,
                "VOLATILE": -10,
            }.get(regime_state, 0)
            score += regime_bonus

            # F&G 極端避開
            if fg_val and 30 <= fg_val <= 70:
                score += 5
            elif fg_val and (fg_val <= 15 or fg_val >= 85):
                score -= 5

            # 共識
            if consensus_count >= 5: score += 8
            elif consensus_count >= 3: score += 4
            elif consensus_count <= 1: score -= 5

            # BTC 健康
            if btc_health == "HEALTHY": score += 5
            elif btc_health == "DANGER": score -= 10

            return max(0, min(100, score))
        except Exception:
            return 50

    def best_session_hint(self, symbol):
        """
        最佳交易時段提示（根據歷史經驗）
        - 主流幣：紐約時段（13:00-17:00 UTC）流動性最好
        - Alt 幣：亞洲時段（00:00-06:00 UTC）波動較大
        - Meme 幣：紐約 + 亞洲交接
        """
        try:
            hour_utc = datetime.now(timezone.utc).hour
            short = symbol.replace("/USDT", "")

            meme = ["PEPE", "SHIB", "DOGE", "WIF", "BONK", "FLOKI"]
            major = ["BTC", "ETH", "BNB", "XRP", "SOL"]

            if short in major:
                # 紐約時段 + 倫敦時段
                if 13 <= hour_utc <= 17:
                    return "🔥 紐約時段（流動性最佳）"
                elif 7 <= hour_utc <= 11:
                    return "✨ 倫敦時段（活躍時段）"
                elif 0 <= hour_utc <= 4:
                    return "💤 亞洲時段（波動較小）"
            elif short in meme:
                if 13 <= hour_utc <= 18:
                    return "🚀 Meme 幣黃金時段"
                else:
                    return "⏰ 非 Meme 主時段"
            else:
                # Alt 幣
                if 0 <= hour_utc <= 6:
                    return "🌏 亞洲時段（Alt 活躍）"
                elif 13 <= hour_utc <= 17:
                    return "🔥 紐約時段（流動性佳）"
            return ""
        except Exception:
            return ""


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
        """並行抓取多來源新聞：加密 + 時事 + 經濟"""

        # === 加密貨幣專屬新聞 ===
        async def try_cryptocompare_zh():
            try:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=ZH&sortOrder=latest"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{
                            "title": x.get("title", ""),
                            "published_at": datetime.fromtimestamp(
                                x.get("published_on", 0), tz=timezone.utc
                            ).isoformat() if x.get("published_on") else "",
                            "source": x.get("source", "CC"),
                            "category": "crypto"
                        } for x in data.get("Data", [])[:12]]
            except Exception: pass
            return None

        async def try_cryptocompare_en_top():
            """English top stories - 含 Trump, Fed, China 等重要時事"""
            try:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest&categories=Regulation,Mining,Trading,Market,Fiat"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{
                            "title": x.get("title", ""),
                            "published_at": datetime.fromtimestamp(
                                x.get("published_on", 0), tz=timezone.utc
                            ).isoformat() if x.get("published_on") else "",
                            "source": x.get("source", "CC"),
                            "category": "crypto"
                        } for x in data.get("Data", [])[:10]]
            except Exception: pass
            return None

        async def try_binance_announce():
            try:
                url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=10"
                headers = {"User-Agent": "Mozilla/5.0", "lang": "zh-CN"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        articles = data.get("data", {}).get("articles", [])[:10]
                        return [{
                            "title": x.get("title", ""),
                            "published_at": datetime.fromtimestamp(
                                x.get("releaseDate", 0) / 1000, tz=timezone.utc
                            ).isoformat() if x.get("releaseDate") else "",
                            "source": "Binance",
                            "category": "crypto"
                        } for x in articles]
            except Exception: pass
            return None

        async def try_binance_square():
            try:
                url = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?catalogId=48&pageNo=1&pageSize=12"
                headers = {"User-Agent": "Mozilla/5.0", "lang": "zh-CN"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        articles = data.get("data", {}).get("articles", [])[:10]
                        return [{
                            "title": x.get("title", ""),
                            "published_at": datetime.fromtimestamp(
                                x.get("releaseDate", 0) / 1000, tz=timezone.utc
                            ).isoformat() if x.get("releaseDate") else "",
                            "source": "幣安",
                            "category": "crypto"
                        } for x in articles]
            except Exception: pass
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
                        for item in items[:10]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title: continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception: pass
                                results.append({"title": title, "published_at": pub_iso,
                                                 "source": "PANews", "category": "crypto"})
                        if results: return results
            except Exception: pass
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
                        for item in items[:10]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title: continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception: pass
                                results.append({"title": title, "published_at": pub_iso,
                                                 "source": "Odaily", "category": "crypto"})
                        if results: return results
            except Exception: pass
            return None

        # === 全球時事 + 經濟新聞（v29 新增） ===
        async def try_bbc_chinese():
            """BBC 中文：國際大事，含中美關係、政治、經濟"""
            try:
                url = "https://feeds.bbci.co.uk/zhongwen/trad/rss.xml"
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        text = await r.text()
                        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                        results = []
                        for item in items[:15]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title: continue
                                # 過濾與經濟/政治/加密相關的
                                keywords = ["經濟", "金融", "聯準會", "通膨", "利率", "美元", "貿易",
                                              "關稅", "制裁", "戰爭", "衝突", "選舉", "拜登", "川普",
                                              "习近平", "中美", "中國", "美國", "歐盟", "FOMC", "GDP",
                                              "失業", "股市", "比特幣", "加密"]
                                if not any(kw in title for kw in keywords):
                                    continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception: pass
                                results.append({"title": title, "published_at": pub_iso,
                                                 "source": "BBC中文", "category": "world"})
                        if results: return results[:8]
            except Exception: pass
            return None

        async def try_yahoo_finance():
            """Yahoo Finance: 經濟 + 加密相關"""
            try:
                url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD,ETH-USD&region=US&lang=en-US"
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        text = await r.text()
                        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                        results = []
                        for item in items[:10]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title: continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception: pass
                                results.append({"title": title, "published_at": pub_iso,
                                                 "source": "Yahoo Finance", "category": "finance"})
                        if results: return results[:8]
            except Exception: pass
            return None

        async def try_dw_chinese():
            """DW 德國之聲中文：國際政治經濟"""
            try:
                url = "https://rss.dw.com/xml/rss-chi-all"
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as r:
                    if r.status == 200:
                        text = await r.text()
                        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                        results = []
                        for item in items[:15]:
                            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", item, re.DOTALL)
                            pub_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_m:
                                title = (title_m.group(1) or title_m.group(2) or "").strip()
                                if not title: continue
                                keywords = ["經濟", "金融", "聯準會", "通膨", "利率", "貿易", "關稅",
                                              "制裁", "戰爭", "衝突", "選舉", "川普", "拜登", "习近平",
                                              "中美", "中國", "美國", "歐盟", "比特幣", "加密"]
                                if not any(kw in title for kw in keywords):
                                    continue
                                pub_iso = ""
                                if pub_m:
                                    try:
                                                                        pub_iso = parsedate_to_datetime(pub_m.group(1)).isoformat()
                                    except Exception: pass
                                results.append({"title": title, "published_at": pub_iso,
                                                 "source": "DW中文", "category": "world"})
                        if results: return results[:8]
            except Exception: pass
            return None

        # ⭐ 並行抓取所有來源
        tasks = [
            try_cryptocompare_zh(),
            try_cryptocompare_en_top(),
            try_binance_announce(),
            try_binance_square(),
            try_panews(),
            try_odaily(),
            try_bbc_chinese(),       # v29 新增
            try_yahoo_finance(),     # v29 新增
            try_dw_chinese(),        # v29 新增
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_news = []
        seen_titles = set()
        for r in results:
            if isinstance(r, list):
                for n in r:
                    title = n.get("title", "")
                    # 去重：用前 30 字作為 key
                    key = title[:30]
                    if title and key not in seen_titles:
                        seen_titles.add(key)
                        all_news.append(n)

        def get_time(n):
            try:
                return datetime.fromisoformat(n.get("published_at", "").replace("Z", "+00:00"))
            except Exception:
                return datetime.min.replace(tzinfo=timezone.utc)
        all_news.sort(key=get_time, reverse=True)
        return all_news[:20]  # v29 返回 20 條（v28 只有 12）


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
        """v29: 加入分類標記（加密/時事/財經）"""
        score, items = 0, []
        for item in news[:20]:
            title = item.get("title", "")
            t = title.lower()
            published = item.get("published_at", "")
            category = item.get("category", "crypto")
            bull_count = sum(1 for w in self.BULL_W if w in title or w in t)
            bear_count = sum(1 for w in self.BEAR_W if w in title or w in t)
            item_score = (bull_count - bear_count) * 0.1
            score += item_score
            # v29 分類 emoji
            cat_emoji = "🌍" if category == "world" else ("💰" if category == "finance" else "")
            sent_emoji = "📗" if item_score > 0.05 else "📕" if item_score < -0.05 else "📒"
            emoji = (cat_emoji + sent_emoji) if cat_emoji else sent_emoji
            items.append({
                "title": title[:80], "emoji": emoji, "published": published,
                "source": item.get("source", ""), "category": category
            })
        score = max(-1.0, min(1.0, score))
        if score > 0.3:
            label = "📗 偏多"
        elif score < -0.3:
            label = "📕 偏空"
        else:
            label = "📒 中性"
        return score, label, items[:12]

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
        if score >= 1.8:  # v46 平衡：±1.8 在雜訊和靈敏度之間
            direction = "做多 🟢"
            den = "LONG"
        elif score <= -1.8:
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
                            btc_df=None, btc_ticker=None, symbol="",
                            historical_results=None, oi_data=None):
        direction = sig1h["direction_en"]
        if direction == "NEUTRAL":
            return None, "信號中性"

        p = current_price
        atr_1h = sig1h["atr"]
        atr_4h = sig4h["atr"] if sig4h["atr"] > 0 else atr_1h * 4

        # ===== 必要過濾（放寬版）=====
        has_div = bool(sig1h.get("div"))

        # 強逆勢且無背離 → 過濾
        # v42 不再強制 reject（讓 score 自己懲罰）
        if direction == "LONG" and sig1h["regime"] == "STRONG_BEAR" and not has_div:
            score -= 12
            risks.append("⚠️ 強空頭逆勢做多")
        if direction == "SHORT" and sig1h["regime"] == "STRONG_BULL" and not has_div:
            score -= 12
            risks.append("⚠️ 強多頭逆勢做空")

        # ADX 放寬到 16（v25 - 允許更多機會）
        if sig1h["adx"] < 15:  # v46 平衡：15+ 是趨勢萌芽
            return None, "ADX過低 (<15，無趨勢)"

        # ⭐ v57 情境閘門：高位不追多/低位不追空、4H強反不逆勢、盤整只做邊緣反轉
        _gate_info = {"range_pos": None, "tags": []}
        if os.getenv("STRICT_CONTEXT_GATE", "true").lower() == "true":
            _ok_gate, _gate_reason, _gate_info = self.entry_context_gate(
                direction, sig1h, sig4h, df1h, df4h, sw_res_1h, sw_sup_1h, p)
            if not _ok_gate:
                try:
                    self._gate_blocked.append({
                        "sym": symbol, "dir": direction, "reason": _gate_reason,
                        "ts": datetime.now(timezone.utc).isoformat()})
                    self._gate_blocked = self._gate_blocked[-300:]
                except Exception:
                    pass
                return None, "情境閘門: " + _gate_reason

        # ⭐ Squeeze 過濾：BB 在 KC 內 = 盤整，不交易
        # v42 不再拒絕 Squeeze（盤整後常有突破，不應錯過）
        if sig1h.get("squeeze_on", False):
            score -= 8  # 改成扣分
            risks.append("⚠️ Squeeze 盤整中（可能假突破）")

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
        # v42 三週期反向不再 reject（可能是反轉機會）
        if direction == "LONG" and mtf_state == "STRONG_BEAR_MTF":
            score -= 15
            risks.append("⚠️ 三週期皆空（極度逆勢）")
        if direction == "SHORT" and mtf_state == "STRONG_BULL_MTF":
            score -= 15
            risks.append("⚠️ 三週期皆多（極度逆勢）")

        # ⭐ v23：反指標檢查
        anti_violations = self.anti_indicator_check(direction, sig1h)
        if anti_violations:
            return None, "反指標：" + ", ".join(anti_violations)

        # 風報比門檻提高到 1.5
        if sig1h["rr"] < 1.0:  # v51：TP1 至少 1:1（TP2/TP3 提供主要獲利，下游 TP2 RR>=1.5 把關）
            return None, "風報比不足 (TP1 <1.0)"

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

        # 多空比（v63：改用 ls_ratio_signal，補全逆向加分 + 擁擠懲罰）
        if ls_ratio is not None:
            lsr_state, lsr_label, lsr_bonus = self.ls_ratio_signal(ls_ratio)
            if lsr_state in ("EXTREME_LONG_CROWDED", "LONG_CROWDED") and direction == "SHORT":
                score += lsr_bonus
                factors.append("⚖️ " + lsr_label)
            elif lsr_state in ("EXTREME_SHORT_CROWDED", "SHORT_CROWDED") and direction == "LONG":
                score += lsr_bonus
                factors.append("⚖️ " + lsr_label)
            elif lsr_state == "EXTREME_LONG_CROWDED" and direction == "LONG":
                score -= lsr_bonus
                risks.append("⚠️ 散戶擁擠做多（反轉風險）")
            elif lsr_state == "EXTREME_SHORT_CROWDED" and direction == "SHORT":
                score -= lsr_bonus
                risks.append("⚠️ 散戶擁擠做空（反轉風險）")

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

        # ⭐ v31 市場結構分析（HH/HL）
        struct_state, struct_label, struct_bonus = self.market_structure(df1h)
        if direction == "LONG":
            if struct_state in ("STRONG_UPTREND", "UPTREND"):
                score += struct_bonus
                factors.append("✅ " + struct_label)
            elif struct_state == "STRONG_DOWNTREND":
                score -= 15
                risks.append("⚠️ 1H 下降結構（逆勢做多）")
        else:
            if struct_state in ("STRONG_DOWNTREND", "DOWNTREND"):
                score += abs(struct_bonus)
                factors.append("✅ " + struct_label)
            elif struct_state == "STRONG_UPTREND":
                score -= 15
                risks.append("⚠️ 1H 上升結構（逆勢做空）")

        # ⭐ v31 多週期共振分級
        mtf_grade, mtf_grade_label, mtf_grade_bonus = self.mtf_resonance_grade(sig15m, sig1h, sig4h)
        if direction == "LONG" and mtf_grade_bonus > 0:
            score += mtf_grade_bonus
            factors.append("✅ " + mtf_grade_label)
        elif direction == "SHORT" and mtf_grade_bonus < 0:
            score += abs(mtf_grade_bonus)
            factors.append("✅ " + mtf_grade_label)
        elif mtf_grade == "DIVERGENT":
            score -= 5
            risks.append("⚠️ 週期分歧")

        # ⭐ v31 BTC 相關性分析（alt 幣）
        if btc_df is not None and sig1h.get("symbol", "") != "BTC/USDT":
            corr_val, corr_state, corr_bonus = self.btc_correlation(df1h, btc_df)
            if corr_state == "INDEPENDENT":
                score += corr_bonus
                factors.append("✅ 獨立行情（相關性 " + str(round(corr_val, 2)) + "）")
            elif corr_state == "STRONG_INVERSE":
                score += corr_bonus
                factors.append("✅ 與 BTC 強反向，獨立性高")
            elif corr_state == "HIGH_SYNC":
                risks.append("📊 與 BTC 高度同步 " + str(round(corr_val, 2)))

        # ⭐ v36 市場 regime（全局視角）
        regime_state, regime_label, regime_bonus = self.market_regime_global(None, df1h)
        # regime 影響：在 trending 期間加分，在 volatile 期間扣分
        if regime_state == "TRENDING_UP" and direction == "LONG":
            score += regime_bonus
            factors.append("🌐 " + regime_label)
        elif regime_state == "TRENDING_DOWN" and direction == "SHORT":
            score += regime_bonus
            factors.append("🌐 " + regime_label)
        elif regime_state == "TRENDING_UP" and direction == "SHORT":
            score -= 5
            risks.append("⚠️ 整體牛市中逆勢做空")
        elif regime_state == "TRENDING_DOWN" and direction == "LONG":
            score -= 5
            risks.append("⚠️ 整體熊市中逆勢做多")
        elif regime_state == "VOLATILE":
            score += regime_bonus  # 負值
            risks.append("⚠️ " + regime_label)

        # ⭐ v37 進場時機分析
        timing_state, timing_msg, timing_zone = self.entry_timing(
            sig1h, df1h, current_price, p, direction
        )
        # 進場時機資訊不影響評分，但會在輸出顯示

        # ⭐ v37 異常成交量區域
        vol_anomalies = self.volume_anomaly(df1h)

        # ⭐ v37 最佳時段提示
        best_session = self.best_session_hint(symbol)

        # ⭐ v36 Funding Rate 極端值反轉
        if funding is not None:
            fr_state, fr_label, fr_bonus = self.funding_extreme(funding)
            if fr_state == "EXTREME_LONG_CROWDED" and direction == "SHORT":
                score += fr_bonus
                factors.append("💰 " + fr_label)
            elif fr_state == "EXTREME_SHORT_CROWDED" and direction == "LONG":
                score += fr_bonus
                factors.append("💰 " + fr_label)
            elif fr_state == "EXTREME_LONG_CROWDED" and direction == "LONG":
                score -= fr_bonus
                risks.append("⚠️ 多單過於擁擠（反轉風險）")
            elif fr_state == "EXTREME_SHORT_CROWDED" and direction == "SHORT":
                score -= fr_bonus
                risks.append("⚠️ 空單過於擁擠（反轉風險）")

        # ⭐ v32 訂單流不平衡（機構動向）
        ofi_value, ofi_state, ofi_bonus = self.order_flow_imbalance(df1h)
        if direction == "LONG" and ofi_state in ("STRONG_BUY_FLOW", "BUY_FLOW"):
            score += ofi_bonus
            factors.append("✅ " + ("強勁主動買盤" if ofi_state == "STRONG_BUY_FLOW" else "主動買盤偏多"))
        elif direction == "SHORT" and ofi_state in ("STRONG_SELL_FLOW", "SELL_FLOW"):
            score += abs(ofi_bonus)
            factors.append("✅ " + ("強勁主動賣盤" if ofi_state == "STRONG_SELL_FLOW" else "主動賣盤偏多"))
        elif direction == "LONG" and ofi_state in ("STRONG_SELL_FLOW",):
            score -= 10
            risks.append("⚠️ 主動賣盤強勢")
        elif direction == "SHORT" and ofi_state in ("STRONG_BUY_FLOW",):
            score -= 10
            risks.append("⚠️ 主動買盤強勢")

        # ⭐ v63 OI 變化率 + 價格方向一致性
        if oi_data is not None:
            oi_state, oi_label, oi_bonus = self.oi_signal(oi_data, direction)
            if oi_state is not None and oi_bonus != 0:
                if oi_bonus > 0:
                    score += oi_bonus
                    factors.append("📊 " + oi_label)
                else:
                    score += oi_bonus
                    risks.append("⚠️ " + oi_label)

        # ⭐ v32 流動性掃蕩偵測（機構掃止損）
        sweep_type, sweep_msg = self.liquidity_sweep(df1h)
        if sweep_type == "BULL_SWEEP" and direction == "LONG":
            score += 15
            factors.append("💧 " + sweep_msg)
        elif sweep_type == "BEAR_SWEEP" and direction == "SHORT":
            score += 15
            factors.append("💧 " + sweep_msg)

        # ⭐ v32 多週期動能背離
        div_type, div_msg = self.momentum_divergence(df4h, df1h)
        if div_type == "BULL_DIV" and direction == "LONG":
            score += 12
            factors.append("📈 " + div_msg)
        elif div_type == "BEAR_DIV" and direction == "SHORT":
            score += 12
            factors.append("📉 " + div_msg)
        elif div_type == "BEAR_DIV" and direction == "LONG":
            score -= 8
            risks.append("⚠️ 高週期動能衰竭，做多風險")
        elif div_type == "BULL_DIV" and direction == "SHORT":
            score -= 8
            risks.append("⚠️ 高週期動能轉強，做空風險")

        # ⭐ v32 Wyckoff 形態
        wyckoff_type, wyckoff_msg = self.wyckoff_pattern(df1h)
        if wyckoff_type == "SPRING" and direction == "LONG":
            score += 14
            factors.append("🎯 " + wyckoff_msg)
        elif wyckoff_type == "UPTHRUST" and direction == "SHORT":
            score += 14
            factors.append("🎯 " + wyckoff_msg)

        # ⭐ v32 K 線形態組合
        combos, combo_bonus = self.candle_combo(df1h, direction)
        if combos:
            score += combo_bonus
            factors.append("🕯 " + " + ".join(combos))

        # ⭐ v32 多策略共識制
        consensus_count, consensus_total, voting_strategies = self.strategy_consensus(
            direction, sig1h, df1h, df4h, df1h, vol_ratio, sw_res_1h, sw_sup_1h, current_price
        )  # v51 修：df15m 未定義（參數名為 df_daily），改傳 df1h（consensus 內部僅用 df1h）

        # ⭐ v55 新聞情緒第 8 票：方向與新聞情緒一致才加票，並記錄來源以便驗證
        news_vote = False
        try:
            _ns = getattr(self, "_news_sentiment", None)
            if _ns:
                _sent = _ns.get("sentiment", "中性")
                try:
                    _strength = int(_ns.get("strength", 0))
                except (ValueError, TypeError):
                    _strength = 0
                # 只有強度 >= 3 的明確情緒才算數，避免雜訊
                if _strength >= 3:
                    if (direction == "LONG" and _sent == "看多") or \
                       (direction == "SHORT" and _sent == "看空"):
                        consensus_count += 1
                        news_vote = True
                        voting_strategies = list(voting_strategies) + ["📰新聞情緒"]
                        # v63 加強：高強度新聞額外直接加分
                        if _strength >= 5:
                            score += 8
                            factors.append("📰 新聞情緒強力支持（強度 5/5）")
                        elif _strength >= 4:
                            score += 4
                            factors.append("📰 新聞情緒支持（強度 " + str(_strength) + "/5）")
        except Exception:
            pass
        # 至少 3 個策略同意才高品質
        # v55: 顯示總票數動態 — 有新聞票時是 /8，否則 /7
        _total_votes = 8 if news_vote else 7
        if consensus_count >= 5:
            score += 15
            factors.append("🎯 多策略共識 (" + str(consensus_count) + "/" + str(_total_votes) + ")")
        elif consensus_count >= 4:
            score += 10
            factors.append("🎯 四重策略共識 (" + str(consensus_count) + "/" + str(_total_votes) + ")")
        elif consensus_count >= 3:
            score += 5
            factors.append("✅ 三重策略共識 (" + str(consensus_count) + "/" + str(_total_votes) + ")")
        elif consensus_count <= 1:
            score -= 10
            risks.append("⚠️ 共識不足 (" + str(consensus_count) + "/" + str(_total_votes) + ")")

        # ⭐ v32 交易所大資金流
        flow_state, flow_msg = self.exchange_flow(df1h)
        if flow_state == "BIG_BUYING" and direction == "LONG":
            score += 8
            factors.append("🐋 " + flow_msg)
        elif flow_state == "BIG_SELLING" and direction == "SHORT":
            score += 8
            factors.append("🐋 " + flow_msg)
        elif flow_state == "BIG_SELLING" and direction == "LONG":
            score -= 5
            risks.append("⚠️ 大資金賣出中")
        elif flow_state == "BIG_BUYING" and direction == "SHORT":
            score -= 5
            risks.append("⚠️ 大資金買入中")

        # ⭐ v31 波動率分位數
        vol_pct, vol_state = self.volatility_percentile(df1h)
        if vol_state == "EXTREME_LOW":
            score += 5
            factors.append("✅ 低波動分位（即將爆發）")
        elif vol_state == "EXTREME_HIGH":
            score -= 5
            risks.append("⚠️ 極高波動分位（注意反轉）")

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

        # ⭐ v57 區間位階輕量加減分
        _rp = _gate_info.get("range_pos")
        if _rp is not None:
            if direction == "LONG":
                if _rp <= 0.35:
                    score += 5; factors.append("✅ 低位階進多")
                elif _rp >= 0.75:
                    score -= 5; risks.append("⚠️ 高位階追多")
            else:
                if _rp >= 0.65:
                    score += 5; factors.append("✅ 高位階進空")
                elif _rp <= 0.25:
                    score -= 5; risks.append("⚠️ 低位階追空")

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
                entry = self.px_round(p * 0.999)
                entry_note = "立即進場（已測支撐）"
            elif ref_sup and (p - ref_sup[0]) / p < 0.015:
                entry = self.px_round(ref_sup[0] * 1.002)
                entry_note = "限價單等回測支撐"
            else:
                entry = self.px_round(p * 0.997)
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
                entry = self.px_round(p * 1.001)
                entry_note = "立即進場（已測阻力）"
            elif ref_res and (ref_res[0] - p) / p < 0.015:
                entry = self.px_round(ref_res[0] * 0.998)
                entry_note = "限價單等反彈阻力"
            else:
                entry = self.px_round(p * 1.003)
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

        # ⭐ v57 防呆：低價幣精度異常（entry/sl 被砍成 0 或重合）直接放棄
        if entry <= 0 or sl <= 0 or abs(entry - sl) <= 0:
            return None, "價格精度異常"

        risk = abs(entry - sl)
        rr1 = round(abs(tp1 - entry) / risk, 2) if risk > 0 else 0
        rr2 = round(abs(tp2 - entry) / risk, 2) if risk > 0 else 0
        rr3 = round(abs(tp3 - entry) / risk, 2) if risk > 0 else 0
        rr4 = round(abs(tp4 - entry) / risk, 2) if risk > 0 else 0

        if rr2 < 1.5:  # v46 平衡：TP2 1.5+ 即可
            return None, "TP2風報比過低 (<1.5)"

        # ⭐ v49 暫定值（會在 entry_grade 之後重算）
        win_rate = 50  # 之後重算
        # Kelly 倉位先用佔位（之後重算）
        avg_rr = (rr1 + rr2) / 2
        position = 0  # 之後重算

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
        # v42 D 級不再 reject（嚴格時機可能錯過好機會）
        if entry_grade["grade"] == "D":
            score -= 10
            risks.append("⚠️ 進場時機 D 級")

        # ⭐ v49 職業勝率校準（在 entry_grade 之後，才有所有變數可用）
        # 1. 基礎勝率：根據 ADX + 趨勢狀態
        _adx_v = sig1h.get("adx", 0)
        _regime = sig1h.get("regime", "")
        if _adx_v >= 28 and _regime in ("STRONG_BULL", "STRONG_BEAR"):
            _base_wr = 61
        elif _adx_v >= 25:
            _base_wr = 58
        elif _adx_v >= 22:
            _base_wr = 56
        elif _adx_v >= 18:
            _base_wr = 54   # v51: 53→54
        elif _adx_v >= 15:
            _base_wr = 51   # v51: 50→51（ADX>15 趨勢成形，誠實 51%）
        else:
            _base_wr = 47

        # 2. 共識加成（每多 1 個策略同意 +2%，從 2 起加，最多 +8）
        _consensus_bonus = max(0, min(consensus_count - 2, 4)) * 2

        # 3. 進場時機加成
        _grade_bonus = {"S": 6, "A": 4, "B": 2, "C": 0, "D": -3}.get(entry_grade["grade"], 0)

        # 4. MTF 共振加成
        _mtf_bonus = 0
        if mtf_grade in ("TRIPLE_BULL", "TRIPLE_BEAR"):
            _mtf_bonus = 5
        elif mtf_grade in ("DOUBLE_BULL", "DOUBLE_BEAR"):
            _mtf_bonus = 2

        # 5. 進場確認 K 線
        _conf_bonus = 2 if has_conf else 0

        # 6. 風險懲罰
        _risk_penalty = 0
        if sig1h.get("squeeze_on", False):
            _risk_penalty += 3
        if _regime == "STRONG_BEAR" and direction == "LONG":
            _risk_penalty += 5
        if _regime == "STRONG_BULL" and direction == "SHORT":
            _risk_penalty += 5

        # 整合
        win_rate = _base_wr + _consensus_bonus + _grade_bonus + _mtf_bonus + _conf_bonus - _risk_penalty
        win_rate = round(min(78, max(40, win_rate)))

        # ⭐ v53 真實勝率校準：理論值整體下修，並用歷史實績覆蓋
        # 理由：v52 理論勝率系統性高估（理論 51% vs 實際 10%）
        win_rate = round(win_rate * 0.82)          # 理論值統一打 82 折（消除樂觀偏差）
        try:
            _hist = getattr(self, "_external_results", None)  # bot.py 會在呼叫前注入
            if _hist:
                # 先看「同進場 grade」的真實勝率（樣本要求較低）
                _g = entry_grade["grade"]
                _grade_hist = [r for r in _hist[-100:] if r.get("entry_grade") == _g]
                if len(_grade_hist) >= 10:
                    _gw = sum(1 for r in _grade_hist if r.get("final_pct", 0) > 0)
                    _real_g = _gw / len(_grade_hist) * 100
                    # 真實值權重 0.7，理論值 0.3（樣本越多越信真實）
                    _w = min(0.7, 0.4 + len(_grade_hist) * 0.01)
                    win_rate = round(win_rate * (1 - _w) + _real_g * _w)
        except Exception:
            pass
        win_rate = round(min(75, max(20, win_rate)))   # 下限放寬到 20（誠實反映可能很低）

        # ⭐ v49 用更新後的 win_rate 重算 Kelly 倉位
        # v57 防呆：avg_rr <= 0 會讓除式爆炸/方向錯誤，異常時退回中性值 1.0
        if avg_rr <= 0:
            avg_rr = 1.0
        kelly = max(0, (win_rate/100 - (1 - win_rate/100) / avg_rr)) * 100
        position = round(min(kelly * 0.5, 6), 1)  # 單筆上限 6%

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
            "news_vote": news_vote,  # v55：這單有沒有吃到新聞情緒票（供事後驗證新聞準不準）
            "regime": sig1h.get("regime", ""),
            "adx": sig1h.get("adx", 0),
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
            # v31 新增深度分析
            "struct_state": struct_state,
            "struct_label": struct_label,
            "mtf_grade": mtf_grade,
            "mtf_grade_label": mtf_grade_label,
            "vol_pct": round(vol_pct, 1),
            "vol_state": vol_state,
            # v57 情境閘門資訊（驗證儀表用）
            "range_pos": _gate_info.get("range_pos"),
            "gate_tags": _gate_info.get("tags", []),
            "scale_in": self.scale_in_plan(direction, entry, sl, p, entry_grade["grade"]),
            # v32 頂尖量化分析
            "ofi_state": ofi_state,
            "ofi_value": round(ofi_value, 2),
            "sweep_type": sweep_type,
            "sweep_msg": sweep_msg,
            "div_type": div_type,
            "div_msg": div_msg,
            "wyckoff_type": wyckoff_type,
            "wyckoff_msg": wyckoff_msg,
            "candle_combos": combos,
            "consensus_count": consensus_count,
            "consensus_total": consensus_total,
            "voting_strategies": voting_strategies,
            "flow_state": flow_state,
            "flow_msg": flow_msg,
            # 期望值計算
            "expected_value": self.expected_value(
                win_rate,
                abs(tp2 - entry) / entry * 100 if entry else 0,
                abs(entry - sl) / entry * 100 if entry else 0
            ),
            # v36 新增
            "regime_state": regime_state,
            "regime_label": regime_label,
            # v37 新增
            "timing_state": timing_state,
            "timing_msg": timing_msg,
            "timing_zone": timing_zone,
            "vol_anomalies": vol_anomalies,
            "best_session": best_session,
        }
        # 一句話核心理由
        plan["one_line_thesis"] = self.one_line_thesis(plan, direction)
        # ⭐ v38 五維度評分
        plan["dimensions"] = self.score_dimensions(plan, sig1h, direction, vol_ratio)
        # ⭐ v38 真實勝率（從歷史資料）
        if historical_results:
            try:
                tier_stats = self.real_winrate_stats(
                    historical_results, tier=plan.get("tier"), lookback=50
                )
                if tier_stats:
                    plan["real_win_rate"] = tier_stats["win_rate"]
                    plan["real_ev"] = tier_stats["real_ev"]
                    plan["real_total_count"] = tier_stats["total"]
            except Exception:
                pass
        # ⭐ v37 全局市場健康分
        try:
            btc_health = "HEALTHY" if not isinstance(btc_ticker, Exception) and btc_ticker and abs(float(btc_ticker.get("priceChangePercent", 0))) < 3 else "DANGER"
            plan["market_health"] = self.market_health_score(
                sig1h, vol_ratio, regime_state, fg_val,
                consensus_count, btc_health
            )
        except Exception:
            plan["market_health"] = 50
        # v33 分級系統：不再硬性過濾，而是計算「信號等級」
        # 三個等級的判定（給後續分級推播用）
        ev_score = plan["expected_value"]
        cons_score = consensus_count

        # ⭐ v53 盈虧比硬門檻：TP1 報酬必須 ≥ 止損距 * 1.2，否則直接拒絕
        # 修掉戰績「平均盈利 +0.2% / 平均虧損 -1.93%」的結構性虧損單
        try:
            _entry = plan.get("entry", 0)
            _sl = plan.get("sl", 0)
            _tp1 = plan.get("tp1", 0)
            if _entry and _sl and _tp1:
                _risk = abs(_entry - _sl) / _entry
                _reward1 = abs(_tp1 - _entry) / _entry
                if _risk > 0 and _reward1 / _risk < 1.2:
                    return None, ("TP1 風報比過低 (" + str(round(_reward1 / _risk, 2))
                                  + " < 1.2)，拒絕爛盈虧比單")
        except Exception:
            pass

        # ⭐ v49 職業勝率分級系統
        # 核心原則：任何被推播的信號 → 理論勝率 ≥ 51%
        # 對應的 EV 標準（基於 RR 2.5）：
        #   51% 勝率 → EV ≈ 1.55
        #   56% 勝率 → EV ≈ 1.90
        #   63% 勝率 → EV ≈ 2.40
        #   70% 勝率 → EV ≈ 2.90
        if (ev_score >= 2.4 and cons_score >= 5
            and entry_grade["grade"] in ("S", "A")
            and win_rate >= 65):
            tier = "S"
            tier_label = "💎 S 級 — 夢幻信號 (勝率 ≥ 65%)"
            tier_emoji = "💎"
        elif (ev_score >= 1.9 and cons_score >= 4
              and entry_grade["grade"] in ("S", "A", "B")
              and win_rate >= 58):
            tier = "A"
            tier_label = "🥇 A 級 — 重點推薦 (勝率 ≥ 58%)"
            tier_emoji = "🥇"
        elif (ev_score >= 1.5 and cons_score >= 3
              and entry_grade["grade"] in ("S", "A", "B", "C")
              and win_rate >= 54):
            tier = "B"
            tier_label = "🥈 B 級 — 一般機會 (勝率 ≥ 54%)"
            tier_emoji = "🥈"
        elif (ev_score >= 1.0 and cons_score >= 2
              and entry_grade["grade"] in ("S", "A", "B", "C")
              and win_rate >= 51):
            tier = "C"
            tier_label = "🥉 C 級 — 試水單 (勝率 ≥ 51%)"
            tier_emoji = "🥉"
        else:
            # v49 嚴格：勝率 < 51% 或 EV < 1.0 → 完全拒絕
            return None, ("信號勝率不足 (理論 " + str(win_rate) + "%, EV=" + str(ev_score)
                          + ", 共識=" + str(cons_score) + "/7, 進場=" + entry_grade["grade"] + ")")

        plan["tier"] = tier
        plan["tier_label"] = tier_label
        plan["tier_emoji"] = tier_emoji
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
                    self.fetch_open_interest(session, symbol),   # v63
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
            oi_data = results[8] if not isinstance(results[8], Exception) else None   # v63
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
            if oi_data is not None:
                oi_emoji = "📈" if oi_data > 0 else "📉"
                r += "🔓 OI 5m " + oi_emoji + " `" + ("+" if oi_data > 0 else "") + str(round(oi_data, 2)) + "%`\n"
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
    async def golden_hunter(self, smart_filter=False, min_score=60, historical_results=None):
        # ⭐ v54 每輪入口重置：避免任何 return 路徑殘留上一輪的結構化數據
        self._last_plans = {}
        self._last_plans_ready = False
        # ⭐ v55 整輪掃描開始前，抓一次新聞情緒（全市場共用，避免每幣重複叫 API）
        try:
            self._news_sentiment = await get_news_sentiment()
        except Exception:
            self._news_sentiment = None
        try:
            now = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S UTC")
            candidates = []
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=30, limit_per_host=15),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                fg_result = await self.fetch_fear_greed(session)
                fg_val = fg_result[1] if not isinstance(fg_result, Exception) else 50

                # ⭐ v30 批次掃描：分批處理，避免被限流（每批 10 個幣）
                BATCH_SIZE = 10
                stride = 7
                all_results = []
                total_batches = (len(self.SCAN_POOL) + BATCH_SIZE - 1) // BATCH_SIZE

                for batch_idx in range(total_batches):
                    batch_start = batch_idx * BATCH_SIZE
                    batch_end = min(batch_start + BATCH_SIZE, len(self.SCAN_POOL))
                    batch_symbols = self.SCAN_POOL[batch_start:batch_end]
                    tasks = []
                    for sym in batch_symbols:
                        tasks.append(self.fetch_ohlcv(session, sym, "15m", 100))
                        tasks.append(self.fetch_ohlcv(session, sym, "1h", 200))
                        tasks.append(self.fetch_ohlcv(session, sym, "4h", 150))
                        tasks.append(self.fetch_ticker(session, sym))
                        # ⭐ v38 用快取版本（5 分鐘 TTL，節省 API 配額）
                        tasks.append(self.fetch_funding_cached(session, sym))
                        tasks.append(self.fetch_lsr_cached(session, sym))
                        tasks.append(self.fetch_oi_cached(session, sym))   # v63
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    all_results.extend(batch_results)
                    # v61：批次間隔 0.5→0.3 秒，縮短整輪掃描時間（仍避免被限流）
                    if batch_idx < total_batches - 1:
                        await asyncio.sleep(0.3)

                # ⭐ v30 重試：對失敗的幣種重試一次（核心關鍵幣）
                retry_indices = []
                for i, sym in enumerate(self.SCAN_POOL):
                    df1h_check = all_results[i*stride+1]
                    if isinstance(df1h_check, Exception):
                        retry_indices.append(i)

                if retry_indices:
                    # 重試最多 20 個失敗幣
                    retry_indices = retry_indices[:20]
                    retry_tasks = []
                    for ri in retry_indices:
                        sym = self.SCAN_POOL[ri]
                        retry_tasks.append(self.fetch_ohlcv(session, sym, "15m", 100))
                        retry_tasks.append(self.fetch_ohlcv(session, sym, "1h", 200))
                        retry_tasks.append(self.fetch_ohlcv(session, sym, "4h", 150))
                        retry_tasks.append(self.fetch_ticker(session, sym))
                        retry_tasks.append(self.fetch_funding_cached(session, sym))
                        retry_tasks.append(self.fetch_lsr_cached(session, sym))
                        retry_tasks.append(self.fetch_oi_cached(session, sym))   # v63
                    retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
                    for k, ri in enumerate(retry_indices):
                        for j in range(stride):
                            if not isinstance(retry_results[k*stride+j], Exception):
                                all_results[ri*stride+j] = retry_results[k*stride+j]

                results = all_results
                ok_count = 0
                # ⭐ v41 詳細統計（讓 Railway log 看到每個過濾點）
                reject_stats = {
                    "fetch_fail": 0,
                    "neutral": 0,
                    "low_volume": 0,
                    "pre_filter": 0,
                    "setup_reject": 0,
                    "winrate_reject": 0,   # v63 P0：細分第11關 win_rate/EV 拒絕，獨立追蹤
                    "score_low": 0,
                    "passed": 0,
                }
                stride = 7
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

                # ⭐ v53 大盤閘門：BTC 無趨勢高波動時暫停（山寨最易插針雙殺）
                try:
                    if btc_df_cache is not None and len(btc_df_cache) >= 30:
                        _btc_adx = self.safe_val(self.adx(btc_df_cache), 20)
                        _btc_atr = self.safe_val(self.atr(btc_df_cache))
                        _btc_price = float(btc_df_cache["close"].iloc[-1])
                        _btc_atr_pct = (_btc_atr / _btc_price * 100) if _btc_price else 0
                        if _btc_adx < 15 and _btc_atr_pct > 2:
                            logger.info("🌊 v53 大盤無趨勢高波動 (BTC ADX=%.0f ATR=%.1f%%)，本輪暫停" % (_btc_adx, _btc_atr_pct))
                            self._last_plans_ready = True  # v54: 正常無信號路徑，非異常
                            return ("📡 *黑潮船長 — 大盤閘門*\n"
                                    "━━━━━━━━━━━━━━━\n"
                                    "🌊 BTC 無趨勢高波動，本輪暫停推播\n"
                                    "_避免區間插針雙殺，下輪自動重試_")
                except Exception as _e:
                    logger.error("大盤閘門檢查失敗: " + str(_e))
                for i, sym in enumerate(self.SCAN_POOL):
                    df15m = results[i*stride]
                    df1h = results[i*stride+1]
                    df4h = results[i*stride+2]
                    ticker = results[i*stride+3]
                    funding = results[i*stride+4]
                    ls_ratio = results[i*stride+5]
                    oi_data = results[i*stride+6]   # v63 OI 變化率
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
                    if isinstance(oi_data, Exception):
                        oi_data = None
                    try:
                        current_price = float(ticker.get("lastPrice", 0)) if ticker else float(df1h["close"].iloc[-1])
                        if current_price == 0:
                            continue
                        sig1h = self.generate_signal(df1h, fg_val, current_price)
                        if sig1h["direction_en"] == "NEUTRAL":
                            reject_stats["neutral"] += 1
                            continue
                        vol24 = float(ticker.get("quoteVolume", 0)) / 1e6
                        if vol24 < 25:  # v46 平衡：25 萬是合理流動性
                            reject_stats["low_volume"] += 1
                            continue

                        # ⭐ v40 Pre-filter 放寬：只擋明顯垃圾，其餘交給後續評分判斷
                        # 1. ADX 極低 = 完全無趨勢
                        adx_v = sig1h.get("adx", 0)
                        if adx_v < 12:  # v46 平衡：Pre-filter 較寬，讓更多進入評分
                            reject_stats["pre_filter"] += 1
                            continue
                        # 2. RSI 極端 + MACD 反向（明顯衰竭）
                        rsi_v = sig1h.get("rsi", 50)
                        macd_h = sig1h.get("macd_hist", 0)
                        if sig1h["direction_en"] == "LONG":
                            if rsi_v > 78 and macd_h <= 0:  # v45 職業：RSI 78+MACD轉弱 = 衰竭
                                reject_stats["pre_filter"] += 1
                                continue
                        else:
                            if rsi_v < 22 and macd_h >= 0:  # v45 職業：RSI 22+MACD轉強 = 衰竭
                                reject_stats["pre_filter"] += 1
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
                        timing_emoji, timing_reason = self.entry_timing_legacy(
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
                            symbol=sym,
                            historical_results=historical_results,
                            oi_data=oi_data
                        )
                        if result[0] is None:
                            if isinstance(result[1], str) and "信號勝率不足" in result[1]:
                                reject_stats["winrate_reject"] += 1
                            else:
                                reject_stats["setup_reject"] += 1
                            continue
                        score, plan = result
                        # 套用最低分過濾
                        if score < min_score:
                            reject_stats["score_low"] += 1
                            continue
                        reject_stats["passed"] += 1
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

            # ⭐ v46 即使 candidates 不空，但都被 score 過濾掉時也要保底
            # 不過 candidates 在 v46 還沒被 score 過濾，所以這裡是「全部都因為其他原因 reject」的情況
            
            # ⭐ v43+v46 緊急保底：candidates 為 0 時，從 NEUTRAL 信號中挑「最有方向」的 3 個
            # v57：結構上偏負期望，預設停用，需設 EMERGENCY_SIGNALS=true 才開啟
            if (not candidates and ok_count > 0
                    and os.getenv("EMERGENCY_SIGNALS", "false").lower() == "true"):
                logger.warning("🆘 緊急保底：candidates 為 0，從 NEUTRAL 信號挑選")
                emergency_candidates = []
                stride = 6
                for idx, sym in enumerate(self.SCAN_POOL):
                    try:
                        df1h = results[idx*stride+1]
                        df15m = results[idx*stride]
                        df4h = results[idx*stride+2]
                        ticker = results[idx*stride+3]
                        if isinstance(df1h, Exception) or df1h is None:
                            continue
                        if isinstance(ticker, Exception) or not ticker:
                            continue
                        current_price = float(ticker.get("lastPrice", 0))
                        if current_price == 0:
                            continue
                        # v46.2 修：在迴圈內定義 vol24/chg（避免後面 KeyError）
                        try:
                            vol24 = float(ticker.get("quoteVolume", 0)) / 1e6
                        except Exception:
                            vol24 = 0
                        try:
                            chg = float(ticker.get("priceChangePercent", 0))
                        except Exception:
                            chg = 0
                        # 即使是 NEUTRAL 也產生信號，看 RSI 偏向
                        sig1h = self.generate_signal(df1h, 50, current_price)
                        rsi = sig1h.get("rsi", 50)
                        adx = sig1h.get("adx", 0)

                        # 緊急模式：用 RSI 偏離 50 + ADX 判斷方向
                        # v54 加嚴：原本 ADX 10 / RSI 55-45 太鬆，盤整期硬擠爛單（score 26、勝率 50%）
                        # 改成 ADX>15（有一定趨勢）+ RSI>60 或 <40（真有動能偏向）才出，寧缺勿濫
                        if adx < 15:
                            continue
                        if rsi > 60:
                            direction_emg = "LONG"
                            score_emg = (rsi - 50) * 2 + adx
                        elif rsi < 40:
                            direction_emg = "SHORT"
                            score_emg = (50 - rsi) * 2 + adx
                        else:
                            continue
                        # v54 修復：緊急保底 score 沒有上限（RSI 79 → 110），統一夾到 0~100
                        score_emg = max(0, min(100, score_emg))

                        # 用 ATR 算 SL/TP（v54：TP 改用風險倍數，與正常單的 1.5R 階梯一致，不再 1:1）
                        atr_val = float(self.atr(df1h).iloc[-1])
                        _risk = atr_val * 1.5  # 風險距離
                        if direction_emg == "LONG":
                            entry = current_price
                            sl = current_price - _risk
                            tp1 = current_price + _risk * 1.5
                            tp2 = current_price + _risk * 2.5
                            tp3 = current_price + _risk * 3.5
                            tp4 = current_price + _risk * 5.0
                        else:
                            entry = current_price
                            sl = current_price + _risk
                            tp1 = current_price - _risk * 1.5
                            tp2 = current_price - _risk * 2.5
                            tp3 = current_price - _risk * 3.5
                            tp4 = current_price - _risk * 5.0

                        # v46.1 補完結構：必須跟正常 candidate 一致
                        # 把 sig1h 強制設置 direction_en（雖然原本可能是 NEUTRAL）
                        sig1h_emg = dict(sig1h)
                        sig1h_emg["direction_en"] = direction_emg
                        sig1h_emg["direction"] = "做多 🟢" if direction_emg == "LONG" else "做空 🔴"

                        emergency_candidates.append({
                            "symbol": sym,
                            "sig1h": sig1h_emg,  # ⭐ v46.1 補上 sig1h（顯示時會用）
                            "direction": direction_emg,
                            "score": 26,  # v54：與 plan/dimensions 一致
                            "current_price": current_price,
                            "vol24": vol24,
                            "chg": chg,
                            "funding": 0,
                            "ls_ratio": 1.0,
                            "btc_corr": 0,
                            "expiry_time": None,
                            "expiry_hours": 4,
                            "timing_emoji": "⚠️",
                            "timing_reason": "觀察單",
                            "confluence_zones": [],
                            "whale_signals": [],
                            "pattern": None,
                            "rs_btc": 0,
                            "upside_liq": [],
                            "downside_liq": [],
                            "sig_hash": sym + "_" + direction_emg + "_emg",
                            "mkt_label": "盤整期",
                            "bull_ob": [], "bear_ob": [],
                            "bull_fvg": [], "bear_fvg": [],
                            "bos_dir": None, "bos_level": 0,
                            "quality_score": 26,  # v54：與 score 一致（後續會在 6146 重算覆蓋，此處統一避免混淆）
                            "plan": {
                                "score": 26,  # v54：與 dimensions.total 一致（原本用 score_emg 導致圖表顯示 100、文字顯示 26 的矛盾）
                                "direction": direction_emg,
                                "direction_en": direction_emg,
                                "tier": "C",
                                "tier_label": "⚠️ 觀察單（市場盤整，僅供參考）",
                                "entry_grade": "D",
                                "regime": sig1h_emg.get("regime", ""),
                                "adx": sig1h_emg.get("adx", 0),
                                "consensus_count": 0,
                                "news_vote": False,
                                "entry": self.px_round(entry),
                                "sl": self.px_round(sl),
                                "tp1": self.px_round(tp1),
                                "tp2": self.px_round(tp2),
                                "tp3": self.px_round(tp3),
                                "tp4": self.px_round(tp4),
                                "rr": 1.0,
                                "rr_ratio": 1.0,
                                "position": 2,
                                "win_rate": 50,
                                "strategy_label": "緊急保底（RSI偏向）",
                                "strategy_type": "RSI_BIAS",
                                "one_line_thesis": "⚠️ 市場盤整期觀察單，RSI " + str(int(rsi)) + " · 建議小倉位試水",
                                "consensus_count": 0,
                                "timing_state": "NOW",
                                "timing_msg": "市場盤整，視為觀察單",
                                "dimensions": {"trend": 5, "momentum": 8, "structure": 5,
                                                "volume": 5, "risk": 3, "total": 26},
                                "regime_label": "盤整期",
                                "market_health": 40,
                                "expected_value": 0.3,
                                "symbol": sym,
                                "timeframe": "短線",
                                "order_type": "MARKET",
                                "regime_state": "RANGING",
                                "struct_state": "NEUTRAL",
                                "mtf_grade": "NEUTRAL_MTF",
                                "sweep_type": "NONE",
                                "ofi_state": "NEUTRAL",
                                # v46.1 修：補上原本 strict access 的 keys（避免 KeyError）
                                "rr2": 1.7,
                                "rr4": 4.0,
                                "pros": ["⚠️ 市場盤整期觀察單"],
                                "cons": ["⚠️ 非高品質信號，僅供參考"],
                                "sweep_msg": "",
                                "wyckoff_msg": "",
                                "tier_emoji": "⚠️",
                                "has_confirmation": False,
                                "order_instruction": "盤整期觀察單，建議小倉位試水",
                                "order_type_label": "市價單",
                                "order_valid_hours": 4,
                                "original_position": 2,
                                "sl_label": "ATR 止損",
                                "tp": [],
                                "real_win_rate": None,
                                "timing_zone": round(entry, 6),
                            }
                        })
                    except Exception:
                        continue
                # 取前 3 個分數最高的
                emergency_candidates.sort(key=lambda x: x["score"], reverse=True)
                candidates = emergency_candidates[:3]
                if candidates:
                    logger.warning("✅ 緊急保底找到 " + str(len(candidates)) + " 個 RSI 偏向信號")

            # ⭐ v41 統計日誌（Railway log 可見）
            logger.info("🌊 黑潮掃描統計: ok=" + str(ok_count)
                        + "/" + str(len(self.SCAN_POOL))
                        + " | 通過=" + str(len(candidates))
                        + " | min_score=" + str(min_score)
                        + " | 中立=" + str(reject_stats["neutral"])
                        + " 低流=" + str(reject_stats["low_volume"])
                        + " 預篩=" + str(reject_stats["pre_filter"])
                        + " 閘門=" + str(reject_stats["setup_reject"])
                        + " 勝率關=" + str(reject_stats["winrate_reject"])
                        + " 低分=" + str(reject_stats["score_low"]))

            # ⭐ v41 修：若 ok_count = 0（全部 API 失敗）直接回診斷訊息
            if ok_count == 0:
                self._last_plans_ready = True  # v54: 正常無信號路徑，非異常
                return ("⚠️ *黑潮船長 — 資料抓取失敗*\n"
                        "_" + now + "_\n"
                        "━━━━━━━━━━━━━━━\n\n"
                        "❌ 已嘗試掃描 " + str(len(self.SCAN_POOL)) + " 幣，全部失敗\n\n"
                        "可能原因：\n"
                        "• Binance API 暫時限流\n"
                        "• 網路連線異常\n"
                        "• Railway worker 受限\n\n"
                        "_系統會在下次掃描自動重試_")

            if smart_filter:
                # v33 分級系統：保留所有通過基本門檻的，但分 S/A/B/C 級顯示
                qualified = []
                for c in candidates:
                    p = c["plan"]
                    # 計算綜合品質分數（用於排序）
                    quality_score = p["score"]
                    grade = p.get("entry_grade", "C")
                    grade_bonus = {"S": 20, "A": 12, "B": 6, "C": 0}.get(grade, 0)
                    strat_bonus = {
                        "BREAKOUT_RETEST": 10,
                        "MOMENTUM": 6,
                        "TREND_FOLLOW": 4,
                        "REVERSAL": 2,
                    }.get(p.get("strategy_type", ""), 0)
                    tier_bonus = {"S": 25, "A": 15, "B": 5, "C": 0}.get(p.get("tier", "C"), 0)
                    quality_score += grade_bonus + strat_bonus + tier_bonus
                    c["quality_score"] = quality_score
                    qualified.append(c)
                # ⭐ v41 修：即使 qualified 空也回傳「掃描狀態訊息」而不是 None
                if not qualified:
                    self._last_plans_ready = True  # v54: 正常無信號路徑，非異常
                    return ("📡 *黑潮船長 — 掃描完成*\n"
                            "_" + now + "_\n"
                            "━━━━━━━━━━━━━━━\n\n"
                            "✅ 已掃描 " + str(ok_count) + "/" + str(len(self.SCAN_POOL)) + " 幣種\n"
                            "📊 通過初篩: " + str(len(candidates)) + " 個\n"
                            "🎯 達到推播門檻 (≥" + str(min_score) + "): 0 個\n\n"
                            "_市場暫無高勝率機會，等待下次掃描_")
                # 按綜合品質排序
                qualified.sort(key=lambda x: x.get("quality_score", 0), reverse=True)

                # v33 智能分配：
                # - S 級全部顯示（最多 3 個）
                # - A 級顯示前 2 個
                # - B 級顯示前 2 個
                # - C 級顯示前 1 個
                # 整體最多 6 個（夠多但不淹沒）
                s_tier = [c for c in qualified if c["plan"].get("tier") == "S"][:3]
                a_tier = [c for c in qualified if c["plan"].get("tier") == "A"][:2]
                b_tier = [c for c in qualified if c["plan"].get("tier") == "B"][:2]
                c_tier = [c for c in qualified if c["plan"].get("tier") == "C"][:1]
                candidates = s_tier + a_tier + b_tier + c_tier
                if not candidates:
                    self._last_plans_ready = True  # v54: 正常無信號路徑，非異常
                    return ("📡 *黑潮船長 — 掃描完成*\n"
                            "_" + now + "_\n"
                            "━━━━━━━━━━━━━━━\n\n"
                            "✅ 已掃描 " + str(ok_count) + "/" + str(len(self.SCAN_POOL)) + " 幣種\n"
                            "📊 通過初篩: " + str(len(qualified)) + " 個\n"
                            "🎯 各等級分配後: 0 個\n\n"
                            "_暫無 S/A/B/C 級信號_")

            if not candidates:
                self._last_plans_ready = True  # v54: 正常無信號路徑，非異常
                return ("🎯 *黑潮船長 — " + now + "*\n"
                        "_" + now + "_\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        "📡 已掃描 " + str(ok_count) + "/" + str(len(self.SCAN_POOL)) + " 幣種\n"
                        "📊 通過過濾後無符合條件機會\n"
                        "🎯 當前門檻: ≥ " + str(min_score) + " 分\n\n"
                        "⏳ 可能原因：\n"
                        "• 50 個幣全部 NEUTRAL\n"
                        "• ADX 都 < 12（無趨勢）\n"
                        "• 風報比都 < 1.3\n"
                        "• Squeeze 盤整中\n\n"
                        "_市場暫時方向不明，等下次_")

            candidates.sort(key=lambda x: x["plan"]["score"], reverse=True)

            # ⭐ v54 結構化輸出：把最終 plan 掛到 self._last_plans，供 bot.py 優先取用
            # 消除「文字→regex 反解析」的失真（entry_grade 真值、rr1、真實勝率全部保留）
            self._last_plans = {}
            self._last_plans_ready = False  # v54：標記本輪掛載是否正常完成
            try:
                for _c in candidates:
                    _p = _c["plan"]
                    _sym = _c["symbol"]
                    _dir = _p.get("direction") or _c.get("sig1h", {}).get("direction_en", "LONG")
                    _key = _sym + "|" + _dir
                    self._last_plans[_key] = {
                        "symbol": _sym,
                        "direction": _dir,
                        "score": _p.get("score", 50),
                        "entry": _p.get("entry"),
                        "sl": _p.get("sl"),
                        "tp1": _p.get("tp1", 0),
                        "tp2": _p.get("tp2", 0),
                        "tp3": _p.get("tp3", 0),
                        "tp4": _p.get("tp4", 0),
                        "tier": _p.get("tier", "C"),
                        "entry_grade": _p.get("entry_grade", "C"),  # v54：真值，不再用 tier 頂替
                        "position": _p.get("position", 5),
                        "win_rate": _p.get("win_rate", 50),
                        "real_win_rate": _p.get("real_win_rate"),
                        "rr_ratio": _p.get("rr1", 0),  # v54：直接給 rr1
                        "rr1": _p.get("rr1", 0),
                        "timing_state": _p.get("timing_state", "NOW"),
                        "timeframe": _p.get("timeframe", "短線"),
                        "order_type": _p.get("order_type", "MARKET"),
                        "regime": _p.get("regime", ""),
                        "adx": _p.get("adx", 0),
                        "consensus_count": _p.get("consensus_count", 0),
                        "news_vote": _p.get("news_vote", False),
                    }
                self._last_plans_ready = True  # 掛載正常完成（即使 candidates 空，也是正常的「無機會」）
            except Exception as _e:
                logger.error("v54 結構化掛載失敗: " + str(_e))
                self._last_plans = {}
                self._last_plans_ready = False

            r = "🌊 *黑潮船長｜分級機會清單*\n"
            r += "_" + now + "_\n"
            r += "━━━━━━━━━━━━━━━\n"

            # ⭐ v33 分級統計
            s_count = sum(1 for c in candidates if c["plan"].get("tier") == "S")
            a_count = sum(1 for c in candidates if c["plan"].get("tier") == "A")
            b_count = sum(1 for c in candidates if c["plan"].get("tier") == "B")
            c_count = sum(1 for c in candidates if c["plan"].get("tier") == "C")

            r += "📡 已掃描 " + str(len(self.SCAN_POOL)) + " 幣 | 共 *" + str(len(candidates)) + "* 個機會\n"
            tier_summary = []
            if s_count > 0: tier_summary.append("💎 S×" + str(s_count))
            if a_count > 0: tier_summary.append("🥇 A×" + str(a_count))
            if b_count > 0: tier_summary.append("🥈 B×" + str(b_count))
            if c_count > 0: tier_summary.append("🥉 C×" + str(c_count))
            if tier_summary:
                r += "📊 " + " | ".join(tier_summary) + "\n"

            # ⭐ v37 Alt 季 / BTC 季提示
            try:
                if btc_df_cache is not None:
                    # 取 ETH 數據
                    eth_idx = None
                    for idx_e, sym_e in enumerate(self.SCAN_POOL):
                        if sym_e == "ETH/USDT":
                            eth_idx = idx_e
                            break
                    eth_df = results[eth_idx*stride+1] if eth_idx is not None else None
                    if not isinstance(eth_df, Exception) and eth_df is not None:
                        alt_state, alt_label = self.alt_season_indicator(btc_df_cache, eth_df)
                        if alt_state in ("ALT_SEASON", "BTC_SEASON"):
                            emoji = "🚀" if alt_state == "ALT_SEASON" else "👑"
                            r += emoji + " " + alt_label + "\n"
            except Exception:
                pass

            # 下次掃描預告
            next_scan = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%H:%M UTC")
            r += "⏳ 下次掃描：" + next_scan + "\n"

            # ⭐ v33 行動建議
            if candidates:
                top = candidates[0]
                top_sym = top["symbol"].replace("/USDT", "")
                top_dir = "做多" if top["sig1h"]["direction_en"] == "LONG" else "做空"
                top_tier = top["plan"].get("tier", "C")
                expected_pct = abs(top["plan"]["tp2"] - top["plan"]["entry"]) / top["plan"]["entry"] * 100
                r += "\n💡 *最佳機會*：" + top["plan"].get("tier_emoji", "") + " " + top_sym + " " + top_dir
                r += " (+" + str(round(expected_pct, 1)) + "% 目標)\n"

                # v33 使用指南
                if top_tier == "S":
                    r += "🎯 *S 級可正常倉跟單，這是稀有的高品質機會*\n"
                elif top_tier == "A":
                    r += "🎯 *A 級建議半倉跟單*\n"
                elif top_tier == "B":
                    r += "🎯 *B 級建議 1/3 倉試水*\n"
                else:
                    r += "🎯 *C 級僅供觀察，跟單需謹慎*\n"
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

            # ⭐ v55 新聞分析（零權重觀察模式：顯示但不影響開單）
            try:
                _news = await get_news_sentiment()
                if _news:
                    r += format_news_section(_news)
            except Exception as _ne:
                logger.error("新聞區塊顯示失敗: " + str(_ne))

            r += "\n"

            # ⭐ v40.2 修復：按 tier 顯示多個信號（最多 6 個）
            # S 級全部顯示、A 級最多 2 個、B 級最多 2 個、C 級最多 1 個
            display_list = []
            s_seen = a_seen = b_seen = c_seen = 0
            for cc in candidates:
                tt = cc["plan"].get("tier", "C")
                if tt == "S" and s_seen < 3:
                    display_list.append(cc); s_seen += 1
                elif tt == "A" and a_seen < 2:
                    display_list.append(cc); a_seen += 1
                elif tt == "B" and b_seen < 2:
                    display_list.append(cc); b_seen += 1
                elif tt == "C" and c_seen < 1:
                    display_list.append(cc); c_seen += 1
                if len(display_list) >= 6:
                    break

            for rank, c in enumerate(display_list, 1):
                sig = c["sig1h"]
                p = c["plan"]
                direction_zh = "做多" if sig["direction_en"] == "LONG" else "做空"
                direction_emoji = "🟢" if sig["direction_en"] == "LONG" else "🔴"
                medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")

                # === 標題區 ===
                r += medal + " *" + c["symbol"].replace("/USDT", "") + " " + direction_zh + " " + direction_emoji + "*\n"

                # === 變數準備 ===
                grade = p.get("entry_grade", "C")
                tier = p.get("tier", "C")
                tier_label = p.get("tier_label", "")
                tier_emoji = p.get("tier_emoji", "")

                # ═══════════ 第一層：決策重點 ═══════════
                r += "\n═══════════════\n"
                r += tier_label + "\n"

                # 進場時機
                timing_state = p.get("timing_state", "NOW")
                if timing_state == "WAIT_PULLBACK":
                    r += "⏰ *等回踩* " + str(p.get("timing_zone", p["entry"])) + "\n"
                elif timing_state == "WAIT_BREAKOUT":
                    r += "⏰ *等突破* " + str(p["entry"]) + "\n"
                else:
                    r += "✅ *現在可進場*\n"

                # 核心價位
                r += "🎯 進場 `" + str(p["entry"]) + "` · 止損 `" + str(p["sl"]) + "`\n"
                # TP（三段 40/35/25：價格 ｜漲幅% ｜分批平倉%，一行一個）
                tp_parts = []
                _entry_v = p.get("entry", 0) or 0
                _dir = 1 if p.get("direction", "LONG") == "LONG" else -1
                _tp_close = {1: 40, 2: 35, 3: 25}
                for n in (1, 2, 3):
                    tp_v = p.get("tp" + str(n), 0)
                    if not tp_v:
                        continue
                    line = "TP" + str(n) + "：" + str(tp_v)
                    if _entry_v:
                        _pct = (tp_v - _entry_v) / _entry_v * 100 * _dir
                        line += " ｜+" + str(round(_pct, 1)) + "%"
                    line += " ｜平" + str(_tp_close[n]) + "%"
                    tp_parts.append(line)
                if tp_parts:
                    r += "🏆 *分批止盈*\n" + "\n".join(tp_parts) + "\n"

                # 風報比 + 倉位 + 勝率
                # v53 修正：plan 存的是 rr1，舊代碼找 rr_ratio/rr 找不到 → 顯示 1:0
                rr = p.get("rr1", p.get("rr_ratio", p.get("rr", 0)))
                pos = p.get("position", 5)
                win_rate = p.get("win_rate", 0)
                real_wr = p.get("real_win_rate", None)
                if real_wr is not None:
                    r += "💰 風報比 *1:" + str(rr) + "* · 倉位 *" + str(pos) + "%* · 實際勝率 *" + str(real_wr) + "%*\n"
                else:
                    r += "💰 風報比 *1:" + str(rr) + "* · 倉位 *" + str(pos) + "%* · 預估勝率 *" + str(win_rate) + "%*\n"

                # S/A 級多顯示 1 行重要詳情；B/C 略過後續詳細
                if tier in ("S", "A"):
                    extras = []
                    if p.get("sweep_msg"):
                        extras.append("💧 " + p["sweep_msg"][:25])
                    elif p.get("wyckoff_msg"):
                        extras.append("🏛 " + p["wyckoff_msg"][:25])
                    if p.get("strategy_label"):
                        extras.append("🎯 " + p["strategy_label"][:20])
                    if extras:
                        r += "  ·  ".join(extras[:2]) + "\n"

                # B/C 級直接跳到下一個（不顯示詳細分析鏈）
                if tier in ("B", "C"):
                    continue

                # ─────────── 第二層：細節 ───────────
                r += "─────────────\n"
                r += "_" + direction_zh + " · " + p["timeframe"] + " · 預估勝率 " + str(p["win_rate"]) + "%_\n"

                # 一句話核心理由
                thesis = p.get("one_line_thesis", "")
                if thesis:
                    r += "_" + thesis + "_\n"

                # 五維度評分
                dims = p.get("dimensions", {})
                if dims:
                    def bar(v, max_v=20):
                        filled = int(v / max_v * 5)
                        return "█" * filled + "░" * (5 - filled)
                    r += "📊 *" + str(dims.get("total", 50)) + "/100*  趨勢" + bar(dims.get("trend", 10))
                    r += " 動能" + bar(dims.get("momentum", 10)) + " 結構" + bar(dims.get("structure", 10))
                    r += " 量能" + bar(dims.get("volume", 10)) + " 風險" + bar(dims.get("risk", 10)) + "\n"

                r += "\n"

                # === 為什麼推薦（最重要）===
                r += "💭 *分析師說明*\n"
                if p.get("pros"):
                    top_pros = p["pros"][:4]
                    for pro in top_pros:
                        r += "  " + pro + "\n"
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
                if sig["direction_en"] == "LONG":
                    sl_pct = (p["entry"] - p["sl"]) / p["entry"] * 100
                else:
                    sl_pct = (p["sl"] - p["entry"]) / p["entry"] * 100
                r += "  • 止損幅度：`" + str(round(sl_pct, 2)) + "%`\n"
                r += "\n"

                # === 分批止盈計劃（權重 40/35/25）===
                r += "🎯 *分批止盈計劃*\n"
                if sig["direction_en"] == "LONG":
                    tp1_pct = (p["tp1"] - p["entry"]) / p["entry"] * 100
                    tp2_pct = (p["tp2"] - p["entry"]) / p["entry"] * 100
                    tp3_pct = (p["tp3"] - p["entry"]) / p["entry"] * 100
                else:
                    tp1_pct = (p["entry"] - p["tp1"]) / p["entry"] * 100
                    tp2_pct = (p["entry"] - p["tp2"]) / p["entry"] * 100
                    tp3_pct = (p["entry"] - p["tp3"]) / p["entry"] * 100
                r += "  ① `" + str(p["tp1"]) + "` (+`" + str(round(tp1_pct, 2)) + "%`) 平 40% _保本出場_\n"
                r += "  ② `" + str(p["tp2"]) + "` (+`" + str(round(tp2_pct, 2)) + "%`) 平 35%\n"
                r += "  ③ `" + str(p["tp3"]) + "` (+`" + str(round(tp3_pct, 2)) + "%`) 平剩餘 25% _大勝下車_\n"
                r += "\n"

                # === 倉位建議 ===
                r += "💼 *倉位建議*\n"
                r += "  建議使用資金的 *" + str(p["position"]) + "%*"
                orig_pos = p.get("original_position", p["position"])
                if p["position"] < orig_pos:
                    r += " _(根據" + grade + "級調整)_"
                r += "\n"
                r += "  風報比 1:" + str(p["rr2"]) + " 至 1:" + str(p["rr3"]) + "\n"

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
            import traceback
            err_type = type(e).__name__
            err_msg = str(e)
            err_trace = traceback.format_exc()
            # log 完整 traceback 到 Railway
            try:
                logger.error("🔥 golden_hunter 崩潰: " + err_type + ": " + err_msg + "\n" + err_trace)
            except Exception:
                pass
            return ("❌ *黑潮船長執行錯誤*\n"
                    "━━━━━━━━━━━━━━━\n"
                    "錯誤類型: `" + err_type + "`\n"
                    "錯誤訊息: `" + err_msg + "`\n\n"
                    "_詳細追蹤已記錄到 Railway log_\n"
                    "_請截圖回報給開發者_")

    async def detect_movers(self):
        """市場異動掃描 — v56 視覺強化 + 描述性判讀"""
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

            avg_chg = sum(d["chg"] for d in data) / len(data)
            gainers_count = sum(1 for d in data if d["chg"] > 0)
            losers_count = sum(1 for d in data if d["chg"] < 0)
            vol_surge_count = sum(1 for d in data if d["vol_ratio"] > 1.5)
            total = len(data)

            def _fp(p):
                if p >= 100:
                    return f"{p:,.2f}"
                if p >= 1:
                    return f"{p:.3f}"
                return f"{p:.5f}"

            mood = "🟢" if avg_chg > 0.3 else ("🔴" if avg_chg < -0.3 else "⚪")
            r = "📊 *24H 市場異動掃描*\n`" + now + "`\n━━━━━━━━━━━━━━━\n"
            r += mood + " 平均 " + ("%+.2f" % avg_chg) + "%　掃描 `" + str(total) + "/" + str(len(self.SCAN_POOL)) + "`\n\n"

            r += "*🚀 漲幅榜*\n"
            for i, c in enumerate(top_gainers, 1):
                a = "▲" if c["chg"] >= 0 else "▼"
                vr = " 🔥`" + str(round(c["vol_ratio"], 1)) + "x`" if c["vol_ratio"] > 1.5 else ""
                rw = " ⚠️過熱" if c["rsi"] > 75 else ""
                r += "`" + str(i) + ".` " + c["symbol"] + " " + _fp(c["price"]) + " " + a + "`" + ("%+.2f" % c["chg"]) + "%`" + vr + rw + "\n"

            r += "\n*📉 跌幅榜*\n"
            for i, c in enumerate(top_losers, 1):
                a = "▲" if c["chg"] >= 0 else "▼"
                vr = " 🔥`" + str(round(c["vol_ratio"], 1)) + "x`" if c["vol_ratio"] > 1.5 else ""
                rw = " ⚠️超賣" if c["rsi"] < 25 else ""
                r += "`" + str(i) + ".` " + c["symbol"] + " " + _fp(c["price"]) + " " + a + "`" + ("%+.2f" % c["chg"]) + "%`" + vr + rw + "\n"

            if top_vol_surge:
                r += "\n*🔥 量能爆發*\n"
                for c in top_vol_surge:
                    a = "▲" if c["chg"] >= 0 else "▼"
                    r += "• " + c["symbol"] + " " + a + "`" + ("%+.1f" % c["chg"]) + "%` 量`" + str(round(c["vol_ratio"], 1)) + "x` `$" + str(round(c["vol"], 0)) + "M`\n"

            r += "\n*💵 成交量*\n"
            for c in top_volume:
                a = "▲" if c["chg"] >= 0 else "▼"
                r += "• " + c["symbol"] + " $" + str(round(c["vol"], 0)) + "M " + a + "`" + ("%+.1f" % c["chg"]) + "%`\n"

            up_ratio = gainers_count / total if total else 0
            blocks = round(up_ratio * 10)
            breadth = "🟩" * blocks + "🟥" * (10 - blocks)
            r += "\n━━━━━━━━━━━━━━━\n📊 *市場概況*\n"
            r += "• 漲跌寬度 " + breadth + "\n"
            r += "• 上漲/下跌 `" + str(gainers_count) + " / " + str(losers_count) + "`（漲占 " + str(round(up_ratio * 100)) + "%）\n"
            r += "• 平均漲跌 `" + ("%+.2f" % avg_chg) + "%`\n"
            r += "• 異常爆量 " + str(vol_surge_count) + " 檔\n\n"

            r += "💡 *市場狀態判讀*\n"
            if avg_chg > 3 and vol_surge_count >= 5:
                r += "🚀 強勢擴散：多數幣種上漲且量能放大，資金活躍。"
            elif avg_chg > 1.5 and gainers_count > losers_count * 2:
                r += "📈 偏多：上漲家數明顯多於下跌。"
            elif avg_chg < -3 and vol_surge_count >= 5:
                r += "💥 急跌：多數幣種重挫且量能放大，情緒偏恐慌。"
            elif avg_chg < -1.5 and losers_count > gainers_count * 2:
                r += "📉 偏弱：下跌家數明顯多於上漲，技術面轉弱。"
            elif vol_surge_count >= 8:
                r += "⚡ 異動：多幣種量能異常，可能有事件驅動，留意新聞。"
            elif abs(avg_chg) < 0.5:
                r += "↔️ 盤整：漲跌幅度小，方向未明。"
            else:
                r += "⚪ 分歧：漲跌互現，以個別輪動為主。"
            r += "\n\n_※ 以上為公開市場數據摘要，僅供參考，非投資建議。_"
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
            r += "💡 *市場狀態總結*\n"
            if bull_score >= 4 and bear_score <= 1:
                r += "🟢 多方主導：多項指標偏多，市場情緒積極、資金活躍。"
            elif bull_score >= 3 and bull_score > bear_score:
                r += "📗 偏多：多數指標偏多，惟需留意 BTC 走勢是否轉弱。"
            elif bear_score >= 4 and bull_score <= 1:
                r += "🔴 空方主導：多項指標偏空，市場情緒疲弱。"
            elif bear_score >= 3 and bear_score > bull_score:
                r += "📕 偏空：指標偏空，技術面轉弱、關鍵支撐承壓。"
            elif fgv <= 25:
                r += "🔵 極度恐懼：情緒處於恐慌區間（歷史上常見於階段性低點附近，但不保證）。"
            elif fgv >= 75:
                r += "🟠 極度貪婪：情緒過熱（歷史上常見於階段性高點附近，回調風險偏高）。"
            else:
                r += "⚪ 中性盤整：多空分歧，方向尚未明確。"
            r += "\n\n_※ 以上為市場數據摘要，僅供參考，非投資建議。_"

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
            r += "💡 *趨勢總結*\n"
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
                r += "🟢 趨勢偏多：多頭家數明顯佔優。\n"
                if best_long:
                    r += "　趨勢最強：*" + best_long["symbol"] + "*（ADX " + str(best_long["adx"]) + "）"
            elif bear_pct > 60:
                r += "🔴 趨勢偏空：空頭家數明顯佔優。\n"
                if best_short:
                    r += "　跌勢最強：*" + best_short["symbol"] + "*（ADX " + str(best_short["adx"]) + "）"
            elif len(ranging) > (len(strong_bull) + len(strong_bear) + len(bull) + len(bear)):
                r += "↔️ 多數標的處於盤整，方向未明。"
            else:
                r += "⚪ 多空分歧，趨勢不明確。"
                if best_long:
                    r += "\n　最強多方：*" + best_long["symbol"] + "*"
                if best_short:
                    r += "　最強空方：*" + best_short["symbol"] + "*"
            r += "\n\n_※ 以上為趨勢數據摘要，僅供參考，非投資建議。_"
            return r
        except Exception as e:
            return "❌ 失敗：" + str(e)

