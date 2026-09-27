"""Prueba rapida: ver si el TP-Link acepta la cookie de auth clasica."""
import base64
import os
import requests

HOST = os.getenv("TPLINK_HOST", "192.168.0.2")
USER = os.getenv("TPLINK_USER", "admin")
PASSWORD = os.getenv("TPLINK_PASS", "admin")

s = requests.Session()
token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
r = s.get(f"http://{HOST}/", cookies={"Authorization": f"Basic {token}"}, timeout=10)
print("status:", r.status_code)
txt = r.text
print("parece login:", "password" in txt[:2000].lower() and "userRpm" not in txt[:2000])
print(txt[:400].replace("\n", " "))
