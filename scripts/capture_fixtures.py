# -*- coding: utf-8 -*-
"""Captura HTML crudo de las paginas que usan las tools de Fase 1.

Uso: python scripts/capture_fixtures.py
Requiere .env con ZTE_HOST / ZTE_USER / ZTE_PASSWORD.
"""
import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from zte_f680_mcp.server import _login, ZTE_HOST

PAGES = [
    "status_dev_info_t.gch",
    "IPv46_status_wan_if_t.gch",
    "net_wlanm_secrity1_t.gch",
    "net_wlanm_secrity2_t.gch",
    "net_dhcp_dynamic_t.gch",
    "app_dmz_conf_t.gch",
]
OUT = Path("tests/fixtures")


async def main() -> None:
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        assert await _login(client), "Login fallido. Revisa .env"
        for page in PAGES:
            url = f"http://{ZTE_HOST}/getpage.gch?pid=1002&nextpage={page}"
            resp = await client.get(url)
            dest = OUT / page.replace(".gch", ".html")
            dest.write_text(resp.text, encoding="utf-8")
            print(f"OK  {dest}  ({len(resp.text)} chars)")


if __name__ == "__main__":
    asyncio.run(main())
