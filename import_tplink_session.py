"""Guarda la sesion del TP-Link (de la consola del navegador) para la app."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import save_tplink_session, tp  # noqa: E402

print("Pega los valores de la consola del navegador (F12) con sesion iniciada:")
print("  localStorage.getItem('encryptorAES') etc., y el token de la URL.\n")
session_id = input("sessionId (token de la URL): ").strip()
aes = input("encryptorAES: ").strip()
seq = input("encryptorSeq: ").strip()
hash_hex = input("encryptorHash: ").strip()
rsa = input("encryptorRsa: ").strip()

save_tplink_session(session_id, aes, seq, hash_hex, rsa)
f = tp().get_mac_filter()
print(f"\nOK sesion guardada. Filtro: {'ON' if f['enabled'] else 'OFF'},",
      f["rule"], "-", len(f["entries"]), "entradas")
for e in f["entries"]:
    print("  ", e["mac"], "->", "bloqueada" if e["enabled"] else "permitida")
