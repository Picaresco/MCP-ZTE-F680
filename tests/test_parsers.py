# -*- coding: utf-8 -*-
"""Tests unitarios de parsers HTML del router ZTE F680."""
from zte_f680_mcp.parsers import (
    parse_transfer_meaning,
    parse_frm_table,
    parse_tdright_table,
    decode_hex_escapes,
    decode_html_entities,
    group_by_numeric_suffix,
)


def test_decode_hex_escapes():
    assert decode_hex_escapes("192\\x2e168\\x2e1\\x2e1") == "192.168.1.1"
    assert decode_hex_escapes("sin-escapes") == "sin-escapes"


def test_decode_html_entities():
    # "F680" en entidades decimales
    assert decode_html_entities("&#70;&#54;&#56;&#48;") == "F680"
    assert decode_html_entities("ya limpio") == "ya limpio"


def test_parse_transfer_meaning_basic():
    html = "Transfer_meaning('Name','test');Transfer_meaning('Proto','TCP');"
    data = parse_transfer_meaning(html)
    assert data == {"Name": "test", "Proto": "TCP"}


def test_parse_transfer_meaning_keeps_last_non_empty():
    # El router emite primero la key vacia (plantilla) y luego con valor.
    # Debe quedarse con la ultima no vacia.
    html = (
        "Transfer_meaning('ESSID','');"
        "Transfer_meaning('ESSID','Casa_Chull_2g');"
    )
    data = parse_transfer_meaning(html)
    assert data == {"ESSID": "Casa_Chull_2g"}


def test_parse_transfer_meaning_decodes_hex():
    html = r"Transfer_meaning('IP','192\x2e168\x2e1\x2e1');"
    data = parse_transfer_meaning(html)
    assert data == {"IP": "192.168.1.1"}


def test_parse_frm_table_basic():
    html = (
        '<td class="tdleft">Model</td>'
        '<td id="Frm_ModelName" name="Frm_ModelName" class="tdright">'
        "&#70;&#54;&#56;&#48;</td>"
    )
    data = parse_frm_table(html)
    assert data == {"Frm_ModelName": "F680"}


def test_parse_frm_table_strips_whitespace():
    html = (
        '<td class="tdleft">Serial</td>'
        '<td id="Frm_SerialNumber" name="Frm_SerialNumber" class="tdright">'
        "  &#90;&#84;&#69;  </td>"
    )
    data = parse_frm_table(html)
    assert data == {"Frm_SerialNumber": "ZTE"}


def test_group_by_numeric_suffix():
    d = {
        "MACAddr0": "aa:bb",
        "IPAddr0": "1.1.1.1",
        "MACAddr1": "cc:dd",
        "IPAddr1": "2.2.2.2",
        "OtherKey": "ignore",
    }
    groups = group_by_numeric_suffix(d, prefixes=["MACAddr", "IPAddr"])
    assert groups == [
        {"MACAddr": "aa:bb", "IPAddr": "1.1.1.1"},
        {"MACAddr": "cc:dd", "IPAddr": "2.2.2.2"},
    ]


def test_group_by_numeric_suffix_sorts_by_index():
    d = {"X2": "c", "X0": "a", "X1": "b"}
    groups = group_by_numeric_suffix(d, prefixes=["X"])
    assert [g["X"] for g in groups] == ["a", "b", "c"]


# Fixture-based (contra HTML real del router)

def test_parse_transfer_meaning_real_wifi_24(html_wifi_24):
    data = parse_transfer_meaning(html_wifi_24)
    assert data["ESSID"] == "Casa_Chull_2g"
    assert data["Channel"] == "1"
    assert data["KeyPassphrase"] == "ChullWapa$"
    assert data["Bssid"] == "24:d3:f2:c6:97:b6"


def test_parse_frm_table_real_device_info(html_device_info):
    data = parse_frm_table(html_device_info)
    assert data["Frm_ModelName"] == "F680"
    assert data["Frm_SerialNumber"] == "ZTEEQERJ8L16414"
    assert data["Frm_SoftwareVer"] == "ZTEGF6804P1T28"
    assert data["Frm_HardwareVer"] == "V4.0"


# parse_tdright_table (formato C)

def test_parse_tdright_table_basic():
    html = (
        '<td class="tdleft">IP</td>'
        '<td class="tdright">&#49;&#46;&#50;&#46;&#51;&#46;&#52;</td>'
    )
    data = parse_tdright_table(html)
    assert data == {"IP": "1.2.3.4"}


def test_parse_tdright_table_whitespace():
    html = (
        '<td   class="tdleft">  Gateway  </td>\n'
        '<td   class="tdright">  10.0.0.1  </td>'
    )
    data = parse_tdright_table(html)
    assert data == {"Gateway": "10.0.0.1"}


def test_parse_tdright_table_empty_value():
    html = (
        '<td class="tdleft">Empty</td>'
        '<td class="tdright"></td>'
    )
    data = parse_tdright_table(html)
    assert data == {"Empty": ""}


def test_parse_tdright_table_duplicate_key_keeps_non_empty():
    # Primera ocurrencia vacia, segunda con valor -> gana la segunda
    html = (
        '<td class="tdleft">DNS</td><td class="tdright"></td>'
        '<td class="tdleft">DNS</td><td class="tdright">8.8.8.8</td>'
    )
    data = parse_tdright_table(html)
    assert data == {"DNS": "8.8.8.8"}


def test_parse_tdright_table_duplicate_key_ipv6_placeholder_replaced():
    # Primera IPv6 vacia (::/::), segunda IPv4 real -> gana IPv4
    html = (
        '<td class="tdleft">DNS</td><td class="tdright">::/:: / ::</td>'
        '<td class="tdleft">DNS</td><td class="tdright">8.8.8.8</td>'
    )
    data = parse_tdright_table(html)
    assert data == {"DNS": "8.8.8.8"}


def test_parse_tdright_table_duplicate_key_first_wins_when_non_empty():
    # Primera con valor real -> no se reemplaza aunque haya segunda
    html = (
        '<td class="tdleft">IP</td><td class="tdright">1.1.1.1</td>'
        '<td class="tdleft">IP</td><td class="tdright">2.2.2.2</td>'
    )
    data = parse_tdright_table(html)
    assert data == {"IP": "1.1.1.1"}


def test_parse_tdright_table_real_wan(html_wan_status):
    data = parse_tdright_table(html_wan_status)
    # Los labels reales incluyen al menos IP, DNS, WAN MAC (los nombres
    # exactos dependen del firmware; verificamos que extrae algo util).
    assert len(data) > 0
    # Algun valor no vacio tiene que haber
    assert any(v for v in data.values())
