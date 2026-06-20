import asyncio
import logging
import time
import os
import json
import re
import csv
import io
import aiohttp
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from analyzer import CryptoAnalyzer
# v29: chart 已合併到 analyzer
try:
    from analyzer import (plot_signal_chart, plot_simple_chart,
                            plot_movers_chart, plot_momentum_chart,
                            plot_trend_distribution, plot_dual_chart)
    CHART_ENABLED = True
except Exception as _e:
    CHART_ENABLED = False
    logging.warning("Chart 模組載入失敗: " + str(_e))

# ⭐ v40 推播間隔：3 分鐘（平衡掃描頻率與 API 配額）
PUSH_INTERVAL_MIN = 3  # ⭐ v40 平衡為 3 分鐘

# ⭐ v40 掃描鎖：含 timeout 防卡死（全域，需在 callback 用到前定義）
_HUNTER_SCANNING = {"locked": False, "locked_at": 0, "last_push": 0}

# ⭐ v48 C 級延遲：記錄最後一次 B 級以上推播時間
# 用途：C_TIER_DELAY_MIN 分鐘內若有 B 級以上推播，C 級就不推
# 一旦推 B+，重置計時；一旦推 C，也重置（避免狂推 C）
_C_TIER_GATE = {"last_high_tier_push": 0, "circuit_break_until": 0}
# ⭐ v61：C 級延遲改環境變數，預設 30 分（原寫死 4.5h，突破型 C 級被卡到噴完）
C_TIER_DELAY_MIN = float(os.getenv("C_TIER_DELAY_MIN", "30"))

# ⭐ v54 版本標識
BOT_VERSION = "v62"

# ⭐ v54 進場品質顯示：內部值 S/A/B/C/D 不變（邏輯依賴），僅在顯示層翻譯成三級中文
def entry_grade_display(grade):
    """S/A → 高品質, B/C → 一般品質, D → 低品質"""
    return {
        "S": "高品質", "A": "高品質",
        "B": "一般品質", "C": "一般品質",
        "D": "低品質",
    }.get(grade, "一般品質")

# ⭐ BingX 連結產生器
def bingx_trade_url(symbol, direction):
    """[DEPRECATED v61 P4-4] 產生 BingX 交易頁深層連結。
    交易所已切 Bybit，本函式無任何呼叫點（死碼）。暫不刪除以免連鎖壞掉，未來確認後再移除。
    symbol: BTC/USDT 格式；direction: LONG / SHORT
    """
    pair = symbol.replace("/", "-")  # BingX 用 BTC-USDT
    # BingX 永續合約交易頁
    base = "https://bingx.com/zh-tw/perpetual/" + pair
    return base

def bingx_swap_url(symbol):
    """Bybit 永續合約頁面（沿用函式名避免改動所有呼叫點）"""
    return "https://www.bybit.com/trade/usdt/" + symbol.replace("/USDT", "").replace("/", "") + "USDT"

def bingx_spot_url(symbol):
    """[DEPRECATED v61 P4-4] BingX 現貨頁面。交易所已切 Bybit，無任何呼叫點（死碼）。暫不刪除。"""
    pair = symbol.replace("/", "_")
    return "https://bingx.com/zh-tw/spot/" + pair


# ⭐ TG 頻道設定
# 一般市場資訊（異動/情緒/趨勢/動能/快訊）：@KuroshioSignal
# 黑潮船長信號專屬：https://t.me/+G1wwlviXQaE2NDRl
import os as _os
TG_CHANNEL_ID = _os.environ.get("TG_CHANNEL_ID", "@KuroshioSignal")
# 黑潮船長專屬頻道：請在 Railway 設環境變數 BLACK_HUNTER_CHANNEL=-100xxxxxxxxxx
# 步驟：1. 將 KARINA Bot 加入私人頻道並設為管理員
#       2. 取得頻道數字 ID（-100 開頭）並設定環境變數
BLACK_HUNTER_CHANNEL = _os.environ.get("BLACK_HUNTER_CHANNEL", "")

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
ADMIN_ID = 5947529357

# ⭐ v30 推播歷史：避免短時間內重複推播相似信號
# 格式：{symbol_direction: {"entry": price, "time": iso, "score": score}}
RECENT_PUSHES = {}
# ⭐ v62 P1：快速動能全體推播時間戳（小時級節流），記憶體即可
_FAST_PUSH_TIMES = []

# ⭐ v54 A 方案：Upstash Redis 雲端持久化（優先），本地檔案 fallback
# 設了 UPSTASH 兩個環境變數 → 用 Redis（永久保存，不受部署/重啟/換平台影響）
# 沒設 → 退回本地檔案（至少不崩，但重啟會丟）
import urllib.request as _urlreq

_REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
_REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
_REDIS_KEY = "bot_data"  # Redis 裡存數據用的 key
_USE_REDIS = bool(_REDIS_URL and _REDIS_TOKEN)

# 本地檔案 fallback 路徑
_DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
try:
    os.makedirs(_DATA_DIR, exist_ok=True)
    DATA_FILE = os.path.join(_DATA_DIR, "bot_data.json")
except Exception:
    DATA_FILE = "/tmp/bot_data.json"

if _USE_REDIS:
    logger.info("✅ 使用 Upstash Redis 雲端持久化（數據永久保存）")
else:
    logger.warning("⚠️ 未設定 Upstash Redis，退回本地檔案 " + DATA_FILE + "（重啟會丟失！）")


def _redis_set(value_str):
    """寫入 Redis。用命令數組格式 POST 到根端點 ["SET", key, value]，
    這是 Upstash 文檔明確支持的方式，能正確處理任意長度的 JSON 值。"""
    body = json.dumps(["SET", _REDIS_KEY, value_str]).encode("utf-8")
    req = _urlreq.Request(_REDIS_URL, data=body,
                          headers={
                              "Authorization": "Bearer " + _REDIS_TOKEN,
                              "Content-Type": "application/json"
                          })
    with _urlreq.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if "error" in result:
            raise Exception("Redis SET 失敗: " + str(result["error"]))
        if result.get("result") != "OK":
            raise Exception("Redis SET 未回傳 OK，實際回傳: " + str(result))
        return result


def _redis_get():
    """從 Redis 讀取，回傳字串或 None"""
    url = _REDIS_URL + "/get/" + _REDIS_KEY
    req = _urlreq.Request(url, headers={"Authorization": "Bearer " + _REDIS_TOKEN})
    with _urlreq.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if "error" in result:
            raise Exception("Redis GET 失敗: " + str(result["error"]))
        return result.get("result")  # Upstash 回傳 {"result": "..."}


def _pack_data():
    """把所有狀態打包成 dict（Redis 和檔案共用）"""
    return {
        "favorites": {str(k): v for k, v in USER_FAVORITES.items()},
        "history": {str(k): v for k, v in PUSH_HISTORY.items()},
        "watchers": list(HUNTER_WATCHERS),
        "daily_schedule": {str(k): v for k, v in USER_DAILY_SCHEDULE.items()},
        "signals": SIGNAL_TRACKER,
        "capital": {str(k): v for k, v in USER_CAPITAL.items()},
        "active_signals": ACTIVE_SIGNALS,
        "signal_results": SIGNAL_RESULTS[-1000:],
        "symbol_losses": SYMBOL_LOSSES,
        "recent_pushes": RECENT_PUSHES
    }


def _unpack_data(data):
    """從 dict 還原所有狀態（Redis 和檔案共用）"""
    global USER_FAVORITES, PUSH_HISTORY, HUNTER_WATCHERS, USER_DAILY_SCHEDULE, SIGNAL_TRACKER, USER_CAPITAL, ACTIVE_SIGNALS, SIGNAL_RESULTS, SYMBOL_LOSSES, RECENT_PUSHES
    USER_FAVORITES = {int(k): v for k, v in data.get("favorites", {}).items()}
    PUSH_HISTORY = {int(k): v for k, v in data.get("history", {}).items()}
    HUNTER_WATCHERS = set(int(x) for x in data.get("watchers", []))
    USER_DAILY_SCHEDULE = {int(k): v for k, v in data.get("daily_schedule", {}).items()}
    SIGNAL_TRACKER = data.get("signals", {})
    USER_CAPITAL = {int(k): v for k, v in data.get("capital", {}).items()}
    ACTIVE_SIGNALS.update(data.get("active_signals", {}))
    SIGNAL_RESULTS.extend(data.get("signal_results", []))
    SYMBOL_LOSSES.update(data.get("symbol_losses", {}))
    RECENT_PUSHES.update(data.get("recent_pushes", {}))


DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]


def load_data():
    # 優先從 Redis 讀
    if _USE_REDIS:
        try:
            raw = _redis_get()
            if raw:
                _unpack_data(json.loads(raw))
                logger.info("✅ 從 Redis 載入：自選 " + str(len(USER_FAVORITES)) + " 戶，獵手 " + str(len(HUNTER_WATCHERS)) + " 戶，追蹤中 " + str(len(ACTIVE_SIGNALS)) + " 個信號，歷史 " + str(len(SIGNAL_RESULTS)) + " 筆")
                return
            else:
                logger.warning("⚠️ Redis 回傳空值，嘗試從本地檔案恢復...")
                try:
                    with open(DATA_FILE, "r") as f:
                        content = f.read()
                    if content.strip():
                        _unpack_data(json.loads(content))
                        logger.warning("⚠️ 已從本地檔案恢復數據（Redis 為空），歷史 " + str(len(SIGNAL_RESULTS)) + " 筆")
                    else:
                        logger.info("Redis 及本地檔案皆無數據，初次啟動")
                except Exception as fe:
                    logger.info("Redis 及本地檔案皆無數據，初次啟動: " + str(fe))
                return
        except Exception as e:
            logger.error("Redis 讀取失敗，嘗試本地檔案: " + str(e))
    # Fallback：本地檔案
    try:
        with open(DATA_FILE, "r") as f:
            _unpack_data(json.load(f))
            logger.info("從本地檔案載入，歷史 " + str(len(SIGNAL_RESULTS)) + " 筆")
    except Exception as e:
        logger.info("初次啟動: " + str(e))


def _redis_health_check():
    """啟動時驗證 Redis 讀寫是否真的正常"""
    if not _USE_REDIS:
        return
    test_key = _REDIS_KEY + "_healthcheck"
    test_val = "ok_" + str(int(__import__("time").time()))
    try:
        # 寫入測試 key
        body = json.dumps(["SET", test_key, test_val]).encode("utf-8")
        req = _urlreq.Request(_REDIS_URL, data=body,
                              headers={
                                  "Authorization": "Bearer " + _REDIS_TOKEN,
                                  "Content-Type": "application/json"
                              })
        with _urlreq.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read().decode("utf-8"))
            if r.get("result") != "OK":
                raise Exception("SET 回傳非 OK: " + str(r))
        # 讀回比對
        url = _REDIS_URL + "/get/" + test_key
        req2 = _urlreq.Request(url, headers={"Authorization": "Bearer " + _REDIS_TOKEN})
        with _urlreq.urlopen(req2, timeout=10) as resp2:
            r2 = json.loads(resp2.read().decode("utf-8"))
            got = r2.get("result")
            if got != test_val:
                raise Exception("讀回值不符，期望 " + test_val + "，實際 " + str(got))
        # 刪除測試 key
        body3 = json.dumps(["DEL", test_key]).encode("utf-8")
        req3 = _urlreq.Request(_REDIS_URL, data=body3,
                               headers={
                                   "Authorization": "Bearer " + _REDIS_TOKEN,
                                   "Content-Type": "application/json"
                               })
        with _urlreq.urlopen(req3, timeout=10) as resp3:
            pass
        logger.info("✅ Redis 健康檢查通過（讀寫正常）")
    except Exception as e:
        logger.error("🔴🔴🔴 Redis 健康檢查失敗：" + str(e))


def _redis_cmd_raw(args):
    """v59：執行任意 Redis 命令（陣列格式），供讀取 auto_trader 寫入的 at:* keys 用。失敗回 None。"""
    if not _USE_REDIS:
        return None
    try:
        body = json.dumps(args).encode("utf-8")
        req = _urlreq.Request(_REDIS_URL, data=body, headers={
            "Authorization": "Bearer " + _REDIS_TOKEN,
            "Content-Type": "application/json",
        })
        with _urlreq.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("Redis 命令失敗 " + str(args[0] if args else "?") + ": " + str(e)[:120])
        return None


def _redis_get_json_key(key, default):
    """v59：讀取任意 key 並 JSON 解析；不存在或失敗回 default。"""
    r = _redis_cmd_raw(["GET", key])
    if r is None:
        return default
    val = r.get("result")
    if val is None:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def _redis_lrange_raw(key):
    """v59：讀取 list（不做 JSON 解析，逐筆回傳原始字串），失敗回空 list。"""
    r = _redis_cmd_raw(["LRANGE", key, "0", "-1"])
    if r is None:
        return []
    return r.get("result", []) or []


def save_data():
    payload = json.dumps(_pack_data())
    # 優先寫 Redis
    if _USE_REDIS:
        try:
            _redis_set(payload)
            verified = _redis_get()
            if verified and len(verified) >= len(payload) * 0.5:
                return
            else:
                actual_len = len(verified) if verified else 0
                logger.error("🔴🔴🔴 Redis 寫入驗證失敗：寫入 " + str(len(payload)) + " bytes，讀回 " + str(actual_len) + " bytes，改存本地檔案")
        except Exception as e:
            logger.error("🔴🔴🔴 Redis 儲存失敗，改存本地檔案: " + str(e))
    # Fallback：本地檔案（原子寫入）
    try:
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, "w") as f:
            f.write(payload)
        os.replace(tmp_file, DATA_FILE)
    except Exception as e:
        logger.error("儲存失敗: " + str(e))


def main_menu():
    return InlineKeyboardMarkup([
        # 第一排：核心功能（最常用）
        [InlineKeyboardButton("🌊 黑潮船長 (即時掃描)", callback_data="hunter")],
        # v61 P4-3：移除「今日為你挑選 TOP1」按鈕（與黑潮掃描重複）；callback todays_pick 仍保留可用
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
        # ⭐ v40 系統狀態
        [InlineKeyboardButton("🩺 系統狀態", callback_data="sys_status")],
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
        "🌊 *黑潮策略 — AI 量化交易助理*\n"
        "━━━━━━━━━━━━━━━\n"
        "24 小時掃描 50 個幣種，找出 *高勝率交易機會*\n"
        "每 3 分鐘高頻掃描，即時通知關鍵價位\n\n"
        "_v51：修復 consensus 崩潰（原本導致信號全被擋）_\n\n"
        "*🎯 信號分級（每級保證勝率）*\n"
        "━━━━━━━━━━━━━━━\n"
        "💎 *S 級* — 勝率 ≥ 65%（正常倉）\n"
        "🥇 *A 級* — 勝率 ≥ 58%（半倉跟單）\n"
        "🥈 *B 級* — 勝率 ≥ 54%（1/3 倉）\n"
        "🥉 *C 級* — 勝率 ≥ 51%（試水單）\n"
        "❌ 低於 51% → 完全不推播\n\n"
        "*📊 多維度勝率計算*\n"
        "• ADX 趨勢強度（基礎 47-60%）\n"
        "• 6 策略共識數（+0~+8%）\n"
        "• 進場時機等級（-3~+6%）\n"
        "• MTF 多週期共振（+0~+5%）\n"
        "• K 線確認 / Squeeze / 逆勢調整\n\n"
        "*⏰ 推播節奏控制*\n"
        "• S/A/B 級 → 即時推播\n"
        "• C 級 → 累積冷卻才推（可調，預設 30min）\n"
        "• 止損移動 → 0.3%+ 才通知（防洗版）\n\n"
        "*🧠 量化分析全項*\n"
        "• 五維度評分（趨勢/動能/結構/量能/風險）\n"
        "• 真實勝率自校準 + 進場時機\n"
        "• 智能 TP 延伸 + ATR 智能止損\n"
        "• Regime + Funding 極端反轉\n"
        "• Wyckoff + 多週期共振 + 主動退出\n\n"
        "_⚠️ 加密貨幣風險極高，僅供參考_"
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")


async def send_chart_with_caption(ctx, chat_id, df, symbol, timeframe, direction,
                                    entry, sl, tp1, tp2, tp3, tp4,
                                    support_levels, resistance_levels,
                                    caption, title_suffix="", subtitle=""):
    """發送 K 線圖 + 說明（v35 強化容錯）"""
    # v35 防呆：df 為空或太少
    if not CHART_ENABLED or df is None or len(df) < 5:
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
            title_suffix=title_suffix,
            subtitle=subtitle
        )
        # v35 檢查圖片大小
        buf.seek(0, 2)
        size = buf.tell()
        buf.seek(0)
        if size < 2000:
            logger.warning("圖片太小可能損壞 → 改純文字")
            await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            return
        short_caption = caption if len(caption) <= 1000 else caption[:1000] + "..."
        await ctx.bot.send_photo(
            chat_id=chat_id, photo=buf,
            caption=short_caption, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("附圖推播失敗: " + str(e))
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
        except Exception:
            pass


async def send_simple_chart(ctx, chat_id, df, symbol, timeframe, caption=""):
    """發送無交易計劃的 K 線圖（v35 強化容錯）"""
    if not CHART_ENABLED or df is None or len(df) < 5:
        if caption:
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            except Exception:
                pass
        return
    try:
        buf = plot_simple_chart(df, symbol, timeframe)
        buf.seek(0, 2)
        if buf.tell() < 2000:
            buf.seek(0)
            if caption:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            return
        buf.seek(0)
        short_caption = caption if len(caption) <= 1000 else caption[:1000] + "..."
        await ctx.bot.send_photo(
            chat_id=chat_id, photo=buf,
            caption=short_caption, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error("簡圖推播失敗: " + str(e))
        if caption:
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            except Exception:
                pass


async def send_chart_buf(ctx, chat_id, buf, caption=""):
    """通用：發送圖表 + caption（v35 強化容錯）"""
    # 沒圖 → 純文字
    if not buf:
        if caption:
            try:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            except Exception as e:
                logger.error("純文字推播失敗 " + str(chat_id) + ": " + str(e))
        return

    # v35 檢查圖片是否有效（最少 2KB，避免空白圖）
    try:
        # 把 BytesIO 內容檢查（不能消耗 buffer）
        buf.seek(0, 2)  # 移到尾端
        size = buf.tell()
        buf.seek(0)  # 還原
        if size < 2000:
            logger.warning("圖片太小可能損壞 (" + str(size) + " bytes) → 改純文字")
            if caption:
                await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            return
    except Exception:
        pass

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


async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        if not SIGNAL_RESULTS:
            await update.message.reply_text("目前還沒有歷史記錄")
            return
        output = io.StringIO()
        fieldnames = list(SIGNAL_RESULTS[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(SIGNAL_RESULTS)
        output.seek(0)
        filename = "signal_results_" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".csv"
        await ctx.bot.send_document(
            chat_id=update.effective_chat.id,
            document=output.read().encode("utf-8-sig"),
            filename=filename,
        )
    except Exception as e:
        await update.message.reply_text("匯出失敗：" + str(e))


async def cmd_reset_stats(update, context):
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return
    n = len(SIGNAL_RESULTS)
    SIGNAL_RESULTS.clear()
    SYMBOL_LOSSES.clear()
    save_data()
    await update.effective_message.reply_text(
        "✅ 已清空 " + str(n) + " 筆歷史戰績與連虧紀錄。\n"
        "追蹤中的信號與 BingX 持倉不受影響，從現在重新統計。"
    )


def _wilson_lb(wins, n):
    """Wilson 95% 信賴區間下界（z=1.96）"""
    if n == 0:
        return 0.0
    z = 1.96
    ph = wins / n
    center = ph + z * z / (2 * n)
    margin = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5)
    return (center - margin) / (1 + z * z / n)


def _edge_bucket_stats(results):
    """v57：給 /edge 用的單一分組統計"""
    n = len(results)
    if n == 0:
        return None
    wins_list = [r for r in results if r.get("final_pct", 0) > 0]
    losses_list = [r for r in results if r.get("final_pct", 0) <= 0]
    wins = len(wins_list)
    win_rate = wins / n * 100
    lb = _wilson_lb(wins, n) * 100
    avg_win = sum(r.get("final_pct", 0) for r in wins_list) / len(wins_list) if wins_list else 0.0
    avg_loss = sum(r.get("final_pct", 0) for r in losses_list) / len(losses_list) if losses_list else 0.0
    gross_ev = sum(r.get("final_pct", 0) for r in results) / n
    net_ev = gross_ev - 0.18
    max_consec_loss = 0
    cur = 0
    for r in results:
        if r.get("final_pct", 0) <= 0:
            cur += 1
            max_consec_loss = max(max_consec_loss, cur)
        else:
            cur = 0
    return {
        "n": n, "win_rate": win_rate, "wilson_lb": lb,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "gross_ev": gross_ev, "net_ev": net_ev,
        "max_consec_loss": max_consec_loss,
    }


async def cmd_edge(update, context):
    """v57：策略期望值驗證儀表（管理員專用，依 SIGNAL_RESULTS 統計）"""
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return

    if not SIGNAL_RESULTS:
        await update.effective_message.reply_text("尚無歷史記錄。")
        return

    overall = _edge_bucket_stats(SIGNAL_RESULTS)
    text = "📊 *策略期望值驗證（v57）*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "*整體（n=" + str(overall["n"]) + "）*\n"
    text += "勝率: " + "{:.2f}%".format(overall["win_rate"]) + "\n"
    text += "Wilson 95% 下界: " + "{:.2f}%".format(overall["wilson_lb"]) + "\n"
    text += "平均盈: " + "{:.2f}%".format(overall["avg_win"]) + "\n"
    text += "平均虧: " + "{:.2f}%".format(overall["avg_loss"]) + "\n"
    text += "毛期望值: " + "{:.2f}%".format(overall["gross_ev"]) + "/筆\n"
    text += "估計淨期望值（估計成本 0.18%）: " + "{:.2f}%".format(overall["net_ev"]) + "/筆\n"
    text += "最大連續虧損: " + str(overall["max_consec_loss"]) + " 筆\n"

    bucket_defs = [
        ("Tier", "tier"),
        ("進場品質", "entry_grade"),
        ("方向", "direction"),
        ("大盤狀態", "regime_at_entry"),
    ]
    for label, key in bucket_defs:
        groups = {}
        for r in SIGNAL_RESULTS:
            v = r.get(key)
            if v is None or v == "":
                v = "NA"
            groups.setdefault(v, []).append(r)
        sub_lines = []
        for k in sorted(groups.keys(), key=str):
            sub_results = groups[k]
            if len(sub_results) < 5:
                continue
            st = _edge_bucket_stats(sub_results)
            sub_lines.append(
                "  `" + str(k) + "`：n=" + str(st["n"])
                + " 勝率=" + "{:.2f}%".format(st["win_rate"])
                + " 毛EV=" + "{:.2f}%".format(st["gross_ev"])
            )
        if sub_lines:
            text += "\n*" + label + "分組（n≥5）*\n" + "\n".join(sub_lines) + "\n"

    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_gate_stats(update, context):
    """v57：列出 entry_context_gate 擋下記錄（管理員專用，存在記憶體、重啟會清空）"""
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return

    blocked = getattr(analyzer, "_gate_blocked", [])
    if not blocked:
        await update.effective_message.reply_text("目前無情境閘門擋下記錄（存在記憶體、重啟會清空）。")
        return

    reason_counts = {}
    for b in blocked:
        r = b.get("reason", "")
        reason_counts[r] = reason_counts.get(r, 0) + 1

    text = "🚧 *情境閘門擋下統計（v57）*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "存在記憶體、重啟會清空。共 " + str(len(blocked)) + " 筆\n\n"
    text += "*原因統計*\n"
    for r, c in sorted(reason_counts.items(), key=lambda x: -x[1]):
        text += "• " + r + "：" + str(c) + "\n"

    text += "\n*最近 10 筆*\n"
    for b in blocked[-10:][::-1]:
        text += "• " + b.get("sym", "") + " " + b.get("dir", "") + " — " + b.get("reason", "") + "\n"

    await update.effective_message.reply_text(text, parse_mode="Markdown")


def _real_pnl_bucket_stats(entries):
    """v59：給 /real_pnl 用的單一分組統計（依 closed_pnl，USDT 絕對值）"""
    n = len(entries)
    if n == 0:
        return None
    wins = [e for e in entries if e.get("closed_pnl", 0) > 0]
    losses = [e for e in entries if e.get("closed_pnl", 0) <= 0]
    total = sum(e.get("closed_pnl", 0) for e in entries)
    win_rate = len(wins) / n * 100
    avg_win = sum(e.get("closed_pnl", 0) for e in wins) / len(wins) if wins else 0.0
    avg_loss = sum(e.get("closed_pnl", 0) for e in losses) / len(losses) if losses else 0.0
    return {"n": n, "win_rate": win_rate, "total": total, "avg_win": avg_win, "avg_loss": avg_loss}


async def cmd_real_pnl(update, context):
    """v59：真實已實現損益帳本（管理員專用，讀 at:pnl_ledger）"""
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return

    if not _USE_REDIS:
        await update.effective_message.reply_text("⚠️ 未設定 Redis，無法讀取真實損益帳本。")
        return

    ledger = _redis_get_json_key("at:pnl_ledger", [])
    if not ledger:
        await update.effective_message.reply_text("尚無真實損益紀錄（at:pnl_ledger 為空｜可能尚未開過真倉或 auto_trader 未啟動）。")
        return

    now = datetime.now(timezone.utc)
    today_entries = []
    week_entries = []
    for e in ledger:
        ts = e.get("ts")
        if ts is None:
            continue
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except Exception:
            continue
        age_days = (now - dt).total_seconds() / 86400
        if age_days <= 1:
            today_entries.append(e)
        if age_days <= 7:
            week_entries.append(e)

    text = "💰 *真實損益帳本（v59）*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    for label, entries in (("今日（近24h）", today_entries), ("近7日", week_entries), ("累計", ledger)):
        st = _real_pnl_bucket_stats(entries)
        text += "\n*" + label + "*（n=" + str(st["n"] if st else 0) + "）\n"
        if not st:
            text += "無資料\n"
            continue
        text += "勝率: " + "{:.1f}%".format(st["win_rate"]) + "\n"
        text += "總已實現 PnL: " + "{:.2f}".format(st["total"]) + " USDT\n"
        text += "平均盈: " + "{:.2f}".format(st["avg_win"]) + "｜平均虧: " + "{:.2f}".format(st["avg_loss"]) + " USDT\n"

    text += "\n此為含手續費的真實數據；與 /edge 的 SIM 數據差異大時，先查滑點與部分成交。"
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_at_status(update, context):
    """v59：自動交易執行層狀態（管理員專用，全部只讀 Redis，不直連交易所）"""
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return

    enabled = os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true"
    try:
        import trader as _tr
        mode = "Bybit 測試網" if _tr.USE_SANDBOX else "🔴 真錢"
    except Exception:
        mode = "未知（trader 模組載入失敗）"

    text = "🤖 *自動交易狀態（v62）*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "AUTO_TRADE_ENABLED: " + ("✅ 開啟" if enabled else "❌ 關閉（不會下單）") + "\n"
    text += "模式: " + mode + "\n\n"

    text += "*倉位設定*\n"
    text += "本金: 固定等額 = 淨值 ÷ 倉數（v62；SIZING_MODE/RISK 已不影響下單）\n"
    text += "槓桿: " + os.getenv("AT_LEVERAGE", "20") + "x\n"
    text += "最大倉數: " + os.getenv("AT_MAX_POSITIONS", "4") + "\n"
    text += "止損上限: " + os.getenv("AT_MAX_SL_PCT", "0.035") + "\n"
    text += "允許等級: " + os.getenv("AUTO_TRADE_TIERS", "S,A,B") + "\n"

    if not _USE_REDIS:
        text += "\n⚠️ 未設定 Redis，以下執行狀態無法讀取。"
        await update.effective_message.reply_text(text, parse_mode="Markdown")
        return

    day_eq = _redis_get_json_key("at:day_equity", None)
    breaker = _redis_get_json_key("at:breaker_tripped", None)
    text += "\n*日內熔斷*\n"
    if day_eq:
        text += "今日(" + str(day_eq.get("date", "")) + ")起始淨值: " + str(day_eq.get("start_equity")) + "\n"
    else:
        text += "今日起始淨值: 無資料\n"
    text += "熔斷狀態: " + ("🛑 已觸發 @ " + str(breaker) if breaker else "✅ 未觸發") + "\n"

    pending = _redis_get_json_key("at:pending", [])
    text += "\n*限價單佇列（" + str(len(pending)) + "）*\n"
    if pending:
        for p in pending[-10:]:
            text += "• " + str(p.get("symbol", "")) + " " + str(p.get("side", "")) + " @ " + str(p.get("entry")) + "\n"
    else:
        text += "無\n"

    trades = _redis_get_json_key("at:trades", [])
    open_trades = [t for t in trades if t.get("ok") and not t.get("cleaned")]
    text += "\n*持倉中（" + str(len(open_trades)) + "）*\n"
    if open_trades:
        for t in open_trades[-10:]:
            text += ("• " + str(t.get("symbol", "")) + " " + str(t.get("side", ""))
                     + " sl_stage=" + str(t.get("sl_stage", 0)) + "\n")
    else:
        text += "無\n"

    text += "\n*最近 5 筆交易紀錄*\n"
    if trades:
        for t in trades[-5:][::-1]:
            ok = "✅" if t.get("ok") else "🔴"
            line = ok + " " + str(t.get("symbol", "")) + " " + str(t.get("side", "")) + "｜本金 " + str(t.get("margin_usdt", "-"))
            if t.get("msg"):
                line += "｜" + str(t.get("msg"))
            text += line + "\n"
    else:
        text += "無紀錄\n"

    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cmd_at_debug(update, context):
    """v60：自動交易斷鏈診斷（管理員專用，只讀 Redis 與 env，不連交易所）"""
    uid = update.effective_user.id if update.effective_user else 0
    if not ADMIN_ID or uid != ADMIN_ID:
        await update.effective_message.reply_text("此指令僅限管理員。你的 id：" + str(uid))
        return

    text = "🔧 *自動交易斷鏈診斷（v60）*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"

    # ① 環境變數體檢
    at_enabled = os.getenv("AUTO_TRADE_ENABLED", "")
    bybit_key = os.getenv("BYBIT_API_KEY", "")
    bybit_secret = os.getenv("BYBIT_API_SECRET", "")
    pyunbuf = os.getenv("PYTHONUNBUFFERED", "")
    text += "\n*① 環境變數*\n"
    text += "AUTO_TRADE_ENABLED: " + (at_enabled if at_enabled else "（未設）") + "\n"
    text += "BYBIT_API_KEY: " + ("有（" + bybit_key[:4] + "...）" if bybit_key else "❌ 無") + "\n"
    text += "BYBIT_API_SECRET: " + ("有（" + bybit_secret[:4] + "...）" if bybit_secret else "❌ 無") + "\n"
    text += "PYTHONUNBUFFERED: " + (pyunbuf if pyunbuf else "（未設）") + ("" if pyunbuf == "1" else " ⚠️建議設為 1") + "\n"

    if not _USE_REDIS:
        text += "\n⚠️ 未設定 Redis，以下執行狀態無法讀取。"
        await update.effective_message.reply_text(text)
        return

    # ② 心跳
    hb_resp = _redis_cmd_raw(["GET", "at:heartbeat"])
    hb_val = (hb_resp or {}).get("result")
    hb_age = None
    if hb_val:
        try:
            hb_dt = datetime.fromisoformat(hb_val)
            if hb_dt.tzinfo is None:
                hb_dt = hb_dt.replace(tzinfo=timezone.utc)
            hb_age = (datetime.now(timezone.utc) - hb_dt).total_seconds()
        except Exception:
            hb_age = None
    text += "\n*② 心跳*\n"
    if hb_age is None:
        text += "at:heartbeat: 無資料 🔴\n"
    else:
        flag = " 🔴 標紅：執行緒未在運行" if hb_age > 60 else " ✅"
        text += "距今 " + str(round(hb_age, 1)) + " 秒" + flag + "\n"

    # ③ signal_queue
    queue_raw = _redis_lrange_raw("signal_queue")
    queue = []
    for it in queue_raw:
        try:
            queue.append(json.loads(it))
        except Exception:
            continue
    text += "\n*③ signal_queue*（長度 " + str(len(queue_raw)) + "）\n"
    now = datetime.now(timezone.utc)
    for s in queue[-3:]:
        sym = s.get("symbol", "?")
        tier = s.get("tier", "?")
        order_type = s.get("order_type", "")
        created = s.get("created")
        age_str = "?"
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_str = str(round((now - dt).total_seconds() / 60.0, 1))
            except Exception:
                age_str = "解析失敗(" + str(created)[:20] + ")"
        text += "• " + sym + " tier=" + str(tier) + " age=" + age_str + "分 order_type=" + (order_type or "（無）") + "\n"

    # ④ processed_signals 交叉比對
    processed = _redis_get_json_key("at:processed_signals", [])
    text += "\n*④ at:processed_signals*（長度 " + str(len(processed)) + "）\n"
    for s in queue[-3:]:
        sig_id = s.get("id") or (s.get("symbol", "") + str(s.get("created", "")))
        text += "• " + sig_id + " → " + ("已處理" if sig_id in processed else "未處理") + "\n"

    # ⑤ at:last_cycle
    last_cycle = _redis_get_json_key("at:last_cycle", None)
    text += "\n*⑤ at:last_cycle*\n"
    if last_cycle:
        text += "ts: " + str(last_cycle.get("ts")) + "\n"
        text += ("queue_len: " + str(last_cycle.get("queue_len"))
                 + "｜pending_len: " + str(last_cycle.get("pending_len"))
                 + "｜open_positions: " + str(last_cycle.get("open_positions")) + "\n")
        skipped = last_cycle.get("skipped", {})
        text += "skipped: " + json.dumps(skipped, ensure_ascii=False) + "\n"
        text += "last_error: " + str(last_cycle.get("last_error")) + "\n"
    else:
        text += "無資料\n"

    # ⑤b bot 主掃描耗時（v61 P3-3 / P4-6）
    last_scan = _redis_get_json_key("bt:last_scan", None)
    text += "\n*⑤b bot 掃描耗時*\n"
    if last_scan:
        ss = last_scan.get("scan_secs")
        flag = " ⚠️>120s 可能跳輪" if (ss or 0) > 120 else ""
        text += "scan_secs: " + str(ss) + flag + "｜ts: " + str(last_scan.get("ts")) + "\n"
    else:
        text += "無資料\n"

    # ⑤c 滿倉候補（v62 P2b）
    waitlist_raw = _redis_lrange_raw("at:waitlist")
    text += "\n*⑤c at:waitlist 候補*（" + str(len(waitlist_raw)) + "）\n"
    if waitlist_raw:
        oldest_age = None
        for it in waitlist_raw:
            try:
                w = json.loads(it)
                cdt = datetime.fromisoformat(w.get("created"))
                if cdt.tzinfo is None:
                    cdt = cdt.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - cdt).total_seconds() / 60.0
                if oldest_age is None or age > oldest_age:
                    oldest_age = age
            except Exception:
                continue
        text += "最舊一筆年齡: " + (str(round(oldest_age, 1)) + " 分" if oldest_age is not None else "?") + "\n"
    else:
        text += "無\n"

    # ⑥ 限價單 / 熔斷
    pending = _redis_get_json_key("at:pending", [])
    breaker = _redis_get_json_key("at:breaker_tripped", None)
    text += "\n*⑥ 限價單 / 熔斷*\n"
    text += "at:pending（" + str(len(pending)) + "）: "
    if pending:
        text += ", ".join(str(p.get("symbol", "")) for p in pending[-5:]) + "\n"
    else:
        text += "無\n"
    text += "at:breaker_tripped: " + (str(breaker) if breaker else "未觸發") + "\n"

    # ⑥b 持倉對帳（v63b：本指令不連交易所，這裡顯示的是 auto_trader 每輪對帳後的 at:trades 狀態，
    # 並非即時重查 Bybit；若 reconcile_positions 正常運作，此清單應與 Bybit 實際持倉一致）
    trades_raw = _redis_get_json_key("at:trades", [])
    open_recs = [t for t in trades_raw if t.get("ok") and not t.get("closed")]
    recently_closed = [t for t in trades_raw if t.get("closed")]
    text += "\n*⑥b 持倉對帳*（bot 紀錄，已經過自動對帳，非即時重查 Bybit）\n"
    text += "bot 記錄持倉中（ok 且未平）: " + str(len(open_recs)) + "\n"
    for t in open_recs[-5:]:
        sym = t.get("symbol", "?")
        side = t.get("side", "?")
        entry = t.get("entry_price", "?")
        opened_at = t.get("opened_at")
        age_str = "?"
        if opened_at:
            try:
                age_str = str(round((time.time() - float(opened_at)) / 60.0, 1)) + "分"
            except Exception:
                pass
        text += "• " + sym + " " + side + " entry=" + str(entry) + " age=" + age_str + "\n"
    if recently_closed:
        last_closed = sorted(recently_closed, key=lambda t: t.get("closed_ts", 0))[-3:]
        text += "近期由對帳標記平倉（含交易所自動觸發）: " + str(len(recently_closed)) + "\n"
        for t in last_closed:
            text += ("• " + t.get("symbol", "?") + " " + str(t.get("close_reason", "?"))
                     + " price=" + str(t.get("close_price")) + " pnl=" + str(t.get("realized_pnl")) + "\n")

    # ⑦ 結論（自動推斷）
    text += "\n*⑦ 結論*\n"
    if hb_age is None or hb_age > 60:
        text += "🔴 執行緒沒在跑：查 AUTO_TRADE_ENABLED / 啟動是否掛掉\n"
    elif queue:
        recent_ids = [(s.get("id") or (s.get("symbol", "") + str(s.get("created", "")))) for s in queue[-3:]]
        if all(rid in processed for rid in recent_ids):
            text += "⚠️ 信號已被過濾，看上面 skipped 計數與 last_error\n"
        else:
            text += "ℹ️ 有未處理信號，下一輪應會嘗試下單，請稍後再查\n"
    else:
        text += "ℹ️ signal_queue 是空的：bot 端沒推進佇列，查註冊與觀察單條件\n"

    await update.effective_message.reply_text(text)


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
                async with aiohttp.ClientSession() as session:
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
        await q.edit_message_text("🎯 專業黑潮船長掃描中...\n(掃描 50 幣種約 30-60 秒)")
        # v41：手動掃描也帶 historical_results，並用 smart_filter=False 確保有訊息回傳
        # ⭐ v46 手動掃描：用戶主動要看，標準稍寬讓他看到東西
        # 但用 smart_filter=False 確保任何情況都有訊息回傳
        result = await safe_run(
            analyzer.golden_hunter(
                smart_filter=False,
                min_score=45,        # v46：手動掃描門檻 45（看到更多 B/C 級）
                historical_results=SIGNAL_RESULTS
            ),
            timeout=120
        )
        if result is None:
            result = ("📡 *手動掃描異常*\n"
                      "━━━━━━━━━━━━━━━\n"
                      "本次掃描沒有回傳結果\n\n"
                      "可能原因：\n"
                      "• API 連線問題\n"
                      "• 50 個幣全部抓取失敗\n"
                      "• 內部異常\n\n"
                      "建議：稍候再試，或檢查 Railway log")
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 為 TOP 3 信號附 K 線圖
        if CHART_ENABLED and result and "📡" in result:
            try:
                # 從結果解析 TOP 3 候選
                parsed = parse_hunter_signals(result)
                if parsed:
                    async with aiohttp.ClientSession() as session:
                        for sig in parsed[:3]:
                            sym = sig.get("symbol", "")
                            try:
                                df = await analyzer.fetch_ohlcv(session, sym, "1h", 100)
                                if df is not None:
                                    sw_res, sw_sup = analyzer.swing_sr(df)
                                    sym_short = sym.replace("/USDT", "")
                                    grade = sig.get("entry_grade", "")
                                    direction = sig.get("direction", "LONG")
                                    title_suffix = entry_grade_display(grade) if grade else ""
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
                async with aiohttp.ClientSession() as session:
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
                sb_m = re.search(r"強多頭.*?\((\d+)\)", result)
                b_m = re.search(r"\*📈 多頭.*?\((\d+)\)", result)
                r_m = re.search(r"震盪.*?\((\d+)\)", result)
                bear_m = re.search(r"\*📉 空頭.*?\((\d+)\)", result)
                sbe_m = re.search(r"強空頭.*?\((\d+)\)", result)
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
                async with aiohttp.ClientSession() as session:
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

    elif d == "multi_tf":
        # ⭐ v40 補上未實作的「多週期分析」
        await q.answer("📊 分析中...", show_alert=False)
        try:
            async with aiohttp.ClientSession() as session:
                df15m, df1h, df4h, ticker = await asyncio.gather(
                    analyzer.fetch_ohlcv(session, "BTC/USDT", "15m", 100),
                    analyzer.fetch_ohlcv(session, "BTC/USDT", "1h", 200),
                    analyzer.fetch_ohlcv(session, "BTC/USDT", "4h", 150),
                    analyzer.fetch_ticker(session, "BTC/USDT"),
                    return_exceptions=True,
                )
            if isinstance(df1h, Exception) or df1h is None:
                await q.edit_message_text("❌ 資料抓取失敗，請稍後再試",
                                            parse_mode="Markdown", reply_markup=back_btn())
                return

            sig15m = analyzer.generate_signal(df15m, 50) if not isinstance(df15m, Exception) else None
            sig1h = analyzer.generate_signal(df1h, 50)
            sig4h = analyzer.generate_signal(df4h, 50) if not isinstance(df4h, Exception) else None
            cur = float(ticker.get("lastPrice", 0)) if not isinstance(ticker, Exception) else float(df1h["close"].iloc[-1])

            text = "📊 *BTC 多週期分析*\n"
            text += "━━━━━━━━━━━━━━━\n"
            text += "💰 現價 `" + str(round(cur, 2)) + "`\n\n"

            # MTF 共振
            if sig15m and sig4h:
                mtf_state, mtf_label, _ = analyzer.mtf_resonance_grade(sig15m, sig1h, sig4h)
                text += "🎯 *共振狀態*\n" + mtf_label + "\n\n"

            # 各週期信號
            for label, sig in [("15分鐘", sig15m), ("1小時", sig1h), ("4小時", sig4h)]:
                if sig:
                    dir_zh = {"LONG": "📈 多頭", "SHORT": "📉 空頭", "NEUTRAL": "➖ 中性"}.get(sig.get("direction_en", "NEUTRAL"), "➖")
                    text += "*" + label + "*: " + dir_zh + "\n"
                    text += "  RSI `" + str(round(sig.get("rsi", 50), 1)) + "` · ADX `" + str(round(sig.get("adx", 0), 1)) + "`\n"
                    text += "  趨勢: " + sig.get("regime", "?") + "\n"
            text += "\n"

            # 市場 regime
            regime_state, regime_label, _ = analyzer.market_regime_global(None, df1h)
            text += "🌐 *整體 regime*\n" + regime_label + "\n"

            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn())
        except Exception as e:
            logger.error("multi_tf 失敗: " + str(e))
            await q.edit_message_text("❌ 分析失敗：" + str(e)[:60],
                                        parse_mode="Markdown", reply_markup=back_btn())

    elif d == "momentum":
        await q.edit_message_text("⚡ 即時動能掃描中...\n(尋找 5-15 分鐘級爆發機會)")
        result = await safe_run(analyzer.momentum_scan(), timeout=60)
        await q.edit_message_text(result, parse_mode="Markdown", reply_markup=back_btn())
        # 附動能 TOP 3 多圖（5m 級別）
        if CHART_ENABLED and "目前沒有顯著爆發信號" not in result:
            try:
                import re as _re_mom
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
                    async with aiohttp.ClientSession() as session:
                        for sym, chg in mom_coins:
                            try:
                                df = await analyzer.fetch_ohlcv(session, sym, "5m", 60)
                                if df is not None:
                                    coin_data.append({"symbol": sym, "df": df, "chg": chg})
                            except Exception:
                                continue
                    if coin_data:
                        # ⭐ v40.3 修：用 plot_momentum_chart 替代不存在的 plot_multi_coin_chart
                        # 轉換資料格式：[{symbol, df, chg}] → [{symbol, chg_5m, chg_15m, chg_30m}]
                        opps = []
                        for cd in coin_data:
                            sym = cd["symbol"]
                            df_c = cd["df"]
                            if df_c is None or len(df_c) < 10:
                                continue
                            chg_5m = cd.get("chg", 0)
                            try:
                                chg_15m = (float(df_c["close"].iloc[-1]) - float(df_c["close"].iloc[-3])) / float(df_c["close"].iloc[-3]) * 100
                                chg_30m = (float(df_c["close"].iloc[-1]) - float(df_c["close"].iloc[-6])) / float(df_c["close"].iloc[-6]) * 100
                            except Exception:
                                chg_15m = chg_5m
                                chg_30m = chg_5m
                            opps.append({"symbol": sym, "chg_5m": chg_5m, "chg_15m": chg_15m, "chg_30m": chg_30m})
                        if opps:
                            buf = plot_momentum_chart(opps, title="Momentum Breakouts (5m/15m/30m)")
                            if buf:
                                await ctx.bot.send_photo(chat_id=chat_id, photo=buf,
                                                          caption="⚡ *即時動能走勢*",
                                                          parse_mode="Markdown")
                                if TG_CHANNEL_ID:
                                    try:
                                        buf2 = plot_momentum_chart(opps, title="Momentum Breakouts (5m/15m/30m)")
                                        if buf2:
                                            await ctx.bot.send_photo(chat_id=TG_CHANNEL_ID, photo=buf2,
                                                                      caption="⚡ *即時動能走勢*",
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
                async with aiohttp.ClientSession() as session:
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
            try:
                async with aiohttp.ClientSession() as session:
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
                # v55 修：用 .get 容錯，缺字段的信號跳過，不拖垮整個清單
                _dir = sig.get("direction")
                _entry = sig.get("entry")
                if not _dir or not _entry:
                    continue
                direction = "做多 🟢" if _dir == "LONG" else "做空 🔴"
                tp_hit = sig.get("tp_hit", [])
                tp_status = "✅TP" + ",".join(str(t) for t in tp_hit) if tp_hit else "進行中"
                try:
                    created = datetime.fromisoformat(sig.get("created", ""))
                    age = now - created
                    age_str = str(int(age.total_seconds() / 3600)) + "h前"
                except Exception:
                    age_str = ""
                sym_short = sym.replace("/USDT", "")
                text += "• *" + sym_short + "* " + direction + "\n"
                text += "  進場 `" + str(_entry) + "` 止損 `" + str(sig.get("sl", "?")) + "`\n"
                text += "  狀態 " + tp_status + " | 評分 `" + str(sig.get("score", "?")) + "` | " + age_str + "\n"
                kb_rows.append([
                    InlineKeyboardButton("📱 " + sym_short + " 開 Bybit", url=bingx_swap_url(sym)),
                    InlineKeyboardButton("📋 參數", callback_data="copy_" + sym.replace("/", "_"))
                ])
            kb_rows.append([InlineKeyboardButton("🏠 返回主選單", callback_data="home")])
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))

    elif d == "stats":
        if not SIGNAL_RESULTS:
            text = "📊 *歷史戰績*\n\n暫無已關閉信號的歷史數據"
        else:
            total = len(SIGNAL_RESULTS)
            wins = [r for r in SIGNAL_RESULTS if r.get("is_win", False) or r.get("final_pct", 0) > 0]
            losses = [r for r in SIGNAL_RESULTS if not (r.get("is_win", False) or r.get("final_pct", 0) > 0)]
            win_rate = (len(wins) / total * 100) if total > 0 else 0
            avg_pct = sum(r.get("final_pct", 0) for r in SIGNAL_RESULTS) / total if total > 0 else 0
            win_pcts = [r.get("final_pct", 0) for r in wins]
            loss_pcts = [abs(r.get("final_pct", 0)) for r in losses]
            avg_win = (sum(win_pcts) / len(win_pcts)) if win_pcts else 0
            avg_loss = (sum(loss_pcts) / len(loss_pcts)) if loss_pcts else 0
            real_ev = (win_rate / 100 * avg_win - (1 - win_rate / 100) * avg_loss)

            text = "📊 *歷史戰績* (" + str(total) + " 筆)\n"
            text += "━━━━━━━━━━━━━━━\n"
            text += "🎯 *總體勝率* `" + str(round(win_rate, 1)) + "%`\n"
            text += "💵 平均盈利 `+" + str(round(avg_win, 2)) + "%` · 平均虧損 `-" + str(round(avg_loss, 2)) + "%`\n"
            text += "📈 實際期望值 `" + ("+" if real_ev >= 0 else "") + str(round(real_ev, 2)) + "%/筆`\n"
            text += "🏆 勝場 `" + str(len(wins)) + "` · 敗場 `" + str(len(losses)) + "`\n\n"

            # ⭐ v38 各 tier 勝率
            text += "*🎖 各等級勝率*\n"
            for tier_name, tier_emoji in [("S", "💎"), ("A", "🥇"), ("B", "🥈"), ("C", "🥉")]:
                tier_results = [r for r in SIGNAL_RESULTS if r.get("tier") == tier_name]
                if tier_results:
                    tier_wins = [r for r in tier_results if r.get("is_win", False) or r.get("final_pct", 0) > 0]
                    tier_wr = len(tier_wins) / len(tier_results) * 100
                    text += tier_emoji + " " + tier_name + " 級 `" + str(round(tier_wr, 1)) + "%` (" + str(len(tier_wins)) + "/" + str(len(tier_results)) + ")\n"
            text += "\n"

            # ⭐ v38 自動保護模式狀態
            protection_mode, protection_reason = analyzer.auto_protection_mode(SIGNAL_RESULTS)
            mode_emoji = {"DEFENSIVE": "🛡", "AGGRESSIVE": "🚀", "NORMAL": "⚖️"}.get(protection_mode, "")
            text += "*當前模式*: " + mode_emoji + " " + protection_reason + "\n\n"

            text += "*最近 5 筆*\n"
            for r in SIGNAL_RESULTS[-5:][::-1]:
                pct = r.get("final_pct", 0)
                is_w = r.get("is_win", False) or pct > 0
                emoji = "✅" if is_w else "❌"
                tier_e = {"S": "💎", "A": "🥇", "B": "🥈", "C": "🥉"}.get(r.get("tier", "B"), "")
                pct_str = "+" + str(pct) if pct >= 0 else str(pct)
                text += emoji + " " + tier_e + " *" + r.get("symbol", "?").replace("/USDT", "") + "* " + pct_str + "%\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn())

    elif d == "sys_status":
        # ⭐ v40 系統狀態查詢
        now_ts = time.time()
        last_push = _HUNTER_SCANNING.get("last_push", 0)
        locked = _HUNTER_SCANNING.get("locked", False)
        locked_at = _HUNTER_SCANNING.get("locked_at", 0)

        text = "🩺 *系統狀態檢查*\n"
        text += "━━━━━━━━━━━━━━━\n\n"

        # 推播間隔
        text += "*⏱ 掃描設定*\n"
        text += "• 推播間隔: `" + str(PUSH_INTERVAL_MIN) + " 分鐘`\n"
        text += "• 掃描幣種: `" + str(len(analyzer.SCAN_POOL)) + " 個`\n\n"

        # 最後推播時間
        text += "*📡 推播狀態*\n"
        if last_push > 0:
            mins_ago = int((now_ts - last_push) / 60)
            if mins_ago < 60:
                text += "• 上次推播: `" + str(mins_ago) + " 分鐘前`\n"
            elif mins_ago < 1440:
                text += "• 上次推播: `" + str(mins_ago // 60) + " 小時 " + str(mins_ago % 60) + " 分前`\n"
            else:
                text += "• 上次推播: `" + str(mins_ago // 1440) + " 天前` ⚠️\n"
        else:
            text += "• 上次推播: `從未` (剛啟動或無資料)\n"

        # 掃描鎖狀態
        if locked:
            lock_mins = int((now_ts - locked_at) / 60)
            text += "• 掃描鎖: 🔒 鎖定中 (" + str(lock_mins) + " 分鐘)\n"
            if lock_mins > 5:
                text += "  ⚠️ 鎖過久，下次掃描會自動重置\n"
        else:
            text += "• 掃描鎖: 🔓 空閒\n"
        text += "\n"

        # 訂閱者狀態
        text += "*👥 訂閱狀態*\n"
        text += "• 私訊訂閱: `" + str(len(HUNTER_WATCHERS)) + " 人`\n"
        if BLACK_HUNTER_CHANNEL:
            text += "• 黑潮頻道: ✅ 已連結\n"
        else:
            text += "• 黑潮頻道: ❌ 未連結\n"
        text += "\n"

        # 活躍信號
        text += "*🎯 活躍信號*\n"
        text += "• 追蹤中: `" + str(len(ACTIVE_SIGNALS)) + " 個`\n"
        text += "• 歷史記錄: `" + str(len(SIGNAL_RESULTS)) + " 筆`\n\n"

        # 保護模式
        protection_mode, protection_reason = analyzer.auto_protection_mode(SIGNAL_RESULTS)
        mode_emoji = {"DEFENSIVE": "🛡", "AGGRESSIVE": "🚀", "NORMAL": "⚖️"}.get(protection_mode, "")
        text += "*🤖 當前模式*\n"
        text += "• " + mode_emoji + " " + protection_reason + "\n\n"

        # 動態門檻
        adaptive_adj = analyzer.adaptive_threshold(SIGNAL_RESULTS[-20:] if SIGNAL_RESULTS else [])
        dyn_score = max(45, 55 + adaptive_adj)
        if protection_mode == "DEFENSIVE":
            dyn_score = max(dyn_score, 65)
        text += "*📊 當前推播門檻*\n"
        text += "• 評分門檻: `≥ " + str(dyn_score) + "` 分\n"

        # v48 C 級冷卻狀態
        last_high = _C_TIER_GATE.get("last_high_tier_push", 0)
        if last_high > 0:
            hrs_since = (now_ts - last_high) / 3600
            _c_delay_h = C_TIER_DELAY_MIN / 60.0
            if hrs_since < _c_delay_h:
                remaining = _c_delay_h - hrs_since
                text += "• C 級冷卻: 🟡 還需 `" + str(round(remaining * 60, 0)) + "min`\n"
            else:
                text += "• C 級冷卻: ✅ 已過，下次有 C 會推\n"
        else:
            text += "• C 級冷卻: 🆕 未啟用\n"

        # 健康評估
        text += "\n*🏥 健康評估*\n"
        issues = []
        if last_push > 0 and (now_ts - last_push) / 3600 > 12:
            issues.append("⚠️ 超過 12 小時無推播")
        if locked and (now_ts - locked_at) / 60 > 10:
            issues.append("⚠️ 掃描鎖卡死")
        if len(HUNTER_WATCHERS) == 0 and not BLACK_HUNTER_CHANNEL:
            issues.append("⚠️ 無訂閱者，不會推播")
        if not issues:
            text += "✅ 系統運作正常\n"
        else:
            for i in issues:
                text += i + "\n"

        # 強制觸發按鈕
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 立即執行掃描", callback_data="force_scan")],
            [InlineKeyboardButton("🔄 重置掃描鎖", callback_data="reset_lock")],
            [InlineKeyboardButton("🏠 返回主選單", callback_data="home")],
        ])
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)

    elif d == "force_scan":
        # 強制執行掃描
        await q.answer("🚀 正在執行掃描...", show_alert=False)
        await q.edit_message_text(
            "🚀 *強制掃描已啟動*\n\n"
            "結果會在約 30 秒內推送\n"
            "請稍候...",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )
        # 重置鎖
        _HUNTER_SCANNING["locked"] = False
        # 異步觸發
        asyncio.create_task(auto_broadcast(ctx))

    elif d == "reset_lock":
        # 重置掃描鎖
        _HUNTER_SCANNING["locked"] = False
        _HUNTER_SCANNING["locked_at"] = 0
        await q.answer("✅ 掃描鎖已重置", show_alert=True)
        await q.edit_message_text(
            "✅ *掃描鎖已重置*\n\n"
            "下次掃描週期會正常執行\n"
            "或點「立即執行掃描」立刻試試",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )

    elif d.startswith("copy_"):
        sym = d[5:].replace("_", "/")
        if sym not in ACTIVE_SIGNALS:
            await q.answer("⚠️ 此信號已過期或已關閉", show_alert=True)
            return
        sig = ACTIVE_SIGNALS[sym]
        # v55 修：缺關鍵字段時告知用戶而非崩潰
        if not sig.get("direction") or not sig.get("entry") or not sig.get("sl"):
            await q.answer("⚠️ 此信號資料不完整，請等下一輪掃描", show_alert=True)
            return
        sym_short = sym.replace("/USDT", "")
        direction_zh = "做多/Long" if sig.get("direction") == "LONG" else "做空/Short"

        msg = "📋 *" + sym_short + " 下單參數*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "請在 Bybit 中設定以下參數：\n\n"
        msg += "🔸 *交易對*：`" + sym.replace("/", "-") + "`\n"
        msg += "🔸 *方向*：" + direction_zh + "\n"
        msg += "🔸 *進場價*：`" + str(sig.get("entry")) + "`\n"
        msg += "🔸 *止損價*：`" + str(sig.get("sl")) + "`\n\n"
        msg += "*📍 階梯止盈設定*\n"
        if sig.get("tp1", 0) > 0:
            msg += "TP1：`" + str(sig.get("tp1")) + "` 平 40%\n"
        if sig.get("tp2", 0) > 0:
            msg += "TP2：`" + str(sig["tp2"]) + "` 平 35%\n"
        if sig.get("tp3", 0) > 0:
            msg += "TP3：`" + str(sig["tp3"]) + "` 平 25%\n"
        msg += "\n*💡 Bybit 設定步驟*\n"
        msg += "1️⃣ 開啟 Bybit 該幣交易頁\n"
        msg += "2️⃣ 選擇 *合約* → 設定槓桿\n"
        if sig.get("order_type") == "LIMIT":
            msg += "3️⃣ 選擇 *限價* → 填入進場價\n"
        else:
            msg += "3️⃣ 選擇 *市價* 即可\n"
        msg += "4️⃣ 下單時勾選 *止損/止盈*\n"
        msg += "5️⃣ 分別填入上方 TP/SL 數值\n\n"
        msg += "_長按上方的價格可以直接複製_\n"
        msg += "_確認後回到 TG 讓我幫你追蹤_"

        # 加入返回按鈕和 Bybit 連結
        url = "https://www.bybit.com/trade/usdt/" + sym.replace("/USDT", "") + "USDT"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 開啟 Bybit " + sym_short, url=url)],
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
    """3 分鐘自動推播黑潮船長機會（v40）"""
    # ⭐ v40.3 先檢查鎖卡死，再檢查訂閱者
    # 避免「無訂閱者 + 鎖卡死」場景永久卡死
    now_ts = time.time()
    _scan_started = now_ts  # v61：記錄本輪掃描耗時
    if _HUNTER_SCANNING["locked"]:
        if now_ts - _HUNTER_SCANNING["locked_at"] > 180:  # v61：鎖 timeout 300→180s
            logger.warning("⚠️ 掃描鎖卡住超過 3 分鐘，強制重置")
            _HUNTER_SCANNING["locked"] = False
        else:
            logger.info("上一輪掃描中，跳過此輪")
            return

    if not HUNTER_WATCHERS and not BLACK_HUNTER_CHANNEL:
        return

    _HUNTER_SCANNING["locked"] = True
    _HUNTER_SCANNING["locked_at"] = now_ts

    # v40 強制推播保底：超過 6 小時沒推就降低門檻
    hours_since_push = (now_ts - _HUNTER_SCANNING["last_push"]) / 3600 if _HUNTER_SCANNING["last_push"] > 0 else 999
    if hours_since_push > 6:
        logger.warning("⚠️ 已 " + str(round(hours_since_push, 1)) + " 小時沒推播，啟動保底模式")

    logger.info("3分推播：訂閱戶 " + str(len(HUNTER_WATCHERS)) + "，活躍信號 " + str(len(ACTIVE_SIGNALS)))
    try:
        # ⭐ 先檢查活躍信號是否觸及 TP/SL/過期（通知用戶）
        await check_active_signals(ctx)
        # ⭐ v32 自適應門檻：根據近期勝率動態調整
        adaptive_adj = analyzer.adaptive_threshold(SIGNAL_RESULTS[-20:] if SIGNAL_RESULTS else [])

        # ⭐ v46 階梯式降級：根據「多久沒推」自動調整
        # 階段 1: 0-2 小時 = 職業標準
        # 階段 2: 2-4 小時 = 略放寬
        # 階段 3: 4-8 小時 = 較寬鬆
        # 階段 4: 8+ 小時 = 強制保底
        if hours_since_push <= 2:
            dynamic_min_score = max(55, 60 + adaptive_adj)  # 階段 1
            stage_label = "PRO"
        elif hours_since_push <= 4:
            dynamic_min_score = max(50, 55 + adaptive_adj)  # 階段 2
            stage_label = "BALANCED"
        elif hours_since_push <= 8:
            dynamic_min_score = max(45, 50 + adaptive_adj)  # 階段 3
            stage_label = "LOOSE"
        else:
            dynamic_min_score = 40  # 階段 4：強制保底
            stage_label = "FALLBACK"

        # ⭐ v38 自動保護模式（在階梯之上微調）
        protection_mode, protection_reason = analyzer.auto_protection_mode(SIGNAL_RESULTS)

        # ⭐ v53 熔斷：連虧 8+ 暫停 6 小時，到點自動恢復（暫時停用）
        if False and protection_mode == "CIRCUIT_BREAK":
            cb_until = _C_TIER_GATE.get("circuit_break_until", 0)
            if cb_until == 0:
                _C_TIER_GATE["circuit_break_until"] = now_ts + 6 * 3600
                logger.info("🚨 熔斷啟動：暫停推播 6 小時")
                _HUNTER_SCANNING["locked"] = False
                return
            elif now_ts < cb_until:
                logger.info("🚨 熔斷中：剩 " + str(round((cb_until - now_ts) / 3600, 1)) + "h")
                _HUNTER_SCANNING["locked"] = False
                return
            else:
                _C_TIER_GATE["circuit_break_until"] = 0
                logger.info("✅ 熔斷自動解除，恢復推播")
        else:
            _C_TIER_GATE["circuit_break_until"] = 0   # 非熔斷狀態清除計時

        # ⭐ v53 注入真實歷史，讓分析器的勝率校準看得到實績
        analyzer._external_results = SIGNAL_RESULTS

        if protection_mode == "DEFENSIVE":
            # 防守模式：階梯 1-2 提高，3-4 不調（避免完全沒信號）
            if stage_label in ("PRO", "BALANCED"):
                dynamic_min_score = max(dynamic_min_score, 65)
            logger.info("🛡 防守模式：" + protection_reason)
        elif protection_mode == "AGGRESSIVE":
            dynamic_min_score = max(dynamic_min_score - 5, 40)
            logger.info("🚀 積極模式：" + protection_reason)

        logger.info("v46 門檻: " + str(dynamic_min_score) + " | 階梯: " + stage_label +
                    " | 距上次推: " + str(round(hours_since_push, 1)) + "h | 模式: " + protection_mode)
        result = await asyncio.wait_for(
            analyzer.golden_hunter(
                smart_filter=True,
                min_score=dynamic_min_score,
                historical_results=SIGNAL_RESULTS  # ⭐ v38 傳入歷史
            ),
            timeout=90
        )
        if result is None:
            # ⭐ v41：即使 golden_hunter 回 None 也要通知保底（避免完全靜默）
            now_str = datetime.now(timezone.utc).strftime("%H:%M UTC")
            diag_msg = (
                "📡 *黑潮船長 — " + now_str + "*\n"
                "━━━━━━━━━━━━━━━\n"
                "本輪掃描異常（無回傳）\n"
                "可能原因：\n"
                "• API 暫時限流\n"
                "• 網路斷線\n"
                "• 50 個幣全部抓取失敗\n\n"
                "_系統會在下次掃描自動重試_"
            )
            # 只在 6 小時保底時主動推診斷（避免每 3 分鐘狂推）
            if hours_since_push > 6:
                targets = list(HUNTER_WATCHERS)
                if BLACK_HUNTER_CHANNEL:
                    targets.append(BLACK_HUNTER_CHANNEL)
                for t in targets:
                    try:
                        await ctx.bot.send_message(chat_id=t, text=diag_msg, parse_mode="Markdown")
                    except Exception:
                        pass
                _HUNTER_SCANNING["last_push"] = time.time()  # 重置計時
            logger.warning("3分推播：golden_hunter 回傳 None")
            return
        # ⭐ v54 完整重構：主路徑完全使用結構化 plan，不經過任何文字反解析
        # entry_grade/rr1/win_rate 全部是真值；三種情況精確區分：
        #   ready=True + 有資料 → 正常使用
        #   ready=True + 空     → 本輪無機會（正常，靜默結束）
        #   ready=False         → analyzer 異常未正常掛載（安全網：警告 + 回退 regex 兜底）
        last_plans = getattr(analyzer, "_last_plans", None)
        plans_ready = getattr(analyzer, "_last_plans_ready", False)

        if plans_ready:
            structured = list((last_plans or {}).values())
            valid = [s for s in structured
                     if s.get("entry") and s.get("sl") and s.get("tp1")]
            parsed_signals = valid
            if valid:
                logger.info("v54 結構化 plan: " + str(len(valid)) + " 筆")
            else:
                logger.info("v54 本輪無機會（結構化正常，candidates 為空）")
        else:
            # 安全網：analyzer 未正常掛載（異常或舊版），回退 regex，並警告
            logger.warning("⚠️ v54 結構化未就緒（analyzer 異常？），啟用 regex 安全網")
            parsed_signals = parse_hunter_signals(result)
            logger.info("v54 安全網 regex 解析: " + str(len(parsed_signals)) + " 筆")

        # ⭐ 冷卻機制：過濾掉已有活躍信號的幣種
        filtered_signals = []
        skipped_reasons = []
        for sig in parsed_signals:
            sym = sig.get("symbol", "")
            # v47 修：若該 symbol 已有 entered 信號 → 跳過（不推同 symbol 新信號）
            existing = ACTIVE_SIGNALS.get(sym)
            if existing and existing.get("entered", False):
                logger.info("跳過 " + sym + " 新信號（已有 entered 同 symbol 信號）")
                continue
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
            # ⭐ v30 相似度檢查：30 分鐘內同幣同方向且進場價接近 → 跳過
            key = sym + "_" + sig.get("direction", "")
            now = datetime.now(timezone.utc)
            if key in RECENT_PUSHES:
                last = RECENT_PUSHES[key]
                try:
                    last_time = datetime.fromisoformat(last["time"])
                    time_diff = (now - last_time).total_seconds() / 60  # 分鐘
                    last_entry = last.get("entry", 0)
                    new_entry = sig.get("entry", 0)
                    if last_entry > 0:
                        price_diff_pct = abs(new_entry - last_entry) / last_entry * 100
                    else:
                        price_diff_pct = 999
                    # 30 分鐘內，進場價差距 < 1.5% → 認為是相似信號，跳過
                    if time_diff < 30 and price_diff_pct < 1.5:  # v38 維持 30 分鐘冷卻
                        skipped_reasons.append(sym + " 30分內已推相似信號 (差 " + str(round(price_diff_pct, 2)) + "%)")
                        continue
                except Exception:
                    pass

            # ⭐ v36 倉位集中風險檢查
            try:
                is_concentrated, conc_reason = analyzer.portfolio_concentration_risk(
                    ACTIVE_SIGNALS, sig
                )
                if is_concentrated and sig.get("tier") not in ("S", "A"):
                    skipped_reasons.append(sym + " " + conc_reason)
                    continue
            except Exception:
                pass

            # ⭐ v53 防守模式放寬到 B 級以上（避免靜音）
            if protection_mode == "DEFENSIVE" and sig.get("tier") not in ("S", "A", "B"):
                skipped_reasons.append(sym + " 防守模式只推 B 級以上")
                continue

            filtered_signals.append(sig)

        if skipped_reasons:
            logger.info("冷卻過濾: " + " | ".join(skipped_reasons))

        if not filtered_signals:
            logger.info("3分推播：所有信號被冷卻過濾，跳過")
            return

        # ⭐ v48 C 級延遲推播邏輯
        # 分組：高品質 (S/A/B) vs C 級 (含緊急保底觀察單)
        high_tier_signals = [s for s in filtered_signals if s.get("tier") in ("S", "A", "B")]
        c_tier_signals = [s for s in filtered_signals if s.get("tier") == "C"]

        now_ts = time.time()
        if high_tier_signals:
            # 有 B 級以上 → 連同 C 級一起推（C 級正常單也要自動下單；觀察單已在推佇列時擋掉）
            filtered_signals = high_tier_signals + c_tier_signals
            _C_TIER_GATE["last_high_tier_push"] = now_ts
            logger.info("📊 推播 " + str(len(high_tier_signals)) + " 個 S/A/B 級信號，重置 C 級冷卻")
        else:
            # 只有 C 級 → 看是否已過 C_TIER_DELAY_MIN 冷卻
            _c_delay_h = C_TIER_DELAY_MIN / 60.0
            hours_since_high = (now_ts - _C_TIER_GATE["last_high_tier_push"]) / 3600
            # 啟動時 last_high_tier_push = 0，會非常大 → 視為從未推過（要等冷卻）
            if _C_TIER_GATE["last_high_tier_push"] == 0:
                # 第一次啟動：用 bot 啟動時間當基準（避免一啟動就狂推 C）
                _C_TIER_GATE["last_high_tier_push"] = now_ts
                logger.info("🕐 v48 啟動：C 級冷卻計時開始（" + str(C_TIER_DELAY_MIN) + " 分鐘後才推 C 級）")
                return
            if hours_since_high < _c_delay_h:
                # 冷卻中，不推 C
                remaining = _c_delay_h - hours_since_high
                logger.info("⏸ C 級冷卻中：距上次 B+ 推播 " + str(round(hours_since_high * 60, 0)) +
                            "min，還需 " + str(round(remaining * 60, 0)) + "min 才推 C")
                return
            # 冷卻完成，可以推 C 級
            filtered_signals = c_tier_signals
            _C_TIER_GATE["last_high_tier_push"] = now_ts  # 推 C 也重置冷卻
            logger.info("✅ C 級冷卻完成（" + str(round(hours_since_high, 1)) + "h），推 " +
                        str(len(c_tier_signals)) + " 個 C 級信號")

        # ⭐ 連虧暫停過濾（暫時停用）
        loss_filtered = filtered_signals  # 暫時停用 — 恢復時還原下方迴圈
        # loss_filtered = []
        # cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        # for sig in filtered_signals:
        #     sym = sig.get("symbol", "")
        #     losses = SYMBOL_LOSSES.get(sym, [])
        #     def _check_loss_time(t):
        #         try:
        #             return datetime.fromisoformat(t) > cutoff
        #         except Exception:
        #             return False
        #     recent_losses = [t for t in losses if _check_loss_time(t)]
        #     if len(recent_losses) >= 2:
        #         skipped_reasons.append(sym + " 連虧暫停中(24h)")
        #         continue
        #     loss_filtered.append(sig)

        if not loss_filtered:
            logger.info("3分推播：全部被連虧過濾，跳過")
            return

        # 註冊新信號到追蹤系統
        for sig in loss_filtered:
            register_signal(sig, list(HUNTER_WATCHERS))
            # ⭐ v30 記錄推播歷史
            sym = sig.get("symbol", "")
            direction = sig.get("direction", "")
            key = sym + "_" + direction
            RECENT_PUSHES[key] = {
                "entry": sig.get("entry", 0),
                "time": datetime.now(timezone.utc).isoformat(),
                "score": sig.get("score", 0),
            }
        # v40 記錄最後成功推播時間
        if loss_filtered:
            _HUNTER_SCANNING["last_push"] = time.time()
        # 清理過期推播記錄（>2 小時）
        cutoff_recent = datetime.now(timezone.utc) - timedelta(hours=2)  # 維持 2 小時
        expired_keys = []
        for k, v in RECENT_PUSHES.items():
            try:
                if datetime.fromisoformat(v["time"]) < cutoff_recent:
                    expired_keys.append(k)
            except Exception:
                expired_keys.append(k)
        for k in expired_keys:
            del RECENT_PUSHES[k]

        logger.info("3分推播：新信號 " + str(len(loss_filtered)) + " 個 / 過濾 " + str(len(skipped_reasons)) + " 個")
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
                    "📱 " + sym_short + " " + direction_zh + " — 開啟 Bybit",
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
                async with aiohttp.ClientSession() as session:
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

        # v29 推播目標：訂閱用戶 + 黑潮船長專屬頻道
        push_targets = list(HUNTER_WATCHERS)
        if BLACK_HUNTER_CHANNEL:
            push_targets.append(BLACK_HUNTER_CHANNEL)

        for chat_id in push_targets:
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
                    tier = sig.get("tier", "B")
                    tier_emoji = {"S": "💎", "A": "🥇", "B": "🥈", "C": "🥉"}.get(tier, "")
                    tier_text = {"S": "[S] DIAMOND", "A": "[A] GOLD", "B": "[B] SILVER", "C": "[C] BRONZE"}.get(tier, "[B] SILVER")
                    title_suffix = tier_text + " | " + entry_grade_display(grade) if grade else tier_text
                    score = sig.get("score", "?")
                    # v33 副標題：tier + 評分
                    subtitle = tier_text + "  |  Score " + str(score) + "  |  " + ("LONG" if direction == "LONG" else "SHORT")
                    caption = (
                        tier_emoji + " *" + sym_short + " " + ("Long ▲" if direction == "LONG" else "Short ▼") + "  " + tier + " 級*\n"
                        "進場品質: " + entry_grade_display(grade) + " | 信心: " + str(score) + "\n"
                        "Entry: `" + str(sig.get("entry", 0)) + "`  |  SL: `" + str(sig.get("sl", 0)) + "`\n"
                        "TP1-3: `" + str(sig.get("tp1", 0)) + "` / `" + str(sig.get("tp2", 0)) + "` / `" + str(sig.get("tp3", 0)) + "`"
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
                        title_suffix=title_suffix,
                        subtitle=subtitle
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
    finally:
        _HUNTER_SCANNING["locked"] = False  # ⭐ v38 釋放鎖
        # v61：記錄本輪掃描耗時，>120s 警告（讓「掃描太慢導致跳輪」看得見）
        try:
            scan_secs = round(time.time() - _scan_started, 1)
            if scan_secs > 120:
                logger.warning("⚠️ 本輪掃描耗時 " + str(scan_secs) + "s（>120s，可能導致跳輪）")
            if _USE_REDIS:
                _redis_cmd_raw(["SET", "bt:last_scan", json.dumps(
                    {"ts": datetime.now(timezone.utc).isoformat(), "scan_secs": scan_secs},
                    ensure_ascii=False)])
        except Exception:
            pass



# ===== 信號追蹤系統 =====

def _safe_after(iso_str, cutoff):
    try:
        return datetime.fromisoformat(iso_str) > cutoff
    except Exception:
        return False


def _build_fast_sig(sym, direction, price, df15m, strength, reason):
    """v61 P3-2：快速動能信號的進場/止損/止盈（結構性 SL + R 階梯 1.5/2.5/3.5）。"""
    try:
        lows = df15m["low"].astype(float)
        highs = df15m["high"].astype(float)
        entry = float(price)
        if direction == "LONG":
            swing_low = float(lows.iloc[-12:].min())
            sl = min(swing_low, entry * (1 - 0.012))
            risk = entry - sl
            if risk <= 0:
                return None
            tp1, tp2, tp3 = entry + risk * 1.5, entry + risk * 2.5, entry + risk * 3.5
        else:
            swing_high = float(highs.iloc[-12:].max())
            sl = max(swing_high, entry * (1 + 0.012))
            risk = sl - entry
            if risk <= 0:
                return None
            tp1, tp2, tp3 = entry - risk * 1.5, entry - risk * 2.5, entry - risk * 3.5
        return {
            "symbol": sym, "direction": direction,
            "entry": analyzer.px_round(entry), "sl": analyzer.px_round(sl),
            "tp1": analyzer.px_round(tp1), "tp2": analyzer.px_round(tp2),
            "tp3": analyzer.px_round(tp3), "tp4": 0,
            "score": max(50, int(strength)),   # >26 避免被觀察單閘門擋掉
            "entry_grade": "B", "tier": "B", "order_type": "MARKET",
            "timeframe": "短線", "tier_label": "⚡精選動能 B 級",
            "rr": 1.5, "fast_momentum": True,
        }
    except Exception:
        return None


def _fast_rr(direction, entry, sl, df15m):
    """v62 P1：到合理目標距離 ÷ 到合理止損距離。
    目標用 swing_sr 的最近結構位；已突破無壓力時用 3×ATR 投射。讀不到回 0。"""
    try:
        risk = abs(float(entry) - float(sl))
        if risk <= 0:
            return 0.0
        res, sup = analyzer.swing_sr(df15m)
        atr15 = float(analyzer.atr(df15m).iloc[-1])
        if direction == "LONG":
            targets = [r for r in res if r > entry]
            target = min(targets) if targets else entry + 3 * atr15
        else:
            targets = [s for s in sup if s < entry]
            target = max(targets) if targets else entry - 3 * atr15
        return abs(float(target) - float(entry)) / risk
    except Exception:
        return 0.0


def _fast_trend_consistency(direction, df1h):
    """v62 P1：1h 趨勢一致性。回傳 0~1（0 = 明確逆向，應否決）。"""
    try:
        if df1h is None or len(df1h) < 50:
            return 0.7
        ema20 = float(df1h["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(df1h["close"].ewm(span=50, adjust=False).mean().iloc[-1])
        px = float(df1h["close"].iloc[-1])
        if direction == "LONG":
            if px > ema20 > ema50:
                return 1.0
            if px < ema20 < ema50:   # 明確下行 → 否決
                return 0.0
            return 0.7
        else:
            if px < ema20 < ema50:
                return 1.0
            if px > ema20 > ema50:   # 明確上行 → 否決
                return 0.0
            return 0.7
    except Exception:
        return 0.7


async def _push_fast_signal(ctx, sig, reason):
    sym_short = sig["symbol"].replace("/USDT", "")
    direction_zh = "做多" if sig["direction"] == "LONG" else "做空"
    msg = "⚡ *" + sym_short + " 精選動能 — " + direction_zh + "*\n"
    msg += "━━━━━━━━━━━━━━━\n"
    msg += "進場 `" + str(sig["entry"]) + "`　止損 `" + str(sig["sl"]) + "`\n"
    msg += "TP1 `" + str(sig["tp1"]) + "` · TP2 `" + str(sig["tp2"]) + "` · TP3 `" + str(sig["tp3"]) + "`\n"
    msg += "強度 *" + str(sig["score"]) + "*｜" + reason + "\n"
    msg += "_⚡ 突破搶先單，節奏快、自負風險_"
    targets = list(HUNTER_WATCHERS)
    if BLACK_HUNTER_CHANNEL:
        targets.append(BLACK_HUNTER_CHANNEL)
    for u in set(targets):
        try:
            await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
        except Exception:
            pass


async def fast_momentum_scan(ctx: ContextTypes.DEFAULT_TYPE):
    """v62 P1：快速動能「精選」搶先偵測（輕量，不動主掃描）。
    掃 24h 漲跌幅前 12，抓 5m+15m+1h；候選需同時滿足 強度≥FAST_MIN_STRENGTH、RR≥FAST_MIN_RR、
    1h 趨勢不逆向、無活躍信號；綜合分（強度×量能×RR×趨勢）排序後每輪只推 FAST_TOP_N 個。
    頻率閘門：同幣 2h 不重複；全體每小時上限 FAST_MAX_PER_HOUR。受連虧/熔斷管制。"""
    if not HUNTER_WATCHERS and not BLACK_HUNTER_CHANNEL:
        return
    try:
        protection_mode, _ = analyzer.auto_protection_mode(SIGNAL_RESULTS)
    except Exception:
        protection_mode = "NORMAL"
    if False and protection_mode == "CIRCUIT_BREAK":  # 暫時停用
        return

    min_strength = int(os.getenv("FAST_MIN_STRENGTH", "70"))
    if protection_mode == "DEFENSIVE":
        min_strength += 15
    min_rr = float(os.getenv("FAST_MIN_RR", "1.8"))
    top_n = int(os.getenv("FAST_TOP_N", "1"))
    max_per_hour = int(os.getenv("FAST_MAX_PER_HOUR", "2"))

    # 全體每小時上限（記憶體節流）
    now = datetime.now(timezone.utc)
    global _FAST_PUSH_TIMES
    _FAST_PUSH_TIMES = [t for t in _FAST_PUSH_TIMES if (now - t).total_seconds() < 3600]
    budget = max_per_hour - len(_FAST_PUSH_TIMES)
    if budget <= 0:
        logger.info("⚡精選動能：本小時已達上限 " + str(max_per_hour) + " 個，本輪不推")
        return

    try:
        async with aiohttp.ClientSession() as session:
            # 1) 只抓 ticker 選候選（不重抓全 52 幣 K 線）
            t_tasks = [analyzer.fetch_ticker(session, s) for s in analyzer.SCAN_POOL]
            tickers = await asyncio.gather(*t_tasks, return_exceptions=True)
            cand = []
            for s, t in zip(analyzer.SCAN_POOL, tickers):
                if isinstance(t, Exception):
                    continue
                try:
                    chg = float(t.get("priceChangePercent", 0))
                    price = float(t.get("lastPrice", 0))
                    if price > 0:
                        cand.append((s, abs(chg), price))
                except Exception:
                    continue
            cand.sort(key=lambda x: x[1], reverse=True)
            cand = cand[:12]
            if not cand:
                return
            # 2) 只對候選抓 5m + 15m + 1h
            k_tasks = []
            for s, _, _ in cand:
                k_tasks.append(analyzer.fetch_ohlcv(session, s, "5m", 60))
                k_tasks.append(analyzer.fetch_ohlcv(session, s, "15m", 60))
                k_tasks.append(analyzer.fetch_ohlcv(session, s, "1h", 80))
            kdata = await asyncio.gather(*k_tasks, return_exceptions=True)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        scored = []   # (composite, sym, direction, price, df15m, strength, reason)
        for idx, (sym, _, price) in enumerate(cand):
            df5m = kdata[idx * 3]
            df15m = kdata[idx * 3 + 1]
            df1h = kdata[idx * 3 + 2]
            if isinstance(df5m, Exception) or isinstance(df15m, Exception):
                continue
            if sym in ACTIVE_SIGNALS:   # 已有活躍信號 → 不疊
                continue
            direction, strength, reason = analyzer.fast_breakout_check(df5m, df15m)
            if not direction:
                continue
            if strength < min_strength:
                logger.info("⚡精選動能：" + sym + " 強度不足(" + str(strength) + ")，只記錄不推")
                continue
            # 連虧暫停過濾（24h 內 ≥2 筆虧損）— 暫時停用
            # recent_losses = [x for x in SYMBOL_LOSSES.get(sym, []) if _safe_after(x, cutoff)]
            # if len(recent_losses) >= 2:
            #     continue
            # 同幣 2h 不重複（同向）
            key = sym + "_" + direction
            rp = RECENT_PUSHES.get(key)
            if rp and _safe_after(rp.get("time", ""), now - timedelta(hours=2)):
                continue
            # RR 門檻
            sig = _build_fast_sig(sym, direction, price, df15m, strength, reason)
            if not sig:
                continue
            rr = _fast_rr(direction, sig["entry"], sig["sl"], df15m)
            if rr < min_rr:
                logger.info("⚡精選動能：" + sym + " RR 不足(" + str(round(rr, 2)) + ")，跳過")
                continue
            # 1h 趨勢不逆向
            df1h_ok = None if isinstance(df1h, Exception) else df1h
            tc = _fast_trend_consistency(direction, df1h_ok)
            if tc <= 0:
                logger.info("⚡精選動能：" + sym + " 1h 趨勢逆向，跳過")
                continue
            # 量能倍數
            try:
                vols5 = df5m["volume"].astype(float)
                avg_vol = float(vols5.iloc[-20:].mean()) if len(vols5) >= 20 else float(vols5.mean())
                vol_ratio = float(vols5.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
            except Exception:
                vol_ratio = 1.0
            composite = strength * vol_ratio * rr * tc
            scored.append((composite, sym, direction, sig, reason, strength, round(rr, 2)))

        if not scored:
            return
        scored.sort(key=lambda x: x[0], reverse=True)
        limit = min(top_n, budget)
        pushed = 0
        for composite, sym, direction, sig, reason, strength, rr in scored[:limit]:
            key = sym + "_" + direction
            register_signal(sig, list(HUNTER_WATCHERS))   # 內含 Redis 佇列橋接
            RECENT_PUSHES[key] = {"entry": sig["entry"],
                                  "time": datetime.now(timezone.utc).isoformat(),
                                  "score": sig["score"]}
            _FAST_PUSH_TIMES.append(datetime.now(timezone.utc))
            await _push_fast_signal(ctx, sig, reason)
            logger.info("⚡精選動能推播: " + sym + " " + direction + " 強度 " + str(strength)
                        + " RR " + str(rr) + " 綜合 " + str(round(composite, 1)))
            pushed += 1
        if pushed:
            logger.info("⚡精選動能：本輪候選 " + str(len(scored)) + " 個，推 " + str(pushed) + " 個")
    except Exception as e:
        logger.error("快速動能掃描失敗: " + str(e))


def parse_hunter_signals(result):
    """從黑潮船長推播文本解析信號詳情（v40.2 配合 v38 實際輸出格式）

    實際格式：
    🥇 *BTC 做多 🟢*
    ═══════════════
    💎 *S 級 — 夢幻信號*
    ═══════════════
    _💎 S 級稀有信號  ·  ..._
    📊 *82/100*  趨勢█████ ...
    ⏰ *等回踩* 81500
    🎯 進場 `82500` · 止損 `81000`
    🏆 TP1 `83500` · TP2 `84500` · TP3 `85500`
    💰 風報比 *1:2.5* · 倉位 *10%* · 預估勝率 *68%*
    """
    signals = []
    # 用標題行（🥇 🥈 🥉 + symbol + 做多/做空）做切割
    # 每個信號從 "🥇 *XXX 做多" 或 "🥈 *XXX 做多" 開始
    pattern = re.compile(
        r"(🥇|🥈|🥉)\s*\*([A-Z0-9]+)\s+(做多|做空)\s*[🟢🔴]?\*"
    )

    # 找所有信號開頭位置
    matches = list(pattern.finditer(result))
    if not matches:
        return signals

    for i, m in enumerate(matches):
        try:
            # 取這個信號的範圍（到下一個信號開頭，或文末）
            start = m.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(result)
            block = result[start:end]

            # 1. symbol + direction
            sym_raw = m.group(2)
            sym = sym_raw + "/USDT"
            direction = "LONG" if m.group(3) == "做多" else "SHORT"

            # 2. tier — v47 修：直接抓 tier 標籤行（避免被排名 emoji 誤導）
            # 真正的 tier 寫在「💎 *S 級 — 夢幻信號*」這種固定格式的行
            tier_match = re.search(r"\*([SABC])\s*級\s*—", block)
            if tier_match:
                tier = tier_match.group(1)
            elif "S 級" in block and "夢幻" in block:
                tier = "S"
            elif "A 級" in block and "重點推薦" in block:
                tier = "A"
            elif "B 級" in block and "一般" in block:
                tier = "B"
            elif "C 級" in block and ("觀察" in block or "試水" in block):
                tier = "C"
            elif "觀察單" in block:
                tier = "C"  # v46 緊急保底信號
            else:
                tier = "C"  # v47：預設改為 C（保守，避免誤判為 A）

            # 3. score (五維度總分)
            score_match = re.search(r"📊\s*\*?(\d+)/100\*?", block)
            score = float(score_match.group(1)) if score_match else 50

            # 4. entry + sl
            entry_match = re.search(r"進場\s*`([\d.]+)`", block)
            sl_match = re.search(r"止損\s*`([\d.]+)`", block)
            if not entry_match or not sl_match:
                continue
            entry = float(entry_match.group(1))
            sl = float(sl_match.group(1))

            # 5. TP1-4
            tp_matches = re.findall(r"TP(\d)\s*`([\d.]+)`", block)
            tps = {1: 0, 2: 0, 3: 0, 4: 0}
            for num, val in tp_matches:
                tps[int(num)] = float(val)

            if tps[1] == 0:
                # 嘗試另一種格式 ① `xxx`
                alt = re.findall(r"[①②③④]\s*`([\d.]+)`", block)
                for idx, val in enumerate(alt[:4]):
                    tps[idx+1] = float(val)

            if tps[1] == 0:
                continue

            # 如果沒有 tp4，用 tp3 推算
            if tps[4] == 0 and tps[3] > 0:
                tps[4] = tps[3] * (1.02 if direction == "LONG" else 0.98)

            # 6. 倉位
            pos_match = re.search(r"倉位\s*\*?(\d+)%", block)
            position = int(pos_match.group(1)) if pos_match else 5

            # 7. 勝率
            wr_match = re.search(r"(?:實際|預估)勝率\s*\*?(\d+(?:\.\d+)?)%", block)
            win_rate = float(wr_match.group(1)) if wr_match else 50

            # 8. 風報比
            rr_match = re.search(r"風報比\s*\*?1:([\d.]+)", block)
            rr = float(rr_match.group(1)) if rr_match else 1.0

            # 9. 進場時機
            if "等回踩" in block:
                timing = "WAIT_PULLBACK"
            elif "等突破" in block:
                timing = "WAIT_BREAKOUT"
            else:
                timing = "NOW"

            signals.append({
                "symbol": sym,
                "direction": direction,
                "score": score,
                "entry": entry,
                "sl": sl,
                "tp1": tps[1],
                "tp2": tps[2],
                "tp3": tps[3],
                "tp4": tps[4],
                "tier": tier,
                "entry_grade": tier,  # v54: 此為 regex fallback 路徑，拿不到真值才用 tier 頂替；結構化路徑(_last_plans)已是真值
                "position": position,
                "win_rate": win_rate,
                "rr_ratio": rr,
                "timing_state": timing,
                "timeframe": "中線" if tier in ("S", "A") else "短線",
                "order_type": "LIMIT" if timing == "WAIT_PULLBACK" else "MARKET",
            })
        except Exception as e:
            logger.error("解析信號失敗: " + str(e))
    return signals

def register_signal(sig, watchers):
    """註冊新信號到追蹤系統（v47 修：已進場拒絕新同向信號）"""
    sym = sig["symbol"]
    new_direction = sig["direction"]

    # ⭐ v40.3 + v47：若已存在同 symbol 信號
    existing = ACTIVE_SIGNALS.get(sym)
    if existing:
        # v47 新增：已進場 → 完全拒絕新信號（不再合併、不再覆蓋）
        if existing.get("entered", False):
            logger.warning("拒絕新信號: " + sym + " 已進場，不接受同 symbol 新信號")
            return
        # 同方向且尚未進場 → 合併 watchers，保留原進場資訊
        if existing.get("direction") == new_direction:
            old_watchers = set(existing.get("watchers", []))
            old_watchers.update(watchers)
            existing["watchers"] = list(old_watchers)
            save_data()
            logger.info("更新信號 watchers: " + sym + " " + new_direction + " 訂閱數 " + str(len(old_watchers)))
            return
        # 反向 → 應該由 reversal_check 處理，這裡不覆蓋
        logger.warning("拒絕反向覆蓋: " + sym + " 已有 " + existing.get("direction", "?") + " 信號")
        return

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
        "watchers": list(set(watchers)),  # 去重
        "tp_hit": [],
        "status": "ACTIVE",
        "created": now.isoformat(),
        "expires": (now + timedelta(hours=expire_hours)).isoformat(),
        "score": sig.get("score", 0),
        "timeframe": sig.get("timeframe", "短線"),
        "entry_grade": sig.get("entry_grade", "C"),
        "order_type": sig.get("order_type", "MARKET"),
        "tier": sig.get("tier", "C"),  # v47: 預設 C 避免誤判
        "entered": False,  # v47: 標記是否已觸及進場價
        "entered_at": None,
        "sl_at_entry": sig.get("sl", 0),
        "rr_at_entry": sig.get("rr", sig.get("rr_ratio", 0)),
        "regime_at_entry": sig.get("regime", ""),
        "adx_at_entry": sig.get("adx", 0),
        "consensus_at_entry": sig.get("consensus_count", 0),
        "news_vote_at_entry": sig.get("news_vote", False),
        "created_hour_utc": now.hour,
        "funding_at_entry": sig.get("funding", 0),
        "ls_ratio_at_entry": sig.get("ls_ratio", 1.0),
        # v57 驗證儀表用欄位
        "range_pos_at_entry": sig.get("range_pos"),
        "vol_pct_at_entry": sig.get("vol_pct"),
        "strategy_type_at_entry": sig.get("strategy_type"),
        "mtf_at_entry": sig.get("mtf_grade"),
    }
    save_data()
    logger.info("註冊信號: " + sym + " " + sig["direction"] + " 評分 " + str(sig.get("score")) + " 等級 " + str(sig.get("entry_grade", "C")) + " 訂閱 " + str(len(watchers)))
    # ⭐ 自動交易橋接：把信號推進 Redis 隊列（給 auto_trader.py 讀）
    _is_observation = ("觀察單" in str(sig.get("tier_label", ""))) or (sig.get("entry_grade", "C") == "D") or (sig.get("score", 100) <= 26)
    if _USE_REDIS and not _is_observation:
        try:
            _sig_obj = {
                "id": sym + "_" + now.isoformat(),
                "symbol": sym,
                "direction": sig["direction"],
                "tier": sig.get("tier", "C"),
                "entry": sig["entry"],
                "sl": sig["sl"],
                "tp1": sig["tp1"], "tp2": sig.get("tp2", 0),
                "tp3": sig.get("tp3", 0), "tp4": sig.get("tp4", 0),
                "created": now.isoformat(),
            }
            _sig_json = json.dumps(_sig_obj, ensure_ascii=False)
            _body = json.dumps(["RPUSH", "signal_queue", _sig_json]).encode("utf-8")
            _req = _urlreq.Request(_REDIS_URL, data=_body, headers={
                "Authorization": "Bearer " + _REDIS_TOKEN,
                "Content-Type": "application/json",
            })
            with _urlreq.urlopen(_req, timeout=10) as _resp:
                _r = json.loads(_resp.read().decode("utf-8"))
                if "error" in _r:
                    raise Exception(str(_r["error"]))
            _body2 = json.dumps(["LTRIM", "signal_queue", -100, -1]).encode("utf-8")
            _req2 = _urlreq.Request(_REDIS_URL, data=_body2, headers={
                "Authorization": "Bearer " + _REDIS_TOKEN,
                "Content-Type": "application/json",
            })
            with _urlreq.urlopen(_req2, timeout=10) as _resp2:
                _resp2.read()
            logger.info("✅ 信號已推入 Redis 隊列 signal_queue: " + sym)
        except Exception as _e:
            logger.warning("⚠️ 寫 Redis 隊列失敗（不影響信號廣播）: " + str(_e)[:100])


async def close_signal(ctx, symbol, reason_code, reason_msg, current_price=None):
    """關閉信號並通知用戶（v26 不再推播到頻道）"""
    if symbol not in ACTIVE_SIGNALS:
        return
    # v55 修：先檢查關鍵字段，缺字段不 pop（避免信號丟失），記錄錯誤後退出
    _sig_peek = ACTIVE_SIGNALS[symbol]
    if not _sig_peek.get("direction") or not _sig_peek.get("entry"):
        logger.error("close_signal: " + symbol + " 缺關鍵字段，跳過此次結算（信號保留）sig=" + str(_sig_peek))
        return
    sig = ACTIVE_SIGNALS.pop(symbol)
    direction = sig["direction"]
    entry = sig["entry"]
    if _USE_REDIS:
        try:
            _close_obj = {
                "id": symbol + "_close_" + datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "direction": direction,
                "reason": reason_code,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            _cbody = json.dumps(["RPUSH", "close_queue", json.dumps(_close_obj, ensure_ascii=False)]).encode("utf-8")
            _creq = _urlreq.Request(_REDIS_URL, data=_cbody, headers={
                "Authorization": "Bearer " + _REDIS_TOKEN,
                "Content-Type": "application/json",
            })
            with _urlreq.urlopen(_creq, timeout=10) as _cresp:
                _cresp.read()
            _ctrim = json.dumps(["LTRIM", "close_queue", -100, -1]).encode("utf-8")
            _creq2 = _urlreq.Request(_REDIS_URL, data=_ctrim, headers={
                "Authorization": "Bearer " + _REDIS_TOKEN,
                "Content-Type": "application/json",
            })
            with _urlreq.urlopen(_creq2, timeout=10) as _cresp2:
                _cresp2.read()
            logger.info("✅ 已推平倉通知到 close_queue: " + symbol + " (" + str(reason_code) + ")")
        except Exception as _ce:
            logger.warning("⚠️ 推 close_queue 失敗（不影響結算）: " + str(_ce)[:100])
    # 計算結果百分比
    cp = current_price or entry
    # ⭐ v53 正確結算：計入分批止盈已實現的利潤
    # 倉位權重：TP1 平 40%、TP2 平 35%、TP3 平 25%（對齊 Bybit 三段實際成交；改此設定後須跑 /reset_stats）
    _weights = {1: 0.40, 2: 0.35, 3: 0.25}
    _dir = 1 if direction == "LONG" else -1
    tp_hit = sig.get("tp_hit", [])

    # 已實現部分：每個已達成的 TP，按其權重結算該段利潤
    realized = 0.0
    realized_weight = 0.0
    for lvl in tp_hit:
        tp_price = sig.get("tp" + str(lvl))
        if tp_price:
            seg_pct = (tp_price - entry) / entry * 100 * _dir
            realized += seg_pct * _weights.get(lvl, 0)
            realized_weight += _weights.get(lvl, 0)

    # 剩餘部分：用最終出場價結算
    remaining_weight = max(0.0, 1.0 - realized_weight)
    if reason_code == "SL_HIT":
        exit_price = sig.get("sl", entry)  # v55: 缺sl时用entry兜底
    elif reason_code == "TP3_HIT":
        exit_price = sig.get("tp3", entry)
    else:
        exit_price = cp
    # v53 加固：若已達過 TP（tp_hit 非空），代表止損應已移至保本價。
    # 萬一 sl 未成功移動（重啟/狀態遺失），剩餘倉位出場價不應低於成本，避免重複計虧。
    if tp_hit:
        if direction == "LONG":
            exit_price = max(exit_price, entry)
        else:
            exit_price = min(exit_price, entry)
    remaining_pct = (exit_price - entry) / entry * 100 * _dir

    final_pct = realized + remaining_pct * remaining_weight

    sym_short = symbol.replace("/USDT", "")
    direction_zh = "做多" if direction == "LONG" else "做空"
    tier = sig.get("tier", "B")
    tier_emoji = {"S": "💎", "A": "🥇", "B": "🥈", "C": "🥉"}.get(tier, "")

    if reason_code == "TP3_HIT":
        msg = "🎉 *" + sym_short + " " + direction_zh + " — 完美下車*\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "已達最後止盈\n進場 `" + str(entry) + "` → 出場 `" + str(sig.get("tp3", "?")) + "`\n"
        msg += "完整收益約 *+" + str(round(final_pct, 2)) + "%*"
    elif reason_code == "SL_HIT":
        tp_hit = sig.get("tp_hit", [])
        if tp_hit:
            msg = "🛡 *" + sym_short + " — 觸及保護位*\n"
            msg += "已先達 TP" + str(max(tp_hit)) + "，剩餘倉位觸發止損\n"
            msg += "雖然回吐部分利潤，整體應仍盈利"
        else:
            _loss = final_pct < 0
            _head = "觸發止損" if _loss else "止損出場（仍獲利）"
            _word = "本次虧損" if _loss else "本次獲利"
            msg = "🛑 *" + sym_short + " " + direction_zh + " — " + _head + "*\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "請立即出場\n進場 `" + str(entry) + "` → 止損 `" + str(sig.get("sl", "?")) + "`\n"
            msg += _word + " *" + str(abs(round(final_pct, 2))) + "%*\n\n"
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
    if reason_code == "SL_HIT" and not sig.get("tp_hit") and final_pct < 0:
        if symbol not in SYMBOL_LOSSES:
            SYMBOL_LOSSES[symbol] = []
        SYMBOL_LOSSES[symbol].append(datetime.now(timezone.utc).isoformat())
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        # ⭐ v40.3 加保護：避免單一壞資料炸掉整個 SYMBOL_LOSSES
        def _safe_parse(t):
            try:
                return datetime.fromisoformat(t) > cutoff
            except Exception:
                return False
        SYMBOL_LOSSES[symbol] = [t for t in SYMBOL_LOSSES[symbol] if _safe_parse(t)]

    # v29 通知目標：訂閱者 + 黑潮船長專屬頻道
    notify_targets = list(sig.get("watchers", []))
    if BLACK_HUNTER_CHANNEL:
        notify_targets.append(BLACK_HUNTER_CHANNEL)
    for chat_id in notify_targets:
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error("通知關閉失敗 " + str(chat_id) + ": " + str(e))

    # ⭐ v38 擴充記錄（為真實勝率校準）
    is_win = final_pct > 0
    try:
        _created = sig.get("created")
        _dur_min = (datetime.now(timezone.utc) - datetime.fromisoformat(_created)).total_seconds() / 60 if _created else 0
    except Exception:
        _dur_min = 0
    SIGNAL_RESULTS.append({
        "symbol": symbol, "direction": direction, "entry": entry,
        "result": reason_code, "final_pct": round(final_pct, 2),
        "tp_hit_count": len(sig.get("tp_hit", [])),
        "score": sig.get("score", 0),
        "tier": sig.get("tier", "B"),  # v38 新增
        "entry_grade": sig.get("entry_grade", ""),  # v53：為真實勝率校準
        "is_win": is_win,  # v38 新增
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "duration_min": _dur_min,
        "sl_at_entry": sig.get("sl_at_entry", 0),
        "rr_at_entry": sig.get("rr_at_entry", 0),
        "regime_at_entry": sig.get("regime_at_entry", ""),
        "adx_at_entry": sig.get("adx_at_entry", 0),
        "consensus_at_entry": sig.get("consensus_at_entry", 0),
        "news_vote_at_entry": sig.get("news_vote_at_entry", False),
        "created_hour_utc": sig.get("created_hour_utc", 0),
        "funding_at_entry": sig.get("funding_at_entry", 0),
        "ls_ratio_at_entry": sig.get("ls_ratio_at_entry", 1.0),
        # v57 驗證儀表用欄位（舊紀錄缺欄位 → None）
        "range_pos_at_entry": sig.get("range_pos_at_entry", None),
        "vol_pct_at_entry": sig.get("vol_pct_at_entry", None),
        "strategy_type_at_entry": sig.get("strategy_type_at_entry", None),
        "mtf_at_entry": sig.get("mtf_at_entry", None),
    })
    # 只保留最近 1000 筆
    if len(SIGNAL_RESULTS) > 1000:
        del SIGNAL_RESULTS[:len(SIGNAL_RESULTS) - 1000]
    save_data()


async def notify_tp_hit(ctx, symbol, tp_level, current_price):
    """通知 TP 達標（v31 自動更新動態止損）"""
    if symbol not in ACTIVE_SIGNALS:
        return
    sig = ACTIVE_SIGNALS[symbol]
    # v55 修：用 .get 容錯
    if tp_level in sig.get("tp_hit", []):
        return
    direction = sig.get("direction")
    entry = sig.get("entry")
    tp_price = sig.get("tp" + str(tp_level))
    if not direction or not entry or not tp_price:
        logger.warning("notify_tp_hit: " + symbol + " 缺關鍵字段，跳過 tp_level=" + str(tp_level))
        return
    sig.setdefault("tp_hit", []).append(tp_level)
    profit_pct = abs(tp_price - entry) / entry * 100
    sym_short = symbol.replace("/USDT", "")
    direction_zh = "做多" if direction == "LONG" else "做空"
    tier = sig.get("tier", "B")
    tier_emoji = {"S": "💎", "A": "🥇", "B": "🥈", "C": "🥉"}.get(tier, "")

    # ⭐ v31 動態移動止損（v61：與 auto_trader 止損口徑一致——TP1 後 entry−緩衝、TP2 後才保本）
    new_sl = None
    old_sl = sig.get("sl", entry)  # v55: 缺sl時用entry兜底
    _buf = float(os.getenv("TRAIL_BUFFER_MIN_PCT", "0.004"))
    if tp_level == 1:
        # v61：TP1 後移到「entry−緩衝」而非鎖死，給回踩留空間（根治「TP1 後一回踩就被保本掃出」）
        new_sl = round(entry * (1 - _buf), 6) if direction == "LONG" else round(entry * (1 + _buf), 6)
        sl_action = "止損自動移至 `" + str(new_sl) + "` (entry−緩衝，留回踩空間)"
    elif tp_level == 2:
        # v61：TP2 後才移到保本價(entry)，讓剩餘倉位有空間跑到 TP3
        new_sl = round(entry, 6)
        sl_action = "止損自動移至保本價 `" + str(new_sl) + "` (鎖利)"
    else:
        sl_action = "達最終止盈"

    if new_sl is not None and new_sl != old_sl:
        if direction == "LONG" and new_sl > old_sl:
            sig["sl"] = new_sl
        elif direction == "SHORT" and new_sl < old_sl:
            sig["sl"] = new_sl

    # ⭐ v37 智能 TP 延伸（達 TP1 後若動能強，拉遠目標）
    if False:  # v55 停用智能 TP 延伸：驗證期間用固定 TP 階梯；它有「只改 TP2/TP3、漏改 TP4」的排序 bug。analyzer.smart_tp_extend 函式保留不刪、不採用。
        try:
            async with aiohttp.ClientSession() as session:
                df1h = await analyzer.fetch_ohlcv(session, symbol, "1h", 50)
            if df1h is not None:
                new_tp2, new_tp3, _, extend_msg = analyzer.smart_tp_extend(
                    df1h, direction, entry, sig.get("tp1", 0), sig.get("tp2", 0),
                    sig.get("tp3", 0), current_price
                )
                if new_tp2 and new_tp3 and extend_msg:
                    old_tp2 = sig.get("tp2", 0)
                    sig["tp2"] = new_tp2
                    sig["tp3"] = new_tp3
                    sym_short = symbol.replace("/USDT", "")
                    msg2 = "🚀 *" + sym_short + " — 智能 TP 延伸*\n"
                    msg2 += "━━━━━━━━━━━━━━━\n"
                    msg2 += "原 TP2: `" + str(old_tp2) + "` → 新 TP2: `" + str(new_tp2) + "`\n"
                    msg2 += "新 TP3: `" + str(new_tp3) + "`\n"
                    msg2 += "_" + extend_msg + "_"
                    notify_t = list(sig.get("watchers", []))
                    if BLACK_HUNTER_CHANNEL:
                        notify_t.append(BLACK_HUNTER_CHANNEL)
                    for u in notify_t:
                        try:
                            await ctx.bot.send_message(chat_id=u, text=msg2, parse_mode="Markdown")
                        except Exception:
                            pass
        except Exception as e:
            logger.error("智能 TP 延伸失敗: " + str(e))

    tp_messages = {
        1: ("✅", "達到 TP1 保本點", "*立即平 40% 倉位*"),
        2: ("💰", "達到 TP2 鎖利", "*平 35% 倉位*"),
        3: ("🏆", "達到 TP3 大勝下車", "*平剩餘 25% 倉位*"),
    }
    emoji, title, action = tp_messages[tp_level]
    msg = emoji + " *" + tier_emoji + " " + sym_short + " " + direction_zh + " — " + title + "*\n"
    msg += "━━━━━━━━━━━━━━━\n"
    msg += "進場 `" + str(entry) + "` → 現價 `" + str(current_price) + "`\n"
    msg += "浮盈 *+" + str(round(profit_pct, 2)) + "%*\n\n"
    msg += "📌 *立即動作*\n" + action + "\n\n"
    msg += "🛡 *自動風控*\n" + sl_action + "\n"
    if tp_level < 3:
        remaining_tps = []
        for t in range(tp_level + 1, 4):
            if sig.get("tp" + str(t), 0) > 0:
                remaining_tps.append("TP" + str(t) + " `" + str(sig["tp" + str(t)]) + "`")
        if remaining_tps:
            msg += "\n🎯 *剩餘目標*\n  " + " · ".join(remaining_tps)
    msg += "\n\n_v31 動態止損已自動更新_"

    notify_targets = list(sig.get("watchers", []))
    if BLACK_HUNTER_CHANNEL:
        notify_targets.append(BLACK_HUNTER_CHANNEL)
    for chat_id in notify_targets:
        try:
            await ctx.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error("通知 TP 失敗 " + str(chat_id) + ": " + str(e))

    if tp_level == 3:
        await close_signal(ctx, symbol, "TP3_HIT", "達最終止盈")
    else:
        save_data()


async def check_active_signals(ctx):
    """檢查所有活躍信號的當前狀態（v31 加入主動退出檢查）"""
    if not ACTIVE_SIGNALS:
        return
    now = datetime.now(timezone.utc)
    symbols_to_check = list(ACTIVE_SIGNALS.keys())
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for sym in symbols_to_check:
                tasks.append(analyzer.fetch_ticker(session, sym))
                tasks.append(analyzer.fetch_ohlcv(session, sym, "15m", 50))
                tasks.append(analyzer.fetch_ohlcv(session, sym, "1h", 60))
            results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, sym in enumerate(symbols_to_check):
            if sym not in ACTIVE_SIGNALS:
                continue
            sig = ACTIVE_SIGNALS[sym]
            ticker = results[i * 3]
            df15m = results[i * 3 + 1]
            df1h_track = results[i * 3 + 2]
            if isinstance(ticker, Exception):
                continue
            try:
                price = float(ticker.get("lastPrice", 0))
            except (ValueError, TypeError):
                price = 0
            if price == 0:
                continue
            # v55 修：缺關鍵字段的信號跳過，不拖垮整個追蹤循環（會錯過其他信號的止損！）
            direction = sig.get("direction")
            entry = sig.get("entry")
            sl = sig.get("sl")
            if not direction or not entry or sl is None:
                logger.warning("TP侦测: " + sym + " 缺關鍵字段，本輪跳過")
                continue

            # === 止損 ===
            if direction == "LONG" and price <= sl:
                await close_signal(ctx, sym, "SL_HIT", "觸及止損", price)
                continue
            if direction == "SHORT" and price >= sl:
                await close_signal(ctx, sym, "SL_HIT", "觸及止損", price)
                continue

            # === 止盈（從高到低）===
            tp_hit = sig.get("tp_hit", [])
            tp_triggered = False
            for level in [3, 2, 1]:
                if level in tp_hit:
                    continue
                tp_price = sig.get("tp" + str(level), 0)
                if tp_price == 0:
                    continue
                if direction == "LONG" and price >= tp_price:
                    await notify_tp_hit(ctx, sym, level, price)
                    tp_triggered = True
                    break
                if direction == "SHORT" and price <= tp_price:
                    await notify_tp_hit(ctx, sym, level, price)
                    tp_triggered = True
                    break

            # === v31 主動退出檢查（達 TP1 之前才檢查，避免已盈利的被誤觸發）===
            if sym in ACTIVE_SIGNALS and not tp_triggered and not tp_hit:
                try:
                    created = datetime.fromisoformat(sig["created"])
                    age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60
                    # 只在 30 分鐘 ~ 6 小時內檢查
                    if 30 < age_min < 360 and not isinstance(df15m, Exception):
                        # v36 信號重評估（v57：改餵 1h K 線，避免 15m 雜訊提前誤判 close_now）
                        if not isinstance(df1h_track, Exception):
                            recheck_action, recheck_reason = analyzer.stale_signal_recheck(
                                sig, price, df1h_track
                            )
                        else:
                            recheck_action, recheck_reason = "hold", ""
                        if recheck_action == "close_now":
                            # 強制平倉
                            await close_signal(ctx, sym, "RECHECK_EXIT",
                                                 recheck_reason, price)
                            continue
                        elif recheck_action == "reduce":
                            # 建議減倉
                            last_advice = sig.get("last_recheck_advice", 0)
                            now_ts = datetime.now(timezone.utc).timestamp()
                            if now_ts - last_advice > 1800:
                                sig["last_recheck_advice"] = now_ts
                                sym_short = sym.replace("/USDT", "")
                                msg = "⚠️ *" + sym_short + " 重評估建議：減倉*\n"
                                msg += "━━━━━━━━━━━━━━━\n"
                                msg += "原因：" + recheck_reason + "\n"
                                msg += "建議：減倉 30-50% 鎖利"
                                notify_t = list(sig.get("watchers", []))
                                if BLACK_HUNTER_CHANNEL:
                                    notify_t.append(BLACK_HUNTER_CHANNEL)
                                for u in notify_t:
                                    try:
                                        await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                                    except Exception:
                                        pass

                        # v55: EMA20 智能移動止損已停用 —— 它會把贏單在還沒到 TP 前洗出場，
                        # 且與 auto_trader 的實單不同步、造成數據失真。
                        # analyzer.adaptive_sl_adjust 函式本體保留但不再採用。
                        # TP 之後的階梯鎖利仍由 notify_tp_hit 處理，不受影響。

                        # v61 降噪：主動退出判斷 K 線 15m→1h，避免 15m 雜訊提前洗出場
                        if not isinstance(df1h_track, Exception):
                            should_exit, exit_reason = analyzer.early_exit_signal(
                                df1h_track, direction, entry, sl
                            )
                        else:
                            should_exit, exit_reason = False, ""
                        if should_exit:
                            # 避免重複警告
                            last_warning = sig.get("last_exit_warning", 0)
                            now_ts = datetime.now(timezone.utc).timestamp()
                            if now_ts - last_warning > 1800:  # 30 分鐘內不重複
                                sig["last_exit_warning"] = now_ts
                                sym_short = sym.replace("/USDT", "")
                                direction_zh = "做多" if direction == "LONG" else "做空"
                                if direction == "LONG":
                                    change_pct = (price - entry) / entry * 100
                                else:
                                    change_pct = (entry - price) / entry * 100
                                msg = "🚨 *" + sym_short + " " + direction_zh + " — 結構破壞警告*\n"
                                msg += "━━━━━━━━━━━━━━━\n"
                                msg += "進場 `" + str(entry) + "` → 現價 `" + str(price) + "`\n"
                                msg += "目前 *" + ("+" if change_pct >= 0 else "") + str(round(change_pct, 2)) + "%*\n\n"
                                msg += "📌 *偵測到*\n  " + exit_reason + "\n\n"
                                msg += "📌 *資深建議*\n"
                                if change_pct > 0:
                                    msg += "  • 有獲利 → 立即出場鎖利\n"
                                    msg += "  • 不要等止損被掃"
                                elif change_pct > -1:
                                    msg += "  • 浮虧小 → 主動出場，下個機會再來\n"
                                    msg += "  • 結構已破壞，繼續持有風險高"
                                else:
                                    msg += "  • 浮虧較深 → 建議主動出場\n"
                                    msg += "  • 比硬撐到止損強"
                                msg += "\n\n_v31 主動退出系統_"
                                notify_t = list(sig.get("watchers", []))
                                if BLACK_HUNTER_CHANNEL:
                                    notify_t.append(BLACK_HUNTER_CHANNEL)
                                for u in notify_t:
                                    try:
                                        await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                                    except Exception:
                                        pass
                                save_data()
                except Exception:
                    pass

            # === 過期檢查 ===
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
    try:
        async with aiohttp.ClientSession() as session:
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
                notify_t = list(affected)
                if BLACK_HUNTER_CHANNEL:
                    notify_t.append(BLACK_HUNTER_CHANNEL)
                for u in notify_t:
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
    try:
        async with aiohttp.ClientSession() as session:
            for sym, sig in list(ACTIVE_SIGNALS.items()):
                # v47 修：已 TP 命中 或 已標記進場 → 不再提醒
                if sig.get("tp_hit"):
                    continue
                if sig.get("entered", False):  # v47: 已進場標記
                    continue
                try:
                    ticker = await analyzer.fetch_ticker(session, sym)
                    current = float(ticker.get("lastPrice", 0))
                    entry = sig.get("entry", 0)
                    if not current or not entry:
                        continue
                    direction = sig.get("direction", "LONG")
                    dist_pct = abs(current - entry) / entry * 100

                    # v47 修：價格已穿越進場價 → 標記為已進場，不再提醒
                    if direction == "LONG" and current <= entry * 1.001:
                        # LONG：價格觸及或低於進場價
                        if not sig.get("entered"):
                            sig["entered"] = True
                            sig["entered_at"] = datetime.now(timezone.utc).isoformat()
                            save_data()
                            logger.info(sym + " 已觸及進場價，標記為 entered")
                        continue
                    elif direction == "SHORT" and current >= entry * 0.999:
                        # SHORT：價格觸及或高於進場價
                        if not sig.get("entered"):
                            sig["entered"] = True
                            sig["entered_at"] = datetime.now(timezone.utc).isoformat()
                            save_data()
                            logger.info(sym + " 已觸及進場價，標記為 entered")
                        continue

                    # 只在「即將觸及但還沒到」才提醒
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
                            notify_t = list(sig.get("watchers", []))
                            if BLACK_HUNTER_CHANNEL:
                                notify_t.append(BLACK_HUNTER_CHANNEL)
                            for u in notify_t:
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
    """檢查活躍信號是否出現即時反向信號"""
    if not ACTIVE_SIGNALS:
        return
    try:
        async with aiohttp.ClientSession() as session:
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
                    # v61 降噪：冷卻 1h→2h
                    if now_ts - last_alert < 7200:
                        continue
                    # v61 降噪：同一信號最多發 2 次反向警告
                    if sig.get("reversal_alert_count", 0) >= 2:
                        continue
                    # v61 降噪：判斷 K 線 15m→1h，避免 15m 雜訊提前誤判
                    df = await analyzer.fetch_ohlcv(session, sym, "1h", 30)
                    if df is None or len(df) < 10:
                        continue
                    has_reversal, reasons = analyzer.kline_reversal_check(df, sig["direction"], sig["entry"])
                    if has_reversal:
                        LAST_REVERSAL_ALERT[sym] = now_ts
                        sig["reversal_alert_count"] = sig.get("reversal_alert_count", 0) + 1
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
                        msg += "📌 偵測信號：" + reasons + "\n\n"
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
                        # v61 降噪：反向警告只發給 watchers，不再發頻道（避免洗頻）
                        notify_t = list(sig.get("watchers", []))
                        for u in notify_t:
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
    _redis_health_check()
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
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("reset_stats", cmd_reset_stats))
    app.add_handler(CommandHandler("edge", cmd_edge))
    app.add_handler(CommandHandler("gate_stats", cmd_gate_stats))
    app.add_handler(CommandHandler("real_pnl", cmd_real_pnl))
    app.add_handler(CommandHandler("at_status", cmd_at_status))
    app.add_handler(CommandHandler("at_debug", cmd_at_debug))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    # ⭐ v59 E4：每 60 秒把 auto_trader 的 at:events 轉發給 ADMIN（單輪最多 10 條防洪水）
    # v63b：改成「先讀全部 → 逐條送成功才移除」，避免讀完即 DEL 導致部署重啟窗口漏發就永久丟失；
    # 送失敗的留著不移除，下輪繼續重試；單輪仍只送前 10 條（防洪水），其餘留到下輪（不再被誤刪）。
    async def at_events_relay(ctx):
        if not _USE_REDIS or not ADMIN_ID:
            return
        try:
            events = _redis_lrange_raw("at:events")
        except Exception as e:
            logger.error("讀取 at:events 失敗: " + str(e)[:120])
            return
        if not events:
            return
        for ev in events[:10]:
            try:
                await ctx.bot.send_message(chat_id=ADMIN_ID, text=str(ev))
            except Exception as e:
                logger.error("at:events 推播失敗（保留，下輪重試）: " + str(e)[:120])
                continue
            try:
                _redis_cmd_raw(["LREM", "at:events", "1", ev])
            except Exception as e:
                logger.error("at:events LREM 失敗: " + str(e)[:120])
    app.job_queue.run_repeating(
        at_events_relay,
        interval=60,
        first=45
    )
    # ⭐ 每 5 分鐘執行黑潮船長
    app.job_queue.run_repeating(
        auto_broadcast,
        interval=PUSH_INTERVAL_MIN * 60,
        first=60
    )
    # ⭐ v61 P3-2：快速動能搶先偵測（輕量，每 90 秒）
    app.job_queue.run_repeating(
        fast_momentum_scan,
        interval=90,
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
    # ⭐ 每 5 分鐘檢查進場後反向信號
    async def reversal_checker(ctx):
        await check_signal_reversal(ctx)
    app.job_queue.run_repeating(
        reversal_checker,
        interval=300,
        first=300
    )

    # ⭐ v31 每 30 分鐘發送持倉狀態報告
    async def position_status_report(ctx):
        """主動回報所有活躍信號的當前狀態"""
        if not ACTIVE_SIGNALS:
            return
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [analyzer.fetch_ticker(session, sym) for sym in ACTIVE_SIGNALS.keys()]
                tickers = await asyncio.gather(*tasks, return_exceptions=True)
            msg = "📊 *持倉狀態報告*\n"
            msg += "_" + datetime.now(timezone.utc).strftime("%H:%M UTC") + "_\n"
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "目前追蹤中 *" + str(len(ACTIVE_SIGNALS)) + "* 個信號\n\n"

            total_pnl = 0
            shown_count = 0
            for i, (sym, sig) in enumerate(ACTIVE_SIGNALS.items()):
                # v55 修復：用 .get 容錯，缺字段的單獨信號跳過，不拖垮整個報告（避免空白）
                direction = sig.get("direction")
                entry = sig.get("entry")
                if not direction or not entry:
                    continue  # 這個信號資料不完整，跳過但繼續處理其他
                sym_short = sym.replace("/USDT", "")
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                tp_hit = sig.get("tp_hit", [])
                tp_status = "達 TP" + str(max(tp_hit)) if tp_hit else "待 TP1"
                grade = sig.get("entry_grade", "?")

                # v55 修復：價格抓不到時不再整個跳過，至少顯示基本資訊（避免空白報告）
                ticker = tickers[i] if i < len(tickers) else None
                price = 0
                if ticker and not isinstance(ticker, Exception):
                    try:
                        price = float(ticker.get("lastPrice", 0))
                    except (ValueError, TypeError):
                        price = 0

                if price == 0:
                    # 抓不到即時價，顯示基本資訊
                    msg += "*" + sym_short + "* " + dir_emoji + " " + entry_grade_display(grade) + " | " + tp_status + "\n"
                    msg += "  進場 `" + str(entry) + "` · _價格更新中_\n\n"
                    shown_count += 1
                    continue

                if direction == "LONG":
                    pnl_pct = (price - entry) / entry * 100
                else:
                    pnl_pct = (entry - price) / entry * 100
                total_pnl += pnl_pct
                shown_count += 1

                pnl_emoji = "📈" if pnl_pct >= 0 else "📉"

                # 距下個 TP 多遠
                next_tp = None
                for level in range(1, 4):
                    if level not in tp_hit:
                        next_tp = sig.get("tp" + str(level), 0)
                        next_tp_label = "TP" + str(level)
                        break
                next_tp_pct = None
                if next_tp:
                    if direction == "LONG":
                        next_tp_pct = (next_tp - price) / price * 100
                    else:
                        next_tp_pct = (price - next_tp) / price * 100

                # 距止損多遠
                sl = sig.get("sl")
                if sl and direction == "LONG":
                    sl_pct = (price - sl) / price * 100
                elif sl:
                    sl_pct = (sl - price) / price * 100
                else:
                    sl_pct = 0

                msg += "*" + sym_short + "* " + dir_emoji + " " + entry_grade_display(grade) + " | " + tp_status + "\n"
                msg += "  進場 `" + str(entry) + "` → `" + str(price) + "`\n"
                msg += "  " + pnl_emoji + " *" + ("+" if pnl_pct >= 0 else "") + str(round(pnl_pct, 2)) + "%*"
                if next_tp_pct is not None:
                    msg += " | " + next_tp_label + " 還差 " + str(round(next_tp_pct, 2)) + "%"
                msg += "\n  🛡 止損距 " + str(round(sl_pct, 2)) + "%\n\n"

            # v55 兜底：若所有信號都無法顯示，給提示而非空白
            if shown_count == 0:
                msg += "_信號資料更新中，稍後再試_\n\n"
            # 整體浮盈（v55 修：分母用實際算到價格的數量，不是全部，避免被抓不到價的拉低）
            priced_count = shown_count if shown_count > 0 else 1
            # 只對有計入 total_pnl 的（即有價格的）求平均
            valid_pnl_count = sum(1 for i, (sym, sig) in enumerate(ACTIVE_SIGNALS.items())
                                  if i < len(tickers) and tickers[i] and not isinstance(tickers[i], Exception))
            avg_pnl = total_pnl / valid_pnl_count if valid_pnl_count > 0 else 0
            msg += "━━━━━━━━━━━━━━━\n"
            msg += "📊 *整體浮盈*: " + ("+" if avg_pnl >= 0 else "") + str(round(avg_pnl, 2)) + "% (平均)\n"
            msg += "_系統持續追蹤中，將即時通知關鍵事件_"

            # 推給訂閱者 + 黑潮頻道
            notified = set()
            for sig in ACTIVE_SIGNALS.values():
                for w in sig.get("watchers", []):
                    notified.add(w)
            if BLACK_HUNTER_CHANNEL:
                notified.add(BLACK_HUNTER_CHANNEL)
            for u in notified:
                try:
                    await ctx.bot.send_message(chat_id=u, text=msg, parse_mode="Markdown")
                except Exception:
                    pass
        except Exception as e:
            logger.error("持倉狀態報告失敗: " + str(e))
    app.job_queue.run_repeating(
        position_status_report,
        interval=1800,  # 30 分鐘
        first=600
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
                        async with aiohttp.ClientSession() as session:
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

        def _md_safe(s):
            for ch in ("*", "_", "`", "[", "]"):
                s = s.replace(ch, "")
            return s

        try:
            async with aiohttp.ClientSession() as session:
                news = await analyzer.fetch_news(session)
                events = await analyzer.fetch_crypto_events(session)
            try:
                econ = analyzer.upcoming_econ_events()
            except Exception:
                econ = []
            now_str = datetime.now(timezone.utc).strftime("%m-%d %H:%M UTC")

            r = "📰 *加密快訊整點報*\n`" + now_str + "`\n━━━━━━━━━━━━━━━\n"

            items = []
            if news:
                score, label, items = analyzer.sentiment(news)
                r += "🧭 新聞情緒　" + label + "\n"

            if econ:
                r += "\n*🔥 重要事件倒數*\n"
                for ev in econ[:4]:
                    name = _md_safe(ev.get("name", ""))
                    date = ev.get("date", "")
                    days = ev.get("days", "")
                    impact = ev.get("impact", "")
                    r += "• " + impact + "｜" + name + " `" + str(date) + "`"
                    if days != "":
                        r += "（" + ("今天" if days == 0 else str(days) + "天") + "）"
                    r += "\n"

            if events:
                r += "\n*🗓 加密幣事件*\n"
                for ev in events[:5]:
                    title = _md_safe(ev.get("title", "")[:50])
                    date = ev.get("date", "")
                    typ = ev.get("type", "")
                    te = "🔓" if typ == "Unlock" else ("🚀" if typ == "Listing" else ("⚙️" if typ == "Upgrade" else "📌"))
                    r += "• " + te + " " + title
                    if date:
                        r += " `" + str(date) + "`"
                    r += "\n"

            if items:
                r += "\n*📰 即時新聞*\n"
                for i, item in enumerate(items[:6], 1):
                    emo = item.get("emoji", "")
                    title = _md_safe(item.get("title", "")[:70])
                    src = _md_safe(item.get("source", ""))
                    time_ago = analyzer.format_published(item.get("published", ""))
                    r += "`" + str(i) + ".` " + emo + " " + title + "\n"
                    meta = [m for m in [src, time_ago] if m]
                    if meta:
                        r += "　　_" + " · ".join(meta) + "_\n"

            r += "\n_📗 看多　📕 看空　📒 中性　·　資訊整理，非投資建議_"
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
                    async with aiohttp.ClientSession() as session:
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
                    sb_m = re.search(r"強多頭.*?\((\d+)\)", result)
                    b_m = re.search(r"\*📈 多頭.*?\((\d+)\)", result)
                    r_m = re.search(r"震盪.*?\((\d+)\)", result)
                    bear_m = re.search(r"\*📉 空頭.*?\((\d+)\)", result)
                    sbe_m = re.search(r"強空頭.*?\((\d+)\)", result)
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
                    async with aiohttp.ClientSession() as session:
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
    logger.info("🤖 Bot " + BOT_VERSION + " 啟動 | 推播間隔 " + str(PUSH_INTERVAL_MIN) + " 分鐘 | 黑潮頻道: " + ("ON" if BLACK_HUNTER_CHANNEL else "OFF"))

    # ⭐ v40 啟動自檢：30 秒後推送啟動通知
    async def startup_notify(ctx):
        targets = list(HUNTER_WATCHERS)
        if BLACK_HUNTER_CHANNEL:
            targets.append(BLACK_HUNTER_CHANNEL)
        if not targets:
            logger.info("無訂閱者，跳過啟動通知")
            return
        msg = ("🌊 *黑潮船長 " + BOT_VERSION + " 已啟動*\n"
                "━━━━━━━━━━━━━━━\n"
                "• 推播間隔: " + str(PUSH_INTERVAL_MIN) + " 分鐘\n"
                "• 掃描幣種: " + str(len(analyzer.SCAN_POOL)) + " 個\n"
                "• 系統狀態: ✅ 正常運作\n\n"
                "_v40 修復：放寬過濾、防卡死、保底推播_\n"
                "_點 /start → 🩺 系統狀態 可查看_")
        for t in targets:
            try:
                await ctx.bot.send_message(chat_id=t, text=msg, parse_mode="Markdown")
            except Exception as e:
                logger.error("啟動通知失敗 " + str(t) + ": " + str(e))
    app.job_queue.run_once(startup_notify, 30)
    # ⭐ 啟動自動交易背景執行緒（由 AUTO_TRADE_ENABLED 控制，未設或非 true 不啟動）
    if os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true":
        try:
            import threading as _threading
            import trader as _tr
            import auto_trader as _at

            def _auto_trade_worker():
                try:
                    logger.info("自動交易執行緒啟動｜模式: " + ("Bybit 測試網" if _tr.USE_SANDBOX else "🔴 真錢"))
                    _at.main_loop()
                except Exception as _e:
                    logger.error("🔴 自動交易背景執行緒掛了（不影響 bot）: " + str(_e)[:200])

            _at_thread = _threading.Thread(target=_auto_trade_worker, daemon=True)
            _at_thread.start()

            # ⭐ 真錢模式啟動警告（推給 ADMIN）
            if not _tr.USE_SANDBOX:
                async def _at_realmoney_warning(ctx):
                    try:
                        await ctx.bot.send_message(
                            chat_id=ADMIN_ID,
                            text="⚠️ 自動交易正以真錢模式運行｜槓桿 " + str(_at.LEVERAGE) + "｜最大倉數 " + str(_at.MAX_POSITIONS),
                        )
                    except Exception as e:
                        logger.error("真錢警告推播失敗: " + str(e))
                app.job_queue.run_once(_at_realmoney_warning, 35)
        except Exception as _e:
            logger.error("🔴 無法啟動自動交易執行緒（不影響 bot）: " + str(_e)[:150])
    else:
        logger.info("ℹ️ AUTO_TRADE_ENABLED 未設，自動交易不啟動")

    # ⭐ 個人儀表板（唯讀 PWA，由 DASH_TOKEN 控制，未設不啟動；不影響 bot 主流程）
    def _dash_state():
        return {
            "active": ACTIVE_SIGNALS,
            "results": SIGNAL_RESULTS,
            "scan": _HUNTER_SCANNING,   # 內含 last_push（epoch 秒）
            "use_redis": _USE_REDIS,
        }
    try:
        import webapp as _webapp
        _webapp.start_dashboard(_dash_state)
    except Exception as _e:
        logger.error("儀表板啟動失敗（不影響 bot）: " + str(_e)[:150])

    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
