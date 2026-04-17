# -*- coding: utf-8 -*-
"""Tests unitarios de formatters (dict -> string bonito)."""
from zte_f680_mcp.formatters import format_device_info, format_wifi_info, format_dhcp_leases


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
    assert "1d 0h" in out      # lease 86400s


def test_format_wifi_clients():
    from zte_f680_mcp.formatters import format_wifi_clients

    clients = [
        {
            "mac": "1e:74:40:88:bf:42",
            "ip": "192.168.1.131",
            "rssi": "-57",
            "tx_rate": "866700",
            "rx_rate": "866700",
            "mode": "11ac",
            "ssid_index": "5",
        },
        {
            "mac": "e6:ae:ed:e9:f6:f2",
            "ip": "192.168.1.135",
            "rssi": "-76",
            "tx_rate": "866700",
            "rx_rate": "866700",
            "mode": "11ac",
            "ssid_index": "7",
        },
    ]
    out = format_wifi_clients(clients)
    assert "1e:74:40:88:bf:42" in out
    assert "-57 dBm (buena)" in out
    assert "-76 dBm (debil)" in out
    assert "5 GHz" in out  # ssid_index 5 -> 5GHz
    assert "11ac" in out


def test_format_wifi_clients_empty():
    from zte_f680_mcp.formatters import format_wifi_clients

    assert "0" in format_wifi_clients([])


def test_format_dmz_off():
    from zte_f680_mcp.formatters import format_dmz

    out = format_dmz({
        "enabled": "0",
        "internal_host": "192.168.1.205",
        "internal_mac": "6c:3b:6b:2c:ab:2e",
    })
    assert "OFF" in out
    assert "192.168.1.205" in out


def test_format_dmz_on():
    from zte_f680_mcp.formatters import format_dmz

    out = format_dmz({
        "enabled": "1",
        "internal_host": "192.168.1.205",
        "internal_mac": "6c:3b:6b:2c:ab:2e",
    })
    assert "ON" in out
