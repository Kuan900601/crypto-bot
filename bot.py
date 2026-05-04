import asyncio, logging, os
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from analyzer import CryptoAnalyzer
from config import Config

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 BTC/USDT", callback_data="a_BTC/USDT"),
         InlineKeyboardButton("📊 ETH/USDT", callback_data="a_ETH/USDT")],
        [InlineKeyboardButton("📊 SOL/USDT", callback_data="a_SOL/USDT"),
         InlineKeyboardButton("📊 BNB/USDT", callback_data="a_BNB/USDT")],
        [InlineKeyboardButton("📊 XRP/USDT", callback_data="a_XRP/USDT"),
         InlineKeyboardButton("📊 DOGE/USDT", callback_data="a_DOGE/USDT")],
        [InlineKeyboardButton("🔭 趨勢總覽", callback_data="trend"),
         InlineKeyboardButton("📰 市場情緒", callback_data="news")],
        [InlineKeyboardButton("🔔 開啟自動推播", callback_data="auto_on"),
         InlineKeyboardButton("🔕 關閉推播", callback_data="auto_off")],
        [InlineKeyboardButton("📋 下單助手", callback_data="order_help"),
         InlineKeyboardButton("⚙️ 設定幣種", callback_data="settings")],
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *加密貨幣 AI 分析機器人 v2.0*\n\n"
        "🔬 *分析引擎：*\n"
        "• RSI + StochRSI + MACD背離\n"
        "• Ichimoku雲圖 + EMA多週期\n"
        "• Fibonacci支撐阻力\n"
        "• OBV量能 + ADX趨勢強度\n"
        "• 訂單簿買賣壓力\n"
        "• 恐懼貪婪指數 + 新聞情緒\n"
        "• 動態止盈止損 + Kelly倉位建議\n\n"
        "📌 *指令：*\n"
        "`/a BTC/USDT` — 分析\n"
        "`/trend` — 趨勢總覽\n"
        "`/watch BTC/USDT ETH/USDT` — 設監控\n"
        "`/order BTC/USDT LONG 95000 97500 93000` — 下單助手",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    msg = await update.message.reply_text(f"⏳ 深度分析 {symbol} 中...")
    await msg.edit_text(await analyzer.full_analysis(symbol), parse_mode="Markdown")

async def cmd_trend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    msg = await update.message.reply_text("⏳ 掃描趨勢中...")
    await msg.edit_text(await analyzer.trend_watch(symbols), parse_mode="Markdown")

async def cmd_news(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 抓取情緒中...")
    await msg.edit_text(await analyzer.get_news_summary(), parse_mode="Markdown")

async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    symbols = [s.upper() for s in ctx.args] if ctx.args else Config.DEFAULT_SYMBOLS
    ctx.bot_data.setdefault("watchers", {})[chat_id] = symbols
    await update.message.reply_text(f"✅ 監控已設定：{', '.join(symbols)}\n每 {Config.ALERT_INTERVAL_MIN} 分鐘自動推播")

async def cmd_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 5:
        await update.message.reply_text(
            "📋 *下單助手：*\n`/order 幣種 方向 進場 止盈 止損 [資金]`\n\n"
            "範例：\n`/order BTC/USDT LONG 95000 97500 93000 1000`",
            parse_mode="Markdown"); return
    try:
        symbol, direction = ctx.args[0].upper(), ctx.args[1].upper()
        entry, tp, sl = float(ctx.args[2]), float(ctx.args[3]), float(ctx.args[4])
        capital = float(ctx.args[5]) if len(ctx.args)>5 else 1000
        profit = abs(tp-entry); loss = abs(sl-entry)
        rr = round(profit/loss, 2) if loss>0 else 0
        pp = round(profit/entry*100, 2); lp = round(loss/entry*100, 2)
        pu = round(capital*pp/100, 2);   lu = round(capital*lp/100, 2)
        dir_icon = "🟢 做多" if direction=="LONG" else "🔴 做空"
        await update.message.reply_text(
            f"📋 *下單計劃 — {symbol}*\n方向：{dir_icon}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎯 進場：`{entry:,.4f}`\n"
            f"🏁 止盈：`{tp:,.4f}` ({pp:+.2f}%)\n"
            f"🛑 止損：`{sl:,.4f}` (-{lp:.2f}%)\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚖️ 風報比：`1:{rr}`\n"
            f"💵 資金 ${capital:.0f} → 盈+${pu} / 虧-${lu}\n\n"
            f"{'✅ 風報比良好' if rr>=1.5 else '⚠️ 風報比偏低，建議調整'}\n"
            f"_建議同時 /a {symbol} 確認方向_",
            parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ 格式錯誤，請確認數值正確")

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    chat_id = q.message.chat_id
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 返回", callback_data="home")]])

    if d.startswith("a_"):
        symbol = d[2:]
        await q.edit_message_text(f"⏳ 分析 {symbol} 中...")
        await q.edit_message_text(await analyzer.full_analysis(symbol), parse_mode="Markdown", reply_markup=back)
    elif d == "trend":
        await q.edit_message_text("⏳ 掃描中...")
        await q.edit_message_text(await analyzer.trend_watch(Config.DEFAULT_SYMBOLS), parse_mode="Markdown", reply_markup=back)
    elif d == "news":
        await q.edit_message_text("⏳ 抓取中...")
        await q.edit_message_text(await analyzer.get_news_summary(), parse_mode="Markdown", reply_markup=back)
    elif d == "auto_on":
        ctx.bot_data.setdefault("watchers", {})[chat_id] = Config.DEFAULT_SYMBOLS
        await q.edit_message_text(f"✅ 自動推播開啟\n{', '.join(Config.DEFAULT_SYMBOLS)}\n每 {Config.ALERT_INTERVAL_MIN} 分鐘")
    elif d == "auto_off":
        ctx.bot_data.get("watchers", {}).pop(chat_id, None)
        await q.edit_message_text("🔕 自動推播已關閉")
    elif d == "order_help":
        await q.edit_message_text(
            "📋 *下單助手*\n`/order 幣種 方向 進場 止盈 止損 [資金]`\n\n"
            "`/order BTC/USDT LONG 95000 97500 93000 1000`",
            parse_mode="Markdown")
    elif d == "settings":
        await q.edit_message_text(
            "⚙️ 自訂監控：\n`/watch BTC/USDT ETH/USDT SOL/USDT`",
            parse_mode="Markdown")
    elif d == "home":
        await q.edit_message_text("🏠 *主選單*", reply_markup=main_menu(), parse_mode="Markdown")

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if "/" in text and len(text) < 15:
        msg = await update.message.reply_text(f"⏳ 分析 {text} 中...")
        await msg.edit_text(await analyzer.full_analysis(text), parse_mode="Markdown")

async def auto_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    for chat_id, symbols in list(ctx.bot_data.get("watchers", {}).items()):
        for symbol in symbols:
            try:
                result = await analyzer.full_analysis(symbol)
                now = datetime.now(timezone.utc).strftime("%H:%M UTC")
                await ctx.bot.send_message(chat_id=chat_id,
                    text=f"🔔 *自動推播* — {now}\n\n{result}", parse_mode="Markdown")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"推播失敗 {chat_id}/{symbol}: {e}")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("請設定 TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("a",       cmd_analyze))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("trend",   cmd_trend))
    app.add_handler(CommandHandler("news",    cmd_news))
    app.add_handler(CommandHandler("watch",   cmd_watch))
    app.add_handler(CommandHandler("order",   cmd_order))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.job_queue.run_repeating(auto_broadcast, interval=Config.ALERT_INTERVAL_MIN*60, first=30)
    logger.info("🤖 Bot v2.0 啟動")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
