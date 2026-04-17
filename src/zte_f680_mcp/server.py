# -*- coding: utf-8 -*-
"""MCP Server para gestionar NAT/port forwarding en router ZTE F680."""

from __future__ import annotations

import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from zte_f680_mcp import http_client
from zte_f680_mcp.parsers import group_by_numeric_suffix, parse_transfer_meaning


# ---------------------------------------------------------------------------
# Helpers NAT (permanecen en server.py porque son logica de negocio)
# ---------------------------------------------------------------------------
def _parse_rules(html: str) -> list[dict[str, str]]:
    """Extrae reglas de port forwarding (usa agrupacion por sufijo numerico)."""
    data = parse_transfer_meaning(html)
    fields = [
        "Name", "Protocol", "Enable", "MinExtPort", "MaxExtPort",
        "InternalHost", "MinIntPort", "MaxIntPort", "ViewName",
    ]
    rows = group_by_numeric_suffix(data, prefixes=fields)
    return [r for r in rows if r.get("Name")]


def _check_response_error(html: str) -> str | None:
    """Busca errores en la respuesta del router. Retorna msg o None."""
    data = parse_transfer_meaning(html)
    val = data.get("IF_ERRORSTR")
    if val and val != "SUCC":
        return val
    return None


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
    html, token = await http_client.fetch_port_fwd_page()
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

    resp_html = await http_client.post_port_fwd_form(form_data)
    err = _check_response_error(resp_html)
    if err:
        return f"Error del router: {err}"

    html2, _ = await http_client.fetch_port_fwd_page()
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
    await http_client.startup()
    yield
    await http_client.shutdown()


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
        html, _ = await http_client.fetch_port_fwd_page()
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
    ip = _get_local_ip_for(http_client.ZTE_HOST)
    if ip is None:
        return (
            f"No se pudo detectar la IP local hacia {http_client.ZTE_HOST}. "
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
            detected = _get_local_ip_for(http_client.ZTE_HOST)
            if detected is None:
                return (
                    f"Error: no se pudo detectar la IP local hacia "
                    f"{http_client.ZTE_HOST}. "
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
        html, token = await http_client.fetch_port_fwd_page()
        if not token:
            return "Error: no se pudo obtener el token de sesion."

        rules = _parse_rules(html)
        if index < 0 or index >= len(rules):
            return f"Error: indice {index} fuera de rango (0-{len(rules) - 1})."

        view_name = rules[index].get("ViewName", "NULL")
        proto_map = {"TCP+UDP": "0", "UDP": "1", "TCP": "2"}
        proto_code = proto_map.get(protocol.upper(), "0")

        html, token = await http_client.fetch_port_fwd_page()
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

        resp_html = await http_client.post_port_fwd_form(form_data)
        err = _check_response_error(resp_html)
        if err:
            return f"Error del router: {err}"

        html2, _ = await http_client.fetch_port_fwd_page()
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
        html, token = await http_client.fetch_port_fwd_page()
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

        resp_html = await http_client.post_port_fwd_form(form_data)
        err = _check_response_error(resp_html)
        if err:
            return f"Error del router: {err}"

        html2, _ = await http_client.fetch_port_fwd_page()
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
        html = await http_client.fetch_html(page_name)

        if raw:
            return html

        data = parse_transfer_meaning(html)
        if not data:
            return f"No se encontraron datos Transfer_meaning en {page_name}"

        items = [f"  {k}: {v}" for k, v in data.items()]
        return f"Pagina: {page_name}\n" + "\n".join(items)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Info del dispositivo ZTE (modelo, firmware, serie)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_device_info() -> str:
    """Devuelve modelo, serie, firmware, hardware, bootloader y chipsets WiFi.

    Lee status_dev_info_t.gch. Esta pagina no incluye uptime, CPU ni RAM
    en el firmware Jazztel; esos datos viven en otras paginas.
    """
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_device_info
        data = await pages.fetch_device_info()
        return format_device_info(data)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Info WiFi (2.4 + 5 GHz)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_wifi_info() -> str:
    """Devuelve SSIDs, canal, estandar, seguridad, clave PSK, BSSID y
    estadisticas de ambas bandas WiFi (2.4 y 5 GHz)."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_wifi_info
        data = await pages.fetch_wifi_info()
        return format_wifi_info(data)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Dispositivos conectados al router (DHCP leases)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_dhcp_leases() -> str:
    """Lista los dispositivos conectados al router: IP, MAC, hostname,
    tipo de conexion (LAN/WiFi) y tiempo de expiracion del lease DHCP."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_dhcp_leases
        data = await pages.fetch_dhcp_leases()
        return format_dhcp_leases(data)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Clientes WiFi asociados (con senal RSSI)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_wifi_clients() -> str:
    """Lista los dispositivos conectados por WiFi con su RSSI (senal),
    banda, modo (11ac/11n) y tasa TX/RX."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_wifi_clients
        data = await pages.fetch_wifi_clients()
        return format_wifi_clients(data)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Estado DMZ",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_dmz() -> str:
    """Devuelve el estado de la zona desmilitarizada (DMZ) y el host interno
    configurado como destino."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_dmz
        data = await pages.fetch_dmz()
        return format_dmz(data)
    except Exception as exc:
        return f"Error: {exc}"


@mcp.tool(
    annotations={
        "title": "Estado conexion WAN (IP publica, DNS, uptime)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_wan_status() -> str:
    """Devuelve IP publica, gateway, DNS, MAC WAN, tipo de conexion y
    uptime del enlace WAN del router."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_wan_status
        data = await pages.fetch_wan_status()
        return format_wan_status(data)
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
