"""Sagemcom Control — enciende/apaga el acceso a internet por MAC.

Uso:  python app.py   ->  http://localhost:8000
"""
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

load_dotenv()

from sagemcom_api.client import SagemcomClient  # noqa: E402
from sagemcom_api.enums import EncryptionMethod  # noqa: E402

HOST = os.getenv("ROUTER_HOST", "192.168.0.1")
USER = os.getenv("ROUTER_USER", "user")
PASSWORD = os.getenv("ROUTER_PASS", "")
ENC = os.getenv("ROUTER_ENCRYPTION", "AUTO").upper()
BLOCK_XPATH = os.getenv("BLOCK_LIST_XPATH", "").strip()
BLOCK_SEP = os.getenv("BLOCK_LIST_SEP", ",")
PORT = int(os.getenv("PORT", "8000"))
STATE_FILE = os.path.join(os.path.dirname(__file__), "blocked.json")

_enc_method = None


def norm_mac(mac: str) -> str:
    h = re.sub(r"[^0-9a-fA-F]", "", mac).upper()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else mac.upper()


def load_blocked() -> list:
    try:
        with open(STATE_FILE) as f:
            return [norm_mac(m) for m in json.load(f)]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_blocked(macs: list):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(set(macs)), f, indent=2)


async def detect_encryption():
    global _enc_method
    if _enc_method is not None:
        return _enc_method
    if ENC != "AUTO":
        _enc_method = EncryptionMethod[ENC]
        return _enc_method
    async with SagemcomClient(HOST, USER, PASSWORD, None) as c:
        _enc_method = await c.get_encryption_method()
    return _enc_method


@asynccontextmanager
async def router():
    if not PASSWORD:
        raise HTTPException(500, "Falta ROUTER_PASS en el .env")
    enc = await detect_encryption()
    async with SagemcomClient(HOST, USER, PASSWORD, enc) as client:
        await client.login()
        yield client


def split_list(raw) -> list:
    if raw is None:
        return []
    s = raw if isinstance(raw, str) else str(raw)
    return [norm_mac(p) for p in s.split(BLOCK_SEP) if p.strip()]


async def read_deny_list(client) -> list:
    data = await client.get_value_by_xpath(BLOCK_XPATH)
    # la respuesta puede venir anidada; quédate con el primer escalar
    def first_scalar(o):
        if isinstance(o, dict):
            for v in o.values():
                r = first_scalar(v)
                if r is not None:
                    return r
        elif isinstance(o, list) and o:
            return first_scalar(o[0])
        elif isinstance(o, (str, int)):
            return o
        return None
    return split_list(first_scalar(data))


async def write_deny_list(client, macs: list):
    value = BLOCK_SEP.join(sorted(set(macs)))
    await client.set_value_by_xpath(BLOCK_XPATH, value)


app = FastAPI(title="Sagemcom Control")


@app.get("/api/devices")
async def devices():
    async with router() as client:
        hosts = await client.get_hosts()
    blocked = set(load_blocked())
    out = []
    for d in hosts:
        mac = norm_mac(d.mac or "")
        out.append({
            "mac": mac,
            "ip": d.ip or "",
            "name": d.name or "desconocido",
            "active": bool(d.active),
            "blocked": mac in blocked,
        })
    # primero los bloqueados, luego activos, luego el resto
    out.sort(key=lambda x: (not x["blocked"], not x["active"], x["name"].lower()))
    return out


@app.post("/api/block/{mac}")
async def block(mac: str):
    if not BLOCK_XPATH:
        raise HTTPException(501, "Bloqueo sin configurar: ejecuta discover.py y pon BLOCK_LIST_XPATH en el .env")
    mac = norm_mac(mac)
    async with router() as client:
        deny = read_deny_list(client)
        if mac not in deny:
            deny.append(mac)
            await write_deny_list(client, deny)
    blocked = load_blocked() + [mac]
    save_blocked(blocked)
    return {"mac": mac, "blocked": True}


@app.post("/api/unblock/{mac}")
async def unblock(mac: str):
    if not BLOCK_XPATH:
        raise HTTPException(501, "Bloqueo sin configurar: ejecuta discover.py y pon BLOCK_LIST_XPATH en el .env")
    mac = norm_mac(mac)
    async with router() as client:
        deny = [m for m in read_deny_list(client) if m != mac]
        await write_deny_list(client, deny)
    save_blocked([m for m in load_blocked() if m != mac])
    return {"mac": mac, "blocked": False}


@app.get("/", response_class=HTMLResponse)
async def index():
    blocking = "true" if BLOCK_XPATH else "false"
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0f1a">
<title>Sagemcom Control</title>
<style>
:root{{--bg:#0b0f1a;--card:#151b2e;--card2:#1b2340;--txt:#f2f4fa;--mut:#8b93b0;
--green:#2fd671;--red:#ff5a5a;--acc:#5b8cff;--acc2:#8b5bff}}
*{{box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
background:radial-gradient(1200px 600px at 80% -10%,#1c2450 0%,var(--bg) 55%) fixed,var(--bg);
color:var(--txt);min-height:100vh;padding-bottom:96px}}
header{{padding:28px 20px 18px;position:sticky;top:0;z-index:5;
background:linear-gradient(180deg,rgba(11,15,26,.96),rgba(11,15,26,.75));backdrop-filter:blur(10px)}}
h1{{margin:0;font-size:24px;letter-spacing:.3px;display:flex;align-items:center;gap:10px}}
h1 .logo{{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;font-size:22px;
background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 4px 18px rgba(91,140,255,.4)}}
.sub{{color:var(--mut);font-size:13px;margin:6px 0 14px}}
.stats{{display:flex;gap:8px}}
.pill{{flex:1;background:var(--card);border:1px solid #232c4e;border-radius:12px;padding:10px 12px;text-align:center}}
.pill b{{display:block;font-size:20px}}.pill span{{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px}}
.pill.ok b{{color:var(--green)}}.pill.ko b{{color:var(--red)}}.pill.tot b{{color:var(--acc)}}
.search{{margin:14px 20px 4px;position:relative}}
.search input{{width:100%;background:var(--card);border:1px solid #232c4e;color:var(--txt);
border-radius:14px;padding:13px 14px 13px 42px;font-size:15px;outline:none}}
.search input:focus{{border-color:var(--acc)}}
.search::before{{content:"🔍";position:absolute;left:14px;top:12px;font-size:16px;opacity:.7}}
#list{{padding:10px 16px}}
.card{{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid #232c4e;
border-radius:16px;padding:14px;margin-bottom:10px;display:flex;align-items:center;gap:12px;
box-shadow:0 6px 20px rgba(0,0,0,.35);animation:pop .25s ease}}
@keyframes pop{{from{{transform:translateY(6px);opacity:0}}}}
.card.blocked{{border-color:rgba(255,90,90,.45)}}
.icon{{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:24px;
background:#0e1428;flex-shrink:0;border:1px solid #232c4e}}
.info{{flex:1;min-width:0}}
.name{{font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.meta{{font-size:11.5px;color:var(--mut);font-family:ui-monospace,monospace;margin-top:3px}}
.tag{{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;margin-top:6px;letter-spacing:.4px}}
.tag.on{{background:rgba(47,214,113,.15);color:var(--green)}}
.tag.off{{background:rgba(255,90,90,.15);color:var(--red)}}
.tag.idle{{background:rgba(139,147,176,.15);color:var(--mut)}}
.switch{{position:relative;width:56px;height:32px;flex-shrink:0}}
.switch input{{opacity:0;width:0;height:0}}
.sl{{position:absolute;inset:0;border-radius:32px;cursor:pointer;transition:.25s;
background:linear-gradient(135deg,#ff7a7a,#ff3b3b);box-shadow:inset 0 2px 6px rgba(0,0,0,.4)}}
.sl:before{{content:"";position:absolute;width:24px;height:24px;left:4px;top:4px;background:#fff;
border-radius:50%;transition:.25s;box-shadow:0 2px 6px rgba(0,0,0,.4)}}
input:checked+.sl{{background:linear-gradient(135deg,#35e07f,#12b857)}}
input:checked+.sl:before{{transform:translateX(24px)}}
.switch input:disabled+.sl{{opacity:.35;cursor:not-allowed}}
.warn{{margin:12px 20px;background:rgba(255,180,0,.1);border:1px solid rgba(255,180,0,.35);
color:#ffcf5c;padding:12px 14px;border-radius:14px;font-size:13px;line-height:1.5}}
.refresh{{position:fixed;bottom:0;left:0;right:0;padding:14px 20px calc(14px + env(safe-area-inset-bottom));
background:linear-gradient(180deg,transparent,rgba(11,15,26,.95) 40%)}}
.refresh button{{width:100%;padding:15px;border:0;border-radius:16px;font-size:16px;font-weight:700;color:#fff;
background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 6px 24px rgba(91,140,255,.45);cursor:pointer}}
.refresh button:active{{transform:scale(.98)}}
.empty{{text-align:center;color:var(--mut);padding:40px 20px;font-size:14px}}
</style></head><body>
<header>
<h1><span class="logo">📡</span>Sagemcom Control</h1>
<div class="sub">Toca el interruptor para dar o quitar internet a cada dispositivo</div>
<div class="stats">
<div class="pill tot"><b id="sTot">–</b><span>dispositivos</span></div>
<div class="pill ok"><b id="sOn">–</b><span>con internet</span></div>
<div class="pill ko"><b id="sOff">–</b><span>bloqueados</span></div>
</div></header>
<div id="warn"></div>
<div class="search"><input id="q" placeholder="Buscar dispositivo…" oninput="render()"></div>
<div id="list"></div>
<div class="refresh"><button onclick="load()">↻ Actualizar</button></div>
<script>
const BLOCKING = {blocking};
let DEVS = [];
function icon(n){{n=n.toLowerCase();
if(/iphone|android|móvil|movil|phone|pixel|galaxy|redmi|poco/i.test(n))return "📱";
if(/tv|tele|smart/i.test(n))return "📺";
if(/play|xbox|nintendo|consola/i.test(n))return "🎮";
if(/laptop|portátil|portatil|macbook|notebook/i.test(n))return "💻";
if(/pc-|pc\b|desktop|sobremesa|imac/i.test(n))return "🖥️";
if(/tablet|ipad/i.test(n))return "📟";
if(/alexa|echo|google home|homepod/i.test(n))return "🔊";
if(/impresora|printer/i.test(n))return "🖨️";
return "🌐";}}
async function load(){{
try{{
const r=await fetch('/api/devices');if(!r.ok)throw new Error(await r.text());
DEVS=await r.json();render();
if(!BLOCKING)document.getElementById('warn').innerHTML=
'<div class="warn">⚠️ <b>Bloqueo sin configurar.</b><br>Ejecuta <b>python discover.py</b> en el portátil y pon <b>BLOCK_LIST_XPATH</b> en el .env para activar los interruptores.</div>';
}}catch(e){{document.getElementById('list').innerHTML='<div class="empty">❌ '+e.message+'</div>';}}
}}
function render(){{
const q=document.getElementById('q').value.toLowerCase();
const devs=DEVS.filter(d=>(d.name+d.mac+d.ip).toLowerCase().includes(q));
const on=DEVS.filter(d=>!d.blocked&&d.active).length, off=DEvs_blocked();
document.getElementById('sTot').textContent=DEVS.length;
document.getElementById('sOn').textContent=on;
document.getElementById('sOff').textContent=off;
document.getElementById('list').innerHTML=devs.length?devs.map(d=>`
<div class="card ${{d.blocked?'blocked':''}}">
<div class="icon">${{icon(d.name)}}</div>
<div class="info"><div class="name">${{d.name}}</div>
<div class="meta">${{d.mac}}<br>${{d.ip||'sin IP'}}</div>
<span class="tag ${{d.blocked?'off':(d.active?'on':'idle')}}">${{d.blocked?'⛔ BLOQUEADO':(d.active?'● EN LÍNEA':'○ INACTIVO')}}</span></div>
<label class="switch" title="Internet"><input type="checkbox" ${{d.blocked?'':'checked'}}
${{BLOCKING?'':'disabled'}} onchange="toggle('${{d.mac}}',this.checked)"><span class="sl"></span></label>
</div>`).join(''):'<div class="empty">Sin resultados 🔍</div>';
}}
function DEvs_blocked(){{return DEVS.filter(d=>d.blocked).length;}}
async function toggle(mac,allowed){{
const r=await fetch('/api/'+(allowed?'unblock/':'block/')+encodeURIComponent(mac),{{method:'POST'}});
if(!r.ok)alert('Error: '+await r.text());load();
}}
load();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
