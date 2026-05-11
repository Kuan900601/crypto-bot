import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from analyzer import CryptoAnalyzer

# ⭐ 推播間隔：5 分鐘
PUSH_INTERVAL_MIN = 5

# ⭐ TG 公開頻道 ID（例如 @kuroshio_alpha，在 Railway 設環境變數 TG_CHANNEL_ID）
import os as _os
TG_CHANNEL_ID = _os.environ.get("TG_CHANNEL_ID", "")

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

DATA_FILE = "/tmp/bot_data.json"

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]


def load_data():
    global USER_FAVORITES, PUSH_HISTORY, HUNTER_WATCHERS, USER_DAILY_SCHEDULE, SIGNAL_TRACKER, USER_CAPITAL
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
            logger.info("載入：自選 " + str(len(USER_FAVORITES)) + " 戶，獵手 " + str(len(HUNTER_WATCHERS)) + " 戶，簡報 " + str(len(USER_DAILY_SCHEDULE)) + " 戶")
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
                "capital": {str(k): v for k, v in USER_CAPITAL.items()}
            }, f)
    except Exception as e:
        logger.error("儲存失敗: " + str(e))


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 黑潮船長 (專業設置)", callback_data="hunter")],
        [InlineKeyboardButton("⭐ 今日為你挑選 (TOP 1)", callback_data="todays_pick")],
        [InlineKeyboardButton("⚡ 異動掃描", callback_data="movers"),
         InlineKeyboardButton("🌐 市場情緒", callback_data="sentiment")],
        [InlineKeyboardButton("🚀 BTC", callback_data="a_BTC/USDT"),
         InlineKeyboardButton("🚀 ETH", callback_data="a_ETH/USDT"),
         InlineKeyboardButton("🚀 SOL", callback_data="a_SOL/USDT")],
        [InlineKeyboardButton("🚀 BNB", callback_data="a_BNB/USDT"),
         InlineKeyboardButton("🚀 XRP", callback_data="a_XRP/USDT"),
         InlineKeyboardButton("🚀 DOGE", callback_data="a_DOGE/USDT")],
        [InlineKeyboardButton("⭐ 我的自選", callback_data="favorites"),
         InlineKeyboardButton("🔍 自訂幣種", callback_data="custom")],
        [InlineKeyboardButton("📊 多週期 K 線位", callback_data="kline"),
         InlineKeyboardButton("🔭 趨勢總覽", callback_data="trend")],
        [InlineKeyboardButton("📜 推播歷史", callback_data="history"),
         InlineKeyboardButton("💼 倉位計算", callback_data="position_calc")],
        [InlineKeyboardButton("🔔 黑潮船長 ON", callback_data="auto_on"),
         InlineKeyboardButton("🔕 OFF", callback_data="auto_off")],
        [InlineKeyboardButton("📅 自訂定時推播", callback_data="schedule_menu")],
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
        "🤖 *加密貨幣 AI 分析機器人 v16.0*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *黑潮船長* — 專業交易設置\n"
        "  • VWAP + SuperTrend 新指標\n"
        "  • BTC 相關性分析\n"
        "  • 信號有效期追蹤\n"
        "  • 三段止盈 + 智能止損\n\n"
        "⚡ *異動掃描* — 漲跌量 TOP 5\n"
        "🌐 *市場情緒* — 中文新聞時事\n"
        "🚀 *深度分析* — 即時價 + 突破警示\n"
        "⭐ *我的自選* — 持久化儲存\n"
        "📊 *多週期 K 線位* — 支撐阻力\n"
        "🔭 *趨勢總覽* — 多空力道\n"
        "📜 *推播歷史* — 信號追蹤\n"
        "🔔 *智能推播* — 每 5 分鐘掃描\n\n"
        "_v16：自訂推播時間、加密幣事件日曆、推播內容自選_\n\n"
        "選擇下方功能 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")


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
        symbol = d[2:]
        await q.edit_message_text("⏳ 分析 " + symbol + "...")
        result = await safe_run(analyzer.full_analysis(symbol), timeout=30)
        keyboard = [[InlineKeyboardButton("⭐ 加入自選", callback_data="favadd_" + symbol),
                     InlineKeyboardButton("🏠 主選單", callback_data="home")]]
        await q.edit_message_text(result, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    elif d == "hunter":
        await q.edit_message_text("🎯 專業黑潮船長掃描中...\n(掃描 30 幣種約 20-30 秒)")
        result = await safe_run(analyzer.golden_hunter(), timeout=90)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

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

    elif d == "sentiment":
        await q.edit_message_text("⏳ 分析情緒...")
        result = await safe_run(analyzer.get_market_sentiment(), timeout=20)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

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
    # 時段問候語
    if 5 <= hour < 12:
        greeting = "🌅 早安！市場簡報"
    elif 12 <= hour < 18:
        greeting = "☀️ 午後市場簡報"
    elif 18 <= hour < 22:
        greeting = "🌆 晚間市場簡報"
    else:
        greeting = "🌙 深夜市場簡報"
    header = greeting + " (" + str(hour).zfill(2) + ":00 UTC)\n━━━━━━━━━━━━━━━━━━━━\n\n"
    # 為每個用戶組合推播內容
    for chat_id, user_types in users_to_push:
        try:
            content_parts = [header]
            if "sentiment" in user_types and "sentiment" in cached_results:
                content_parts.append(cached_results["sentiment"])
            elif "events" in user_types and "sentiment" in cached_results:
                # events 跟 sentiment 共用同一個函式（事件日曆包含在 sentiment 裡）
                content_parts.append(cached_results["sentiment"])
            if "trend" in user_types and "trend" in cached_results:
                content_parts.append(cached_results["trend"])
            if "movers" in user_types and "movers" in cached_results:
                content_parts.append(cached_results["movers"])
            content = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(content_parts)
            # 拆分長訊息
            chunks = []
            if len(content) <= 4000:
                chunks = [content]
            else:
                parts = content.split("━━━━━━━━━━━━━━━━━━━━")
                current = ""
                for p in parts:
                    if len(current) + len(p) < 3800:
                        current += p + "━━━━━━━━━━━━━━━━━━━━"
                    else:
                        if current:
                            chunks.append(current)
                        current = p + "━━━━━━━━━━━━━━━━━━━━"
                if current:
                    chunks.append(current)
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


# ⭐ 5 分鐘智能推播
async def auto_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    if not HUNTER_WATCHERS:
        return
    logger.info("5分推播：訂閱戶 " + str(len(HUNTER_WATCHERS)))
    try:
        result = await asyncio.wait_for(
            analyzer.golden_hunter(smart_filter=True),  # 過濾 ≥65 分
            timeout=90
        )
        if result is None:
            logger.info("5分推播：無 ≥65 信號，跳過")
            return
        # ⭐ 推播去重：從結果中抽取信號指紋
        # golden_hunter 結果包含 sig_hash，我們提取出來比對
        import re as _re
        # 找出所有候選的 symbol + direction 組合
        symbols_in_result = _re.findall(r"🥇 \*([A-Z]+/USDT)\*|🥈 \*([A-Z]+/USDT)\*|🥉 \*([A-Z]+/USDT)\*", result)
        directions_in_result = _re.findall(r"方向：(做多|做空)", result)
        entries_in_result = _re.findall(r"進場 `([\d.]+)`", result)
        # 為當前推播產生簡易指紋（symbol+direction+entry）
        push_signatures = []
        for i, sym_tuple in enumerate(symbols_in_result[:3]):
            sym = next((s for s in sym_tuple if s), "")
            if i < len(directions_in_result) and i < len(entries_in_result):
                dir_str = directions_in_result[i]
                entry_str = entries_in_result[i]
                sig = sym + "|" + dir_str + "|" + str(round(float(entry_str), 0))
                push_signatures.append(sig)
        # 檢查是否與最近 30 分鐘的推播重複
        now_ts = datetime.now(timezone.utc).timestamp()
        # 清理過期記錄
        expired = [h for h, t in RECENT_PUSHED.items() if now_ts - t > PUSH_DEDUP_MINUTES * 60]
        for h in expired:
            del RECENT_PUSHED[h]
        # 計算新信號數量
        new_signals = [s for s in push_signatures if s not in RECENT_PUSHED]
        if not new_signals and push_signatures:
            logger.info("5分推播：所有信號重複，跳過 (已推過: " + str(push_signatures) + ")")
            return
        # 記錄新信號
        for s in new_signals:
            RECENT_PUSHED[s] = now_ts
        logger.info("5分推播：新信號 " + str(len(new_signals)) + " 個 / 重複 " + str(len(push_signatures) - len(new_signals)) + " 個")
        # ⭐ 同步推播到 TG 公開頻道
        if TG_CHANNEL_ID:
            try:
                await ctx.bot.send_message(
                    chat_id=TG_CHANNEL_ID,
                    text=(
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "🚢 *黑潮船長 — 即時信號*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        + result +
                        "\n\n_此信號由黑潮策略 AI 系統產生_"
                    ),
                    parse_mode="Markdown"
                )
                logger.info("頻道推播成功：" + TG_CHANNEL_ID)
            except Exception as e:
                logger.error("頻道推播失敗: " + str(e))

        for chat_id in list(HUNTER_WATCHERS):
            try:
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "🚢 *黑潮船長 — 即時信號*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        + result +
                        "\n\n_此信號由黑潮策略 AI 系統產生_"
                    ),
                    parse_mode="Markdown"
                )
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
    # ⭐ 定時市場簡報（每小時檢查一次）
    app.job_queue.run_repeating(
        daily_report_check,
        interval=3600,
        first=120
    )
    logger.info("🤖 Bot v16.0 啟動 | 推播間隔 " + str(PUSH_INTERVAL_MIN) + " 分鐘")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()