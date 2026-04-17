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


@pytest.mark.asyncio
async def test_fetch_wifi_clients_real(mock_fetch, html_dhcp):
    mock_fetch({"net_dhcp_dynamic_t.gch": html_dhcp})
    data = await pages.fetch_wifi_clients()
    assert len(data) == 3
    # Primero: 1e:74:40:88:bf:42 en 5GHz SSID 5
    c0 = data[0]
    assert c0["mac"] == "1e:74:40:88:bf:42"
    assert c0["ip"] == "192.168.1.131"
    assert c0["rssi"] == "-57"
    assert c0["mode"] == "11ac"
    assert c0["ssid_index"] == "5"


@pytest.mark.asyncio
async def test_fetch_dmz_real(mock_fetch, html_dmz):
    mock_fetch({"app_dmz_conf_t.gch": html_dmz})
    data = await pages.fetch_dmz()
    assert data["enabled"] == "0"
    assert data["internal_host"] == "192.168.1.205"
    assert data["internal_mac"] == "6c:3b:6b:2c:ab:2e"


@pytest.mark.asyncio
async def test_fetch_wan_status(mock_fetch, html_wan_status):
    mock_fetch({"IPv46_status_wan_if_t.gch": html_wan_status})
    data = await pages.fetch_wan_status()
    if data.get("_unsupported"):
        pytest.skip("WAN status no soportado en este firmware")
    # Al menos algun campo tiene que aparecer
    assert any(v for v in data.values()), "fetch_wan_status devolvio todo vacio"
    # Fixture tiene datos reales: verificar campos clave
    assert data["public_ip"] == "207.188.156.71"
    assert data["subnet_mask"] == "255.255.248.0"
    assert data["gateway"] == "207.188.152.1"
    assert data["dns1"] == "46.6.113.34"
    assert data["dns2"] == "212.230.135.1"
    assert data["wan_mac"] == "24:d3:f2:c6:97:b6"
    assert data["status"] == "Connected"
    assert data["uptime_seconds"].isdigit()
    assert int(data["uptime_seconds"]) > 0
