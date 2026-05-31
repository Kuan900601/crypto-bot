"""
trader_test.py — BingX 模擬盤（標準 sandbox + 多方法）
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


def try_method(name, fn):
    print("\n>>> 嘗試:", name)
    try:
        bal = fn()
        total = bal.get("total", {}) if isinstance(bal, dict) else {}
        nonzero = {k: v for k, v in total.items() if v and v > 0}
        if nonzero:
            print("   ✅ 成功！餘額:", nonzero)
        else:
            print("   ✅ 連線成功（餘額空或0）")
        return True
    except Exception as e:
        print("   🔴", str(e)[:180])
        return False


def main():
    print("=" * 40)
    print("BingX 模擬盤測試（多方法）")
    print("=" * 40)
    env = load_env()
    api_key = env.get("BINGX_API_KEY", "")
    secret = env.get("BINGX_API_SECRET", "")
    if not api_key or not secret:
        print("🔴 沒讀到 key/secret")
        return
    print("✅ key 長度", len(api_key), " secret 長度", len(secret))
    ex_a = ccxt.bingx({
        "apiKey": api_key, "secret": secret,
        "options": {"defaultType": "swap"},
    })
    try:
        ex_a.set_sandbox_mode(True)
        print("\n[A] set_sandbox_mode(True) 已設定")
        print("    API 網址:", ex_a.urls.get("api"))
    except Exception as e:
        print("[A] set_sandbox_mode 失敗:", str(e)[:120])
    if try_method("A: sandbox + fetch_balance", lambda: ex_a.fetch_balance()):
        return
    if try_method("B: sandbox + type=swap", lambda: ex_a.fetch_balance({"type": "swap"})):
        return
    print("\n--- 都失敗，把上面的『API 網址』和錯誤給 web Claude ---")


if __name__ == "__main__":
    main()
