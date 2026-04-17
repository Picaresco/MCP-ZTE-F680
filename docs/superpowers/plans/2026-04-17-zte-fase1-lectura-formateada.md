# ZTE F680 MCP - Fase 1 (Lectura formateada) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir 6 tools de solo lectura al MCP zte-f680-mcp (device_info, wan_status, wifi_info, dhcp_leases, dmz, wifi_clients) con salida formateada, y refactorizar el código a 5 módulos con tests unitarios.

**Architecture:** Refactor mínimo: extraer la lógica de `server.py` actual a `http_client.py`, `parsers.py`, `pages.py`, `formatters.py`; `server.py` queda con solo lifespan + declaración de tools. Añadir un segundo parser para páginas tipo `Frm_*` con entidades HTML decimales. Tests unitarios contra fixtures HTML capturados del router real.

**Tech Stack:** Python 3.10+, FastMCP (`mcp[cli]`), httpx, pytest, hatchling.

**Spec:** `docs/superpowers/specs/2026-04-17-zte-fase1-lectura-formateada-design.md`.

---

## Task 0: Setup — fixtures y esqueleto de tests

**Files:**
- Create: `tests/__init__.py` (vacío)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/README.md`
- Create: `tests/fixtures/status_dev_info_t.html`
- Create: `tests/fixtures/IPv46_status_wan_if_t.html`
- Create: `tests/fixtures/net_wlanm_secrity1_t.html`
- Create: `tests/fixtures/net_wlanm_secrity2_t.html`
- Create: `tests/fixtures/net_dhcp_dynamic_t.html`
- Create: `tests/fixtures/app_dmz_conf_t.html`
- Modify: `pyproject.toml` (añadir pytest como dep de test)

- [ ] **Step 0.1: Activar venv y añadir pytest**

```bash
cd C:/Users/Alberto/Documents/code_claude/ROUTER_CASA
source venv/Scripts/activate  # bash en Windows
pip install pytest pytest-asyncio
```

- [ ] **Step 0.2: Añadir dependencia de test a `pyproject.toml`**

Añadir al final del fichero (antes de `[tool.hatch.*]`):

```toml
[project.optional-dependencies]
test = [
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "router: tests que requieren router ZTE real (desactivados por defecto)",
]
```

- [ ] **Step 0.3: Capturar fixtures HTML del router real**

Crear script temporal `scripts/capture_fixtures.py`:

```python
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
```

Ejecutar:

```bash
python scripts/capture_fixtures.py
```

Expected: 6 ficheros creados en `tests/fixtures/` con tamaños > 1000 chars cada uno.

- [ ] **Step 0.4: Crear `tests/fixtures/README.md`**

```markdown
# Fixtures HTML del router ZTE F680

Capturados del router real (firmware Jazztel `ZTEGF6804P1T28`) con
`scripts/capture_fixtures.py`. Se usan para tests unitarios de parsers
y formatters sin necesidad de router.

Si el firmware cambia, regenerar con el script anterior.
```

- [ ] **Step 0.5: Crear `tests/__init__.py` vacío y `tests/conftest.py`**

`tests/conftest.py`:

```python
# -*- coding: utf-8 -*-
"""Fixtures compartidos por los tests unitarios."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def html_device_info() -> str:
    return (FIXTURES / "status_dev_info_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wan_status() -> str:
    return (FIXTURES / "IPv46_status_wan_if_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wifi_24() -> str:
    return (FIXTURES / "net_wlanm_secrity1_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wifi_5() -> str:
    return (FIXTURES / "net_wlanm_secrity2_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_dhcp() -> str:
    return (FIXTURES / "net_dhcp_dynamic_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_dmz() -> str:
    return (FIXTURES / "app_dmz_conf_t.html").read_text(encoding="utf-8")
```

- [ ] **Step 0.6: Verificar que pytest descubre los tests vacíos**

```bash
pytest tests/ -v
```

Expected: `no tests ran` (no hay tests todavía) sin errores de colección.

- [ ] **Step 0.7: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/pyproject.toml ROUTER_CASA/scripts/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
test(zte-mcp): fixtures HTML + scaffold pytest (Fase 1)

Capturados los 6 HTML crudos del router Jazztel como fixtures para
tests unitarios sin router. Añadido pyproject [test] deps + conftest.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: Módulo `parsers.py`

**Files:**
- Create: `src/zte_f680_mcp/parsers.py`
- Create: `tests/test_parsers.py`

Extrae del `server.py` actual los helpers de parseo y añade `parse_frm_table` para el formato B.

- [ ] **Step 1.1: Escribir tests que fallen para `parse_transfer_meaning`**

`tests/test_parsers.py`:

```python
# -*- coding: utf-8 -*-
"""Tests unitarios de parsers HTML del router ZTE F680."""
from zte_f680_mcp.parsers import (
    parse_transfer_meaning,
    parse_frm_table,
    decode_hex_escapes,
    decode_html_entities,
    group_by_numeric_suffix,
)


def test_decode_hex_escapes():
    assert decode_hex_escapes("192\\x2e168\\x2e1\\x2e1") == "192.168.1.1"
    assert decode_hex_escapes("sin-escapes") == "sin-escapes"


def test_decode_html_entities():
    # "F680" en entidades decimales
    assert decode_html_entities("&#70;&#54;&#56;&#48;") == "F680"
    assert decode_html_entities("ya limpio") == "ya limpio"


def test_parse_transfer_meaning_basic():
    html = "Transfer_meaning('Name','test');Transfer_meaning('Proto','TCP');"
    data = parse_transfer_meaning(html)
    assert data == {"Name": "test", "Proto": "TCP"}


def test_parse_transfer_meaning_keeps_last_non_empty():
    # El router emite primero la key vacía (plantilla) y luego con valor.
    # Debe quedarse con la última no vacía.
    html = (
        "Transfer_meaning('ESSID','');"
        "Transfer_meaning('ESSID','Casa_Chull_2g');"
    )
    data = parse_transfer_meaning(html)
    assert data == {"ESSID": "Casa_Chull_2g"}


def test_parse_transfer_meaning_decodes_hex():
    html = r"Transfer_meaning('IP','192\x2e168\x2e1\x2e1');"
    data = parse_transfer_meaning(html)
    assert data == {"IP": "192.168.1.1"}


def test_parse_frm_table_basic():
    html = (
        '<td class="tdleft">Model</td>'
        '<td id="Frm_ModelName" name="Frm_ModelName" class="tdright">'
        "&#70;&#54;&#56;&#48;</td>"
    )
    data = parse_frm_table(html)
    assert data == {"Frm_ModelName": "F680"}


def test_parse_frm_table_strips_whitespace():
    html = (
        '<td class="tdleft">Serial</td>'
        '<td id="Frm_SerialNumber" name="Frm_SerialNumber" class="tdright">'
        "  &#90;&#84;&#69;  </td>"
    )
    data = parse_frm_table(html)
    assert data == {"Frm_SerialNumber": "ZTE"}


def test_group_by_numeric_suffix():
    d = {
        "MACAddr0": "aa:bb",
        "IPAddr0": "1.1.1.1",
        "MACAddr1": "cc:dd",
        "IPAddr1": "2.2.2.2",
        "OtherKey": "ignore",
    }
    groups = group_by_numeric_suffix(d, prefixes=["MACAddr", "IPAddr"])
    assert groups == [
        {"MACAddr": "aa:bb", "IPAddr": "1.1.1.1"},
        {"MACAddr": "cc:dd", "IPAddr": "2.2.2.2"},
    ]


def test_group_by_numeric_suffix_sorts_by_index():
    d = {"X2": "c", "X0": "a", "X1": "b"}
    groups = group_by_numeric_suffix(d, prefixes=["X"])
    assert [g["X"] for g in groups] == ["a", "b", "c"]


# Fixture-based (contra HTML real del router)

def test_parse_transfer_meaning_real_wifi_24(html_wifi_24):
    data = parse_transfer_meaning(html_wifi_24)
    assert data["ESSID"] == "Casa_Chull_2g"
    assert data["Channel"] == "1"
    assert data["KeyPassphrase"] == "ChullWapa$"
    assert data["Bssid"] == "24:d3:f2:c6:97:b6"


def test_parse_frm_table_real_device_info(html_device_info):
    data = parse_frm_table(html_device_info)
    assert data["Frm_ModelName"] == "F680"
    assert data["Frm_SerialNumber"] == "ZTEEQERJ8L16414"
    assert data["Frm_SoftwareVer"] == "ZTEGF6804P1T28"
    assert data["Frm_HardwareVer"] == "V4.0"
```

- [ ] **Step 1.2: Ejecutar tests — deben fallar**

```bash
pytest tests/test_parsers.py -v
```

Expected: `ModuleNotFoundError: zte_f680_mcp.parsers`.

- [ ] **Step 1.3: Implementar `parsers.py`**

`src/zte_f680_mcp/parsers.py`:

```python
# -*- coding: utf-8 -*-
"""Parsers HTML puros para el router ZTE F680.

Dos formatos:
- A (Transfer_meaning): paginas de configuracion (WiFi, DHCP, DMZ, NAT).
- B (Frm_* + entidades HTML): paginas de status (device info).

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
        # Siempre actualiza si val no es vacio, asi la ultima ocurrencia gana.
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
```

- [ ] **Step 1.4: Ejecutar tests — deben pasar**

```bash
pytest tests/test_parsers.py -v
```

Expected: todos los tests PASAN (11 tests).

- [ ] **Step 1.5: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/parsers.py ROUTER_CASA/tests/test_parsers.py
git commit -m "$(cat <<'EOF'
feat(zte-mcp): parsers.py con soporte formato A (Transfer_meaning) y B (Frm_*)

Nuevos helpers puros: decode_hex_escapes, decode_html_entities,
parse_transfer_meaning (se queda con la ultima ocurrencia no vacia),
parse_frm_table, group_by_numeric_suffix. Tests unitarios contra
fixtures reales del router.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Módulo `http_client.py`

**Files:**
- Create: `src/zte_f680_mcp/http_client.py`
- Modify: `src/zte_f680_mcp/server.py` (eliminar funciones extraídas)

Mueve `_login`, `_ensure_session`, `_fetch_port_fwd_page`, `_post_form` y el estado global del cliente a `http_client.py`. Deja en `server.py` solo lifespan + tools.

- [ ] **Step 2.1: Crear `http_client.py` copiando lógica actual**

`src/zte_f680_mcp/http_client.py`:

```python
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
```

- [ ] **Step 2.2: Refactorizar `server.py` para usar `http_client`**

En `server.py`, hacer estas sustituciones exactas:

**Eliminar** las líneas 4-36 (imports innecesarios) y 129-229 (funciones movidas) y sustituir el bloque de imports por:

```python
# -*- coding: utf-8 -*-
"""MCP Server para gestionar NAT/port forwarding en router ZTE F680."""

from __future__ import annotations

import re
import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from zte_f680_mcp import http_client
from zte_f680_mcp.parsers import (
    decode_hex_escapes,
    parse_transfer_meaning,
)
```

**Eliminar** las constantes globales `ZTE_HOST`, `ZTE_USER`, `ZTE_PASSWORD`, `FORM_URL`, `SESSION_TIMEOUT`, `_http_client`, `_session_valid`, `_last_request_time` (ahora viven en `http_client`).

**Eliminar** funciones `_decode_hex_escapes`, `_parse_rules`, `_extract_session_token`, `_check_response_error`, `_login`, `_ensure_session`, `_fetch_port_fwd_page`, `_post_form`.

**Sustituir** las llamadas internas:
- `_fetch_port_fwd_page()` → `await http_client.fetch_port_fwd_page()`
- `_post_form(data)` → `await http_client.post_port_fwd_form(data)`
- `_ensure_session()` → `await http_client.ensure_session()`
- `_parse_rules(html)` → ver siguiente paso (movemos a función local o importamos)
- `_decode_hex_escapes` → usar `decode_hex_escapes` importado

**Añadir** de vuelta `_parse_rules` y `_check_response_error` (son específicas del dominio NAT, no van a parsers):

```python
def _parse_rules(html: str) -> list[dict[str, str]]:
    """Extrae reglas de port forwarding (usa agrupacion por sufijo numerico)."""
    data = parse_transfer_meaning(html)
    # El parser ya decodifica \xNN, ahora agrupamos por sufijo numerico.
    # Las claves relevantes son: Name, Protocol, Enable, MinExtPort, MaxExtPort,
    # InternalHost, MinIntPort, MaxIntPort, ViewName.
    from zte_f680_mcp.parsers import group_by_numeric_suffix
    fields = [
        "Name", "Protocol", "Enable", "MinExtPort", "MaxExtPort",
        "InternalHost", "MinIntPort", "MaxIntPort", "ViewName",
    ]
    rows = group_by_numeric_suffix(data, prefixes=fields)
    # Filtrar filas sin Name (eran entradas de plantilla).
    return [r for r in rows if r.get("Name")]


def _check_response_error(html: str) -> str | None:
    data = parse_transfer_meaning(html)
    val = data.get("IF_ERRORSTR")
    if val and val != "SUCC":
        return val
    return None
```

**Sustituir** el `lifespan` actual por:

```python
@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    await http_client.startup()
    yield
    await http_client.shutdown()
```

**Sustituir** la función `_get_local_ip_for` dejándola igual, y en `zte_get_local_ip` / `zte_open_port` cambiar `ZTE_HOST` por `http_client.ZTE_HOST`.

- [ ] **Step 2.3: Test smoke — cargar el módulo no debe romper**

```bash
cd C:/Users/Alberto/Documents/code_claude/ROUTER_CASA
python -c "from zte_f680_mcp.server import mcp; print('OK')"
```

Expected: `OK` (sin imports rotos).

- [ ] **Step 2.4: Test smoke funcional contra router real**

```bash
python -c "
import asyncio
from zte_f680_mcp.server import zte_get_port_forwards
print(asyncio.run(zte_get_port_forwards()))
"
```

Expected: lista de reglas NAT (misma salida que antes del refactor).

- [ ] **Step 2.5: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/http_client.py ROUTER_CASA/src/zte_f680_mcp/server.py
git commit -m "$(cat <<'EOF'
refactor(zte-mcp): extraer sesion HTTP a http_client.py

server.py ahora solo declara tools y lifespan. http_client encapsula
login, ensure_session, fetch_html y POST de port forwarding. Las
tools NAT existentes reutilizan las APIs nuevas sin cambios de firma.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Módulos `pages.py` y `formatters.py` (esqueleto) + tool `zte_get_device_info`

**Files:**
- Create: `src/zte_f680_mcp/pages.py`
- Create: `src/zte_f680_mcp/formatters.py`
- Create: `tests/test_formatters.py`
- Modify: `src/zte_f680_mcp/server.py`

Añade la primera tool completa como referencia. Las siguientes reusan este patrón.

- [ ] **Step 3.1: Escribir test de formatter para device info**

`tests/test_formatters.py`:

```python
# -*- coding: utf-8 -*-
"""Tests unitarios de formatters (dict -> string bonito)."""
from zte_f680_mcp.formatters import format_device_info


def test_format_device_info_all_fields():
    data = {
        "model": "F680",
        "serial": "ZTEEQERJ8L16414",
        "hardware": "V4.0",
        "firmware": "ZTEGF6804P1T28",
        "firmware_batch": "07e4T10456",
        "bootloader": "V4.0.10",
        "wifi_chipsets": "2.4G Broadcom BCM43217 / 5G Quantenna QV840",
    }
    out = format_device_info(data)
    assert "F680" in out
    assert "ZTEEQERJ8L16414" in out
    assert "ZTEGF6804P1T28" in out
    assert "07e4T10456" in out
    assert "V4.0.10" in out
    assert "Modelo:" in out


def test_format_device_info_missing_fields():
    data = {"model": "F680"}
    out = format_device_info(data)
    assert "F680" in out
    assert "—" in out  # para los campos ausentes
```

- [ ] **Step 3.2: Ejecutar tests — deben fallar**

```bash
pytest tests/test_formatters.py -v
```

Expected: `ModuleNotFoundError: zte_f680_mcp.formatters`.

- [ ] **Step 3.3: Crear `formatters.py` con `format_device_info`**

`src/zte_f680_mcp/formatters.py`:

```python
# -*- coding: utf-8 -*-
"""Formatters: dict limpio -> texto bonito para mostrar al usuario."""
from __future__ import annotations


def _val(d: dict[str, str], key: str) -> str:
    """Devuelve d[key] o '—' si falta / esta vacio."""
    v = d.get(key, "").strip() if isinstance(d.get(key), str) else d.get(key)
    return v if v else "—"


def format_device_info(data: dict[str, str]) -> str:
    lines = [
        "ZTE F680 - Informacion del dispositivo",
        f"  Modelo:         {_val(data, 'model')}",
        f"  Serie:          {_val(data, 'serial')}",
        f"  Firmware:       {_val(data, 'firmware')}  "
        f"(batch {_val(data, 'firmware_batch')})",
        f"  Hardware:       {_val(data, 'hardware')}",
        f"  BootLoader:     {_val(data, 'bootloader')}",
        f"  WiFi chipsets:  {_val(data, 'wifi_chipsets')}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 3.4: Ejecutar tests — deben pasar**

```bash
pytest tests/test_formatters.py -v
```

Expected: 2 tests PASAN.

- [ ] **Step 3.5: Escribir test para `pages.fetch_device_info` (offline, usando fixture)**

Añadir a `tests/test_parsers.py` (reutilizamos su conftest):

Crear `tests/test_pages.py`:

```python
# -*- coding: utf-8 -*-
"""Tests de pages.py (layer entre http_client y parsers).

Estos tests NO usan router real: parchean http_client.fetch_html para
devolver fixtures HTML.
"""
import pytest

from zte_f680_mcp import pages


@pytest.fixture
def mock_fetch(monkeypatch):
    """Devuelve una factory: pages_to_html (dict) -> stub de fetch_html."""
    calls = []

    def make(pages_to_html: dict[str, str]):
        async def stub(page_name: str) -> str:
            calls.append(page_name)
            if page_name not in pages_to_html:
                raise AssertionError(f"pagina inesperada: {page_name}")
            return pages_to_html[page_name]

        monkeypatch.setattr(pages.http_client, "fetch_html", stub)
        return calls

    return make


@pytest.mark.asyncio
async def test_fetch_device_info_real(mock_fetch, html_device_info):
    mock_fetch({"status_dev_info_t.gch": html_device_info})
    data = await pages.fetch_device_info()
    assert data["model"] == "F680"
    assert data["serial"] == "ZTEEQERJ8L16414"
    assert data["firmware"] == "ZTEGF6804P1T28"
    assert data["firmware_batch"] == "07e4T10456"
    assert data["hardware"] == "V4.0"
    assert data["bootloader"] == "V4.0.10"
    assert "Broadcom" in data["wifi_chipsets"]
```

- [ ] **Step 3.6: Crear `pages.py` con `fetch_device_info`**

`src/zte_f680_mcp/pages.py`:

```python
# -*- coding: utf-8 -*-
"""Orquestadores por pagina funcional del router ZTE F680.

Cada funcion combina http_client + parsers y devuelve un dict con
claves limpias en español/ingles que el formatter sabe presentar.
"""
from __future__ import annotations

from zte_f680_mcp import http_client
from zte_f680_mcp.parsers import parse_frm_table


async def fetch_device_info() -> dict[str, str]:
    """Lee status_dev_info_t.gch y devuelve dict con identidad HW/SW."""
    html = await http_client.fetch_html("status_dev_info_t.gch")
    raw = parse_frm_table(html)

    wifi_chipsets = ""
    if raw.get("Frm_WiFiVendor") and raw.get("Frm_WiFiModel"):
        # "2.4G Broadcom 5G Quantenna" + "2.4G BCM43217 5G QV840" ->
        # "2.4G Broadcom BCM43217 / 5G Quantenna QV840"
        wifi_chipsets = (
            f"{raw['Frm_WiFiVendor']} "
            f"{raw['Frm_WiFiModel']}"
        ).strip()

    return {
        "model": raw.get("Frm_ModelName", ""),
        "serial": raw.get("Frm_SerialNumber", ""),
        "hardware": raw.get("Frm_HardwareVer", ""),
        "firmware": raw.get("Frm_SoftwareVer", ""),
        "firmware_batch": raw.get("Frm_SoftwareVerExtent", ""),
        "bootloader": raw.get("Frm_BootVer", ""),
        "wifi_chipsets": wifi_chipsets,
    }
```

- [ ] **Step 3.7: Ejecutar tests de pages**

```bash
pytest tests/test_pages.py -v
```

Expected: 1 test PASA.

- [ ] **Step 3.8: Añadir tool `zte_get_device_info` en `server.py`**

Al final de `server.py` (antes de `def main()`):

```python
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
```

- [ ] **Step 3.9: Smoke test contra router real**

```bash
python -c "
import asyncio
from zte_f680_mcp.server import zte_get_device_info
print(asyncio.run(zte_get_device_info()))
"
```

Expected:

```
ZTE F680 - Informacion del dispositivo
  Modelo:         F680
  Serie:          ZTEEQERJ8L16414
  Firmware:       ZTEGF6804P1T28  (batch 07e4T10456)
  Hardware:       V4.0
  BootLoader:     V4.0.10
  WiFi chipsets:  2.4G Broadcom 5G Quantenna 2.4G BCM43217 5G QV840
```

- [ ] **Step 3.10: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/pages.py ROUTER_CASA/src/zte_f680_mcp/formatters.py ROUTER_CASA/src/zte_f680_mcp/server.py ROUTER_CASA/tests/test_formatters.py ROUTER_CASA/tests/test_pages.py
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_device_info + modulos pages/formatters

Primera tool de Fase 1: lee status_dev_info_t.gch (formato Frm_*),
devuelve modelo/serie/firmware/hardware/bootloader/chipsets. Establece
el patron tools = pages.fetch_X() + formatters.format_X(data).

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Tool `zte_get_wifi_info` (combina 2 páginas)

**Files:**
- Modify: `src/zte_f680_mcp/pages.py`
- Modify: `src/zte_f680_mcp/formatters.py`
- Modify: `src/zte_f680_mcp/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 4.1: Test de pages.fetch_wifi_info**

Añadir a `tests/test_pages.py`:

```python
@pytest.mark.asyncio
async def test_fetch_wifi_info_real(mock_fetch, html_wifi_24, html_wifi_5):
    mock_fetch({
        "net_wlanm_secrity1_t.gch": html_wifi_24,
        "net_wlanm_secrity2_t.gch": html_wifi_5,
    })
    data = await pages.fetch_wifi_info()
    assert data["band_24"]["essid"] == "Casa_Chull_2g"
    assert data["band_24"]["passphrase"] == "ChullWapa$"
    assert data["band_24"]["bssid"] == "24:d3:f2:c6:97:b6"
    assert data["band_24"]["channel"] == "1"
    assert data["band_24"]["enabled"] == "1"
    assert data["band_5"]["essid"] == "Casa_chull_5g"
    assert data["band_5"]["channel"] == "100"
    assert data["band_5"]["bssid"] == "24:d3:f2:c6:97:b7"
```

Ejecutar: `pytest tests/test_pages.py::test_fetch_wifi_info_real -v` → FAIL (no existe).

- [ ] **Step 4.2: Implementar `fetch_wifi_info` en `pages.py`**

Añadir a `pages.py`:

```python
from zte_f680_mcp.parsers import parse_transfer_meaning


_WIFI_WHITELIST = {
    "ESSID": "essid",
    "Channel": "channel",
    "Band": "band",
    "Enable": "enabled",
    "RadioStatus": "radio_on",
    "Standard": "standard",
    "BandWidth": "bandwidth",
    "BeaconType": "beacon_type",
    "WPAAuthMode": "wpa_auth",
    "WPAEncryptType": "wpa_encrypt",
    "KeyPassphrase": "passphrase",
    "Bssid": "bssid",
    "ESSIDHideEnable": "hidden",
    "TxPower": "tx_power",
    "MaxUserNum": "max_clients",
    "AutoChannelEnabled": "auto_channel",
    "TotalBytesSent": "tx_bytes",
    "TotalBytesReceived": "rx_bytes",
    "TotalAssociations": "associations",
}


def _pick_wifi(raw: dict[str, str]) -> dict[str, str]:
    return {
        clean: raw.get(orig, "")
        for orig, clean in _WIFI_WHITELIST.items()
    }


async def fetch_wifi_info() -> dict[str, dict[str, str]]:
    """Lee config WiFi de ambas bandas (secrity1 y secrity2).

    Retorna dict con claves 'band_24' y 'band_5', cada una con los
    campos limpios de _WIFI_WHITELIST.
    """
    html_24 = await http_client.fetch_html("net_wlanm_secrity1_t.gch")
    html_5 = await http_client.fetch_html("net_wlanm_secrity2_t.gch")
    return {
        "band_24": _pick_wifi(parse_transfer_meaning(html_24)),
        "band_5": _pick_wifi(parse_transfer_meaning(html_5)),
    }
```

Ejecutar test: `pytest tests/test_pages.py::test_fetch_wifi_info_real -v` → PASS.

- [ ] **Step 4.3: Test de formatter**

Añadir a `tests/test_formatters.py`:

```python
from zte_f680_mcp.formatters import format_wifi_info


def test_format_wifi_info_both_bands():
    data = {
        "band_24": {
            "essid": "Casa_Chull_2g",
            "channel": "1",
            "band": "2.4G",
            "enabled": "1",
            "standard": "g,n",
            "bandwidth": "20MHz",
            "wpa_encrypt": "AESEncryption",
            "passphrase": "ChullWapa$",
            "bssid": "24:d3:f2:c6:97:b6",
            "hidden": "0",
            "tx_power": "100%",
            "max_clients": "16",
            "auto_channel": "0",
            "tx_bytes": "1273164037",
            "rx_bytes": "90736063",
            "associations": "1",
        },
        "band_5": {
            "essid": "Casa_chull_5g",
            "channel": "100",
            "band": "5G",
            "enabled": "1",
            "standard": "a,n,ac",
            "bandwidth": "Auto",
            "wpa_encrypt": "AESEncryption",
            "passphrase": "ChullWapa$",
            "bssid": "24:d3:f2:c6:97:b7",
            "hidden": "0",
            "tx_power": "100%",
            "max_clients": "16",
            "auto_channel": "1",
            "tx_bytes": "18502710717",
            "rx_bytes": "451755856",
            "associations": "1",
        },
    }
    out = format_wifi_info(data)
    assert "WiFi 2.4 GHz" in out
    assert "WiFi 5 GHz" in out
    assert "Casa_Chull_2g" in out
    assert "Casa_chull_5g" in out
    assert "ChullWapa$" in out
    assert "24:d3:f2:c6:97:b6" in out
    # Bytes convertidos a GB/MB
    assert "GB" in out or "MB" in out
    # Canal manual (auto_channel=0 en 2.4)
    assert "1 (manual)" in out
    # Canal auto en 5GHz (auto_channel=1)
    assert "100 (auto)" in out
```

- [ ] **Step 4.4: Implementar `format_wifi_info` en `formatters.py`**

```python
def _human_bytes(n_str: str) -> str:
    try:
        n = int(n_str)
    except (TypeError, ValueError):
        return "—"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


def _onoff(v: str) -> str:
    return "ON" if v == "1" else "OFF"


def _yesno(v: str) -> str:
    return "SI" if v == "1" else "NO"


_ENCRYPT_LABEL = {
    "AESEncryption": "WPA/WPA2 AES",
    "TKIPEncryption": "WPA TKIP",
    "TKIPandAESEncryption": "WPA/WPA2 TKIP+AES",
}


def _format_wifi_band(title: str, b: dict[str, str]) -> list[str]:
    channel_mode = "auto" if b.get("auto_channel") == "1" else "manual"
    encrypt = _ENCRYPT_LABEL.get(b.get("wpa_encrypt", ""), b.get("wpa_encrypt", "—"))
    return [
        title,
        f"  SSID:        {_val(b, 'essid')}       Canal:     "
        f"{_val(b, 'channel')} ({channel_mode})",
        f"  Estado:      {_onoff(b.get('enabled', ''))}                  "
        f"Estandar:  {_val(b, 'standard')}     Ancho: {_val(b, 'bandwidth')}",
        f"  Seguridad:   {encrypt}        Clave:     {_val(b, 'passphrase')}",
        f"  BSSID:       {_val(b, 'bssid')}   Oculta:    "
        f"{_yesno(b.get('hidden', ''))}",
        f"  TxPower:     {_val(b, 'tx_power')}                "
        f"Max clientes: {_val(b, 'max_clients')}",
        f"  Trafico:     TX {_human_bytes(b.get('tx_bytes', ''))} / "
        f"RX {_human_bytes(b.get('rx_bytes', ''))}      "
        f"Asociaciones: {_val(b, 'associations')}",
    ]


def format_wifi_info(data: dict[str, dict[str, str]]) -> str:
    lines: list[str] = []
    lines.extend(_format_wifi_band("WiFi 2.4 GHz", data.get("band_24", {})))
    lines.append("")
    lines.extend(_format_wifi_band("WiFi 5 GHz", data.get("band_5", {})))
    return "\n".join(lines)
```

Ejecutar: `pytest tests/test_formatters.py -v` → todos PASAN.

- [ ] **Step 4.5: Añadir tool en `server.py`**

```python
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
```

- [ ] **Step 4.6: Smoke test router real**

```bash
python -c "
import asyncio
from zte_f680_mcp.server import zte_get_wifi_info
print(asyncio.run(zte_get_wifi_info()))
"
```

Expected: bloque con `Casa_Chull_2g` y `Casa_chull_5g`, clave `ChullWapa$`, BSSIDs `24:d3:f2:c6:97:b6/b7`.

- [ ] **Step 4.7: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_wifi_info (2.4 + 5 GHz con PSK real)

Lee net_wlanm_secrity{1,2}_t.gch (superset de conf{1,2}). Incluye PSK
real (KeyPassphrase), BSSID y stats de trafico. Descarta placeholders
RADIUS (WPAEAPSecret) que confunden.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Tool `zte_get_dhcp_leases`

**Files:**
- Modify: `src/zte_f680_mcp/pages.py`
- Modify: `src/zte_f680_mcp/formatters.py`
- Modify: `src/zte_f680_mcp/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 5.1: Test de pages.fetch_dhcp_leases**

```python
@pytest.mark.asyncio
async def test_fetch_dhcp_leases_real(mock_fetch, html_dhcp):
    mock_fetch({"net_dhcp_dynamic_t.gch": html_dhcp})
    data = await pages.fetch_dhcp_leases()

    pool = data["pool"]
    assert pool["router_ip"] == "192.168.1.1"
    assert pool["min_addr"] == "192.168.1.128"
    assert pool["max_addr"] == "192.168.1.149"
    assert pool["lease_seconds"] == "86400"

    leases = data["leases"]
    assert len(leases) == 9
    # Verifica uno conocido
    pc101 = next(l for l in leases if l["hostname"] == "PC101")
    assert pc101["ip"] == "192.168.1.128"
    assert pc101["mac"] == "e0:73:e7:2b:89:75"
    assert pc101["port"] == "LAN1"
    assert int(pc101["expires_seconds"]) > 0
```

Ejecutar: FAIL.

- [ ] **Step 5.2: Implementar `fetch_dhcp_leases`**

```python
async def fetch_dhcp_leases() -> dict:
    """Lee net_dhcp_dynamic_t.gch y devuelve pool + lista de leases."""
    html = await http_client.fetch_html("net_dhcp_dynamic_t.gch")
    raw = parse_transfer_meaning(html)

    pool = {
        "router_ip": raw.get("BasicIPAddr", ""),
        "min_addr": raw.get("MinAddress", ""),
        "max_addr": raw.get("MaxAddress", ""),
        "subnet_mask": raw.get("SubnetMask", ""),
        "dns1": raw.get("DNSServer1", ""),
        "lease_seconds": raw.get("LeaseTime", ""),
    }

    from zte_f680_mcp.parsers import group_by_numeric_suffix
    groups = group_by_numeric_suffix(
        raw,
        prefixes=["MACAddr", "IPAddr", "HostName", "ExpiredTime", "PhyPortName"],
    )
    leases = [
        {
            "mac": g.get("MACAddr", ""),
            "ip": g.get("IPAddr", ""),
            "hostname": g.get("HostName", ""),
            "expires_seconds": g.get("ExpiredTime", ""),
            "port": g.get("PhyPortName", ""),
        }
        for g in groups
        if g.get("MACAddr")  # descarta filas plantilla vacias
    ]
    return {"pool": pool, "leases": leases}
```

Ejecutar test → PASS.

- [ ] **Step 5.3: Test de formatter**

```python
from zte_f680_mcp.formatters import format_dhcp_leases


def test_format_dhcp_leases_real():
    data = {
        "pool": {
            "router_ip": "192.168.1.1",
            "min_addr": "192.168.1.128",
            "max_addr": "192.168.1.149",
            "subnet_mask": "255.255.255.0",
            "dns1": "192.168.1.1",
            "lease_seconds": "86400",
        },
        "leases": [
            {
                "mac": "e0:73:e7:2b:89:75",
                "ip": "192.168.1.128",
                "hostname": "PC101",
                "expires_seconds": "61837",
                "port": "LAN1",
            },
            {
                "mac": "56:90:e5:ef:55:45",
                "ip": "192.168.1.130",
                "hostname": "",
                "expires_seconds": "26230",
                "port": "eth4",
            },
        ],
    }
    out = format_dhcp_leases(data)
    assert "192.168.1.1" in out
    assert ".128-.149" in out
    assert "PC101" in out
    assert "—" in out  # hostname vacio
    assert "LAN1" in out
    assert "WiFi" in out  # eth4 -> WiFi
    assert "17h 10m" in out  # 61837s
    assert "7h 17m" in out   # 26230s
    assert "24h" in out      # lease 86400s
```

- [ ] **Step 5.4: Implementar `format_dhcp_leases`**

```python
def _human_seconds(s_str: str) -> str:
    try:
        s = int(s_str)
    except (TypeError, ValueError):
        return "—"
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d > 0:
        return f"{d}d {h}h"
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def _port_label(port: str) -> str:
    if port.startswith("LAN"):
        return port
    if port == "eth4":
        return "WiFi"
    if port.startswith("SSID"):
        # SSID1-4 -> WiFi 2.4GHz, SSID5-8 -> WiFi 5GHz
        try:
            n = int(port[4:])
            return "WiFi 2.4GHz" if n <= 4 else "WiFi 5GHz"
        except ValueError:
            return port
    return port or "—"


def format_dhcp_leases(data: dict) -> str:
    pool = data.get("pool", {})
    leases = data.get("leases", [])
    lease_h = _human_seconds(pool.get("lease_seconds", ""))

    header = [
        f"ZTE F680 - Dispositivos conectados ({len(leases)} activos)",
        f"  Router:   {_val(pool, 'router_ip')}   "
        f"Rango DHCP: .{pool.get('min_addr', '').rsplit('.', 1)[-1]}-"
        f".{pool.get('max_addr', '').rsplit('.', 1)[-1]}   Lease: {lease_h}",
        "",
        "  IP              MAC                 Hostname       "
        "Conexion       Expira",
    ]

    rows = []
    for l in leases:
        hostname = l.get("hostname", "") or "—"
        rows.append(
            f"  {l.get('ip', ''):15s} {l.get('mac', ''):18s}  "
            f"{hostname:13s}  {_port_label(l.get('port', '')):13s}  "
            f"{_human_seconds(l.get('expires_seconds', ''))}"
        )
    return "\n".join(header + rows)
```

Ejecutar tests → PASAN.

- [ ] **Step 5.5: Tool en server.py**

```python
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
```

- [ ] **Step 5.6: Smoke test**

```bash
python -c "
import asyncio
from zte_f680_mcp.server import zte_get_dhcp_leases
print(asyncio.run(zte_get_dhcp_leases()))
"
```

Expected: tabla con 9 dispositivos, hostnames PC101, A36-de-Beto, MikroTik, POCO-X6-5G, etc.

- [ ] **Step 5.7: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_dhcp_leases

Lista dispositivos DHCP (IP, MAC, hostname, conexion LAN/WiFi,
expiracion) + info de pool. Mapea puertos internos (eth4, SSIDx)
a etiquetas humanas.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Tool `zte_get_wifi_clients`

**Files:**
- Modify: `src/zte_f680_mcp/pages.py`
- Modify: `src/zte_f680_mcp/formatters.py`
- Modify: `src/zte_f680_mcp/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 6.1: Test de pages.fetch_wifi_clients**

```python
@pytest.mark.asyncio
async def test_fetch_wifi_clients_real(mock_fetch, html_dhcp):
    mock_fetch({"net_dhcp_dynamic_t.gch": html_dhcp})
    data = await pages.fetch_wifi_clients()
    assert len(data) == 3
    # Primero: 1e:74:40:88:bf:42 en 5GHz SSID 5
    c0 = data[0]
    assert c0["mac"] == "1e:74:40:88:bf:42"
    assert c0["ip"] == "192.168.1.131"
    assert c0["rssi"] == "-58"
    assert c0["mode"] == "11ac"
    assert c0["ssid_index"] == "5"
```

- [ ] **Step 6.2: Implementar `fetch_wifi_clients`**

```python
async def fetch_wifi_clients() -> list[dict[str, str]]:
    """Lee la tabla de clientes WiFi asociados (viene en la pagina DHCP)."""
    html = await http_client.fetch_html("net_dhcp_dynamic_t.gch")
    raw = parse_transfer_meaning(html)

    from zte_f680_mcp.parsers import group_by_numeric_suffix
    groups = group_by_numeric_suffix(
        raw,
        prefixes=[
            "ADMACAddress", "ADIPAddress", "RSSI",
            "TXRate", "RXRate", "CurrentMode", "SSIDNAME",
        ],
    )
    return [
        {
            "mac": g.get("ADMACAddress", ""),
            "ip": g.get("ADIPAddress", ""),
            "rssi": g.get("RSSI", ""),
            "tx_rate": g.get("TXRate", ""),
            "rx_rate": g.get("RXRate", ""),
            "mode": g.get("CurrentMode", ""),
            "ssid_index": g.get("SSIDNAME", ""),
        }
        for g in groups
        if g.get("ADMACAddress")
    ]
```

- [ ] **Step 6.3: Test de formatter**

```python
from zte_f680_mcp.formatters import format_wifi_clients


def test_format_wifi_clients():
    clients = [
        {
            "mac": "1e:74:40:88:bf:42",
            "ip": "192.168.1.131",
            "rssi": "-58",
            "tx_rate": "866700",
            "rx_rate": "866700",
            "mode": "11ac",
            "ssid_index": "5",
        },
        {
            "mac": "e6:ae:ed:e9:f6:f2",
            "ip": "192.168.1.135",
            "rssi": "-77",
            "tx_rate": "866700",
            "rx_rate": "866700",
            "mode": "11ac",
            "ssid_index": "7",
        },
    ]
    out = format_wifi_clients(clients)
    assert "1e:74:40:88:bf:42" in out
    assert "-58 dBm (buena)" in out
    assert "-77 dBm (regular)" in out
    assert "5 GHz" in out  # ssid_index 5 -> 5GHz
    assert "11ac" in out


def test_format_wifi_clients_empty():
    assert "0" in format_wifi_clients([])
```

- [ ] **Step 6.4: Implementar `format_wifi_clients`**

```python
def _rssi_label(rssi_str: str) -> str:
    try:
        v = int(rssi_str)
    except (TypeError, ValueError):
        return "—"
    if v > -60:
        q = "buena"
    elif v > -75:
        q = "regular"
    else:
        q = "debil"
    return f"{v} dBm ({q})"


def _ssid_to_band(idx: str) -> str:
    try:
        n = int(idx)
    except (TypeError, ValueError):
        return "—"
    if 1 <= n <= 4:
        return f"2.4 GHz (SSID{n})"
    if 5 <= n <= 8:
        return f"5 GHz (SSID{n})"
    return f"SSID{n}"


def format_wifi_clients(clients: list[dict[str, str]]) -> str:
    header = [
        f"Clientes WiFi asociados ({len(clients)})",
        "  MAC                 IP              Banda (SSID)         "
        "Modo    Señal",
    ]
    rows = [
        f"  {c.get('mac', ''):18s}  {c.get('ip', ''):15s} "
        f"{_ssid_to_band(c.get('ssid_index', '')):20s} "
        f"{c.get('mode', ''):7s} {_rssi_label(c.get('rssi', ''))}"
        for c in clients
    ]
    return "\n".join(header + rows)
```

- [ ] **Step 6.5: Tool en server.py**

```python
@mcp.tool(
    annotations={
        "title": "Clientes WiFi asociados (con señal RSSI)",
        "readOnlyHint": True,
        "destructiveHint": False,
    }
)
async def zte_get_wifi_clients() -> str:
    """Lista los dispositivos conectados por WiFi con su RSSI (señal),
    banda, modo (11ac/11n) y tasa TX/RX."""
    try:
        from zte_f680_mcp import pages
        from zte_f680_mcp.formatters import format_wifi_clients
        data = await pages.fetch_wifi_clients()
        return format_wifi_clients(data)
    except Exception as exc:
        return f"Error: {exc}"
```

- [ ] **Step 6.6: Smoke test + commit**

```bash
python -c "
import asyncio
from zte_f680_mcp.server import zte_get_wifi_clients
print(asyncio.run(zte_get_wifi_clients()))
"
```

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_wifi_clients (RSSI + banda + modo)

Expone la tabla de clientes WiFi asociados (misma pagina DHCP).
Clasifica señal por umbrales (buena/regular/debil) y mapea SSID
index a banda.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Tool `zte_get_dmz`

**Files:**
- Modify: `src/zte_f680_mcp/pages.py`
- Modify: `src/zte_f680_mcp/formatters.py`
- Modify: `src/zte_f680_mcp/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 7.1: Tests (añadidos)**

```python
# tests/test_pages.py
@pytest.mark.asyncio
async def test_fetch_dmz_real(mock_fetch, html_dmz):
    mock_fetch({"app_dmz_conf_t.gch": html_dmz})
    data = await pages.fetch_dmz()
    assert data["enabled"] == "0"
    assert data["internal_host"] == "192.168.1.205"
    assert data["internal_mac"] == "6c:3b:6b:2c:ab:2e"


# tests/test_formatters.py
from zte_f680_mcp.formatters import format_dmz


def test_format_dmz_off():
    out = format_dmz({
        "enabled": "0",
        "internal_host": "192.168.1.205",
        "internal_mac": "6c:3b:6b:2c:ab:2e",
    })
    assert "OFF" in out
    assert "192.168.1.205" in out


def test_format_dmz_on():
    out = format_dmz({
        "enabled": "1",
        "internal_host": "192.168.1.205",
        "internal_mac": "6c:3b:6b:2c:ab:2e",
    })
    assert "ON" in out
```

- [ ] **Step 7.2: Implementacion en pages.py**

```python
async def fetch_dmz() -> dict[str, str]:
    """Lee app_dmz_conf_t.gch."""
    html = await http_client.fetch_html("app_dmz_conf_t.gch")
    raw = parse_transfer_meaning(html)
    return {
        "enabled": raw.get("Enable", ""),
        "internal_host": raw.get("InternalHost", ""),
        "internal_mac": raw.get("InternalMacHost", ""),
    }
```

- [ ] **Step 7.3: Implementacion en formatters.py**

```python
def format_dmz(data: dict[str, str]) -> str:
    status = _onoff(data.get("enabled", ""))
    host = _val(data, "internal_host")
    mac = _val(data, "internal_mac")
    note = "" if data.get("enabled") == "1" else " (configurado pero inactivo)"
    return (
        "ZTE F680 - DMZ\n"
        f"  Estado:        {status}{note}\n"
        f"  Host destino:  {host}\n"
        f"  MAC destino:   {mac}"
    )
```

- [ ] **Step 7.4: Tool en server.py**

```python
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
```

- [ ] **Step 7.5: Tests + smoke + commit**

```bash
pytest tests/ -v
python -c "import asyncio; from zte_f680_mcp.server import zte_get_dmz; print(asyncio.run(zte_get_dmz()))"
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_dmz

Estado DMZ + host/MAC destino. Indica si esta activa o solo configurada.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Tool `zte_get_wan_status` (con exploración previa)

El fixture de `IPv46_status_wan_if_t.gch` fue capturado en Task 0 pero la página no respondió a `parse_transfer_meaning` en la exploración inicial. Aquí confirmamos qué formato usa y ajustamos.

**Files:**
- Modify: `src/zte_f680_mcp/pages.py`
- Modify: `src/zte_f680_mcp/formatters.py`
- Modify: `src/zte_f680_mcp/server.py`
- Modify: `tests/test_pages.py`
- Modify: `tests/test_formatters.py`

- [ ] **Step 8.1: Inspeccionar el fixture**

```bash
cd C:/Users/Alberto/Documents/code_claude/ROUTER_CASA
python -c "
html = open('tests/fixtures/IPv46_status_wan_if_t.html', encoding='utf-8').read()
print('tamaño:', len(html))
import re
# Intento formato A
a = re.findall(r\"Transfer_meaning\\('(\\w+)'\\s*,\\s*'([^']*)'\\)\", html)
print('Transfer_meaning matches:', len(a))
for k, v in a[:20]:
    print(' ', k, '=', v[:60])
# Intento formato B
b = re.findall(r'<td\\s+class=\"tdleft\">\\s*([^<]+?)\\s*</td>\\s*<td\\s+id=\"(Frm_[^\"]+)\"', html)
print('Frm_* matches:', len(b))
for label, name in b[:20]:
    print(' ', label, '->', name)
"
```

Según lo que devuelva:

- **Si aparecen `Transfer_meaning`** (formato A) → whitelist a extraer: `WANIPAddress`, `WANSubnetMask`, `DefaultGateway`, `DNSServer1`, `DNSServer2`, `MACAddress`, `Uptime`, `ConnectionStatus`, `ConnectionType`. Usar `parse_transfer_meaning`.
- **Si aparecen `Frm_*`** (formato B) → whitelist `Frm_WanIp`, `Frm_WanMask`, `Frm_DefGw`, `Frm_Dns1`, `Frm_Dns2`, `Frm_MacAddr`, `Frm_Uptime`, etc. Usar `parse_frm_table`.
- **Si no aparece ninguno** → la página usa un tercer formato. Documentar limitación en el CLAUDE.md y devolver error claro desde la tool: `"Error: WAN status no soportado en este firmware. Usa zte_run_page(page_name='IPv46_status_wan_if_t.gch', raw=True) para ver HTML crudo y abrir issue."`. La tool se implementa igual (para no romper la API) pero con el mensaje de fallback hasta encontrar el patrón correcto.

- [ ] **Step 8.2: Implementación según el resultado (caso A — Transfer_meaning)**

`pages.py`:

```python
_WAN_WHITELIST_A = {
    "WANIPAddress": "public_ip",
    "WANSubnetMask": "subnet_mask",
    "DefaultGateway": "gateway",
    "DNSServer1": "dns1",
    "DNSServer2": "dns2",
    "MACAddress": "wan_mac",
    "Uptime": "uptime_seconds",
    "ConnectionStatus": "status",
    "ConnectionType": "conn_type",
}


async def fetch_wan_status() -> dict[str, str]:
    """Lee IPv46_status_wan_if_t.gch. Whitelist se ajusto durante Task 8.1."""
    html = await http_client.fetch_html("IPv46_status_wan_if_t.gch")
    raw = parse_transfer_meaning(html)
    if not raw:
        raw_b = parse_frm_table(html)
        if not raw_b:
            # Firmware distinto - error claro
            return {"_unsupported": "1"}
        # Fallback formato B: re-mapear claves Frm_*
        return {
            "public_ip": raw_b.get("Frm_WanIp", ""),
            "subnet_mask": raw_b.get("Frm_WanMask", ""),
            "gateway": raw_b.get("Frm_DefGw", ""),
            "dns1": raw_b.get("Frm_Dns1", ""),
            "dns2": raw_b.get("Frm_Dns2", ""),
            "wan_mac": raw_b.get("Frm_MacAddr", ""),
            "uptime_seconds": raw_b.get("Frm_Uptime", ""),
            "status": raw_b.get("Frm_Status", ""),
            "conn_type": raw_b.get("Frm_ConnType", ""),
        }
    return {clean: raw.get(orig, "") for orig, clean in _WAN_WHITELIST_A.items()}
```

- [ ] **Step 8.3: Test (saltar si la página no es parseable)**

```python
@pytest.mark.asyncio
async def test_fetch_wan_status(mock_fetch, html_wan_status):
    mock_fetch({"IPv46_status_wan_if_t.gch": html_wan_status})
    data = await pages.fetch_wan_status()
    if data.get("_unsupported"):
        pytest.skip("WAN status no soportado en este firmware")
    # Al menos algun campo tiene que aparecer
    assert any(v for v in data.values()), "fetch_wan_status devolvio todo vacio"
```

- [ ] **Step 8.4: Formatter**

```python
def format_wan_status(data: dict[str, str]) -> str:
    if data.get("_unsupported"):
        return (
            "ZTE F680 - WAN\n"
            "  No se pudo parsear IPv46_status_wan_if_t.gch en este firmware.\n"
            "  Usa zte_run_page(page_name='IPv46_status_wan_if_t.gch', "
            "raw=True) para ver el HTML crudo."
        )
    lines = [
        "ZTE F680 - Estado WAN",
        f"  IP publica:     {_val(data, 'public_ip')}",
        f"  Mascara:        {_val(data, 'subnet_mask')}",
        f"  Gateway:        {_val(data, 'gateway')}",
        f"  DNS:            {_val(data, 'dns1')} / {_val(data, 'dns2')}",
        f"  MAC WAN:        {_val(data, 'wan_mac')}",
        f"  Tipo conexion:  {_val(data, 'conn_type')}",
        f"  Estado:         {_val(data, 'status')}",
    ]
    uptime = data.get("uptime_seconds", "")
    if uptime:
        lines.append(f"  Uptime:         {_human_seconds(uptime)}")
    return "\n".join(lines)
```

- [ ] **Step 8.5: Tool en server.py**

```python
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
```

- [ ] **Step 8.6: Smoke + commit**

```bash
python -c "import asyncio; from zte_f680_mcp.server import zte_get_wan_status; print(asyncio.run(zte_get_wan_status()))"
pytest tests/ -v
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/src/zte_f680_mcp/ ROUTER_CASA/tests/
git commit -m "$(cat <<'EOF'
feat(zte-mcp): tool zte_get_wan_status (IP publica, DNS, uptime WAN)

Con fallback a formato Frm_* si la pagina no trae Transfer_meaning, y
mensaje claro si el firmware usa un tercer formato no soportado.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Bump versión, actualizar docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/zte_f680_mcp/__init__.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/changelog.md`

- [ ] **Step 9.1: Bump versión a 0.3.0**

En `pyproject.toml`:
```toml
version = "0.3.0"
```

En `src/zte_f680_mcp/__init__.py`:
```python
__version__ = "0.3.0"
```

- [ ] **Step 9.2: Actualizar README.md**

Añadir en la sección de tools (entre `zte_delete_port_forward` y `zte_run_page`):

```markdown
- `zte_get_device_info` — modelo, serie, firmware, hardware, bootloader, chipsets WiFi
- `zte_get_wan_status` — IP pública, DNS, MAC WAN, tipo de conexión, uptime
- `zte_get_wifi_info` — ambas bandas (SSID, canal, clave PSK real, BSSID, stats)
- `zte_get_dhcp_leases` — dispositivos conectados (IP, MAC, hostname, conexión)
- `zte_get_dmz` — estado DMZ y host destino
- `zte_get_wifi_clients` — clientes WiFi asociados con RSSI (señal)
```

- [ ] **Step 9.3: Actualizar CLAUDE.md**

Añadir las 6 tools nuevas a la sección "Herramientas MCP". Actualizar "Estado actual" con v0.3.0.

- [ ] **Step 9.4: Añadir entrada en `docs/changelog.md`**

```markdown
## 2026-04-17 - v0.3.0 — Fase 1: lectura formateada

Añadidas 6 tools de solo lectura con salida en texto bonito:
- `zte_get_device_info` (status_dev_info_t.gch, formato Frm_*)
- `zte_get_wan_status` (IPv46_status_wan_if_t.gch)
- `zte_get_wifi_info` (net_wlanm_secrity{1,2}_t.gch, incluye PSK real)
- `zte_get_dhcp_leases` (net_dhcp_dynamic_t.gch)
- `zte_get_dmz` (app_dmz_conf_t.gch)
- `zte_get_wifi_clients` (misma página DHCP, con RSSI)

Refactor a 5 módulos: `http_client`, `parsers`, `pages`, `formatters`,
`server`. Tests unitarios contra fixtures HTML reales.
Spec: `docs/superpowers/specs/2026-04-17-zte-fase1-lectura-formateada-design.md`.
```

- [ ] **Step 9.5: Commit**

```bash
cd C:/Users/Alberto/Documents/code_claude
git add ROUTER_CASA/pyproject.toml ROUTER_CASA/src/zte_f680_mcp/__init__.py ROUTER_CASA/README.md ROUTER_CASA/CLAUDE.md ROUTER_CASA/docs/changelog.md
git commit -m "$(cat <<'EOF'
release(zte-mcp): v0.3.0 - Fase 1 lectura formateada

Bump a 0.3.0. Docs actualizados con las 6 tools nuevas.

Co-Authored-By: Alberto Diaz <informatica@hcmarbella.com>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Publicación (TestPyPI + PyPI + GitHub)

Delegable al skill `publish-mcp` cuando llegue este punto. Si se hace manual:

**Files:**
- Generados: `dist/zte_f680_mcp-0.3.0-py3-none-any.whl`, `dist/zte_f680_mcp-0.3.0.tar.gz`

- [ ] **Step 10.1: Build**

```bash
cd C:/Users/Alberto/Documents/code_claude/ROUTER_CASA
rm -rf dist/
python -m build
twine check dist/*
```

Expected: `PASSED` para wheel y sdist.

- [ ] **Step 10.2: Upload a TestPyPI**

```bash
twine upload --repository testpypi dist/*
```

- [ ] **Step 10.3: Validar instalación desde TestPyPI**

```bash
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zte-f680-mcp@0.3.0 --help
```

Expected: arranca (si requiere `.env` fallará en login, pero el comando no debe crashear con ImportError).

- [ ] **Step 10.4: Upload a PyPI real**

```bash
twine upload dist/*
```

- [ ] **Step 10.5: Validar desde PyPI real**

```bash
uvx --refresh zte-f680-mcp@0.3.0 --help
```

- [ ] **Step 10.6: Sync a repo GitHub público**

Según lección 10 del CLAUDE.md global: clonar aparte `Picaresco/MCP-ZTE-F680`, `cp -r` los ficheros nuevos/modificados, commit + push, crear release v0.3.0.

- [ ] **Step 10.7: Tag local + commit final**

```bash
cd C:/Users/Alberto/Documents/code_claude
git tag -a zte-mcp-v0.3.0 -m "ZTE F680 MCP v0.3.0 - Fase 1 lectura formateada"
```

---

## Checklist final de verificación

- [ ] `pytest tests/ -v` → todos los tests pasan (estimado ~20-25 tests).
- [ ] `python -c "from zte_f680_mcp.server import mcp; print(mcp)"` → OK.
- [ ] Cada una de las 6 tools nuevas produce salida bonita contra el router real.
- [ ] Las 7 tools existentes (port forwarding) siguen funcionando sin cambios.
- [ ] `server.py` ≤ 500 líneas.
- [ ] `uvx zte-f680-mcp@0.3.0` funciona en instalación limpia.
- [ ] README, CLAUDE.md y changelog actualizados.
- [ ] Release publicado en PyPI + GitHub.
