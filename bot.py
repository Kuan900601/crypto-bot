import asyncio
import logging
import os
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from analyzer import CryptoAnalyzer
from config import Config

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

USER_STATES = {}


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 黃金獵手 (找最佳機會)", callback_data="hunter")],
        [InlineKeyboardButton("⚡ 異動掃描", callback_data="movers"),
         InlineKeyboardButton("🌐 市場情緒", callback_data="sentiment")],
        [InlineKeyboardButton("🚀 BTC", callback_data="a_BTC/USDT"),
         InlineKeyboardButton("🚀 ETH", callback_data="a_ETH/USDT"),
         InlineKeyboardButton("🚀 SOL", callback_data="a_SOL/USDT")],
        [InlineKeyboardButton("🚀 BNB", callback_data="a_BNB/USDT"),
         InlineKeyboardButton("🚀 XRP", callback_data="a_XRP/USDT"),
         InlineKeyboardButton("🚀 DOGE", callback_data="a_DOGE/USDT")],
        [InlineKeyboardButton("🔍 自訂幣種分析", callback_data="custom")],
        [InlineKeyboardButton("📊 多週期 K 線位", callback_data="kline"),
         InlineKeyboardButton("🔭 趨勢總覽", callback_data="trend")],
        [InlineKeyboardButton("🔔 開啟自動推播", callback_data="auto_on"),
         InlineKeyboardButton("🔕 關閉推播", callback_data="auto_off")],
    ])


def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主選單", callback_data="home")]])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *加密貨幣 AI 分析機器人 v5.0*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *黃金獵手* — 自動掃描 30 幣種找最佳機會\n"
        "⚡ *異動掃描* — 漲跌量榜即時掌握\n"
        "🌐 *市場情緒* — 恐懼貪婪+新聞時事\n"
        "🚀 *深度分析* — 含背離+資金費率+多空比\n"
        "🔍 *自訂幣種* — 任意 Binance 幣種\n"
        "📊 *多週期 K 線位* — 1m/15m/1H/4H/日支撐阻力\n"
        "🔭 *趨勢總覽* — 強弱分類掃描\n"
        "🔔 *自動推播* — 24h 監控\n\n"
        "選擇下方功能 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")


async def safe_run(coro, timeout=20):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return "⏱ 處理超時，請再試一次"
    except Exception as e:
        return "❌ 發生錯誤：" + str(e)


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
    result = await safe_run(analyzer.full_analysis(symbol))
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_hunter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎯 黃金獵手掃描中... (約 15 秒)")
    result = await safe_run(analyzer.golden_hunter(), timeout=45)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_movers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 掃描異動...")
    result = await safe_run(analyzer.detect_movers(), timeout=20)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_kline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    msg = await update.message.reply_text("⏳ 多週期分析中...")
    result = await safe_run(analyzer.kline_sr_analysis(symbol), timeout=25)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_trend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    msg = await update.message.reply_text("⏳ 掃描趨勢...")
    result = await safe_run(analyzer.trend_watch(symbols), timeout=30)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_sentiment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 分析市場情緒...")
    result = await safe_run(analyzer.get_market_sentiment(), timeout=15)
    await msg.edit_text(result, parse_mode="Markdown")


async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    ctx.bot_data.setdefault("watchers", {})[chat_id] = symbols
    await update.message.reply_text(
        "✅ 自動推播已開啟\n幣種：" + ", ".join(symbols)
        + "\n間隔：每 " + str(Config.ALERT_INTERVAL_MIN) + " 分鐘"
    )


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    chat_id = q.message.chat_id

    if d.startswith("a_"):
        symbol = d[2:]
        await q.edit_message_text("⏳ 深度分析 " + symbol + " 中...")
        result = await safe_run(analyzer.full_analysis(symbol))
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "hunter":
        await q.edit_message_text("🎯 黃金獵手掃描中...\n(掃描 30 幣種約 15-30 秒)")
        result = await safe_run(analyzer.golden_hunter(), timeout=45)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "movers":
        await q.edit_message_text("⏳ 掃描市場異動...")
        result = await safe_run(analyzer.detect_movers(), timeout=20)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "kline":
        USER_STATES[chat_id] = "WAIT_KLINE"
        await q.edit_message_text(
            "📊 *多週期 K 線支撐阻力*\n\n"
            "請輸入幣種，例如：\n"
            "`BTC` / `ETH` / `SOL` / `PEPE`\n\n"
            "顯示 1m/15m/1H/4H/日 各週期支撐阻力",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "trend":
        await q.edit_message_text("⏳ 掃描市場趨勢...")
        result = await safe_run(analyzer.trend_watch(Config.DEFAULT_SYMBOLS), timeout=30)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "sentiment":
        await q.edit_message_text("⏳ 分析市場情緒...")
        result = await safe_run(analyzer.get_market_sentiment(), timeout=15)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "custom":
        USER_STATES[chat_id] = "WAIT_SYMBOL"
        await q.edit_message_text(
            "🔍 *自訂幣種深度分析*\n\n"
            "請輸入幣種，例如：\n"
            "`BTC` `ETH` `PEPE` `LINK` `AVAX`\n\n"
            "支援所有 Binance 現貨幣種",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "auto_on":
        ctx.bot_data.setdefault("watchers", {})[chat_id] = Config.DEFAULT_SYMBOLS
        await q.edit_message_text(
            "✅ 自動推播已開啟\n"
            "幣種：" + ", ".join(Config.DEFAULT_SYMBOLS) + "\n"
            "間隔：每 " + str(Config.ALERT_INTERVAL_MIN) + " 分鐘",
            reply_markup=back_btn()
        )

    elif d == "auto_off":
        ctx.bot_data.get("watchers", {}).pop(chat_id, None)
        await q.edit_message_text("🔕 自動推播已關閉", reply_markup=back_btn())

    elif d == "home":
        USER_STATES.pop(chat_id, None)
        await q.edit_message_text(
            "🤖 *主選單*\n選擇功能 👇",
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
        msg = await update.message.reply_text("⏳ 深度分析 " + symbol + " 中...")
        result = await safe_run(analyzer.full_analysis(symbol))
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=back_btn())
        return

    if state == "WAIT_KLINE":
        USER_STATES.pop(chat_id, None)
        msg = await update.message.reply_text("⏳ 多週期分析 " + symbol + " 中...")
        result = await safe_run(analyzer.kline_sr_analysis(symbol), timeout=25)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=back_btn())
        return

    if "/" in text and len(text) < 15:
        msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
        result = await safe_run(analyzer.full_analysis(symbol))
        await msg.edit_text(result, parse_mode="Markdown")


async def auto_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    for chat_id, symbols in list(ctx.bot_data.get("watchers", {}).items()):
        for symbol in symbols:
            try:
                result = await asyncio.wait_for(analyzer.full_analysis(symbol), timeout=20)
                now = datetime.now(timezone.utc).strftime("%H:%M UTC")
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text="🔔 *自動推播* | " + now + "\n\n" + result,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(2)
            except Exception as e:
                logger.error("推播失敗 " + str(chat_id) + "/" + symbol + ": " + str(e))


def main():
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
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.job_queue.run_repeating(
        auto_broadcast,
        interval=Config.ALERT_INTERVAL_MIN * 60,
        first=30
    )
    logger.info("🤖 Bot v5.0 啟動")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()