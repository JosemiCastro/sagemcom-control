"""Prueba rápida del login web y lectura del filtro MAC.

Uso:  python test_login.py
"""
import os
from dotenv import load_dotenv

load_dotenv()
from router_web import RouterWeb

HOST = os.getenv("ROUTER_HOST", "192.168.0.1")
USER = os.getenv("ROUTER_USER", "user")
PASSWORD = os.getenv("ROUTER_PASS", "")

rw = RouterWeb(HOST, USER, PASSWORD)
key = rw.login()
print("OK login. sessionKey =", key)
entries, page_key = rw.get_filters()
print("page_key =", page_key)
print(f"Filtros actuales ({len(entries)}):")
for name, mac in entries:
    print(f"  - {name}  {mac}")
