"""Tests for the diagnostics download."""

import json

import aiohttp
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravelli_smart_wifi.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .fake_module import HOST, MAC, FakeModule

PERSONAL = (HOST, MAC, "192.0.2", "255.255.255.0", "example-network", "Evening")


async def test_diagnostics_hold_the_registers_and_no_personal_data(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Enough to support a new model, nothing that identifies a home."""
    fake_module.extra["name"] = "Living room"
    fake_module.extra["tsense"] = {"show": 1, "list": [["11:22:33:44:55:66", 21]]}
    fake_module.system["eNowDevs"] = [["11:22:33:44:55:66", "probe"]]

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    text = json.dumps(result, default=str)
    for secret in (*PERSONAL, "Living room", "11:22:33:44:55:66"):
        assert secret not in text, secret
    assert result["model"] == "AIR-RDS"
    assert result["entry"]["data"] == {"host": REDACTED, "model": 7, "mac": REDACTED}
    assert result["entry"]["unique_id"] == REDACTED
    assert result["system"]["fwVer"] == "0.51"
    assert result["system"]["rssi"] == -74
    assert result["system"]["network"] == REDACTED
    assert list(result["categories"]) == [str(number) for number in range(13)]
    assert [50, 22] in result["categories"]["2"]["params"]
    assert [300, 1] in result["categories"]["0"]["params"]
    assert result["categories"]["2"]["name"] == REDACTED
    assert result["schedule"]["enabled"] is True
    assert result["schedule"]["programs"][0] == [
        1,
        1,
        18,
        0,
        1,
        22,
        2,
        22,
        1,
        127,
        REDACTED,
    ]
    assert result["schedule"]["programs"][1][10] == ""


async def test_diagnostics_of_an_unreachable_module(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The download still works, and says what failed without the address."""
    fake_module.error = aiohttp.ClientConnectionError(f"cannot connect to {HOST}")

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    failed = {"error": "WinetConnectionError"}
    assert result["model"] == "AIR-RDS"
    assert result["system"] == failed
    assert result["schedule"] == failed
    assert result["categories"] == {str(number): failed for number in range(13)}
    assert HOST not in json.dumps(result, default=str)


async def test_one_refused_category_keeps_the_others(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A category the board refuses must not hide the rest of the download."""
    fake_module.refused_categories.add(5)

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["categories"]["5"] == {"error": "WinetResponseError"}
    assert [50, 22] in result["categories"]["2"]["params"]
    assert [300, 1] in result["categories"]["0"]["params"]
    assert result["system"]["fwVer"] == "0.51"
    assert result["schedule"]["enabled"] is True


async def test_diagnostics_keep_only_the_keys_support_needs(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Every key not known to be harmless is redacted, but still listed."""
    fake_module.system.update(
        {"mac": MAC, "ssid": "example-network", "hostname": "stove", "future": 1}
    )
    fake_module.extra["netatmo"] = [True, False, "home-token", 0, 0]
    fake_module.extra["future"] = "unknown"
    fake_module.schedule_enabled = True

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    system = result["system"]
    for key in ("mac", "ssid", "hostname", "future", "inetTime", "network"):
        assert system[key] == REDACTED, key
    for key, value in {
        "status": 5,
        "fwUpdate": False,
        "fwVer": "0.51",
        "boot": 2,
        "board": [7, 0, 0, 0],
        "signal": 3,
        "rssi": -74,
        "client": 2,
        "useTSense": 0,
        "lastDisconnectReason": 0,
        "lastCloudError": 0,
        "apConnected": 0,
        "pairing": 0,
        "show": 0,
        "timeout": 0,
    }.items():
        assert system[key] == value, key
    category = result["categories"]["2"]
    for key in ("netatmo", "future", "name", "tsense", "inetTime"):
        assert category[key] == REDACTED, key
    for key, value in {
        "cat": 2,
        "model": 7,
        "flame": 255,
        "chrono": 0,
        "alr": "",
        "signal": 3,
        "authLevel": 0,
        "localWeb": 1,
    }.items():
        assert category[key] == value, key
    assert [50, 22] in category["params"]
    assert "home-token" not in json.dumps(result, default=str)
