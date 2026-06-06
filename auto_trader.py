"""
auto_trader.py — 自動交易橋接器（Redis 隊列｜15秒輪詢）
單筆本金 = 當前淨值 ÷ 4｜最多 4 倉｜15 倍｜同幣不疊倉｜平倉同步｜殘單清理
"""
import json
import os
import time
import math
import urllib.request

import trader

MAX_POSITIONS = 4
LEVERAGE = 15
MAX_SL_PCT = 0.04
ALLOWED_TIERS = ["S", "A", "B", "C"]
TP_SPLIT = {1: 0.15, 2: 0.35, 3: 0.35, 4: 0.15}
POLL_INTERVAL = 15

PROCESSED_FILE = "processed_signals.json"
PROCESSED_CLOSES_FILE = "processed_closes.json"
TRADES_FILE = "auto_trades.json"
REDIS_QUEUE_KEY = "signal_queue"
REDIS_CLOSE_KEY = "close_queue"


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
    for _k in ("BINGX_API_KEY", "BINGX_API_SECRET",
               "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        _v = os.environ.get(_k)
        if _v:
            env[_k] = _v
    return env


_ENV = load_env()
_REDIS_URL = _ENV.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
_REDIS_TOKEN = _ENV.get("UPSTASH_REDIS_REST_TOKEN", "")
_USE_REDIS = bool(_REDIS_URL and _REDIS_TOKEN)


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
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
        print("🔴 讀 Redis", key, "失敗:", str(e)[:150])
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


def open_batch_tp_position(ex, signal, margin_usdt):
    symbol = to_ccxt_symbol(signal["symbol"])
    direction = signal.get("direction", "").upper()
    side = "buy" if direction in ("LONG", "BUY", "做多") else "sell"
    ticker = ex.fetch_ticker(symbol)
    price = ticker["last"]
    total_amount = calc_amount(ex, symbol, margin_usdt, price)
    position_side = "LONG" if side == "buy" else "SHORT"
    close_side = "sell" if side == "buy" else "buy"
    record = {
        "symbol": symbol, "side": side,
        "margin_usdt": round(margin_usdt, 2),
        "entry_price": price, "total_amount": total_amount,
        "opened_at": time.time(), "tp_orders": [], "sl_ok": False,
        "sl_order_id": None, "ok": False, "msg": "",
    }
    try:
        ex.set_leverage(LEVERAGE, symbol, {"side": position_side})
    except Exception:
        pass
    try:
        order = ex.create_order(symbol, "market", side, total_amount, None,
                                {"positionSide": position_side})
        record["order_id"] = order.get("id")
        record["ok"] = True
    except Exception as e:
        record["msg"] = "開倉失敗: " + str(e)[:200]
        return record
    sl = signal.get("sl")
    if sl:
        if side == "buy":
            safe_sl = price * (1 - MAX_SL_PCT)
            if sl < safe_sl:
                record["msg"] += " | 止損從 %.6f 收緊到 %.6f（爆倉保護）" % (sl, safe_sl)
                sl = safe_sl
        else:
            safe_sl = price * (1 + MAX_SL_PCT)
            if sl > safe_sl:
                record["msg"] += " | 止損從 %.6f 收緊到 %.6f（爆倉保護）" % (sl, safe_sl)
                sl = safe_sl
        try:
            slo = ex.create_order(symbol, "STOP_MARKET", close_side, total_amount, None,
                                  {"positionSide": position_side, "stopPrice": sl})
            record["sl_ok"] = True
            record["sl_used"] = sl
            record["sl_order_id"] = slo.get("id")
        except Exception as e:
            record["msg"] += " | 止損失敗: " + str(e)[:120]
    for level in (1, 2, 3, 4):
        tp_price = signal.get("tp%d" % level)
        if not tp_price:
            continue
        tp_amount = total_amount * TP_SPLIT[level]
        try:
            tpo = ex.create_order(symbol, "TAKE_PROFIT_MARKET", close_side, tp_amount, None,
                                  {"positionSide": position_side, "stopPrice": tp_price})
            record["tp_orders"].append({"level": level, "price": tp_price, "amount": tp_amount, "ok": True, "id": tpo.get("id")})
        except Exception as e:
            record["tp_orders"].append({"level": level, "price": tp_price, "ok": False, "err": str(e)[:80]})
    if record["ok"] and sl and not record["sl_ok"]:
        record["msg"] = "🔴🔴🔴 開倉成功但止損沒掛上！" + record["msg"]
    return record


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
        print("  ⏹ 收到平倉通知:", sym_raw, "｜", c.get("reason", ""))
        try:
            cancelled = trader.cancel_symbol_orders(ex, csym)
        except Exception as e:
            cancelled = 0
            print("    ⚠️ 取消掛單出錯:", str(e)[:100])
        try:
            ok = trader.close_position(ex, csym)
            print("    平倉:", "✅" if ok else "🔴", "｜取消掛單", cancelled, "張")
        except Exception as e:
            print("    🔴 平倉出錯:", str(e)[:120])
        done.append(cid)
        changed = True
    if changed:
        save_json(PROCESSED_CLOSES_FILE, done[-1000:])


def process_once(ex):
    queue = read_redis_list(REDIS_QUEUE_KEY)
    processed = load_json(PROCESSED_FILE, [])
    trades = load_json(TRADES_FILE, [])
    if not queue:
        return
    try:
        equity = float(trader.get_balance(ex)) or 0.0
    except Exception as e:
        print("🔴 讀餘額失敗，本輪不開倉:", str(e)[:120])
        return
    if equity <= 0:
        print("🔴 餘額為 0，跳過開倉")
        return
    per_position_margin = equity / 4.0

    current_positions = trader.get_positions(ex)
    open_symbols = {to_ccxt_symbol(p["symbol"]) for p in current_positions}
    pos_count = len(current_positions)
    new_count = 0
    for signal in queue:
        sig_id = signal.get("id") or (signal.get("symbol", "") + str(signal.get("created", "")))
        if sig_id in processed:
            continue
        if signal.get("tier", "B") not in ALLOWED_TIERS:
            processed.append(sig_id)
            continue
        csym = to_ccxt_symbol(signal.get("symbol", ""))
        if csym in open_symbols:
            print("  ⏭ 跳過", signal.get("symbol"), "：同幣已有持倉（不疊倉）")
            processed.append(sig_id)
            continue
        if pos_count >= MAX_POSITIONS:
            print("  已達最大持倉數", MAX_POSITIONS, "，跳過剩餘")
            break
        print("  處理新信號:", sig_id, "｜本金", round(per_position_margin, 2), "×", LEVERAGE, "倍")
        record = open_batch_tp_position(ex, signal, per_position_margin)
        record["sig_id"] = sig_id
        trades.append(record)
        processed.append(sig_id)
        new_count += 1
        if record["ok"]:
            open_symbols.add(csym)
            pos_count += 1
            print("    ✅ 下單成功:", record["symbol"],
                  "TP單:", len([t for t in record["tp_orders"] if t.get("ok")]),
                  "止損:", record["sl_ok"])
            if record["msg"]:
                print("    ⚠️", record["msg"])
        else:
            print("    🔴 下單失敗:", record["msg"])
    if new_count > 0:
        save_json(PROCESSED_FILE, processed[-2000:])
        save_json(TRADES_FILE, trades[-1000:])
        print("  本輪處理", new_count, "個新信號。總紀錄:", len(trades))


def check_trailing_stop(ex):
    trades = load_json(TRADES_FILE, [])
    positions = trader.get_positions(ex)
    pos_map = {to_ccxt_symbol(p["symbol"]): p for p in positions}
    changed = False
    for rec in trades:
        if not rec.get("ok") or rec.get("trailing_done"):
            continue
        sym = rec["symbol"]
        p = pos_map.get(sym)
        if not p:
            continue
        current_amount = abs(p.get("contracts", 0))
        if current_amount <= 0:
            continue
        if current_amount < rec["total_amount"] * 0.95:
            entry = rec["entry_price"]
            side = rec["side"]
            position_side = "LONG" if side == "buy" else "SHORT"
            close_side = "sell" if side == "buy" else "buy"
            old_id = rec.get("sl_order_id")
            if old_id:
                try:
                    ex.cancel_order(old_id, sym)
                except Exception:
                    pass
            try:
                slo = ex.create_order(sym, "STOP_MARKET", close_side, current_amount, None,
                                      {"positionSide": position_side, "stopPrice": entry})
                rec["sl_order_id"] = slo.get("id")
                rec["trailing_done"] = True
                changed = True
                print("  ✅ 移動止損到保本:", sym)
            except Exception as e:
                print("  ⚠️ 移動止損失敗:", str(e)[:100])
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
            print("  🧹 清理殘單:", sym, "取消", cancelled, "張")
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
        print("  🔴🔴🔴 偵測到爆倉！", lq.get("symbol"), "（累計:", data["count"], "）")
    if new > 0:
        save_json(liq_file, data)
        print("  ⚠️ 本輪新增", new, "次爆倉。請留意 liquidations.json")


def main_loop():
    print("=" * 50)
    print("auto_trader.py 自動交易（Redis｜輪詢", POLL_INTERVAL, "秒）")
    print("=" * 50)
    print("模式：", "模擬盤(VST假錢)" if trader.USE_SANDBOX else "🔴🔴🔴 真錢 🔴🔴🔴")
    print("設定：最多", MAX_POSITIONS, "倉｜單筆本金 = 淨值 ÷ 4｜槓桿", LEVERAGE, "｜等級", ALLOWED_TIERS)
    print("⚠️ 15倍：爆倉線約 -6.7%，止損強制收緊到最遠 -4%（留爆倉緩衝）")
    print("⚠️ 4 倉同向同時觸損，單日約 -60% 淨值；插針穿損可能更多。未設熔斷。")
    if not _USE_REDIS:
        print("🔴 .env 缺 Upstash Redis 設定，無法讀信號")
        return
    ex = trader.get_exchange()
    print("✅ 連線成功，餘額:", trader.get_balance(ex))
    print("開始輪詢...（Ctrl+C 停止）\n")
    while True:
        try:
            process_closes(ex)
            process_once(ex)
            check_trailing_stop(ex)
            reconcile_stale_orders(ex)
            check_liquidations(ex)
        except KeyboardInterrupt:
            print("\n已停止。")
            break
        except Exception as e:
            print("⚠️ 本輪出錯（繼續下一輪）:", str(e)[:150])
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
