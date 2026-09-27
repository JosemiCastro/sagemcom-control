"""Importa una sesion del navegador y vuelca la pagina del filtro MAC."""
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
from tplink import TPLinkWeb

HOST = os.getenv("TPLINK_HOST", "192.168.0.2")

print("Pega los valores de la consola del navegador (sin comillas):")
session_id = input("sessionId (token de la URL): ").strip()
aes = input("encryptorAES: ").strip()
seq = input("encryptorSeq: ").strip()
hash_hex = input("encryptorHash: ").strip()
rsa = input("encryptorRsa: ").strip()

tp = TPLinkWeb(HOST)
tp.import_browser_session(session_id, aes, seq, hash_hex, rsa)
print("OK sesion importada")

html = tp.get_page("WlanMacFilterRpm.htm")
print("pagina:", len(html), "bytes")
open("/tmp/wlanmacfilter.htm", "w", encoding="utf-8", errors="replace").write(html)

varlist = tp.encrypted_vars(html)
for name, val in varlist.items():
    print(f"--- {name} ---")
    print(val[:3000])
    print()
