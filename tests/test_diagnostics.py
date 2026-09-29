"""Tests for the diagnostics download."""

import asyncio
import json

import aiohttp
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravelli_smart_wifi.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .fake_module import HOST, MAC, PATH_GET, FakeModule

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


async def test_unreachable_module_gets_one_request_only(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A module that does not answer is not asked fifteen times."""
    fake_module.error = aiohttp.ClientConnectionError("no answer")
    before = len(fake_module.requests)

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert len(fake_module.requests) - before == 1
    failed = {"error": "WinetConnectionError"}
    assert result["system"] == failed
    assert result["schedule"] == failed
    assert result["categories"] == {str(number): failed for number in range(13)}


async def test_turn_off_does_not_wait_for_the_download(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A turn-off starts after one request of the download, not after all."""
    coordinator = init_integration.runtime_data
    fake_module.common[2] = 5
    fake_module.delay = 0.02
    before = len(fake_module.requests)

    download = asyncio.create_task(coordinator.async_read_diagnostics())
    await asyncio.sleep(0.03)
    await coordinator.async_set_power(False)
    off_at = next(
        index
        for index, (_, fields) in enumerate(fake_module.requests[before:])
        if fields.get("key") == "022"
    )
    await download

    assert off_at <= 3
    assert fake_module.count(PATH_GET, key="022", status="0") == 1
    assert len(fake_module.requests) - before > 15
    assert fake_module.max_concurrent == 1


async def test_malformed_schedule_rows_are_redacted_or_described(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Nothing but an integer comes out of a row; a bad row is described."""
    fake_module.programs = [
        [1, "secret-a", 18, 0, 1, 22, 2, 22, True, 127, "Evening"],
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127],
        "secret-b",
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening", "secret-c"],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""],
    ]

    result = await async_get_config_entry_diagnostics(hass, init_integration)

    programs = result["schedule"]["programs"]
    assert programs[0] == [
        1,
        REDACTED,
        18,
        0,
        1,
        22,
        2,
        22,
        REDACTED,
        127,
        REDACTED,
    ]
    assert programs[1] == "list of 10 items"
    assert programs[2] == "str"
    assert programs[3] == "list of 12 items"
    assert programs[4][10] == ""
    text = json.dumps(result, default=str)
    for secret in ("secret-a", "secret-b", "secret-c"):
        assert secret not in text, secret
