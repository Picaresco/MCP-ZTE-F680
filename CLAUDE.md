> Ultima actualizacion: 2026-04-17 (v0.3.0)

# ROUTER_CASA - MCP Server ZTE F680

## Descripcion
MCP server (Python/FastMCP) para gestionar NAT/port forwarding en un router ZTE ZXHN F680 via su interfaz web HTTP. Publicado en PyPI como `zte-f680-mcp`, instalable con un solo comando (`uvx zte-f680-mcp`) desde cualquier cliente MCP (Claude Desktop, Claude Code, Cursor, Windsurf, Cline, OpenAI Agents SDK, etc.).

## Stack y dependencias
- Python 3.10+ (runtime) / FastMCP (`mcp[cli]`), httpx async, python-dotenv, pydantic
- Build backend: hatchling (PEP 621 via pyproject.toml)
- Distribucion: PyPI + TestPyPI. Transporte MCP: stdio
- Auth: SHA256(password + random) + tokens dinamicos (Frm_Logintoken, Frm_Loginchecktoken)

## Estructura del proyecto
```
ROUTER_CASA/
├── pyproject.toml              # Metadata + deps + entry point (hatchling)
├── LICENSE                     # MIT - Alberto Diaz
├── README.md                   # Publico: install en todos los clientes MCP
├── CLAUDE.md                   # Este fichero
├── .env.example                # Plantilla de credenciales
├── .gitignore
├── src/
│   └── zte_f680_mcp/
│       ├── __init__.py         # Expone main(), __version__
│       ├── server.py           # Tools MCP + lifespan (~640 lineas tras v0.3.0)
│       ├── http_client.py      # v0.3.0: sesion HTTP, login, fetch_html
│       ├── parsers.py          # v0.3.0: regex puros (formatos A, B, C)
│       ├── pages.py            # v0.3.0: fetch_X por pagina (dict limpio)
│       └── formatters.py       # v0.3.0: format_X (dict -> texto bonito)
├── tests/
│   ├── conftest.py             # v0.3.0: fixtures HTML del router
│   ├── fixtures/               # 6 HTML reales capturados
│   ├── test_parsers.py         # 18 tests unitarios
│   ├── test_pages.py           # 6 tests con monkeypatch
│   └── test_formatters.py      # 8 tests de formato
├── scripts/
│   └── capture_fixtures.py     # Regenera fixtures desde el router real
├── docs/
│   ├── changelog.md            # Historial de actualizaciones /actualiza
│   └── superpowers/            # Specs y plans de fases (v0.3.0+)
├── assets/
│   └── banner.png              # Banner del README (1498x781)
├── dist/                       # Wheels + sdist generados (gitignored)
└── venv/                       # Solo desarrollo local (gitignored)
```
Nota: `src/zte_f680_mcp/server.py` es el mismo codigo que antes vivia suelto como `zte_mcp_server.py`; el historial se preservo con git rename.

## Herramientas MCP
- `zte_get_port_forwards` - Lista reglas NAT (read-only)
- `zte_open_port` - v0.2.0: abre un puerto con defaults inteligentes (IP local auto-detectada + mismo puerto en ambos lados)
- `zte_get_local_ip` - v0.2.0: IP local del host en la subred del router (truco UDP+connect+getsockname, cross-platform)
- `zte_add_port_forward` - Anade regla con control total (rangos, IP y puerto interno arbitrarios)
- `zte_modify_port_forward` - Modifica regla existente por indice
- `zte_delete_port_forward` - Borra regla por indice (destructive)
- `zte_get_device_info` - v0.3.0: modelo, serie, firmware, hardware, bootloader, chipsets WiFi
- `zte_get_wan_status` - v0.3.0: IP publica, DNS, MAC WAN, tipo de conexion, uptime
- `zte_get_wifi_info` - v0.3.0: ambas bandas (SSID, canal, clave PSK real, BSSID, stats)
- `zte_get_dhcp_leases` - v0.3.0: dispositivos conectados (IP, MAC, hostname, conexion)
- `zte_get_dmz` - v0.3.0: estado DMZ y host destino
- `zte_get_wifi_clients` - v0.3.0: clientes WiFi asociados con RSSI (senal)
- `zte_run_page` - Generico: obtiene cualquier pagina del router

## Flujo conversacional (v0.2.0)
El campo `instructions=` del FastMCP guia al LLM:
1. Usuario: "abre el puerto X".
2. LLM llama `zte_get_local_ip` -> obtiene IP.
3. LLM pregunta al usuario: "Redirijo X -> <IP>:X?".
4. Confirmacion -> `zte_open_port(port=X)`. Otro puerto/IP -> `zte_add_port_forward`.

## Mecanica
1. Login: GET / -> extraer Frm_Logintoken + Frm_Loginchecktoken -> SHA256(pass+random) -> POST /
2. Sesion: cookie SID, expira ~60s idle, re-login automatico a los 45s
3. Lectura: GET getpage.gch?pid=1002&nextpage=X -> parsear Transfer_meaning('FieldN','val')
4. Escritura: GET pagina (obtener _SESSION_TOKEN) -> POST con token + IF_ACTION (new/apply/delete)

## Configuracion
Variables de entorno (via `.env` local o bloque `env` del cliente MCP):
- `ZTE_HOST` - IP del router (default: 192.168.1.1)
- `ZTE_USER` - Usuario login (default: 1234)
- `ZTE_PASSWORD` - Contrasena (requerida)

## Comandos

### Usuario final (cualquier cliente MCP)
```bash
# uvx descarga el paquete + deps, crea venv aislado, lo ejecuta
# @latest -> revalida contra PyPI en cada arranque (auto-update)
uvx zte-f680-mcp@latest

# Registro en Claude Code:
claude mcp add zte \
  --env ZTE_HOST=192.168.1.1 \
  --env ZTE_USER=1234 \
  --env ZTE_PASSWORD=xxx \
  -- uvx zte-f680-mcp@latest

# Refresh manual si omitiste @latest:
#   uv cache clean zte-f680-mcp   (o)   uvx --refresh zte-f680-mcp
```

### Desarrollo local
```bash
# Instalacion editable (reflejo directo de cambios)
python -m venv venv && venv\Scripts\activate
pip install -e .

# Build + publicacion (requiere .pypirc con tokens)
python -m build
twine check dist/*
twine upload --repository testpypi dist/*   # TestPyPI
twine upload dist/*                         # PyPI real
```

## Estado actual
Operativo y publicado. v0.3.0 en desarrollo (Fase 1: lectura formateada, 6 tools nuevos read-only). v0.2.0 disponible en PyPI (`pip install zte-f680-mcp`) con NAT/port forwarding CRUD. Validado extremo-a-extremo: instalacion desde PyPI real via `uvx`, conexion a router, login, listado real de reglas NAT.

- **PyPI**: https://pypi.org/project/zte-f680-mcp/
- **GitHub**: https://github.com/Picaresco/MCP-ZTE-F680
- **Release v0.2.0**: https://github.com/Picaresco/MCP-ZTE-F680/releases/tag/v0.2.0

## Decisiones de arquitectura
- Layout `src/` (PEP 621) + hatchling: estandar moderno, sin setup.py
- Entry point consola `zte-f680-mcp = "zte_f680_mcp.server:main"` -> compatible con `uvx`/`pipx`
- httpx AsyncClient global: mantiene cookies de sesion entre llamadas
- Regex sobre HTML (no BeautifulSoup): Transfer_meaning es regular, evita dependencia extra
- `_SESSION_TOKEN` fresco por cada POST: el router lo exige como anti-CSRF
- Licencia MIT: maxima adopcion por cualquier cliente MCP

## Notas tecnicas
- Protocolo NAT: `0=TCP+UDP`, `1=UDP`, `2=TCP`
- WAN interface fija: `IGD.WD1.WCD1.WCIP1`
- `Frm_Logintoken` cambia en cada carga (NO es fijo "1")
- Bloqueo por 3 intentos fallidos: auto-detecta y espera `60s + 2`
- `.pypirc` vive en `%USERPROFILE%\.pypirc` (fuera del repo) con tokens TestPyPI + PyPI

## Problemas resueltos
- **Distribucion**: antes requeria clonar repo + venv + registrar ruta absoluta al script. Ahora: una linea `uvx zte-f680-mcp`, funciona offline tras primera ejecucion.
- **Monorepo git**: el `.git` vive en `code_claude/`, no en `ROUTER_CASA/`. Para publicar al repo publico `Picaresco/MCP-ZTE-F680` se clona aparte y se sincroniza.

## Posibles mejoras
- GitHub Actions con Trusted Publishing (OIDC) para publicar v0.x.y automaticamente al hacer `git tag`
- Badges en README: version PyPI, downloads, license
- Revocar y rotar tokens PyPI/TestPyPI a scope limitado al proyecto (ahora son "Entire account")
- PoC files (`poc_*.py`) en raiz del working dir: archivar o mover a `docs/dev/` tras validacion
- Fases siguientes del plan maestro: 2 (descubrimiento), 3 (escritura basica), 4 (escritura avanzada), 5 (mantenimiento)

## Proximos pasos
1. Revocar tokens globales y crear unos con scope `zte-f680-mcp` -> actualizar `.pypirc`
2. Montar Trusted Publishing en GitHub Actions (release automatico en push de tag `v*`)
3. Limpiar PoC files del working directory local
