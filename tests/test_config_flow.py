"""Tests for the config flow started by the user."""

from collections.abc import Generator
from ipaddress import IPv4Network
import re
from typing import Any
from unittest.mock import patch

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.config_flow import (
    CHOICE_MANUAL,
    async_local_networks,
)
from custom_components.ravelli_smart_wifi.const import DOMAIN, ISSUE_URL

from .fake_module import HOST, MAC, PATH_STATUS, FakeModule

MAC_LOOKUP = "custom_components.ravelli_smart_wifi.config_flow.get_mac_address"
NETWORKS = "custom_components.ravelli_smart_wifi.config_flow.async_local_networks"
ADAPTERS = "custom_components.ravelli_smart_wifi.config_flow.network.async_get_adapters"


@pytest.fixture
def small_network() -> Generator[None]:
    """Scan six addresses, 192.0.2.9 to 192.0.2.14, instead of a real network."""
    with patch(NETWORKS, return_value=[IPv4Network("192.0.2.8/29")]):
        yield


@pytest.fixture
def silent_network(aioclient_mock: AiohttpClientMocker) -> None:
    """Refuse the connection at every address that is not a module."""
    aioclient_mock.post(
        re.compile(r"^http://192\.0\.2\.\d+/ajax/get-status$"),
        exc=aiohttp.ClientConnectionError(),
    )


@pytest.fixture
def module_on_network(fake_module: FakeModule, silent_network: None) -> FakeModule:
    """Put one module among silent addresses; the module is matched first."""
    return fake_module


async def start(hass: HomeAssistant, choice: str) -> dict[str, Any]:
    """Open the flow and pick an entry of its menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["scan", "manual"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": choice}
    )


async def scan(hass: HomeAssistant) -> dict[str, Any]:
    """Run the network search to its end."""
    result = await start(hass, "scan")
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "scan"
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_manual_entry_creates_the_entry(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """The entry holds the host, the model and the MAC address."""
    result = await start(hass, "manual")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ravelli AIR-RDS"
    assert result["data"] == {CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: MAC}
    assert result["result"].unique_id == MAC


@pytest.mark.parametrize(
    "typed", [f"  {HOST} ", f"http://{HOST}", f"http://{HOST}/management.html"]
)
async def test_pasted_addresses_are_accepted(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None, typed: str
) -> None:
    """People paste what their browser shows."""
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: typed}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST


async def test_empty_address(hass: HomeAssistant) -> None:
    """A scheme alone is not an address."""
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "http://"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_unreachable_address_can_be_corrected(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """The form comes back with an error, then accepts a second try."""
    fake_module.error = aiohttp.ClientConnectionError()
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    fake_module.error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "answer", ["<html><body>Router</body></html>", '{"status": 5}', "[]"]
)
async def test_another_device_is_not_a_module(
    hass: HomeAssistant, fake_module: FakeModule, answer: str
) -> None:
    """A router or a NAS answers, but not with the system status."""
    fake_module.raw_answers[PATH_STATUS] = answer
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_winet"}


@pytest.mark.parametrize("model", [None, "7", True])
async def test_answer_without_a_model_is_not_a_module(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_mac: None,
    model: Any,
) -> None:
    """Never "Stove model None is not supported yet"."""
    FakeModule(model=model).install(aioclient_mock)
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_winet"}


async def test_unsupported_model_aborts(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_mac: None
) -> None:
    """The message names the model code and the issue tracker."""
    FakeModule(model=2).install(aioclient_mock)
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
    assert result["description_placeholders"] == {
        "model": "2",
        "issue_url": ISSUE_URL,
    }


async def test_known_module_at_a_new_address_updates_the_entry(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """The MAC address identifies the module."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: "192.0.2.99", CONF_MODEL: 7, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


@pytest.mark.parametrize("found", [None, "", "00:00:00:00:00:00"])
async def test_module_without_a_known_mac_address(
    hass: HomeAssistant, fake_module: FakeModule, found: str | None
) -> None:
    """Without a MAC address, the host blocks duplicates."""
    with patch(MAC_LOOKUP, return_value=found):
        result = await start(hass, "manual")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_MAC] is None
        assert result["result"].unique_id is None

        result = await start(hass, "manual")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_entry_without_a_mac_address_blocks_a_later_lookup(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """The host of an entry created without a MAC address is checked too."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: None}
    ).add_to_hass(hass)
    result = await start(hass, "manual")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_hostname_is_looked_up_by_name(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The MAC lookup is told whether it gets an address or a name."""
    FakeModule(host="stove.example").install(aioclient_mock)

    with patch(MAC_LOOKUP, return_value=MAC) as lookup:
        result = await start(hass, "manual")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "stove.example"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    lookup.assert_called_once_with(hostname="stove.example")


async def test_scan_finds_the_module(
    hass: HomeAssistant,
    module_on_network: FakeModule,
    small_network: None,
    mock_mac: None,
) -> None:
    """The search lists the module and a manual choice."""
    result = await scan(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    options = result["data_schema"].schema[CONF_HOST].config["options"]
    assert [option["value"] for option in options] == [HOST, CHOICE_MANUAL]
    assert module_on_network.count(PATH_STATUS) == 1

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: MAC}


async def test_scan_then_manual_choice(
    hass: HomeAssistant, module_on_network: FakeModule, small_network: None
) -> None:
    """The list of found modules leads to the manual form."""
    result = await scan(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: CHOICE_MANUAL}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}


async def test_scan_that_finds_nothing_asks_for_the_address(
    hass: HomeAssistant, silent_network: None, small_network: None
) -> None:
    """The manual form says why it is shown."""
    result = await scan(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "none_found"}


async def test_scan_skips_configured_modules(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    module_on_network: FakeModule,
    small_network: None,
) -> None:
    """A module that is already set up is not offered again."""
    result = await scan(hass)

    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "none_found"}


async def test_scan_ignores_other_devices(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    small_network: None,
) -> None:
    """A device that answers without the two status fields is not a module."""
    aioclient_mock.post(f"http://192.0.2.9{PATH_STATUS}", text="<html></html>")
    aioclient_mock.post(f"http://192.0.2.11{PATH_STATUS}", json={"status": 5})
    aioclient_mock.post(
        re.compile(r"^http://192\.0\.2\.\d+/ajax/get-status$"), exc=TimeoutError()
    )

    result = await scan(hass)

    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "none_found"}


async def test_local_networks_are_bounded(hass: HomeAssistant) -> None:
    """Disabled adapters, large networks and link-local addresses are skipped."""
    adapters = [
        {
            "name": "eth0",
            "enabled": True,
            "ipv4": [{"address": "192.0.2.20", "network_prefix": 24}],
        },
        {
            "name": "wlan0",
            "enabled": True,
            "ipv4": [{"address": "192.0.2.21", "network_prefix": 24}],
        },
        {
            "name": "eth1",
            "enabled": False,
            "ipv4": [{"address": "198.51.100.5", "network_prefix": 24}],
        },
        {
            "name": "eth2",
            "enabled": True,
            "ipv4": [{"address": "203.0.113.5", "network_prefix": 16}],
        },
        {
            "name": "eth3",
            "enabled": True,
            "ipv4": [{"address": "169.254.3.4", "network_prefix": 24}],
        },
        {"name": "eth4", "enabled": True, "ipv4": []},
    ]

    with patch(ADAPTERS, return_value=adapters):
        assert await async_local_networks(hass) == [IPv4Network("192.0.2.0/24")]
