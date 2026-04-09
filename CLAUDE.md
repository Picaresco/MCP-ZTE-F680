# ROUTER_CASA - MCP Server ZTE F680

## Que es
MCP server (Python/FastMCP) para gestionar NAT/port forwarding en un router ZTE ZXHN F680 via su interfaz web HTTP.

## Stack
- Python 3.11 + FastMCP (mcp[cli]) + httpx + python-dotenv + pydantic
- Transporte: stdio
- Auth: SHA256(password + random) + tokens dinamicos (Frm_Logintoken + Frm_Loginchecktoken + _SESSION_TOKEN)

## Herramientas MCP
- `zte_get_port_forwards` - Lista reglas NAT
- `zte_add_port_forward` - Anade regla (nombre, protocolo, puertos, IP destino)
- `zte_modify_port_forward` - Modifica regla existente por indice
- `zte_delete_port_forward` - Borra regla por indice
- `zte_run_page` - Generico: obtiene cualquier pagina del router

## Config
Credenciales en `.env` (nunca en codigo). Ver `.env.example`.

## Registro en Claude Code
```
claude mcp add zte "<ruta>/venv/Scripts/python.exe" "<ruta>/zte_mcp_server.py"
```

## Notas tecnicas
- Sesion expira ~60s idle, re-login automatico a los 45s
- Cada POST de escritura requiere _SESSION_TOKEN fresco (anti-CSRF)
- Protocolo: 0=TCP+UDP, 1=UDP, 2=TCP
- WAN interface fija: IGD.WD1.WCD1.WCIP1
