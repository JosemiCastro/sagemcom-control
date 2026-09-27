"""Restaura la entrada E0-9D-31-E7-75-B6 (LolaDeb) en el filtro."""
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

f = tp.set_mac_block("E0-9D-31-E7-75-B6", block=True, desc="LolaDeb")
print("Filtro:", f["enabled"], f["rule"])
for e in f["entries"]:
    print(" ", e["mac"], "enabled:" , e["enabled"], repr(e["desc"]))
