# -*- coding: utf-8 -*-
"""Sesion HTTP contra el router ZTE F680.

Maneja login (SHA256 + tokens dinamicos), cookies, re-login automatico
cuando la sesion expira (~45s idle). Sin conocimiento de campos de
negocio; solo mueve HTML.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import re
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

ZTE_HOST: str = os.getenv("ZTE_HOST", "192.168.1.1")
ZTE_USER: str = os.getenv("ZTE_USER", "1234")
ZTE_PASSWORD: str = os.getenv("ZTE_PASSWORD", "")

SESSION_TIMEOUT: float = 45.0
PORT_FWD_URL = "getpage.gch?pid=1002&nextpage=app_virtual_conf_t.gch"

_http_client: httpx.AsyncClient | None = None
_session_valid: bool = False
_last_request_time: float = 0.0


async def login(client: httpx.AsyncClient) -> bool:
    """Autentica contra el ZTE F680. Retorna True si exito."""
    try:
        resp = await client.get(f"http://{ZTE_HOST}/")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        print(f"ZTE: error conectando a {ZTE_HOST} ({exc})", file=sys.stderr)
        return False

    html = resp.text
    mt = re.search(r'Frm_Logintoken",\s*"(\d+)"', html)
    mc = re.search(r'Frm_Loginchecktoken",\s*"(\d+)"', html)
    if not mt or not mc:
        print("ZTE: no se encontraron tokens de login", file=sys.stderr)
        return False

    lock_match = re.search(
        r"Math\.min\(60,\s*(\d+)\s*\+\s*60\s*-\s*(\d+)\)", html
    )
    if lock_match:
        val1, val2 = int(lock_match.group(1)), int(lock_match.group(2))
        lock_time = min(60, val1 + 60 - val2)
        if lock_time > 0:
            print(
                f"ZTE: bloqueado por intentos fallidos, esperando "
                f"{lock_time + 2}s...",
                file=sys.stderr,
            )
            await asyncio.sleep(lock_time + 2)
            resp = await client.get(f"http://{ZTE_HOST}/")
            html = resp.text
            mt = re.search(r'Frm_Logintoken",\s*"(\d+)"', html)
            mc = re.search(r'Frm_Loginchecktoken",\s*"(\d+)"', html)
            if not mt or not mc:
                return False

    rnd = random.randint(10000000, 99999999)
    pw_hash = hashlib.sha256(
        (ZTE_PASSWORD + str(rnd)).encode("utf-8")
    ).hexdigest()

    form_data = {
        "action": "login",
        "Username": ZTE_USER,
        "Password": pw_hash,
        "Frm_Logintoken": mt.group(1),
        "UserRandomNum": str(rnd),
        "port": "",
        "Frm_Loginchecktoken": mc.group(1),
    }
    await client.post(f"http://{ZTE_HOST}/", data=form_data)
    return "SID" in dict(client.cookies)


async def ensure_session() -> httpx.AsyncClient:
    """Retorna un cliente HTTP autenticado, re-logueando si hace falta."""
    global _http_client, _session_valid, _last_request_time

    now = time.monotonic()

    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        )
        _session_valid = False

    if not _session_valid or (now - _last_request_time) > SESSION_TIMEOUT:
        ok = await login(_http_client)
        if not ok:
            raise RuntimeError(
                f"Login fallido en {ZTE_HOST}. "
                "Verifica ZTE_USER/ZTE_PASSWORD en .env"
            )
        _session_valid = True
        print(f"ZTE: sesion iniciada en {ZTE_HOST}", file=sys.stderr)

    _last_request_time = now
    return _http_client


async def fetch_html(page_name: str) -> str:
    """Descarga el HTML de una pagina del router.

    Args:
        page_name: p.ej. 'status_dev_info_t.gch'.
    """
    client = await ensure_session()
    url = f"http://{ZTE_HOST}/getpage.gch?pid=1002&nextpage={page_name}"
    resp = await client.get(url)

    if len(resp.text) < 1000:
        global _session_valid
        _session_valid = False
        client = await ensure_session()
        resp = await client.get(url)

    return resp.text


async def fetch_port_fwd_page() -> tuple[str, str | None]:
    """Carga la pagina de port forwarding. Retorna (html, session_token).

    Mantenido como API separada por compatibilidad con las tools
    NAT existentes que necesitan el token CSRF.
    """
    html = await fetch_html("app_virtual_conf_t.gch")
    token = _extract_session_token(html)
    return html, token


async def post_port_fwd_form(form_data: dict[str, str]) -> str:
    """Envia POST al formulario de port forwarding. Retorna HTML respuesta."""
    client = await ensure_session()
    resp = await client.post(
        f"http://{ZTE_HOST}/{PORT_FWD_URL}", data=form_data
    )
    return resp.text


def _extract_session_token(html: str) -> str | None:
    m = re.search(r'session_token\s*=\s*"(\d+)"', html)
    return m.group(1) if m else None


async def startup() -> None:
    """Llamar al arrancar el servidor MCP (lifespan)."""
    global _http_client, _session_valid
    try:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        )
        ok = await login(_http_client)
        if ok:
            _session_valid = True
            print(f"ZTE F680: sesion iniciada en {ZTE_HOST}", file=sys.stderr)
        else:
            print(
                f"Aviso: no se pudo iniciar sesion en {ZTE_HOST}. "
                "Se reintentara al ejecutar herramientas.",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"Aviso: error conectando a {ZTE_HOST} ({exc})", file=sys.stderr)


async def shutdown() -> None:
    """Llamar al cerrar el servidor MCP (lifespan)."""
    global _http_client, _session_valid
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        _session_valid = False
        print("ZTE F680: sesion cerrada.", file=sys.stderr)
