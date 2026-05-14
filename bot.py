import asyncio
import logging
import os
import json
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from analyzer import CryptoAnalyzer
try:
    from chart import (plot_signal_chart, plot_simple_chart,
                         plot_movers_chart, plot_momentum_chart,
                         plot_trend_distribution, plot_dual_chart)
    CHART_ENABLED = True
except Exception as _e:
    CHART_ENABLED = False
    logging.warning("Chart 模組載入失敗: " + str(_e))

# ⭐ 推播間隔：5 分鐘
PUSH_INTERVAL_MIN = 5

# ⭐ BingX 連結產生器
def bingx_trade_url(symbol, direction):
    """
    產生 BingX 交易頁面深層連結
    symbol: BTC/USDT 格式
    direction: LONG / SHORT
    """
    pair = symbol.replace("/", "-")  # BingX 用 BTC-USDT
    # BingX 永續合約交易頁
    base = "https://bingx.com/zh-tw/perpetual/" + pair
    return base

def bingx_swap_url(symbol):
    """BingX 永續合約頁面"""
    pair = symbol.replace("/", "-")
    return "https://bingx.com/zh-tw/perpetual/" + pair

def bingx_spot_url(symbol):
    """BingX 現貨頁面"""
    pair = symbol.replace("/", "_")
    return "https://bingx.com/zh-tw/spot/" + pair


# ⭐ TG 公開頻道 ID（自動推播所有信息）
# 預設頻道：@KuroshioSignal（https://t.me/KuroshioSignal）
import os as _os
TG_CHANNEL_ID = _os.environ.get("TG_CHANNEL_ID", "@KuroshioSignal")

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

USER_STATES = {}
USER_FAVORITES = {}
PUSH_HISTORY = {}
HUNTER_WATCHERS = set()
# ⭐ 推播去重：{sig_hash: timestamp}，30 分鐘內相同信號不重推
RECENT_PUSHED = {}
PUSH_DEDUP_MINUTES = 30
# ⭐ 自訂定時推播：{chat_id: {"hours": [8, 12, 20], "types": ["sentiment", "trend", "movers", "events"]}}
USER_DAILY_SCHEDULE = {}
# ⭐ 信號追蹤：{signal_id: {symbol, direction, entry, sl, tp1, tp2, tp3, tp4, status, created}}
SIGNAL_TRACKER = {}
# ⭐ 用戶資金設定：{chat_id: capital}
USER_CAPITAL = {}
# ⭐ 信號追蹤系統：{symbol: signal_data}
# signal_data: {direction, entry, sl, tp1-tp4, watchers, tp_hit, status, created, expires, score, timeframe}
ACTIVE_SIGNALS = {}
# ⭐ 信號歷史（用於統計勝率）
SIGNAL_RESULTS = []
# ⭐ 連虧紀錄：{symbol: [iso_timestamp...]}
SYMBOL_LOSSES = {}

DATA_FILE = "/tmp/bot_data.json"

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]


def load_data():
    global USER_FAVORITES, PUSH_HISTORY, HUNTER_WATCHERS, USER_DAILY_SCHEDULE, SIGNAL_TRACKER, USER_CAPITAL, ACTIVE_SIGNALS, SIGNAL_RESULTS, SYMBOL_LOSSES
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            USER_FAVORITES = {int(k): v for k, v in data.get("favorites", {}).items()}
            PUSH_HISTORY = {int(k): v for k, v in data.get("history", {}).items()}
            HUNTER_WATCHERS = set(int(x) for x in data.get("watchers", []))
            schedule_raw = data.get("daily_schedule", {})
            USER_DAILY_SCHEDULE = {int(k): v for k, v in schedule_raw.items()}
            SIGNAL_TRACKER = data.get("signals", {})
            USER_CAPITAL = {int(k): v for k, v in data.get("capital", {}).items()}
            ACTIVE_SIGNALS.update(data.get("active_signals", {}))
            SIGNAL_RESULTS.extend(data.get("signal_results", []))
            SYMBOL_LOSSES.update(data.get("symbol_losses", {}))
            logger.info("載入：自選 " + str(len(USER_FAVORITES)) + " 戶，獵手 " + str(len(HUNTER_WATCHERS)) + " 戶，簡報 " + str(len(USER_DAILY_SCHEDULE)) + " 戶，追蹤中 " + str(len(ACTIVE_SIGNALS)) + " 個信號")
    except Exception as e:
        logger.info("初次啟動: " + str(e))


def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "favorites": {str(k): v for k, v in USER_FAVORITES.items()},
                "history": {str(k): v for k, v in PUSH_HISTORY.items()},
                "watchers": list(HUNTER_WATCHERS),
                "daily_schedule": {str(k): v for k, v in USER_DAILY_SCHEDULE.items()},
                "signals": SIGNAL_TRACKER,
                "capital": {str(k): v for k, v in USER_CAPITAL.items()},
                "active_signals": ACTIVE_SIGNALS,
                "signal_results": SIGNAL_RESULTS[-50:],
                "symbol_losses": SYMBOL_LOSSES
            }, f)
    except Exception as e:
        logger.error("儲存失敗: " + str(e))


def main_menu():
    return InlineKeyboardMarkup([
        # 第一排：核心功能（最常用）
        [InlineKeyboardButton("🌊 黑潮船長 (即時掃描)", callback_data="hunter")],
        [InlineKeyboardButton("⭐ 今日為你挑選 TOP 1", callback_data="todays_pick")],
        # 第二排：自動化
        [InlineKeyboardButton("🔔 黑潮船長推播 ON", callback_data="auto_on"),
         InlineKeyboardButton("🔕 OFF", callback_data="auto_off")],
        [InlineKeyboardButton("📅 自訂定時推播", callback_data="schedule_menu")],
        # 第三排：信號管理
        [InlineKeyboardButton("📡 追蹤中信號", callback_data="active_signals"),
         InlineKeyboardButton("📊 歷史戰績", callback_data="stats")],
        # 第四排：個別分析
        [InlineKeyboardButton("⚡ 即時動能", callback_data="momentum"),
         InlineKeyboardButton("📊 異動掃描", callback_data="movers")],
        [InlineKeyboardButton("🌐 市場情緒", callback_data="sentiment"),
         InlineKeyboardButton("📰 加密快訊", callback_data="news_only")],
        [InlineKeyboardButton("🔭 趨勢總覽", callback_data="trend"),
         InlineKeyboardButton("📊 多週期分析", callback_data="multi_tf")],
        # 第五排：快速幣種
        [InlineKeyboardButton("BTC", callback_data="a_BTC"),
         InlineKeyboardButton("ETH", callback_data="a_ETH"),
         InlineKeyboardButton("SOL", callback_data="a_SOL"),
         InlineKeyboardButton("BNB", callback_data="a_BNB")],
        # 第六排：工具
        [InlineKeyboardButton("⭐ 我的自選", callback_data="favorites"),
         InlineKeyboardButton("🔍 自訂幣種", callback_data="custom")],
        [InlineKeyboardButton("💼 倉位計算", callback_data="position_calc"),
         InlineKeyboardButton("📜 推播歷史", callback_data="history")],
    ])


def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主選單", callback_data="home")]])


def fav_menu(chat_id):
    favs = USER_FAVORITES.get(chat_id, [])
    buttons = []
    if favs:
        for sym in favs[:8]:
            row = [
                InlineKeyboardButton("📊 " + sym, callback_data="a_" + sym),
                InlineKeyboardButton("❌", callback_data="favrm_" + sym)
            ]
            buttons.append(row)
    buttons.append([InlineKeyboardButton("➕ 新增自選", callback_data="favadd")])
    buttons.append([InlineKeyboardButton("🏠 返回主選單", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🌊 *黑潮策略 — 加密貨幣 AI 分析助理*\n"
        "━━━━━━━━━━━━━━━\n"
        "我會 24 小時幫你掃描市場，找出 *高勝率交易機會*\n"
        "全程追蹤每筆信號，即時通知關鍵價位\n\n"
        "*🎯 v23 升級*\n"
        "• 多週期嚴格共振過濾\n"
        "• 紐約倫敦時段加權\n"
        "• 黑天鵝事件自動暫停\n"
        "• 反指標訊號自動拒絕\n"
        "• 異常波動全面保護\n\n"
        "_⚠️ 加密貨幣風險極高，建議僅供參考_"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")


async def send_chart_with_caption(ctx, chat_id, df, symbol, timeframe, direction,
                                    entry, sl, tp1, tp2, tp3, tp4,
                                    support_levels, resistance_levels,
                                    caption, title_suffix=""):
    """發送 K 線圖 + 說明"""
    if not CHART_ENABLED or df is None:
        # 降級：純文字推播
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
        except Exception as e:
            logger.error("純文字推播失敗 " + str(chat_id) + ": " + str(e))
        return
    try:
        buf = plot_signal_chart(
            df, symbol, timeframe, direction,
            entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, tp4=tp4,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            title_suffix=title_suffix
        )
        # Telegram caption 上限 1024 字元
        short_caption = caption if len(caption) <= 1000 else caption[:1000] + "..."
        await ctx.bot.send_photo(
            chat_id=chat_id, photo=buf,
            caption=short_caption, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("附圖推播失敗: " + str(e))
        # 降級
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
        except Exception:
            pass


async def send_simple_chart(ctx, chat_id, df, symbol, timeframe, caption=""):
    """發送無交易計劃的 K 線圖"""
    if not CHART_ENABLED or df is None:
        if caption:
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            except Exception:
                pass
        return
    try:
        buf = plot_simple_chart(df, symbol, timeframe)
        short_caption = caption if len(caption) <= 1000 else caption[:1000] + "..."
        await ctx.bot.send_photo(
            chat_id=chat_id, photo=buf,
            caption=short_caption, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("簡圖推播失敗: " + str(e))


async def send_chart_buf(ctx, chat_id, buf, caption=""):
    """通用：發送圖表 + caption"""
    if not buf:
        if caption:
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            except Exception:
                pass
        return
    try:
        short_caption = caption if len(caption) <= 1000 else caption[:1000] + "..."
        await ctx.bot.send_photo(
            chat_id=chat_id, photo=buf,
            caption=short_caption, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("圖表推播失敗: " + str(e))
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
        except Exception:
            pass


async def safe_run(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return "⏱ 處理超時"
    except Exception as e:
        return "❌ 錯誤：" + str(e)


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
    result = await safe_run(analyzer.full_analysis(symbol), timeout=30)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_hunter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 專業黑潮船長掃描中...")
    result = await safe_run(analyzer.golden_hunter(), timeout=90)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_movers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 掃描異動...")
    result = await safe_run(analyzer.detect_movers(), timeout=30)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_kline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    msg = await update.message.reply_text("⏳ 多週期分析中...")
    result = await safe_run(analyzer.kline_sr_analysis(symbol), timeout=30)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_trend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbols = [s.upper() for s in ctx.args] if ctx.args else DEFAULT_SYMBOLS
    msg = await update.message.reply_text("⏳ 掃描趨勢...")
    result = await safe_run(analyzer.trend_watch(symbols), timeout=40)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_sentiment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 分析市場情緒...")
    result = await safe_run(analyzer.get_market_sentiment(), timeout=20)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_testpush(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 測試推播中...")
    result = await safe_run(analyzer.golden_hunter(smart_filter=False), timeout=90)
    await msg.edit_text("🧪 *測試推播*\n\n" + result, parse_mode="Markdown")


def show_history(chat_id):
    history = PUSH_HISTORY.get(chat_id, [])
    if not history:
        return "📜 *推播歷史*\n\n尚無記錄"
    r = "📜 *推播歷史 (最近 10 筆)*\n"
    r += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, h in enumerate(reversed(history[-10:]), 1):
        try:
            dt = datetime.fromisoformat(h["time"])
            now = datetime.now(timezone.utc)
            diff = now - dt
            if diff.total_seconds() < 3600:
                ago = str(int(diff.total_seconds() / 60)) + "分鐘前"
            elif diff.total_seconds() < 86400:
                ago = str(int(diff.total_seconds() / 3600)) + "小時前"
            else:
                ago = str(int(diff.total_seconds() / 86400)) + "天前"
        except Exception:
            ago = "—"
        r += str(i) + ". *" + h["symbol"] + "* " + h.get("direction", "") + "\n"
        r += "   信號價 `" + str(h.get("price", "?")) + "` | 信心 `" + str(h.get("confidence", "?")) + "`\n"
        r += "   _" + ago + "_\n\n"
    return r


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    chat_id = q.message.chat_id

    if d.startswith("a_"):
        symbol_short = d[2:]
        sym_full = symbol_short + "/USDT" if "/" not in symbol_short else symbol_short
        await q.edit_message_text("⏳ 分析 " + sym_full + "...")
        result = await safe_run(analyzer.full_analysis(sym_full), timeout=30)
        keyboard = [[InlineKeyboardButton("⭐ 加入自選", callback_data="favadd_" + sym_full),
                     InlineKeyboardButton("🏠 主選單", callback_data="home")]]
        # 先發文字
        await q.edit_message_text(result, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))
        # 附 K 線圖
        if CHART_ENABLED:
            try:
                import aiohttp as _aiohttp
                async with _aiohttp.ClientSession() as session:
                    df = await analyzer.fetch_ohlcv(session, sym_full, "1h", 100)
                    if df is not None:
                        sw_res, sw_sup = analyzer.swing_sr(df)
                        await send_simple_chart(
                            ctx, chat_id, df, sym_full, "1H",
                            caption="📊 *" + symbol_short + "* K 線（1H）"
                        )
            except Exception as e:
                logger.error("分析圖失敗 " + sym_full + ": " + str(e))

    elif d == "hunter":
        await q.edit_message_text("🎯 專業黑潮船長掃描中...\n(掃描 30 幣種約 20-30 秒)")
        result = await safe_run(analyzer.golden_hunter(), timeout=90)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 為 TOP 3 信號附 K 線圖
        if CHART_ENABLED and result and "📡" in result:
            try:
                import re as _re_re
                import aiohttp as _aiohttp_chart
                # 從結果解析 TOP 3 候選
                parsed = parse_hunter_signals(result)
                if parsed:
                    async with _aiohttp_chart.ClientSession() as session:
                        for sig in parsed[:3]:
                            sym = sig.get("symbol", "")
                            try:
                                df = await analyzer.fetch_ohlcv(session, sym, "1h", 100)
                                if df is not None:
                                    sw_res, sw_sup = analyzer.swing_sr(df)
                                    sym_short = sym.replace("/USDT", "")
                                    grade = sig.get("entry_grade", "")
                                    direction = sig.get("direction", "LONG")
                                    title_suffix = grade + " GRADE" if grade else ""
                                    caption = (
                                        "📊 *" + sym_short + " " + ("Long" if direction == "LONG" else "Short") + "*\n"
                                        "Entry: `" + str(sig.get("entry", 0)) + "` | SL: `" + str(sig.get("sl", 0)) + "`"
                                    )
                                    await send_chart_with_caption(
                                        ctx, chat_id, df, sym, "1H", direction,
                                        entry=sig.get("entry"), sl=sig.get("sl"),
                                        tp1=sig.get("tp1"), tp2=sig.get("tp2"),
                                        tp3=sig.get("tp3"), tp4=sig.get("tp4"),
                                        support_levels=sw_sup[:2] if sw_sup else [],
                                        resistance_levels=sw_res[:2] if sw_res else [],
                                        caption=caption, title_suffix=title_suffix
                                    )
                                    await asyncio.sleep(0.3)
                            except Exception:
                                continue
            except Exception as e:
                logger.error("hunter 附圖失敗: " + str(e))

    elif d == "todays_pick":
        await q.edit_message_text("⭐ 為你挑選今日最佳機會中...")
        # 只要最高分的那一個
        result = await safe_run(analyzer.golden_hunter(min_score=70), timeout=90)
        if result and "🥇" in result:
            # 截取第一名部分
            try:
                idx_start = result.find("🥇")
                idx_end = result.find("🥈")
                if idx_end == -1:
                    idx_end = result.find("━━━━━━━━━━━━━━━━━━━━\n💡")
                if idx_end == -1:
                    idx_end = len(result)
                pick = "⭐ *今日為你挑選 — TOP 1*\n━━━━━━━━━━━━━━━━━━━━\n\n" + result[idx_start:idx_end].strip()
                pick += "\n\n_僅顯示信心 ≥70 最高分機會_"
                result = pick
            except Exception:
                pass
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "movers":
        await q.edit_message_text("⏳ 掃描異動...")
        result = await safe_run(analyzer.detect_movers(), timeout=30)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 附漲跌榜圖
        if CHART_ENABLED:
            try:
                import aiohttp as _aio
                async with _aio.ClientSession() as session:
                    tasks = [analyzer.fetch_ticker(session, s) for s in analyzer.SCAN_POOL]
                    tickers = await asyncio.gather(*tasks, return_exceptions=True)
                data = []
                for i, sym in enumerate(analyzer.SCAN_POOL):
                    t = tickers[i]
                    if isinstance(t, Exception):
                        continue
                    try:
                        chg = float(t.get("priceChangePercent", 0))
                        sym_short = sym.replace("/USDT", "")
                        data.append((sym_short, chg))
                    except Exception:
                        continue
                gainers = sorted(data, key=lambda x: x[1], reverse=True)[:8]
                losers = sorted(data, key=lambda x: x[1])[:8]
                now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                buf = plot_movers_chart(gainers, losers, "MARKET MOVERS  |  " + now_str)
                await send_chart_buf(ctx, chat_id, buf, "📊 *24H 漲跌排行榜*")
            except Exception as e:
                logger.error("movers 圖表失敗: " + str(e))

    elif d == "kline":
        USER_STATES[chat_id] = "WAIT_KLINE"
        await q.edit_message_text(
            "📊 *多週期支撐阻力*\n\n請輸入幣種：\n`BTC` / `ETH` / `SOL`",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "trend":
        await q.edit_message_text("⏳ 掃描趨勢...")
        result = await safe_run(analyzer.trend_watch(DEFAULT_SYMBOLS), timeout=40)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 附趨勢分布圖
        if CHART_ENABLED:
            try:
                # 從文字結果提取分類數量
                import re as _re_trend
                sb_m = _re_trend.search(r"強多頭.*?\((\d+)\)", result)
                b_m = _re_trend.search(r"\*📈 多頭.*?\((\d+)\)", result)
                r_m = _re_trend.search(r"震盪.*?\((\d+)\)", result)
                bear_m = _re_trend.search(r"\*📉 空頭.*?\((\d+)\)", result)
                sbe_m = _re_trend.search(r"強空頭.*?\((\d+)\)", result)
                sb = int(sb_m.group(1)) if sb_m else 0
                b = int(b_m.group(1)) if b_m else 0
                r_c = int(r_m.group(1)) if r_m else 0
                be = int(bear_m.group(1)) if bear_m else 0
                sbe = int(sbe_m.group(1)) if sbe_m else 0
                if sb + b + r_c + be + sbe > 0:
                    buf = plot_trend_distribution(sb, b, r_c, be, sbe)
                    await send_chart_buf(ctx, chat_id, buf, "🔭 *趨勢分布圖*")
            except Exception as e:
                logger.error("trend 圖表失敗: " + str(e))

    elif d == "sentiment":
        await q.edit_message_text("⏳ 分析情緒...")
        result = await safe_run(analyzer.get_market_sentiment(), timeout=20)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 附 BTC + ETH 雙圖
        if CHART_ENABLED:
            try:
                import aiohttp as _aio
                async with _aio.ClientSession() as session:
                    df_btc = await analyzer.fetch_ohlcv(session, "BTC/USDT", "1h", 100)
                    df_eth = await analyzer.fetch_ohlcv(session, "ETH/USDT", "1h", 100)
                if df_btc is not None and df_eth is not None:
                    buf = plot_dual_chart(df_btc, df_eth)
                    await send_chart_buf(ctx, chat_id, buf, "🌐 *市場脈動 — BTC & ETH*")
            except Exception as e:
                logger.error("sentiment 圖表失敗: " + str(e))

    elif d == "custom":
        USER_STATES[chat_id] = "WAIT_SYMBOL"
        await q.edit_message_text(
            "🔍 *自訂幣種*\n\n請輸入：`BTC` `ETH` `PEPE` `LINK`",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "favorites":
        favs = USER_FAVORITES.get(chat_id, [])
        text = "⭐ *我的自選*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        if favs:
            text += "點選幣種立即分析：\n"
        else:
            text += "尚無自選，點下方新增\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=fav_menu(chat_id))

    elif d == "favadd":
        USER_STATES[chat_id] = "WAIT_FAV_ADD"
        await q.edit_message_text(
            "➕ *新增自選*\n\n輸入幣種：`BTC` `ETH` `PEPE`",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d.startswith("favadd_"):
        symbol = d[7:]
        favs = USER_FAVORITES.setdefault(chat_id, [])
        if symbol not in favs:
            favs.append(symbol)
            save_data()
            await q.answer("✅ 已加入自選：" + symbol, show_alert=True)
        else:
            await q.answer("⚠️ 已在自選中", show_alert=True)

    elif d.startswith("favrm_"):
        symbol = d[6:]
        favs = USER_FAVORITES.get(chat_id, [])
        if symbol in favs:
            favs.remove(symbol)
            save_data()
        await q.edit_message_text(
            "⭐ *我的自選*\n━━━━━━━━━━━━━━━━━━━━\n\n更新成功",
            parse_mode="Markdown", reply_markup=fav_menu(chat_id)
        )

    elif d == "history":
        result = show_history(chat_id)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "auto_on":
        HUNTER_WATCHERS.add(chat_id)
        save_data()
        await q.edit_message_text(
            "✅ *5分鐘智能推播已開啟*\n\n"
            "🎯 每 *5 分鐘* 自動掃描 30 幣種\n"
            "💡 推送信心 *≥65* 的設置\n"
            "📊 包含完整下單計劃\n"
            "📜 自動記錄到推播歷史\n\n"
            "🧪 用 /testpush 立即測試\n\n"
            "_盤整時不會打擾你_",
            reply_markup=back_btn(),
            parse_mode="Markdown"
        )

    elif d == "auto_off":
        HUNTER_WATCHERS.discard(chat_id)
        save_data()
        await q.edit_message_text("🔕 推播已關閉", reply_markup=back_btn())

    elif d == "schedule_menu":
        config = USER_DAILY_SCHEDULE.get(chat_id, {"hours": [], "types": []})
        hours_str = ", ".join(str(h) + ":00" for h in sorted(config.get("hours", []))) if config.get("hours") else "未設定"
        type_labels = {
            "sentiment": "市場情緒",
            "trend": "趨勢總覽",
            "movers": "異動掃描",
            "events": "新聞+事件日曆"
        }
        types_str = ", ".join(type_labels.get(t, t) for t in config.get("types", [])) if config.get("types") else "未設定"
        text = (
            "📅 *自訂定時推播*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🕐 *推播時間 (UTC)*: " + hours_str + "\n"
            "📋 *推播內容*: " + types_str + "\n\n"
            "_台北時間 = UTC + 8 小時_\n"
            "_例如 UTC 12:00 = 台北 20:00_\n\n"
            "請選擇要設定的項目："
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 設定推播時間", callback_data="sched_hours")],
            [InlineKeyboardButton("📋 設定推播內容", callback_data="sched_types")],
            [InlineKeyboardButton("🚀 快速設定（推薦）", callback_data="sched_preset")],
            [InlineKeyboardButton("🗑 清除全部", callback_data="sched_clear")],
            [InlineKeyboardButton("🏠 返回主選單", callback_data="home")],
        ])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif d == "sched_preset":
        USER_DAILY_SCHEDULE[chat_id] = {
            "hours": [8, 12, 20],
            "types": ["sentiment", "trend", "movers", "events"]
        }
        save_data()
        await q.edit_message_text(
            "✅ *快速設定完成*\n\n"
            "📅 推播時段：\n"
            "• 08:00 UTC（台北 16:00）\n"
            "• 12:00 UTC（台北 20:00）\n"
            "• 20:00 UTC（台北 04:00）\n\n"
            "📋 推播內容：\n"
            "• 🌐 市場情緒（含新聞 + 事件日曆）\n"
            "• 🔭 趨勢總覽\n"
            "• ⚡ 異動掃描\n"
            "• 🗓 新聞+事件日曆",
            reply_markup=back_btn(),
            parse_mode="Markdown"
        )

    elif d == "sched_hours":
        config = USER_DAILY_SCHEDULE.get(chat_id, {"hours": [], "types": []})
        selected = set(config.get("hours", []))
        # 產生 24 小時按鈕（4 排，每排 6 個）
        kb_rows = []
        for row_start in range(0, 24, 6):
            row = []
            for h in range(row_start, min(row_start + 6, 24)):
                mark = "✅" if h in selected else ""
                row.append(InlineKeyboardButton(mark + str(h).zfill(2), callback_data="schhr_" + str(h)))
            kb_rows.append(row)
        kb_rows.append([InlineKeyboardButton("✅ 確認完成", callback_data="schedule_menu")])
        await q.edit_message_text(
            "🕐 *選擇推播時間 (UTC)*\n\n"
            "點選想推播的時段（可多選）\n"
            "_例：08 表示 UTC 08:00，台北 16:00_\n\n"
            "已選：" + (", ".join(str(h) for h in sorted(selected)) if selected else "無"),
            reply_markup=InlineKeyboardMarkup(kb_rows),
            parse_mode="Markdown"
        )

    elif d.startswith("schhr_"):
        hour = int(d[6:])
        config = USER_DAILY_SCHEDULE.setdefault(chat_id, {"hours": [], "types": []})
        hours = config.get("hours", [])
        if hour in hours:
            hours.remove(hour)
        else:
            hours.append(hour)
        config["hours"] = hours
        save_data()
        # 重繪畫面
        selected = set(hours)
        kb_rows = []
        for row_start in range(0, 24, 6):
            row = []
            for h in range(row_start, min(row_start + 6, 24)):
                mark = "✅" if h in selected else ""
                row.append(InlineKeyboardButton(mark + str(h).zfill(2), callback_data="schhr_" + str(h)))
            kb_rows.append(row)
        kb_rows.append([InlineKeyboardButton("✅ 確認完成", callback_data="schedule_menu")])
        await q.edit_message_text(
            "🕐 *選擇推播時間 (UTC)*\n\n"
            "已選：" + (", ".join(str(h) for h in sorted(selected)) if selected else "無"),
            reply_markup=InlineKeyboardMarkup(kb_rows),
            parse_mode="Markdown"
        )

    elif d == "sched_types":
        config = USER_DAILY_SCHEDULE.get(chat_id, {"hours": [], "types": []})
        selected = set(config.get("types", []))
        type_options = [
            ("sentiment", "🌐 市場情緒"),
            ("trend", "🔭 趨勢總覽"),
            ("movers", "⚡ 異動掃描"),
            ("events", "🗓 新聞+事件日曆"),
        ]
        kb_rows = []
        for key, label in type_options:
            mark = "✅ " if key in selected else ""
            kb_rows.append([InlineKeyboardButton(mark + label, callback_data="schtype_" + key)])
        kb_rows.append([InlineKeyboardButton("✅ 確認完成", callback_data="schedule_menu")])
        await q.edit_message_text(
            "📋 *選擇推播內容*\n\n"
            "可多選，每次推播時段都會發送你選的內容",
            reply_markup=InlineKeyboardMarkup(kb_rows),
            parse_mode="Markdown"
        )

    elif d.startswith("schtype_"):
        type_key = d[8:]
        config = USER_DAILY_SCHEDULE.setdefault(chat_id, {"hours": [], "types": []})
        types = config.get("types", [])
        if type_key in types:
            types.remove(type_key)
        else:
            types.append(type_key)
        config["types"] = types
        save_data()
        # 重繪
        selected = set(types)
        type_options = [
            ("sentiment", "🌐 市場情緒"),
            ("trend", "🔭 趨勢總覽"),
            ("movers", "⚡ 異動掃描"),
            ("events", "🗓 新聞+事件日曆"),
        ]
        kb_rows = []
        for key, label in type_options:
            mark = "✅ " if key in selected else ""
            kb_rows.append([InlineKeyboardButton(mark + label, callback_data="schtype_" + key)])
        kb_rows.append([InlineKeyboardButton("✅ 確認完成", callback_data="schedule_menu")])
        await q.edit_message_text(
            "📋 *選擇推播內容*\n\n已選 " + str(len(selected)) + " 項",
            reply_markup=InlineKeyboardMarkup(kb_rows),
            parse_mode="Markdown"
        )

    elif d == "sched_clear":
        USER_DAILY_SCHEDULE.pop(chat_id, None)
        save_data()
        await q.edit_message_text(
            "🗑 已清除所有定時推播設定",
            reply_markup=back_btn()
        )

    elif d == "position_calc":
        capital = USER_CAPITAL.get(chat_id)
        if not capital:
            USER_STATES[chat_id] = "WAIT_CAPITAL"
            await q.edit_message_text(
                "💼 *倉位風險計算器*\n\n"
                "首次使用，請先設定你的交易資金：\n"
                "（例如：`5000` 代表 $5000 USDT）",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
        else:
            USER_STATES[chat_id] = "WAIT_POSITION_INFO"
            await q.edit_message_text(
                "💼 *倉位風險計算器*\n\n"
                "目前資金 `$" + str(capital) + "`\n\n"
                "請依序輸入（用空格分隔）：\n"
                "`進場價 止損價 槓桿`\n\n"
                "例如：`50000 49000 5`\n"
                "（進場 50000，止損 49000，5倍槓桿）\n\n"
                "輸入 `reset` 重設資金",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )

    elif d == "momentum":
        await q.edit_message_text("⚡ 即時動能掃描中...\n(尋找 5-15 分鐘級爆發機會)")
        result = await safe_run(analyzer.momentum_scan(), timeout=60)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 附動能 TOP 3 多圖（5m 級別）
        if CHART_ENABLED and "目前沒有顯著爆發信號" not in result:
            try:
                import re as _re_mom
                import aiohttp as _aiohttp_mom
                mom_coins = []
                for line in result.split("\n"):
                    m = _re_mom.search(r"\*([A-Z0-9]+)\*", line)
                    if m and ("爆發" in line or "崩跌" in line):
                        chg_m = _re_mom.search(r"5分 `([+-]?\d+\.?\d*)%`", line)
                        if chg_m:
                            mom_coins.append((m.group(1) + "/USDT", float(chg_m.group(1))))
                mom_coins = mom_coins[:6]
                if mom_coins:
                    coin_data = []
                    async with _aiohttp_mom.ClientSession() as session:
                        for sym, chg in mom_coins:
                            try:
                                df = await analyzer.fetch_ohlcv(session, sym, "5m", 60)
                                if df is not None:
                                    coin_data.append({"symbol": sym, "df": df, "chg": chg})
                            except Exception:
                                continue
                    if coin_data:
                        buf = plot_multi_coin_chart(coin_data, title="Momentum Breakouts (5m)")
                        if buf:
                            await ctx.bot.send_photo(chat_id=chat_id, photo=buf,
                                                       caption="⚡ *即時動能 5m 走勢*",
                                                       parse_mode="Markdown")
                            if TG_CHANNEL_ID:
                                try:
                                    buf2 = plot_multi_coin_chart(coin_data, title="Momentum Breakouts (5m)")
                                    if buf2:
                                        await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf2,
                                                                  caption="⚡ *即時動能 5m 走勢*",
                                                                  parse_mode="Markdown")
                                except Exception:
                                    pass
            except Exception as e:
                logger.error("動能附圖失敗: " + str(e))
        # 推到頻道
        if TG_CHANNEL_ID and "目前沒有顯著爆發信號" not in result:
            try:
                await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
            except Exception as e:
                logger.error("動能推播頻道失敗: " + str(e))
        # 附動能圖（重新抓資料生成）
        if CHART_ENABLED:
            try:
                import aiohttp as _aio
                async with _aio.ClientSession() as session:
                    tasks = []
                    for sym in analyzer.SCAN_POOL:
                        tasks.append(analyzer.fetch_ticker(session, sym))
                        tasks.append(analyzer.fetch_ohlcv(session, sym, "5m", 30))
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                opportunities = []
                for i, sym in enumerate(analyzer.SCAN_POOL):
                    ticker = results[i * 2]
                    df5m = results[i * 2 + 1]
                    if isinstance(ticker, Exception) or isinstance(df5m, Exception):
                        continue
                    if df5m is None or len(df5m) < 8:
                        continue
                    try:
                        current_price = float(ticker.get("lastPrice", 0))
                        if not current_price:
                            continue
                        chg_5m = (current_price - float(df5m["close"].iloc[-2])) / float(df5m["close"].iloc[-2]) * 100
                        chg_15m = (current_price - float(df5m["close"].iloc[-4])) / float(df5m["close"].iloc[-4]) * 100
                        chg_30m = (current_price - float(df5m["close"].iloc[-7])) / float(df5m["close"].iloc[-7]) * 100
                        recent_vol = float(df5m["volume"].iloc[-1])
                        avg_vol = float(df5m["volume"].tail(20).mean())
                        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
                        if abs(chg_5m) >= 1.0 and vol_ratio >= 1.5:
                            opportunities.append({
                                "symbol": sym, "chg_5m": round(chg_5m, 2),
                                "chg_15m": round(chg_15m, 2), "chg_30m": round(chg_30m, 2),
                                "vol_ratio": round(vol_ratio, 1),
                                "intensity": abs(chg_5m) * vol_ratio
                            })
                    except Exception:
                        continue
                opportunities.sort(key=lambda x: x["intensity"], reverse=True)
                if opportunities:
                    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                    buf = plot_momentum_chart(opportunities, "MOMENTUM SCAN  |  " + now_str)
                    if buf:
                        await send_chart_buf(ctx, chat_id, buf, "⚡ *即時動能榜（5m / 15m / 30m）*")
            except Exception as e:
                logger.error("momentum 圖表失敗: " + str(e))

    elif d == "news_only":
        await q.edit_message_text("📰 抓取加密快訊中...")
        async def get_news_only():
            import aiohttp as _aiohttp
            try:
                async with _aiohttp.ClientSession() as session:
                    news = await analyzer.fetch_news(session)
                    events = await analyzer.fetch_crypto_events(session)
                r = "📰 *加密貨幣最新資訊*\n"
                r += "━━━━━━━━━━━━━━━\n\n"
                if news:
                    score, label, items = analyzer.sentiment(news)
                    r += "*━━ 📰 即時新聞 ━━*\n"
                    for i, item in enumerate(items[:8], 1):
                        time_ago = analyzer.format_published(item.get("published", ""))
                        r += str(i) + ". " + item["emoji"] + " " + item["title"][:75]
                        if time_ago:
                            r += " _(" + time_ago + ")_"
                        r += "\n"
                if events:
                    r += "\n*━━ 🗓 加密幣事件 ━━*\n"
                    for ev in events[:6]:
                        title = ev.get("title", "")[:55]
                        date = ev.get("date", "")
                        typ = ev.get("type", "")
                        type_emoji = "🔓" if typ == "Unlock" else ("🚀" if typ == "Listing" else ("⚙️" if typ == "Upgrade" else "📌"))
                        r += "• " + type_emoji + " " + title
                        if date:
                            r += " `" + date + "`"
                        r += "\n"
                return r
            except Exception as e:
                return "❌ 新聞抓取失敗：" + str(e)
        result = await safe_run(get_news_only(), timeout=30)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 自動推到頻道
        if TG_CHANNEL_ID:
            try:
                await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
            except Exception as e:
                logger.error("快訊推播失敗: " + str(e))

    elif d == "active_signals":
        if not ACTIVE_SIGNALS:
            text = "📡 *追蹤中的信號*\n\n目前無活躍信號\n_當黑潮船長發出推播時會自動追蹤_"
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn())
        else:
            text = "📡 *追蹤中的信號* (" + str(len(ACTIVE_SIGNALS)) + ")\n"
            text += "━━━━━━━━━━━━━━━\n"
            now = datetime.now(timezone.utc)
            kb_rows = []
            for sym, sig in ACTIVE_SIGNALS.items():
                direction = "做多 🟢" if sig["direction"] == "LONG" else "做空 🔴"
                tp_hit = sig.get("tp_hit", [])
                tp_status = "✅TP" + ",".join(str(t) for t in tp_hit) if tp_hit else "進行中"
                try:
                    created = datetime.fromisoformat(sig["created"])
                    age = now - created
                    age_str = str(int(age.total_seconds() / 3600)) + "h前"
                except Exception:
                    age_str = ""
                sym_short = sym.replace("/USDT", "")
                text += "• *" + sym_short + "* " + direction + "\n"
                text += "  進場 `" + str(sig["entry"]) + "` 止損 `" + str(sig["sl"]) + "`\n"
                text += "  狀態 " + tp_status + " | 評分 `" + str(sig.get("score", "?")) + "` | " + age_str + "\n"
                kb_rows.append([
                    InlineKeyboardButton("📱 " + sym_short + " 開 BingX", url=bingx_swap_url(sym)),
                    InlineKeyboardButton("📋 參數", callback_data="copy_" + sym.replace("/", "_"))
                ])
            kb_rows.append([InlineKeyboardButton("🏠 返回主選單", callback_data="home")])
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))

    elif d == "stats":
        if not SIGNAL_RESULTS:
            text = "📊 *歷史戰績*\n\n暫無已關閉信號的歷史數據"
        else:
            wins = [r for r in SIGNAL_RESULTS if r.get("result") in ("TP4_HIT",) or r.get("tp_hit_count", 0) >= 2]
            partial = [r for r in SIGNAL_RESULTS if r.get("tp_hit_count", 0) == 1]
            losses = [r for r in SIGNAL_RESULTS if r.get("result") == "SL_HIT" and r.get("tp_hit_count", 0) == 0]
            others = [r for r in SIGNAL_RESULTS if r not in wins and r not in partial and r not in losses]
            total = len(SIGNAL_RESULTS)
            win_count = len(wins) + len(partial)
            win_rate = (win_count / total * 100) if total > 0 else 0
            avg_pct = sum(r.get("final_pct", 0) for r in SIGNAL_RESULTS) / total if total > 0 else 0
            text = "📊 *歷史戰績* (" + str(total) + " 筆)\n"
            text += "━━━━━━━━━━━━━━━\n"
            text += "🏆 完美止盈：`" + str(len(wins)) + "` 筆\n"
            text += "💰 部分獲利：`" + str(len(partial)) + "` 筆\n"
            text += "🛑 止損出場：`" + str(len(losses)) + "` 筆\n"
            text += "⏰ 其他結果：`" + str(len(others)) + "` 筆\n\n"
            text += "📈 實際勝率 `" + str(round(win_rate, 1)) + "%`\n"
            text += "💵 平均盈虧 `" + str(round(avg_pct, 2)) + "%`\n\n"
            text += "*最近 5 筆*\n"
            for r in SIGNAL_RESULTS[-5:][::-1]:
                emoji = "🏆" if r.get("result") == "TP4_HIT" else ("🛑" if r.get("result") == "SL_HIT" else ("⏰" if r.get("result") == "EXPIRED" else "📌"))
                pct = r.get("final_pct", 0)
                pct_str = "+" + str(pct) if pct >= 0 else str(pct)
                text += emoji + " *" + r.get("symbol", "?") + "* " + pct_str + "%\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn())

    elif d.startswith("copy_"):
        sym = d[5:].replace("_", "/")
        if sym not in ACTIVE_SIGNALS:
            await q.answer("⚠️ 此信號已過期或已關閉", show_alert=True)
            return
        sig = ACTIVE_SIGNALS[sym]
        sym_short = sym.replace("/USDT", "")
        direction_zh = "做多/Long" if sig["direction"] == "LONG" else "做空/Short"

        msg = "📋 *" + sym_short + " 下單參數*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "請在 BingX 中設定以下參數：\n\n"
        msg += "🔸 *交易對*：`" + sym.replace("/", "-") + "`\n"
        msg += "🔸 *方向*：" + direction_zh + "\n"
        msg += "🔸 *進場價*：`" + str(sig["entry"]) + "`\n"
        msg += "🔸 *止損價*：`" + str(sig["sl"]) + "`\n\n"
        msg += "*📍 階梯止盈設定*\n"
        msg += "TP1：`" + str(sig["tp1"]) + "` 平 25%\n"
        if sig.get("tp2", 0) > 0:
            msg += "TP2：`" + str(sig["tp2"]) + "` 平 35%\n"
        if sig.get("tp3", 0) > 0:
            msg += "TP3：`" + str(sig["tp3"]) + "` 平 25%\n"
        if sig.get("tp4", 0) > 0:
            msg += "TP4：`" + str(sig["tp4"]) + "` 平 15%\n"
        msg += "\n*💡 BingX 設定步驟*\n"
        msg += "1️⃣ 開啟 BingX 該幣交易頁\n"
        msg += "2️⃣ 選擇 *合約* → 設定槓桿\n"
        if sig.get("order_type") == "LIMIT":
            msg += "3️⃣ 選擇 *限價* → 填入進場價\n"
        else:
            msg += "3️⃣ 選擇 *市價* 即可\n"
        msg += "4️⃣ 下單時勾選 *止損/止盈*\n"
        msg += "5️⃣ 分別填入上方 TP/SL 數值\n\n"
        msg += "_長按上方的價格可以直接複製_\n"
        msg += "_確認後回到 TG 讓我幫你追蹤_"

        # 加入返回按鈕和 BingX 連結
        url = bingx_swap_url(sym)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 開啟 BingX " + sym_short, url=url)],
            [InlineKeyboardButton("🔙 返回", callback_data="home")]
        ])
        await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif d == "home":
        USER_STATES.pop(chat_id, None)
        await q.edit_message_text(
            "🤖 *主選單*",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    state = USER_STATES.get(chat_id)
    symbol = text.upper()
    if "/" not in symbol:
        symbol = symbol + "/USDT"

    if state == "WAIT_SYMBOL":
        USER_STATES.pop(chat_id, None)
        msg = await update.message.reply_text("⏳ 分析 " + symbol + "...")
        result = await safe_run(analyzer.full_analysis(symbol), timeout=30)
        keyboard = [[InlineKeyboardButton("⭐ 加入自選", callback_data="favadd_" + symbol),
                     InlineKeyboardButton("🏠 主選單", callback_data="home")]]
        await msg.edit_text(result, parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if state == "WAIT_KLINE":
        USER_STATES.pop(chat_id, None)
        msg = await update.message.reply_text("⏳ 多週期分析 " + symbol + "...")
        result = await safe_run(analyzer.kline_sr_analysis(symbol), timeout=30)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=back_btn())
        return

    if state == "WAIT_FAV_ADD":
        USER_STATES.pop(chat_id, None)
        favs = USER_FAVORITES.setdefault(chat_id, [])
        if symbol not in favs:
            favs.append(symbol)
            save_data()
            await update.message.reply_text(
                "✅ 已加入自選：" + symbol,
                reply_markup=fav_menu(chat_id)
            )
        else:
            await update.message.reply_text(
                "⚠️ " + symbol + " 已在自選中",
                reply_markup=fav_menu(chat_id)
            )
        return

    if state == "WAIT_CAPITAL":
        USER_STATES.pop(chat_id, None)
        try:
            capital = float(text.replace("$", "").replace(",", "").strip())
            if capital < 100:
                await update.message.reply_text("❌ 資金太少，至少需要 $100")
                return
            USER_CAPITAL[chat_id] = capital
            save_data()
            USER_STATES[chat_id] = "WAIT_POSITION_INFO"
            await update.message.reply_text(
                "✅ 資金已設為 `$" + str(capital) + "`\n\n"
                "現在輸入 *進場價 止損價 槓桿* (用空格)：\n"
                "例如：`50000 49000 5`",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
        except Exception:
            await update.message.reply_text("❌ 格式錯誤，請輸入數字（例如：5000）")
        return

    if state == "WAIT_POSITION_INFO":
        if text.lower() == "reset":
            USER_CAPITAL.pop(chat_id, None)
            save_data()
            USER_STATES[chat_id] = "WAIT_CAPITAL"
            await update.message.reply_text(
                "已重設。請輸入新的資金量：",
                reply_markup=back_btn()
            )
            return
        USER_STATES.pop(chat_id, None)
        try:
            parts = text.split()
            if len(parts) != 3:
                raise ValueError("需要3個數值")
            entry = float(parts[0])
            sl = float(parts[1])
            leverage = float(parts[2])
            capital = USER_CAPITAL.get(chat_id, 1000)
            # 風險 1% 和 2% 兩種選擇
            r = "💼 *倉位風險計算結果*\n"
            r += "━━━━━━━━━━━━━━━━━━━━\n\n"
            r += "💰 資金 `$" + str(capital) + "`\n"
            r += "🎯 進場 `" + str(entry) + "`\n"
            r += "🛑 止損 `" + str(sl) + "`\n"
            r += "⚖️ 槓桿 `" + str(leverage) + "x`\n\n"
            stop_pct = abs(entry - sl) / entry * 100
            r += "📏 止損距離 `" + str(round(stop_pct, 2)) + "%`\n\n"
            for risk_pct in [1, 2]:
                pos = analyzer.calculate_position(capital, risk_pct, entry, sl, leverage)
                if pos:
                    r += "*━━ 風險 " + str(risk_pct) + "% ━━*\n"
                    r += "📦 倉位 `" + str(pos["coins"]) + "` 幣\n"
                    r += "💵 倉位值 `$" + str(pos["position_value"]) + "`\n"
                    r += "💳 保證金 `$" + str(pos["margin"]) + "`\n"
                    r += "🛑 最大虧損 `$" + str(pos["max_loss"]) + "`\n\n"
            r += "_專業建議：單筆風險不超過資金 2%_"
            await update.message.reply_text(r, parse_mode="Markdown", reply_markup=back_btn())
        except Exception as e:
            await update.message.reply_text(
                "❌ 格式錯誤：" + str(e) + "\n\n"
                "正確格式：`進場 止損 槓桿`\n"
                "例如：`50000 49000 5`",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
        return

    if "/" in text and len(text) < 15:
        msg = await update.message.reply_text("⏳ 分析 " + symbol + "...")
        result = await safe_run(analyzer.full_analysis(symbol), timeout=30)
        await msg.edit_text(result, parse_mode="Markdown")


# ⭐ 自訂定時推播
DAILY_PUSHED_HOURS = {}  # {chat_id: set(已推播小時)}

async def daily_report_check(ctx: ContextTypes.DEFAULT_TYPE):
    """每小時檢查每個用戶的自訂推播設定"""
    global DAILY_PUSHED_HOURS
    now = datetime.now(timezone.utc)
    hour = now.hour
    today = now.strftime("%Y-%m-%d")
    if not USER_DAILY_SCHEDULE:
        return
    # 找出本小時需要推播的用戶
    users_to_push = []
    for chat_id, config in USER_DAILY_SCHEDULE.items():
        hours = config.get("hours", [])
        types = config.get("types", [])
        if hour not in hours or not types:
            continue
        # 檢查今天這個時段是否已推播
        user_pushed = DAILY_PUSHED_HOURS.setdefault(chat_id, set())
        pushed_key = today + "-" + str(hour)
        if pushed_key in user_pushed:
            continue
        # 清理過期紀錄（保留今天的）
        DAILY_PUSHED_HOURS[chat_id] = {k for k in user_pushed if k.startswith(today)}
        DAILY_PUSHED_HOURS[chat_id].add(pushed_key)
        users_to_push.append((chat_id, types))
    if not users_to_push:
        return
    # 預先抓資料（避免每個用戶重複抓）
    needed_types = set()
    for _, types in users_to_push:
        needed_types.update(types)
    logger.info("定時推播 UTC " + str(hour) + ":00 → " + str(len(users_to_push)) + " 戶，內容：" + str(needed_types))
    cached_results = {}
    try:
        if "sentiment" in needed_types or "events" in needed_types:
            cached_results["sentiment"] = await asyncio.wait_for(
                analyzer.get_market_sentiment(), timeout=40
            )
        if "trend" in needed_types:
            cached_results["trend"] = await asyncio.wait_for(
                analyzer.trend_watch(DEFAULT_SYMBOLS), timeout=40
            )
        if "movers" in needed_types:
            cached_results["movers"] = await asyncio.wait_for(
                analyzer.detect_movers(), timeout=30
            )
    except Exception as e:
        logger.error("定時推播資料抓取失敗: " + str(e))
        return
    # 時段問候語（精簡版）
    if 5 <= hour < 12:
        greeting = "🌅 *早安市場簡報*"
    elif 12 <= hour < 18:
        greeting = "☀️ *午後市場簡報*"
    elif 18 <= hour < 22:
        greeting = "🌆 *晚間市場簡報*"
    else:
        greeting = "🌙 *深夜市場簡報*"
    # 不加分隔線，直接讓內容跟上
    header = greeting + " | " + str(hour).zfill(2) + ":00 UTC\n"
    # 為每個用戶組合推播內容
    for chat_id, user_types in users_to_push:
        try:
            # 智能去重：避免 sentiment 和 events 同時選會推播兩次
            added_sentiment = False
            content_parts = [header]
            if "sentiment" in user_types and "sentiment" in cached_results:
                content_parts.append(cached_results["sentiment"])
                added_sentiment = True
            if "events" in user_types and not added_sentiment and "sentiment" in cached_results:
                content_parts.append(cached_results["sentiment"])
            if "trend" in user_types and "trend" in cached_results:
                content_parts.append(cached_results["trend"])
            if "movers" in user_types and "movers" in cached_results:
                content_parts.append(cached_results["movers"])
            # 使用單行分隔（節省空間）
            content = "\n\n".join(content_parts)
            # 拆分長訊息（Telegram 限制 4096 字元）
            chunks = []
            if len(content) <= 4000:
                chunks = [content]
            else:
                # 按 ━━━━━━━━━━━━━━━ 大標題拆分
                separator = "━━━━━━━━━━━━━━━"
                parts = content.split(separator)
                current = ""
                for p in parts:
                    candidate = current + (separator if current else "") + p
                    if len(candidate) < 3800:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        current = p
                if current:
                    chunks.append(current)
                # 如果切完還有過長的，按段落再切
                final_chunks = []
                for chunk in chunks:
                    if len(chunk) <= 4000:
                        final_chunks.append(chunk)
                    else:
                        # 按行切
                        lines = chunk.split("\n")
                        cur = ""
                        for line in lines:
                            if len(cur) + len(line) < 3800:
                                cur += line + "\n"
                            else:
                                if cur:
                                    final_chunks.append(cur)
                                cur = line + "\n"
                        if cur:
                            final_chunks.append(cur)
                chunks = final_chunks
            for chunk in chunks:
                await ctx.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
                await asyncio.sleep(0.5)
            # 同步到 TG 頻道
            if TG_CHANNEL_ID:
                try:
                    for chunk in chunks:
                        await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=chunk, parse_mode="Markdown")
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error("頻道推播失敗: " + str(e))
        except Exception as e:
            logger.error("定時推播失敗 " + str(chat_id) + ": " + str(e))
    save_data()


# ⭐ 5 分鐘智能推播（含信號追蹤、冷卻機制）
async def auto_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    if not HUNTER_WATCHERS:
        return
    logger.info("5分推播：訂閱戶 " + str(len(HUNTER_WATCHERS)) + "，活躍信號 " + str(len(ACTIVE_SIGNALS)))
    try:
        # ⭐ 先檢查活躍信號是否觸及 TP/SL/過期（通知用戶）
        await check_active_signals(ctx)
        result = await asyncio.wait_for(
            analyzer.golden_hunter(smart_filter=True),  # 過濾 ≥65 分
            timeout=90
        )
        if result is None:
            logger.info("5分推播：無 ≥65 信號，跳過")
            return
        # ⭐ 從結果解析信號詳情並進行冷卻檢查
        import re as _re
        # 解析推播訊息中的每個候選信號
        parsed_signals = parse_hunter_signals(result)

        # ⭐ 冷卻機制：過濾掉已有活躍信號的幣種
        filtered_signals = []
        skipped_reasons = []
        for sig in parsed_signals:
            sym = sig.get("symbol", "")
            if sym in ACTIVE_SIGNALS:
                active = ACTIVE_SIGNALS[sym]
                # 同方向 → 直接跳過（冷卻中）
                if active.get("direction") == sig.get("direction"):
                    skipped_reasons.append(sym + " 冷卻中（同向）")
                    continue
                # 反向 → 必須評分 >= 75 才允許
                if sig.get("score", 0) < 75:
                    skipped_reasons.append(sym + " 反向但分數不足 (" + str(sig.get("score")) + ")")
                    continue
                # 允許反向 → 先關閉舊信號
                logger.info("關閉 " + sym + " 舊信號（反向高分新信號）")
                await close_signal(ctx, sym, "REVERSED", "反向新信號出現")
            filtered_signals.append(sig)

        if skipped_reasons:
            logger.info("冷卻過濾: " + " | ".join(skipped_reasons))

        if not filtered_signals:
            logger.info("5分推播：所有信號被冷卻過濾，跳過")
            return

        # ⭐ 連虧暫停過濾
        loss_filtered = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for sig in filtered_signals:
            sym = sig.get("symbol", "")
            losses = SYMBOL_LOSSES.get(sym, [])
            recent_losses = [t for t in losses if datetime.fromisoformat(t) > cutoff]
            if len(recent_losses) >= 2:
                skipped_reasons.append(sym + " 連虧暫停中(24h)")
                continue
            loss_filtered.append(sig)

        if not loss_filtered:
            logger.info("5分推播：全部被連虧過濾，跳過")
            return

        # 註冊新信號到追蹤系統
        for sig in loss_filtered:
            register_signal(sig, list(HUNTER_WATCHERS))

        logger.info("5分推播：新信號 " + str(len(loss_filtered)) + " 個 / 過濾 " + str(len(skipped_reasons)) + " 個")
        # 重新組合 result 文字（只保留沒被過濾的）
        if len(loss_filtered) < len(filtered_signals):
            kept_symbols = set(s["symbol"] for s in loss_filtered)
            # 從原 result 抽取保留的部分（簡化做法：直接重新生成提示）
            # 不重組訊息，只是 log 一下
            pass
        # ⭐ v26：黑潮船長只推私人用戶，不推頻道
        # ⭐ 為主推播產生 BingX 一鍵下單按鈕（TOP 3 信號）
        keyboard_rows = []
        for sig in loss_filtered[:3]:
            sym = sig.get("symbol", "")
            direction_zh = "做多" if sig.get("direction") == "LONG" else "做空"
            sym_short = sym.replace("/USDT", "")
            # 按鈕 1：跳轉 BingX 永續
            url = bingx_swap_url(sym)
            keyboard_rows.append([
                InlineKeyboardButton(
                    "📱 " + sym_short + " " + direction_zh + " — 開啟 BingX",
                    url=url
                )
            ])
            # 按鈕 2：複製下單參數
            keyboard_rows.append([
                InlineKeyboardButton(
                    "📋 複製 " + sym_short + " 下單參數",
                    callback_data="copy_" + sym.replace("/", "_")
                )
            ])

        # ⭐ v27 為每個信號附 K 線圖（最多 3 張）
        chart_data_list = []
        if CHART_ENABLED:
            try:
                import aiohttp as _aiohttp
                async with _aiohttp.ClientSession() as session:
                    for sig in loss_filtered[:3]:
                        sym = sig.get("symbol", "")
                        try:
                            df = await analyzer.fetch_ohlcv(session, sym, "1h", 100)
                            if df is not None:
                                # 簡化的支撐阻力
                                sw_res, sw_sup = analyzer.swing_sr(df)
                                chart_data_list.append({
                                    "sig": sig,
                                    "df": df,
                                    "sw_res": sw_res[:2] if sw_res else [],
                                    "sw_sup": sw_sup[:2] if sw_sup else [],
                                })
                        except Exception as e:
                            logger.error("圖表資料抓取失敗 " + sym + ": " + str(e))
            except Exception as e:
                logger.error("圖表批次抓取失敗: " + str(e))

        for chat_id in list(HUNTER_WATCHERS):
            try:
                # 主訊息（含全部分析）
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "━━━━━━━━━━━━━━━\n"
                        "🚢 *黑潮船長 — 即時信號*\n"
                        "━━━━━━━━━━━━━━━\n\n"
                        + result +
                        "\n\n_點下方按鈕直接前往 BingX 下單_"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None
                )
                # 附上 K 線圖
                for chart_data in chart_data_list:
                    sig = chart_data["sig"]
                    sym = sig.get("symbol", "")
                    sym_short = sym.replace("/USDT", "")
                    direction = sig.get("direction", "LONG")
                    grade = sig.get("entry_grade", "")
                    title_suffix = grade + " GRADE" if grade else ""
                    caption = (
                        "📊 *" + sym_short + " " + ("Long" if direction == "LONG" else "Short") + " " + grade + " " + "Grade*\n"
                        "Entry: `" + str(sig.get("entry", 0)) + "`\n"
                        "SL: `" + str(sig.get("sl", 0)) + "` | TP1: `" + str(sig.get("tp1", 0)) + "`"
                    )
                    await send_chart_with_caption(
                        ctx, chat_id, chart_data["df"], sym, "1H", direction,
                        entry=sig.get("entry"),
                        sl=sig.get("sl"),
                        tp1=sig.get("tp1"),
                        tp2=sig.get("tp2"),
                        tp3=sig.get("tp3"),
                        tp4=sig.get("tp4"),
                        support_levels=chart_data["sw_sup"],
                        resistance_levels=chart_data["sw_res"],
                        caption=caption,
                        title_suffix=title_suffix
                    )
                    await asyncio.sleep(0.3)
                # 記錄歷史
                lines = result.split("\n")
                for j, line in enumerate(lines):
                    if "🥇" in line and "*" in line:
                        try:
                            sym = line.split("*")[1].strip().split(" ")[0]
                            direction = ""
                            confidence = "?"
                            price = "?"
                            for k in range(j, min(j+15, len(lines))):
                                if "方向" in lines[k]:
                                    parts = lines[k].split("*")
                                    if len(parts) > 1:
                                        direction = parts[1]
                                if "信心評分" in lines[k]:
                                    parts = lines[k].split("`")
                                    if len(parts) > 1:
                                        confidence = parts[1]
                                if "即時價" in lines[k]:
                                    parts = lines[k].split("`")
                                    if len(parts) > 1:
                                        price = parts[1]
                            history = PUSH_HISTORY.setdefault(chat_id, [])
                            history.append({
                                "symbol": sym, "direction": direction,
                                "confidence": confidence, "price": price,
                                "time": datetime.now(timezone.utc).isoformat()
                            })
                            if len(history) > 30:
                                PUSH_HISTORY[chat_id] = history[-30:]
                            break
                        except Exception:
                            pass
                save_data()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("推播失敗 " + str(chat_id) + ": " + str(e))
    except Exception as e:
        logger.error("黑潮船長執行失敗: " + str(e))



# ===== 信號追蹤系統 =====

import re as _re_module
import hashlib

def parse_hunter_signals(result):
    """從黑潮船長推播文本解析信號詳情"""
    signals = []
    parts = _re_module.split(r"🥇|🥈|🥉", result)
    for i, part in enumerate(parts[1:], 1):
        try:
            sym_match = _re_module.search(r"\*([A-Z0-9]+)\s*(做多|做空)", part)
            if not sym_match:
                sym_match = _re_module.search(r"\*([A-Z0-9]+/USDT)\*", part)
                if not sym_match:
                    continue
                sym_raw = sym_match.group(1)
            else:
                sym_raw = sym_match.group(1)
            if "/USDT" not in sym_raw:
                sym = sym_raw + "/USDT"
            else:
                sym = sym_raw
            # 方向
            dir_match = _re_module.search(r"(做多|做空)", part)
            if not dir_match:
                continue
            direction = "LONG" if dir_match.group(1) == "做多" else "SHORT"
            # 評分
            score_match = _re_module.search(r"信心評分 `(\d+\.?\d*)/100`", part)
            if not score_match:
                score_match = _re_module.search(r"信心 `(\d+\.?\d*)/100`", part)
            score = float(score_match.group(1)) if score_match else 0
            # 進場價
            entry_match = _re_module.search(r"進場.{0,5}`([\d.]+)`", part)
            entry = float(entry_match.group(1)) if entry_match else 0
            # 止盈 1-4
            tp1_match = _re_module.search(r"止盈1?\s*`([\d.]+)`|①\s*`([\d.]+)`", part)
            tp2_match = _re_module.search(r"止盈2\s*`([\d.]+)`|②\s*`([\d.]+)`", part)
            tp3_match = _re_module.search(r"止盈3\s*`([\d.]+)`|③\s*`([\d.]+)`", part)
            tp4_match = _re_module.search(r"止盈4\s*`([\d.]+)`|④\s*`([\d.]+)`", part)
            sl_match = _re_module.search(r"止損.{0,5}`([\d.]+)`", part)
            # 持有時間
            tf_match = _re_module.search(r"持有時間 \*([^*]+)\*|\*?(短線|中線)", part)
            timeframe = tf_match.group(1).strip() if (tf_match and tf_match.group(1)) else "短線"
            # 進場品質
            grade_match = _re_module.search(r"([SABCD])\s*級", part)
            entry_grade = grade_match.group(1) if grade_match else "C"
            # 訂單類型
            order_match = _re_module.search(r"(市價單|限價單)", part)
            order_type = "MARKET" if (order_match and order_match.group(1) == "市價單") else "LIMIT"
            if not (entry and tp1_match and sl_match):
                continue
            def _grp(m):
                return float(m.group(1) or m.group(2))
            signals.append({
                "symbol": sym, "direction": direction, "score": score,
                "entry": entry,
                "tp1": _grp(tp1_match),
                "tp2": _grp(tp2_match) if tp2_match else 0,
                "tp3": _grp(tp3_match) if tp3_match else 0,
                "tp4": _grp(tp4_match) if tp4_match else 0,
                "sl": float(sl_match.group(1)),
                "timeframe": timeframe,
                "entry_grade": entry_grade,
                "order_type": order_type,
            })
        except Exception as e:
            logger.error("解析信號失敗: " + str(e))
    return signals


def register_signal(sig, watchers):
    """註冊新信號到追蹤系統"""
    sym = sig["symbol"]
    # 過期時間
    if "中線" in sig.get("timeframe", ""):
        expire_hours = 72
    else:
        expire_hours = 8
    now = datetime.now(timezone.utc)
    ACTIVE_SIGNALS[sym] = {
        "direction": sig["direction"],
        "entry": sig["entry"],
        "sl": sig["sl"],
        "tp1": sig["tp1"], "tp2": sig.get("tp2", 0),
        "tp3": sig.get("tp3", 0), "tp4": sig.get("tp4", 0),
        "watchers": list(watchers),
        "tp_hit": [],
        "status": "ACTIVE",
        "created": now.isoformat(),
        "expires": (now + timedelta(hours=expire_hours)).isoformat(),
        "score": sig.get("score", 0),
        "timeframe": sig.get("timeframe", "短線"),
        "entry_grade": sig.get("entry_grade", "C"),
        "order_type": sig.get("order_type", "MARKET"),
    }
    save_data()
    logger.info("註冊信號: " + sym + " " + sig["direction"] + " 評分 " + str(sig.get("score")) + " 等級 " + str(sig.get("entry_grade", "C")))


async def close_signal(ctx, symbol, reason_code, reason_msg, current_price=None):
    """關閉信號並通知用戶（v26 不再推播到頻道）"""
    if symbol not in ACTIVE_SIGNALS:
        return
    sig = ACTIVE_SIGNALS.pop(symbol)
    direction = sig["direction"]
    entry = sig["entry"]
    # 計算結果百分比
    cp = current_price or entry
    if reason_code == "SL_HIT":
        final_pct = -abs(entry - sig["sl"]) / entry * 100
    elif reason_code == "TP4_HIT":
        final_pct = abs(sig["tp4"] - entry) / entry * 100 * (1 if direction == "LONG" else -1)
    else:
        final_pct = (cp - entry) / entry * 100 * (1 if direction == "LONG" else -1)

    sym_short = symbol.replace("/USDT", "")
    direction_zh = "做多" if direction == "LONG" else "做空"

    if reason_code == "TP4_HIT":
        msg = "🎉 *" + sym_short + " " + direction_zh + " — 完美下車*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "已達最後止盈\n進場 `" + str(entry) + "` → 出場 `" + str(sig["tp4"]) + "`\n"
        msg += "完整收益約 *+" + str(round(final_pct, 2)) + "%*"
    elif reason_code == "SL_HIT":
        tp_hit = sig.get("tp_hit", [])
        if tp_hit:
            msg = "🛡 *" + sym_short + " — 觸及保護位*\n"
            msg += "已先達 TP" + str(max(tp_hit)) + "，剩餘倉位觸發止損\n"
            msg += "雖然回吐部分利潤，整體應仍盈利"
        else:
            msg = "🛑 *" + sym_short + " " + direction_zh + " — 觸發止損*\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "請立即出場\n進場 `" + str(entry) + "` → 止損 `" + str(sig["sl"]) + "`\n"
            msg += "本次虧損 *" + str(round(final_pct, 2)) + "%*\n\n"
            msg += "_該幣 24 小時內若再虧損將暫停推送_"
    elif reason_code == "EXPIRED":
        msg = "⏰ *" + sym_short + " — 信號失效*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "持有時間已過，建議：\n"
        msg += "  • 有獲利 → 立即移動止損守利\n"
        msg += "  • 無獲利 → 出場觀望\n"
        msg += "  • 尚未進場 → 取消掛單"
    elif reason_code == "REVERSED":
        msg = "🔄 *" + sym_short + " — 反向信號*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "偵測到高品質反向信號，原方向已關閉\n"
        msg += "新的反向信號將在下一則推送\n"
        msg += "若已進場原方向：有獲利立即出，虧損等下根 K 線"
    else:
        msg = "📌 *" + sym_short + " 信號結束*\n" + reason_msg

    # 連虧紀錄
    if reason_code == "SL_HIT" and not sig.get("tp_hit"):
        if symbol not in SYMBOL_LOSSES:
            SYMBOL_LOSSES[symbol] = []
        SYMBOL_LOSSES[symbol].append(datetime.now(timezone.utc).isoformat())
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        SYMBOL_LOSSES[symbol] = [t for t in SYMBOL_LOSSES[symbol]
                                  if datetime.fromisoformat(t) > cutoff]

    # 只通知訂閱者，不推頻道（v26）
    for chat_id in sig.get("watchers", []):
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error("通知關閉失敗 " + str(chat_id) + ": " + str(e))

    # 記錄歷史
    SIGNAL_RESULTS.append({
        "symbol": symbol, "direction": direction, "entry": entry,
        "result": reason_code, "final_pct": round(final_pct, 2),
        "tp_hit_count": len(sig.get("tp_hit", [])),
        "score": sig.get("score", 0),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    })
    save_data()


async def notify_tp_hit(ctx, symbol, tp_level, current_price):
    """通知 TP 達標（v26 不推頻道）"""
    if symbol not in ACTIVE_SIGNALS:
        return
    sig = ACTIVE_SIGNALS[symbol]
    if tp_level in sig["tp_hit"]:
        return
    sig["tp_hit"].append(tp_level)
    direction = sig["direction"]
    entry = sig["entry"]
    tp_price = sig["tp" + str(tp_level)]
    profit_pct = abs(tp_price - entry) / entry * 100
    sym_short = symbol.replace("/USDT", "")
    direction_zh = "做多" if direction == "LONG" else "做空"

    tp_messages = {
        1: ("✅", "達到 TP1 保本點", "*立即平 25% 倉位*", "止損移到成本價 `" + str(entry) + "`"),
        2: ("💰", "達到 TP2 鎖利", "*平 35% 倉位*", "止損移到 TP1 `" + str(sig.get("tp1", entry)) + "`"),
        3: ("🏆", "達到 TP3 大勝", "*平 25% 倉位*", "止損移到 TP2 `" + str(sig.get("tp2", entry)) + "`"),
        4: ("🎯", "達到 TP4 滿貫", "*平剩餘 15%*", "本輪交易圓滿結束"),
    }
    emoji, title, action, sl_advice = tp_messages[tp_level]
    msg = emoji + " *" + sym_short + " " + direction_zh + " — " + title + "*\n"
    msg += "━━━━━━━━━━━━━━━\n"
    msg += "進場 `" + str(entry) + "` → 現價 `" + str(current_price) + "`\n"
    msg += "浮盈 *+" + str(round(profit_pct, 2)) + "%*\n\n"
    msg += "📌 立即動作：" + action + "\n"
    msg += "📌 後續：" + sl_advice
    if tp_level < 4:
        remaining_tps = []
        for t in range(tp_level + 1, 5):
            if sig.get("tp" + str(t), 0) > 0:
                remaining_tps.append("TP" + str(t) + " `" + str(sig["tp" + str(t)]) + "`")
        if remaining_tps:
            msg += "\n\n🎯 剩餘：" + " · ".join(remaining_tps)

    # 只通知訂閱者
    for chat_id in sig.get("watchers", []):
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error("通知 TP 失敗 " + str(chat_id) + ": " + str(e))

    if tp_level == 4:
        await close_signal(ctx, symbol, "TP4_HIT", "達最終止盈")
    else:
        save_data()


async def check_active_signals(ctx):
    """檢查所有活躍信號的當前狀態"""
    if not ACTIVE_SIGNALS:
        return
    import aiohttp as _aiohttp
    now = datetime.now(timezone.utc)
    symbols_to_check = list(ACTIVE_SIGNALS.keys())
    try:
        async with _aiohttp.ClientSession() as session:
            tasks = [analyzer.fetch_ticker(session, sym) for sym in symbols_to_check]
            tickers = await asyncio.gather(*tasks, return_exceptions=True)
        for i, sym in enumerate(symbols_to_check):
            if sym not in ACTIVE_SIGNALS:
                continue
            sig = ACTIVE_SIGNALS[sym]
            ticker = tickers[i]
            if isinstance(ticker, Exception):
                continue
            price = float(ticker.get("lastPrice", 0))
            if price == 0:
                continue
            direction = sig["direction"]
            entry = sig["entry"]
            sl = sig["sl"]
            # 止損
            if direction == "LONG" and price <= sl:
                await close_signal(ctx, sym, "SL_HIT", "觸及止損", price)
                continue
            if direction == "SHORT" and price >= sl:
                await close_signal(ctx, sym, "SL_HIT", "觸及止損", price)
                continue
            # 止盈（從高到低）
            tp_hit = sig.get("tp_hit", [])
            for level in [4, 3, 2, 1]:
                if level in tp_hit:
                    continue
                tp_price = sig.get("tp" + str(level), 0)
                if tp_price == 0:
                    continue
                if direction == "LONG" and price >= tp_price:
                    await notify_tp_hit(ctx, sym, level, price)
                    break
                if direction == "SHORT" and price <= tp_price:
                    await notify_tp_hit(ctx, sym, level, price)
                    break
            # 過期
            if sym in ACTIVE_SIGNALS:
                try:
                    expires = datetime.fromisoformat(sig["expires"])
                    if now > expires:
                        await close_signal(ctx, sym, "EXPIRED", "信號過期", price)
                except Exception:
                    pass
    except Exception as e:
        logger.error("檢查活躍信號失敗: " + str(e))


# BTC 緊急警告（市場信息 → 推頻道）
LAST_BTC_ALERT_TIME = {"value": 0}
BTC_ALERT_THRESHOLD = 2.5

async def check_btc_emergency(ctx):
    """BTC 大幅變動警告"""
    if not ACTIVE_SIGNALS:
        return
    import aiohttp as _aiohttp
    try:
        async with _aiohttp.ClientSession() as session:
            btc_ticker = await analyzer.fetch_ticker(session, "BTC/USDT")
            btc_df = await analyzer.fetch_ohlcv(session, "BTC/USDT", "5m", 12)
        if btc_df is not None and len(btc_df) >= 6:
            recent_chg = (float(btc_df["close"].iloc[-1]) - float(btc_df["close"].iloc[-6])) / float(btc_df["close"].iloc[-6]) * 100
            now_ts = datetime.now(timezone.utc).timestamp()
            if now_ts - LAST_BTC_ALERT_TIME["value"] < 1800:
                return
            if abs(recent_chg) >= BTC_ALERT_THRESHOLD:
                LAST_BTC_ALERT_TIME["value"] = now_ts
                direction_word = "急漲" if recent_chg > 0 else "急跌"
                affected = set()
                for sym, sig in ACTIVE_SIGNALS.items():
                    for w in sig.get("watchers", []):
                        affected.add(w)
                if not affected:
                    return
                msg = "🚨 *BTC 30 分鐘" + direction_word + "* — 警示通知\n"
                msg += "━━━━━━━━━━━━━━━\n"
                msg += "30 分鐘變動 *" + str(round(recent_chg, 2)) + "%*\n"
                msg += "現價 `" + str(round(float(btc_ticker.get("lastPrice", 0)), 2)) + "`\n\n"
                msg += "📌 持倉影響\n你持有 " + str(len(ACTIVE_SIGNALS)) + " 個追蹤信號\n"
                if recent_chg < 0:
                    msg += "  • 做多：考慮緊縮止損\n"
                    msg += "  • 做空：注意止盈時機\n"
                else:
                    msg += "  • 做多：注意止盈時機\n"
                    msg += "  • 做空：考慮緊縮止損\n"
                for u in affected:
                    try:
                        await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                    except Exception:
                        pass
    except Exception as e:
        logger.error("BTC 監控失敗: " + str(e))


# 進場價接近提醒
LAST_NEAR_ENTRY_ALERT = {}

async def check_near_entry(ctx):
    """檢查活躍信號的進場價接近，提醒用戶"""
    if not ACTIVE_SIGNALS:
        return
    import aiohttp as _aiohttp
    try:
        async with _aiohttp.ClientSession() as session:
            for sym, sig in list(ACTIVE_SIGNALS.items()):
                if sig.get("tp_hit"):
                    continue
                try:
                    ticker = await analyzer.fetch_ticker(session, sym)
                    current = float(ticker.get("lastPrice", 0))
                    entry = sig.get("entry", 0)
                    if not current or not entry:
                        continue
                    dist_pct = abs(current - entry) / entry * 100
                    if dist_pct < 0.3:
                        last_alert = LAST_NEAR_ENTRY_ALERT.get(sym, 0)
                        now_ts = datetime.now(timezone.utc).timestamp()
                        if now_ts - last_alert > 1800:
                            LAST_NEAR_ENTRY_ALERT[sym] = now_ts
                            sym_short = sym.replace("/USDT", "")
                            direction_zh = "做多" if sig["direction"] == "LONG" else "做空"
                            msg = "⏰ *" + sym_short + " 即將觸及進場價*\n"
                            msg += "━━━━━━━━━━━━━━━\n"
                            msg += "現價 `" + str(current) + "`\n"
                            msg += "進場價 `" + str(entry) + "` (差距 " + str(round(dist_pct, 2)) + "%)\n\n"
                            msg += "📌 請準備：\n"
                            msg += "  • 已掛限價單 → 等待自動成交\n"
                            msg += "  • 尚未下單 → 立即準備 " + direction_zh + " 倉位"
                            for u in sig.get("watchers", []):
                                try:
                                    await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                                except Exception:
                                    pass
                except Exception:
                    continue
    except Exception as e:
        logger.error("進場價監控失敗: " + str(e))


# 反向警告
LAST_REVERSAL_ALERT = {}

async def check_signal_reversal(ctx):
    """檢查活躍信號是否出現即時反向訊號"""
    if not ACTIVE_SIGNALS:
        return
    import aiohttp as _aiohttp
    try:
        async with _aiohttp.ClientSession() as session:
            for sym, sig in list(ACTIVE_SIGNALS.items()):
                if sig.get("tp_hit"):
                    continue
                try:
                    created = datetime.fromisoformat(sig["created"])
                    age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60
                    if age_min < 15 or age_min > 240:
                        continue
                    last_alert = LAST_REVERSAL_ALERT.get(sym, 0)
                    now_ts = datetime.now(timezone.utc).timestamp()
                    if now_ts - last_alert < 3600:
                        continue
                    df = await analyzer.fetch_ohlcv(session, sym, "15m", 30)
                    if df is None or len(df) < 10:
                        continue
                    has_reversal, reasons = analyzer.kline_reversal_check(df, sig["direction"], sig["entry"])
                    if has_reversal:
                        LAST_REVERSAL_ALERT[sym] = now_ts
                        sym_short = sym.replace("/USDT", "")
                        direction_zh = "做多" if sig["direction"] == "LONG" else "做空"
                        ticker = await analyzer.fetch_ticker(session, sym)
                        current = float(ticker.get("lastPrice", 0))
                        entry = sig["entry"]
                        if sig["direction"] == "LONG":
                            change_pct = (current - entry) / entry * 100
                        else:
                            change_pct = (entry - current) / entry * 100
                        msg = "⚠️ *" + sym_short + " 反向警告*\n"
                        msg += "━━━━━━━━━━━━━━━\n"
                        msg += direction_zh + " 倉位現況：\n"
                        msg += "進場 `" + str(entry) + "` → 現價 `" + str(current) + "`\n"
                        msg += "目前 *" + ("+" if change_pct >= 0 else "") + str(round(change_pct, 2)) + "%*\n\n"
                        msg += "📌 偵測訊號：" + reasons + "\n\n"
                        msg += "📌 建議：\n"
                        if change_pct > 0:
                            msg += "  • 有浮盈 → 立即移止損鎖利\n"
                            msg += "  • 或部分平倉 50% 落袋"
                        elif change_pct > -0.5:
                            msg += "  • 未到止損 → 等下根 K 線\n"
                            msg += "  • 繼續惡化考慮主動出場"
                        else:
                            msg += "  • 浮虧較深 → 建議主動出場\n"
                            msg += "  • 不要硬撐到止損價"
                        for u in sig.get("watchers", []):
                            try:
                                await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                            except Exception:
                                pass
                except Exception as e:
                    logger.error("反向檢查失敗 " + sym + ": " + str(e))
    except Exception as e:
        logger.error("反向監控失敗: " + str(e))



def main():
    load_data()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("請設定 TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("a", cmd_analyze))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("hunter", cmd_hunter))
    app.add_handler(CommandHandler("movers", cmd_movers))
    app.add_handler(CommandHandler("kline", cmd_kline))
    app.add_handler(CommandHandler("trend", cmd_trend))
    app.add_handler(CommandHandler("sentiment", cmd_sentiment))
    app.add_handler(CommandHandler("news", cmd_sentiment))
    app.add_handler(CommandHandler("testpush", cmd_testpush))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    # ⭐ 每 5 分鐘執行黑潮船長
    app.job_queue.run_repeating(
        auto_broadcast,
        interval=PUSH_INTERVAL_MIN * 60,
        first=60
    )
    # ⭐ 每 2 分鐘檢查活躍信號（TP/SL/過期）
    async def signal_checker(ctx):
        await check_active_signals(ctx)
    app.job_queue.run_repeating(
        signal_checker,
        interval=120,
        first=30
    )
    # ⭐ 每 5 分鐘檢查 BTC 緊急狀況
    async def btc_emergency_checker(ctx):
        await check_btc_emergency(ctx)
    app.job_queue.run_repeating(
        btc_emergency_checker,
        interval=300,
        first=180
    )
    # ⭐ 每 3 分鐘檢查進場價接近
    async def near_entry_checker(ctx):
        await check_near_entry(ctx)
    app.job_queue.run_repeating(
        near_entry_checker,
        interval=180,
        first=90
    )
    # ⭐ 每 5 分鐘檢查進場後反向訊號
    async def reversal_checker(ctx):
        await check_signal_reversal(ctx)
    app.job_queue.run_repeating(
        reversal_checker,
        interval=300,
        first=300
    )

    # ⭐ v25 每 30 分鐘自動推播即時動能到頻道
    async def auto_momentum_channel(ctx):
        if not TG_CHANNEL_ID:
            return
        try:
            result = await asyncio.wait_for(analyzer.momentum_scan(), timeout=60)
            if "目前沒有顯著爆發信號" not in result:
                await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
                # 附動能圖
                if CHART_ENABLED:
                    try:
                        import aiohttp as _aio
                        async with _aio.ClientSession() as session:
                            tasks = []
                            for sym in analyzer.SCAN_POOL:
                                tasks.append(analyzer.fetch_ticker(session, sym))
                                tasks.append(analyzer.fetch_ohlcv(session, sym, "5m", 30))
                            results = await asyncio.gather(*tasks, return_exceptions=True)
                        opportunities = []
                        for i, sym in enumerate(analyzer.SCAN_POOL):
                            ticker = results[i * 2]
                            df5m = results[i * 2 + 1]
                            if isinstance(ticker, Exception) or isinstance(df5m, Exception):
                                continue
                            if df5m is None or len(df5m) < 8:
                                continue
                            try:
                                cp = float(ticker.get("lastPrice", 0))
                                if not cp: continue
                                c5 = (cp - float(df5m["close"].iloc[-2])) / float(df5m["close"].iloc[-2]) * 100
                                c15 = (cp - float(df5m["close"].iloc[-4])) / float(df5m["close"].iloc[-4]) * 100
                                c30 = (cp - float(df5m["close"].iloc[-7])) / float(df5m["close"].iloc[-7]) * 100
                                rv = float(df5m["volume"].iloc[-1])
                                av = float(df5m["volume"].tail(20).mean())
                                vr = rv / av if av > 0 else 1.0
                                if abs(c5) >= 1.0 and vr >= 1.5:
                                    opportunities.append({"symbol": sym, "chg_5m": round(c5, 2),
                                                              "chg_15m": round(c15, 2), "chg_30m": round(c30, 2),
                                                              "vol_ratio": round(vr, 1),
                                                              "intensity": abs(c5) * vr})
                            except Exception: continue
                        opportunities.sort(key=lambda x: x["intensity"], reverse=True)
                        if opportunities:
                            now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                            buf = plot_momentum_chart(opportunities, "MOMENTUM  |  " + now_str)
                            if buf:
                                await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf,
                                                            caption="⚡ *即時動能榜*",
                                                            parse_mode="Markdown")
                    except Exception as e:
                        logger.error("auto_momentum 圖失敗: " + str(e))
                logger.info("即時動能自動推播完成")
        except Exception as e:
            logger.error("即時動能自動推播失敗: " + str(e))
    app.job_queue.run_repeating(
        auto_momentum_channel,
        interval=1800,  # 30 分鐘
        first=600
    )

    # ⭐ v25 每 2 小時推播加密快訊到頻道
    async def auto_news_channel(ctx):
        if not TG_CHANNEL_ID:
            return
        try:
            import aiohttp as _aiohttp
            async with _aiohttp.ClientSession() as session:
                news = await analyzer.fetch_news(session)
                events = await analyzer.fetch_crypto_events(session)
            r = "📰 *加密快訊整點報*\n━━━━━━━━━━━━━━━\n\n"
            if news:
                score, label, items = analyzer.sentiment(news)
                r += "*📰 即時新聞*\n"
                for i, item in enumerate(items[:6], 1):
                    time_ago = analyzer.format_published(item.get("published", ""))
                    r += str(i) + ". " + item["emoji"] + " " + item["title"][:70]
                    if time_ago:
                        r += " _(" + time_ago + ")_"
                    r += "\n"
            if events:
                r += "\n*🗓 事件預告*\n"
                for ev in events[:5]:
                    title = ev.get("title", "")[:55]
                    date = ev.get("date", "")
                    typ = ev.get("type", "")
                    type_emoji = "🔓" if typ == "Unlock" else ("🚀" if typ == "Listing" else ("⚙️" if typ == "Upgrade" else "📌"))
                    r += "• " + type_emoji + " " + title
                    if date:
                        r += " `" + date + "`"
                    r += "\n"
            await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=r, parse_mode="Markdown")
            logger.info("加密快訊整點報已推播")
        except Exception as e:
            logger.error("快訊推播失敗: " + str(e))
    app.job_queue.run_repeating(
        auto_news_channel,
        interval=7200,  # 2 小時
        first=900
    )

    # ⭐ v25 每 4 小時推播市場情緒到頻道
    async def auto_sentiment_channel(ctx):
        if not TG_CHANNEL_ID:
            return
        try:
            result = await asyncio.wait_for(analyzer.get_market_sentiment(), timeout=40)
            await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
            # 附 BTC+ETH 雙圖
            if CHART_ENABLED:
                try:
                    import aiohttp as _aio
                    async with _aio.ClientSession() as session:
                        df_btc = await analyzer.fetch_ohlcv(session, "BTC/USDT", "1h", 100)
                        df_eth = await analyzer.fetch_ohlcv(session, "ETH/USDT", "1h", 100)
                    if df_btc is not None and df_eth is not None:
                        buf = plot_dual_chart(df_btc, df_eth)
                        await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf,
                                                    caption="🌐 *市場脈動*",
                                                    parse_mode="Markdown")
                except Exception as e:
                    logger.error("auto_sentiment 圖失敗: " + str(e))
            logger.info("市場情緒已推播頻道")
        except Exception as e:
            logger.error("情緒推播失敗: " + str(e))
    app.job_queue.run_repeating(
        auto_sentiment_channel,
        interval=14400,  # 4 小時
        first=1200
    )

    # ⭐ v25 每 1 小時推播趨勢總覽到頻道
    async def auto_trend_channel(ctx):
        if not TG_CHANNEL_ID:
            return
        try:
            result = await asyncio.wait_for(analyzer.trend_watch(DEFAULT_SYMBOLS), timeout=40)
            await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
            # 附趨勢分布圖
            if CHART_ENABLED:
                try:
                    import re as _re_t
                    sb_m = _re_t.search(r"強多頭.*?\((\d+)\)", result)
                    b_m = _re_t.search(r"\*📈 多頭.*?\((\d+)\)", result)
                    r_m = _re_t.search(r"震盪.*?\((\d+)\)", result)
                    bear_m = _re_t.search(r"\*📉 空頭.*?\((\d+)\)", result)
                    sbe_m = _re_t.search(r"強空頭.*?\((\d+)\)", result)
                    sb = int(sb_m.group(1)) if sb_m else 0
                    b = int(b_m.group(1)) if b_m else 0
                    r_c = int(r_m.group(1)) if r_m else 0
                    be = int(bear_m.group(1)) if bear_m else 0
                    sbe = int(sbe_m.group(1)) if sbe_m else 0
                    if sb + b + r_c + be + sbe > 0:
                        buf = plot_trend_distribution(sb, b, r_c, be, sbe)
                        await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf,
                                                    caption="🔭 *趨勢分布*",
                                                    parse_mode="Markdown")
                except Exception as e:
                    logger.error("auto_trend 圖失敗: " + str(e))
            logger.info("趨勢總覽已推播頻道")
        except Exception as e:
            logger.error("趨勢推播失敗: " + str(e))
    app.job_queue.run_repeating(
        auto_trend_channel,
        interval=3600,  # 1 小時
        first=1500
    )

    # ⭐ v25 每 1 小時推播異動掃描到頻道
    async def auto_movers_channel(ctx):
        if not TG_CHANNEL_ID:
            return
        try:
            result = await asyncio.wait_for(analyzer.detect_movers(), timeout=30)
            await ctx.bot.send_message(chat_id=TG_CHANNEL_ID, text=result, parse_mode="Markdown")
            # 附漲跌榜圖
            if CHART_ENABLED:
                try:
                    import aiohttp as _aio
                    async with _aio.ClientSession() as session:
                        tasks = [analyzer.fetch_ticker(session, s) for s in analyzer.SCAN_POOL]
                        tickers = await asyncio.gather(*tasks, return_exceptions=True)
                    data = []
                    for i, sym in enumerate(analyzer.SCAN_POOL):
                        t = tickers[i]
                        if isinstance(t, Exception):
                            continue
                        try:
                            chg = float(t.get("priceChangePercent", 0))
                            data.append((sym.replace("/USDT", ""), chg))
                        except Exception:
                            continue
                    gainers = sorted(data, key=lambda x: x[1], reverse=True)[:8]
                    losers = sorted(data, key=lambda x: x[1])[:8]
                    now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
                    buf = plot_movers_chart(gainers, losers, "MARKET MOVERS  |  " + now_str)
                    await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf,
                                                caption="📊 *24H 漲跌排行*",
                                                parse_mode="Markdown")
                except Exception as e:
                    logger.error("auto_movers 圖失敗: " + str(e))
            logger.info("異動掃描已推播頻道")
        except Exception as e:
            logger.error("異動推播失敗: " + str(e))
    app.job_queue.run_repeating(
        auto_movers_channel,
        interval=3600,  # 1 小時
        first=1800
    )
    # ⭐ 定時市場簡報（每小時檢查一次）
    app.job_queue.run_repeating(
        daily_report_check,
        interval=3600,
        first=120
    )
    logger.info("🤖 Bot v28.0 啟動 | 推播間隔 " + str(PUSH_INTERVAL_MIN) + " 分鐘")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()