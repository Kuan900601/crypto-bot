"""
trader.py — BingX 模擬盤交易模組（整合版）
"""
import os
import ccxt

USE_SANDBOX = False  # 🔴 真錢模式


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


def get_exchange():
    env = load_env()
    ex = ccxt.bingx({
        "apiKey": env.get("BINGX_API_KEY", ""),
        "secret": env.get("BINGX_API_SECRET", ""),
        "options": {"defaultType": "swap"},
    })
    if USE_SANDBOX:
        ex.set_sandbox_mode(True)
    ex.load_markets()
    return ex


def get_balance(ex):
    bal = ex.fetch_balance()
    total = bal.get("total", {})
    return total.get("USDT", 0) or total.get("VST", 0)


def get_positions(ex, symbol=None):
    symbols = [symbol] if symbol else None
    positions = ex.fetch_positions(symbols)
    return [p for p in positions if p.get("contracts") and p.get("contracts") != 0]


def open_position(ex, symbol, side, amount, leverage, tp_price=None, sl_price=None):
    result = {"ok": False, "order_id": None, "tp_ok": False, "sl_ok": False, "msg": ""}
    position_side = "LONG" if side == "buy" else "SHORT"
    try:
        ex.set_leverage(leverage, symbol, {"side": position_side})
    except Exception:
        pass
    try:
        order = ex.create_order(symbol, "market", side, amount, None,
                                {"positionSide": position_side})
        result["order_id"] = order.get("id")
        result["ok"] = True
    except Exception as e:
        result["msg"] = "開倉失敗: " + str(e)[:200]
        return result
    close_side = "sell" if side == "buy" else "buy"
    if sl_price is not None:
        try:
            ex.create_order(symbol, "STOP_MARKET", close_side, amount, None,
                            {"positionSide": position_side, "stopPrice": sl_price})
            result["sl_ok"] = True
        except Exception as e:
            result["msg"] += " | 止損掛單失敗: " + str(e)[:150]
    if tp_price is not None:
        try:
            ex.create_order(symbol, "TAKE_PROFIT_MARKET", close_side, amount, None,
                            {"positionSide": position_side, "stopPrice": tp_price})
            result["tp_ok"] = True
        except Exception as e:
            result["msg"] += " | 止盈掛單失敗: " + str(e)[:150]
    if result["ok"] and sl_price is not None and not result["sl_ok"]:
        result["msg"] = "🔴🔴🔴 警告：開倉成功但止損沒掛上！倉位無保護，請立即手動補止損！" + result["msg"]
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
        position_side = "LONG" if side == "long" else "SHORT"
        try:
            ex.create_order(symbol, "market", close_side, contracts, None,
                            {"positionSide": position_side})
        except Exception:
            ok = False
    return ok


def cancel_symbol_orders(ex, symbol):
    """取消該 symbol 全部掛單（含止盈/止損條件單）。盡力而為，回傳逐筆取消成功數。"""
    n = 0
    try:
        ex.cancel_all_orders(symbol)
    except Exception:
        pass
    try:
        orders = ex.fetch_open_orders(symbol)
        for o in orders:
            try:
                ex.cancel_order(o.get("id"), symbol)
                n += 1
            except Exception:
                pass
    except Exception:
        pass
    return n


if __name__ == "__main__":
    print("=" * 45)
    print("trader.py 自我測試（模擬盤）")
    print("=" * 45)
    ex = get_exchange()
    print("✅ 連線成功，餘額:", get_balance(ex))
    positions = get_positions(ex)
    print("✅ 目前持倉數:", len(positions))
    for p in positions:
        print("   -", p.get("symbol"), p.get("contracts"), p.get("side"))
    print("\n（只讀測試，沒下單）")
