
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

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

USER_STATES = {}
USER_FAVORITES = {}
PUSH_HISTORY = {}
HUNTER_WATCHERS = set()

DATA_FILE = "/tmp/bot_data.json"

DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]


def load_data():
    global USER_FAVORITES, PUSH_HISTORY, HUNTER_WATCHERS
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            USER_FAVORITES = {int(k): v for k, v in data.get("favorites", {}).items()}
            PUSH_HISTORY = {int(k): v for k, v in data.get("history", {}).items()}
            HUNTER_WATCHERS = set(int(x) for x in data.get("watchers", []))
            logger.info("載入：自選 " + str(len(USER_FAVORITES)) + " 戶，推播 " + str(len(HUNTER_WATCHERS)) + " 戶")
    except Exception as e:
        logger.info("初次啟動: " + str(e))


def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({
                "favorites": {str(k): v for k, v in USER_FAVORITES.items()},
                "history": {str(k): v for k, v in PUSH_HISTORY.items()},
                "watchers": list(HUNTER_WATCHERS)
            }, f)
    except Exception as e:
        logger.error("儲存失敗: " + str(e))


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 黃金獵手 (專業設置)", callback_data="hunter")],
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
        [InlineKeyboardButton("📜 推播歷史", callback_data="history")],
        [InlineKeyboardButton("🔔 5分推播 ON", callback_data="auto_on"),
         InlineKeyboardButton("🔕 推播 OFF", callback_data="auto_off")],
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
        "🤖 *加密貨幣 AI 分析機器人 v10.0*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *黃金獵手* — 平衡版專業設置\n"
        "  • 評分 ≥55 即推薦（勝率 60-70%）\n"
        "  • 6 項過濾 + 100 分評分系統\n"
        "  • 三段止盈 + 智能止損\n"
        "  • 中短線分流\n\n"
        "⚡ *異動掃描* — 漲跌量 TOP 5\n"
        "🌐 *市場情緒* — 中文新聞時事\n"
        "🚀 *深度分析* — 即時價 + 突破警示\n"
        "⭐ *我的自選* — 持久化儲存\n"
        "📊 *多週期 K 線位* — 支撐阻力\n"
        "🔭 *趨勢總覽* — 多空力道\n"
        "📜 *推播歷史* — 信號追蹤\n"
        "🔔 *智能推播* — 每 5 分鐘掃描\n\n"
        "_v10：平衡標準、中文新聞、5分推播_\n\n"
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
    msg = await update.message.reply_text("🎯 專業黃金獵手掃描中...")
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
        await q.edit_message_text("🎯 專業黃金獵手掃描中...\n(掃描 30 幣種約 20-30 秒)")
        result = await safe_run(analyzer.golden_hunter(), timeout=90)
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

    if "/" in text and len(text) < 15:
        msg = await update.message.reply_text("⏳ 分析 " + symbol + "...")
        result = await safe_run(analyzer.full_analysis(symbol), timeout=30)
        await msg.edit_text(result, parse_mode="Markdown")


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
        for chat_id in list(HUNTER_WATCHERS):
            try:
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text="🔔 *黃金獵手即時推播*\n\n" + result,
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
        logger.error("黃金獵手執行失敗: " + str(e))


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
    # ⭐ 每 5 分鐘執行
    app.job_queue.run_repeating(
        auto_broadcast,
        interval=PUSH_INTERVAL_MIN * 60,
        first=60
    )
    logger.info("🤖 Bot v10.0 啟動 | 推播間隔 " + str(PUSH_INTERVAL_MIN) + " 分鐘")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()