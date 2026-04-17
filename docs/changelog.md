## 2026-04-17 - v0.3.0 — Fase 1: lectura formateada

Anadidas 6 tools de solo lectura con salida en texto bonito:
- `zte_get_device_info` (status_dev_info_t.gch, formato Frm_*)
- `zte_get_wan_status` (IPv46_status_wan_if_t.gch, formato C td/tdright)
- `zte_get_wifi_info` (net_wlanm_secrity{1,2}_t.gch, incluye PSK real)
- `zte_get_dhcp_leases` (net_dhcp_dynamic_t.gch)
- `zte_get_dmz` (app_dmz_conf_t.gch)
- `zte_get_wifi_clients` (misma pagina DHCP, con RSSI)

Refactor a 5 modulos: http_client, parsers, pages, formatters, server.
Nuevo parser parse_tdright_table para formato C (tablas td sin Frm_*).
32 tests unitarios contra fixtures HTML reales.
Spec: docs/superpowers/specs/2026-04-17-zte-fase1-lectura-formateada-design.md

## 2026-04-15 (post-v0.2.0 housekeeping)

### Docs
- `README.md`: recomendacion de `uvx zte-f680-mcp@latest` en lugar de `uvx zte-f680-mcp` -> auto-update en cada arranque. Anadida seccion "Upgrading existing installs" con `uvx --refresh` y `uv cache clean`.
- `CLAUDE.md`: bloque de "Comandos" actualizado para reflejar `@latest` y refresh manual.

### GitHub
- Histoira reescrita con `git filter-branch` para unificar todos los autores a `Alberto Diaz <albertodiazalba@gmail.com>` y mantener solo a Claude como co-author (eliminadas asociaciones a hcmarbella / hotmail). Force-push + retagging v0.1.0/v0.2.0.
- Registro local de MCP re-creado con `uvx zte-f680-mcp@latest`.

### Infraestructura cross-proyecto (aplicable a todos los MCPs futuros)
- **Skill nuevo**: `~/.claude/skills/publish-mcp/SKILL.md` (250 lineas) - automatiza el pipeline completo: scaffold -> build -> TestPyPI -> PyPI -> GitHub release -> registro en Claude Code -> docs.
- **Memoria nueva**: `reference_mcp_publishing.md` (type=reference) con cuentas, ubicacion de tokens (`.pypirc` + keyring de `gh`), convenciones de naming y layout estandar. Indexada en `MEMORY.md`.
- `feedback_coauthor.md` reescrito: autor principal `albertodiazalba@gmail.com`, solo Claude como co-author.

## 2026-04-15 (v0.2.0)

### Release
- `zte-f680-mcp 0.2.0` publicado en TestPyPI y PyPI real
- GitHub release: https://github.com/Picaresco/MCP-ZTE-F680/releases/tag/v0.2.0

### Features anadidas
- Tool `zte_open_port(port, protocol="TCP+UDP", internal_host=None, internal_port=None, name=None)`: flujo rapido con defaults (auto IP local, mismo puerto en ambos lados, nombre auto-generado)
- Tool `zte_get_local_ip()`: devuelve IP del host en la subred del router (cross-platform, multi-homed aware)
- Helper privado `_get_local_ip_for(target)` con truco UDP+connect+getsockname (no envia paquetes)
- Helper privado `_create_port_forward(...)` extraido para compartir entre `zte_add_port_forward` y `zte_open_port` (DRY)
- Campo `instructions=` del FastMCP extendido con flujo conversacional ("abre el puerto X" -> detectar IP -> confirmar -> abrir)

### Ficheros modificados
- `src/zte_f680_mcp/server.py`: +212/-48 lineas
- `src/zte_f680_mcp/__init__.py`: bump `__version__` a "0.2.0"
- `pyproject.toml`: bump version a 0.2.0

### Compatibilidad
Fully backwards compatible. Firmas de tools existentes sin cambios. No hay nuevas dependencias (todo con `socket` del stdlib).

## 2026-04-15

### Files updated
- CLAUDE.md: reescrito para reflejar refactor a paquete PyPI (layout src/, pyproject.toml, entry point consola, distribucion via uvx). Anadidos "Estructura del proyecto", "Problemas resueltos" (distribucion y monorepo git), "Proximos pasos".
- README.md: ya actualizado esta sesion (banner restaurado al principio, instrucciones `uvx zte-f680-mcp` para Claude Desktop/Code/Cursor/Windsurf/Cline/OpenAI Agents SDK/pip)
- Global `~/.claude/CLAUDE.md`: entry del MCP `zte` actualizado a "publicado en PyPI, instalable con uvx". Anadidas 3 lecciones (distribucion de MCPs Python, cuentas TestPyPI/PyPI separadas, sync monorepo->repo publico)
- MEMORY.md: entry ROUTER_CASA anadido "Publicado en PyPI: uvx zte-f680-mcp"

### Files created
- `LICENSE` (MIT, Alberto Diaz)
- `pyproject.toml` (hatchling, entry point consola `zte-f680-mcp`)
- `src/zte_f680_mcp/__init__.py`, `src/zte_f680_mcp/server.py` (refactor del antiguo `zte_mcp_server.py`)
- Publicado `zte-f680-mcp 0.1.0` en TestPyPI y PyPI real
- GitHub release `v0.1.0`

### Files deleted
- `zte_mcp_server.py` en raiz (movido a `src/zte_f680_mcp/server.py`, rename preservado por git)
- `requirements.txt` (reemplazado por `[project.dependencies]` en `pyproject.toml`)

### Cross-reference fixes
- Referencias a `zte_mcp_server.py` en CLAUDE.md -> `src/zte_f680_mcp/server.py`
- Referencias a `requirements.txt` en CLAUDE.md -> `pyproject.toml`

### Improvements identified
- Montar GitHub Actions con Trusted Publishing (OIDC) para release automatico al hacer `git tag v*`
- Tests unitarios para `_parse_rules()` y `_decode_hex_escapes()` (pytest, no requiere router)
- Badges en README (version PyPI, downloads, license)
- Revocar tokens PyPI/TestPyPI actuales (scope "Entire account") y crear con scope limitado a `zte-f680-mcp`
- Archivar `poc_*.py` en `docs/dev/` o eliminarlos

## 2026-04-10

### Files updated
- CLAUDE.md: Reescrito completo — anadido timestamp, archivos clave, mecanica de auth, decisiones de arquitectura, estado actual, notas tecnicas
- README.md: Ya estaba actualizado (subido a GitHub con banner)
- Global CLAUDE.md: Anadido MCP zte + 2 lecciones aprendidas (Frm_Logintoken, chrome-extension IPs locales)
- MEMORY.md: Anadido proyecto ROUTER_CASA con link a GitHub

### Files created
- docs/changelog.md (este fichero)

### Cross-reference fixes
- Ninguno necesario (proyecto nuevo, todas las referencias correctas)

### Improvements identified
- linkedin_banner.html no esta en .gitignore pero tampoco commiteado — considerar anadir al repo o al ignore
- PoC files (poc_*.py) podrian archivarse o eliminarse tras validacion completa
- Considerar anadir tests unitarios para _parse_rules() y _decode_hex_escapes()
