"""
trader_tpsl_test.py — BingX 模擬盤：開倉 → 分別掛 TP/SL 條件單（兩步）
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
    print("=" * 50)
    print("BingX 模擬盤：開倉 + 分別掛 TP/SL")
    print("=" * 50)
    ex = make_exchange()
    ex.load_markets()
    symbol = "BTC/USDT:USDT"
    leverage = 5
    SL_PCT = 0.02
    TP_PCT = 0.03

    # 取市價
    try:
        ticker = ex.fetch_ticker(symbol)
        price = ticker["last"]
        print("✅ 目前市價:", price)
    except Exception as e:
        print("🔴 取得市價失敗:", str(e)[:150])
        return

    sl_price = round(price * (1 - SL_PCT), 1)
    tp_price = round(price * (1 + TP_PCT), 1)
    print("   止損 SL:", sl_price, "（-2%）")
    print("   止盈 TP:", tp_price, "（+3%）")

    market = ex.market(symbol)
    amount = market.get("limits", {}).get("amount", {}).get("min") or 0.0001

    try:
        ex.set_leverage(leverage, symbol, {"side": "LONG"})
    except Exception as e:
        print("⚠️ 槓桿略過:", str(e)[:80])

    # ── 第一步：市價開倉 ──
    print("\n【第一步】市價開倉...")
    try:
        order = ex.create_order(
            symbol, "market", "buy", amount, None,
            {"positionSide": "LONG"}
        )
        print("✅ 開倉成功！訂單 ID:", order.get("id"), " 狀態:", order.get("status"))
    except Exception as e:
        print("🔴 開倉失敗:", str(e)[:250])
        return

    # ── 第二步：掛 SL 條件單 ──
    print("\n【第二步-A】掛止損單（STOP_MARKET @ " + str(sl_price) + "）...")
    sl_ok = False
    try:
        sl_order = ex.create_order(
            symbol, "STOP_MARKET", "sell", amount, None,
            {"positionSide": "LONG", "stopPrice": sl_price}
        )
        print("✅ 止損單掛上！訂單 ID:", sl_order.get("id"))
        sl_ok = True
    except Exception as e:
        print("🔴 止損單失敗:", str(e)[:250])

    # ── 第二步：掛 TP 條件單 ──
    print("\n【第二步-B】掛止盈單（TAKE_PROFIT_MARKET @ " + str(tp_price) + "）...")
    tp_ok = False
    try:
        tp_order = ex.create_order(
            symbol, "TAKE_PROFIT_MARKET", "sell", amount, None,
            {"positionSide": "LONG", "stopPrice": tp_price}
        )
        print("✅ 止盈單掛上！訂單 ID:", tp_order.get("id"))
        tp_ok = True
    except Exception as e:
        print("🔴 止盈單失敗:", str(e)[:250])

    # ── 警告：有倉位但沒保護 ──
    if not sl_ok or not tp_ok:
        print("\n" + "!" * 50)
        print("⚠️  警告！倉位已開但保護不完整：")
        if not sl_ok:
            print("   🔴 止損單未掛上 → 虧損無上限！")
        if not tp_ok:
            print("   🔴 止盈單未掛上 → 無法自動獲利了結")
        print("   → 請立即去 BingX App 模擬盤手動補掛止損！")
        print("!" * 50)

    # ── 查詢確認 ──
    print("\n【確認】查詢現有條件單...")
    try:
        open_orders = ex.fetch_open_orders(symbol)
        if not open_orders:
            print("   （沒查到掛單，可能 BingX 把 TP/SL 附在持倉上，請去 App 確認）")
        else:
            for o in open_orders:
                raw_type = str(o.get("info", {}).get("type", o.get("type", ""))).upper()
                trigger = o.get("info", {}).get("stopPrice") or o.get("triggerPrice", "?")
                print("   掛單類型:", raw_type, " 觸發價:", trigger, " ID:", o.get("id"))
    except Exception as e:
        print("   ⚠️ 查詢失敗:", str(e)[:150])

    # ── 總結 ──
    print("\n--- 結果摘要 ---")
    print("   開倉：✅")
    print("   止損 SL：", "✅ 已掛" if sl_ok else "🔴 失敗")
    print("   止盈 TP：", "✅ 已掛" if tp_ok else "🔴 失敗")
    if sl_ok and tp_ok:
        print("\n✅✅✅ 完美！開倉 + TP + SL 全部成功。")


if __name__ == "__main__":
    main()
