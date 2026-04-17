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


def _human_bytes(n_str: str) -> str:
    """Convierte string numerico a unidades humanas (B, KB, MB, GB)."""
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
    """Convierte '1' -> 'ON', else -> 'OFF'."""
    return "ON" if v == "1" else "OFF"


def _yesno(v: str) -> str:
    """Convierte '1' -> 'SI', else -> 'NO'."""
    return "SI" if v == "1" else "NO"


_ENCRYPT_LABEL = {
    "AESEncryption": "WPA/WPA2 AES",
    "TKIPEncryption": "WPA TKIP",
    "TKIPandAESEncryption": "WPA/WPA2 TKIP+AES",
}


def _format_wifi_band(title: str, b: dict[str, str]) -> list[str]:
    """Formatea una banda WiFi (2.4 o 5 GHz) en lineas de texto."""
    channel_mode = "auto" if b.get("auto_channel") == "1" else "manual"
    encrypt = _ENCRYPT_LABEL.get(
        b.get("wpa_encrypt", ""), b.get("wpa_encrypt", "—")
    )
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
    """Formatea informacion de ambas bandas WiFi."""
    lines: list[str] = []
    lines.extend(_format_wifi_band("WiFi 2.4 GHz", data.get("band_24", {})))
    lines.append("")
    lines.extend(_format_wifi_band("WiFi 5 GHz", data.get("band_5", {})))
    return "\n".join(lines)


def _human_seconds(s_str: str) -> str:
    """Convierte segundos a formato 'Xd Yh' o 'Yh ZZm' o 'ZZm'."""
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
    """Mapea puertos internos (eth4, SSIDx) a etiquetas humanas."""
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
    """Formatea lista de dispositivos DHCP conectados."""
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
        "Modo    Senal",
    ]
    rows = [
        f"  {c.get('mac', ''):18s}  {c.get('ip', ''):15s} "
        f"{_ssid_to_band(c.get('ssid_index', '')):20s} "
        f"{c.get('mode', ''):7s} {_rssi_label(c.get('rssi', ''))}"
        for c in clients
    ]
    return "\n".join(header + rows)


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


def format_wan_status(data: dict[str, str]) -> str:
    """Formatea estado WAN: IP publica, gateway, DNS, MAC, uptime."""
    if data.get("_unsupported"):
        return (
            "ZTE F680 - WAN\n"
            "  No se pudo parsear IPv46_status_wan_if_t.gch en este firmware.\n"
            "  Usa zte_run_page(page_name='IPv46_status_wan_if_t.gch', "
            "raw=True) para ver el HTML crudo."
        )
    dns1 = _val(data, "dns1")
    dns2_raw = data.get("dns2", "")
    dns_str = f"{dns1} / {dns2_raw}" if dns2_raw else dns1

    lines = [
        "ZTE F680 - Estado WAN",
        f"  IP publica:     {_val(data, 'public_ip')}",
        f"  Mascara:        {_val(data, 'subnet_mask')}",
        f"  Gateway:        {_val(data, 'gateway')}",
        f"  DNS:            {dns_str}",
        f"  MAC WAN:        {_val(data, 'wan_mac')}",
        f"  Tipo conexion:  {_val(data, 'conn_type')}",
        f"  Version IP:     {_val(data, 'ip_version')}",
        f"  NAT:            {_val(data, 'nat')}",
        f"  Estado:         {_val(data, 'status')}",
    ]
    uptime = data.get("uptime_seconds", "")
    if uptime:
        lines.append(f"  Uptime:         {_human_seconds(uptime)}")
    return "\n".join(lines)
