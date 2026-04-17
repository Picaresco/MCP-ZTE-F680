# -*- coding: utf-8 -*-
"""Orquestadores por pagina funcional del router ZTE F680.

Cada funcion combina http_client + parsers y devuelve un dict con
claves limpias en castellano/ingles que el formatter sabe presentar.
"""
from __future__ import annotations

from zte_f680_mcp import http_client
from zte_f680_mcp.parsers import (
    parse_frm_table,
    parse_tdright_table,
    parse_transfer_meaning,
)


async def fetch_device_info() -> dict[str, str]:
    """Lee status_dev_info_t.gch y devuelve dict con identidad HW/SW."""
    html = await http_client.fetch_html("status_dev_info_t.gch")
    raw = parse_frm_table(html)

    wifi_chipsets = ""
    if raw.get("Frm_WiFiVendor") and raw.get("Frm_WiFiModel"):
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


async def fetch_dmz() -> dict[str, str]:
    """Lee app_dmz_conf_t.gch."""
    html = await http_client.fetch_html("app_dmz_conf_t.gch")
    raw = parse_transfer_meaning(html)
    return {
        "enabled": raw.get("Enable", ""),
        "internal_host": raw.get("InternalHost", ""),
        "internal_mac": raw.get("InternalMacHost", ""),
    }


def _split_ip_mask(combined: str) -> tuple[str, str]:
    """Separa 'IP/MASK' en (ip, mask). Si no hay '/', devuelve (combined, '')."""
    if "/" in combined:
        ip, mask = combined.split("/", 1)
        return ip.strip(), mask.strip()
    return combined.strip(), ""


def _first_dns(combined: str) -> str:
    """Primer DNS de 'dns1/dns2/dns3' (descarta 0.0.0.0)."""
    parts = [p.strip() for p in combined.split("/") if p.strip() not in ("", "::")]
    non_zero = [p for p in parts if p != "0.0.0.0"]
    return non_zero[0] if non_zero else ""


def _second_dns(combined: str) -> str:
    """Segundo DNS de 'dns1/dns2/dns3' (descarta 0.0.0.0)."""
    parts = [p.strip() for p in combined.split("/") if p.strip() not in ("", "::")]
    non_zero = [p for p in parts if p != "0.0.0.0"]
    return non_zero[1] if len(non_zero) > 1 else ""


def _strip_unit(val: str, suffix: str) -> str:
    """Elimina sufijo textual: '645422 sec' -> '645422'."""
    val = val.strip()
    if val.lower().endswith(suffix.lower()):
        return val[: -len(suffix)].strip()
    return val


async def fetch_wan_status() -> dict[str, str]:
    """Lee IPv46_status_wan_if_t.gch.

    Formato C (tdleft/tdright). Campos del router:
      'IP'               -> '207.188.156.71/255.255.248.0' (IP publica + mascara)
      'DNS'              -> '46.6.113.34/212.230.135.1/0.0.0.0'
      'IPv4 Gateway'     -> '207.188.152.1'
      'IPv4 Connection Status' -> 'Connected'
      'IPv4 Online Duration'   -> '645422 sec'
      'WAN MAC'          -> '24:d3:f2:c6:97:b6'
      'Type'             -> 'IP'
      'Connection Name'  -> 'WANConnection'
      'IP Version'       -> 'IPv4/v6'
      'NAT'              -> 'Enabled'
    """
    html = await http_client.fetch_html("IPv46_status_wan_if_t.gch")
    raw = parse_tdright_table(html)
    if not raw:
        # Pagina no reconocida: fallback gracioso
        return {"_unsupported": "1"}

    ip_combined = raw.get("IP", "")
    ip, mask = _split_ip_mask(ip_combined)
    dns_combined = raw.get("DNS", "")

    uptime_raw = raw.get("IPv4 Online Duration", "")
    uptime_sec = _strip_unit(uptime_raw, "sec")

    return {
        "public_ip": ip,
        "subnet_mask": mask,
        "gateway": raw.get("IPv4 Gateway", ""),
        "dns1": _first_dns(dns_combined),
        "dns2": _second_dns(dns_combined),
        "wan_mac": raw.get("WAN MAC", ""),
        "uptime_seconds": uptime_sec,
        "status": raw.get("IPv4 Connection Status", ""),
        "conn_type": raw.get("Type", ""),
        "ip_version": raw.get("IP Version", ""),
        "nat": raw.get("NAT", ""),
        "conn_name": raw.get("Connection Name", ""),
    }
