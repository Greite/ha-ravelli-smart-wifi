"""Tests for the options flow."""

from datetime import timedelta

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_options_change_the_polling_interval(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The entry is reloaded with the new interval."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {CONF_SCAN_INTERVAL: 60}
    assert init_integration.runtime_data.update_interval == timedelta(seconds=60)


@pytest.mark.parametrize("seconds", [9, 301])
async def test_interval_outside_the_bounds_is_refused(
    hass: HomeAssistant, init_integration: MockConfigEntry, seconds: int
) -> None:
    """The bounds protect the module from being polled too often."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: seconds}
        )

    assert init_integration.options == {}
