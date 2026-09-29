"""Shared fixtures."""

from collections.abc import Generator
from unittest.mock import patch

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, FakeModule


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def fake_module(aioclient_mock: AiohttpClientMocker) -> FakeModule:
    """Put an idle AIR-RDS module on the network."""
    module = FakeModule()
    module.install(aioclient_mock)
    return module


@pytest.fixture
def mock_mac() -> Generator[None]:
    """Answer the MAC address lookup without touching the network."""
    with patch(
        "custom_components.ravelli_smart_wifi.config_flow.get_mac_address",
        return_value=MAC,
    ):
        yield


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Register a config entry for the module, not set up yet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli AIR-RDS",
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> MockConfigEntry:
    """Set the integration up against the simulated module."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def enable_all_entities() -> Generator[None]:
    """Create the entities that are disabled by default as enabled."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield
