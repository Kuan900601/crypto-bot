"""
trader.py — Bybit 永續合約交易模組（單向 One-Way 模式）
⚠️ 止損/止盈用 stopLossPrice / takeProfitPrice + reduceOnly（與 BingX 不同）。
⚠️ 請先把 Bybit 帳號設成「單向持倉 One-Way」模式，否則 reduceOnly 平倉會出錯。
"""
import os
try:
    import ccxt
except ImportError as e:
    raise ImportError(
        "缺少 ccxt 依賴，請先執行 `pip install ccxt`"
    ) from e

# 🔴 真錢模式
USE_SANDBOX = False


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


def get_exchange():
    env = load_env()
    ex = ccxt.bybit({
        "apiKey": env.get("BYBIT_API_KEY", ""),
        "secret": env.get("BYBIT_API_SECRET", ""),
        "hostname": "bytick.com",
        "options": {"defaultType": "swap"},
    })
    if USE_SANDBOX:
        ex.set_sandbox_mode(True)
    ex.has["fetchCurrencies"] = False  # /v5/asset/coin/query-info 回 403，load_markets 跳過該呼叫
    ex.load_markets()
    return ex


def get_balance(ex):
    """統一交易帳戶（UTA）USDT 權益。優先讀 unified，讀不到退回預設帳戶。"""
    bal = None
    try:
        bal = ex.fetch_balance({"type": "unified"})
    except Exception:
        bal = None
    if not bal:
        bal = ex.fetch_balance()
    usdt = (bal.get("total", {}) or {}).get("USDT", 0)
    if not usdt:
        # UTA 有時要用 accountType=UNIFIED 才讀得到
        try:
            bal2 = ex.fetch_balance({"accountType": "UNIFIED"})
            usdt = (bal2.get("total", {}) or {}).get("USDT", 0) or usdt
        except Exception:
            pass
    return usdt


def get_free_balance(ex):
    """可用餘額（USDT）。讀取失敗回 None，呼叫端應略過該上限。"""
    try:
        bal = ex.fetch_balance()
        free = bal.get("free", {})
        return float(free.get("USDT", 0))
    except Exception as e:
        print("⚠️ get_free_balance 讀取失敗（將略過可用餘額上限）:", str(e)[:150], flush=True)
        return None


def get_positions(ex, symbol=None):
    symbols = [symbol] if symbol else None
    positions = ex.fetch_positions(symbols)
    return [p for p in positions if p.get("contracts") and p.get("contracts") != 0]


def open_position(ex, symbol, side, amount, leverage, tp_price=None, sl_price=None):
    """單筆開倉 + 可選止損/止盈（單向模式 + reduceOnly）。"""
    result = {"ok": False, "order_id": None, "tp_ok": False, "sl_ok": False, "msg": ""}
    try:
        ex.set_leverage(leverage, symbol)
    except Exception:
        pass
    try:
        order = ex.create_order(symbol, "market", side, amount)
        result["order_id"] = order.get("id")
        result["ok"] = True
    except Exception as e:
        result["msg"] = "開倉失敗: " + str(e)[:200]
        return result
    close_side = "sell" if side == "buy" else "buy"
    if sl_price is not None:
        try:
            ex.create_order(symbol, "market", close_side, amount, None,
                            {"stopLossPrice": sl_price, "reduceOnly": True})
            result["sl_ok"] = True
        except Exception as e:
            result["msg"] += " | 止損掛單失敗: " + str(e)[:150]
    if tp_price is not None:
        try:
            ex.create_order(symbol, "market", close_side, amount, None,
                            {"takeProfitPrice": tp_price, "reduceOnly": True})
            result["tp_ok"] = True
        except Exception as e:
            result["msg"] += " | 止盈掛單失敗: " + str(e)[:150]
    if result["ok"] and sl_price is not None and not result["sl_ok"]:
        result["msg"] = "🔴🔴🔴 警告：開倉成功但止損沒掛上！請立即手動補止損！" + result["msg"]
    return result


def _bybit_symbol_id(ex, symbol):
    """取 Bybit V5 原生 symbol（如 BTCUSDT）。讀不到就用字串還原。"""
    try:
        return ex.market(symbol)["id"]
    except Exception:
        return symbol.replace("/", "").split(":")[0]


def open_position_with_protection(ex, symbol, side, amount, sl_price, tp_prices=None):
    """市價開倉並以 Bybit V5 原生附帶式止損（整倉 stopLoss）保護。
    進場單直接帶 stopLoss → 開倉即附帶，根治「開了卻沒止損的窗口」。
    讀回持倉確認 stopLoss 已生效；沒生效則用 V5 trading-stop 補設；仍失敗才算裸倉。
    回傳 dict：ok, order_id, sl_attached(bool), sl_used, msg, error。"""
    result = {"ok": False, "order_id": None, "sl_attached": False,
              "sl_used": None, "msg": "", "error": ""}
    params = {}
    sl_str = None
    if sl_price:
        try:
            sl_str = ex.price_to_precision(symbol, sl_price)
        except Exception:
            sl_str = str(sl_price)
        params["stopLoss"] = sl_str
    try:
        order = ex.create_order(symbol, "market", side, amount, None, params)
        result["order_id"] = order.get("id")
        result["ok"] = True
    except Exception as e:
        result["error"] = str(e)[:300]
        result["msg"] = "開倉失敗: " + str(e)[:200]
        return result
    if not sl_price:
        return result
    # 讀回持倉確認 stopLoss 是否生效
    try:
        positions = ex.fetch_positions([symbol])
        for p in positions:
            if abs(p.get("contracts") or 0) > 0:
                info = p.get("info", {}) or {}
                sl_val = info.get("stopLoss")
                if sl_val and str(sl_val) not in ("", "0", "0.0"):
                    result["sl_attached"] = True
                    result["sl_used"] = float(sl_val)
                break
    except Exception as e:
        result["msg"] += " | 讀回持倉確認止損失敗: " + str(e)[:120]
    # fallback：附帶沒生效 → 用 V5 trading-stop 設整倉止損
    if not result["sl_attached"]:
        try:
            ex.private_post_v5_position_trading_stop({
                "category": "linear",
                "symbol": _bybit_symbol_id(ex, symbol),
                "stopLoss": sl_str,
                "positionIdx": 0,
            })
            result["sl_attached"] = True
            result["sl_used"] = float(sl_str)
            result["msg"] += " | 止損改用 V5 trading-stop 設定成功"
        except Exception as e:
            result["error"] = (result["error"] + " | " if result["error"] else "") + str(e)[:200]
            result["msg"] += " | 🔴 V5 trading-stop 也失敗: " + str(e)[:150]
    return result


def close_position(ex, symbol):
    positions = get_positions(ex, symbol)
    if not positions:
        return True
    ok = True
    for p in positions:
        contracts = abs(p.get("contracts", 0))
        side = p.get("side")
        close_side = "sell" if side == "long" else "buy"
        try:
            ex.create_order(symbol, "market", close_side, contracts, None,
                            {"reduceOnly": True})
        except Exception:
            ok = False
    return ok


def cancel_symbol_orders(ex, symbol):
    """取消該 symbol 全部掛單（含止盈/止損條件單）。Bybit 條件單可能要額外用 StopOrder filter。"""
    n = 0
    try:
        ex.cancel_all_orders(symbol)
    except Exception:
        pass
    for _params in ({}, {"orderFilter": "StopOrder"}):
        try:
            orders = ex.fetch_open_orders(symbol, None, None, _params)
            for o in orders:
                try:
                    ex.cancel_order(o.get("id"), symbol, _params)
                    n += 1
                except Exception:
                    pass
        except Exception:
            pass
    return n


if __name__ == "__main__":
    print("=" * 45)
    print("trader.py 自我測試（Bybit", "測試網" if USE_SANDBOX else "🔴真錢", "）")
    print("=" * 45)
    ex = get_exchange()
    print("✅ 連線成功，餘額:", get_balance(ex))
    positions = get_positions(ex)
    print("✅ 目前持倉數:", len(positions))
    for p in positions:
        print("   -", p.get("symbol"), p.get("contracts"), p.get("side"))
    print("\n（只讀測試，沒下單）")
