"""Test alta/baja de entrada en el filtro MAC."""
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()
from tplink import TPLinkWeb

HOST = os.getenv("TPLINK_HOST", "192.168.0.2")
FAKE = "AA-BB-CC-DD-EE-FF"

session_id = input("sessionId: ").strip()
aes = input("encryptorAES: ").strip()
seq = input("encryptorSeq: ").strip()
hash_hex = input("encryptorHash: ").strip()
rsa = input("encryptorRsa: ").strip()

tp = TPLinkWeb(HOST)
tp.import_browser_session(session_id, aes, seq, hash_hex, rsa)

f = tp.set_mac_block(FAKE, block=True, desc="prueba")
print("TRAS alta:", [(e["mac"], e["enabled"]) for e in f["entries"]])

f = tp.set_mac_block(FAKE, block=False)
print("TRAS baja:", [(e["mac"], e["enabled"]) for e in f["entries"]])
ok = not any(e["mac"] == FAKE for e in f["entries"])
print("OK alta/baja funciona" if ok else "FALLO")
