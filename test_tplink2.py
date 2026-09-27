"""Prueba el login cifrado del TP-Link y vuelca la pagina del filtro MAC."""
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
from tplink import TPLinkWeb

HOST = os.getenv("TPLINK_HOST", "192.168.0.2")
USER = os.getenv("TPLINK_USER", "admin")
PASSWORD = os.getenv("TPLINK_PASS", "admin")

tp = TPLinkWeb(HOST, USER, PASSWORD)
try:
    tp.login()
except RuntimeError as e:
    print("ERROR:", e)
    sys.exit(1)
print("OK login, session:", tp.session_id)

html = tp.get_page("WlanMacFilterRpm.htm")
print("pagina:", len(html), "bytes")
varlist = tp.encrypted_vars(html)
for name, val in varlist.items():
    print(f"--- {name} ---")
    print(val[:2000])
    print()
