# webapp.py — 黑潮船長 Black Tide Signals 儀表板 v2（唯讀 PWA，黑金版）
# 原則：不碰策略；缺字段 .get 容錯；沒有的數據整欄不顯示；外部數據 server 端快取、失敗沿用舊值
import json
import os
import time
import threading
import logging
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("webapp")
_get_state = None
_TOKEN = os.environ.get("DASH_TOKEN", "")
_UA = {"User-Agent": "Mozilla/5.0 (BlackTideDash/2.0)"}
_ICON_PATHS = ["dashboard_icon.png", "static/dashboard_icon.png"]

# ---------- 外部數據（快取） ----------
_CACHE = {}
_LOCKS = {}

def _cached(key, ttl, fn):
    now = time.time()
    ent = _CACHE.get(key)
    if ent and now - ent[0] < ttl and ent[1] is not None:
        return ent[1]
    lock = _LOCKS.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        return ent[1] if ent else None
    try:
        try:
            val = fn()
            if val is not None:
                _CACHE[key] = (now, val)
        except Exception as e:
            logger.warning("webapp fetch " + key + " 失敗: " + str(e))
    finally:
        lock.release()
    ent = _CACHE.get(key)
    return ent[1] if ent else None

def _http_json(url, timeout=8):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _http_text(url, timeout=10):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def _fetch_fng():
    d = _http_json("https://api.alternative.me/fng/?limit=1")
    item = (d.get("data") or [{}])[0]
    zh = {"Extreme Fear": "極度恐懼", "Fear": "恐懼", "Neutral": "中性",
          "Greed": "貪婪", "Extreme Greed": "極度貪婪"}
    return {"value": int(item.get("value")), "label": zh.get(item.get("value_classification", ""), item.get("value_classification", ""))}

_COINS = [("bitcoin", "BTC"), ("ethereum", "ETH"), ("solana", "SOL"), ("binancecoin", "BNB"), ("ripple", "XRP")]

def _fetch_coins():
    ids = ",".join(c[0] for c in _COINS)
    d = _http_json("https://api.coingecko.com/api/v3/simple/price?ids=" + ids + "&vs_currencies=usd&include_24hr_change=true")
    out = []
    for cid, sym in _COINS:
        row = d.get(cid) or {}
        p = row.get("usd")
        ch = row.get("usd_24h_change")
        if p is None:
            continue
        out.append({"sym": sym, "price": p, "chg": round(ch, 2) if ch is not None else None})
    return out or None

def _rss_time(pd):
    try:
        dt = parsedate_to_datetime(pd)
        h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if h < 1:
            return str(max(1, int(h * 60))) + " 分鐘前"
        if h < 48:
            return str(int(h)) + " 小時前"
        return str(int(h / 24)) + " 天前"
    except Exception:
        return ""

_FEEDS = [("動區 BlockTempo", "https://www.blocktempo.com/feed/"),
          ("Cointelegraph", "https://cointelegraph.com/rss")]

def _fetch_news():
    for name, url in _FEEDS:
        try:
            root = ET.fromstring(_http_text(url))
            items = []
            for it in root.iter("item"):
                t = (it.findtext("title") or "").strip()
                if not t:
                    continue
                items.append({"title": t[:60], "time": _rss_time((it.findtext("pubDate") or "").strip()), "src": name})
                if len(items) >= 8:
                    break
            if items:
                return items
        except Exception as e:
            logger.warning("webapp RSS " + name + " 失敗: " + str(e))
    return None

def _market():
    return {
        "fng": _cached("fng", 1800, _fetch_fng),
        "coins": _cached("coins", 120, _fetch_coins),
        "news": _cached("news", 600, _fetch_news),
        "ts": datetime.now(timezone.utc).isoformat(),
    }

def _icon_bytes():
    def _read():
        for p in _ICON_PATHS:
            try:
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return f.read()
            except Exception:
                pass
        return None
    return _cached("icon", 3600, _read)

# ---------- bot 狀態快照 ----------
# 對齊實際 sig key（已比對 Upstash 實際資料）：rr→rr_at_entry，移除不存在的 win_rate/position/confidence，
# 補上有撈到的 timeframe/order_type/status/funding_at_entry/ls_ratio_at_entry
_SIG_KEYS = ["direction", "entry", "sl", "tp1", "tp2", "tp3", "tp4", "tp_hit", "score",
             "tier", "created", "entry_grade", "rr_at_entry", "timeframe", "order_type",
             "status", "regime_at_entry", "adx_at_entry", "consensus_at_entry",
             "news_vote_at_entry", "funding_at_entry", "ls_ratio_at_entry"]
_RES_KEYS = ["symbol", "direction", "final_pct", "result", "tier", "tp_hit_count",
             "score", "entry_grade", "consensus_at_entry"]

def _stats(results_raw):
    out = {"n": 0, "win_rate": None, "exp": None, "avg_win": None, "avg_loss": None}
    try:
        vals = []
        for r in results_raw:
            if not isinstance(r, dict):
                continue
            try:
                vals.append(float(r.get("final_pct")))
            except Exception:
                continue
        if not vals:
            return out
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v <= 0]
        out["n"] = len(vals)
        out["win_rate"] = round(len(wins) / len(vals) * 100, 1)
        out["exp"] = round(sum(vals) / len(vals), 3)
        if wins:
            out["avg_win"] = round(sum(wins) / len(wins), 2)
        if losses:
            out["avg_loss"] = round(sum(losses) / len(losses), 2)
    except Exception as e:
        logger.warning("webapp stats 失敗: " + str(e))
    return out

def _snapshot():
    st = _get_state() if _get_state else {}
    active_raw = st.get("active") or {}
    results_raw = st.get("results") or []
    scan = st.get("scan") or {}
    active = []
    try:
        for sym, sig in list(active_raw.items()):
            if not isinstance(sig, dict):
                continue
            row = {"symbol": sym}
            for k in _SIG_KEYS:
                v = sig.get(k)
                if v is not None:
                    row[k] = v
            active.append(row)
    except Exception as e:
        logger.warning("webapp active 快照失敗: " + str(e))
    results, cum = [], []
    try:
        total = 0.0
        for r in results_raw:
            if not isinstance(r, dict):
                continue
            try:
                total += float(r.get("final_pct"))
                cum.append(round(total, 2))
            except Exception:
                continue
        for r in list(results_raw)[-60:][::-1]:
            if not isinstance(r, dict):
                continue
            row = {}
            for k in _RES_KEYS:
                v = r.get(k)
                if v is not None:
                    row[k] = v
            row["ts"] = r.get("ts") or r.get("closed_at") or r.get("time") or ""
            results.append(row)
    except Exception as e:
        logger.warning("webapp results 快照失敗: " + str(e))
    return {"ts": datetime.now(timezone.utc).isoformat(), "active": active, "results": results,
            "stats": _stats(results_raw), "cum": cum,
            "last_push": scan.get("last_push"), "use_redis": st.get("use_redis")}

# ---------- HTTP ----------
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, code, data, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            u = urlparse(self.path)
            if u.path in ("/icon.png", "/logo.png"):
                ic = _icon_bytes()
                if ic:
                    self._send_bytes(200, ic, "image/png")
                else:
                    self._send(404, "no icon", "text/plain")
                return
            q = parse_qs(u.query)
            key = (q.get("key") or [""])[0]
            if (not _TOKEN) or key != _TOKEN:
                self._send(401, "未授權：網址需帶 ?key=DASH_TOKEN", "text/plain")
                return
            if u.path in ("/", "/app"):
                self._send(200, _HTML.replace("__KEY__", key), "text/html")
            elif u.path == "/api/state":
                self._send(200, json.dumps(_snapshot(), ensure_ascii=False, default=str), "application/json")
            elif u.path == "/api/market":
                self._send(200, json.dumps(_market(), ensure_ascii=False, default=str), "application/json")
            else:
                self._send(404, "not found", "text/plain")
        except Exception as e:
            try:
                self._send(500, "error: " + str(e), "text/plain")
            except Exception:
                pass

def start_dashboard(state_getter):
    global _get_state
    _get_state = state_getter
    if not _TOKEN:
        logger.warning("DASH_TOKEN 未設定，儀表板不啟動（安全預設）")
        return
    port = int(os.environ.get("PORT", "8080"))

    def _run():
        try:
            ThreadingHTTPServer(("0.0.0.0", port), _Handler).serve_forever()
        except Exception as e:
            logger.error("dashboard server 結束: " + str(e))

    t = threading.Thread(target=_run, daemon=True, name="dashboard")
    t.start()
    logger.info("儀表板已啟動 port=" + str(port))


_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#05060A">
<title>黑潮船長 · Black Tide</title>
<style>
:root{--bg:#05060A;--bg2:#0B0E16;--card:rgba(18,20,30,.82);--line:rgba(212,175,90,.14);
--gold:#E9C45A;--gold2:#F7E29B;--cyan:#22D3EE;--green:#34D399;--rose:#FB7185;
--amber:#F5A623;--tx:#ECE7DA;--mut:#9A9482;--dim:#5E5A4E}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:
radial-gradient(900px 420px at 50% -8%,rgba(233,196,90,.10) 0%,transparent 60%),
radial-gradient(700px 500px at 90% 12%,rgba(34,211,238,.05) 0%,transparent 55%),
var(--bg);
color:var(--tx);font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif;
min-height:100vh;padding-bottom:48px}
.wrap{max-width:440px;margin:0 auto;padding:0 15px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.gold{color:var(--gold)}
header{position:sticky;top:0;z-index:30;
background:linear-gradient(180deg,rgba(5,6,10,.94),rgba(5,6,10,.70));
backdrop-filter:blur(16px);padding:14px 0 8px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:11px}
.mark{width:38px;height:38px;border-radius:11px;overflow:hidden;display:flex;align-items:center;
justify-content:center;font-size:19px;
background:linear-gradient(135deg,#1A1407,rgba(233,196,90,.28));
border:1px solid rgba(233,196,90,.42);box-shadow:0 0 16px rgba(233,196,90,.14)}
.mark img{width:100%;height:100%;object-fit:cover;display:block}
.h1{font-size:16px;font-weight:800;letter-spacing:1px;
background:linear-gradient(90deg,var(--gold2),var(--gold));-webkit-background-clip:text;
-webkit-text-fill-color:transparent;background-clip:text}
.h2{font-size:8px;color:var(--dim);letter-spacing:3px;margin-top:1px}
.upd{font-size:10px;font-weight:600;padding:3px 9px;border-radius:999px;
border:1px solid rgba(233,196,90,.28);color:var(--mut)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.chip{font-size:10px;font-weight:600;padding:2px 9px;border-radius:999px;
border:1px solid;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.rule{height:1px;margin-top:9px;
background:linear-gradient(90deg,transparent,rgba(233,196,90,.55),transparent)}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.tabs{display:flex;gap:7px;margin:12px 0}
.tab{flex:1;text-align:center;padding:9px 0;border-radius:13px;font-size:13px;
font-weight:700;color:var(--mut);background:var(--card);border:1px solid var(--line);cursor:pointer;
transition:.15s}
.tab.on{color:var(--gold2);border-color:rgba(233,196,90,.5);
box-shadow:0 0 16px rgba(233,196,90,.12);background:rgba(233,196,90,.06)}
.card{background:var(--card);border:1px solid var(--line);border-radius:17px;
padding:14px;margin-bottom:11px;backdrop-filter:blur(10px);animation:fadeUp .3s}
.row{display:flex;align-items:center;justify-content:space-between}
.sym{font-size:17px;font-weight:800}
.small{font-size:10px;color:var(--mut)}
.tiny{font-size:9px;color:var(--dim)}
.sec{font-size:11px;letter-spacing:2px;color:var(--gold);font-weight:700;margin:18px 2px 9px;
display:flex;align-items:center;gap:8px}
.sec:before{content:"";width:14px;height:1px;background:var(--gold);opacity:.6}
.badge{font-size:9px;font-weight:700;padding:1px 7px;border-radius:6px;border:1px solid var(--line)}
.kgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:11px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:13px;
padding:11px 8px;text-align:center}
.kpi .l{font-size:9px;color:var(--dim);margin-bottom:3px}
.kpi .v{font-size:15px;font-weight:800}
.tpgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}
.tp{text-align:center;padding:6px 2px;border-radius:9px;background:rgba(154,148,130,.06);
border:1px solid var(--line)}
.tp.hit{border-color:rgba(233,196,90,.5);background:rgba(233,196,90,.12)}
.tp .l{font-size:9px;color:var(--dim)}
.tp .v{font-size:11px;font-weight:700;margin-top:2px}
.meta{display:flex;flex-wrap:wrap;gap:5px;margin-top:9px}
.note{font-size:10px;color:var(--mut);margin:4px 2px 10px;line-height:1.7}
.banner{border-left:3px solid var(--gold)}
.coin{display:flex;align-items:center;justify-content:space-between;padding:8px 2px;
border-bottom:1px solid rgba(154,148,130,.08)}
.coin:last-child{border-bottom:0}
.news a,.news{text-decoration:none;color:var(--tx)}
.nitem{padding:9px 2px;border-bottom:1px solid rgba(154,148,130,.08)}
.nitem:last-child{border-bottom:0}
.gauge{position:relative;height:9px;border-radius:99px;margin:10px 0 6px;overflow:hidden;
background:linear-gradient(90deg,#FB7185,#F5A623,#E9C45A,#34D399)}
.gpin{position:absolute;top:-3px;width:3px;height:15px;border-radius:2px;background:#fff;
box-shadow:0 0 6px rgba(255,255,255,.7)}
svg{display:block}
.err{font-size:11px;color:var(--rose);text-align:center;margin:8px 0}
.empty{text-align:center;color:var(--dim);font-size:11px;padding:6px 0}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand">
    <div class="logo">
      <div class="mark"><img src="/icon.png" onerror="this.parentNode.textContent='&#9875;'"></div>
      <div><div class="h1">黑潮船長</div><div class="h2">BLACK TIDE · SIGNALS</div></div>
    </div>
    <span class="upd" id="upd">--</span>
  </div>
  <div class="chips" id="chips"></div>
  <div class="rule"></div>
  <div class="tabs">
    <div class="tab on" id="tab_sig" onclick="setTab('sig')">&#128225; 信號</div>
    <div class="tab" id="tab_sta" onclick="setTab('sta')">&#128202; 統計</div>
    <div class="tab" id="tab_mkt" onclick="setTab('mkt')">&#127758; 市場</div>
  </div>
</header>
<div id="err"></div>
<div id="v_sig"></div>
<div id="v_sta" style="display:none"></div>
<div id="v_mkt" style="display:none"></div>
</div>
<script>
var KEY = "__KEY__";
var TIER = {S:"&#128142; S", A:"&#129351; A", B:"&#129352; B", C:"&#129353; C", D:"D"};
var GRADE = {S:"高品質", A:"高品質", B:"一般", C:"一般", D:"低品質"};

function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function has(v){return v!=null&&v!=="";}
function num(v,d){if(!has(v))return null;var n=Number(v);if(isNaN(n))return esc(v);return n.toFixed(d==null?2:d);}
function pct(v){var n=Number(v);if(isNaN(n))return "--";return (n>0?"+":"")+n.toFixed(2)+"%";}

function setTab(t){
  ["sig","sta","mkt"].forEach(function(k){
    $("tab_"+k).className="tab"+(k===t?" on":"");
    $("v_"+k).style.display=(k===t?"":"none");
  });
  if(t==="mkt")loadMarket();
}

function dirChip(d){
  if(d==="LONG"||d==="多"||d==="long")return '<span style="color:var(--green);font-weight:700">&#9650; 多</span>';
  if(d==="SHORT"||d==="空"||d==="short")return '<span style="color:var(--rose);font-weight:700">&#9660; 空</span>';
  return '<span style="color:var(--mut)">'+esc(d||"--")+'</span>';
}
function pill(label,val){
  if(!has(val))return "";
  return '<span class="badge">'+label+' '+esc(val)+'</span>';
}
function tpCell(label,val,hit){
  var v=num(val,4);
  return '<div class="tp'+(hit?" hit":"")+'"><div class="l">'+label+'</div><div class="v mono">'+(v==null?"--":v)+'</div></div>';
}

function sigCard(s){
  var hit=s.tp_hit||[];
  function isHit(n){return hit.indexOf(n)>=0||hit.indexOf(String(n))>=0;}
  var tier=TIER[s.tier]||esc(s.tier||"");
  var h='<div class="card">';
  h+='<div class="row"><div class="sym">'+esc(s.symbol||"--")+'</div>'+(tier?'<div class="small gold">'+tier+'</div>':'')+'</div>';
  h+='<div class="row" style="margin-top:6px"><div>'+dirChip(s.direction)+'</div><div class="small">';
  var bits=[];
  if(has(s.score))bits.push("分數 "+num(s.score,0));
  if(has(s.rr_at_entry))bits.push("RR "+num(s.rr_at_entry,2));
  if(has(s.entry_grade))bits.push(GRADE[s.entry_grade]||esc(s.entry_grade));
  h+=bits.join("｜")+'</div></div>';
  h+='<div class="row" style="margin-top:8px"><div class="small">進場 <span class="mono gold">'+(num(s.entry,4)||"--")+'</span></div>';
  h+='<div class="small">止損 <span class="mono" style="color:var(--rose)">'+(num(s.sl,4)||"--")+'</span></div></div>';
  h+='<div class="tpgrid">'+tpCell("TP1",s.tp1,isHit(1))+tpCell("TP2",s.tp2,isHit(2))+tpCell("TP3",s.tp3,isHit(3))+tpCell("TP4",s.tp4,isHit(4))+'</div>';
  var meta=pill("狀態",s.status)+pill("週期",s.timeframe)+pill("型態",s.order_type)+pill("環境",s.regime_at_entry)+pill("ADX",num(s.adx_at_entry,0))+pill("共識",s.consensus_at_entry)+pill("資費",num(s.funding_at_entry,4))+pill("多空比",num(s.ls_ratio_at_entry,2));
  if(meta)h+='<div class="meta">'+meta+'</div>';
  if(has(s.created))h+='<div class="tiny" style="margin-top:8px">建立：'+esc(s.created)+'</div>';
  h+='</div>';
  return h;
}

function resRow(r){
  var p=Number(r.final_pct);
  var col=(!isNaN(p)&&p>0)?"var(--green)":"var(--rose)";
  var h='<div class="card" style="padding:11px 13px"><div class="row">';
  h+='<div><span class="sym" style="font-size:14px">'+esc(r.symbol||"--")+'</span> '+dirChip(r.direction)+'</div>';
  h+='<div class="mono" style="font-weight:800;color:'+col+'">'+pct(r.final_pct)+'</div></div>';
  h+='<div class="row" style="margin-top:5px"><div class="tiny">'+esc(r.result||"")+(has(r.tp_hit_count)?'｜TP命中 '+num(r.tp_hit_count,0):'')+'</div>';
  h+='<div class="tiny">'+esc(r.ts||"")+'</div></div></div>';
  return h;
}

function spark(cum){
  if(!cum||!cum.length)return '<div class="empty">尚無已結算交易</div>';
  var w=400,h=92,pad=7;
  var mn=Math.min.apply(null,cum),mx=Math.max.apply(null,cum);
  if(mn===mx){mn-=1;mx+=1;}
  var dx=(w-pad*2)/Math.max(1,cum.length-1);
  var pts=cum.map(function(v,i){
    var x=pad+i*dx, y=pad+(h-pad*2)*(1-(v-mn)/(mx-mn));
    return x.toFixed(1)+","+y.toFixed(1);
  }).join(" ");
  var last=cum[cum.length-1], col=last>=0?"var(--green)":"var(--rose)";
  var s='<svg viewBox="0 0 '+w+' '+h+'" width="100%" height="'+h+'">';
  if(0>=mn&&0<=mx){
    var zy=pad+(h-pad*2)*(1-(0-mn)/(mx-mn));
    s+='<line x1="'+pad+'" y1="'+zy.toFixed(1)+'" x2="'+(w-pad)+'" y2="'+zy.toFixed(1)+'" stroke="var(--line)" stroke-width="1"/>';
  }
  s+='<polyline fill="none" stroke="'+col+'" stroke-width="2" points="'+pts+'"/></svg>';
  return s;
}

function render(d){
  $("err").innerHTML="";
  var chips=d.use_redis
    ?'<span class="chip" style="color:var(--green);border-color:rgba(52,211,153,.3)">&#9679; Redis 已連</span>'
    :'<span class="chip" style="color:var(--amber);border-color:rgba(245,166,35,.3)">&#9679; 本機暫存</span>';
  chips+='<span class="chip gold" style="border-color:rgba(233,196,90,.3)">追蹤 '+(d.active?d.active.length:0)+'</span>';
  var st=d.stats||{};
  chips+='<span class="chip" style="color:var(--mut);border-color:rgba(154,148,130,.3)">已結算 '+(st.n||0)+'</span>';
  $("chips").innerHTML=chips;
  try{$("upd").textContent=new Date(d.ts).toLocaleTimeString("zh-Hant",{hour12:false});}catch(e){$("upd").textContent="--";}

  var sv="";
  if(d.active&&d.active.length)d.active.forEach(function(s){sv+=sigCard(s);});
  else sv='<div class="card"><div class="empty">目前沒有追蹤中的信號</div></div>';
  $("v_sig").innerHTML=sv;

  var ev='<div class="kgrid">';
  ev+='<div class="kpi"><div class="l">樣本數</div><div class="v">'+(st.n||0)+'</div></div>';
  ev+='<div class="kpi"><div class="l">勝率</div><div class="v">'+(st.win_rate==null?"--":st.win_rate+"%")+'</div></div>';
  var ecol=(st.exp!=null&&st.exp>0)?"var(--green)":(st.exp!=null?"var(--rose)":"var(--tx)");
  ev+='<div class="kpi"><div class="l">毛期望值</div><div class="v" style="color:'+ecol+'">'+(st.exp==null?"--":(st.exp>0?"+":"")+st.exp+"%")+'</div></div>';
  ev+='<div class="kpi"><div class="l">平均盈</div><div class="v" style="color:var(--green)">'+(st.avg_win==null?"--":"+"+st.avg_win+"%")+'</div></div>';
  ev+='<div class="kpi"><div class="l">平均虧</div><div class="v" style="color:var(--rose)">'+(st.avg_loss==null?"--":st.avg_loss+"%")+'</div></div>';
  var pf=(st.avg_win!=null&&st.avg_loss!=null&&st.avg_loss!=0)?Math.abs(st.avg_win/st.avg_loss).toFixed(2):"--";
  ev+='<div class="kpi"><div class="l">盈虧比</div><div class="v">'+pf+'</div></div>';
  ev+='</div>';
  ev+='<div class="card"><div class="sec" style="margin:0 0 6px">累積毛損益 %</div>'+spark(d.cum)+'</div>';
  ev+='<div class="sec">最近結算</div>';
  if(d.results&&d.results.length)d.results.forEach(function(r){ev+=resRow(r);});
  else ev+='<div class="card"><div class="empty">尚無結算紀錄</div></div>';
  ev+='<div class="note banner card" style="padding:10px 13px">數值為毛價格 %（未扣手續費/滑點，約 0.15~0.2%/筆）。SIM 資料，僅供自我驗證，非真錢績效。</div>';
  $("v_sta").innerHTML=ev;
}

function fngColor(v){
  if(v<25)return "var(--rose)";
  if(v<45)return "var(--amber)";
  if(v<55)return "var(--gold)";
  if(v<75)return "var(--green)";
  return "var(--green)";
}
function renderMarket(m){
  var h="";
  var f=m.fng;
  if(f&&has(f.value)){
    h+='<div class="card"><div class="row"><div class="small gold">恐懼與貪婪指數</div><div class="tiny">每 30 分更新</div></div>';
    h+='<div class="row" style="margin-top:6px;align-items:flex-end"><div class="mono" style="font-size:30px;font-weight:800;color:'+fngColor(f.value)+'">'+f.value+'</div>';
    h+='<div class="small" style="color:'+fngColor(f.value)+'">'+esc(f.label||"")+'</div></div>';
    h+='<div class="gauge"><div class="gpin" style="left:'+Math.max(0,Math.min(100,f.value))+'%"></div></div>';
    h+='<div class="row tiny"><span>極度恐懼</span><span>極度貪婪</span></div></div>';
  }
  if(m.coins&&m.coins.length){
    h+='<div class="sec">主流行情</div><div class="card">';
    m.coins.forEach(function(c){
      var ccol=(c.chg!=null&&c.chg>=0)?"var(--green)":"var(--rose)";
      var pr=Number(c.price);
      var ps=pr>=100?pr.toFixed(0):pr>=1?pr.toFixed(2):pr.toFixed(4);
      h+='<div class="coin"><div><span class="sym" style="font-size:14px">'+esc(c.sym)+'</span></div>';
      h+='<div style="text-align:right"><div class="mono" style="font-weight:700">$'+ps+'</div>';
      h+='<div class="tiny mono" style="color:'+ccol+'">'+(c.chg==null?"--":pct(c.chg))+'</div></div></div>';
    });
    h+='</div>';
  }
  if(m.news&&m.news.length){
    h+='<div class="sec">市場快訊</div><div class="card news">';
    m.news.forEach(function(n){
      h+='<div class="nitem"><div style="font-size:12px;line-height:1.5">'+esc(n.title)+'</div>';
      h+='<div class="tiny" style="margin-top:3px">'+esc(n.src||"")+(has(n.time)?' · '+esc(n.time):'')+'</div></div>';
    });
    h+='</div>';
  }
  if(!h)h='<div class="card"><div class="empty">外部行情讀取中或暫時無法取得</div></div>';
  $("v_mkt").innerHTML=h;
}

function load(){
  fetch("/api/state?key="+encodeURIComponent(KEY),{cache:"no-store"})
    .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(render)
    .catch(function(e){$("err").innerHTML='<div class="err">讀取失敗：'+esc(e.message)+'</div>';});
}
var _mktAt=0;
function loadMarket(force){
  if(!force&&Date.now()-_mktAt<60000)return;
  _mktAt=Date.now();
  fetch("/api/market?key="+encodeURIComponent(KEY),{cache:"no-store"})
    .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(renderMarket)
    .catch(function(e){$("v_mkt").innerHTML='<div class="err">行情讀取失敗：'+esc(e.message)+'</div>';});
}
setTab("sig");
load();
setInterval(load,20000);
</script>
</body>
</html>"""