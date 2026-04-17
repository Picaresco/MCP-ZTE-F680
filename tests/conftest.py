# -*- coding: utf-8 -*-
"""Fixtures compartidos por los tests unitarios."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def html_device_info() -> str:
    return (FIXTURES / "status_dev_info_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wan_status() -> str:
    return (FIXTURES / "IPv46_status_wan_if_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wifi_24() -> str:
    return (FIXTURES / "net_wlanm_secrity1_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_wifi_5() -> str:
    return (FIXTURES / "net_wlanm_secrity2_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_dhcp() -> str:
    return (FIXTURES / "net_dhcp_dynamic_t.html").read_text(encoding="utf-8")


@pytest.fixture
def html_dmz() -> str:
    return (FIXTURES / "app_dmz_conf_t.html").read_text(encoding="utf-8")
