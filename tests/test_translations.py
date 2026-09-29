"""Tests for the translation and icon files."""

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import Any

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components" / "ravelli_smart_wifi"
ENGLISH = json.loads((COMPONENT / "translations" / "en.json").read_text())
FRENCH = json.loads((COMPONENT / "translations" / "fr.json").read_text())
ICONS = json.loads((COMPONENT / "icons.json").read_text())

EXCEPTIONS = {
    "cannot_connect",
    "command_refused",
    "device_not_found",
    "model_mismatch",
    "register_not_writable",
    "schedule_end_before_start",
    "schedule_mismatch",
    "schedule_name_characters",
    "schedule_name_length",
    "schedule_no_time",
    "schedule_no_weekday",
    "schedule_power_range",
    "schedule_slot_range",
    "schedule_temperature_range",
    "schedule_time_step",
    "schedule_unreadable",
    "temperature_required",
    "turn_off_during_ignition",
    "turn_on_in_alarm",
    "unsupported_model",
    "value_out_of_range",
}
ENTITIES = {
    "binary_sensor": {"alarm", "firmware_update", "flame"},
    "button": {"sync_clock"},
    "calendar": {"schedule"},
    "climate": {"duct_left", "duct_right", "stove", "water"},
    "number": {"comfort_delay", "comfort_delta", "power"},
    "sensor": {
        "alarm",
        "ambient_temperature",
        "extractor_speed",
        "flue_temperature",
        "status",
        "wifi_signal",
    },
    "switch": {"schedule"},
}
STATUS_STATES = {
    "off",
    "pellet_loading",
    "ignition",
    "waiting_flame",
    "flame_present",
    "working",
    "final_cleaning",
    "eco_stop",
    "alarm",
    "alarm_memory",
}


def flatten(data: dict[str, Any], prefix: str = "") -> Iterator[tuple[str, str]]:
    """Yield every text with its dotted path."""
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from flatten(value, path)
        else:
            yield path, value


def test_french_has_the_keys_of_english() -> None:
    """A missing French text would show in English."""
    assert sorted(dict(flatten(FRENCH))) == sorted(dict(flatten(ENGLISH)))


def test_placeholders_are_the_same_in_both_languages() -> None:
    """A renamed placeholder would show as raw braces."""
    french = dict(flatten(FRENCH))
    for path, text in flatten(ENGLISH):
        assert set(re.findall(r"\{(\w+)\}", text)) == set(
            re.findall(r"\{(\w+)\}", french[path])
        ), path


def test_no_text_is_empty() -> None:
    """Every key carries a text."""
    for language in (ENGLISH, FRENCH):
        for path, text in flatten(language):
            assert isinstance(text, str) and text.strip(), path


def test_every_error_of_the_code_has_a_message() -> None:
    """The keys raised by the coordinator and the actions."""
    assert set(ENGLISH["exceptions"]) == EXCEPTIONS


@pytest.mark.parametrize("platform", sorted(ENTITIES))
def test_every_entity_has_a_name(platform: str) -> None:
    """The keys the platforms use as translation_key."""
    assert set(ENGLISH["entity"][platform]) == ENTITIES[platform]
    for entity in ENGLISH["entity"][platform].values():
        assert entity["name"]


def test_every_status_has_a_label() -> None:
    """The ten status keys of the register model."""
    assert set(ENGLISH["entity"]["sensor"]["status"]["state"]) == STATUS_STATES


def test_icons_name_known_entities() -> None:
    """An icon for an entity that does not exist is a typo."""
    for platform, entities in ICONS["entity"].items():
        assert set(entities) <= ENTITIES[platform], platform
    assert set(ICONS["services"]) == set(ENGLISH["services"])
