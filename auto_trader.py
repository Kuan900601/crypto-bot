"""
auto_trader.py — 自動交易橋接器（Redis 隊列｜15秒輪詢）
單筆本金 = 當前淨值 ÷ 4｜最多 4 倉｜20 倍｜同幣不疊倉｜平倉同步｜殘單清理
"""
import json
import os
import time
import math
import urllib.request
from datetime import datetime, timezone

import trader

MAX_POSITIONS = int(os.getenv("AT_MAX_POSITIONS", "4"))
LEVERAGE = int(os.getenv("AT_LEVERAGE", "20"))
MAX_SL_PCT = float(os.getenv("AT_MAX_SL_PCT", "0.035"))
ALLOWED_TIERS = [t.strip() for t in os.getenv("AUTO_TRADE_TIERS", "S,A,B").split(",") if t.strip()]
TP_SPLIT = {1: 0.40, 2: 0.35, 3: 0.25}  # v61：三段止盈 40/35/25，對齊 bot.py 結算與 Bybit 實際三段成交
POLL_INTERVAL = 15

PROCESSED_FILE = "processed_signals.json"
PROCESSED_CLOSES_FILE = "processed_closes.json"
TRADES_FILE = "auto_trades.json"
PENDING_FILE = "pending_orders.json"
REDIS_QUEUE_KEY = "signal_queue"
REDIS_CLOSE_KEY = "close_queue"
REDIS_WAITLIST_KEY = "at:waitlist"   # v62 P2b：滿倉時暫存信號，有空位再補單


def log(*a):
    """v60：強制 flush，確保 Railway 日誌即時可見。"""
    print(*a, flush=True)


def load_env():
    env = {}
    try:
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    for _k in ("BYBIT_API_KEY", "BYBIT_API_SECRET",
               "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        _v = os.environ.get(_k)
        if _v:
            env[_k] = _v
    return env


_ENV = load_env()
_REDIS_URL = _ENV.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
_REDIS_TOKEN = _ENV.get("UPSTASH_REDIS_REST_TOKEN", "")
_USE_REDIS = bool(_REDIS_URL and _REDIS_TOKEN)


# ⭐ 狀態改存 Redis(部署換容器不會丟)——根治「重啟重放 backlog」
_REDIS_STATE_KEYS = {
    PROCESSED_FILE: "at:processed_signals",
    PROCESSED_CLOSES_FILE: "at:processed_closes",
    TRADES_FILE: "at:trades",
    "liquidations.json": "at:liquidations",
    "day_equity.json": "at:day_equity",
    "breaker_tripped.json": "at:breaker_tripped",
    PENDING_FILE: "at:pending",
    "pnl_ledger.json": "at:pnl_ledger",
}


def redis_cmd(args):
    """執行單一 Redis 命令(命令數組格式)。成功回應 dict,失敗回 None。"""
    if not _USE_REDIS:
        return None
    try:
        body = json.dumps(args).encode("utf-8")
        req = urllib.request.Request(_REDIS_URL, data=body, headers={
            "Authorization": "Bearer " + _REDIS_TOKEN,
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log("🔴 Redis 命令失敗:", (args[0] if args else "?"), str(e)[:120])
        return None


def redis_get_json(key, default):
    """鍵不存在→回 default;讀取出錯→拋例外(讓本輪中止,絕不用空狀態去開/平倉)。"""
    r = redis_cmd(["GET", key])
    if r is None:
        raise RuntimeError("Redis GET 失敗,本輪中止: " + key)
    val = r.get("result")
    if val is None:
        return default
    try:
        return json.loads(val)
    except Exception:
        return default


def redis_set_json(key, data):
    r = redis_cmd(["SET", key, json.dumps(data, ensure_ascii=False)])
    if r is None:
        log("⚠️ Redis SET 失敗(狀態本輪未存,下輪會重存):", key)


def load_json(path, default):
    rkey = _REDIS_STATE_KEYS.get(path)
    if rkey and _USE_REDIS:
        return redis_get_json(rkey, default)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    rkey = _REDIS_STATE_KEYS.get(path)
    if rkey and _USE_REDIS:
        redis_set_json(rkey, data)
        return
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_redis_list(key):
    if not _USE_REDIS:
        return []
    try:
        body = json.dumps(["LRANGE", key, "0", "-1"]).encode("utf-8")
        req = urllib.request.Request(_REDIS_URL, data=body, headers={
            "Authorization": "Bearer " + _REDIS_TOKEN,
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        items = result.get("result", []) or []
        out = []
        for it in items:
            try:
                out.append(json.loads(it))
            except Exception:
                continue
        return out
    except Exception as e:
        log("🔴 讀 Redis", key, "失敗:", str(e)[:150])
        return []


def to_ccxt_symbol(sym):
    if ":" in sym:
        return sym
    if sym.endswith("/USDT"):
        return sym + ":USDT"
    return sym


def calc_amount(ex, symbol, margin_usdt, price):
    notional = margin_usdt * LEVERAGE
    raw_amount = notional / price
    try:
        market = ex.market(symbol)
        precision = market.get("precision", {}).get("amount")
        min_amt = market.get("limits", {}).get("amount", {}).get("min") or 0.0001
        if precision is not None:
            if precision < 1:
                step = precision
                raw_amount = math.floor(raw_amount / step) * step
            else:
                raw_amount = round(raw_amount, int(precision))
        return max(raw_amount, min_amt)
    except Exception:
        return max(raw_amount, 0.0001)


def _get_min_notional(ex, symbol):
    """交易所最小名目金額（USDT）。讀不到就保守用 5。"""
    try:
        market = ex.market(symbol)
        min_cost = market.get("limits", {}).get("cost", {}).get("min")
        if min_cost:
            return float(min_cost)
    except Exception:
        pass
    return 5.0


def _get_min_amount(ex, symbol):
    """交易所最小下單量。讀不到就保守用 0.0001。"""
    try:
        market = ex.market(symbol)
        return market.get("limits", {}).get("amount", {}).get("min") or 0.0001
    except Exception:
        return 0.0001


def _place_tp_orders(ex, symbol, side, close_side, total_amount, signal, record):
    """掛分批止盈（TP1~3 各自獨立 reduceOnly 條件單；某段失敗不影響整倉止損，不再因此平倉）。
    三段口徑＝TP_SPLIT 40/35/25；單段量過小就併入下一段，最後段不足併回前段。"""
    min_amt = _get_min_amount(ex, symbol)
    levels = [lv for lv in (1, 2, 3) if signal.get("tp%d" % lv)]
    final_amounts = {}
    carry = 0.0
    for i, lv in enumerate(levels):
        amt = total_amount * TP_SPLIT.get(lv, 0) + carry
        if amt < min_amt and i < len(levels) - 1:
            carry = amt
            continue
        carry = 0.0
        final_amounts[lv] = amt
    placed_levels = list(final_amounts.keys())
    if len(placed_levels) > 1 and final_amounts[placed_levels[-1]] < min_amt:
        last = placed_levels[-1]
        prev = placed_levels[-2]
        final_amounts[prev] += final_amounts.pop(last)
        log("  ℹ️ TP段合併:", symbol, "TP" + str(last), "併入 TP" + str(prev))

    for lv in levels:
        if lv not in final_amounts:
            continue
        tp_price = signal.get("tp%d" % lv)
        try:
            tp_price = float(ex.price_to_precision(symbol, tp_price))
        except Exception:
            pass
        tp_amount = final_amounts[lv]
        try:
            tpo = ex.create_order(symbol, "market", close_side, tp_amount, None,
                                  {"takeProfitPrice": tp_price, "reduceOnly": True})
            record["tp_orders"].append({"level": lv, "price": tp_price, "amount": tp_amount, "ok": True, "id": tpo.get("id")})
        except Exception as e:
            record["tp_orders"].append({"level": lv, "price": tp_price, "ok": False, "err": str(e)[:80]})
            push_event("⚠️ TP" + str(lv) + " 掛單失敗（不影響整倉止損）｜" + symbol + "｜" + str(e)[:100])
    return record


def _clamp_sl(side, ref_price, sl):
    """夾住止損距離不超過 MAX_SL_PCT。回傳止損價（無 sl 回 None）。"""
    if not sl:
        return None
    sl = float(sl)
    if side == "buy":
        return max(sl, ref_price * (1 - MAX_SL_PCT))
    return min(sl, ref_price * (1 + MAX_SL_PCT))


def _attach_position_sl(ex, symbol, sl_price, total_amount, close_side):
    """對已存在的持倉設整倉止損：優先 Bybit V5 trading-stop，退回 reduceOnly 條件單。
    回傳 (ok, sl_used, msg, error)。"""
    if not sl_price:
        return False, None, "", ""
    try:
        sl_str = ex.price_to_precision(symbol, sl_price)
    except Exception:
        sl_str = str(sl_price)
    try:
        ex.private_post_v5_position_trading_stop({
            "category": "linear",
            "symbol": trader._bybit_symbol_id(ex, symbol),
            "stopLoss": sl_str,
            "positionIdx": 0,
        })
        return True, float(sl_str), " | 整倉止損已設(V5)", ""
    except Exception as e1:
        err = str(e1)[:200]
    try:
        ex.create_order(symbol, "market", close_side, total_amount, None,
                        {"stopLossPrice": float(sl_str), "reduceOnly": True})
        return True, float(sl_str), " | 止損改用 reduceOnly 條件單", err
    except Exception as e2:
        return False, None, " | 🔴 止損 V5 與 reduceOnly 皆失敗", err + " | " + str(e2)[:150]


def _finalize_filled_position(ex, symbol, side, close_side, amount, fill_price, sig_like, record):
    """限價成交/部分成交轉正式倉：先補整倉止損，成功才掛分批止盈；止損掛不上才緊急平倉。"""
    sl_price = _clamp_sl(side, fill_price, sig_like.get("sl"))
    ok, sl_used, msg, err = _attach_position_sl(ex, symbol, sl_price, amount, close_side)
    record["sl_ok"] = ok
    record["sl_used"] = sl_used
    if msg:
        record["msg"] += msg
    if sl_price and not ok:
        record["ok"] = False
        record["closed_naked"] = True
        record["msg"] = "🔴 限價成交後止損掛失敗，緊急平倉（最後手段）。" + record["msg"]
        try:
            trader.close_position(ex, symbol)
            push_event("🔴 限價成交後止損掛失敗，已緊急平倉｜" + symbol + "｜" + err)
        except Exception as e:
            record["msg"] += " | ⚠️ 平倉也失敗，請手動平倉: " + str(e)[:120]
            push_event("🔴🔴🔴 止損失敗且緊急平倉也失敗，請手動處理｜" + symbol + " | " + str(e)[:80])
        return record
    return _place_tp_orders(ex, symbol, side, close_side, amount, sig_like, record)


def open_batch_tp_position(ex, signal, equity, free_usdt=None):
    symbol = to_ccxt_symbol(signal["symbol"])
    # S5：開倉前先清掉同幣殘留的舊 TP/SL 掛單，避免干擾新倉
    try:
        trader.cancel_symbol_orders(ex, symbol)
    except Exception as e:
        log("  ⚠️ 開倉前清舊掛單失敗（續開）:", symbol, str(e)[:100])
    direction = signal.get("direction", "").upper()
    side = "buy" if direction in ("LONG", "BUY", "做多") else "sell"
    close_side = "sell" if side == "buy" else "buy"
    ticker = ex.fetch_ticker(symbol)
    price = ticker["last"]
    record = {
        "symbol": symbol, "side": side,
        "entry_price": price,
        "opened_at": time.time(), "tp_orders": [], "sl_ok": False,
        "sl_order_id": None, "ok": False, "msg": "", "sl_stage": 0,
        "tp1": signal.get("tp1"), "tp2": signal.get("tp2"),
    }

    # v62 P2a：倉位本金固定等額 = 淨值 ÷ MAX_POSITIONS（移除 SIZING_MODE=risk 風險定額殘留）
    margin = equity / MAX_POSITIONS
    if free_usdt is not None:
        margin = min(margin, free_usdt * 0.95)
    if margin <= 0:
        record["msg"] = "可用本金不足，跳過"
        return record

    total_amount = calc_amount(ex, symbol, margin, price)
    record["margin_usdt"] = round(margin, 2)
    record["total_amount"] = total_amount

    # 名目金額低於交易所最小門檻 → 跳過
    notional = margin * LEVERAGE
    min_notional = _get_min_notional(ex, symbol)
    if notional < min_notional:
        record["msg"] = "倉位名目金額過小（" + str(round(notional, 2)) + " < 最小 " + str(min_notional) + "），跳過"
        return record

    # E2：信號要求限價單，且現價偏離進場價夠多時才掛限價單；否則照舊市價流程
    sig_entry = signal.get("entry")
    order_type = str(signal.get("order_type", "")).upper()
    use_limit = False
    if os.getenv("LIMIT_ORDERS", "true").lower() == "true" and order_type == "LIMIT" and sig_entry:
        try:
            if abs(price - float(sig_entry)) / price > 0.002:
                use_limit = True
        except Exception:
            use_limit = False

    # S2c：現價偏離信號進場價過多就放棄（僅市價單路徑；限價單路徑見 E2）
    if not use_limit and sig_entry:
        try:
            drift_pct = abs(price - float(sig_entry)) / float(sig_entry) * 100
            if drift_pct > float(os.getenv("MAX_ENTRY_DRIFT_PCT", "1.5")):
                record["msg"] = "現價偏離信號進場價過多，放棄"
                return record
        except Exception:
            pass

    try:
        ex.set_leverage(LEVERAGE, symbol)
    except Exception:
        pass

    # E2：限價單路徑——掛單後交給 process_pending 追蹤成交
    if use_limit:
        try:
            entry_px = float(ex.price_to_precision(symbol, sig_entry))
        except Exception:
            entry_px = float(sig_entry)
        try:
            order = ex.create_order(symbol, "limit", side, total_amount, entry_px)
        except Exception as e:
            record["msg"] = "限價單掛單失敗: " + str(e)[:200]
            return record
        record["ok"] = True
        record["pending"] = True
        record["order_id"] = order.get("id")
        record["entry"] = entry_px
        return record

    # 1) 市價開倉 + Bybit V5 原生附帶整倉止損（P1-1：開倉即附帶止損，無「開了卻沒止損」窗口）
    sl_price = _clamp_sl(side, price, signal.get("sl"))  # 不允許比 MAX_SL_PCT 更遠
    prot = trader.open_position_with_protection(ex, symbol, side, total_amount, sl_price)
    record["order_id"] = prot.get("order_id")
    record["ok"] = prot.get("ok", False)
    record["sl_ok"] = prot.get("sl_attached", False)
    record["sl_used"] = prot.get("sl_used")
    if prot.get("msg"):
        record["msg"] += (" | " if record["msg"] else "") + prot["msg"]
    if not record["ok"]:
        return record  # 開倉本身失敗

    # 止損附帶 + V5 fallback 皆失敗 → 最後手段才緊急平倉（不再是常態路徑）
    if sl_price and not record["sl_ok"]:
        record["ok"] = False
        record["closed_naked"] = True
        record["msg"] = "🔴 止損附帶與 V5 fallback 皆失敗，緊急平倉（最後手段）。" + record["msg"]
        try:
            trader.close_position(ex, symbol)
            push_event("🔴 止損掛單失敗，已緊急平倉（不留裸倉）｜" + symbol + "｜" + (prot.get("error") or ""))
        except Exception as e:
            record["msg"] += " | ⚠️⚠️⚠️ 平倉也失敗，請立刻手動平倉！: " + str(e)[:120]
            push_event("🔴🔴🔴 止損失敗且緊急平倉也失敗，請立刻手動處理！｜" + symbol + " | " + str(e)[:80])
        return record

    # 2) 整倉止損已附帶 → 掛分批止盈（TP1~3 獨立 reduceOnly；某段失敗不影響整倉止損）
    return _place_tp_orders(ex, symbol, side, close_side, total_amount, signal, record)


def push_event(text):
    """推一則即時事件到 Redis 'at:events'(供 bot.py 轉發 ADMIN)。失敗不影響主流程。"""
    try:
        redis_cmd(["RPUSH", "at:events", text])
        redis_cmd(["LTRIM", "at:events", "-200", "-1"])
    except Exception:
        pass


def check_circuit_breaker(equity):
    """日內熔斷：淨值跌破當日起始 ×(1-MAX_DAILY_DD) 就熔斷，當日不再開新倉。回傳 True=已熔斷。"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_json("day_equity.json", None)
    if not state or state.get("date") != today:
        state = {"date": today, "start_equity": equity}
        save_json("day_equity.json", state)
        save_json("breaker_tripped.json", None)
        return False
    if load_json("breaker_tripped.json", None):
        return True
    start_equity = state.get("start_equity") or equity
    max_dd = float(os.getenv("MAX_DAILY_DD", "0.10"))
    if start_equity > 0 and equity < start_equity * (1 - max_dd):
        save_json("breaker_tripped.json", datetime.now(timezone.utc).isoformat())
        push_event("🛑 日內熔斷觸發｜淨值 " + str(round(equity, 2)) + " < 門檻 " +
                   str(round(start_equity * (1 - max_dd), 2)) + "（當日不再開新倉）")
        log("  🛑 日內熔斷觸發！當日不再開新倉。")
        return True
    return False


def process_closes(ex):
    closes = read_redis_list(REDIS_CLOSE_KEY)
    if not closes:
        return
    done = load_json(PROCESSED_CLOSES_FILE, [])
    changed = False
    for c in closes:
        cid = c.get("id") or (c.get("symbol", "") + str(c.get("ts", "")))
        if cid in done:
            continue
        sym_raw = c.get("symbol", "")
        if not sym_raw:
            done.append(cid); changed = True; continue
        csym = to_ccxt_symbol(sym_raw)
        log("  ⏹ 收到平倉通知:", sym_raw, "｜", c.get("reason", ""))
        try:
            cancelled = trader.cancel_symbol_orders(ex, csym)
        except Exception as e:
            cancelled = 0
            log("    ⚠️ 取消掛單出錯:", str(e)[:100])
        try:
            ok = trader.close_position(ex, csym)
            log("    平倉:", "✅" if ok else "🔴", "｜取消掛單", cancelled, "張")
            push_event(("✅" if ok else "🔴") + " 平倉同步｜" + sym_raw + "｜" + c.get("reason", ""))
        except Exception as e:
            log("    🔴 平倉出錯:", str(e)[:120])
            push_event("🔴 平倉同步出錯｜" + sym_raw + "｜" + str(e)[:100])
        done.append(cid)
        changed = True
    if changed:
        save_json(PROCESSED_CLOSES_FILE, done[-1000:])


def _save_last_cycle(queue, pending, open_positions, skipped, last_error):
    """v60：每輪結束寫 at:last_cycle，供 /at_debug 判斷自動交易卡在哪一環。"""
    redis_cmd(["SET", "at:last_cycle", json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "queue_len": len(queue),
        "pending_len": len(pending),
        "open_positions": open_positions,
        "skipped": skipped,
        "last_error": last_error,
    }, ensure_ascii=False)])


def _commit_open_record(record, signal, sig_id, trades, pending, open_symbols):
    """把 open_batch_tp_position 的 record 落地到 pending/trades，回傳 'pending'|'ok'|'fail'。
    （主佇列開倉與候補補單共用，避免重複那段落地邏輯。）"""
    csym = to_ccxt_symbol(signal.get("symbol", ""))
    if record.get("pending"):
        pending.append({
            "sig_id": sig_id, "symbol": record["symbol"], "side": record["side"],
            "order_id": record.get("order_id"), "entry": record.get("entry"),
            "sl": signal.get("sl"), "tp1": signal.get("tp1"), "tp2": signal.get("tp2"),
            "tp3": signal.get("tp3"), "tp4": signal.get("tp4"),
            "amount": record.get("total_amount"), "margin_usdt": record.get("margin_usdt", 0),
            "created_ts": time.time(),
            "expire_ts": time.time() + float(signal.get("order_valid_hours", 8)) * 3600,
            "tier": signal.get("tier"),
        })
        open_symbols.add(csym)
        log("    🕐 限價單已掛:", record["symbol"], "@", record.get("entry"))
        push_event("🕐 限價單已掛｜" + record["symbol"] + " @ " + str(record.get("entry")))
        return "pending"
    trades.append(record)
    if record["ok"]:
        open_symbols.add(csym)
        log("    ✅ 下單成功:", record["symbol"],
            "本金", record.get("margin_usdt"), "×", LEVERAGE, "倍",
            "TP單:", len([t for t in record["tp_orders"] if t.get("ok")]),
            "止損:", record["sl_ok"])
        push_event("✅ 開倉成功｜" + record["symbol"] + " " + record["side"] +
                   "｜本金 " + str(record.get("margin_usdt")) + "｜止損 " + ("OK" if record["sl_ok"] else "失敗"))
        if record["msg"]:
            log("    ⚠️", record["msg"])
        return "ok"
    log("    🔴 下單失敗:", record["msg"])
    push_event("🔴 開倉失敗｜" + signal.get("symbol", "") + "｜" + record["msg"])
    return "fail"


def process_once(ex):
    queue = read_redis_list(REDIS_QUEUE_KEY)
    processed = load_json(PROCESSED_FILE, [])
    trades = load_json(TRADES_FILE, [])
    pending = load_json(PENDING_FILE, [])
    waitlist = read_redis_list(REDIS_WAITLIST_KEY)   # v62 P2b：滿倉候補
    waitlist_changed = False
    skipped = {"tier": 0, "same_symbol": 0, "max_pos": 0, "expired": 0, "drift": 0, "breaker": 0}
    if not queue and not waitlist:
        _save_last_cycle(queue, pending, None, skipped, None)
        return
    try:
        equity = float(trader.get_balance(ex)) or 0.0
    except Exception as e:
        last_error = "讀餘額失敗: " + str(e)[:120]
        log("🔴 讀餘額失敗，本輪不開倉:", str(e)[:120])
        push_event("🔴 讀餘額失敗，本輪不開倉｜" + str(e)[:150])
        _save_last_cycle(queue, pending, None, skipped, last_error)
        return
    if equity <= 0:
        log("🔴 餘額為 0，跳過開倉（請確認資金在統一交易帳戶 UTA、API 已開合約權限）")
        push_event("🔴 餘額為 0，跳過開倉｜請確認資金在統一交易帳戶 UTA、API 已開合約權限")
        _save_last_cycle(queue, pending, None, skipped, "餘額為 0（請確認資金在 UTA 統一帳戶、API 開合約權限）")
        return
    if check_circuit_breaker(equity):
        skipped["breaker"] = 1
        log("  🛑 日內熔斷中，本輪不開新倉")
        _save_last_cycle(queue, pending, None, skipped, None)
        return
    free_usdt = trader.get_free_balance(ex)

    current_positions = trader.get_positions(ex)
    open_symbols = {to_ccxt_symbol(p["symbol"]) for p in current_positions}
    # E2：pending 限價單視同占一倉
    open_symbols |= {to_ccxt_symbol(p.get("symbol", "")) for p in pending}
    pos_count = len(current_positions) + len(pending)
    new_count = 0
    new_pending = 0
    last_error = None
    _changed = False
    for signal in queue:
        sig_id = signal.get("id") or (signal.get("symbol", "") + str(signal.get("created", "")))
        if sig_id in processed:
            continue
        # S2b：信號太舊就不追了
        created_str = signal.get("created")
        if created_str:
            try:
                created_dt = datetime.fromisoformat(created_str)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_min = (datetime.now(timezone.utc) - created_dt).total_seconds() / 60.0
                if age_min > float(os.getenv("SIGNAL_MAX_AGE_MIN", "10")):
                    log("  ⏭ 跳過", signal.get("symbol"), "：信號過舊（", round(age_min, 1), "分鐘）")
                    processed.append(sig_id)
                    _changed = True
                    skipped["expired"] += 1
                    continue
            except Exception:
                pass
        if signal.get("tier", "B") not in ALLOWED_TIERS:
            processed.append(sig_id)
            _changed = True
            skipped["tier"] += 1
            continue
        csym = to_ccxt_symbol(signal.get("symbol", ""))
        if csym in open_symbols:
            log("  ⏭ 跳過", signal.get("symbol"), "：同幣已有持倉（不疊倉）")
            processed.append(sig_id)
            _changed = True
            skipped["same_symbol"] += 1
            continue
        if pos_count >= MAX_POSITIONS:
            # v62 P2b：滿倉 → 進候補（不丟棄、不 mark processed），有空位再補單；bot 端照推 TG
            wl_ids = {(w.get("id") or (w.get("symbol", "") + str(w.get("created", "")))) for w in waitlist}
            if sig_id not in wl_ids:
                waitlist.append(signal)
                waitlist_changed = True
                log("  🪧 滿倉，信號進候補:", signal.get("symbol"))
            skipped["max_pos"] += 1
            continue
        log("  處理新信號:", sig_id)
        record = open_batch_tp_position(ex, signal, equity, free_usdt)
        record["sig_id"] = sig_id
        processed.append(sig_id)
        _changed = True
        if "現價偏離信號進場價過多" in (record.get("msg") or ""):
            skipped["drift"] += 1
        outcome = _commit_open_record(record, signal, sig_id, trades, pending, open_symbols)
        if outcome == "pending":
            new_pending += 1
            pos_count += 1
        else:
            new_count += 1
            if outcome == "ok":
                pos_count += 1
            else:
                last_error = signal.get("symbol", "") + "：" + record["msg"]

    # v62 P2b：有空位 → 從候補「由新到舊」補單；超時/漂移過大則放棄
    if pos_count < MAX_POSITIONS and waitlist:
        wl_max_age = float(os.getenv("WAITLIST_MAX_AGE_MIN", "60"))
        max_drift = float(os.getenv("MAX_ENTRY_DRIFT_PCT", "1.5"))
        kept = []
        for w in reversed(waitlist):   # newest 在尾端 → reversed 即由新到舊
            w_id = w.get("id") or (w.get("symbol", "") + str(w.get("created", "")))
            wsym = to_ccxt_symbol(w.get("symbol", ""))
            # 已被主佇列處理過（開倉或過期）→ 候補副本作廢，丟棄不重開
            if w_id in processed:
                waitlist_changed = True
                continue
            # 年齡
            age_min = None
            if w.get("created"):
                try:
                    cdt = datetime.fromisoformat(w["created"])
                    if cdt.tzinfo is None:
                        cdt = cdt.replace(tzinfo=timezone.utc)
                    age_min = (datetime.now(timezone.utc) - cdt).total_seconds() / 60.0
                except Exception:
                    age_min = None
            if age_min is not None and age_min > wl_max_age:
                if w_id not in processed:
                    processed.append(w_id); _changed = True
                waitlist_changed = True
                log("  🪧 候補超時放棄:", w.get("symbol"), round(age_min, 1), "分")
                continue
            # 沒空位 / 同幣已持倉 → 留到下輪
            if pos_count >= MAX_POSITIONS or wsym in open_symbols:
                kept.append(w); continue
            # 現價偏離信號 entry 過大 → 放棄不追高
            try:
                cur_px = float(ex.fetch_ticker(wsym)["last"])
                w_entry = w.get("entry")
                if w_entry and abs(cur_px - float(w_entry)) / float(w_entry) * 100 > max_drift:
                    if w_id not in processed:
                        processed.append(w_id); _changed = True
                    waitlist_changed = True
                    log("  🪧 候補漂移過大放棄:", w.get("symbol"))
                    continue
            except Exception:
                kept.append(w); continue   # 取價失敗 → 留著下輪再試
            # 補單
            log("  🪧 候補補單:", w.get("symbol"))
            record = open_batch_tp_position(ex, w, equity, free_usdt)
            record["sig_id"] = w_id
            record["from_waitlist"] = True
            if w_id not in processed:
                processed.append(w_id)
            _changed = True
            waitlist_changed = True
            outcome = _commit_open_record(record, w, w_id, trades, pending, open_symbols)
            if outcome == "pending":
                new_pending += 1
                pos_count += 1
            else:
                new_count += 1
                if outcome == "ok":
                    pos_count += 1
                else:
                    last_error = w.get("symbol", "") + "：" + record["msg"]
        # 重建候補（kept 是反序蒐集，還原成 oldest→newest）
        if waitlist_changed:
            new_waitlist = list(reversed(kept))[-20:]
            redis_cmd(["DEL", REDIS_WAITLIST_KEY])
            for w in new_waitlist:
                redis_cmd(["RPUSH", REDIS_WAITLIST_KEY, json.dumps(w, ensure_ascii=False)])
            waitlist_changed = False
    # 滿倉這輪只新增候補、沒補單 → 寫回（含去重後的新候補）
    if waitlist_changed:
        redis_cmd(["DEL", REDIS_WAITLIST_KEY])
        for w in waitlist[-20:]:
            redis_cmd(["RPUSH", REDIS_WAITLIST_KEY, json.dumps(w, ensure_ascii=False)])

    if _changed:
        save_json(PROCESSED_FILE, processed[-2000:])
    if new_pending > 0:
        save_json(PENDING_FILE, pending[-100:])
    if new_count > 0:
        save_json(TRADES_FILE, trades[-1000:])
        log("  本輪處理", new_count, "個新信號。總紀錄:", len(trades))
    _save_last_cycle(queue, pending, len(current_positions), skipped, last_error)


def process_pending(ex):
    """E2：追蹤限價單成交/過期。成交→補 SL/TP 轉正式倉；過期→撤單，碎股嘗試平倉。"""
    pending = load_json(PENDING_FILE, [])
    if not pending:
        return
    trades = load_json(TRADES_FILE, [])
    now = time.time()
    remaining = []
    changed_pending = False
    changed_trades = False
    for p in pending:
        symbol = p.get("symbol", "")
        order_id = p.get("order_id")
        side = p.get("side", "buy")
        close_side = "sell" if side == "buy" else "buy"
        try:
            order = ex.fetch_order(order_id, symbol)
        except Exception as e:
            log("  ⚠️ 查詢限價單失敗:", symbol, str(e)[:100])
            remaining.append(p)
            continue

        status = order.get("status")
        amount = float(p.get("amount") or 0)
        filled = float(order.get("filled") or 0)
        is_filled = status == "closed" or (amount > 0 and filled >= amount * 0.999)
        is_expired = now >= p.get("expire_ts", 0)

        if is_filled:
            fill_price = float(order.get("average") or p.get("entry") or 0)
            record = {
                "symbol": symbol, "side": side, "sig_id": p.get("sig_id"),
                "margin_usdt": p.get("margin_usdt", 0),
                "entry_price": fill_price, "total_amount": filled,
                "opened_at": time.time(), "tp_orders": [], "sl_ok": False,
                "sl_order_id": None, "ok": True, "msg": "", "sl_stage": 0,
                "tp1": p.get("tp1"), "tp2": p.get("tp2"),
            }
            _finalize_filled_position(ex, symbol, side, close_side, filled, fill_price, p, record)
            trades.append(record)
            changed_trades = True
            changed_pending = True
            log("  ✅ 限價單成交:", symbol, "@", fill_price)
            push_event("✅ 限價成交｜" + symbol + " @ " + str(fill_price))
            continue

        if is_expired:
            try:
                ex.cancel_order(order_id, symbol)
            except Exception as e:
                log("  ⚠️ 取消過期限價單失敗:", symbol, str(e)[:100])
            if filled > 0:
                min_amt = _get_min_amount(ex, symbol)
                if filled >= min_amt:
                    fill_price = float(order.get("average") or p.get("entry") or 0)
                    record = {
                        "symbol": symbol, "side": side, "sig_id": p.get("sig_id"),
                        "margin_usdt": p.get("margin_usdt", 0),
                        "entry_price": fill_price, "total_amount": filled,
                        "opened_at": time.time(), "tp_orders": [], "sl_ok": False,
                        "sl_order_id": None, "ok": True, "msg": "", "sl_stage": 0,
                        "tp1": p.get("tp1"), "tp2": p.get("tp2"),
                    }
                    _finalize_filled_position(ex, symbol, side, close_side, filled, fill_price, p, record)
                    trades.append(record)
                    changed_trades = True
                    log("  ⚠️ 限價單部分成交後過期，已轉正式倉:", symbol, "量", filled)
                    push_event("⚠️ 限價單部分成交後過期，已轉正式倉｜" + symbol + "（量 " + str(filled) + "）")
                else:
                    try:
                        ex.create_order(symbol, "market", close_side, filled, None, {"reduceOnly": True})
                        push_event("⚠️ 限價單碎股已市價平掉｜" + symbol + "（量 " + str(filled) + "）")
                    except Exception as e:
                        push_event("🔴🔴 限價單碎股無法平倉，請手動處理｜" + symbol + " 量 " + str(filled) + " | " + str(e)[:80])
            else:
                log("  ⏰ 限價單過期未成交，已取消:", symbol)
                push_event("⏰ 限價單過期未成交，已取消｜" + symbol)
            changed_pending = True
            continue

        remaining.append(p)

    if changed_pending:
        save_json(PENDING_FILE, remaining[-100:])
    if changed_trades:
        save_json(TRADES_FILE, trades[-1000:])


def _atr_pct(ex, symbol):
    """最近 14 根 1h ATR / 收盤價。讀不到回 None。"""
    try:
        ohlcv = ex.fetch_ohlcv(symbol, "1h", limit=20)
        if not ohlcv or len(ohlcv) < 15:
            return None
        trs = []
        prev_close = ohlcv[0][4]
        for o in ohlcv[1:]:
            high, low, close = o[2], o[3], o[4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            prev_close = close
        atr = sum(trs[-14:]) / min(14, len(trs))
        last_close = ohlcv[-1][4]
        if last_close > 0:
            return atr / last_close
    except Exception:
        return None
    return None


def _trail_buffer_pct(ex, symbol):
    """止損緩衝 = max(TRAIL_BUFFER_MIN_PCT, 0.5×ATR%)。讀不到 ATR 用最小值。"""
    min_buf = float(os.getenv("TRAIL_BUFFER_MIN_PCT", "0.004"))
    atr_pct = _atr_pct(ex, symbol)
    if atr_pct:
        return max(min_buf, 0.5 * atr_pct)
    return min_buf


def check_trailing_stop(ex):
    """E3 / v61：TP 成交階梯移動整倉止損（每階段只做一次，用 V5 trading-stop 原子更新位階止損）。
    依剩餘倉位比例反推已成交到哪一段（三段 40/35/25：TP1後≈0.60、TP2後≈0.25、TP3後≈0）：
      stage1（TP1 成交）→ entry−緩衝（給回踩留空間，非死保本）
      stage2（TP2 成交）→ entry（此時才保本）
      stage3（TP3 成交）→ TP1
    緩衝用 max(TRAIL_BUFFER_MIN_PCT, 0.5×1h ATR%)。整倉止損為位階屬性，更新即原子取代，無需先撤舊單。"""
    trades = load_json(TRADES_FILE, [])
    positions = trader.get_positions(ex)
    pos_map = {to_ccxt_symbol(p["symbol"]): p for p in positions}
    changed = False
    for rec in trades:
        if not rec.get("ok"):
            continue
        sym = rec["symbol"]
        p = pos_map.get(sym)
        if not p:
            continue
        current_amount = abs(p.get("contracts", 0))
        total_amount = rec.get("total_amount") or 0
        if current_amount <= 0 or total_amount <= 0:
            continue
        ratio = current_amount / total_amount
        side = rec["side"]
        entry = rec.get("entry_price")
        tp1 = rec.get("tp1")
        stage = rec.get("sl_stage", 0)
        if not entry:
            continue

        new_sl = None
        new_stage = stage
        if ratio <= 0.05 and stage < 3 and tp1:
            new_sl = tp1
            new_stage = 3
        elif ratio <= 0.27 and stage < 2:
            new_sl = entry  # TP2 成交 → 保本
            new_stage = 2
        elif ratio <= 0.62 and stage < 1:
            buf = _trail_buffer_pct(ex, sym)
            new_sl = entry * (1 - buf) if side == "buy" else entry * (1 + buf)
            new_stage = 1

        if new_sl is None:
            continue

        try:
            sl_str = ex.price_to_precision(sym, new_sl)
        except Exception:
            sl_str = str(new_sl)
        # 用 V5 trading-stop 原子更新整倉止損（無需先撤舊單）；失敗保留原止損
        try:
            ex.private_post_v5_position_trading_stop({
                "category": "linear",
                "symbol": trader._bybit_symbol_id(ex, sym),
                "stopLoss": sl_str,
                "positionIdx": 0,
            })
        except Exception as e:
            log("  ⚠️ 止損上移失敗（保留原止損）:", sym, str(e)[:100])
            continue
        rec["sl_used"] = float(sl_str)
        rec["sl_stage"] = new_stage
        rec["trailing_done"] = True
        changed = True
        log("  ✅ 止損上移:", sym, "stage", new_stage, "→ SL", sl_str)
        push_event("🔒 止損上移 stage" + str(new_stage) + "｜" + sym + " → SL " + str(sl_str))
    if changed:
        save_json(TRADES_FILE, trades)


def reconcile_stale_orders(ex):
    trades = load_json(TRADES_FILE, [])
    positions = trader.get_positions(ex)
    open_syms = {to_ccxt_symbol(p["symbol"]) for p in positions}
    changed = False
    now = time.time()
    for rec in trades:
        if not rec.get("ok") or rec.get("cleaned"):
            continue
        if now - rec.get("opened_at", 0) < 60:
            continue
        sym = rec["symbol"]
        if sym in open_syms:
            continue
        cancelled = 0
        try:
            cancelled = trader.cancel_symbol_orders(ex, sym)
        except Exception:
            pass
        rec["cleaned"] = True
        changed = True
        if cancelled:
            log("  🧹 清理殘單:", sym, "取消", cancelled, "張")
    if changed:
        save_json(TRADES_FILE, trades)


def check_liquidations(ex):
    liq_file = "liquidations.json"
    data = load_json(liq_file, {"count": 0, "seen_ids": [], "records": []})
    try:
        liqs = ex.fetch_my_liquidations()
    except Exception:
        return
    new = 0
    for lq in liqs:
        lid = str(lq.get("id") or lq.get("timestamp") or lq.get("info", {}))
        if lid in data["seen_ids"]:
            continue
        data["seen_ids"] = data["seen_ids"][-200:]
        data["seen_ids"].append(lid)
        data["count"] += 1
        data["records"].append({
            "symbol": lq.get("symbol"),
            "time": lq.get("datetime"),
            "amount": lq.get("contracts") or lq.get("amount"),
        })
        data["records"] = data["records"][-100:]
        new += 1
        log("  🔴🔴🔴 偵測到爆倉！", lq.get("symbol"), "（累計:", data["count"], "）")
    if new > 0:
        save_json(liq_file, data)
        log("  ⚠️ 本輪新增", new, "次爆倉。請留意 liquidations.json")


def update_pnl_ledger(ex):
    """E5：抓 Bybit 已實現損益（約每 10 分鐘一次），以 orderId+updatedTime 去重後寫入 at:pnl_ledger。"""
    raw_list = []
    try:
        positions = ex.fetch_positions_history(None, None, 50, {"category": "linear"})
        raw_list = [p.get("info", {}) for p in positions]
    except Exception:
        try:
            resp = ex.private_get_v5_position_closed_pnl({"category": "linear", "limit": "50"})
            raw_list = (resp.get("result") or {}).get("list") or []
        except Exception as e:
            log("  ⚠️ 抓真實 PnL 失敗（本輪略過）:", str(e)[:120])
            return

    if not raw_list:
        return

    ledger = load_json("pnl_ledger.json", [])
    seen = {(str(r.get("order_id")), str(r.get("updated_time"))) for r in ledger}
    changed = False
    for r in raw_list:
        order_id = r.get("orderId")
        updated_time = r.get("updatedTime")
        key = (str(order_id), str(updated_time))
        if key in seen:
            continue
        try:
            ts = float(updated_time) / 1000.0 if updated_time else time.time()
            ledger.append({
                "symbol": r.get("symbol"),
                "side": r.get("side"),
                "qty": float(r.get("qty") or 0),
                "avg_entry": float(r.get("avgEntryPrice") or 0),
                "avg_exit": float(r.get("avgExitPrice") or 0),
                "closed_pnl": float(r.get("closedPnl") or 0),
                "order_id": order_id,
                "updated_time": updated_time,
                "ts": ts,
            })
        except Exception:
            continue
        seen.add(key)
        changed = True
    if changed:
        ledger.sort(key=lambda x: x.get("ts", 0))
        save_json("pnl_ledger.json", ledger[-500:])


def mark_backlog_processed():
    """啟動時把佇列裡「過舊」的信號標記為已處理；新鮮信號保留給正常流程處理。
    主要保護:第一次部署這版、或 Redis 狀態被清空時,不要把殘留 backlog 重開重平；
    同時修掉「每次部署都吃掉剛推播的新信號」的問題（年齡檢查在 process_once 也有，雙重防呆）。"""
    try:
        max_age = float(os.getenv("SIGNAL_MAX_AGE_MIN", "10"))
        now = datetime.now(timezone.utc)
        sigs = read_redis_list(REDIS_QUEUE_KEY)
        closes = read_redis_list(REDIS_CLOSE_KEY)
        old_sig_ids = []
        fresh_count = 0
        for s in sigs:
            sig_id = s.get("id") or (s.get("symbol", "") + str(s.get("created", "")))
            created_str = s.get("created")
            is_old = True
            if created_str:
                try:
                    created_dt = datetime.fromisoformat(created_str)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    age_min = (now - created_dt).total_seconds() / 60.0
                    is_old = age_min > max_age
                except Exception:
                    is_old = True  # created 格式無法解析 → 視為過舊，不冒險下單
            if is_old:
                old_sig_ids.append(sig_id)
            else:
                fresh_count += 1
        close_ids = [c.get("id") or (c.get("symbol", "") + str(c.get("ts", ""))) for c in closes]
        processed = load_json(PROCESSED_FILE, [])
        save_json(PROCESSED_FILE, list(dict.fromkeys(processed + old_sig_ids))[-2000:])
        done = load_json(PROCESSED_CLOSES_FILE, [])
        save_json(PROCESSED_CLOSES_FILE, list(dict.fromkeys(done + close_ids))[-1000:])
        log("  🚦 啟動標記:", len(old_sig_ids), "個過舊信號 +", len(close_ids), "個平倉 → 已處理,",
            fresh_count, "個新鮮信號保留給正常流程")
    except Exception as e:
        log("⚠️ 啟動標記 backlog 失敗(略過,改靠 Redis 既有狀態保護):", str(e)[:120])


def main_loop():
    log("=" * 50)
    log("auto_trader.py 自動交易（Redis｜輪詢", POLL_INTERVAL, "秒）")
    log("=" * 50)
    log("模式：", "Bybit 測試網(假錢)" if trader.USE_SANDBOX else "🔴🔴🔴 真錢 🔴🔴🔴")
    log("設定：最多", MAX_POSITIONS, "倉｜單筆本金 = 淨值 ÷ 4｜槓桿", LEVERAGE, "｜等級", ALLOWED_TIERS)
    log("⚠️ 20倍：爆倉線約 -5%，止損強制收緊到最遠 -3.5%（留爆倉緩衝）")
    log("⚠️ 日內熔斷：淨值跌破當日起始 ×(1-" + os.getenv("MAX_DAILY_DD", "0.10") + ")，當日不再開新倉")
    if not _USE_REDIS:
        log("🔴 .env 缺 Upstash Redis 設定，無法讀信號")
        return
    # 2a：連線/憑證失敗不讓執行緒永久死亡——每 60 秒重試，連續失敗每 10 次推一則 at:events
    ex = None
    fail_count = 0
    while ex is None:
        try:
            ex = trader.get_exchange()
            trader.get_balance(ex)
        except Exception as e:
            fail_count += 1
            log("🔴 連線/讀餘額失敗（第", fail_count, "次），60 秒後重試:", str(e)[:150])
            if fail_count % 10 == 0:
                push_event("🔴 auto_trader 連線失敗已 " + str(fail_count) + " 次，請檢查 BYBIT_API_KEY/SECRET 與網路: " + str(e)[:150])
            ex = None
            time.sleep(60)
    # S6：啟動時確認帳戶為單向持倉模式（失敗只警告，不中斷）
    try:
        ex.set_position_mode(False)
    except Exception as e:
        log("⚠️ 設定單向持倉模式失敗，請確認 Bybit 帳戶為 One-Way 模式:", str(e)[:120])
    log("✅ 連線成功，餘額:", trader.get_balance(ex))
    log("開始輪詢...（Ctrl+C 停止）\n")
    mark_backlog_processed()
    round_num = 0
    while True:
        try:
            process_closes(ex)
            process_once(ex)
            process_pending(ex)
            check_trailing_stop(ex)
            reconcile_stale_orders(ex)
            check_liquidations(ex)
            round_num += 1
            if round_num % 40 == 0:
                update_pnl_ledger(ex)
        except KeyboardInterrupt:
            log("\n已停止。")
            break
        except Exception as e:
            log("⚠️ 本輪出錯（繼續下一輪）:", str(e)[:150])
        redis_cmd(["SET", "at:heartbeat", datetime.now(timezone.utc).isoformat()])
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
