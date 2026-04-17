# -*- coding: utf-8 -*-
"""Parsers HTML puros para el router ZTE F680.

Tres formatos:
- A (Transfer_meaning): paginas de configuracion (WiFi, DHCP, DMZ, NAT).
- B (Frm_* + entidades HTML): paginas de status (device info).
- C (tdleft/tdright): tablas de status WAN (IPv46_status_wan_if_t).

Todas las funciones son puras: sin I/O, sin estado. Testables con
fixtures HTML.
"""
from __future__ import annotations

import re
from typing import Iterable


_HEX_ESCAPE = re.compile(r"\\x([0-9a-fA-F]{2})")
_HTML_ENTITY = re.compile(r"&#(\d+);")
_TRANSFER = re.compile(r"Transfer_meaning\('(\w+)'\s*,\s*'([^']*)'\)")
_FRM_TABLE = re.compile(
    r'<td\s+class="tdleft">\s*([^<]+?)\s*</td>\s*'
    r'<td\s+id="(Frm_[^"]+)"[^>]*class="tdright"[^>]*>\s*([^<]*?)\s*</td>',
    re.DOTALL,
)
_NUMERIC_SUFFIX = re.compile(r"^(.*?)(\d+)$")
_TDRIGHT_TABLE = re.compile(
    r'<td\s+class="tdleft">\s*([^<]+?)\s*</td>\s*'
    r'<td\s+class="tdright">\s*([^<]*?)\s*</td>',
    re.DOTALL,
)
_IPV6_EMPTY_RE = re.compile(r"^[:/ ]+$")


def decode_hex_escapes(s: str) -> str:
    """Reemplaza '\\xNN' por su char (formato A)."""
    return _HEX_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), s)


def decode_html_entities(s: str) -> str:
    """Reemplaza '&#NNN;' (decimal) por su char (formato B)."""
    return _HTML_ENTITY.sub(lambda m: chr(int(m.group(1))), s)


def parse_transfer_meaning(html: str) -> dict[str, str]:
    """Extrae campos Transfer_meaning('Campo','valor').

    El router emite cada campo dos veces: primero con valor vacio
    (plantilla) y luego con valor real. Nos quedamos con la ultima
    ocurrencia NO vacia para cada key.
    """
    out: dict[str, str] = {}
    for m in _TRANSFER.finditer(html):
        key = m.group(1)
        val = decode_hex_escapes(m.group(2))
        if val != "":
            out[key] = val
        else:
            out.setdefault(key, "")
    return out


def parse_frm_table(html: str) -> dict[str, str]:
    """Extrae pares Frm_XXX -> valor de tablas <td class=tdleft>/<td id=Frm_*>."""
    out: dict[str, str] = {}
    for m in _FRM_TABLE.finditer(html):
        key = m.group(2)
        val = decode_html_entities(m.group(3)).strip()
        out[key] = val
    return out


def parse_tdright_table(html: str) -> dict[str, str]:
    """Extrae pares label->valor de tablas <td class=tdleft>/<td class=tdright>.

    Formato C: usado en paginas de status WAN. Los valores pueden contener
    entidades HTML decimales (&#NNN;). Si hay labels duplicadas (ej: 'DNS'
    aparece dos veces, IPv4 e IPv6) se conserva la primera aparicion no
    vacia y que no sea solo '::' (IPv6 vacio). Esto prioriza IPv4.
    """
    out: dict[str, str] = {}
    for m in _TDRIGHT_TABLE.finditer(html):
        key = decode_html_entities(m.group(1)).strip()
        val = decode_html_entities(m.group(2)).strip()
        if key not in out:
            out[key] = val
        elif not out[key] or _IPV6_EMPTY_RE.match(out[key]):
            # La primera aparicion era vacia/IPv6-vacio, reemplazar
            out[key] = val
    return out


def group_by_numeric_suffix(
    data: dict[str, str],
    prefixes: Iterable[str],
) -> list[dict[str, str]]:
    """Agrupa keys tipo 'MACAddr0', 'MACAddr1' en list[dict] por indice.

    Solo toma en cuenta las keys cuyo prefijo esta en `prefixes`. Ignora
    las demas. Ordena por indice numerico ascendente.
    """
    prefixes_set = set(prefixes)
    rows: dict[int, dict[str, str]] = {}
    for key, val in data.items():
        m = _NUMERIC_SUFFIX.match(key)
        if not m:
            continue
        prefix, idx_str = m.group(1), m.group(2)
        if prefix not in prefixes_set:
            continue
        idx = int(idx_str)
        rows.setdefault(idx, {})[prefix] = val
    return [rows[i] for i in sorted(rows.keys())]
