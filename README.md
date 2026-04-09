# MCP-ZTE-F680

![MCP-ZTE-F680 Banner](assets/banner.png)

MCP Server (Model Context Protocol) para gestionar NAT/port forwarding en un router **ZTE ZXHN F680** (GPON ONT) desde cualquier agente IA compatible con MCP.

**Compatible con:** Claude Code, OpenAI Agents, Gemini CLI, Cursor, Windsurf, Copilot y otros clientes MCP.

## Que hace

Controla las reglas de redireccion de puertos (port forwarding) del router ZTE F680 a traves de su interfaz web HTTP, sin necesidad de abrir el navegador.

### Herramientas disponibles

| Herramienta | Descripcion |
|---|---|
| `zte_get_port_forwards` | Lista todas las reglas NAT configuradas |
| `zte_add_port_forward` | Anade una nueva regla de redireccion de puertos |
| `zte_modify_port_forward` | Modifica una regla existente por su indice |
| `zte_delete_port_forward` | Elimina una regla por su indice |
| `zte_run_page` | Obtiene y parsea cualquier pagina del router (generico) |

## Requisitos

- Python 3.11+
- Router ZTE ZXHN F680 accesible en la red local
- Credenciales de acceso al panel web del router

## Instalacion

### 1. Clonar el repositorio

```bash
git clone https://github.com/Picaresco/MCP-ZTE-F680.git
cd MCP-ZTE-F680
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copiar el fichero de ejemplo y editar con tus credenciales:

```bash
cp .env.example .env
```

Editar `.env` con los datos de tu router:

```env
ZTE_HOST=192.168.1.1
ZTE_USER=1234
ZTE_PASSWORD=tu_password_aqui
```

> **Nota:** El fichero `.env` contiene credenciales y esta excluido del repositorio via `.gitignore`. Nunca subas tus credenciales reales.

### 4. Registrar en tu cliente MCP

**Claude Code:**
```bash
claude mcp add zte "/ruta/al/proyecto/venv/Scripts/python.exe" "/ruta/al/proyecto/zte_mcp_server.py"
```

**Otros clientes MCP (Cursor, Windsurf, etc.):** Configurar como servidor stdio apuntando al mismo comando.

### 5. Verificar

```bash
claude mcp list
# Debe mostrar: zte: ... - Connected
```

## Uso

Una vez registrado, las herramientas estan disponibles directamente desde tu agente IA:

```
> Lista las reglas NAT de mi router ZTE
> Abre el puerto 8080 TCP hacia 192.168.1.100
> Borra la regla de port forwarding numero 2
```

## Notas tecnicas

- **Autenticacion**: SHA256(password + random) con tokens dinamicos (`Frm_Logintoken`, `Frm_Loginchecktoken`)
- **Sesion**: Expira ~60s idle. El servidor re-autentica automaticamente cada 45s
- **Anti-CSRF**: Cada operacion de escritura requiere un `_SESSION_TOKEN` fresco obtenido de la pagina
- **Protocolo**: `0` = TCP+UDP, `1` = UDP, `2` = TCP
- **Transporte MCP**: stdio

## Stack

- Python 3.11
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) (mcp[cli])
- httpx (HTTP async client)
- python-dotenv
- pydantic

## Licencia

MIT
