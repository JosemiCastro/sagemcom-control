"""Cliente para TP-Link TL-WR940N v6.

La web de este firmware cifra todo (login y formularios):
  AES-128-CBC/PKCS7 para los datos  +  RSA-512/PKCS#1 v1.5 para la firma.
Esquema revertido de tpEncrypt.js / encrypt.js / login.htm del propio router.
"""
import base64
import hashlib
import json
import random
import re
import time
import urllib.parse

import requests
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA


class TPLinkWeb:
    def __init__(self, host, user="admin", password="admin"):
        self.host = host
        self.user = user
        self.password = password
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self.s.headers["Referer"] = f"http://{host}/"
        self.s.headers["Origin"] = f"http://{host}"
        self.aes_key = None
        self.aes_iv = None
        self.hash = None
        self.seq = None
        self.rsa = None
        self.session_id = None

    # ---------------- crypto ----------------
    def _gen_aes_key(self):
        base = str(int(time.time() * 1000)) + str(random.random() * 1000000000)
        self.aes_key = base[:16]
        base = str(int(time.time() * 1000)) + str(random.random() * 1000000000)
        self.aes_iv = base[:16]

    def _aes_encrypt(self, plaintext: str) -> str:
        data = plaintext.encode("utf-8")
        pad = 16 - (len(data) % 16)
        data += bytes([pad]) * pad
        c = AES.new(self.aes_key.encode(), AES.MODE_CBC, self.aes_iv.encode())
        return base64.b64encode(c.encrypt(data)).decode()

    def _aes_decrypt(self, b64: str) -> str:
        c = AES.new(self.aes_key.encode(), AES.MODE_CBC, self.aes_iv.encode())
        data = c.decrypt(base64.b64decode(b64))
        return data[:-data[-1]].decode("utf-8")

    def _rsa_sign(self, s: str) -> str:
        cipher = PKCS1_v1_5.new(self.rsa)
        out = []
        for i in range(0, len(s), 53):
            chunk = s[i:i + 53].encode()
            out.append(cipher.encrypt(chunk).hex().rjust(128, "0"))
        return "".join(out)

    def _data_encrypt(self, data: str, is_login=False):
        enc = self._aes_encrypt(data)
        seq = self.seq + len(enc)
        if is_login:
            s = f"key={self.aes_key}&iv={self.aes_iv}&h={self.hash}&s={seq}"
        else:
            s = f"h={self.hash}&s={seq}"
        return {"sign": self._rsa_sign(s), "data": enc}

    # ---------------- sesion ----------------
    def login(self):
        # 0. Cargar la pagina de login como el navegador (puede fijar cookies)
        self.s.get(f"http://{self.host}/", timeout=10)
        r = self.s.get(f"http://{self.host}/login/getRsa.json", timeout=10)
        try:
            info = r.json()
        except Exception:
            raise RuntimeError(
                f"getRsa.json no devolvio JSON: HTTP {r.status_code}, "
                f"Content-Type={r.headers.get('Content-Type')}, "
                f"cuerpo={r.text[:200]!r}"
            )
        nn, mm = info["rsa"]["nn"], info["rsa"]["mm"]
        self.seq = int(info["seq"])
        self.rsa = RSA.construct((int(nn, 16), int(mm, 16)))
        self._gen_aes_key()
        self.hash = hashlib.md5((self.user + self.password).encode()).hexdigest()
        data = json.dumps({"name": self.user, "password": self.password},
                          separators=(",", ":"))
        payload = self._data_encrypt(data, is_login=True)
        body = "JSONDATA: " + json.dumps(payload, separators=(",", ":")) + "\n"
        r = self.s.post(
            f"http://{self.host}/login/login.json",
            data=body,
            headers={"Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        ret = None
        try:
            ret = r.json()
        except Exception:
            pass
        if not isinstance(ret, dict) or not ret.get("valid"):
            raise RuntimeError(
                f"login TP-Link fallido: HTTP {r.status_code}, "
                f"cuerpo={r.text[:200]!r}"
            )
        self.session_id = ret["sessionId"]
        self.s.cookies.set("Authorization", str(self.seq),
                           domain=self.host, path="/")
        return True

    def _url(self, page):
        return f"http://{self.host}/{self.session_id}/userRpm/{page}"

    def import_browser_session(self, session_id, aes_string, seq, hash_hex,
                               rsa_string):
        """Reutiliza una sesion iniciada en el navegador.

        Valores desde devtools (con la sesion iniciada):
          session_id = token de la URL (ej. AYQVHBCAPGABTWSC)
          aes_string = localStorage 'encryptorAES'  ("key=...&iv=...")
          seq        = localStorage 'encryptorSeq'
          hash_hex   = localStorage 'encryptorHash' (MD5 simple, tal cual)
          rsa_string = localStorage 'encryptorRsa'  ("nn=...&ee=...")
        """
        self.session_id = session_id
        self.aes_key = aes_string.split("&")[0].split("=", 1)[1]
        self.aes_iv = aes_string.split("&")[1].split("=", 1)[1]
        self.seq = int(seq)
        self.hash = hash_hex
        nn = rsa_string.split("&")[0].split("=", 1)[1]
        ee = rsa_string.split("&")[1].split("=", 1)[1]
        self.rsa = RSA.construct((int(nn, 16), int(ee, 16)))
        self.s.cookies.set("Authorization", str(self.seq),
                           domain=self.host, path="/")
        return True

    def get_page(self, page):
        r = self.s.get(self._url(page), timeout=15)
        r.raise_for_status()
        return r.text

    def post_form(self, page, fields: dict):
        """Envia un formulario cifrado como lo hace la web (multipart, campo data)."""
        plain = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}"
            for k, v in fields.items()
        )
        payload = self._data_encrypt(plain)
        r = self.s.post(self._url(page),
                        files={"data": (None, json.dumps(payload,
                                                         separators=(",", ":")))},
                        timeout=15)
        return r

    def _parse_array(self, text):
        """Convierte 'var x = new Array(1,"a",...);' en lista Python."""
        m = re.search(r"new Array\((.*)\)", text, re.S)
        if not m:
            return text
        items = []
        for part in m.group(1).split(","):
            part = part.strip()
            if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
                items.append(part[1:-1])
            elif part.lstrip("-").isdigit():
                items.append(int(part))
            else:
                try:
                    items.append(float(part))
                except ValueError:
                    items.append(part)
        return items

    def encrypted_vars(self, html):
        """Extrae y descifra las variables name=encryptedData de una pagina."""
        out = {}
        for m in re.finditer(
            r'data-name="([^"]+)"[^>]*>\s*var\s+\1\s*=\s*"([^"]*)"',
            html,
        ):
            name, enc = m.group(1), m.group(2)
            try:
                out[name] = self._parse_array(self._aes_decrypt(enc))
            except Exception as e:  # noqa: BLE001
                out[name] = f"<error: {e}>"
        return out

    # ---------- Filtro MAC wifi ----------
    def get_mac_filter(self):
        """Lee el estado del filtro MAC wifi.

        Devuelve dict(enabled: bool, rule: 'deny'|'allow', entries: [...]).
        Cada entry: dict(id, mac, enabled, desc).
        """
        html = self.get_page("WlanMacFilterRpm.htm")
        varlist = self.encrypted_vars(html)
        para = varlist.get("wlanFilterPara", [])
        raw = varlist.get("wlanFilterList", [])
        stride = para[6] if len(para) > 6 else 5
        n = para[5] if len(para) > 5 else 0
        entries = []
        for i in range(n):
            row = i * stride
            if row + 4 >= len(raw):
                break
            entries.append({
                "id": i,
                "mac": str(raw[row]).upper(),
                "enabled": str(raw[row + 1]) == "1",
                "desc": str(raw[row + 4]),
            })
        return {
            "enabled": bool(para and para[0] == 1),
            "rule": "deny" if not para or para[1] == 0 else "allow",
            "entries": entries,
        }

    def mac_filter_action(self, query):
        """Ejecuta una accion del filtro (Del, DoAll, Enfilter...).

        query: ej. "Page=1&Del=0&vapIdx=1". Devuelve el filtro actualizado.
        """
        self.post_encrypted("WlanMacFilterRpm.htm", query)
        return self.get_mac_filter()

    def set_mac_block(self, mac, block=True, desc=""):
        """Bloquea (block=True) o desbloquea (block=False) una MAC."""
        mac = mac.upper().replace(":", "-")
        f = self.get_mac_filter()
        entry = next((e for e in f["entries"] if e["mac"] == mac), None)
        if entry:
            if entry["enabled"] == block:
                return f  # ya esta como se pide
            self.mac_filter_action(f"Page=1&Del={entry['id']}&vapIdx=1")
            if block:
                return self.add_mac_entry(mac, desc or entry["desc"])
            return self.get_mac_filter()
        if block:
            return self.add_mac_entry(mac, desc)
        return f

    def add_mac_entry(self, mac, desc=""):
        """Crea una entrada en el filtro (habilitada)."""
        mac = mac.upper().replace(":", "-")
        html = self.post_encrypted(
            "WlanMacFilterRpm.htm", "Add=Add&Page=1&vapIdx=1").text
        names = re.findall(r'name="([^"]+)"', html)
        fields = {}
        for n in dict.fromkeys(names):
            m = re.search(
                r'name="' + re.escape(n) + r'"[^>]*value="([^"]*)"', html)
            fields[n] = m.group(1) if m else ""
        for k in fields:
            kl = k.lower()
            if "mac" in kl:
                fields[k] = mac
            elif "desc" in kl:
                fields[k] = desc
            elif "status" in kl or "type" in kl or "enable" in kl:
                fields[k] = "1"
        if "Changed" in fields:
            fields["Changed"] = "1"
        if "Save" not in fields:
            fields["Save"] = "Save"
        query = urllib.parse.urlencode(fields)
        self.post_encrypted("WlanMacFilterRpm.htm", query)
        return self.get_mac_filter()
