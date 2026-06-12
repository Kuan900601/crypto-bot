# webapp.py — 黑潮船長 個人儀表板（唯讀 PWA）
# 原則：不碰策略；缺字段一律 .get 容錯；未設 DASH_TOKEN 則不啟動（安全預設）；純標準庫，零新依賴
import json
import os
import threading
import logging
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("webapp")
_get_state = None
_TOKEN = os.environ.get("DASH_TOKEN", "")


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
        logger.warning("stats 計算失敗: " + str(e))
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
            active.append({
                "symbol": sym,
                "direction": sig.get("direction"),
                "entry": sig.get("entry"),
                "sl": sig.get("sl"),
                "tp1": sig.get("tp1"), "tp2": sig.get("tp2"),
                "tp3": sig.get("tp3"), "tp4": sig.get("tp4"),
                "tp_hit": sig.get("tp_hit", []),
                "score": sig.get("score"),
                "tier": sig.get("tier"),
                "win_rate": sig.get("win_rate"),
                "created": sig.get("created"),
            })
    except Exception as e:
        logger.warning("active 快照失敗: " + str(e))

    results = []
    cum = []
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
            results.append({
                "symbol": r.get("symbol"),
                "direction": r.get("direction"),
                "final_pct": r.get("final_pct"),
                "result": r.get("result"),
                "tier": r.get("tier"),
                "tp_hit_count": r.get("tp_hit_count"),
                "ts": r.get("ts") or r.get("closed_at") or r.get("time") or "",
            })
    except Exception as e:
        logger.warning("results 快照失敗: " + str(e))

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "active": active,
        "results": results,
        "stats": _stats(results_raw),
        "cum": cum,
        "last_push": scan.get("last_push"),
        "use_redis": st.get("use_redis"),
    }


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

    def do_GET(self):
        try:
            u = urlparse(self.path)
            q = parse_qs(u.query)
            key = (q.get("key") or [""])[0]
            if (not _TOKEN) or key != _TOKEN:
                self._send(401, "未授權：網址需帶 ?key=DASH_TOKEN", "text/plain")
                return
            if u.path in ("/", "/app"):
                self._send(200, _HTML.replace("__KEY__", key), "text/html")
            elif u.path == "/api/state":
                self._send(200, json.dumps(_snapshot(), ensure_ascii=False, default=str), "application/json")
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
<meta name="theme-color" content="#04090F">
<title>黑潮船長</title>
<style>
:root{--bg:#04090F;--card:rgba(13,26,38,.78);--line:rgba(110,180,210,.10);
--cyan:#22D3EE;--deep:#1E3A5F;--gold:#F5C66B;--green:#34D399;--rose:#FB7185;
--amber:#F5A623;--tx:#E6EDF3;--mut:#8AA0B4;--dim:#5A7186}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:radial-gradient(1100px 500px at 50% -10%,#0A1A2E 0%,var(--bg) 60%);
color:var(--tx);font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif;
min-height:100vh;padding-bottom:40px}
.wrap{max-width:430px;margin:0 auto;padding:0 16px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
header{position:sticky;top:0;z-index:20;background:rgba(4,9,15,.85);
backdrop-filter:blur(14px);padding:14px 0 10px}
.brand{display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:10px}
.anchor{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;
justify-content:center;background:linear-gradient(135deg,var(--deep),rgba(34,211,238,.27));
border:1px solid rgba(34,211,238,.33);font-size:16px}
.h1{font-size:16px;font-weight:800;letter-spacing:1px}
.h2{font-size:8px;color:var(--dim);letter-spacing:3px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.chip{font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px;
border:1px solid;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.flow{height:2px;margin-top:10px;border-radius:99px;opacity:.6;
background:linear-gradient(90deg,transparent,var(--cyan),var(--deep),var(--cyan),transparent);
background-size:200% 100%;animation:flow 7s linear infinite}
@keyframes flow{0%{background-position:0 0}100%{background-position:200% 0}}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.tabs{display:flex;gap:8px;margin:12px 0}
.tab{flex:1;text-align:center;padding:9px 0;border-radius:14px;font-size:13px;
font-weight:700;color:var(--dim);background:var(--card);border:1px solid var(--line);cursor:pointer}
.tab.on{color:var(--cyan);border-color:rgba(34,211,238,.4);box-shadow:0 0 14px rgba(34,211,238,.12)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;
padding:14px;margin-bottom:12px;backdrop-filter:blur(10px);animation:fadeUp .3s}
.row{display:flex;align-items:center;justify-content:space-between}
.sym{font-size:17px;font-weight:800}
.small{font-size:10px;color:var(--dim)}
.sec{font-size:11px;letter-spacing:2px;color:var(--dim);font-weight:700;margin:16px 2px 8px}
.kgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:10px 8px;text-align:center}
.kpi .l{font-size:9px;color:var(--dim);margin-bottom:3px}
.kpi .v{font-size:14px;font-weight:800}
.tpgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}
.tp{text-align:center;padding:6px 2px;border-radius:10px;background:rgba(138,160,180,.07);
border:1px solid var(--line)}
.tp.hit{border-color:rgba(34,211,238,.45);background:rgba(34,211,238,.10)}
.tp .l{font-size:9px;color:var(--dim)}
.tp .v{font-size:11px;font-weight:700;margin-top:2px}
.note{font-size:10px;color:var(--dim);margin:4px 2px 10px;line-height:1.7}
.banner{border-left:3px solid var(--amber)}
svg{display:block}
.err{font-size:11px;color:var(--rose);text-align:center;margin:8px 0}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand">
    <div class="logo">
      <div class="anchor">&#9875;</div>
      <div><div class="h1">黑潮船長</div><div class="h2">SIGNALS BOT</div></div>
    </div>
    <span class="chip" style="color:var(--mut);border-color:rgba(138,160,180,.3)" id="upd">--</span>
  </div>
  <div class="chips" id="statusChips"></div>
  <div class="flow"></div>
  <div class="tabs">
    <div class="tab on" id="tabSig" onclick="setTab('sig')">&#128225; 信號</div>
    <div class="tab" id="tabSta" onclick="setTab('sta')">&#128202; 統計</div>
  </div>
</header>
<div id="err"></div>
<div id="viewSig"></div>
<div id="viewSta" style="display:none"></div>
</div>
<script>
var KEY = "__KEY__";
var TIER = {S:"\\uD83D\\uDC8E S", A:"\\uD83E\\uDD47 A", B:"\\uD83E\\uDD48 B", C:"\\uD83E\\uDD49 C"};
var tab = "sig";

function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?"":s).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function num(v,d){if(v==null||v==="")return "--";var n=Number(v);if(isNaN(n))return esc(v);return n.toFixed(d==null?2:d);}
function pct(v){if(v==null||v==="")return "--";var n=Number(v);if(isNaN(n))return esc(v);return (n>0?"+":"")+n.toFixed(2)+"%";}

function setTab(t){
  tab=t;
  $("tabSig").className="tab"+(t==="sig"?" on":"");
  $("tabSta").className="tab"+(t==="sta"?" on":"");
  $("viewSig").style.display=(t==="sig"?"":"none");
  $("viewSta").style.display=(t==="sta"?"":"none");
}

function dirChip(d){
  if(d==="LONG"||d==="多")return '<span style="color:var(--green)">多 LONG</span>';
  if(d==="SHORT"||d==="空")return '<span style="color:var(--rose)">空 SHORT</span>';
  return '<span style="color:var(--mut)">'+esc(d||"--")+'</span>';
}

function tpCell(label,val,hit){
  return '<div class="tp'+(hit?" hit":"")+'"><div class="l">'+label+'</div><div class="v mono">'+num(val,4)+'</div></div>';
}

function sigCard(s){
  var hit = s.tp_hit||[];
  function isHit(n){return hit.indexOf(n)>=0||hit.indexOf(String(n))>=0;}
  var tier = TIER[s.tier]||esc(s.tier||"--");
  var h='<div class="card">';
  h+='<div class="row"><div class="sym">'+esc(s.symbol||"--")+'</div><div class="small">'+tier+'</div></div>';
  h+='<div class="row" style="margin-top:6px"><div>'+dirChip(s.direction)+'</div>';
  h+='<div class="small">分數 '+num(s.score,0)+'｜勝率 '+num(s.win_rate,0)+'%</div></div>';
  h+='<div class="row" style="margin-top:8px"><div class="small">進場 <span class="mono">'+num(s.entry,4)+'</span></div>';
  h+='<div class="small">止損 <span class="mono" style="color:var(--rose)">'+num(s.sl,4)+'</span></div></div>';
  h+='<div class="tpgrid">';
  h+=tpCell("TP1",s.tp1,isHit(1))+tpCell("TP2",s.tp2,isHit(2))+tpCell("TP3",s.tp3,isHit(3))+tpCell("TP4",s.tp4,isHit(4));
  h+='</div>';
  if(s.created)h+='<div class="note">建立：'+esc(s.created)+'</div>';
  h+='</div>';
  return h;
}

function resRow(r){
  var p=Number(r.final_pct);
  var col=(!isNaN(p)&&p>0)?"var(--green)":"var(--rose)";
  var h='<div class="card" style="padding:10px 12px"><div class="row">';
  h+='<div><span class="sym" style="font-size:14px">'+esc(r.symbol||"--")+'</span> '+dirChip(r.direction)+'</div>';
  h+='<div class="mono" style="font-weight:800;color:'+col+'">'+pct(r.final_pct)+'</div></div>';
  h+='<div class="row" style="margin-top:4px"><div class="small">'+esc(r.result||"")+'｜TP命中 '+num(r.tp_hit_count,0)+'</div>';
  h+='<div class="small">'+esc(r.ts||"")+'</div></div></div>';
  return h;
}

function spark(cum){
  if(!cum||!cum.length)return '<div class="note">尚無已結算交易</div>';
  var w=380,h=90,pad=6;
  var mn=Math.min.apply(null,cum),mx=Math.max.apply(null,cum);
  if(mn===mx){mn-=1;mx+=1;}
  var dx=(w-pad*2)/Math.max(1,cum.length-1);
  var pts=cum.map(function(v,i){
    var x=pad+i*dx;
    var y=pad+(h-pad*2)*(1-(v-mn)/(mx-mn));
    return x.toFixed(1)+","+y.toFixed(1);
  }).join(" ");
  var last=cum[cum.length-1];
  var col=last>=0?"var(--green)":"var(--rose)";
  var s='<svg viewBox="0 0 '+w+' '+h+'" width="100%" height="'+h+'">';
  if(0>=mn&&0<=mx){
    var zeroY=pad+(h-pad*2)*(1-(0-mn)/(mx-mn));
    s+='<line x1="'+pad+'" y1="'+zeroY.toFixed(1)+'" x2="'+(w-pad)+'" y2="'+zeroY.toFixed(1)+'" stroke="var(--line)" stroke-width="1"/>';
  }
  s+='<polyline fill="none" stroke="'+col+'" stroke-width="2" points="'+pts+'"/></svg>';
  return s;
}

function render(d){
  $("err").innerHTML="";
  var chips="";
  chips+=d.use_redis
    ?'<span class="chip" style="color:var(--green);border-color:rgba(52,211,153,.3)">Redis 已連</span>'
    :'<span class="chip" style="color:var(--amber);border-color:rgba(245,166,35,.3)">本機暫存</span>';
  chips+='<span class="chip" style="color:var(--cyan);border-color:rgba(34,211,238,.3)">追蹤 '+(d.active?d.active.length:0)+'</span>';
  var st=d.stats||{};
  chips+='<span class="chip" style="color:var(--mut);border-color:rgba(138,160,180,.3)">已結算 '+(st.n||0)+'</span>';
  $("statusChips").innerHTML=chips;
  try{$("upd").textContent=new Date(d.ts).toLocaleTimeString("zh-Hant",{hour12:false});}catch(e){$("upd").textContent="--";}

  var sv="";
  if(d.active&&d.active.length){d.active.forEach(function(s){sv+=sigCard(s);});}
  else sv='<div class="card"><div class="note" style="text-align:center">目前沒有追蹤中的信號</div></div>';
  $("viewSig").innerHTML=sv;

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
  ev+='<div class="card"><div class="sec" style="margin:0 0 8px">累積毛損益 %</div>'+spark(d.cum)+'</div>';
  ev+='<div class="sec">最近結算</div>';
  if(d.results&&d.results.length){d.results.forEach(function(r){ev+=resRow(r);});}
  else ev+='<div class="card"><div class="note" style="text-align:center">尚無結算紀錄</div></div>';
  ev+='<div class="note banner card" style="padding:10px 12px">數值為毛價格 %（未扣手續費/滑點，約 0.15~0.2%/筆）。SIM 資料，僅供自我驗證，非真錢績效。</div>';
  $("viewSta").innerHTML=ev;
}

function load(){
  fetch("/api/state?key="+encodeURIComponent(KEY),{cache:"no-store"})
    .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
    .then(render)
    .catch(function(e){$("err").innerHTML='<div class="err">讀取失敗：'+esc(e.message)+'</div>';});
}
setTab("sig");
load();
setInterval(load,20000);
</script>
</body>
</html>"""
