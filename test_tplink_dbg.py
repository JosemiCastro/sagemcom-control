"""Debug detallado del login TP-Link."""
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

r = tp.s.get(f"http://{HOST}/", timeout=10)
print("GET / ->", r.status_code)
print("  cookies:", dict(tp.s.cookies))
print("  headers:", dict(r.headers))

r = tp.s.get(f"http://{HOST}/login/getRsa.json", timeout=10)
print("GET getRsa.json ->", r.status_code)
print("  cuerpo:", r.text)
print("  cookies:", dict(tp.s.cookies))
