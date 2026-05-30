"""
trader_test.py — BingX 模擬盤連線測試（第 1 步）
這支程式只讀取模擬盤 VST 餘額，完全不下單，零風險。
目的：驗證 API key 正確、確認連的是模擬盤而不是實盤。
"""

import os
import time
import hmac
import hashlib
import json
import urllib.request as _urlreq

# 模擬盤網址（VST 虛擬資金）。實盤是 open-api.bingx.com，我們不碰。
BINGX_BASE_URL = "https://open-api-vst.bingx.com"

API_KEY = os.environ.get("BINGX_API_KEY", "")
API_SECRET = os.environ.get("BINGX_API_SECRET", "")


def _sign(params_str):
    return hmac.new(
        API_SECRET.encode("utf-8"),
        params_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def _signed_get(path, params=None):
    if params is None:
        params = {}
    params["timestamp"] = str(int(time.time() * 1000))
    sorted_keys = sorted(params.keys())
    params_str = "&".join("%s=%s" % (k, params[k]) for k in sorted_keys)
    signature = _sign(params_str)
    url = "%s%s?%s&signature=%s" % (BINGX_BASE_URL, path, params_str, signature)
    req = _urlreq.Request(url, headers={"X-BX-APIKEY": API_KEY})
    with _urlreq.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("=" * 50)
    print("BingX 模擬盤連線測試")
    print("=" * 50)

    if "vst" not in BINGX_BASE_URL:
        print("🔴 危險！BASE_URL 不是模擬盤！中止。")
        return
    print("✅ 確認連線目標：模擬盤（VST）" + BINGX_BASE_URL)

    if not API_KEY or not API_SECRET:
        print("🔴 沒有讀到 BINGX_API_KEY 或 BINGX_API_SECRET")
        return
    print("✅ API key 已讀取（長度 %d）" % len(API_KEY))

    print("\n正在讀取模擬盤 VST 餘額...")
    try:
        result = _signed_get("/openApi/swap/v2/user/balance")
        print("\n--- BingX 回應 ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("code") == 0:
            data = result.get("data", {})
            balance = data.get("balance", {})
            print("\n✅ 連線成功！")
            print("   餘額：" + str(balance.get("balance", "?")) + " VST")
            print("   可用：" + str(balance.get("availableMargin", "?")) + " VST")
        else:
            print("\n⚠️ API 回應錯誤碼：" + str(result.get("code")))
            print("   訊息：" + str(result.get("msg", "")))
    except Exception as e:
        print("\n🔴 連線失敗：" + str(e))


if __name__ == "__main__":
    main()
