"""Tests for the numbers."""

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .fake_module import PATH_SET, FakeModule
from .helpers import entity_id_for


async def set_value(hass: HomeAssistant, key: str, value: float) -> None:
    """Call the action a slider of the user interface calls."""
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id_for(hass, "number", key), "value": value},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("key", "state", "minimum", "maximum", "unit", "category"),
    [
        ("power", "1", 1, 5, None, None),
        ("comfort_delta", "1", 0, 20, "°C", EntityCategory.CONFIG),
        ("comfort_delay", "0", 0, 9, "min", EntityCategory.CONFIG),
    ],
)
async def test_numbers_of_an_idle_stove(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    key: str,
    state: str,
    minimum: int,
    maximum: int,
    unit: str | None,
    category: EntityCategory | None,
) -> None:
    """The bounds are those of the register table."""
    entity_id = entity_id_for(hass, "number", key)
    number = hass.states.get(entity_id)

    assert number.state == state
    assert number.attributes["min"] == minimum
    assert number.attributes["max"] == maximum
    assert number.attributes["step"] == 1
    assert number.attributes.get("unit_of_measurement") == unit
    assert er.async_get(hass).async_get(entity_id).entity_category is category


@pytest.mark.parametrize(
    ("key", "category", "register", "value"),
    [("power", 2, 51, 3), ("comfort_delta", 11, 74, 2), ("comfort_delay", 11, 73, 5)],
)
async def test_set_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    key: str,
    category: int,
    register: int,
    value: int,
) -> None:
    """The register is written and the new value shows at once."""
    await set_value(hass, key, value)

    assert fake_module.categories[category][register] == value
    assert fake_module.count(PATH_SET, regId=str(register), value=str(value)) == 1
    assert hass.states.get(entity_id_for(hass, "number", key)).state == str(value)


@pytest.mark.parametrize("value", [0, 6])
async def test_value_outside_the_bounds_is_refused(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    value: int,
) -> None:
    """Nothing reaches the module."""
    with pytest.raises(ServiceValidationError):
        await set_value(hass, "power", value)

    assert fake_module.count(PATH_SET) == 0
    assert fake_module.categories[2][51] == 1


async def test_refused_write_is_reported(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The user sees why the slider did not move."""
    fake_module.write_result = False

    with pytest.raises(HomeAssistantError) as err:
        await set_value(hass, "power", 3)

    assert err.value.translation_key == "command_refused"
    assert hass.states.get(entity_id_for(hass, "number", "power")).state == "1"
