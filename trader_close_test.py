"""
trader_close_test.py — BingX 模擬盤平倉測試（VST 假錢）
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
    print("BingX 模擬盤平倉測試（VST 假錢）")
    print("=" * 45)
    ex = make_exchange()
    ex.load_markets()
    print("\n查詢目前持倉...")
    try:
        positions = ex.fetch_positions()
        open_positions = [p for p in positions if p.get("contracts") and p.get("contracts") != 0]
    except Exception as e:
        print("🔴 查持倉失敗:", str(e)[:200])
        return
    if not open_positions:
        print("✅ 目前沒有開著的持倉")
        return
    print("找到", len(open_positions), "個持倉：")
    for p in open_positions:
        print("   -", p.get("symbol"), "數量:", p.get("contracts"), "方向:", p.get("side"))
    for p in open_positions:
        symbol = p.get("symbol")
        contracts = abs(p.get("contracts", 0))
        side = p.get("side")
        close_side = "sell" if side == "long" else "buy"
        position_side = "LONG" if side == "long" else "SHORT"
        print("\n正在平倉:", symbol, "（", side, "→ 下", close_side, "單）")
        try:
            order = ex.create_order(
                symbol, "market", close_side, contracts, None,
                {"positionSide": position_side}
            )
            print("   ✅ 平倉單送出！訂單 ID:", order.get("id"))
        except Exception as e:
            print("   🔴 平倉失敗:", str(e)[:200])
    print("\n再次查詢持倉確認...")
    try:
        positions2 = ex.fetch_positions()
        still_open = [p for p in positions2 if p.get("contracts") and p.get("contracts") != 0]
        if not still_open:
            print("✅✅✅ 平倉成功！目前沒有持倉了。")
        else:
            print("⚠️ 還有持倉（可能需幾秒同步，或再跑一次）：")
            for p in still_open:
                print("   -", p.get("symbol"), "數量:", p.get("contracts"))
    except Exception as e:
        print("⚠️ 確認查詢失敗:", str(e)[:150])


if __name__ == "__main__":
    main()
