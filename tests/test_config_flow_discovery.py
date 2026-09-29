"""Tests for the DHCP discovery and the reconfiguration."""

from unittest.mock import patch

import aiohttp
from homeassistant.config_entries import SOURCE_DHCP
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.const import DOMAIN, ISSUE_URL

from .fake_module import HOST, MAC, PATH_STATUS, FakeModule

MAC_LOOKUP = "custom_components.ravelli_smart_wifi.config_flow.get_mac_address"
DISCOVERY = DhcpServiceInfo(ip=HOST, hostname="module", macaddress="aabbccddeeff")
OTHER_HOST = "192.0.2.11"


async def discover(hass: HomeAssistant) -> dict:
    """Start the flow the way the DHCP integration does."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DISCOVERY
    )


async def test_discovery_offers_the_module(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """The MAC address of the DHCP request becomes the unique id."""
    result = await discover(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"model": "AIR-RDS", "host": HOST}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ravelli AIR-RDS"
    assert result["data"] == {CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: MAC}
    assert result["result"].unique_id == MAC


async def test_discovery_uses_the_mac_address_of_the_request(
    hass: HomeAssistant, fake_module: FakeModule
) -> None:
    """The neighbour table can be empty; the DHCP request is enough."""
    with patch(MAC_LOOKUP, return_value=None):
        result = await discover(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == MAC


async def test_discovery_of_a_known_module_updates_its_address(
    hass: HomeAssistant, fake_module: FakeModule, mock_mac: None
) -> None:
    """This is how the entry follows a new DHCP lease."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: "192.0.2.99", CONF_MODEL: 7, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)

    result = await discover(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST
    assert fake_module.count(PATH_STATUS) == 0


async def test_discovery_of_a_silent_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device with a matching name that does not answer is dropped."""
    aioclient_mock.post(
        f"http://{HOST}{PATH_STATUS}", exc=aiohttp.ClientConnectionError()
    )

    result = await discover(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovery_of_another_device(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A device with a matching name that is not a module is dropped."""
    aioclient_mock.post(f"http://{HOST}{PATH_STATUS}", text="<html></html>")

    result = await discover(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_winet"


async def test_discovery_of_an_unsupported_model(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_mac: None
) -> None:
    """The abort names the model code."""
    FakeModule(model=15).install(aioclient_mock)

    result = await discover(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"
    assert result["description_placeholders"] == {
        "model": "15",
        "issue_url": ISSUE_URL,
    }


async def test_reconfigure_changes_the_address(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_mac: None,
) -> None:
    """The entry, and with it the entities and their history, is kept."""
    FakeModule(host=OTHER_HOST).install(aioclient_mock)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f"http://{OTHER_HOST}/"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: OTHER_HOST, CONF_MODEL: 7, CONF_MAC: MAC}
    assert config_entry.unique_id == MAC


async def test_reconfigure_refuses_another_module(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Another stove at the new address would inherit the wrong history."""
    FakeModule(host=OTHER_HOST).install(aioclient_mock)
    result = await config_entry.start_reconfigure_flow(hass)

    with patch(MAC_LOOKUP, return_value="11:22:33:44:55:66"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: OTHER_HOST}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data[CONF_HOST] == HOST


async def test_reconfigure_without_a_mac_address_is_accepted(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A failed lookup cannot prove that the module is another one."""
    FakeModule(host=OTHER_HOST).install(aioclient_mock)
    result = await config_entry.start_reconfigure_flow(hass)

    with patch(MAC_LOOKUP, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: OTHER_HOST}
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == OTHER_HOST
    assert config_entry.data[CONF_MAC] == MAC


async def test_reconfigure_with_an_unreachable_address(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The form comes back with an error and the entry is unchanged."""
    aioclient_mock.post(
        f"http://{OTHER_HOST}{PATH_STATUS}", exc=aiohttp.ClientConnectionError()
    )
    result = await config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert config_entry.data[CONF_HOST] == HOST
