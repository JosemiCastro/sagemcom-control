"""Test minimo: solo GET getRsa.json (sin POST de login)."""
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
HOST = os.getenv("TPLINK_HOST", "192.168.0.2")

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
s.headers["Referer"] = f"http://{HOST}/"

for i in range(3):
    try:
        r = s.get(f"http://{HOST}/login/getRsa.json", timeout=10)
        print(f"intento {i+1}: HTTP {r.status_code}, {r.headers.get('Content-Type')}, "
              f"cuerpo={r.text[:120]!r}")
    except Exception as e:
        print(f"intento {i+1}: ERROR {type(e).__name__}: {e}")
        break
    time.sleep(3)
