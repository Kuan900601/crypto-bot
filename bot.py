#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from analyzer import CryptoAnalyzer
from config import Config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📊 分析 BTC/USDT", callback_data="analyze_BTC/USDT"),
         InlineKeyboardButton("📊 分析 ETH/USDT", callback_data="analyze_ETH/USDT")],
        [InlineKeyboardButton("📊 分析 SOL/USDT", callback_data="analyze_SOL/USDT"),
         InlineKeyboardButton("📊 分析 BNB/USDT", callback_data="analyze_BNB/USDT")],
        [InlineKeyboardButton("🔔 開啟自動推播", callback_data="auto_on"),
         InlineKeyboardButton("🔕 關閉自動推播", callback_data="auto_off")],
        [InlineKeyboardButton("📰 最新加密新聞", callback_data="news")],
    ]
    await update.message.reply_text(
        "🤖 *加密貨幣 AI 分析機器人*\n\n我會結合：\n• 📈 技術分析（RSI、MACD、布林、EMA）\n• 📰 即時新聞情緒\n• 🎯 進場/出場/止損/止盈點位\n\n輸入 `/analyze BTC/USDT` 開始分析",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("用法：`/analyze BTC/USDT`", parse_mode="Markdown")
        return
    symbol = ctx.args[0].upper()
    msg = await update.message.reply_text(f"⏳ 正在分析 {symbol}，請稍候...")
    result = await analyzer.full_analysis(symbol)
    await msg.edit_text(result, parse_mode="Markdown")

async def cmd_news(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ 抓取新聞中...")
    news = await analyzer.get_news_summary()
    await msg.edit_text(news, parse_mode="Markdown")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data.startswith("analyze_"):
        symbol = data.replace("analyze_", "")
        await query.edit_message_text(f"⏳ 正在深度分析 {symbol}...")
        result = await analyzer.full_analysis(symbol)
        await query.edit_message_text(result, parse_mode="Markdown")
    elif data == "news":
        await query.edit_message_text("⏳ 抓取新聞中...")
        news = await analyzer.get_news_summary()
        await query.edit_message_text(news, parse_mode="Markdown")
    elif data == "auto_on":
        ctx.bot_data.setdefault("watchers", {})[chat_id] = Config.DEFAULT_SYMBOLS
        await query.edit_message_text(f"✅ 自動推播已開啟\n監控：{', '.join(Config.DEFAULT_SYMBOLS)}\n每 {Config.ALERT_INTERVAL_MIN} 分鐘推播一次")
    elif data == "auto_off":
        ctx.bot_data.get("watchers", {}).pop(chat_id, None)
        await query.edit_message_text("🔕 自動推播已關閉")

async def auto_broadcast(ctx: ContextTypes.DEFAULT_TYPE):
    watchers = ctx.bot_data.get("watchers", {})
    for chat_id, symbols in list(watchers.items()):
        for symbol in symbols:
            try:
                result = await analyzer.full_analysis(symbol)
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔔 *自動推播* — {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n\n{result}",
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"推播失敗: {e}")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("請設定 TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.job_queue.run_repeating(auto_broadcast, interval=Config.ALERT_INTERVAL_MIN * 60, first=10)
    logger.info("🤖 Bot 啟動中...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
