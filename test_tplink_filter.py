"""Test de escritura del filtro MAC (reversible: DisAll -> EnAll)."""
import os
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

f = tp.get_mac_filter()
print("INICIAL:", f["enabled"], f["rule"],
      [(e["mac"], e["enabled"]) for e in f["entries"]])

f = tp.mac_filter_action({"Page": 1, "DoAll": "DisAll", "vapIdx": 1})
print("TRAS DisAll:", [(e["mac"], e["enabled"]) for e in f["entries"]])

f = tp.mac_filter_action({"Page": 1, "DoAll": "EnAll", "vapIdx": 1})
print("TRAS EnAll:", [(e["mac"], e["enabled"]) for e in f["entries"]])
print("OK escritura funciona" if all(e["enabled"] for e in f["entries"]) else "FALLO")
