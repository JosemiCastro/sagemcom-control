"""Habla directamente con la web del Sagemcom F@st 3686 (firmware Vodafone/ONO).

La API interna (/cgi/json-req) no existe en este firmware, así que se replica
lo que hace el navegador:

- Login:       POST /goform/login   (loginUsername, loginPassword, loginpage_flag)
- Ver filtros: GET  /Wifi_MAC_Filter.asp?m=54&sessionKey=XXX
- Aplicar:     POST /goform/Wifi_MAC_Filter?sessionKey=XXX
               (WifiMACFilteringEnable=1, WifiMACFilteringDeny=1,
                WifiMACNumFilters=N, Wifi_Filter_name_I, mac_01_I..mac_06_I)
"""
import os
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def norm_mac(mac: str) -> str:
    h = re.sub(r"[^0-9a-fA-F]", "", mac or "").upper()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else (mac or "").upper()


class RouterWeb:
    def __init__(self, host: str, user: str, password: str, timeout: int = 15):
        self.base = f"http://{host}"
        self.user = user
        self.password = password
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Referer": self.base + "/"})
        self.session_key = None

    # ---------- login ----------
    def _req(self, method, url, **kwargs):
        """Petición con reintentos: el servidor del router a veces corta conexiones."""
        last = None
        for i in range(4):
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kwargs)
                return r
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError) as e:
                last = e
                time.sleep(0.7 * (i + 1))
        raise RuntimeError(f"El router no responde tras varios intentos: {last}")

    def _page_key(self, html: str):
        """Busca el SessionKey en el HTML (var SessionKey=NNNNN)."""
        m = re.search(r"SessionKey\s*=\s*[\"']?(\d+)", html or "", re.IGNORECASE)
        return m.group(1) if m else None

    def login(self) -> str:
        # 1. La página de login trae el SessionKey en su HTML
        r = self._req("GET", self.base + "/login.asp")
        pre_key = self._page_key(r.text)
        if not pre_key:
            raise RuntimeError(
                "No se encontró el SessionKey en la página de login. "
                "El firmware puede haber cambiado.")

        # 2. POST de credenciales con ese sessionKey
        r = self._req(
            "POST", f"{self.base}/goform/login?sessionKey={pre_key}",
            data={"loginUsername": self.user,
                  "loginPassword": self.password,
                  "loginpage_flag": ""},
            allow_redirects=True,
        )
        key = self._extract_key(r) or pre_key
        # 3. Verificar que la sesión es válida pidiendo una página protegida
        probe = self._req("GET", f"{self.base}/Overview.asp?sessionKey={key}")
        if "login.asp" in (probe.url or "") or 'name="login"' in (probe.text or ""):
            raise RuntimeError(
                "Login fallido: el router no aceptó las credenciales. "
                "Revisa ROUTER_USER y ROUTER_PASS en el .env")
        self.session_key = key
        return key

    def _extract_key(self, r: requests.Response):
        for resp in [r, *r.history]:
            for url in (resp.url or "", resp.headers.get("Location", "")):
                m = re.search(r"sessionKey=(\d+)", url)
                if m:
                    return m.group(1)
        m = re.search(r"sessionKey[\"']?\s*[:=]\s*[\"']?(\d+)", r.text or "")
        if m:
            return m.group(1)
        return None

    def _go(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{self.base}{path}{sep}sessionKey={self.session_key}"

    # ---------- filtro MAC ----------
    def _input_val(self, html: str, name: str) -> str:
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), html)
        if not m:
            m = re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(name), html)
        return m.group(1) if m else ""

    def get_filters(self) -> tuple:
        """Devuelve ([(nombre, mac)], page_key) de la lista de filtrado."""
        url = self._go("/Wifi_MAC_Filter.asp?m=54")
        r = self._req("GET", url)
        r.raise_for_status()
        html = r.text
        page_key = self._page_key(html) or self.session_key
        idxs = sorted({int(m.group(1))
                       for m in re.finditer(r'name="Wifi_Filter_name_(\d+)"', html)})
        entries = []
        for i in idxs:
            name = self._input_val(html, f"Wifi_Filter_name_{i}")
            octs = [self._input_val(html, f"mac_{n:02d}_{i}") for n in range(1, 7)]
            if any(octs):
                mac = norm_mac(":".join(octs))
                entries.append((name.strip() or mac, mac))
        return entries, page_key

    def set_filters(self, entries: list, page_key: str = None) -> bool:
        """Reescribe la lista completa en modo DENEGAR. entries=[(nombre, mac)]."""
        key = page_key or self.session_key
        data = {
            "ResetApply": "0",
            "WifiMACFilteringEnable": "1",
            "WifiMACFilteringDeny": "1",
            "WifiMACNumFilters": str(len(entries)),
        }
        for i, (name, mac) in enumerate(entries):
            octs = norm_mac(mac).split(":")
            data[f"Wifi_Filter_name_{i}"] = name or mac
            for n, o in enumerate(octs, 1):
                data[f"mac_{n:02d}_{i}"] = o
        url = f"{self.base}/goform/Wifi_MAC_Filter?sessionKey={key}"
        r = self._req("POST", url, data=data, allow_redirects=True,
                      headers={"Referer": self._go("/Wifi_MAC_Filter.asp?m=54")})
        r.raise_for_status()
        return True


# ---------- descubrimiento de dispositivos en la LAN ----------
def scan_devices(host: str) -> dict:
    """Ping sweep rápido + tabla ARP -> {mac: (ip, hostname)} de equipos visibles."""
    import socket
    base = host.rsplit(".", 1)[0]
    ping_base = (["ping", "-n", "1", "-w", "400"] if os.name == "nt"
                 else ["ping", "-c", "1", "-W", "1"])

    def _ping(i):
        try:
            subprocess.run(ping_base + [f"{base}.{i}"],
                           capture_output=True, timeout=6)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=64) as ex:
        list(ex.map(_ping, range(1, 255)))

    try:
        out = subprocess.run(["arp", "-a"], capture_output=True,
                             text=True, timeout=15).stdout
    except Exception:
        return {}
    devices = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F\-:]{17})\s+\w+", line)
        if m and m.group(1).startswith(base + "."):
            mac = norm_mac(m.group(2))
            if mac and not mac.startswith("FF:FF"):
                ip = m.group(1)
                hostname = ""
                try:
                    hostname = socket.gethostbyaddr(ip)[0].split(".")[0]
                except Exception:
                    pass
                devices[mac] = (ip, hostname)
    return devices
