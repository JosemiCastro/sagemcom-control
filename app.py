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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sagemcom Control</title>
<style>
*{{box-sizing:border-box}}body{{font-family:system-ui;margin:0;background:#111;color:#eee;padding:16px}}
h1{{font-size:20px;margin:0 0 4px}}p.sub{{color:#999;font-size:13px;margin:0 0 16px}}
.card{{background:#1c1c1e;border-radius:12px;padding:12px;margin-bottom:10px;display:flex;align-items:center;gap:12px}}
.info{{flex:1;min-width:0}}.name{{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.meta{{font-size:12px;color:#999;font-family:monospace}}
.dot{{width:10px;height:10px;border-radius:50%;background:#333;flex-shrink:0}}
.dot.on{{background:#30d158}}.dot.off{{background:#ff453a}}
.switch{{position:relative;width:52px;height:30px;flex-shrink:0}}
.switch input{{opacity:0;width:0;height:0}}
.slider{{position:absolute;inset:0;background:#333;border-radius:30px;transition:.2s;cursor:pointer}}
.slider:before{{content:"";position:absolute;width:22px;height:22px;left:4px;top:4px;background:#fff;border-radius:50%;transition:.2s}}
input:checked+.slider{{background:#ff453a}}input:checked+.slider:before{{transform:translateX(22px)}}
#bar{{text-align:center;color:#999;font-size:13px;margin:12px}}
.warn{{background:#3a2b00;color:#ffcc00;padding:10px;border-radius:10px;font-size:13px;margin-bottom:12px}}
button.refresh{{width:100%;padding:12px;border-radius:10px;border:0;background:#0a84ff;color:#fff;font-size:15px;margin-top:8px}}
</style></head><body>
<h1>📡 Sagemcom Control</h1>
<p class="sub">Encender / apagar internet por dispositivo</p>
<div id="warn"></div>
<div id="list"></div>
<div id="bar"></div>
<button class="refresh" onclick="load()">↻ Actualizar</button>
<script>
const BLOCKING = {blocking};
async function load(){{
  document.getElementById('bar').textContent='Cargando...';
  try{{
    const r = await fetch('/api/devices');
    if(!r.ok) throw new Error(await r.text());
    const devs = await r.json();
    document.getElementById('bar').textContent = devs.length+' dispositivos';
    if(!BLOCKING) document.getElementById('warn').innerHTML =
      '<div class="warn">⚠️ Bloqueo sin configurar. Ejecuta <b>python discover.py</b> y pon BLOCK_LIST_XPATH en el .env</div>';
    document.getElementById('list').innerHTML = devs.map(d=>`
      <div class="card">
        <div class="dot ${{d.active?'on':'off'}}"></div>
        <div class="info"><div class="name">${{d.name}}</div>
        <div class="meta">${{d.mac}} · ${{d.ip||'sin IP'}}${{d.active?'':' · inactivo'}}</div></div>
        <label class="switch"><input type="checkbox" ${{d.blocked?'checked':''}}
          ${{BLOCKING?'':'disabled'}} onchange="toggle('${{d.mac}}',this.checked)">
          <span class="slider"></span></label>
      </div>`).join('');
  }}catch(e){{ document.getElementById('bar').textContent='Error: '+e.message; }}
}}
async function toggle(mac,on){{
  const r = await fetch('/api/'+(on?'block/':'unblock/')+encodeURIComponent(mac),{{method:'POST'}});
  if(!r.ok){{ alert('Error: '+await r.text()); load(); }}
}}
load();
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
