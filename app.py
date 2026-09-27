"""Sagemcom Control — enciende/apaga el acceso a internet por MAC.

Habla directamente con la web del router (sin API interna):
el bloqueo usa la página "Filtro MAC" en modo DENEGAR.

Uso:  python app.py   ->  http://localhost:8000
"""
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

load_dotenv()

from router_web import RouterWeb, norm_mac, scan_devices  # noqa: E402
from tplink import TPLinkWeb  # noqa: E402

HOST = os.getenv("ROUTER_HOST", "192.168.0.1")
USER = os.getenv("ROUTER_USER", "user")
PASSWORD = os.getenv("ROUTER_PASS", "")
PORT = int(os.getenv("PORT", "8000"))
NAMES_FILE = os.path.join(os.path.dirname(__file__), "names.json")
TPLINK_HOST = os.getenv("TPLINK_HOST", "192.168.0.2")
TPLINK_SESSION_FILE = os.path.join(os.path.dirname(__file__),
                                   "tplink_session.json")


def load_names() -> dict:
    try:
        with open(NAMES_FILE) as f:
            return {norm_mac(k): v for k, v in json.load(f).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_names(names: dict):
    with open(NAMES_FILE, "w") as f:
        json.dump(names, f, indent=2, ensure_ascii=False)


def rw() -> RouterWeb:
    if not PASSWORD:
        raise HTTPException(500, "Falta ROUTER_PASS en el .env")
    r = RouterWeb(HOST, USER, PASSWORD)
    r.login()
    return r


def tp() -> TPLinkWeb:
    """TP-Link con la sesion importada del navegador."""
    try:
        with open(TPLINK_SESSION_FILE) as f:
            s = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(500, "Sin sesion TP-Link: importala desde /api/tplink/session")
    t = TPLinkWeb(TPLINK_HOST)
    t.import_browser_session(s["session_id"], s["aes"], s["seq"],
                             s["hash"], s["rsa"])
    return t


def save_tplink_session(session_id, aes, seq, hash_hex, rsa):
    with open(TPLINK_SESSION_FILE, "w") as f:
        json.dump({"session_id": session_id, "aes": aes, "seq": seq,
                   "hash": hash_hex, "rsa": rsa}, f)


app = FastAPI(title="Sagemcom Control")


@app.get("/api/devices")
def devices():
    r = rw()
    entries, _ = r.get_filters()                # [(nombre, mac)] bloqueados
    blocked = {m: n for n, m in entries}
    live = scan_devices(HOST)                      # {mac: (ip, hostname)}
    custom = load_names()
    out = []
    for mac, (ip, hostname) in live.items():
        out.append({"mac": mac, "ip": ip, "router": "sagemcom",
                    "name": custom.get(mac) or blocked.get(mac) or hostname or ip,
                    "active": True, "blocked": mac in blocked})
    for mac, name in blocked.items():              # bloqueados aunque estén offline
        if mac not in live:
            out.append({"mac": mac, "ip": "", "router": "sagemcom",
                        "name": custom.get(mac, name),
                        "active": False, "blocked": True})
    # Dispositivos del TP-Link (filtro MAC)
    try:
        seen = {norm_mac(x["mac"]) for x in out}
        for d in tplink_devices():
            nm = norm_mac(d["mac"])
            if nm not in seen:
                out.append(d)
                seen.add(nm)
            else:
                for x in out:
                    if norm_mac(x["mac"]) == nm:
                        x["router"] = "tplink"
                        x["blocked"] = d["blocked"]
                        x["name"] = d["name"] if d["name"] != d["mac"] else x["name"]
    except HTTPException:
        pass  # sin sesion TP-Link, solo Sagemcom
    out.sort(key=lambda x: (not x["blocked"], not x["active"], x["name"].lower()))
    return out


@app.post("/api/name/{mac}")
def set_name(mac: str, payload: dict):
    mac = norm_mac(mac)
    name = (payload.get("name") or "").strip()
    names = load_names()
    if name:
        names[mac] = name
    else:
        names.pop(mac, None)
    save_names(names)
    return {"mac": mac, "name": name}


@app.post("/api/block/{mac}")
def block(mac: str):
    mac = norm_mac(mac)
    r = rw()
    entries, page_key = r.get_filters()
    if mac not in [m for _, m in entries]:
        entries.append((mac, mac))
        r.set_filters(entries, page_key)
    # Tambien en el TP-Link, por si el dispositivo cambia de wifi
    try:
        tp().set_mac_block(mac, block=True)
    except HTTPException:
        pass
    return {"mac": mac, "blocked": True}


@app.post("/api/unblock/{mac}")
def unblock(mac: str):
    mac = norm_mac(mac)
    r = rw()
    entries, page_key = r.get_filters()
    entries = [(n, m) for n, m in entries if m != mac]
    r.set_filters(entries, page_key)
    try:
        tp().set_mac_block(mac, block=False)
    except HTTPException:
        pass
    return {"mac": mac, "blocked": False}


# ---------- TP-Link ----------
@app.post("/api/tplink/session")
def tplink_session(payload: dict):
    """Importa la sesion del navegador (5 valores de localStorage + URL)."""
    save_tplink_session(payload["session_id"], payload["aes"], payload["seq"],
                        payload["hash"], payload["rsa"])
    f = tp().get_mac_filter()
    return {"ok": True, "entries": len(f["entries"])}


@app.get("/api/tplink/devices")
def tplink_devices():
    t = tp()
    f = t.get_mac_filter()
    custom = load_names()
    out = []
    for e in f["entries"]:
        mac = norm_mac(e["mac"])
        out.append({"mac": e["mac"], "ip": "", "router": "tplink",
                    "name": custom.get(mac) or e["desc"] or e["mac"],
                    "active": True, "blocked": e["enabled"]})
    return out


@app.post("/api/tplink/block/{mac}")
def tplink_block(mac: str, payload: dict = None):
    mac = norm_mac(mac)
    desc = (payload or {}).get("desc", "")
    t = tp()
    t.set_mac_block(mac, block=True, desc=desc)
    return {"mac": mac, "blocked": True, "router": "tplink"}


@app.post("/api/tplink/unblock/{mac}")
def tplink_unblock(mac: str):
    mac = norm_mac(mac)
    t = tp()
    t.set_mac_block(mac, block=False)
    return {"mac": mac, "blocked": False, "router": "tplink"}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0f1a">
<title>Sagemcom Control</title>
<style>
:root{--bg:#0b0f1a;--card:#151b2e;--card2:#1b2340;--txt:#f2f4fa;--mut:#8b93b0;
--green:#2fd671;--red:#ff5a5a;--acc:#5b8cff;--acc2:#8b5bff}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
background:radial-gradient(1200px 600px at 80% -10%,#1c2450 0%,var(--bg) 55%) fixed,var(--bg);
color:var(--txt);min-height:100vh;padding-bottom:96px}
header{padding:28px 20px 18px;position:sticky;top:0;z-index:5;
background:linear-gradient(180deg,rgba(11,15,26,.96),rgba(11,15,26,.75));backdrop-filter:blur(10px)}
h1{margin:0;font-size:24px;letter-spacing:.3px;display:flex;align-items:center;gap:10px}
h1 .logo{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;font-size:22px;
background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 4px 18px rgba(91,140,255,.4)}
.sub{color:var(--mut);font-size:13px;margin:6px 0 14px}
.stats{display:flex;gap:8px}
.pill{flex:1;background:var(--card);border:1px solid #232c4e;border-radius:12px;padding:10px 12px;text-align:center}
.pill b{display:block;font-size:20px}.pill span{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px}
.pill.ok b{color:var(--green)}.pill.ko b{color:var(--red)}.pill.tot b{color:var(--acc)}
.search{margin:14px 20px 4px;position:relative}
.search input{width:100%;background:var(--card);border:1px solid #232c4e;color:var(--txt);
border-radius:14px;padding:13px 14px 13px 42px;font-size:15px;outline:none}
.search input:focus{border-color:var(--acc)}
.search::before{content:"🔍";position:absolute;left:14px;top:12px;font-size:16px;opacity:.7}
#list{padding:10px 16px}
.card{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid #232c4e;
border-radius:16px;padding:14px;margin-bottom:10px;display:flex;align-items:center;gap:12px;
box-shadow:0 6px 20px rgba(0,0,0,.35);animation:pop .25s ease}
@keyframes pop{from{transform:translateY(6px);opacity:0}}
.card.blocked{border-color:rgba(255,90,90,.45)}
.icon{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:24px;
background:#0e1428;flex-shrink:0;border:1px solid #232c4e}
.info{flex:1;min-width:0}
.name{font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.name:active{opacity:.7}
.meta{font-size:11.5px;color:var(--mut);font-family:ui-monospace,monospace;margin-top:3px}
.tag{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;margin-top:6px;letter-spacing:.4px}
.tag.on{background:rgba(47,214,113,.15);color:var(--green)}
.tag.off{background:rgba(255,90,90,.15);color:var(--red)}
.tag.idle{background:rgba(139,147,176,.15);color:var(--mut)}
.switch{position:relative;width:56px;height:32px;flex-shrink:0}
.switch input{opacity:0;width:0;height:0}
.sl{position:absolute;inset:0;border-radius:32px;cursor:pointer;transition:.25s;
background:linear-gradient(135deg,#ff7a7a,#ff3b3b);box-shadow:inset 0 2px 6px rgba(0,0,0,.4)}
.sl:before{content:"";position:absolute;width:24px;height:24px;left:4px;top:4px;background:#fff;
border-radius:50%;transition:.25s;box-shadow:0 2px 6px rgba(0,0,0,.4)}
input:checked+.sl{background:linear-gradient(135deg,#35e07f,#12b857)}
input:checked+.sl:before{transform:translateX(24px)}
.switch input:disabled+.sl{opacity:.35;cursor:not-allowed}
.refresh{position:fixed;bottom:0;left:0;right:0;padding:14px 20px calc(14px + env(safe-area-inset-bottom));
background:linear-gradient(180deg,transparent,rgba(11,15,26,.95) 40%)}
.refresh button{width:100%;padding:15px;border:0;border-radius:16px;font-size:16px;font-weight:700;color:#fff;
background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 6px 24px rgba(91,140,255,.45);cursor:pointer}
.refresh button:active{transform:scale(.98)}
.empty{text-align:center;color:var(--mut);padding:40px 20px;font-size:14px}
.spin{text-align:center;color:var(--mut);padding:40px 20px;font-size:14px;animation:blink 1s infinite}
@keyframes blink{50%{opacity:.4}}
</style></head><body>
<header>
<h1><span class="logo">📡</span>Sagemcom Control</h1>
<div class="sub">Toca el interruptor para dar o quitar internet a cada dispositivo</div>
<div class="stats">
<div class="pill tot"><b id="sTot">–</b><span>dispositivos</span></div>
<div class="pill ok"><b id="sOn">–</b><span>con internet</span></div>
<div class="pill ko"><b id="sOff">–</b><span>bloqueados</span></div>
</div></header>
<div class="search"><input id="q" placeholder="Buscar dispositivo…" oninput="render()"></div>
<div class="search" style="display:flex;gap:8px">
<input id="manualMac" placeholder="MAC manual (ej. E0:9D:31:E7:75:B6)" style="flex:1">
<button onclick="blockManual()" style="background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;border:0;border-radius:14px;padding:13px 18px;font-weight:700;cursor:pointer">⛔ Bloquear</button>
</div>
<div id="list"><div class="spin">Buscando dispositivos en la red… ⏳</div></div>
<div class="refresh"><button onclick="load()">↻ Actualizar</button></div>
<script>
let DEVS = [];
function icon(n){n=n.toLowerCase();
if(/iphone|android|móvil|movil|phone|pixel|galaxy|redmi|poco/i.test(n))return "📱";
if(/tv|tele|smart/i.test(n))return "📺";
if(/play|xbox|nintendo|consola/i.test(n))return "🎮";
if(/laptop|portátil|portatil|macbook|notebook/i.test(n))return "💻";
if(/pc-|pc\b|desktop|sobremesa|imac/i.test(n))return "🖥️";
if(/tablet|ipad/i.test(n))return "📟";
if(/alexa|echo|google home|homepod/i.test(n))return "🔊";
if(/impresora|printer/i.test(n))return "🖨️";
return "🌐";}
async function load(){
document.getElementById('list').innerHTML='<div class="spin">Buscando dispositivos en la red… ⏳</div>';
try{
const r=await fetch('/api/devices');if(!r.ok)throw new Error(await r.text());
DEVS=await r.json();render();
}catch(e){document.getElementById('list').innerHTML='<div class="empty">❌ '+e.message+'</div>';}
}
function render(){
const q=document.getElementById('q').value.toLowerCase();
const devs=DEVS.filter(d=>(d.name+d.mac+d.ip).toLowerCase().includes(q));
const on=DEVS.filter(d=>!d.blocked&&d.active).length, off=DEVS.filter(d=>d.blocked).length;
document.getElementById('sTot').textContent=DEVS.length;
document.getElementById('sOn').textContent=on;
document.getElementById('sOff').textContent=off;
document.getElementById('list').innerHTML=devs.length?devs.map(d=>`
<div class="card ${d.blocked?'blocked':''}">
<div class="icon">${icon(d.name)}</div>
<div class="info"><div class="name" onclick="rename('${d.mac}','${d.name.replace(/'/g,"\\'")}')" title="Toca para renombrar">✏️ ${d.name}</div>
<div class="meta">${d.mac}<br>${d.ip||'sin IP'}${d.router==='tplink'?' · TP-Link':''}</div>
<span class="tag ${d.blocked?'off':(d.active?'on':'idle')}">${d.blocked?'⛔ BLOQUEADO':(d.active?'● EN LÍNEA':'○ INACTIVO')}</span></div>
<label class="switch" title="Internet"><input type="checkbox" ${d.blocked?'':'checked'}
onchange="toggle('${d.mac}',this.checked,this,'${d.router||'sagemcom'}')"><span class="sl"></span></label>
</div>`).join(''):'<div class="empty">Sin resultados 🔍</div>';
}
async function toggle(mac,allowed,el,router){
el.disabled=true;
const base=router==='tplink'?'/api/tplink/':'/api/';
const r=await fetch(base+(allowed?'unblock/':'block/')+encodeURIComponent(mac),{method:'POST'});
if(!r.ok){alert('Error: '+await r.text());el.disabled=false;el.checked=!allowed;return;}
load();
}
async function rename(mac,current){
const name=prompt('Nombre para este dispositivo:',current);
if(name===null)return;
const r=await fetch('/api/name/'+encodeURIComponent(mac),{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
if(!r.ok)alert('Error: '+await r.text());load();
}
async function blockManual(){
const mac=document.getElementById('manualMac').value.trim();
if(!mac){alert('Escribe una MAC');return;}
const r=await fetch('/api/block/'+encodeURIComponent(mac),{method:'POST'});
if(!r.ok){alert('Error: '+await r.text());return;}
document.getElementById('manualMac').value='';
load();
}
load();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
