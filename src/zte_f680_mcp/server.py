# -*- coding: utf-8 -*-
"""MCP Server para gestionar NAT/port forwarding en router ZTE F680."""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
import re
import socket
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ---------------------------------------------------------------------------
# Configuracion (desde .env o variables de entorno)
# ---------------------------------------------------------------------------
ZTE_HOST: str = os.getenv("ZTE_HOST", "192.168.1.1")
ZTE_USER: str = os.getenv("ZTE_USER", "1234")
ZTE_PASSWORD: str = os.getenv("ZTE_PASSWORD", "")

FORM_URL = "getpage.gch?pid=1002&nextpage=app_virtual_conf_t.gch"
SESSION_TIMEOUT: float = 45.0

# Estado global
_http_client: httpx.AsyncClient | None = None
_session_valid: bool = False
_last_request_time: float = 0.0


# ---------------------------------------------------------------------------
# Utilidades de parseo
# ---------------------------------------------------------------------------
def _decode_hex_escapes(s: str) -> str:
    """Reemplaza \\x2e -> '.', \\x3a -> ':', etc."""
    return re.sub(
        r"\\x([0-9a-fA-F]{2})",
        lambda m: chr(int(m.group(1), 16)),
        s,
    )


def _parse_rules(html: str) -> list[dict[str, str]]:
    """Extrae reglas de port forwarding del HTML de app_virtual_conf_t.gch."""
    pat = re.compile(r"Transfer_meaning\('(\w+)'\s*,\s*'([^']*)'\)")
    rows: dict[int, dict[str, str]] = {}
    for m in pat.finditer(html):
        full_name = m.group(1)
        raw_value = m.group(2)
        m2 = re.match(r"^(.*?)(\d+)$", full_name)
        if not m2:
            continue
        field_name = m2.group(1)
        row_index = int(m2.group(2))
        value = _decode_hex_escapes(raw_value)
        if row_index not in rows:
            rows[row_index] = {}
        rows[row_index][field_name] = value
    return [rows[i] for i in sorted(rows.keys()) if "Name" in rows.get(i, {})]


def _extract_session_token(html: str) -> str | None:
    """Extrae el _SESSION_TOKEN anti-CSRF de la pagina."""
    m = re.search(r'session_token\s*=\s*"(\d+)"', html)
    return m.group(1) if m else None


def _format_rule(i: int, rule: dict[str, str]) -> str:
    """Formatea una regla para mostrar."""
    proto_map = {"0": "TCP+UDP", "1": "UDP", "2": "TCP"}
    proto = proto_map.get(rule.get("Protocol", ""), "?")
    enabled = "ON" if rule.get("Enable") == "1" else "OFF"
    return (
        f"[{i}] {rule.get('Name', '?'):15s} | {proto:7s} | "
        f":{rule.get('MinExtPort', '?')}-{rule.get('MaxExtPort', '?')} -> "
        f"{rule.get('InternalHost', '?')}:"
        f"{rule.get('MinIntPort', '?')}-{rule.get('MaxIntPort', '?')} | "
        f"{enabled}"
    )


def _check_response_error(html: str) -> str | None:
    """Busca errores en la respuesta del router. Retorna msg o None."""
    errors = re.findall(
        r"Transfer_meaning\('IF_ERRORSTR'\s*,\s*'([^']*)'\)", html
    )
    for err in errors:
        val = _decode_hex_escapes(err)
        if val and val != "SUCC":
            return val
    return None


def _get_local_ip_for(target_host: str) -> str | None:
    """Devuelve la IP del interfaz que enrutaria hacia target_host.

    Usa el truco UDP: abre un socket SOCK_DGRAM y hace connect() contra
    target_host. connect() en UDP es solo bind local (no envia paquetes),
    pero fuerza al SO a elegir el interfaz que se usaria para alcanzar
    esa IP. getsockname() devuelve entonces la IP local asociada.

    Funciona igual en Linux, Windows y macOS. En hosts multi-homed
    (varias IPs en varias subredes) devuelve la IP del interfaz correcto
    para el router configurado.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(1.0)
            s.connect((target_host, 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Autenticacion y sesion
# ---------------------------------------------------------------------------
async def _login(client: httpx.AsyncClient) -> bool:
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
                f"ZTE: bloqueado por intentos fallidos, esperando {lock_time + 2}s...",
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


async def _ensure_session() -> httpx.AsyncClient:
    """Retorna un cliente HTTP autenticado, re-logueando si es necesario."""
    global _http_client, _session_valid, _last_request_time

    now = time.monotonic()

    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        )
        _session_valid = False

    if not _session_valid or (now - _last_request_time) > SESSION_TIMEOUT:
        ok = await _login(_http_client)
        if not ok:
            raise RuntimeError(
                f"Login fallido en {ZTE_HOST}. "
                "Verifica ZTE_USER/ZTE_PASSWORD en .env"
            )
        _session_valid = True
        print(f"ZTE: sesion iniciada en {ZTE_HOST}", file=sys.stderr)

    _last_request_time = now
    return _http_client


async def _fetch_port_fwd_page() -> tuple[str, str | None]:
    """Carga la pagina de port forwarding. Retorna (html, session_token)."""
    client = await _ensure_session()
    resp = await client.get(f"http://{ZTE_HOST}/{FORM_URL}")

    if len(resp.text) < 1000:
        global _session_valid
        _session_valid = False
        client = await _ensure_session()
        resp = await client.get(f"http://{ZTE_HOST}/{FORM_URL}")

    token = _extract_session_token(resp.text)
    return resp.text, token


async def _post_form(form_data: dict[str, str]) -> str:
    """Envia POST al formulario de port forwarding. Retorna HTML respuesta."""
    client = await _ensure_session()
    resp = await client.post(
        f"http://{ZTE_HOST}/{FORM_URL}", data=form_data
    )
    return resp.text


async def _create_port_forward(
    name: str,
    protocol: str,
    ext_start: int,
    ext_end: int,
    internal_host: str,
    int_start: int,
    int_end: int,
) -> str:
    """Crea una regla de port forwarding. Helper compartido por los tools
    `zte_add_port_forward` (control total) y `zte_open_port` (flujo rapido).

    Retorna un string con el resultado y la lista actualizada de reglas,
    o un mensaje de error.
    """
    html, token = await _fetch_port_fwd_page()
    if not token:
        return "Error: no se pudo obtener el token de sesion."

    proto_map = {"TCP+UDP": "0", "UDP": "1", "TCP": "2"}
    proto_code = proto_map.get(protocol.upper(), "0")

    form_data = {
        "_SESSION_TOKEN": token,
        "IF_ACTION": "new",
        "IF_INDEX": "-1",
        "Enable": "1",
        "Name": name,
        "Protocol": proto_code,
        "WANCViewName": "IGD.WD1.WCD1.WCIP1",
        "MinExtPort": str(ext_start),
        "MaxExtPort": str(ext_end),
        "InternalHost": internal_host,
        "MinIntPort": str(int_start),
        "MaxIntPort": str(int_end),
        "MinRemoteHost": "0.0.0.0",
        "MaxRemoteHost": "0.0.0.0",
        "MacEnable": "0",
        "InternalMacHost": "NULL",
        "Description": "",
        "LeaseDuration": "NULL",
        "PortMappCreator": "NULL",
        "ViewName": "NULL",
        "WANCName": "NULL",
    }

    resp_html = await _post_form(form_data)
    err = _check_response_error(resp_html)
    if err:
        return f"Error del router: {err}"

    html2, _ = await _fetch_port_fwd_page()
    rules = _parse_rules(html2)
    added = any(r.get("Name") == name for r in rules)

    lines = [f"{'Regla anadida.' if added else 'No se pudo verificar.'}\n"]
    lines.extend(_format_rule(i, r) for i, r in enumerate(rules))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Gestiona el ciclo de vida de la conexion HTTP al ZTE."""
    global _http_client, _session_valid
    try:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        )
        ok = await _login(_http_client)
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

    yield

    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        _session_valid = False
        print("ZTE F680: sesion cerrada.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Servidor MCP
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="ZTE-F680",
    instructions=(
        "Servidor MCP para gestionar NAT/port forwarding en un router "
        "ZTE ZXHN F680 (GPON ONT). Permite listar, anadir, modificar y "
        "borrar reglas de redireccion de puertos.\n"
        "\n"
        "FLUJO CONVERSACIONAL cuando el usuario pide 'abre el puerto X':\n"
        "  1. Llama a zte_get_local_ip para obtener la IP local sugerida "
        "(la del host que corre el MCP, en la subred del router).\n"
        "  2. Pregunta al usuario: 'Redirijo el puerto X a <IP_local>:X? "
        "(si / no, puerto interno distinto / no, otra IP)'.\n"
        "  3. Si confirma el default: llama a zte_open_port(port=X).\n"
        "  4. Si pide otro puerto interno: zte_open_port(port=X, "
        "internal_port=Y).\n"
        "  5. Si pide otra IP: zte_open_port(port=X, internal_host='Z.Z.Z.Z').\n"
        "  6. Si necesita un rango de puertos o control total: "
        "zte_add_port_forward con todos los parametros.\n"
        "\n"
        "Nunca inventes IPs internas y nunca abras puertos sin confirmar "
        "el destino con el usuario.\n"
        "\n"
        "Usa zte_run_page para obtener datos de cualquier otra pagina del "
        "router (DHCP, DMZ, WiFi, firewall, etc)."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool(
    annotations={
        "title": "Listar reglas de port forwarding",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_port_forwards() -> str:
    """Lista todas las reglas NAT/port forwarding configuradas."""
    try:
        html, _ = await _fetch_port_fwd_page()
        rules = _parse_rules(html)
        if not rules:
            return "No hay reglas de port forwarding configuradas."
        lines = [_format_rule(i, r) for i, r in enumerate(rules)]
        lines.append(f"\nTotal: {len(rules)} reglas")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "IP local detectada (subred del router)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_local_ip() -> str:
    """Detecta la IP local del host en la subred del router.

    En hosts multi-homed devuelve la IP del interfaz que enrutaria hacia
    ZTE_HOST, que es la que hay que usar como destino en port forwarding.
    Funciona en Linux, Windows y macOS sin dependencias externas.

    Usa este tool ANTES de abrir un puerto para sugerir al usuario la IP
    por defecto. Ejemplo de flujo:
      1. Usuario: "abre el puerto 8080"
      2. zte_get_local_ip() -> "192.168.1.133"
      3. Preguntar: "Redirijo 8080 -> 192.168.1.133:8080?"
      4. Si confirma: zte_open_port(port=8080)
    """
    ip = _get_local_ip_for(ZTE_HOST)
    if ip is None:
        return (
            f"No se pudo detectar la IP local hacia {ZTE_HOST}. "
            "Verifica conectividad con el router."
        )
    return ip


@mcp.tool(
    annotations={
        "title": "Abrir puerto (rapido, con defaults)",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def zte_open_port(
    port: int,
    protocol: str = "TCP+UDP",
    internal_host: str | None = None,
    internal_port: int | None = None,
    name: str | None = None,
) -> str:
    """Abre un puerto con defaults sensatos. Flujo conversacional recomendado.

    Args:
        port: Puerto externo a abrir.
        protocol: "TCP", "UDP" o "TCP+UDP" (default).
        internal_host: IP interna destino. Si None o "auto",
            se detecta automaticamente la IP local del host en la subred
            del router (llamando al helper equivalente a zte_get_local_ip).
        internal_port: Puerto interno. Si None, se usa el mismo que `port`.
        name: Nombre descriptivo. Si None, se genera como "port_<port>".

    Para rangos de puertos o control total, usa `zte_add_port_forward`.

    Flujo recomendado:
        1. Pide al usuario el puerto a abrir.
        2. Llama a zte_get_local_ip y propon la IP detectada.
        3. Confirma con el usuario antes de abrir (destino IP y puerto interno).
        4. Llama a zte_open_port con los valores acordados.
    """
    try:
        if internal_host is None or internal_host.lower() == "auto":
            detected = _get_local_ip_for(ZTE_HOST)
            if detected is None:
                return (
                    f"Error: no se pudo detectar la IP local hacia {ZTE_HOST}. "
                    "Pasa internal_host explicitamente."
                )
            internal_host = detected

        if internal_port is None:
            internal_port = port

        if name is None:
            name = f"port_{port}"

        return await _create_port_forward(
            name=name,
            protocol=protocol,
            ext_start=port,
            ext_end=port,
            internal_host=internal_host,
            int_start=internal_port,
            int_end=internal_port,
        )
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Anadir regla de port forwarding",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def zte_add_port_forward(
    name: str,
    protocol: str,
    external_port_start: int,
    external_port_end: int,
    internal_host: str,
    internal_port_start: int,
    internal_port_end: int,
) -> str:
    """Anade una regla de port forwarding con control total.

    Para el caso comun (un solo puerto -> IP local en el mismo puerto),
    considera usar `zte_open_port`, que tiene defaults inteligentes.

    Args:
        name: Nombre descriptivo de la regla (max 32 chars).
        protocol: "TCP", "UDP" o "TCP+UDP".
        external_port_start: Puerto externo inicial.
        external_port_end: Puerto externo final (igual que start para 1 puerto).
        internal_host: IP interna destino (ej: 192.168.1.100).
        internal_port_start: Puerto interno inicial.
        internal_port_end: Puerto interno final.
    """
    try:
        return await _create_port_forward(
            name=name,
            protocol=protocol,
            ext_start=external_port_start,
            ext_end=external_port_end,
            internal_host=internal_host,
            int_start=internal_port_start,
            int_end=internal_port_end,
        )
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Modificar regla de port forwarding",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def zte_modify_port_forward(
    index: int,
    name: str,
    protocol: str,
    external_port_start: int,
    external_port_end: int,
    internal_host: str,
    internal_port_start: int,
    internal_port_end: int,
) -> str:
    """Modifica una regla de port forwarding existente.

    Args:
        index: Indice de la regla (obtenido con zte_get_port_forwards).
        name: Nuevo nombre de la regla.
        protocol: "TCP", "UDP" o "TCP+UDP".
        external_port_start: Puerto externo inicial.
        external_port_end: Puerto externo final.
        internal_host: IP interna destino.
        internal_port_start: Puerto interno inicial.
        internal_port_end: Puerto interno final.
    """
    try:
        html, token = await _fetch_port_fwd_page()
        if not token:
            return "Error: no se pudo obtener el token de sesion."

        rules = _parse_rules(html)
        if index < 0 or index >= len(rules):
            return f"Error: indice {index} fuera de rango (0-{len(rules) - 1})."

        view_name = rules[index].get("ViewName", "NULL")
        proto_map = {"TCP+UDP": "0", "UDP": "1", "TCP": "2"}
        proto_code = proto_map.get(protocol.upper(), "0")

        html, token = await _fetch_port_fwd_page()
        if not token:
            return "Error: no se pudo obtener el token de sesion."

        form_data = {
            "_SESSION_TOKEN": token,
            "IF_ACTION": "apply",
            "IF_INDEX": str(index),
            "Enable": "1",
            "Name": name,
            "Protocol": proto_code,
            "WANCViewName": "IGD.WD1.WCD1.WCIP1",
            "MinExtPort": str(external_port_start),
            "MaxExtPort": str(external_port_end),
            "InternalHost": internal_host,
            "MinIntPort": str(internal_port_start),
            "MaxIntPort": str(internal_port_end),
            "MinRemoteHost": "0.0.0.0",
            "MaxRemoteHost": "0.0.0.0",
            "MacEnable": "0",
            "InternalMacHost": "NULL",
            "Description": "",
            "LeaseDuration": "NULL",
            "PortMappCreator": "NULL",
            "ViewName": view_name,
            "WANCName": "NULL",
        }

        resp_html = await _post_form(form_data)
        err = _check_response_error(resp_html)
        if err:
            return f"Error del router: {err}"

        html2, _ = await _fetch_port_fwd_page()
        rules = _parse_rules(html2)
        lines = ["Regla modificada.\n"]
        lines.extend(_format_rule(i, r) for i, r in enumerate(rules))
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Borrar regla de port forwarding",
        "readOnlyHint": False,
        "destructiveHint": True,
    }
)
async def zte_delete_port_forward(index: int) -> str:
    """Borra una regla de port forwarding por su indice.

    Args:
        index: Indice de la regla (obtenido con zte_get_port_forwards).
    """
    try:
        html, token = await _fetch_port_fwd_page()
        if not token:
            return "Error: no se pudo obtener el token de sesion."

        rules_before = _parse_rules(html)
        if index < 0 or index >= len(rules_before):
            return f"Error: indice {index} fuera de rango (0-{len(rules_before) - 1})."

        deleted_name = rules_before[index].get("Name", "?")

        form_data = {
            "_SESSION_TOKEN": token,
            "IF_ACTION": "delete",
            "IF_INDEX": str(index),
        }

        resp_html = await _post_form(form_data)
        err = _check_response_error(resp_html)
        if err:
            return f"Error del router: {err}"

        html2, _ = await _fetch_port_fwd_page()
        rules_after = _parse_rules(html2)

        lines = [f"Regla '{deleted_name}' borrada.\n"]
        if rules_after:
            lines.extend(_format_rule(i, r) for i, r in enumerate(rules_after))
        else:
            lines.append("No quedan reglas de port forwarding.")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Obtener pagina ZTE (generico)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    }
)
async def zte_run_page(page_name: str, raw: bool = False) -> str:
    """Obtiene y parsea cualquier pagina del router ZTE.

    Args:
        page_name: Nombre de la pagina (ej: 'app_virtual_conf_t.gch').
        raw: Si True, devuelve HTML crudo. Si False, parsea Transfer_meaning.

    Paginas conocidas:
        - app_virtual_conf_t.gch (port forwarding)
        - app_dmz_conf_t.gch (DMZ)
        - app_upnp_conf_t.gch (UPnP)
        - net_dhcp_dynamic_t.gch (DHCP leases)
        - status_dev_info_t.gch (device info)
        - IPv46_status_wan_if_t.gch (WAN status)
        - net_wlanm_conf1_t.gch (WiFi 2.4GHz)
        - net_wlanm_conf2_t.gch (WiFi 5GHz)
        - sec_firewall_conf_t.gch (firewall)
    """
    try:
        client = await _ensure_session()
        url = f"http://{ZTE_HOST}/getpage.gch?pid=1002&nextpage={page_name}"
        resp = await client.get(url)

        if len(resp.text) < 1000:
            global _session_valid
            _session_valid = False
            client = await _ensure_session()
            resp = await client.get(url)

        if raw:
            return resp.text

        pat = re.compile(r"Transfer_meaning\('(\w+)'\s*,\s*'([^']*)'\)")
        items: list[str] = []
        for m in pat.finditer(resp.text):
            name = m.group(1)
            val = _decode_hex_escapes(m.group(2))
            items.append(f"  {name}: {val}")

        if not items:
            return f"No se encontraron datos Transfer_meaning en {page_name}"

        return f"Pagina: {page_name}\n" + "\n".join(items)
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Entry point for the installed console script `zte-f680-mcp`."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
