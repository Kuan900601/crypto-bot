
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

# 用戶狀態：等待輸入幣種或下單參數
USER_STATES = {}


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 BTC", callback_data="a_BTC/USDT"),
         InlineKeyboardButton("📊 ETH", callback_data="a_ETH/USDT"),
         InlineKeyboardButton("📊 SOL", callback_data="a_SOL/USDT")],
        [InlineKeyboardButton("📊 BNB", callback_data="a_BNB/USDT"),
         InlineKeyboardButton("📊 XRP", callback_data="a_XRP/USDT"),
         InlineKeyboardButton("📊 DOGE", callback_data="a_DOGE/USDT")],
        [InlineKeyboardButton("🔭 趨勢總覽", callback_data="trend"),
         InlineKeyboardButton("🌐 市場情緒", callback_data="sentiment")],
        [InlineKeyboardButton("🔍 自訂幣種", callback_data="custom"),
         InlineKeyboardButton("📋 下單助手", callback_data="order")],
        [InlineKeyboardButton("🔔 開啟推播", callback_data="auto_on"),
         InlineKeyboardButton("🔕 關閉推播", callback_data="auto_off")],
    ])


def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回主選單", callback_data="home")]])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *加密貨幣 AI 分析機器人*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🔬 *功能：*\n"
        "• 📊 即時技術分析（10+ 指標）\n"
        "• 🎯 進出場 / 止盈止損點位\n"
        "• 🌐 市場情緒 + 新聞時事\n"
        "• 🔭 多幣種趨勢總覽\n"
        "• 📋 下單助手（風報計算）\n"
        "• 🔔 24h 自動推播\n\n"
        "選擇下方按鈕開始 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
    try:
        result = await asyncio.wait_for(analyzer.full_analysis(symbol), timeout=20)
        await msg.edit_text(result, parse_mode="Markdown")
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ 分析超時，請再試一次")


async def cmd_trend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    msg = await update.message.reply_text("⏳ 掃描趨勢...")
    try:
        result = await asyncio.wait_for(analyzer.trend_watch(symbols), timeout=25)
        await msg.edit_text(result, parse_mode="Markdown")
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ 掃描超時")


async def cmd_sentiment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 分析市場情緒...")
    try:
        result = await asyncio.wait_for(analyzer.get_market_sentiment(), timeout=15)
        await msg.edit_text(result, parse_mode="Markdown")
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ 超時")


async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    ctx.bot_data.setdefault("watchers", {})[chat_id] = symbols
    await update.message.reply_text(
        "✅ 自動推播已開啟\n幣種：" + ", ".join(symbols) + "\n間隔：每 " + str(Config.ALERT_INTERVAL_MIN) + " 分鐘"
    )


async def cmd_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """下單助手：/order BTC/USDT LONG 95000 97500 93000 [資金]"""
    if len(ctx.args) < 5:
        await update.message.reply_text(
            "📋 *下單助手用法：*\n"
            "`/order 幣種 方向 進場 止盈 止損 [資金]`\n\n"
            "範例：\n"
            "`/order BTC/USDT LONG 95000 97500 93000 1000`\n"
            "`/order ETH/USDT SHORT 3200 3050 3350`",
            parse_mode="Markdown"
        )
        return
    await process_order(update, ctx.args)


async def process_order(update_or_query, args):
    """處理下單參數，輸出完整下單計劃"""
    try:
        symbol = args[0].upper()
        if "/" not in symbol:
            symbol = symbol + "/USDT"
        direction = args[1].upper()
        entry = float(args[2])
        tp = float(args[3])
        sl = float(args[4])
        capital = float(args[5]) if len(args) > 5 else 1000

        # 取得當下市價驗證
        try:
            ticker = await analyzer.fetch_ticker(symbol)
            current = float(ticker.get("lastPrice", entry))
        except Exception:
            current = entry

        profit = abs(tp - entry)
        loss = abs(sl - entry)
        rr = round(profit / loss, 2) if loss > 0 else 0
        pp = round(profit / entry * 100, 2)
        lp = round(loss / entry * 100, 2)
        pu = round(capital * pp / 100, 2)
        lu = round(capital * lp / 100, 2)

        if direction == "LONG":
            dir_icon = "🟢 做多 LONG"
            entry_diff = round((entry - current) / current * 100, 2)
        else:
            dir_icon = "🔴 做空 SHORT"
            entry_diff = round((current - entry) / current * 100, 2)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        report = "📋 *下單計劃確認*\n"
        report += "━━━━━━━━━━━━━━━━━━\n"
        report += "🕒 *時間：* " + now + "\n"
        report += "💎 *幣種：* `" + symbol + "`\n"
        report += "📍 *方向：* " + dir_icon + "\n\n"
        report += "*━━ 💰 當前市況 ━━*\n"
        report += "• 市價：`" + str(current) + "`\n"
        report += "• 進場價偏離：`" + str(entry_diff) + "%`\n\n"
        report += "*━━ 🎯 點位設定 ━━*\n"
        report += "🎯 進場價：`" + str(entry) + "`\n"
        report += "🏁 止盈價：`" + str(tp) + "` (盈 +" + str(pp) + "%)\n"
        report += "🛑 止損價：`" + str(sl) + "` (虧 -" + str(lp) + "%)\n\n"
        report += "*━━ 📊 風險評估 ━━*\n"
        report += "⚖️ 風險報酬比：`1 : " + str(rr) + "`\n"
        report += "💵 模擬資金 $" + str(capital) + "：\n"
        report += "  ✅ 預期盈利：+$" + str(pu) + "\n"
        report += "  ❌ 最大虧損：-$" + str(lu) + "\n\n"
        report += "*━━ 💡 建議 ━━*\n"
        if rr >= 2:
            report += "✅ 風報比優秀（≥2），建議執行"
        elif rr >= 1.5:
            report += "✅ 風報比良好（≥1.5），可執行"
        elif rr >= 1:
            report += "⚠️ 風報比偏低，建議調整止盈"
        else:
            report += "❌ 風報比過低（<1），不建議進場"

        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text(report, parse_mode="Markdown")
        else:
            await update_or_query.edit_message_text(report, parse_mode="Markdown", reply_markup=back_btn())
    except (ValueError, IndexError) as e:
        msg = "❌ 格式錯誤：" + str(e) + "\n\n正確格式：\n`/order BTC/USDT LONG 95000 97500 93000 1000`"
        if hasattr(update_or_query, 'message'):
            await update_or_query.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update_or_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_btn())


async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    chat_id = q.message.chat_id

    if d.startswith("a_"):
        symbol = d[2:]
        await q.edit_message_text("⏳ 分析 " + symbol + " 中...")
        try:
            result = await asyncio.wait_for(analyzer.full_analysis(symbol), timeout=20)
            await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        except asyncio.TimeoutError:
            await q.edit_message_text("⏱ 分析超時", reply_markup=back_btn())

    elif d == "trend":
        await q.edit_message_text("⏳ 掃描趨勢...")
        try:
            result = await asyncio.wait_for(analyzer.trend_watch(Config.DEFAULT_SYMBOLS), timeout=25)
            await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        except asyncio.TimeoutError:
            await q.edit_message_text("⏱ 超時", reply_markup=back_btn())

    elif d == "sentiment":
        await q.edit_message_text("⏳ 分析市場情緒...")
        try:
            result = await asyncio.wait_for(analyzer.get_market_sentiment(), timeout=15)
            await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        except asyncio.TimeoutError:
            await q.edit_message_text("⏱ 超時", reply_markup=back_btn())

    elif d == "custom":
        USER_STATES[chat_id] = "WAIT_SYMBOL"
        await q.edit_message_text(
            "🔍 *自訂幣種分析*\n\n"
            "請直接輸入幣種，例如：\n"
            "`BTC` 或 `BTC/USDT`\n"
            "`PEPE` `SHIB` `LINK` `AVAX`\n\n"
            "支援所有 Binance 上的幣種",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "order":
        USER_STATES[chat_id] = "WAIT_ORDER"
        await q.edit_message_text(
            "📋 *下單助手*\n\n"
            "請直接輸入下單參數：\n"
            "`幣種 方向 進場 止盈 止損 [資金]`\n\n"
            "範例：\n"
            "`BTC/USDT LONG 95000 97500 93000 1000`\n"
            "`ETH SHORT 3200 3050 3350`\n\n"
            "會自動計算風報比、預期盈虧",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d == "auto_on":
        ctx.bot_data.setdefault("watchers", {})[chat_id] = Config.DEFAULT_SYMBOLS
        await q.edit_message_text(
            "✅ 自動推播已開啟\n幣種：" + ", ".join(Config.DEFAULT_SYMBOLS) + "\n間隔：每 " + str(Config.ALERT_INTERVAL_MIN) + " 分鐘",
            reply_markup=back_btn()
        )

    elif d == "auto_off":
        ctx.bot_data.get("watchers", {}).pop(chat_id, None)
        await q.edit_message_text("🔕 自動推播已關閉", reply_markup=back_btn())

    elif d == "home":
        USER_STATES.pop(chat_id, None)
        await q.edit_message_text("🏠 *主選單*", reply_markup=main_menu(), parse_mode="Markdown")


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    state = USER_STATES.get(chat_id)

    if state == "WAIT_SYMBOL":
        USER_STATES.pop(chat_id, None)
        symbol = text.upper()
        if "/" not in symbol:
            symbol = symbol + "/USDT"
        msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
        try:
            result = await asyncio.wait_for(analyzer.full_analysis(symbol), timeout=20)
            await msg.edit_text(result, parse_mode="Markdown", reply_markup=back_btn())
        except asyncio.TimeoutError:
            await msg.edit_text("⏱ 超時", reply_markup=back_btn())
        return

    if state == "WAIT_ORDER":
        USER_STATES.pop(chat_id, None)
        args = text.split()
        if len(args) < 5:
            await update.message.reply_text(
                "❌ 參數不足，需要：\n`幣種 方向 進場 止盈 止損`",
                parse_mode="Markdown",
                reply_markup=back_btn()
            )
            return
        await process_order(update, args)
        return

    # 沒有狀態時，如果包含 / 就分析
    if "/" in text and len(text) < 15:
        symbol = text.upper()
        msg = await update.message.reply_text("⏳ 分析 " + symbol + " 中...")
        try:
            result = await asyncio.wait_for(analyzer.full_analysis(symbol), timeout=20)
            await msg.edit_text(result, parse_mode="Markdown")
        except asyncio.TimeoutError:
            await msg.edit_text("⏱ 超時")


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
    app.add_handler(CommandHandler("trend", cmd_trend))
    app.add_handler(CommandHandler("sentiment", cmd_sentiment))
    app.add_handler(CommandHandler("news", cmd_sentiment))
    app.add_handler(CommandHandler("watch", cmd_watch))
    app.add_handler(CommandHandler("order", cmd_order))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.job_queue.run_repeating(
        auto_broadcast,
        interval=Config.ALERT_INTERVAL_MIN * 60,
        first=30
    )
    logger.info("🤖 Bot v3.0 啟動")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()