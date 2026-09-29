"""Tests that keep the documentation in step with the code."""

from pathlib import Path
import re

import pytest

from custom_components.ravelli_smart_wifi.models import SUPPORTED_MODELS
from custom_components.ravelli_smart_wifi.services import (
    SERVICE_DELETE_PROGRAM,
    SERVICE_SET_PROGRAM,
)

ROOT = Path(__file__).parent.parent
README = (ROOT / "README.md").read_text()
CHECKLIST = (ROOT / "docs" / "hardware-verification.md").read_text()
PRIVATE_ADDRESS = re.compile(
    r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b"
)


@pytest.mark.parametrize("model", [model.name for model in SUPPORTED_MODELS.values()])
def test_readme_lists_the_supported_models(model: str) -> None:
    """A reader must know whether the stove is supported before installing."""
    assert model in README


@pytest.mark.parametrize("action", [SERVICE_SET_PROGRAM, SERVICE_DELETE_PROGRAM])
def test_readme_documents_the_actions(action: str) -> None:
    """The actions have no entity; the README is where they are found."""
    assert f"ravelli_smart_wifi.{action}" in README


def test_readme_states_the_limits() -> None:
    """Unofficial, unauthenticated, and what is not verified."""
    assert "unofficial" in README.lower()
    assert "no authentication" in README.lower()
    assert "docs/hardware-verification.md" in README


@pytest.mark.parametrize("text", [README, CHECKLIST], ids=["readme", "checklist"])
def test_documentation_holds_no_private_address(text: str) -> None:
    """Examples use documentation addresses."""
    assert PRIVATE_ADDRESS.search(text) is None


def test_checklist_covers_the_open_points() -> None:
    """The points the spec lists as unverified."""
    for point in (
        "On and off",
        "Flue gas temperature",
        "Extractor speed",
        "Manual mode",
        "Schedule, names",
        "Schedule, write",
        "Schedule, switch",
        "Schedule, delete",
        "Clock",
        "DHCP hostname",
        "Answers to commands",
        "Diagnostics",
        "French interface",
        "Thermostat card",
        "Soak",
        "Schedule, switch with a foreign program",
    ):
        assert f"| {point} |" in CHECKLIST, point


def test_checklist_reads_names_before_writing() -> None:
    """The accented name test tells whether the write test is safe to run."""
    assert CHECKLIST.index("| Schedule, names |") < CHECKLIST.index(
        "| Schedule, write |"
    )


def test_readme_explains_debug_logging() -> None:
    """The checklist needs the raw answers of the module."""
    assert "custom_components.ravelli_smart_wifi: debug" in README
