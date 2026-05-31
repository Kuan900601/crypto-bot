"""
trader_order_test.py — BingX 模擬盤下單測試（VST 假錢）
"""
import ccxt


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
        print("🔴 找不到 .env 檔")
    return env


def make_exchange():
    env = load_env()
    ex = ccxt.bingx({
        "apiKey": env.get("BINGX_API_KEY", ""),
        "secret": env.get("BINGX_API_SECRET", ""),
        "options": {"defaultType": "swap"},
    })
    ex.set_sandbox_mode(True)
    return ex


def main():
    print("=" * 45)
    print("BingX 模擬盤下單測試（VST 假錢）")
    print("=" * 45)
    ex = make_exchange()
    symbol = "BTC/USDT:USDT"
    side = "buy"
    leverage = 5
    try:
        bal = ex.fetch_balance()
        usdt = bal.get("total", {}).get("USDT", 0) or bal.get("total", {}).get("VST", 0)
        print("✅ 模擬盤餘額:", usdt)
    except Exception as e:
        print("🔴 讀餘額失敗:", str(e)[:150])
        return
    try:
        ex.load_markets()
        market = ex.market(symbol)
        min_amount = market.get("limits", {}).get("amount", {}).get("min")
        print("✅ 載入市場成功，", symbol, "最小下單量:", min_amount)
    except Exception as e:
        print("🔴 載入市場失敗:", str(e)[:150])
        return
    amount = min_amount if min_amount else 0.0001
    print("\n--- 即將下單（模擬盤）---")
    print("   標的:", symbol, " 方向:", side, " 數量:", amount, " 槓桿:", leverage)
    try:
        ex.set_leverage(leverage, symbol, {"side": "LONG"})
        print("✅ 槓桿設定為", leverage)
    except Exception as e:
        print("⚠️ 槓桿設定略過:", str(e)[:100])
    print("\n正在下單...")
    try:
        order = ex.create_order(symbol, "market", side, amount, None, {"positionSide": "LONG"})
        print("✅✅✅ 下單成功！訂單 ID:", order.get("id"), " 狀態:", order.get("status"))
    except Exception as e:
        print("🔴 下單失敗:", str(e)[:250])
        return
    print("\n查詢持倉...")
    try:
        positions = ex.fetch_positions([symbol])
        for p in positions:
            c = p.get("contracts", 0)
            if c and c != 0:
                print("✅ 持倉:", p.get("symbol"), "數量:", c, "方向:", p.get("side"))
        print("\n✅ 下單測試完成！模擬盤，沒動到真錢。")
    except Exception as e:
        print("⚠️ 查詢持倉失敗:", str(e)[:150])


if __name__ == "__main__":
    main()
