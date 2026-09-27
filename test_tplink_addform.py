"""Descarga el formulario de alta del filtro y lo guarda."""
import os
import re
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
from tplink import TPLinkWeb

HOST = os.getenv("TPLINK_HOST", "192.168.0.2")

session_id = input("sessionId: ").strip()
aes = input("encryptorAES: ").strip()
seq = input("encryptorSeq: ").strip()
hash_hex = input("encryptorHash: ").strip()
rsa = input("encryptorRsa: ").strip()

tp = TPLinkWeb(HOST)
tp.import_browser_session(session_id, aes, seq, hash_hex, rsa)

r = tp.post_form("WlanMacFilterRpm.htm",
                 {"Add": "Add", "Page": 1, "vapIdx": 1})
html = r.text
with open("wlanmacadd.htm", "w", encoding="utf-8", errors="replace") as f:
    f.write(html)
print("guardado wlanmacadd.htm", len(html), "bytes")
print("--- inputs ---")
for m in re.finditer(r'<input[^>]*>', html):
    print(m.group(0)[:160])
print("--- selects ---")
for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>',
                     html, re.S):
    print(m.group(1), "->", m.group(2)[:200])
