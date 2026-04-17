# Fase 1 — Lectura formateada (ZTE F680 MCP)

> Spec de diseño · 2026-04-17 · versión objetivo: v0.3.0

## 1. Contexto y motivacion

El MCP `zte-f680-mcp` v0.2.0 cubre hoy NAT/port forwarding pero la lectura del resto del router se reduce a `zte_run_page`, que devuelve un volcado crudo de `Transfer_meaning('Campo','valor')`. El usuario tiene que leer decenas de campos con nombres internos.

Este spec cubre la **Fase 1** de un plan mayor para completar el MCP (Fase 2: descubrimiento; Fase 3: escritura basica; Fase 4: escritura avanzada; Fase 5: mantenimiento). Cada fase tiene su propio ciclo spec → plan → release.

**Objetivo de Fase 1**: 6 tools de lectura formateada que traducen jerga a lenguaje humano y presentan los datos en tablas legibles. Cero escritura, cero riesgo.

## 2. Alcance

**Dentro del alcance:**
- 6 tools MCP de solo lectura (ver seccion 4).
- Segundo parser para paginas tipo `Frm_*` con entidades HTML decimales.
- Refactor del codigo a 5 modulos con fronteras claras.
- Tests unitarios de parsers y formatters contra fixtures HTML capturados del router real.
- Release v0.3.0 en PyPI y TestPyPI.

**Fuera del alcance (Fases posteriores):**
- Cualquier tool de escritura (DMZ on/off, WiFi SSID, reboot, etc.).
- Descubrimiento automatico de paginas (`zte_list_pages`).
- Soporte para firmwares distintos al de Jazztel (`ZTEGF6804P1T28`). Tools con firmwares distintos pueden devolver "pagina no parseable" → se tolera pero no se cubre.
- Mock HTTP o tests de `http_client`/`pages` (demasiada fricción para Fase 1).

## 3. Arquitectura

### 3.1 Estructura de ficheros

```
src/zte_f680_mcp/
├── __init__.py              # sin cambios (expone main + __version__)
├── server.py                # lifespan + declaracion de tools
├── http_client.py           # NUEVO - sesion HTTP, login, fetch
├── parsers.py               # NUEVO - regex + decoders puros (sin I/O)
├── pages.py                 # NUEVO - una fetch_X por pagina funcional
└── formatters.py            # NUEVO - format_X (dict -> string bonito)

tests/
├── fixtures/                # NUEVO - HTML capturado del router
│   ├── status_dev_info_t.html
│   ├── net_wlanm_secrity1_t.html
│   ├── net_wlanm_secrity2_t.html
│   ├── net_dhcp_dynamic_t.html
│   ├── app_dmz_conf_t.html
│   └── IPv46_status_wan_if_t.html
├── test_parsers.py          # unitarios contra fixtures
└── test_formatters.py       # dict de entrada -> string esperado
```

### 3.2 Responsabilidades

| Modulo | Responsabilidad | Depende de |
|---|---|---|
| `http_client.py` | Login, mantenimiento de sesion, re-login a los 45s, fetch HTML por nombre de pagina. **Cero conocimiento de campos.** | `httpx`, env vars |
| `parsers.py` | Regex puras: extraer `Transfer_meaning`, extraer `Frm_*` + entidades HTML, agrupar tablas por sufijo numerico. **Sin I/O.** | `re` |
| `pages.py` | Orquesta fetch + parse por pagina funcional. Aplica whitelist. Devuelve dicts con claves limpias. | `http_client`, `parsers` |
| `formatters.py` | Dict limpio → texto bonito tipo tabla. | stdlib |
| `server.py` | Lifespan, declaracion de tools. Cada tool = `await fetch_X()` + `format_X()`. | `mcp`, todo lo anterior |

### 3.3 Flujo de datos (ejemplo: `zte_get_wifi_info`)

```
tool zte_get_wifi_info()
  └─> pages.fetch_wifi_info()
        ├─> http_client.fetch_html("net_wlanm_secrity1_t.gch")
        ├─> parsers.parse_transfer_meaning(html_24)
        ├─> http_client.fetch_html("net_wlanm_secrity2_t.gch")
        ├─> parsers.parse_transfer_meaning(html_5)
        └─> {"band_24": {campos limpios}, "band_5": {campos limpios}}
  └─> formatters.format_wifi_info(data) -> str bonito
```

## 4. Tools MCP de Fase 1

### 4.1 Resumen

| Tool | Paginas fuente | Formato HTML |
|---|---|---|
| `zte_get_device_info` | `status_dev_info_t.gch` | B (`Frm_*`) |
| `zte_get_wan_status` | `IPv46_status_wan_if_t.gch` | B (a confirmar en impl.) |
| `zte_get_wifi_info` | `net_wlanm_secrity1_t.gch` + `net_wlanm_secrity2_t.gch` | A (Transfer_meaning) |
| `zte_get_dhcp_leases` | `net_dhcp_dynamic_t.gch` | A + tabular |
| `zte_get_dmz` | `app_dmz_conf_t.gch` | A |
| `zte_get_wifi_clients` | `net_dhcp_dynamic_t.gch` (misma pagina que leases) | A + tabular (claves `ADMACAddressN`, `ADIPAddressN`, `RSSIN`...) |

**Nota:** `zte_get_wifi_info` usa `secrity{1,2}` en lugar de `conf{1,2}` porque `secrity` es un superconjunto: incluye **PSK real (`KeyPassphrase`)**, **BSSID** y stats de trafico, ademas de toda la config basica (canal, estandar, ancho, seguridad). Reduce llamadas HTTP de 4 a 2.

**Nota:** `WPAEAPSecret` y `Master*ServerSecret` se descartan explicitamente. Son placeholders del servidor RADIUS (valor por defecto `12345678`) irrelevantes en modo PSK y generan confusion.

### 4.2 Campos extraidos y transformaciones

#### `zte_get_device_info` — formato B
- **Campos**: `Frm_ModelName`, `Frm_SerialNumber`, `Frm_HardwareVer`, `Frm_SoftwareVer`, `Frm_BootVer`, `Frm_SoftwareVerExtent`, `Frm_WiFiVendor`, `Frm_WiFiModel`, `Frm_WiFiVersion`.
- **Transformacion**: decode `&#NNN;` → char. Strip espacios.
- **Ausentes**: uptime, CPU, RAM, MAC (esta pagina no los trae en este firmware). **No se falsean**: si no estan, no aparecen.

#### `zte_get_wan_status` — formato B (a confirmar)
- **Campos esperados** (validar en implementacion): IP publica, MAC WAN, estado de conexion, tipo (PPPoE/IPoE), DNS primario/secundario, uptime WAN.
- **Transformacion**: uptime segundos → `Xd Yh Zm`.
- **Plan B si la pagina no trae Transfer_meaning ni Frm_\***: capturar HTML crudo, analizar con subagent, ajustar whitelist. Es una desviacion aceptable dentro del mismo release.

#### `zte_get_wifi_info` — formato A ×2
- **Campos por banda**: ESSID, Channel, Band, Enable, RadioStatus, Standard, BandWidth, BeaconType, WPAAuthMode, WPAEncryptType, **KeyPassphrase** (PSK real), **Bssid**, ESSIDHideEnable, TxPower, MaxUserNum, AutoChannelEnabled, TotalBytesSent, TotalBytesReceived, TotalAssociations.
- **Transformacion**: bytes → MB/GB; `Enable` 0/1 → `ON/OFF`; `ESSIDHideEnable` 0/1 → `NO/SI`.
- **Salida**: dos bloques (2.4 GHz y 5 GHz) en una sola respuesta.

#### `zte_get_dhcp_leases` — formato A (mixto pool + tabla)
- **Pool**: `BasicIPAddr` (IP router), `MinAddress`, `MaxAddress`, `SubnetMask`, `DNSServer1`, `LeaseTime`.
- **Tabla** (claves indexadas `MACAddrN`, `IPAddrN`, `HostNameN`, `ExpiredTimeN`, `PhyPortNameN` con `N` de 0 a `IF_INSTNUM-1`): agrupar por sufijo.
- **Transformacion**:
  - `LeaseTime` segundos → `24h`.
  - `ExpiredTime` segundos restantes → `Xh Ym` (p. ej. `61837` → `17h 10m`).
  - `HostName` vacio → `—`.
  - `PhyPortName` → etiqueta humana: `LAN1-4` igual; `eth4` → `WiFi`; `SSID1-8` → `WiFi 2.4GHz` o `WiFi 5GHz` segun mapeo.

#### `zte_get_dmz` — formato A
- **Campos**: `Enable`, `InternalHost`, `InternalMacHost`.
- **Transformacion**: `Enable` 0/1 → `OFF/ON`; si `Enable=0` mostrar host como "configurado pero inactivo".

#### `zte_get_wifi_clients` — formato A tabular
- **Misma pagina** que `zte_get_dhcp_leases` (ahorra un GET si se invocan ambas seguidas, via cache).
- **Campos por cliente** (claves `ADMACAddressN`, `ADIPAddressN`, `RSSIN`, `TXRateN`, `RXRateN`, `CurrentModeN`, `SSIDNAMEN` con `N` < `ALLAD_INSTNUM`): MAC, IP, RSSI, TX/RX rate, modo (11ac/11n), SSID index.
- **Transformacion**:
  - `RSSI` → `-58 dBm (buena)`/`-77 dBm (regular)` via umbrales (`>-60`=buena, `-60..-75`=regular, `<-75`=debil).
  - `TXRate`/`RXRate` (kbps) → Mbps.
  - `SSIDNAME` (numero 1-8 interno del router) → banda + nombre: 1-4 = 2.4 GHz, 5-8 = 5 GHz. El SSID visible se obtiene cruzando con la ESSID de `zte_get_wifi_info` (reutiliza cache si ya se llamo en la misma sesion). Si el cruce no es posible, salida con banda + numero: `WiFi 5GHz (SSID7)`.

### 4.3 Ejemplos de salida (datos reales del router del usuario)

```
# zte_get_device_info
ZTE F680 - Informacion del dispositivo
  Modelo:         F680
  Serie:          ZTEEQERJ8L16414
  Firmware:       ZTEGF6804P1T28  (batch 07e4T10456)
  Hardware:       V4.0
  BootLoader:     V4.0.10
  WiFi chipsets:  2.4G Broadcom BCM43217 / 5G Quantenna QV840
```

```
# zte_get_wifi_info
WiFi 2.4 GHz
  SSID:        Casa_Chull_2g       Canal:     1 (manual)
  Estado:      ON                  Estandar:  g,n     Ancho: 20MHz
  Seguridad:   WPA/WPA2 AES        Clave:     ChullWapa$
  BSSID:       24:d3:f2:c6:97:b6   Oculta:    NO
  TxPower:     100%                Max clientes: 16
  Trafico:     TX 1.21 GB / RX 87 MB      Asociaciones: 1

WiFi 5 GHz
  SSID:        Casa_chull_5g       Canal:     100 (manual)
  ...
```

```
# zte_get_dhcp_leases
ZTE F680 - Dispositivos conectados (9 activos)
  Router:   192.168.1.1   Rango DHCP: .128-.149   Lease: 24h

  IP              MAC                 Hostname       Conexion       Expira
  192.168.1.128   e0:73:e7:2b:89:75   PC101          LAN1           17h 10m
  192.168.1.129   e8:5f:b4:01:d5:33   POCO-X6-5G     WiFi 5GHz      23h 08m
  192.168.1.130   56:90:e5:ef:55:45   —              WiFi           7h 17m
  ...
```

```
# zte_get_wifi_clients
Clientes WiFi asociados (3)
  MAC                 IP              SSID            Modo    Señal
  1e:74:40:88:bf:42   192.168.1.131   Casa_chull_5g   11ac    -58 dBm (buena)
  e6:ae:ed:e9:f6:f2   192.168.1.135   Casa_chull_5g   11ac    -77 dBm (regular)
  e8:5f:b4:01:d5:33   192.168.1.129   Casa_chull_5g   11ac    -53 dBm (buena)
```

## 5. Parsers

### 5.1 `parse_transfer_meaning(html) -> dict[str, str] | list[dict[str, str]]`

- Regex: `Transfer_meaning\('(\w+)'\s*,\s*'([^']*)'\)`.
- Decoder `\xNN` → char (ya existe como `_decode_hex_escapes`).
- El router repite cada key dos veces (una vacia de plantilla, una con valor). El parser **siempre se queda con la ultima ocurrencia no vacia** por key.
- Si detecta sufijos numericos (`NombreN`), agrupa por indice y devuelve `list[dict]`. Umbral: **dos o mas keys con el mismo prefijo y sufijos numericos contiguos**.

### 5.2 `parse_frm_table(html) -> dict[str, str]`

- Regex: `<td\s+class="tdleft">\s*([^<]+?)\s*</td>\s*<td\s+id="(Frm_[^"]+)"[^>]*class="tdright"[^>]*>\s*([^<]*?)\s*</td>`.
- Decoder `&#NNN;` → `chr(int(N))`.
- Devuelve `{Frm_XXX: valor_decodificado}`. La etiqueta humana del `<td class="tdleft">` se ignora (el formatter tiene sus propias etiquetas).

### 5.3 Helpers

- `decode_hex_escapes(s)`: `\xNN` → char (existente).
- `decode_html_entities(s)`: `&#NNN;` → char (nuevo).
- `group_by_numeric_suffix(dict) -> list[dict]`: agrupa keys tipo `MACAddr0`, `MACAddr1` en lista de dicts.

## 6. Manejo de errores

| Situacion | Respuesta de la tool |
|---|---|
| Login fallido / router bloqueado | `"Error: no se pudo iniciar sesion en <host>. Verifica .env"` (reutiliza logica actual, ya espera cooldown de 60s) |
| Pagina no existe o no parseable | `"Error: pagina '<X>' no trae datos reconocibles. Firmware distinto?"` |
| Pagina carga pero faltan campos whitelist | Devuelve lo que haya, campos ausentes → `—`. Nunca devolver `null` crudo. |
| Timeout / red caida | `"Error: sin respuesta de <host> (timeout)"` |
| Sesion expiro a mitad del fetch | Re-login automatico (ya existe). Si falla → error de login. |

Todas las tools envuelven su cuerpo en `try/except Exception as exc: return f"Error: {exc}"`. Patron existente, se mantiene.

## 7. Testing

### 7.1 Unitarios

- `tests/test_parsers.py`: cada parser contra su fixture HTML. Asserts sobre claves concretas y valores concretos.
- `tests/test_formatters.py`: dict de entrada → string esperado. Tests idempotentes, sin dependencias externas.
- Ejecucion: `pytest tests/`. Sin router requerido.

### 7.2 Smoke manual contra router real

- No forma parte de CI.
- `pytest -m router tests/` corre tests adicionales que usan `.env` para conectar. El desarrollador local los dispara antes de release.

### 7.3 No cubierto en Fase 1

- Tests de `http_client.py`: requieren mock HTTP; se posponen a Fase 3 (escrituras), donde el valor de los tests sube.
- Tests de `pages.py`: al ser orquestadores simples, se cubren indirectamente via el smoke manual.

## 8. Criterios de aceptacion

1. Las 6 tools devuelven la salida bonita especificada en la seccion 4.3 cuando se ejecutan contra el router real del usuario (F680 firmware Jazztel `ZTEGF6804P1T28`).
2. Los fixtures HTML guardados reproducen esa misma salida en tests unitarios sin router.
3. `src/zte_f680_mcp/server.py` queda ≤ 500 lineas tras el refactor.
4. `uvx zte-f680-mcp@0.3.0` (y `@latest`) funciona en instalacion limpia.
5. CLAUDE.md y README.md del proyecto se actualizan listando las 6 tools nuevas.

## 9. Compatibilidad y migracion

- v0.3.0 es **retrocompatible**: las 7 tools de v0.2.0 (`zte_get_port_forwards`, `zte_open_port`, `zte_add_port_forward`, `zte_modify_port_forward`, `zte_delete_port_forward`, `zte_get_local_ip`, `zte_run_page`) permanecen sin cambios funcionales.
- El refactor extrae logica a `http_client.py`, `parsers.py`, `pages.py` pero las firmas publicas de las tools existentes no cambian.
- `zte_run_page` se mantiene como escape hatch para paginas no cubiertas por las tools dedicadas.

## 10. Futuro (no en este spec)

- **Fase 2 — Descubrimiento**: `zte_list_pages` que barre nombres conocidos y reporta cuales responden. Util para adaptar el MCP a firmwares distintos.
- **Fase 3 — Escritura basica**: DMZ on/off, WiFi SSID/clave, reboot. Requiere cableado POST por pagina (como existe ya para port forwarding).
- **Fase 4 — Escritura avanzada**: DHCP static leases, firewall rules, QoS, backup/restore.
- **Fase 5 — Mantenimiento**: firmware info, DDNS, NTP, logs.

Las paginas identificadas en la exploracion inicial cubren todas estas fases (ver commit de este spec para el listado completo).
