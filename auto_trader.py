"""
auto_trader.py — 自動交易橋接器（模擬盤｜Redis 隊列版｜15秒輪詢）
"""
import json
import os
import time
import math
import urllib.request

import trader

MAX_POSITIONS = 5
BASE_AMOUNT_USDT = 1000
TIER_MULTIPLIER = {"S": 2.0, "A": 1.5, "B": 1.0, "C": 0.5}
ALLOWED_TIERS = ["S", "A", "B", "C"]  # C 級也下單
LEVERAGE = 15  # ⚠️ 15倍：爆倉線約 -6.7%，止損必須離爆倉線夠遠（見 MAX_SL_PCT）
MAX_SL_PCT = 0.04  # 止損最遠 -4%（離 -6.7% 爆倉線留 2.7% 緩衝）
TP_SPLIT = {1: 0.15, 2: 0.35, 3: 0.35, 4: 0.15}
POLL_INTERVAL = 15

PROCESSED_FILE = "processed_signals.json"
TRADES_FILE = "auto_trades.json"
REDIS_QUEUE_KEY = "signal_queue"


def load_env():
    # 先讀 .env 檔案（本地用），再用環境變數覆蓋（Railway 用）
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


def read_redis_queue():
    """從 Redis 讀整個 signal_queue。用 POST + JSON 數組格式（跟寫入端一致，最可靠）"""
    if not _USE_REDIS:
        print("🔴 沒設定 Upstash Redis（.env 缺 URL/TOKEN）")
        return []
    try:
        body = json.dumps(["LRANGE", REDIS_QUEUE_KEY, "0", "-1"]).encode("utf-8")
        req = urllib.request.Request(_REDIS_URL, data=body, headers={
            "Authorization": "Bearer " + _REDIS_TOKEN,
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        items = result.get("result", []) or []
        signals = []
        for it in items:
            try:
                signals.append(json.loads(it))
            except Exception:
                continue
        return signals
    except Exception as e:
        print("🔴 讀 Redis 隊列失敗:", str(e)[:150])
        return []


def calc_amount(ex, symbol, tier, price):
    usdt = BASE_AMOUNT_USDT * TIER_MULTIPLIER.get(tier, 1.0)
    raw_amount = (usdt * LEVERAGE) / price
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


def to_ccxt_symbol(sym):
    if ":" in sym:
        return sym
    if sym.endswith("/USDT"):
        return sym + ":USDT"
    return sym


def open_batch_tp_position(ex, signal):
    symbol = to_ccxt_symbol(signal["symbol"])
    direction = signal.get("direction", "").upper()
    side = "buy" if direction in ("LONG", "BUY", "做多") else "sell"
    tier = signal.get("tier", "B")
    ticker = ex.fetch_ticker(symbol)
    price = ticker["last"]
    total_amount = calc_amount(ex, symbol, tier, price)
    position_side = "LONG" if side == "buy" else "SHORT"
    close_side = "sell" if side == "buy" else "buy"
    record = {
        "symbol": symbol, "side": side, "tier": tier,
        "entry_price": price, "total_amount": total_amount,
        "opened_at": time.time(), "tp_orders": [], "sl_ok": False,
        "ok": False, "msg": "",
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
                record["msg"] += " | 止損從 %.4f 收緊到 %.4f（爆倉保護）" % (sl, safe_sl)
                sl = safe_sl
        else:
            safe_sl = price * (1 + MAX_SL_PCT)
            if sl > safe_sl:
                record["msg"] += " | 止損從 %.4f 收緊到 %.4f（爆倉保護）" % (sl, safe_sl)
                sl = safe_sl
        try:
            ex.create_order(symbol, "STOP_MARKET", close_side, total_amount, None,
                            {"positionSide": position_side, "stopPrice": sl})
            record["sl_ok"] = True
            record["sl_used"] = sl
        except Exception as e:
            record["msg"] += " | 止損失敗: " + str(e)[:120]
    for level in (1, 2, 3, 4):
        tp_price = signal.get("tp%d" % level)
        if not tp_price:
            continue
        tp_amount = total_amount * TP_SPLIT[level]
        try:
            ex.create_order(symbol, "TAKE_PROFIT_MARKET", close_side, tp_amount, None,
                            {"positionSide": position_side, "stopPrice": tp_price})
            record["tp_orders"].append({"level": level, "price": tp_price, "amount": tp_amount, "ok": True})
        except Exception as e:
            record["tp_orders"].append({"level": level, "price": tp_price, "ok": False, "err": str(e)[:80]})
    if record["ok"] and sl and not record["sl_ok"]:
        record["msg"] = "🔴🔴🔴 開倉成功但止損沒掛上！" + record["msg"]
    return record


def process_once(ex):
    queue = read_redis_queue()
    processed = load_json(PROCESSED_FILE, [])
    trades = load_json(TRADES_FILE, [])
    if not queue:
        return
    current_positions = trader.get_positions(ex)
    pos_count = len(current_positions)
    new_count = 0
    for signal in queue:
        sig_id = signal.get("id") or (signal.get("symbol", "") + str(signal.get("created", "")))
        if sig_id in processed:
            continue
        if signal.get("tier", "B") not in ALLOWED_TIERS:
            processed.append(sig_id)
            continue
        if pos_count >= MAX_POSITIONS:
            print("  已達最大持倉數", MAX_POSITIONS, "，跳過剩餘")
            break
        print("  處理新信號:", sig_id)
        record = open_batch_tp_position(ex, signal)
        record["sig_id"] = sig_id
        trades.append(record)
        processed.append(sig_id)
        new_count += 1
        if record["ok"]:
            pos_count += 1
            print("    ✅ 下單成功:", record["symbol"], "TP單:", len(record["tp_orders"]), "止損:", record["sl_ok"])
            if record["msg"]:
                print("    ⚠️", record["msg"])
        else:
            print("    🔴 下單失敗:", record["msg"])
    if new_count > 0:
        save_json(PROCESSED_FILE, processed)
        save_json(TRADES_FILE, trades)
        print("  本輪處理", new_count, "個新信號。總紀錄:", len(trades))


def check_liquidations(ex):
    """爆倉計數器：讀 BingX 爆倉紀錄，記錄發生過幾次爆倉"""
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
        print("  🔴🔴🔴 偵測到爆倉！", lq.get("symbol"), "（累計爆倉次數:", data["count"], "）")
    if new > 0:
        save_json(liq_file, data)
        print("  ⚠️ 本輪新增", new, "次爆倉。請留意 liquidations.json")


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
        if current_amount < rec["total_amount"] * 0.95:
            entry = rec["entry_price"]
            new_sl = entry
            side = rec["side"]
            position_side = "LONG" if side == "buy" else "SHORT"
            close_side = "sell" if side == "buy" else "buy"
            try:
                ex.create_order(sym, "STOP_MARKET", close_side, current_amount, None,
                                {"positionSide": position_side, "stopPrice": new_sl})
                rec["trailing_done"] = True
                changed = True
                print("  ✅ 移動止損到保本:", sym)
            except Exception as e:
                print("  ⚠️ 移動止損失敗:", str(e)[:100])
    if changed:
        save_json(TRADES_FILE, trades)


def main_loop():
    print("=" * 50)
    print("auto_trader.py 自動交易（模擬盤｜Redis｜輪詢", POLL_INTERVAL, "秒）")
    print("=" * 50)
    print("設定：最多", MAX_POSITIONS, "倉，基礎", BASE_AMOUNT_USDT, "VST，槓桿", LEVERAGE, "，等級", ALLOWED_TIERS)
    print("⚠️ 15倍槓桿：爆倉線約 -6.7%，止損已強制收緊到最遠 -4%（留爆倉緩衝）")
    print("⚠️ 但插針仍可能瞬間穿過止損與爆倉線。爆倉次數記錄在 liquidations.json")
    if not _USE_REDIS:
        print("🔴 .env 缺 Upstash Redis 設定，無法讀信號")
        return
    ex = trader.get_exchange()
    print("✅ 連線成功，餘額:", trader.get_balance(ex), "VST")
    print("開始輪詢 Redis 隊列...（Ctrl+C 停止）\n")
    while True:
        try:
            process_once(ex)
            check_trailing_stop(ex)
            check_liquidations(ex)  # 爆倉計數器
        except KeyboardInterrupt:
            print("\n已停止。")
            break
        except Exception as e:
            print("⚠️ 本輪出錯（繼續下一輪）:", str(e)[:150])
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
