"""
trader_test.py — BingX 模擬盤連線測試（官方範例寫法）
只讀餘額，不下單，零風險。
"""

import os
import time
import hmac
import json
from hashlib import sha256
import requests

APIURL = "https://open-api-vst.bingx.com"
APIKEY = os.environ.get("BINGX_API_KEY", "")
SECRETKEY = os.environ.get("BINGX_API_SECRET", "")


def get_sign(api_secret, payload):
    return hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), digestmod=sha256).hexdigest()


def parseParam(paramsMap):
    sortedKeys = sorted(paramsMap)
    paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
    if paramsStr != "":
        return paramsStr + "&timestamp=" + str(int(time.time() * 1000))
    else:
        return paramsStr + "timestamp=" + str(int(time.time() * 1000))


def send_request(method, path, urlpa, payload):
    url = "%s%s?%s&signature=%s" % (APIURL, path, urlpa, get_sign(SECRETKEY, urlpa))
    headers = {"X-BX-APIKEY": APIKEY}
    response = requests.request(method, url, headers=headers, data=payload)
    return response.text


def main():
    print("=" * 40)
    print("BingX 模擬盤測試（官方範例寫法）")
    print("=" * 40)
    if not APIKEY or not SECRETKEY:
        print("🔴 沒讀到 key/secret")
        return
    if APIKEY == SECRETKEY:
        print("🔴 KEY 和 SECRET 一樣，貼錯了")
        return
    print("✅ key/secret 是不同兩串")
    print("   KEY 長度:", len(APIKEY), " SECRET 長度:", len(SECRETKEY))
    payload = {}
    path = "/openApi/swap/v2/user/balance"
    method = "GET"
    paramsMap = {}
    paramsStr = parseParam(paramsMap)
    print("   簽名字串:", repr(paramsStr))
    try:
        result_text = send_request(method, path, paramsStr, payload)
        print("\n--- 回應 ---")
        print(result_text)
        result = json.loads(result_text)
        if result.get("code") == 0:
            bal = result.get("data", {}).get("balance", {})
            print("\n✅✅✅ 成功！餘額:", bal.get("balance", "?"), "VST")
        elif result.get("code") == 100001:
            print("\n🔴 還是簽名錯誤，可能 key 剛申請還沒生效，等幾分鐘再試")
        else:
            print("\n⚠️ 錯誤碼:", result.get("code"), result.get("msg", ""))
    except Exception as e:
        print("🔴 失敗:", str(e))


if __name__ == "__main__":
    main()
