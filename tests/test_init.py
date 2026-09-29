"""Tests for the setup of a config entry."""

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from .fake_module import FakeModule


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The coordinator is stored on the entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data.model.name == "AIR-RDS"
    assert init_integration.runtime_data.data.state.setpoint == 22

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_waits_for_an_unreachable_module(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Home Assistant retries later when the stove is unplugged."""
    fake_module.error = aiohttp.ClientConnectionError()

    assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_refuses_an_unsupported_model(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The board can be changed from the vendor UI after the setup."""
    FakeModule(model=2).install(aioclient_mock)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
