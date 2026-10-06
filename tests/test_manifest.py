"""Tests for the static metadata of the integration."""

import json
from pathlib import Path

from custom_components.ravelli_smart_wifi.const import DOMAIN

ROOT = Path(__file__).parent.parent
MANIFEST = ROOT / "custom_components" / "ravelli_smart_wifi" / "manifest.json"


def test_manifest_describes_a_local_polling_integration() -> None:
    """The manifest carries the domain, the flow flag and the requirement."""
    manifest = json.loads(MANIFEST.read_text())

    assert manifest["domain"] == DOMAIN == "ravelli_smart_wifi"
    assert manifest["name"] == "Ravelli Smart Wi-Fi"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "device"
    assert manifest["iot_class"] == "local_polling"
    assert manifest["requirements"] == ["getmac==0.9.5"]
    # Modules of other brands share the prefix: the flow probes the board.
    assert manifest["dhcp"] == [
        {"hostname": "winet-*"},
        {"registered_devices": True},
    ]


def test_manifest_keys_are_sorted_as_hassfest_requires() -> None:
    """hassfest wants domain, name, then the other keys in alphabetical order."""
    keys = list(json.loads(MANIFEST.read_text()))

    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_hacs_manifest() -> None:
    """HACS reads the display name and the minimum Home Assistant version."""
    hacs = json.loads((ROOT / "hacs.json").read_text())

    assert hacs == {
        "name": "Ravelli Smart Wi-Fi",
        "homeassistant": "2026.9.0",
        "render_readme": True,
    }
