"""Descubre en qué parámetro del Sagemcom se puede bloquear por MAC.

Uso:  python discover.py
Lee la config de .env e imprime ramas candidatas del modelo de datos.
"""
import asyncio
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

from sagemcom_api.client import SagemcomClient  # noqa: E402
from sagemcom_api.enums import EncryptionMethod  # noqa: E402

HOST = os.getenv("ROUTER_HOST", "192.168.0.1")
USER = os.getenv("ROUTER_USER", "user")
PASSWORD = os.getenv("ROUTER_PASS", "")
ENC = os.getenv("ROUTER_ENCRYPTION", "AUTO").upper()

KEYWORDS = re.compile(r"parental|macfilter|mac.?filter|block|access.?control|denylist|blacklist",
                      re.IGNORECASE)

# Ramas que merece la pena inspeccionar en busca del control de acceso
BRANCHES = [
    "Device.WiFi",
    "Device.X_SAGEMCOM",
    "Device.Services",
    "Device.Firewall",
    "Device.Hosts",
]


def find_candidates(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if KEYWORDS.search(p) or (isinstance(v, str) and KEYWORDS.search(v)):
                hits.append(p)
            hits += find_candidates(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:25]):
            hits += find_candidates(v, f"{path}.{i}")
    return hits


async def main():
    if not PASSWORD or PASSWORD.startswith("pon_aqui"):
        print("ERROR: pon tu ROUTER_PASS en el .env primero.")
        return

    enc = None if ENC == "AUTO" else EncryptionMethod[ENC]
    async with SagemcomClient(HOST, USER, PASSWORD, enc) as client:
        if enc is None:
            enc = await client.get_encryption_method()
            print(f"Método de cifrado detectado: {enc.name}\n")
            # re-login con el método detectado ya lo hace el cliente solo
        await client.login()
        info = await client.get_device_info()
        print(f"Router: {info.model_name} (id {info.id})\n")

        print("== Dispositivos conectados ==")
        for d in await client.get_hosts():
            if d.active:
                print(f"  {d.mac or '?':17}  {d.ip or '?':15}  {d.name}")

        print("\n== Buscando parámetros de bloqueo/parental/MAC-filter ==")
        seen = set()
        for branch in BRANCHES:
            try:
                data = await client.get_value_by_xpath(branch)
            except Exception as e:  # rama inexistente en este firmware
                print(f"  ({branch}: no disponible)")
                continue
            for hit in find_candidates(data, branch):
                if hit not in seen:
                    seen.add(hit)
                    print(f"  CANDIDATO: {hit}")

        print(
            "\nCopia el XPATH del parámetro que contenga la lista de MACs\n"
            "denegadas (o el flag de bloqueo) en BLOCK_LIST_XPATH dentro del .env.\n"
            "Si ninguno es escribible, el router no permite bloqueo por API."
        )


if __name__ == "__main__":
    asyncio.run(main())
