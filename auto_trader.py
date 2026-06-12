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
TP_SPLIT = {1: 0.15, 2: 0.35, 3: 0.35, 4: 0.15}  # 四段止盈，與 bot.py 結算權重同口徑
POLL_INTERVAL = 15

PROCESSED_FILE = "processed_signals.json"
PROCESSED_CLOSES_FILE = "processed_closes.json"
TRADES_FILE = "auto_trades.json"
PENDING_FILE = "pending_orders.json"
REDIS_QUEUE_KEY = "signal_queue"
REDIS_CLOSE_KEY = "close_queue"


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


def _place_sl_and_tp(ex, symbol, side, close_side, total_amount, price, signal, record):
    """掛止損（必須成功，否則市價平倉、絕不留裸倉）+ 分批止盈（TP1~4，過小段自動合併）。"""
    sl = signal.get("sl")
    if sl:
        if side == "buy":
            safe_sl = price * (1 - MAX_SL_PCT)
            if sl < safe_sl:
                sl = safe_sl
        else:
            safe_sl = price * (1 + MAX_SL_PCT)
            if sl > safe_sl:
                sl = safe_sl
        try:
            sl = float(ex.price_to_precision(symbol, sl))  # 對齊價格精度，避免被交易所打回
        except Exception:
            pass
        try:
            slo = ex.create_order(symbol, "market", close_side, total_amount, None,
                                  {"stopLossPrice": sl, "reduceOnly": True})
            record["sl_ok"] = True
            record["sl_used"] = sl
            record["sl_order_id"] = slo.get("id")
        except Exception as e:
            record["msg"] += " | 止損掛單失敗: " + str(e)[:150]

    # 止損沒掛上（價格缺失或被交易所打回）→ 立刻平倉，絕不持有沒止損的倉
    if not record["sl_ok"]:
        record["ok"] = False
        record["closed_naked"] = True
        record["msg"] = "🔴 止損沒掛上，已立刻平倉（不留裸倉）。" + record["msg"]
        try:
            trader.close_position(ex, symbol)
            push_event("🔴 止損掛單失敗，已緊急平倉（不留裸倉）｜" + symbol)
        except Exception as e:
            record["msg"] += " | ⚠️⚠️⚠️ 平倉也失敗，請立刻手動平倉！: " + str(e)[:120]
            push_event("🔴🔴🔴 止損失敗且緊急平倉也失敗，請立刻手動處理！｜" + symbol + " | " + str(e)[:80])
        return record

    # E3：止損成功才掛止盈，TP1~4 分批；單段量過小就併入下一段，最後段不足併回前段
    min_amt = _get_min_amount(ex, symbol)
    levels = [lv for lv in (1, 2, 3, 4) if signal.get("tp%d" % lv)]
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
    return record


def open_batch_tp_position(ex, signal, equity, free_usdt=None):
    symbol = to_ccxt_symbol(signal["symbol"])
    # S5：開倉前先清掉同幣殘留的舊 TP/SL 掛單，避免干擾新倉
    try:
        trader.cancel_symbol_orders(ex, symbol)
    except Exception:
        pass
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

    # E1：止損距離（夾完 MAX_SL_PCT 之後），供風險定額計算用
    sl = signal.get("sl")
    if sl:
        raw_dist = abs(price - sl) / price
        sl_dist_pct = min(raw_dist, MAX_SL_PCT) if raw_dist > 0 else MAX_SL_PCT
    else:
        sl_dist_pct = MAX_SL_PCT

    sizing_mode = os.getenv("SIZING_MODE", "fixed")
    if sizing_mode == "risk":
        risk_pct = float(os.getenv("RISK_PER_TRADE_PCT", "0.03"))
        margin = equity * risk_pct / (sl_dist_pct * LEVERAGE)
    else:
        margin = equity / 4.0
    margin = min(margin, equity / 4.0)
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

    # 1) 市價開倉
    try:
        order = ex.create_order(symbol, "market", side, total_amount)
        record["order_id"] = order.get("id")
        record["ok"] = True
    except Exception as e:
        record["msg"] = "開倉失敗: " + str(e)[:200]
        return record

    # 2)+3) 掛止損（必須成功，否則立刻平倉）+ 分批止盈
    return _place_sl_and_tp(ex, symbol, side, close_side, total_amount, price, signal, record)


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


def process_once(ex):
    queue = read_redis_list(REDIS_QUEUE_KEY)
    processed = load_json(PROCESSED_FILE, [])
    trades = load_json(TRADES_FILE, [])
    pending = load_json(PENDING_FILE, [])
    skipped = {"tier": 0, "same_symbol": 0, "max_pos": 0, "expired": 0, "drift": 0, "breaker": 0}
    if not queue:
        _save_last_cycle(queue, pending, None, skipped, None)
        return
    try:
        equity = float(trader.get_balance(ex)) or 0.0
    except Exception as e:
        last_error = "讀餘額失敗: " + str(e)[:120]
        log("🔴 讀餘額失敗，本輪不開倉:", str(e)[:120])
        _save_last_cycle(queue, pending, None, skipped, last_error)
        return
    if equity <= 0:
        log("🔴 餘額為 0，跳過開倉")
        _save_last_cycle(queue, pending, None, skipped, "餘額為 0")
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
            log("  已達最大持倉數", MAX_POSITIONS, "，跳過剩餘")
            skipped["max_pos"] += 1
            break
        log("  處理新信號:", sig_id)
        record = open_batch_tp_position(ex, signal, equity, free_usdt)
        record["sig_id"] = sig_id
        processed.append(sig_id)
        _changed = True
        if "現價偏離信號進場價過多" in (record.get("msg") or ""):
            skipped["drift"] += 1

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
            new_pending += 1
            open_symbols.add(csym)
            pos_count += 1
            log("    🕐 限價單已掛:", record["symbol"], "@", record.get("entry"))
            push_event("🕐 限價單已掛｜" + record["symbol"] + " @ " + str(record.get("entry")))
            continue

        trades.append(record)
        new_count += 1
        if record["ok"]:
            open_symbols.add(csym)
            pos_count += 1
            log("    ✅ 下單成功:", record["symbol"],
                  "本金", record.get("margin_usdt"), "×", LEVERAGE, "倍",
                  "TP單:", len([t for t in record["tp_orders"] if t.get("ok")]),
                  "止損:", record["sl_ok"])
            push_event("✅ 開倉成功｜" + record["symbol"] + " " + record["side"] +
                       "｜本金 " + str(record.get("margin_usdt")) + "｜止損 " + ("OK" if record["sl_ok"] else "失敗"))
            if record["msg"]:
                log("    ⚠️", record["msg"])
        else:
            log("    🔴 下單失敗:", record["msg"])
            push_event("🔴 開倉失敗｜" + signal.get("symbol", "") + "｜" + record["msg"])
            last_error = signal.get("symbol", "") + "：" + record["msg"]
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
            _place_sl_and_tp(ex, symbol, side, close_side, filled, fill_price, p, record)
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
                    _place_sl_and_tp(ex, symbol, side, close_side, filled, fill_price, p, record)
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


def check_trailing_stop(ex):
    """E3：TP 鎖利階梯。隨 TP1~3 陸續成交，分三階段把止損上移鎖利（每階段只做一次）。
    sl_stage：0=未鎖利, 1=鎖30% TP1距離, 2=鎖到TP1, 3=鎖到TP2。"""
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
        tp2 = rec.get("tp2")
        stage = rec.get("sl_stage", 0)

        new_sl = None
        new_stage = stage
        if ratio <= 0.17 and stage < 3 and tp2:
            new_sl = tp2
            new_stage = 3
        elif ratio <= 0.52 and stage < 2 and tp1:
            new_sl = tp1
            new_stage = 2
        elif ratio <= 0.87 and stage < 1 and tp1 and entry:
            if side == "buy":
                new_sl = entry + (tp1 - entry) * 0.3
            else:
                new_sl = entry - (entry - tp1) * 0.3
            new_stage = 1

        if new_sl is None:
            continue

        close_side = "sell" if side == "buy" else "buy"
        old_id = rec.get("sl_order_id")
        try:
            new_sl = float(ex.price_to_precision(sym, new_sl))
        except Exception:
            pass
        # S3：先掛新止損單成功拿到 id，才撤舊單；新掛失敗保留舊單
        try:
            slo = ex.create_order(sym, "market", close_side, current_amount, None,
                                  {"stopLossPrice": new_sl, "reduceOnly": True})
        except Exception as e:
            log("  ⚠️ 鎖利上移失敗（保留舊止損單）:", sym, str(e)[:100])
            continue
        if old_id:
            try:
                ex.cancel_order(old_id, sym)
            except Exception as e:
                log("  ⚠️ 撤舊止損單失敗（新舊單可能短暫並存）:", str(e)[:100])
        rec["sl_order_id"] = slo.get("id")
        rec["sl_used"] = new_sl
        rec["sl_stage"] = new_stage
        rec["trailing_done"] = True
        changed = True
        log("  ✅ 鎖利上移:", sym, "stage", new_stage, "→ SL", new_sl)
        push_event("🔒 鎖利上移｜" + sym + " stage " + str(new_stage) + " → SL " + str(new_sl))
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
    """啟動時把佇列裡現有的舊信號/舊平倉標記為已處理。
    主要保護:第一次部署這版、或 Redis 狀態被清空時,不要把殘留 backlog 重開重平。"""
    try:
        sigs = read_redis_list(REDIS_QUEUE_KEY)
        closes = read_redis_list(REDIS_CLOSE_KEY)
        sig_ids = [s.get("id") or (s.get("symbol", "") + str(s.get("created", ""))) for s in sigs]
        close_ids = [c.get("id") or (c.get("symbol", "") + str(c.get("ts", ""))) for c in closes]
        processed = load_json(PROCESSED_FILE, [])
        save_json(PROCESSED_FILE, list(dict.fromkeys(processed + sig_ids))[-2000:])
        done = load_json(PROCESSED_CLOSES_FILE, [])
        save_json(PROCESSED_CLOSES_FILE, list(dict.fromkeys(done + close_ids))[-1000:])
        log("  🚦 啟動標記:既有", len(sig_ids), "信號 +", len(close_ids), "平倉 → 已處理,只交易啟動後的新信號")
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
    ex = trader.get_exchange()
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
