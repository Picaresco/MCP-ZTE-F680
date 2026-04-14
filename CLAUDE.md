> Ultima actualizacion: 2026-04-10

# ROUTER_CASA - MCP Server ZTE F680

## Descripcion
MCP server (Python/FastMCP) para gestionar NAT/port forwarding en un router ZTE ZXHN F680 via su interfaz web HTTP.

## Stack y dependencias
- Python 3.11 + FastMCP (mcp[cli]) + httpx + python-dotenv + pydantic
- Transporte: stdio
- Auth: SHA256(password + random) + 3 tokens dinamicos

## Archivos clave
- `zte_mcp_server.py` - Servidor MCP completo (581 lineas): auth, sesion, parseo HTML, 5 tools
- `requirements.txt` - Dependencias: mcp[cli], httpx, python-dotenv, pydantic
- `.env` - Credenciales (en .gitignore, nunca en codigo)
- `.env.example` - Plantilla de configuracion
- `linkedin_banner.html` - Banner visual del proyecto para redes/README

## Herramientas MCP
- `zte_get_port_forwards` - Lista reglas NAT (read-only)
- `zte_add_port_forward` - Anade regla (nombre, protocolo, puertos, IP destino)
- `zte_modify_port_forward` - Modifica regla existente por indice
- `zte_delete_port_forward` - Borra regla por indice (destructive)
- `zte_run_page` - Generico: obtiene cualquier pagina del router

## Mecanica
1. Login: GET / -> extraer Frm_Logintoken + Frm_Loginchecktoken -> SHA256(pass+random) -> POST /
2. Sesion: cookie SID, expira ~60s idle, re-login automatico a los 45s
3. Lectura: GET getpage.gch?pid=1002&nextpage=X -> parsear Transfer_meaning('FieldN','val')
4. Escritura: GET pagina (obtener _SESSION_TOKEN) -> POST con token + IF_ACTION (new/apply/delete)

## Configuracion
Variables de entorno en `.env`:
- `ZTE_HOST` - IP del router (default: 192.168.1.1)
- `ZTE_USER` - Usuario login (default: 1234)
- `ZTE_PASSWORD` - Contrasena (requerida)

## Comandos
```bash
# Instalar
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
# Registrar en Claude Code
claude mcp add zte "<ruta>/venv/Scripts/python.exe" "<ruta>/zte_mcp_server.py"
# Verificar
claude mcp list
```

## Estado actual
Operativo. Login, lectura y CRUD de reglas NAT validados via PoC y en produccion.
Repo publico: https://github.com/Picaresco/MCP-ZTE-F680

## Decisiones de arquitectura
- Fichero unico: mismo patron que mikrotik_mcp_server.py, simple y portable
- httpx AsyncClient global: mantiene cookies de sesion entre llamadas
- Regex sobre HTML (no BeautifulSoup): Transfer_meaning es regular, sin dependencia extra
- _SESSION_TOKEN fresco por cada POST: el router lo exige como anti-CSRF

## Notas tecnicas
- Protocolo NAT: 0=TCP+UDP, 1=UDP, 2=TCP
- WAN interface fija: IGD.WD1.WCD1.WCIP1
- Frm_Logintoken cambia en cada carga (NO es fijo "1")
- Bloqueo por 3 intentos fallidos: auto-detecta y espera 60s+2
