# Ravelli Smart Wi-Fi Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a HACS-installable Home Assistant integration that controls Ravelli RDS pellet stoves through the local HTTP API of the Ravelli Smart Wi-Fi module.

**Architecture:** A Home-Assistant-free core (`api.py` for HTTP, `models.py` for registers and schedule) sits under one `DataUpdateCoordinator` that polls the module, serializes every request and applies the safety rules. Seven entity platforms, two schedule actions, a config flow and diagnostics read from that coordinator. Tests drive everything through one HTTP-level simulator of the module.

**Tech Stack:** Python 3.14, Home Assistant 2026.9.4, aiohttp, getmac 0.9.5, pytest with pytest-homeassistant-custom-component 0.13.367, ruff 0.16.9, uv, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-29-ravelli-smart-wifi-integration-design.md`

## Global Constraints

- Python 3.14 or later. Home Assistant 2026.9.0 or later.
- Pinned development tools: `pytest-homeassistant-custom-component==0.13.367`, `ruff==0.16.9`, `getmac==0.9.5`.
- Integration domain: `ravelli_smart_wifi`. Display name: `Ravelli Smart Wi-Fi`.
- Supported model codes: 7 (AIR-RDS), 11 (HYDRO-RDS), 12 (ECO-RDS). Every other code is refused.
- `api.py` and `models.py` import nothing from `homeassistant`.
- Every request to the module is a `POST` with the header `Content-Type: application/json; charset=utf-8` and a form-urlencoded body.
- Only registers listed in the model table are written. No action writes an arbitrary register.
- Writes are never retried automatically.
- Code, comments, commit messages and documentation are in English. Entity and flow texts exist in English and French.
- No personal data in any file or commit message: no names, no hostnames, no private IP addresses, no network names. Examples use `192.0.2.x` addresses and the MAC address `aa:bb:cc:dd:ee:ff`.
- Tests are written before the code they cover.
- Commit messages follow conventional commits and carry no attribution trailer.
- Git: every task is done on its own `feature/<slug>` branch created from `main`, then merged with `git merge --ff-only`. No merge commits. No commit is made directly on `main`.
- Versions are CalVer: tags `vYYYY.MM` and `vYYYY.MM.N`; the manifest version is the tag without `v`.
- Nothing is pushed to GitHub and no repository is created without the owner's explicit approval.

## Review Focus

These inputs are implied by the spec and are the most likely to reach a real user. Each one is pinned by a test in the task named at the end of the line.

1. The module answers a category read without a register the integration expects (module booting, or another firmware). Entities must show `unknown`, not crash. Tests in Task 2 and Task 8.
2. Something that is not the module answers at the address: an HTML page, a JSON array, an HTTP error. Setup must say "not a module" and polling must mark entities unavailable. Tests in Task 4, Task 5 and Task 6.
3. The user types the address with a scheme, spaces or a trailing slash (`http://192.0.2.10/`). The flow must accept it. Tests in Task 4 and Task 6.
4. A schedule program name contains `&`, `=`, a space or an accented letter. The first three must survive the form encoding; the last must be refused with a clear message. Tests in Task 3, Task 4 and Task 14.
5. The stove changes state between the last poll and an on/off command (an alarm is raised, ignition starts). The safety rules must use the state read at command time. Tests in Task 5.

## File Structure

```
ha-ravelli-smart-wifi/
├── .github/workflows/test.yml          ruff + pytest
├── .github/workflows/validate.yml      hassfest + HACS validation
├── .gitignore
├── LICENSE
├── README.md
├── hacs.json
├── pyproject.toml                      dev dependencies, pytest and ruff settings
├── uv.lock
├── custom_components/
│   ├── __init__.py                     empty, makes the package importable in tests
│   └── ravelli_smart_wifi/
│       ├── __init__.py                 setup and unload of a config entry, action registration
│       ├── api.py                      HTTP client, no Home Assistant import
│       ├── binary_sensor.py
│       ├── button.py
│       ├── calendar.py
│       ├── climate.py
│       ├── config_flow.py              user, DHCP, reconfigure and options flows
│       ├── const.py
│       ├── coordinator.py              polling, locking, safety rules, commands
│       ├── diagnostics.py
│       ├── entity.py                   base entity
│       ├── icons.json
│       ├── manifest.json
│       ├── models.py                   registers, state, schedule, clock; no Home Assistant import
│       ├── number.py
│       ├── sensor.py
│       ├── services.py                 the two schedule actions
│       ├── services.yaml
│       ├── switch.py
│       └── translations/{en,fr}.json
├── docs/
│   ├── hardware-verification.md
│   └── superpowers/{specs,plans}/
└── tests/
    ├── __init__.py
    ├── conftest.py                     shared fixtures
    ├── fake_module.py                  HTTP-level simulator of the module
    ├── fixtures/air_rds.json           anonymized capture of a real AIR-RDS module
    ├── helpers.py                      entity lookup and time travel
    └── test_*.py                       one file per source file
```

## How Every Task Starts and Ends

Each task names its branch. Start it with:

```bash
git checkout main
git checkout -b feature/<slug>
```

End it, once its review has passed, with:

```bash
git checkout main
git merge --ff-only feature/<slug>
git branch -d feature/<slug>
```

Run the whole check before every commit. The code blocks of this plan are
written for readability; `ruff format` decides the final layout, so run it
first and commit what it produces.

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

---

### Task 1: Project skeleton and tooling

**Branch:** `feature/project-skeleton`

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `hacs.json`
- Create: `custom_components/__init__.py`
- Create: `custom_components/ravelli_smart_wifi/__init__.py`
- Create: `custom_components/ravelli_smart_wifi/const.py`
- Create: `custom_components/ravelli_smart_wifi/manifest.json`
- Create: `.github/workflows/test.yml`, `.github/workflows/validate.yml`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the constants of `const.py` (names and values below), and the commands `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/project-skeleton
```

- [ ] **Step 2: Write the tooling files**

`pyproject.toml`:

```toml
[project]
name = "ha-ravelli-smart-wifi"
version = "0.0.0"
description = "Home Assistant integration for the Ravelli Smart Wi-Fi module"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = [
    "getmac==0.9.5",
    "pytest-homeassistant-custom-component==0.13.367",
    "ruff==0.16.9",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
target-version = "py314"
line-length = 88

[tool.ruff.lint]
select = ["B", "E", "F", "I", "RUF", "SIM", "UP"]
# E501: the formatter owns the line length.
# RUF012: Home Assistant entities declare list and dict class attributes.
ignore = ["E501", "RUF012"]

[tool.ruff.lint.isort]
force-sort-within-sections = true
known-first-party = ["custom_components", "tests"]
```

`.gitignore`:

```
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
.DS_Store
```

`tests/__init__.py`:

```python
"""Tests for the Ravelli Smart Wi-Fi integration."""
```

`tests/conftest.py`:

```python
"""Shared fixtures."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""
```

- [ ] **Step 3: Install the environment**

Run: `uv sync`
Expected: a `.venv` directory and a `uv.lock` file are created, and the output ends with a list of installed packages that includes `homeassistant==2026.9.4`.

- [ ] **Step 4: Write the failing test**

`tests/test_manifest.py`:

```python
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
    assert manifest["dhcp"] == [{"registered_devices": True}]


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
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'custom_components'`.

- [ ] **Step 6: Write the integration metadata**

`custom_components/__init__.py`:

```python
"""Custom components."""
```

`custom_components/ravelli_smart_wifi/__init__.py`:

```python
"""Ravelli Smart Wi-Fi integration."""
```

`custom_components/ravelli_smart_wifi/const.py`:

```python
"""Constants of the Ravelli Smart Wi-Fi integration."""

from typing import Final

DOMAIN: Final = "ravelli_smart_wifi"
MANUFACTURER: Final = "Ravelli"
ISSUE_URL: Final = "https://github.com/Greite/ha-ravelli-smart-wifi/issues"

# Polling, in seconds.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 300
# System status and schedule change rarely.
SLOW_REFRESH_INTERVAL: Final = 600
# Gaps between the polls that follow a command: polls at 2, 5, 10, 20 and 30 s.
FAST_REFRESH_STEPS: Final = (2, 3, 5, 10, 10)

# Network scan of the config flow.
SCAN_TIMEOUT: Final = 1.5
SCAN_CONCURRENCY: Final = 32
SCAN_MIN_PREFIX: Final = 22

# Register categories dumped by the diagnostics download: 0 to 12.
DIAGNOSTIC_CATEGORIES: Final = 13
```

`custom_components/ravelli_smart_wifi/manifest.json`:

```json
{
  "domain": "ravelli_smart_wifi",
  "name": "Ravelli Smart Wi-Fi",
  "codeowners": ["@Greite"],
  "config_flow": true,
  "dependencies": ["network"],
  "dhcp": [{ "registered_devices": true }],
  "documentation": "https://github.com/Greite/ha-ravelli-smart-wifi",
  "integration_type": "device",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/Greite/ha-ravelli-smart-wifi/issues",
  "requirements": ["getmac==0.9.5"],
  "version": "2026.10"
}
```

`hacs.json`:

```json
{
  "name": "Ravelli Smart Wi-Fi",
  "homeassistant": "2026.9.0",
  "render_readme": true
}
```

- [ ] **Step 7: Write the licence, the first README and the workflows**

`LICENSE` (the same MIT text and copyright holder as the owner's other repositories):

```
MIT License

Copyright (c) 2026 Gauthier Painteaux

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`README.md` (replaced by the full version in Task 16):

```markdown
# Ravelli Smart Wi-Fi for Home Assistant

Unofficial Home Assistant integration for Ravelli pellet stoves fitted with
the Ravelli Smart Wi-Fi module. Work in progress.
```

`.github/workflows/test.yml`:

```yaml
name: Test

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest
```

`.github/workflows/validate.yml`:

```yaml
name: Validate

on:
  push:
  pull_request:
  schedule:
    - cron: "0 3 * * 1"

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: hacs/action@main
        with:
          category: integration
          ignore: brands
```

- [ ] **Step 8: Run the checks to verify they pass**

Run: `uv run pytest -v`
Expected: 3 passed.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!` and no file listed as needing a reformat.

- [ ] **Step 9: Commit and integrate**

```bash
git add -A
git commit -m "chore: add project skeleton, tooling and CI"
git checkout main
git merge --ff-only feature/project-skeleton
git branch -d feature/project-skeleton
```

---

### Task 2: Register model and stove state

**Branch:** `feature/register-model`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces, all in `models.py`:
  - Register constants: `REG_AMBIENT_TEMP = 0`, `REG_WATER_TEMP = 1`, `REG_STATUS = 2`, `REG_ALARM = 3`, `REG_FLUE_TEMP = 4`, `REG_EXTRACTOR = 5`, `REG_DUCT_RIGHT_TEMP = 24`, `REG_DUCT_LEFT_TEMP = 25`, `REG_WATER_SETPOINT = 49`, `REG_SETPOINT = 50`, `REG_POWER = 51`, `REG_CLOCK_WEEKDAY = 59` to `REG_CLOCK_YEAR = 64`, `REG_COMFORT_DELAY = 73`, `REG_COMFORT_DELTA = 74`, `REG_DUCT_RIGHT_SETPOINT = 184`, `REG_DUCT_LEFT_SETPOINT = 185`.
  - `CATEGORY_MAIN = 2`, `MANUAL_SETPOINT = 41`, `WATER_MANUAL_SETPOINT = 81`, `DUCT_OFF = 5`, `DUCT_EXTERNAL = 6`.
  - `STATUS_KEYS: dict[int, str]`, `STATUS_UNKNOWN = "unknown"`.
  - `WRITE_BOUNDS: dict[int, tuple[int, int]]`.
  - `StoveModel` (fields `code`, `name`, `categories`, `writable`, `has_ducting`, `has_water`) and `SUPPORTED_MODELS: dict[int, StoveModel]`.
  - `InvalidPayloadError`, `RegisterNotWritableError`, `ValueOutOfRangeError` (attributes `register`, `value`, `minimum`, `maximum`), all subclasses of `ValueError`.
  - `parse_registers(payload: Any) -> dict[int, int]`.
  - `validate_write(model: StoveModel, register: int, value: int) -> None`.
  - `StoveState` with `from_payloads(payloads: list[Any]) -> StoveState`, `raw(register: int) -> int | None` and the properties `status_code`, `status_key`, `is_on`, `is_igniting`, `in_alarm`, `has_alarm`, `ambient_temperature`, `is_manual`, `setpoint`, `power`, `flue_temperature`, `extractor_speed`, `water_temperature`, `water_setpoint`; fields `model`, `registers`, `flame`, `alarm_text`, `name`.
  - `to_bcd(value: int) -> int`, `from_bcd(raw: int) -> int`, `encode_clock(now: datetime) -> list[tuple[int, int]]`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/register-model
```

- [ ] **Step 2: Write the failing tests**

`tests/test_models.py`:

```python
"""Tests for the register model."""

from datetime import datetime
from typing import Any

import pytest

from custom_components.ravelli_smart_wifi.models import (
    SUPPORTED_MODELS,
    InvalidPayloadError,
    RegisterNotWritableError,
    StoveState,
    ValueOutOfRangeError,
    encode_clock,
    from_bcd,
    parse_registers,
    to_bcd,
    validate_write,
)

MAIN = [[0, 44], [2, 0], [3, 0], [4, 0], [5, 0], [37, 0], [50, 22], [51, 1]]


def payload(params: list[list[int]], **extra: Any) -> dict[str, Any]:
    """Build the answer to a category read."""
    return {
        "params": params,
        "model": 7,
        "flame": 255,
        "alr": "",
        "name": "NO NAME",
        **extra,
    }


def state(registers: dict[int, int], **extra: Any) -> StoveState:
    """Build a state from a register mapping."""
    params = [[register, value] for register, value in registers.items()]
    return StoveState.from_payloads([payload(params, **extra)])


def test_main_registers_are_decoded() -> None:
    """A capture of an idle AIR-RDS stove decodes to readable values."""
    decoded = StoveState.from_payloads([payload(MAIN)])

    assert decoded.model == 7
    assert decoded.status_code == 0
    assert decoded.status_key == "off"
    assert decoded.ambient_temperature == 22.0
    assert decoded.setpoint == 22
    assert decoded.power == 1
    assert decoded.flue_temperature == 0
    assert decoded.extractor_speed == 0
    assert decoded.flame is None
    assert decoded.alarm_text == ""
    assert decoded.name == "NO NAME"
    assert decoded.is_on is False
    assert decoded.has_alarm is False


def test_categories_are_merged_and_the_last_answer_wins() -> None:
    """Registers of all categories end up in one state."""
    decoded = StoveState.from_payloads(
        [
            payload(MAIN),
            payload([[2, 0], [24, 0], [25, 19], [184, 5], [185, 22]]),
            payload([[2, 5], [73, 0], [74, 1]], flame=1, alr=" AL05 NO IGNITION "),
        ]
    )

    assert decoded.raw(185) == 22
    assert decoded.raw(74) == 1
    assert decoded.raw(999) is None
    assert decoded.status_key == "working"
    assert decoded.flame == 1
    assert decoded.alarm_text == "AL05 NO IGNITION"


@pytest.mark.parametrize(
    ("code", "key", "is_on", "is_igniting", "in_alarm"),
    [
        (0, "off", False, False, False),
        (1, "pellet_loading", True, True, False),
        (2, "ignition", True, True, False),
        (3, "waiting_flame", True, True, False),
        (4, "flame_present", True, True, False),
        (5, "working", True, False, False),
        (6, "final_cleaning", False, False, False),
        (7, "eco_stop", True, False, False),
        (8, "alarm", False, False, True),
        (9, "alarm_memory", False, False, True),
        (42, "unknown", False, False, False),
    ],
)
def test_status_table(
    code: int, key: str, is_on: bool, is_igniting: bool, in_alarm: bool
) -> None:
    """Every status code has a key and the flags the safety rules use."""
    decoded = state({2: code})

    assert decoded.status_key == key
    assert decoded.is_on is is_on
    assert decoded.is_igniting is is_igniting
    assert decoded.in_alarm is in_alarm


def test_manual_set_point_has_no_temperature() -> None:
    """Raw 41 means manual mode, not 41 degrees."""
    decoded = state({2: 0, 50: 41})

    assert decoded.is_manual is True
    assert decoded.setpoint is None


def test_missing_registers_give_none() -> None:
    """A category answer without the usual registers must not raise."""
    decoded = state({2: 5})

    assert decoded.ambient_temperature is None
    assert decoded.setpoint is None
    assert decoded.is_manual is False
    assert decoded.power is None
    assert decoded.flue_temperature is None
    assert decoded.extractor_speed is None
    assert decoded.water_temperature is None
    assert decoded.water_setpoint is None


def test_zero_ambient_temperature_means_no_reading() -> None:
    """The vendor UI shows dashes for a raw value of 0."""
    assert state({2: 0, 0: 0}).ambient_temperature is None


def test_half_degrees_are_kept() -> None:
    """The ambient probe has a resolution of half a degree."""
    assert state({2: 0, 0: 43}).ambient_temperature == 21.5


def test_alarm_register_raises_the_alarm_flag() -> None:
    """An alarm code counts even when the status is not an alarm status."""
    assert state({2: 5, 3: 4}).has_alarm is True
    assert state({2: 8, 3: 0}).has_alarm is True


def test_water_registers() -> None:
    """The hydro model adds a water probe and a water set point."""
    assert state({2: 5, 1: 45, 49: 60}).water_temperature == 45
    assert state({2: 5, 1: 45, 49: 60}).water_setpoint == 60
    assert state({2: 5, 1: 0, 49: 81}).water_temperature is None
    assert state({2: 5, 1: 0, 49: 81}).water_setpoint is None


@pytest.mark.parametrize(
    "answer",
    [
        None,
        [],
        "text",
        {},
        {"params": None},
        {"params": [[1]]},
        {"params": [[1, 2, 3]]},
        {"params": [["1", 2]]},
        {"params": [[1, 2.5]]},
        {"params": [[1, True]]},
        {"params": ["12"]},
    ],
)
def test_malformed_answers_are_rejected(answer: Any) -> None:
    """Anything that is not a list of integer pairs is refused."""
    with pytest.raises(InvalidPayloadError):
        parse_registers(answer)


def test_status_register_is_required() -> None:
    """A state without a status cannot be trusted."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([payload([[0, 44]])])


def test_no_answer_is_rejected() -> None:
    """At least one category is needed."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([])


def test_model_must_be_a_number() -> None:
    """The model code drives the register table."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([payload(MAIN, model="7")])


def test_only_the_rds_family_is_supported() -> None:
    """Three model codes, with the categories each one polls."""
    assert sorted(SUPPORTED_MODELS) == [7, 11, 12]
    assert SUPPORTED_MODELS[7].name == "AIR-RDS"
    assert SUPPORTED_MODELS[11].name == "HYDRO-RDS"
    assert SUPPORTED_MODELS[12].name == "ECO-RDS"
    assert SUPPORTED_MODELS[7].categories == (2, 6, 11)
    assert SUPPORTED_MODELS[11].categories == (2, 11)
    assert SUPPORTED_MODELS[12].categories == (2, 11)
    assert SUPPORTED_MODELS[7].has_ducting and not SUPPORTED_MODELS[7].has_water
    assert SUPPORTED_MODELS[11].has_water and not SUPPORTED_MODELS[11].has_ducting
    assert not SUPPORTED_MODELS[12].has_water
    assert not SUPPORTED_MODELS[12].has_ducting


@pytest.mark.parametrize(
    ("model", "register", "value"),
    [
        (7, 50, 5),
        (7, 50, 41),
        (7, 51, 1),
        (7, 51, 5),
        (7, 73, 0),
        (7, 73, 9),
        (7, 74, 0),
        (7, 74, 20),
        (7, 184, 5),
        (7, 185, 41),
        (7, 59, 7),
        (7, 60, 0x23),
        (11, 49, 30),
        (11, 49, 81),
        (12, 50, 20),
    ],
)
def test_valid_writes_pass(model: int, register: int, value: int) -> None:
    """The bounds are those of the vendor UI, both ends included."""
    validate_write(SUPPORTED_MODELS[model], register, value)


@pytest.mark.parametrize(
    ("register", "value", "minimum", "maximum"),
    [
        (50, 4, 5, 41),
        (50, 42, 5, 41),
        (51, 0, 1, 5),
        (51, 6, 1, 5),
        (73, 10, 0, 9),
        (74, 21, 0, 20),
        (184, 4, 5, 41),
        (60, 0x24, 0x00, 0x23),
    ],
)
def test_out_of_range_writes_are_refused(
    register: int, value: int, minimum: int, maximum: int
) -> None:
    """The error carries what the message needs."""
    with pytest.raises(ValueOutOfRangeError) as err:
        validate_write(SUPPORTED_MODELS[7], register, value)

    assert err.value.register == register
    assert err.value.value == value
    assert err.value.minimum == minimum
    assert err.value.maximum == maximum


@pytest.mark.parametrize(
    ("model", "register"),
    [(7, 49), (11, 184), (12, 184), (12, 49), (7, 0), (7, 2), (7, 999)],
)
def test_registers_outside_the_table_are_refused(model: int, register: int) -> None:
    """Read-only, unknown and other-model registers cannot be written."""
    with pytest.raises(RegisterNotWritableError):
        validate_write(SUPPORTED_MODELS[model], register, 20)


def test_bcd_round_trip() -> None:
    """The clock registers hold two decimal digits in one byte."""
    assert to_bcd(0) == 0x00
    assert to_bcd(18) == 0x18
    assert to_bcd(59) == 0x59
    assert from_bcd(0x57) == 57
    for value in range(100):
        assert from_bcd(to_bcd(value)) == value


@pytest.mark.parametrize("value", [-1, 100])
def test_bcd_holds_two_digits_only(value: int) -> None:
    """Three digits do not fit."""
    with pytest.raises(ValueError, match="two decimal digits"):
        to_bcd(value)


def test_clock_encoding() -> None:
    """Tuesday 29 September 2026, 18:57."""
    assert encode_clock(datetime(2026, 9, 29, 18, 57)) == [
        (59, 2),
        (60, 0x18),
        (61, 0x57),
        (62, 0x29),
        (63, 0x09),
        (64, 0x26),
    ]


def test_sunday_is_day_seven() -> None:
    """The module counts Monday as 1 and Sunday as 7."""
    assert encode_clock(datetime(2026, 10, 4, 0, 0))[0] == (59, 7)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'custom_components.ravelli_smart_wifi.models'`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/models.py`:

```python
"""Register tables and data model of the RDS stove family.

This module imports nothing from Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

REG_AMBIENT_TEMP = 0
REG_WATER_TEMP = 1
REG_STATUS = 2
REG_ALARM = 3
REG_FLUE_TEMP = 4
REG_EXTRACTOR = 5
REG_DUCT_RIGHT_TEMP = 24
REG_DUCT_LEFT_TEMP = 25
REG_WATER_SETPOINT = 49
REG_SETPOINT = 50
REG_POWER = 51
REG_CLOCK_WEEKDAY = 59
REG_CLOCK_HOUR = 60
REG_CLOCK_MINUTE = 61
REG_CLOCK_DAY = 62
REG_CLOCK_MONTH = 63
REG_CLOCK_YEAR = 64
REG_COMFORT_DELAY = 73
REG_COMFORT_DELTA = 74
REG_DUCT_RIGHT_SETPOINT = 184
REG_DUCT_LEFT_SETPOINT = 185

CATEGORY_MAIN = 2
CATEGORY_DUCTING = 6
CATEGORY_COMFORT = 11

# Special raw values of the set point registers.
MANUAL_SETPOINT = 41
WATER_MANUAL_SETPOINT = 81
DUCT_OFF = 5
DUCT_EXTERNAL = 6

# The module reports 255 when the board has no flame information.
FLAME_UNSUPPORTED = 255

STATUS_KEYS: dict[int, str] = {
    0: "off",
    1: "pellet_loading",
    2: "ignition",
    3: "waiting_flame",
    4: "flame_present",
    5: "working",
    6: "final_cleaning",
    7: "eco_stop",
    8: "alarm",
    9: "alarm_memory",
}
STATUS_UNKNOWN = "unknown"
STATUS_IGNITING = frozenset({1, 2, 3, 4})
STATUS_ON = frozenset({1, 2, 3, 4, 5, 7})
STATUS_ALARM = frozenset({8, 9})

# Raw bounds of every writable register, as enforced by the vendor UI.
WRITE_BOUNDS: dict[int, tuple[int, int]] = {
    REG_WATER_SETPOINT: (30, WATER_MANUAL_SETPOINT),
    REG_SETPOINT: (5, MANUAL_SETPOINT),
    REG_POWER: (1, 5),
    REG_CLOCK_WEEKDAY: (1, 7),
    REG_CLOCK_HOUR: (0x00, 0x23),
    REG_CLOCK_MINUTE: (0x00, 0x59),
    REG_CLOCK_DAY: (0x01, 0x31),
    REG_CLOCK_MONTH: (0x01, 0x12),
    REG_CLOCK_YEAR: (0x00, 0x99),
    REG_COMFORT_DELAY: (0, 9),
    REG_COMFORT_DELTA: (0, 20),
    REG_DUCT_RIGHT_SETPOINT: (DUCT_OFF, 41),
    REG_DUCT_LEFT_SETPOINT: (DUCT_OFF, 41),
}

_COMMON_WRITABLE = frozenset(
    {
        REG_SETPOINT,
        REG_POWER,
        REG_CLOCK_WEEKDAY,
        REG_CLOCK_HOUR,
        REG_CLOCK_MINUTE,
        REG_CLOCK_DAY,
        REG_CLOCK_MONTH,
        REG_CLOCK_YEAR,
        REG_COMFORT_DELAY,
        REG_COMFORT_DELTA,
    }
)


class InvalidPayloadError(ValueError):
    """The module answered with data that cannot be decoded."""


class RegisterNotWritableError(ValueError):
    """The register is not writable on this stove model."""

    def __init__(self, register: int) -> None:
        """Remember the register."""
        super().__init__(f"register {register} is not writable")
        self.register = register


class ValueOutOfRangeError(ValueError):
    """The value is outside the bounds of the register."""

    def __init__(self, register: int, value: int, minimum: int, maximum: int) -> None:
        """Remember what the error message needs."""
        super().__init__(
            f"value {value} for register {register} is outside {minimum}..{maximum}"
        )
        self.register = register
        self.value = value
        self.minimum = minimum
        self.maximum = maximum


@dataclass(frozen=True, slots=True)
class StoveModel:
    """What the integration knows about one board model."""

    code: int
    name: str
    categories: tuple[int, ...]
    writable: frozenset[int]
    has_ducting: bool = False
    has_water: bool = False


SUPPORTED_MODELS: dict[int, StoveModel] = {
    7: StoveModel(
        code=7,
        name="AIR-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_DUCTING, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE
        | {REG_DUCT_RIGHT_SETPOINT, REG_DUCT_LEFT_SETPOINT},
        has_ducting=True,
    ),
    11: StoveModel(
        code=11,
        name="HYDRO-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE | {REG_WATER_SETPOINT},
        has_water=True,
    ),
    12: StoveModel(
        code=12,
        name="ECO-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE,
    ),
}


def _is_int(value: object) -> bool:
    """Tell a real integer from a boolean or a float."""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_registers(payload: Any) -> dict[int, int]:
    """Turn the answer to a category read into a register mapping."""
    if not isinstance(payload, dict):
        raise InvalidPayloadError("the answer is not an object")
    params = payload.get("params")
    if not isinstance(params, list):
        raise InvalidPayloadError("the answer has no register list")
    registers: dict[int, int] = {}
    for item in params:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not _is_int(item[0])
            or not _is_int(item[1])
        ):
            raise InvalidPayloadError(f"malformed register entry: {item!r}")
        registers[item[0]] = item[1]
    return registers


def validate_write(model: StoveModel, register: int, value: int) -> None:
    """Refuse a write the vendor UI would not allow."""
    if register not in model.writable:
        raise RegisterNotWritableError(register)
    minimum, maximum = WRITE_BOUNDS[register]
    if not minimum <= value <= maximum:
        raise ValueOutOfRangeError(register, value, minimum, maximum)


@dataclass(frozen=True, slots=True)
class StoveState:
    """State of the stove, decoded from one or more category reads."""

    model: int
    registers: dict[int, int]
    flame: int | None
    alarm_text: str
    name: str

    @classmethod
    def from_payloads(cls, payloads: list[Any]) -> StoveState:
        """Merge the category answers of one polling cycle."""
        if not payloads:
            raise InvalidPayloadError("there is no answer to decode")
        registers: dict[int, int] = {}
        for payload in payloads:
            registers.update(parse_registers(payload))
        if REG_STATUS not in registers:
            raise InvalidPayloadError("the status register is missing")
        last = payloads[-1]
        model = last.get("model")
        if not _is_int(model):
            raise InvalidPayloadError("the model code is missing")
        flame = last.get("flame")
        return cls(
            model=model,
            registers=registers,
            flame=flame if _is_int(flame) and flame != FLAME_UNSUPPORTED else None,
            alarm_text=str(last.get("alr") or "").strip(),
            name=str(last.get("name") or ""),
        )

    def raw(self, register: int) -> int | None:
        """Return the raw value of a register, if the module sent it."""
        return self.registers.get(register)

    @property
    def status_code(self) -> int:
        """Raw status code."""
        return self.registers[REG_STATUS]

    @property
    def status_key(self) -> str:
        """Status as a translation key."""
        return STATUS_KEYS.get(self.status_code, STATUS_UNKNOWN)

    @property
    def is_on(self) -> bool:
        """Whether the stove is running or about to."""
        return self.status_code in STATUS_ON

    @property
    def is_igniting(self) -> bool:
        """Whether the stove is between the on command and steady work."""
        return self.status_code in STATUS_IGNITING

    @property
    def in_alarm(self) -> bool:
        """Whether the status is an alarm status."""
        return self.status_code in STATUS_ALARM

    @property
    def has_alarm(self) -> bool:
        """Whether an alarm is active or waiting to be acknowledged."""
        return self.in_alarm or bool(self.raw(REG_ALARM))

    @property
    def ambient_temperature(self) -> float | None:
        """Ambient temperature in degrees Celsius."""
        raw = self.raw(REG_AMBIENT_TEMP)
        return raw / 2 if raw else None

    @property
    def is_manual(self) -> bool:
        """Whether the stove ignores the ambient set point."""
        return self.raw(REG_SETPOINT) == MANUAL_SETPOINT

    @property
    def setpoint(self) -> int | None:
        """Ambient set point in degrees Celsius, None in manual mode."""
        raw = self.raw(REG_SETPOINT)
        return None if raw == MANUAL_SETPOINT else raw

    @property
    def power(self) -> int | None:
        """Power level, 1 to 5."""
        return self.raw(REG_POWER)

    @property
    def flue_temperature(self) -> int | None:
        """Flue gas temperature, raw."""
        return self.raw(REG_FLUE_TEMP)

    @property
    def extractor_speed(self) -> int | None:
        """Extractor speed, raw."""
        return self.raw(REG_EXTRACTOR)

    @property
    def water_temperature(self) -> int | None:
        """Water temperature in degrees Celsius."""
        return self.raw(REG_WATER_TEMP) or None

    @property
    def water_setpoint(self) -> int | None:
        """Water set point in degrees Celsius, None in manual mode."""
        raw = self.raw(REG_WATER_SETPOINT)
        return None if raw == WATER_MANUAL_SETPOINT else raw


def to_bcd(value: int) -> int:
    """Encode two decimal digits in one byte."""
    if not 0 <= value <= 99:
        raise ValueError(f"{value} does not fit in two decimal digits")
    return (value // 10) * 16 + value % 10


def from_bcd(raw: int) -> int:
    """Decode one byte holding two decimal digits."""
    return (raw >> 4) * 10 + (raw & 0x0F)


def encode_clock(now: datetime) -> list[tuple[int, int]]:
    """Return the register writes that set the stove clock to a local time."""
    return [
        (REG_CLOCK_WEEKDAY, now.isoweekday()),
        (REG_CLOCK_HOUR, to_bcd(now.hour)),
        (REG_CLOCK_MINUTE, to_bcd(now.minute)),
        (REG_CLOCK_DAY, to_bcd(now.day)),
        (REG_CLOCK_MONTH, to_bcd(now.month)),
        (REG_CLOCK_YEAR, to_bcd(now.year % 100)),
    ]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: all tests pass, none skipped.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!`. If ruff reports a formatting difference, run `uv run ruff format .` and look at the diff before committing.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add register model and stove state"
git checkout main
git merge --ff-only feature/register-model
git branch -d feature/register-model
```

---

### Task 3: Schedule model

**Branch:** `feature/schedule-model`

**Files:**
- Modify: `custom_components/ravelli_smart_wifi/models.py` (append at the end; add two imports at the top)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes from Task 2: `InvalidPayloadError`, `MANUAL_SETPOINT`, `_is_int`.
- Produces, all in `models.py`:
  - `WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")`, `SLOT_COUNT = 6`, `NAME_MAX_LENGTH = 15`.
  - `ScheduleValidationError(ValueError)` with the attribute `key: str`. Keys: `slot_range`, `name_length`, `name_characters`, `time_step`, `end_before_start`, `no_time`, `no_weekday`, `temperature_range`, `power_range`.
  - `ScheduleProgram(name: str, enabled: bool, start: time | None, end: time | None, temperature: int, power: int, weekdays: frozenset[str])` with `validate() -> None`, `from_raw(raw: Any) -> ScheduleProgram | None` and `to_fields(slot: int) -> dict[str, int | str]`.
  - `Schedule(enabled: bool, programs: tuple[ScheduleProgram | None, ...])` with `from_payload(payload: Any) -> Schedule`, `to_fields() -> dict[str, int | str]`, `with_enabled(enabled: bool) -> Schedule` and `with_program(slot: int, program: ScheduleProgram | None) -> Schedule`. Slots are numbered 1 to 6.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/schedule-model
```

- [ ] **Step 2: Write the failing tests**

`tests/test_schedule.py`:

```python
"""Tests for the schedule model."""

from dataclasses import replace
from datetime import time
from typing import Any

import pytest

from custom_components.ravelli_smart_wifi.models import (
    InvalidPayloadError,
    Schedule,
    ScheduleProgram,
    ScheduleValidationError,
)

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
FREE_RAW = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""]
ALL_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
EVENING = ScheduleProgram(
    name="Evening",
    enabled=True,
    start=time(18, 0),
    end=time(22, 30),
    temperature=22,
    power=1,
    weekdays=ALL_DAYS,
)
EVENING_FIELDS = {
    "p011": 1,
    "p012": 200,
    "p013": 218,
    "p014": 22,
    "p015": 1,
    "p016": 127,
    "p017": "Evening",
}


def answer(*programs: list[Any], enabled: bool = True) -> dict[str, Any]:
    """Build the answer to a schedule read, padded to six slots."""
    rows = [*programs, *([FREE_RAW] * (6 - len(programs)))]
    return {"key": 33, "enabled": enabled, "programs": rows}


def test_program_is_decoded() -> None:
    """Quarters of an hour become minutes and the mask becomes weekdays."""
    assert ScheduleProgram.from_raw(EVENING_RAW) == EVENING


@pytest.mark.parametrize(
    "raw",
    [
        FREE_RAW,
        [2, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"],
        [1, 1, 18, 0, 1, 22, 2, 22, 0, 127, "Evening"],
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, ""],
    ],
)
def test_free_slots_decode_to_none(raw: list[Any]) -> None:
    """The vendor UI skips a row with power 0, enabled above 1 or no name."""
    assert ScheduleProgram.from_raw(raw) is None


def test_disabled_times_are_none() -> None:
    """A program can have a stop time only."""
    program = ScheduleProgram.from_raw([1, 0, 18, 0, 1, 22, 2, 22, 1, 127, "Stop"])

    assert program is not None
    assert program.start is None
    assert program.end == time(22, 30)


def test_disabled_program_is_kept() -> None:
    """A disabled program still occupies its slot."""
    program = ScheduleProgram.from_raw([0, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Off"])

    assert program is not None
    assert program.enabled is False


def test_weekday_mask() -> None:
    """Bit 0 is Monday and bit 6 is Sunday."""
    week = ScheduleProgram.from_raw([1, 1, 6, 2, 1, 8, 0, 21, 3, 0b0011111, "Week"])
    sunday = ScheduleProgram.from_raw([1, 1, 6, 2, 1, 8, 0, 21, 3, 0b1000000, "Sun"])

    assert week is not None
    assert week.weekdays == frozenset({"mon", "tue", "wed", "thu", "fri"})
    assert sunday is not None
    assert sunday.weekdays == frozenset({"sun"})


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        "text",
        EVENING_RAW[:10],
        [*EVENING_RAW, 1],
        [1, 1, 24, 0, 1, 22, 2, 22, 1, 127, "Hour"],
        [1, 1, 18, 4, 1, 22, 2, 22, 1, 127, "Quarter"],
        [1, 1, "18", 0, 1, 22, 2, 22, 1, 127, "Text"],
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, 5],
    ],
)
def test_malformed_programs_are_rejected(raw: Any) -> None:
    """A short row must raise a decoding error, not an IndexError."""
    with pytest.raises(InvalidPayloadError):
        ScheduleProgram.from_raw(raw)


def test_program_fields() -> None:
    """Start and stop are packed as enabled, hour and quarter."""
    assert EVENING.to_fields(1) == EVENING_FIELDS


def test_fields_carry_the_slot_number() -> None:
    """Slot 4 uses the prefix p04."""
    assert sorted(EVENING.to_fields(4)) == [
        "p041",
        "p042",
        "p043",
        "p044",
        "p045",
        "p046",
        "p047",
    ]


def test_disabled_time_is_encoded_as_zero() -> None:
    """No enabled bit, no hour, no quarter."""
    assert replace(EVENING, start=None).to_fields(1)["p012"] == 0


def test_schedule_round_trip() -> None:
    """What is read can be written back unchanged."""
    schedule = Schedule.from_payload(answer(EVENING_RAW))

    assert schedule.enabled is True
    assert schedule.programs == (EVENING, None, None, None, None, None)
    assert schedule.to_fields() == {"enabled": 1, **EVENING_FIELDS}


def test_disabled_schedule() -> None:
    """The global flag is sent as 0 or 1."""
    schedule = Schedule.from_payload(answer(EVENING_RAW, enabled=False))

    assert schedule.enabled is False
    assert schedule.to_fields()["enabled"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"programs": "text"},
        {"programs": []},
        {"programs": [FREE_RAW] * 5},
        {"programs": [FREE_RAW] * 7},
    ],
)
def test_malformed_schedules_are_rejected(payload: Any) -> None:
    """The module always sends six rows."""
    with pytest.raises(InvalidPayloadError):
        Schedule.from_payload(payload)


def test_with_program_replaces_one_slot() -> None:
    """The other slots are untouched."""
    morning = replace(EVENING, name="Morning", start=time(6, 30), end=time(8, 0))
    schedule = Schedule.from_payload(answer(EVENING_RAW)).with_program(3, morning)

    assert schedule.programs == (EVENING, None, morning, None, None, None)
    assert schedule.with_program(1, None).programs[0] is None


@pytest.mark.parametrize("slot", [0, 7, -1])
def test_slot_must_exist(slot: int) -> None:
    """Slots are numbered 1 to 6."""
    with pytest.raises(ScheduleValidationError) as err:
        Schedule.from_payload(answer()).with_program(slot, EVENING)

    assert err.value.key == "slot_range"


def test_with_enabled_keeps_the_programs() -> None:
    """Only the global flag changes."""
    schedule = Schedule.from_payload(answer(EVENING_RAW)).with_enabled(False)

    assert schedule.enabled is False
    assert schedule.programs[0] == EVENING


@pytest.mark.parametrize(
    "program",
    [
        EVENING,
        replace(EVENING, temperature=41),
        replace(EVENING, temperature=5, power=5),
        replace(EVENING, start=None),
        replace(EVENING, end=None),
        replace(EVENING, enabled=False, start=None, end=None),
        replace(EVENING, name="A & B = C"),
        replace(EVENING, name="x" * 15),
        replace(EVENING, weekdays=frozenset({"sun"})),
    ],
)
def test_valid_programs_pass(program: ScheduleProgram) -> None:
    """Separators of the form encoding are allowed in a name."""
    program.validate()


@pytest.mark.parametrize(
    ("changes", "key"),
    [
        ({"name": ""}, "name_length"),
        ({"name": "   "}, "name_length"),
        ({"name": "x" * 16}, "name_length"),
        ({"name": "Café"}, "name_characters"),
        ({"name": "a\tb"}, "name_characters"),
        ({"start": time(18, 10)}, "time_step"),
        ({"end": time(22, 30, 5)}, "time_step"),
        ({"end": time(18, 0)}, "end_before_start"),
        ({"end": time(17, 45)}, "end_before_start"),
        ({"start": None, "end": None}, "no_time"),
        ({"weekdays": frozenset()}, "no_weekday"),
        ({"weekdays": frozenset({"mon", "someday"})}, "no_weekday"),
        ({"temperature": 4}, "temperature_range"),
        ({"temperature": 42}, "temperature_range"),
        ({"power": 0}, "power_range"),
        ({"power": 6}, "power_range"),
    ],
)
def test_invalid_programs_are_refused(changes: dict[str, Any], key: str) -> None:
    """Every rule of the vendor UI has its own error key."""
    with pytest.raises(ScheduleValidationError) as err:
        replace(EVENING, **changes).validate()

    assert err.value.key == key
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_schedule.py -v`
Expected: collection error, `ImportError: cannot import name 'Schedule' from 'custom_components.ravelli_smart_wifi.models'`.

- [ ] **Step 4: Write the implementation**

In `custom_components/ravelli_smart_wifi/models.py`, replace the two import lines

```python
from dataclasses import dataclass
from datetime import datetime
```

with

```python
from dataclasses import dataclass, replace
from datetime import datetime, time
```

and append this at the end of the file:

```python
WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SLOT_COUNT = 6
NAME_MAX_LENGTH = 15
_PROGRAM_LENGTH = 11
_QUARTER = 15


class ScheduleValidationError(ValueError):
    """A schedule program breaks a rule of the vendor UI."""

    def __init__(self, key: str) -> None:
        """Remember which rule was broken."""
        super().__init__(key)
        self.key = key


def _decode_time(enabled: int, hour: int, quarter: int) -> time | None:
    """Decode one start or stop time."""
    if not 0 <= hour <= 23 or not 0 <= quarter <= 3:
        raise InvalidPayloadError(f"malformed time: {hour}h, quarter {quarter}")
    return time(hour, quarter * _QUARTER) if enabled == 1 else None


def _encode_time(moment: time | None) -> int:
    """Pack one start or stop time as enabled, hour and quarter."""
    if moment is None:
        return 0
    return 1 << 7 | moment.hour << 2 | moment.minute // _QUARTER


@dataclass(frozen=True, slots=True)
class ScheduleProgram:
    """One of the six programs stored by the module."""

    name: str
    enabled: bool
    start: time | None
    end: time | None
    temperature: int
    power: int
    weekdays: frozenset[str]

    @classmethod
    def from_raw(cls, raw: Any) -> ScheduleProgram | None:
        """Decode one row of a schedule read; None is a free slot."""
        if not isinstance(raw, list) or len(raw) != _PROGRAM_LENGTH:
            raise InvalidPayloadError(f"malformed program: {raw!r}")
        *numbers, name = raw
        if not isinstance(name, str) or not all(_is_int(item) for item in numbers):
            raise InvalidPayloadError(f"malformed program: {raw!r}")
        (
            enabled,
            start_enabled,
            start_hour,
            start_quarter,
            stop_enabled,
            stop_hour,
            stop_quarter,
            temperature,
            power,
            days,
        ) = numbers
        # Same test as the vendor UI; a free slot may hold anything else.
        if enabled > 1 or power == 0 or not name:
            return None
        return cls(
            name=name,
            enabled=enabled == 1,
            start=_decode_time(start_enabled, start_hour, start_quarter),
            end=_decode_time(stop_enabled, stop_hour, stop_quarter),
            temperature=temperature,
            power=power,
            weekdays=frozenset(
                day for bit, day in enumerate(WEEKDAYS) if days >> bit & 1
            ),
        )

    def validate(self) -> None:
        """Apply the rules the vendor UI applies before saving."""
        if not self.name.strip() or len(self.name) > NAME_MAX_LENGTH:
            raise ScheduleValidationError("name_length")
        if any(not " " <= char <= "~" for char in self.name):
            raise ScheduleValidationError("name_characters")
        for moment in (self.start, self.end):
            if moment is not None and (
                moment.minute % _QUARTER or moment.second or moment.microsecond
            ):
                raise ScheduleValidationError("time_step")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ScheduleValidationError("end_before_start")
        if self.enabled and self.start is None and self.end is None:
            raise ScheduleValidationError("no_time")
        if not self.weekdays or not self.weekdays <= set(WEEKDAYS):
            raise ScheduleValidationError("no_weekday")
        if not 5 <= self.temperature <= MANUAL_SETPOINT:
            raise ScheduleValidationError("temperature_range")
        if not 1 <= self.power <= 5:
            raise ScheduleValidationError("power_range")

    def to_fields(self, slot: int) -> dict[str, int | str]:
        """Return the form fields of this program for a slot, 1 to 6."""
        prefix = f"p0{slot}"
        days = sum(
            1 << bit for bit, day in enumerate(WEEKDAYS) if day in self.weekdays
        )
        return {
            f"{prefix}1": int(self.enabled),
            f"{prefix}2": _encode_time(self.start),
            f"{prefix}3": _encode_time(self.end),
            f"{prefix}4": self.temperature,
            f"{prefix}5": self.power,
            f"{prefix}6": days,
            f"{prefix}7": self.name,
        }


@dataclass(frozen=True, slots=True)
class Schedule:
    """The whole schedule table and its global switch."""

    enabled: bool
    programs: tuple[ScheduleProgram | None, ...]

    @classmethod
    def from_payload(cls, payload: Any) -> Schedule:
        """Decode the answer to a schedule read."""
        if not isinstance(payload, dict):
            raise InvalidPayloadError("the schedule answer is not an object")
        rows = payload.get("programs")
        if not isinstance(rows, list) or len(rows) != SLOT_COUNT:
            raise InvalidPayloadError("the schedule does not hold six programs")
        return cls(
            enabled=bool(payload.get("enabled")),
            programs=tuple(ScheduleProgram.from_raw(row) for row in rows),
        )

    def to_fields(self) -> dict[str, int | str]:
        """Return the form fields that write the whole table."""
        fields: dict[str, int | str] = {"enabled": int(self.enabled)}
        for slot, program in enumerate(self.programs, start=1):
            if program is not None:
                fields.update(program.to_fields(slot))
        return fields

    def with_enabled(self, enabled: bool) -> Schedule:
        """Return a copy with the global switch changed."""
        return replace(self, enabled=enabled)

    def with_program(self, slot: int, program: ScheduleProgram | None) -> Schedule:
        """Return a copy with one slot, 1 to 6, replaced or freed."""
        if not 1 <= slot <= SLOT_COUNT:
            raise ScheduleValidationError("slot_range")
        programs = list(self.programs)
        programs[slot - 1] = program
        return replace(self, programs=tuple(programs))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_schedule.py tests/test_models.py -v`
Expected: all tests pass.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: `All checks passed!`.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add schedule model"
git checkout main
git merge --ff-only feature/schedule-model
git branch -d feature/schedule-model
```

---

### Task 4: HTTP client and module simulator

**Branch:** `feature/http-client`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/api.py`
- Create: `tests/fixtures/air_rds.json`
- Create: `tests/fake_module.py`
- Create: `tests/helpers.py`
- Modify: `tests/conftest.py` (replace the whole file)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces in `api.py`:
  - `WinetError(Exception)`, `WinetConnectionError(WinetError)`, `WinetResponseError(WinetError)`.
  - `normalize_host(value: str) -> str`.
  - `is_winet_status(payload: Mapping[str, Any]) -> bool`.
  - `WinetClient(session: aiohttp.ClientSession, host: str, *, timeout: float = 10.0)` with the attribute `host` and the coroutines `get_status() -> dict[str, Any]`, `get_info() -> dict[str, Any]`, `get_registers(category: int) -> dict[str, Any]`, `set_register(register: int, value: int) -> None`, `set_power(on: bool) -> None`, `get_schedule() -> dict[str, Any]`, `set_schedule(fields: Mapping[str, int | str]) -> None`, `delete_program(index: int) -> None` (index 0 to 5).
- Produces in `tests/fake_module.py`: `HOST = "192.0.2.10"`, `MAC = "aa:bb:cc:dd:ee:ff"`, `FREE_PROGRAM`, and `FakeModule(host: str = HOST, model: int = 7)` with `install(mocker)`, `count(path: str | None = None, **fields: str) -> int` and the public attributes `system`, `common`, `categories`, `extra`, `schedule_enabled`, `programs`, `requests`, `error`, `http_status`, `raw_answers`, `write_result`, `ignore_schedule_writes`, `delay`, `max_concurrent`.
- Produces in `tests/conftest.py`: the fixtures `fake_module`, `mock_mac`, `config_entry`, `init_integration`, `enable_all_entities`.
- Produces in `tests/helpers.py`: `entity_id_for(hass, platform: str, key: str) -> str` and `advance(hass, freezer, seconds: int = 31) -> None`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/http-client
```

- [ ] **Step 2: Write the capture fixture**

This is a capture of a real AIR-RDS module (firmware 0.51) with the network name, the IP addresses and the program name replaced.

`tests/fixtures/air_rds.json`:

```json
{
  "system": {
    "status": 5,
    "fwUpdate": false,
    "apConnected": 0,
    "lastDisconnectReason": 0,
    "lastCloudError": 0,
    "currentApIp": "192.0.2.1",
    "currentIp": "192.0.2.10",
    "currentMask": "255.255.255.0",
    "currentGw": "192.0.2.254",
    "inetTime": "2026-09-29 19:15",
    "inetWeekDay": 2,
    "client": 2,
    "network": "example-network",
    "signal": 3,
    "rssi": -74,
    "useTSense": 0,
    "board": [7, 0, 0, 0],
    "eNowDevs": [],
    "show": 0,
    "pairing": 0,
    "timeout": 0,
    "fwVer": "0.51",
    "boot": 2
  },
  "common": { "2": 0, "3": 0, "37": 0 },
  "categories": {
    "0": { "300": 1, "301": 160 },
    "2": { "0": 44, "4": 0, "5": 0, "50": 22, "51": 1 },
    "4": { "59": 2, "60": 24, "61": 87, "62": 41, "63": 9, "64": 38 },
    "6": { "24": 0, "25": 0, "184": 5, "185": 5 },
    "11": { "73": 0, "74": 1 }
  },
  "extra": {
    "localWeb": 1,
    "authLevel": 0,
    "signal": 3,
    "flame": 255,
    "chrono": 0,
    "alr": "",
    "name": "NO NAME",
    "inetTime": [2026, 9, 29, 2, 18, 52],
    "netatmo": [false, false, "", 0, 0],
    "tsense": { "show": 0, "list": [] }
  },
  "schedule": {
    "enabled": true,
    "programs": [
      [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"],
      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""],
      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""],
      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""],
      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""],
      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""]
    ]
  }
}
```

- [ ] **Step 3: Write the module simulator**

The simulator answers at the HTTP level, so the same object serves the client tests and every later test. It decodes the schedule fields on its own, without using `models.py`, so that an encoding mistake in `models.py` cannot hide behind the same mistake in the simulator.

`tests/fake_module.py`:

```python
"""HTTP-level simulator of the Smart Wi-Fi module."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

HOST = "192.0.2.10"
MAC = "aa:bb:cc:dd:ee:ff"
PATH_STATUS = "/ajax/get-status"
PATH_GET = "/ajax/get-registers"
PATH_SET = "/ajax/set-register"
FREE_PROGRAM: list[Any] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""]
_CAPTURE = Path(__file__).parent / "fixtures" / "air_rds.json"


def _int_keys(mapping: dict[str, int]) -> dict[int, int]:
    """JSON object keys are strings; registers are numbers."""
    return {int(key): value for key, value in mapping.items()}


class FakeModule:
    """Answers like the module and remembers what it was asked."""

    def __init__(self, host: str = HOST, model: int = 7) -> None:
        """Start from the capture of an idle AIR-RDS stove."""
        capture = json.loads(_CAPTURE.read_text())
        self.host = host
        self.model = model
        self.system: dict[str, Any] = capture["system"]
        self.system["board"] = [model, 0, 0, 0]
        self.system["currentIp"] = host
        self.common = _int_keys(capture["common"])
        self.categories = {
            int(category): _int_keys(registers)
            for category, registers in capture["categories"].items()
        }
        if model != 7:
            del self.categories[6]
        if model == 11:
            self.categories[2].update({1: 45, 49: 60})
        self.extra: dict[str, Any] = capture["extra"]
        self.schedule_enabled: bool = capture["schedule"]["enabled"]
        self.programs: list[list[Any]] = capture["schedule"]["programs"]
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.error: BaseException | None = None
        self.http_status = 200
        self.raw_answers: dict[str, str] = {}
        self.write_result = True
        self.ignore_schedule_writes = False
        self.delay = 0.0
        self.max_concurrent = 0
        self._active = 0

    def install(self, mocker: AiohttpClientMocker) -> None:
        """Answer every request sent to this host."""
        for path in (PATH_STATUS, PATH_GET, PATH_SET):
            mocker.post(f"http://{self.host}{path}", side_effect=self._handle)

    def count(self, path: str | None = None, **fields: str) -> int:
        """Count the requests sent to a path and carrying these fields."""
        return sum(
            1
            for seen_path, seen_fields in self.requests
            if (path is None or seen_path == path)
            and fields.items() <= seen_fields.items()
        )

    async def _handle(
        self, method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        fields = dict(parse_qsl(data or "", keep_blank_values=True))
        self.requests.append((url.path, fields))
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error is not None:
                raise self.error
            if url.path in self.raw_answers:
                return AiohttpClientMockResponse(
                    method,
                    url,
                    status=self.http_status,
                    text=self.raw_answers[url.path],
                )
            return AiohttpClientMockResponse(
                method,
                url,
                status=self.http_status,
                json=self._answer(url.path, fields),
            )
        finally:
            self._active -= 1

    def _answer(self, path: str, fields: dict[str, str]) -> dict[str, Any]:
        if path == PATH_STATUS:
            return deepcopy(self.system)
        if path == PATH_SET:
            return self._set_register(fields)
        key = fields.get("key")
        if key == "019":
            return {"fwUpdate": False, "localWeb": 1, "model": self.model}
        if key == "020":
            return self._category(int(fields["category"]))
        if key == "022":
            if not self.write_result:
                return {"result": False}
            self.common[2] = 2 if fields["status"] == "1" else 0
            return {"result": True}
        if key == "033":
            return {
                "key": 33,
                "enabled": self.schedule_enabled,
                "programs": deepcopy(self.programs),
            }
        if key == "032":
            if not self.write_result:
                return {"result": False}
            if not self.ignore_schedule_writes:
                self._store_schedule(fields)
            return {"result": True}
        if key == "034":
            if not self.write_result:
                return {"result": False}
            if not self.ignore_schedule_writes:
                self.programs[int(fields["index"])] = list(FREE_PROGRAM)
            return {"result": True}
        return {"result": False}

    def _set_register(self, fields: dict[str, str]) -> dict[str, Any]:
        if fields.get("key") != "002" or not self.write_result:
            return {"result": False}
        register = int(fields["regId"])
        for registers in self.categories.values():
            if register in registers:
                registers[register] = int(fields["value"])
        return {"result": True}

    def _category(self, category: int) -> dict[str, Any]:
        registers = {**self.common, **self.categories.get(category, {})}
        return {
            "params": [[key, registers[key]] for key in sorted(registers)],
            "cat": category,
            "model": self.model,
            **deepcopy(self.extra),
        }

    def _store_schedule(self, fields: dict[str, str]) -> None:
        self.schedule_enabled = fields.get("enabled") == "1"
        programs: list[list[Any]] = []
        for slot in range(1, 7):
            prefix = f"p0{slot}"
            if f"{prefix}1" not in fields:
                programs.append(list(FREE_PROGRAM))
                continue
            start = int(fields[f"{prefix}2"])
            stop = int(fields[f"{prefix}3"])
            programs.append(
                [
                    int(fields[f"{prefix}1"]),
                    start >> 7,
                    start >> 2 & 0x1F,
                    start & 0x03,
                    stop >> 7,
                    stop >> 2 & 0x1F,
                    stop & 0x03,
                    int(fields[f"{prefix}4"]),
                    int(fields[f"{prefix}5"]),
                    int(fields[f"{prefix}6"]),
                    fields[f"{prefix}7"],
                ]
            )
        self.programs = programs
```

- [ ] **Step 4: Write the shared fixtures and helpers**

Replace `tests/conftest.py` with:

```python
"""Shared fixtures."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant

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
```

`tests/helpers.py`:

```python
"""Helpers shared by the tests."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC


def entity_id_for(hass: HomeAssistant, platform: str, key: str) -> str:
    """Find an entity by its key, whatever its translated name is."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{MAC}_{key}"
    )
    assert entity_id is not None, f"no {platform} entity for {key}"
    return entity_id


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int = 31
) -> None:
    """Move the clock forward and let the due timers run."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
```

- [ ] **Step 5: Write the failing tests**

`tests/test_api.py`:

```python
"""Tests for the HTTP client."""

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.ravelli_smart_wifi.api import (
    WinetClient,
    WinetConnectionError,
    WinetResponseError,
    is_winet_status,
    normalize_host,
)

from .fake_module import HOST, PATH_GET, PATH_SET, PATH_STATUS, FakeModule


@pytest.fixture
def client(hass: HomeAssistant, fake_module: FakeModule) -> WinetClient:
    """Return a client that talks to the simulated module."""
    return WinetClient(async_get_clientsession(hass), HOST)


async def test_body_is_form_encoded_under_a_json_header(
    client: WinetClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The module refuses a JSON body although it asks for the JSON header."""
    await client.get_registers(2)

    method, url, data, headers = aioclient_mock.mock_calls[-1]
    assert method.lower() == "post"
    assert str(url) == f"http://{HOST}{PATH_GET}"
    assert data == "key=020&category=2"
    assert headers["Content-Type"] == "application/json; charset=utf-8"


async def test_status_has_no_body(
    client: WinetClient, aioclient_mock: AiohttpClientMocker
) -> None:
    """The system status is a bare POST."""
    status = await client.get_status()

    assert status["fwVer"] == "0.51"
    assert status["rssi"] == -74
    assert aioclient_mock.mock_calls[-1][2] is None
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_STATUS}"


async def test_reads(client: WinetClient, fake_module: FakeModule) -> None:
    """Every read returns the decoded JSON object."""
    assert (await client.get_info())["model"] == 7
    assert [50, 22] in (await client.get_registers(2))["params"]
    assert (await client.get_schedule())["programs"][0][10] == "Evening"
    assert fake_module.count(PATH_GET, key="019") == 1
    assert fake_module.count(PATH_GET, key="033") == 1


async def test_set_register(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A register write carries the five fields the vendor UI sends."""
    await client.set_register(50, 23)

    assert aioclient_mock.mock_calls[-1][2] == (
        "key=002&memory=1&regId=50&value=23&result=false"
    )
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_SET}"
    assert fake_module.categories[2][50] == 23


async def test_refused_register_write(
    client: WinetClient, fake_module: FakeModule
) -> None:
    """The module answers result false when it refuses."""
    fake_module.write_result = False

    with pytest.raises(WinetResponseError):
        await client.set_register(50, 23)


async def test_register_write_needs_a_positive_answer(
    client: WinetClient, fake_module: FakeModule
) -> None:
    """An answer without a result is not a confirmation."""
    fake_module.raw_answers[PATH_SET] = "{}"

    with pytest.raises(WinetResponseError):
        await client.set_register(50, 23)


@pytest.mark.parametrize(("on", "body"), [(True, "key=022&status=1"), (False, "key=022&status=0")])
async def test_set_power(
    client: WinetClient,
    aioclient_mock: AiohttpClientMocker,
    on: bool,
    body: str,
) -> None:
    """On and off go through the read endpoint with key 022."""
    await client.set_power(on)

    assert aioclient_mock.mock_calls[-1][2] == body
    assert str(aioclient_mock.mock_calls[-1][1]) == f"http://{HOST}{PATH_GET}"


async def test_schedule_write_encodes_separators_in_names(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An ampersand in a name must not split the body."""
    await client.set_schedule(
        {
            "enabled": 1,
            "p011": 1,
            "p012": 200,
            "p013": 218,
            "p014": 22,
            "p015": 1,
            "p016": 127,
            "p017": "A & B = C",
        }
    )

    assert aioclient_mock.mock_calls[-1][2] == (
        "enabled=1&p011=1&p012=200&p013=218&p014=22&p015=1&p016=127"
        "&p017=A+%26+B+%3D+C&key=032"
    )
    assert fake_module.programs[0] == [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "A & B = C"]
    assert fake_module.programs[1][10] == ""


async def test_delete_program(
    client: WinetClient,
    fake_module: FakeModule,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Programs are deleted by index, starting at 0."""
    await client.delete_program(0)

    assert aioclient_mock.mock_calls[-1][2] == "key=034&index=0"
    assert fake_module.programs[0][10] == ""


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError(), TimeoutError(), aiohttp.ClientOSError()]
)
async def test_unreachable_module(
    client: WinetClient, fake_module: FakeModule, error: BaseException
) -> None:
    """Network failures become one error type."""
    fake_module.error = error

    with pytest.raises(WinetConnectionError):
        await client.get_registers(2)


async def test_http_error(client: WinetClient, fake_module: FakeModule) -> None:
    """An HTTP error means the answer cannot be trusted."""
    fake_module.http_status = 500

    with pytest.raises(WinetResponseError):
        await client.get_registers(2)


@pytest.mark.parametrize(
    "answer", ["<html><body>Login</body></html>", "", "[]", '"text"', '{"result": false}']
)
async def test_unexpected_answers(
    client: WinetClient, fake_module: FakeModule, answer: str
) -> None:
    """Another device at the same address must not crash the client."""
    fake_module.raw_answers[PATH_GET] = answer

    with pytest.raises(WinetResponseError):
        await client.get_registers(2)


@pytest.mark.parametrize(
    ("typed", "host"),
    [
        ("192.0.2.10", "192.0.2.10"),
        ("  192.0.2.10  ", "192.0.2.10"),
        ("http://192.0.2.10", "192.0.2.10"),
        ("http://192.0.2.10/", "192.0.2.10"),
        ("HTTP://192.0.2.10/management.html", "192.0.2.10"),
        ("https://stove.example/", "stove.example"),
        ("stove.example", "stove.example"),
        ("", ""),
        ("http://", ""),
    ],
)
def test_normalize_host(typed: str, host: str) -> None:
    """People paste what their browser shows."""
    assert normalize_host(typed) == host


def test_status_signature() -> None:
    """A module is recognized by two fields of its system status."""
    assert is_winet_status({"fwVer": "0.51", "board": [7, 0, 0, 0]}) is True
    assert is_winet_status({"fwVer": "0.51"}) is False
    assert is_winet_status({"board": [7, 0, 0, 0]}) is False
    assert is_winet_status({}) is False
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'custom_components.ravelli_smart_wifi.api'`.

- [ ] **Step 7: Write the implementation**

`custom_components/ravelli_smart_wifi/api.py`:

```python
"""HTTP client of the Smart Wi-Fi module.

This module imports nothing from Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any
from urllib.parse import urlencode

import aiohttp

PATH_STATUS = "/ajax/get-status"
PATH_GET = "/ajax/get-registers"
PATH_SET = "/ajax/set-register"

# The module wants this header and a form-urlencoded body.
_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


class WinetError(Exception):
    """Base class of the client errors."""


class WinetConnectionError(WinetError):
    """The module cannot be reached."""


class WinetResponseError(WinetError):
    """The module answered, but not with what was expected."""


def normalize_host(value: str) -> str:
    """Strip the scheme, the path and the spaces of a typed address."""
    host = value.strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.split("/", 1)[0].strip()


def is_winet_status(payload: Mapping[str, Any]) -> bool:
    """Tell whether a system status comes from a Smart Wi-Fi module."""
    return "fwVer" in payload and "board" in payload


class WinetClient:
    """Talks to one module."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, *, timeout: float = 10.0
    ) -> None:
        """Remember the session and the address."""
        self.host = host
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _post(
        self, path: str, fields: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        body = urlencode(fields) if fields else None
        try:
            async with self._session.post(
                f"http://{self.host}{path}",
                data=body,
                headers=_HEADERS,
                timeout=self._timeout,
            ) as response:
                status = response.status
                raw = await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WinetConnectionError(f"no answer from {path}") from err
        if status != 200:
            raise WinetResponseError(f"HTTP {status} from {path}")
        try:
            payload = json.loads(raw)
        except ValueError as err:
            raise WinetResponseError(f"the answer from {path} is not JSON") from err
        if not isinstance(payload, dict):
            raise WinetResponseError(f"the answer from {path} is not an object")
        if payload.get("result") is False:
            raise WinetResponseError(f"the module refused the request to {path}")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Read the system status: firmware, signal, network."""
        return await self._post(PATH_STATUS)

    async def get_info(self) -> dict[str, Any]:
        """Read the board model."""
        return await self._post(PATH_GET, {"key": "019"})

    async def get_registers(self, category: int) -> dict[str, Any]:
        """Read one register category."""
        return await self._post(PATH_GET, {"key": "020", "category": category})

    async def set_register(self, register: int, value: int) -> None:
        """Write one register."""
        payload = await self._post(
            PATH_SET,
            {
                "key": "002",
                "memory": 1,
                "regId": register,
                "value": value,
                "result": "false",
            },
        )
        if payload.get("result") is not True:
            raise WinetResponseError("the module did not confirm the write")

    async def set_power(self, on: bool) -> None:
        """Turn the stove on or off."""
        await self._post(PATH_GET, {"key": "022", "status": int(on)})

    async def get_schedule(self) -> dict[str, Any]:
        """Read the six programs and the global switch."""
        return await self._post(PATH_GET, {"key": "033"})

    async def set_schedule(self, fields: Mapping[str, int | str]) -> None:
        """Write the whole schedule table."""
        await self._post(PATH_GET, {**fields, "key": "032"})

    async def delete_program(self, index: int) -> None:
        """Free one program slot, 0 to 5."""
        await self._post(PATH_GET, {"key": "034", "index": index})
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api.py -v`
Expected: all tests pass.

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: every test passes and `All checks passed!`. Run `uv run ruff format .` if only the layout of the long parametrize lists differs.

- [ ] **Step 9: Check that the fixture holds no personal data**

Run: `grep -rnE '192\.168\.|10\.[0-9]+\.[0-9]+\.|172\.(1[6-9]|2[0-9]|3[01])\.' tests custom_components ; echo "exit $?"`
Expected: no line is printed and the last line is `exit 1`.

- [ ] **Step 10: Commit and integrate**

```bash
git add -A
git commit -m "feat: add HTTP client and module simulator"
git checkout main
git merge --ff-only feature/http-client
git branch -d feature/http-client
```

---

### Task 5: Coordinator

**Branch:** `feature/coordinator`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/coordinator.py`
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `WinetClient`, `WinetError`, `WinetConnectionError`, `WinetResponseError` from `api.py`; `StoveModel`, `StoveState`, `Schedule`, `ScheduleProgram`, `ScheduleValidationError`, `InvalidPayloadError`, `RegisterNotWritableError`, `ValueOutOfRangeError`, `validate_write`, `encode_clock`, `CATEGORY_MAIN`, `SLOT_COUNT` from `models.py`; `DOMAIN`, `DEFAULT_SCAN_INTERVAL`, `SLOW_REFRESH_INTERVAL`, `FAST_REFRESH_STEPS`, `DIAGNOSTIC_CATEGORIES` from `const.py`; the fixtures of Task 4.
- Produces in `coordinator.py`:
  - `RavelliData(state: StoveState, system: dict[str, Any], schedule: Schedule)`.
  - `type RavelliConfigEntry = ConfigEntry[RavelliCoordinator]`.
  - `RavelliCoordinator(hass, entry: RavelliConfigEntry, client: WinetClient, model: StoveModel)` with the attributes `client` and `model` and the coroutines:
    - `async_write_register(register: int, value: int) -> None`
    - `async_set_power(on: bool) -> None`
    - `async_set_schedule_enabled(enabled: bool) -> None`
    - `async_set_program(slot: int, program: ScheduleProgram) -> None`
    - `async_delete_program(slot: int) -> None`
    - `async_sync_clock() -> None`
    - `async_read_diagnostics() -> dict[str, Any]` returning `{"system": ..., "categories": {"0": ..., ...}, "schedule": ...}`
  - Error contract: invalid input raises `ServiceValidationError`; a module that does not answer or refuses raises `HomeAssistantError`. Both carry `translation_domain=DOMAIN` and one of these `translation_key` values: `value_out_of_range`, `register_not_writable`, `turn_on_in_alarm`, `turn_off_during_ignition`, `schedule_<key>` (one per `ScheduleValidationError` key), `cannot_connect`, `command_refused`, `schedule_mismatch`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/coordinator
```

- [ ] **Step 2: Write the failing tests**

`tests/test_coordinator.py`:

```python
"""Tests for the coordinator."""

import asyncio
from dataclasses import replace
from datetime import time, timedelta

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.ravelli_smart_wifi.api import WinetClient
from custom_components.ravelli_smart_wifi.const import DOMAIN
from custom_components.ravelli_smart_wifi.coordinator import RavelliCoordinator
from custom_components.ravelli_smart_wifi.models import (
    SUPPORTED_MODELS,
    ScheduleProgram,
)

from .fake_module import HOST, PATH_GET, PATH_SET, PATH_STATUS, FakeModule

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
MORNING = ScheduleProgram(
    name="Morning",
    enabled=True,
    start=time(6, 30),
    end=time(8, 0),
    temperature=21,
    power=3,
    weekdays=frozenset({"mon", "tue", "wed", "thu", "fri"}),
)
MORNING_RAW = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]


def build(
    hass: HomeAssistant, entry: MockConfigEntry, model: int = 7
) -> RavelliCoordinator:
    """Build a coordinator without setting the integration up."""
    client = WinetClient(async_get_clientsession(hass), HOST)
    return RavelliCoordinator(hass, entry, client, SUPPORTED_MODELS[model])


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> RavelliCoordinator:
    """Return a coordinator that has polled the module once."""
    coordinator = build(hass, config_entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    fake_module.requests.clear()
    return coordinator


def categories_read(fake_module: FakeModule) -> list[str]:
    """List the categories read, in order."""
    return [
        fields["category"]
        for _, fields in fake_module.requests
        if fields.get("key") == "020"
    ]


async def test_first_refresh_reads_everything(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The first poll reads the registers, the system status and the schedule."""
    coordinator = build(hass, config_entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.state.setpoint == 22
    assert coordinator.data.state.raw(184) == 5
    assert coordinator.data.state.raw(74) == 1
    assert coordinator.data.system["fwVer"] == "0.51"
    assert coordinator.data.schedule.programs[0].name == "Evening"
    assert categories_read(fake_module) == ["2", "6", "11"]
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_models_without_ducting_skip_its_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """HYDRO-RDS and ECO-RDS read two categories."""
    module = FakeModule(model=12)
    module.install(aioclient_mock)
    coordinator = build(hass, config_entry, model=12)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert categories_read(module) == ["2", "11"]


async def test_polling_interval_comes_from_the_options(
    hass: HomeAssistant, fake_module: FakeModule
) -> None:
    """The options flow stores the interval in seconds."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": HOST}, options={"scan_interval": 60}
    )
    entry.add_to_hass(hass)

    assert build(hass, entry).update_interval == timedelta(seconds=60)


async def test_slow_data_is_read_every_ten_minutes(
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """System status and schedule are not part of every poll."""
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert fake_module.count(PATH_STATUS) == 0
    assert fake_module.count(PATH_GET, key="033") == 0

    freezer.tick(timedelta(seconds=601))
    await coordinator.async_refresh()

    assert fake_module.count(PATH_STATUS) == 1
    assert fake_module.count(PATH_GET, key="033") == 1


async def test_unreachable_module_fails_the_update(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Entities follow last_update_success."""
    fake_module.error = aiohttp.ClientConnectionError()
    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    fake_module.error = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success


@pytest.mark.parametrize("answer", ["<html>busy</html>", '{"params": [[0, 44]]}'])
async def test_unexpected_answer_fails_the_update(
    coordinator: RavelliCoordinator, fake_module: FakeModule, answer: str
) -> None:
    """HTML, or registers without a status, must not raise out of the poll."""
    fake_module.raw_answers[PATH_GET] = answer

    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_write_register(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A write is followed by a read, so the new value shows at once."""
    await coordinator.async_write_register(50, 23)

    assert fake_module.requests[0] == (
        PATH_SET,
        {"key": "002", "memory": "1", "regId": "50", "value": "23", "result": "false"},
    )
    assert categories_read(fake_module) == ["2", "6", "11"]
    assert coordinator.data.state.setpoint == 23


async def test_out_of_range_write_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The bounds are checked before the module is contacted."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_write_register(50, 42)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "value_out_of_range"
    assert err.value.translation_placeholders == {
        "value": "42",
        "minimum": "5",
        "maximum": "41",
    }
    assert fake_module.requests == []


async def test_register_outside_the_table_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Register 49 belongs to the hydro model."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_write_register(49, 60)

    assert err.value.translation_key == "register_not_writable"
    assert err.value.translation_placeholders == {"register": "49"}
    assert fake_module.requests == []


async def test_refused_write(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A refusal is reported and the write is not repeated."""
    fake_module.write_result = False

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)

    assert err.value.translation_key == "command_refused"
    assert fake_module.count(PATH_SET) == 1


async def test_write_to_an_unreachable_module(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A network failure is reported and the write is not repeated."""
    fake_module.error = aiohttp.ClientConnectionError()

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)

    assert err.value.translation_key == "cannot_connect"
    assert fake_module.count(PATH_SET) == 1


async def test_polls_faster_after_a_command(
    hass: HomeAssistant,
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Five close polls follow a command, then the normal pace returns."""
    remove_listener = coordinator.async_add_listener(lambda: None)

    await coordinator.async_write_register(51, 2)
    assert coordinator.update_interval == timedelta(seconds=2)

    for expected in (3, 5, 10, 10, 30):
        polls = fake_module.count(PATH_GET, key="020", category="2")
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert fake_module.count(PATH_GET, key="020", category="2") == polls + 1
        assert coordinator.update_interval == timedelta(seconds=expected)

    remove_listener()


async def test_requests_never_overlap(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The module handles one request at a time."""
    fake_module.delay = 0.01

    await asyncio.gather(
        coordinator.async_write_register(51, 2),
        coordinator.async_write_register(50, 21),
        coordinator.async_refresh(),
    )

    assert fake_module.max_concurrent == 1
    assert fake_module.categories[2][51] == 2
    assert fake_module.categories[2][50] == 21


async def test_turn_on(coordinator: RavelliCoordinator, fake_module: FakeModule) -> None:
    """The command is sent and the new status is read back."""
    await coordinator.async_set_power(True)

    assert fake_module.count(PATH_GET, key="022", status="1") == 1
    assert coordinator.data.state.status_key == "ignition"


async def test_turn_on_when_already_on_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """An on command never reaches a running stove."""
    fake_module.common[2] = 5

    await coordinator.async_set_power(True)

    assert fake_module.count(PATH_GET, key="022") == 0
    assert coordinator.data.state.status_key == "working"


async def test_turn_on_is_refused_in_alarm_raised_since_the_last_poll(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The rule uses the state read at command time, not the polled one."""
    assert coordinator.data.state.status_key == "off"
    fake_module.common[2] = 8

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_power(True)

    assert err.value.translation_key == "turn_on_in_alarm"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_turn_off(coordinator: RavelliCoordinator, fake_module: FakeModule) -> None:
    """A working stove can be turned off."""
    fake_module.common[2] = 5

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1
    assert coordinator.data.state.status_key == "off"


async def test_turn_off_when_already_off_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """An off command never reaches an idle stove."""
    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022") == 0


@pytest.mark.parametrize("status", [1, 2, 3, 4])
async def test_turn_off_is_refused_while_igniting_without_flame(
    coordinator: RavelliCoordinator, fake_module: FakeModule, status: int
) -> None:
    """The vendor UI refuses this too."""
    fake_module.common[2] = status
    fake_module.extra["flame"] = 0

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_power(False)

    assert err.value.translation_key == "turn_off_during_ignition"
    assert fake_module.count(PATH_GET, key="022") == 0


@pytest.mark.parametrize("flame", [255, 1])
async def test_turn_off_while_igniting_is_allowed_otherwise(
    coordinator: RavelliCoordinator, fake_module: FakeModule, flame: int
) -> None:
    """Allowed when the flame is there, or when the board does not report it."""
    fake_module.common[2] = 2
    fake_module.extra["flame"] = flame

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1


@pytest.mark.parametrize("status", [8, 9])
async def test_turn_off_in_alarm_acknowledges_it(
    coordinator: RavelliCoordinator, fake_module: FakeModule, status: int
) -> None:
    """Like the power button of the stove."""
    fake_module.common[2] = status

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1


async def test_set_program_keeps_the_other_slots(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The table is read, changed, written and read back."""
    await coordinator.async_set_program(2, MORNING)

    assert fake_module.programs[0] == EVENING_RAW
    assert fake_module.programs[1] == MORNING_RAW
    assert fake_module.count(PATH_GET, key="033") == 2
    assert fake_module.count(PATH_GET, key="032") == 1
    assert coordinator.data.schedule.programs[1] == MORNING


async def test_set_program_uses_the_table_of_the_module(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A program added from the vendor UI since the last poll is kept."""
    fake_module.programs[4] = [1, 1, 7, 0, 0, 0, 0, 20, 2, 64, "Sunday"]

    await coordinator.async_set_program(2, MORNING)

    assert fake_module.programs[4] == [1, 1, 7, 0, 0, 0, 0, 20, 2, 64, "Sunday"]
    assert fake_module.programs[1] == MORNING_RAW


async def test_schedule_is_checked_after_the_write(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A write the module ignored is reported."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_program(2, MORNING)

    assert err.value.translation_key == "schedule_mismatch"
    assert fake_module.count(PATH_GET, key="032") == 1


async def test_invalid_program_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The rules of the vendor UI apply before anything is sent."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_program(2, replace(MORNING, end=time(6, 0)))

    assert err.value.translation_key == "schedule_end_before_start"
    assert fake_module.requests == []


@pytest.mark.parametrize("slot", [0, 7])
async def test_slot_must_exist(
    coordinator: RavelliCoordinator, fake_module: FakeModule, slot: int
) -> None:
    """Slots are numbered 1 to 6, for writing and for deleting."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_program(slot, MORNING)
    assert err.value.translation_key == "schedule_slot_range"

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_delete_program(slot)
    assert err.value.translation_key == "schedule_slot_range"

    assert fake_module.requests == []


async def test_delete_program(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Slot 1 is index 0 for the module."""
    await coordinator.async_delete_program(1)

    assert fake_module.count(PATH_GET, key="034", index="0") == 1
    assert fake_module.programs[0][10] == ""
    assert coordinator.data.schedule.programs[0] is None


async def test_delete_a_free_slot_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """There is nothing to delete."""
    await coordinator.async_delete_program(3)

    assert fake_module.count(PATH_GET, key="034") == 0


async def test_schedule_switch_keeps_the_programs(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The global flag travels with the whole table."""
    await coordinator.async_set_schedule_enabled(False)

    assert fake_module.schedule_enabled is False
    assert fake_module.programs[0] == EVENING_RAW
    assert coordinator.data.schedule.enabled is False


@pytest.mark.freeze_time("2026-09-29T16:57:30+00:00")
async def test_clock_is_set_to_local_time(
    hass: HomeAssistant, coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """16:57 UTC is 18:57 in Paris; the stove shows local time."""
    await hass.config.async_set_time_zone("Europe/Paris")
    fake_module.categories[4] = dict.fromkeys(range(59, 65), 0)

    await coordinator.async_sync_clock()

    assert fake_module.categories[4] == {
        59: 2,
        60: 0x18,
        61: 0x57,
        62: 0x29,
        63: 0x09,
        64: 0x26,
    }
    assert fake_module.count(PATH_SET) == 6


async def test_diagnostics_read(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Every category from 0 to 12 is read, with the status and the schedule."""
    dump = await coordinator.async_read_diagnostics()

    assert sorted(dump) == ["categories", "schedule", "system"]
    assert list(dump["categories"]) == [str(number) for number in range(13)]
    assert [300, 1] in dump["categories"]["0"]["params"]
    assert [60, 24] in dump["categories"]["4"]["params"]
    assert dump["system"]["fwVer"] == "0.51"
    assert dump["schedule"]["programs"][0] == EVENING_RAW
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'custom_components.ravelli_smart_wifi.coordinator'`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/coordinator.py`:

```python
"""Polling, locking, safety rules and commands."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WinetClient, WinetConnectionError, WinetError, WinetResponseError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DIAGNOSTIC_CATEGORIES,
    DOMAIN,
    FAST_REFRESH_STEPS,
    SLOW_REFRESH_INTERVAL,
)
from .models import (
    CATEGORY_MAIN,
    SLOT_COUNT,
    InvalidPayloadError,
    RegisterNotWritableError,
    Schedule,
    ScheduleProgram,
    ScheduleValidationError,
    StoveModel,
    StoveState,
    ValueOutOfRangeError,
    encode_clock,
    validate_write,
)

_LOGGER = logging.getLogger(__name__)

type RavelliConfigEntry = ConfigEntry[RavelliCoordinator]


@dataclass(frozen=True, slots=True)
class RavelliData:
    """What one polling cycle knows about the stove."""

    state: StoveState
    system: dict[str, Any]
    schedule: Schedule


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    """Build the error raised for an input that breaks a rule."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _failed(key: str) -> HomeAssistantError:
    """Build the error raised when the module does not do what was asked."""
    return HomeAssistantError(translation_domain=DOMAIN, translation_key=key)


def _check_slot(slot: int) -> None:
    if not 1 <= slot <= SLOT_COUNT:
        raise _invalid("schedule_slot_range")


class RavelliCoordinator(DataUpdateCoordinator[RavelliData]):
    """Owns every exchange with one module."""

    config_entry: RavelliConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RavelliConfigEntry,
        client: WinetClient,
        model: StoveModel,
    ) -> None:
        """Set the polling interval from the options."""
        self._normal_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )
        self.client = client
        self.model = model
        # The module handles one request at a time.
        self._lock = asyncio.Lock()
        self._system: dict[str, Any] = {}
        self._schedule: Schedule | None = None
        self._slow_read_at: datetime | None = None
        self._fast_steps: list[int] = []

    async def _async_update_data(self) -> RavelliData:
        try:
            async with self._lock:
                payloads = [
                    await self.client.get_registers(category)
                    for category in self.model.categories
                ]
                now = dt_util.utcnow()
                if (
                    self._schedule is None
                    or self._slow_read_at is None
                    or (now - self._slow_read_at).total_seconds()
                    >= SLOW_REFRESH_INTERVAL
                ):
                    self._system = await self.client.get_status()
                    self._schedule = Schedule.from_payload(
                        await self.client.get_schedule()
                    )
                    self._slow_read_at = now
                schedule = self._schedule
            state = StoveState.from_payloads(payloads)
        except (WinetError, InvalidPayloadError) as err:
            raise UpdateFailed(str(err)) from err
        finally:
            self.update_interval = (
                timedelta(seconds=self._fast_steps.pop(0))
                if self._fast_steps
                else self._normal_interval
            )
        return RavelliData(state=state, system=self._system, schedule=schedule)

    async def _async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        """Run one command under the lock, then read the result back."""
        try:
            async with self._lock:
                await command()
        except WinetConnectionError as err:
            raise _failed("cannot_connect") from err
        except (WinetResponseError, InvalidPayloadError) as err:
            raise _failed("command_refused") from err
        self._fast_steps = list(FAST_REFRESH_STEPS)
        await self.async_refresh()

    async def async_write_register(self, register: int, value: int) -> None:
        """Write one register of the model table."""
        try:
            validate_write(self.model, register, value)
        except RegisterNotWritableError as err:
            raise _invalid("register_not_writable", register=str(register)) from err
        except ValueOutOfRangeError as err:
            raise _invalid(
                "value_out_of_range",
                value=str(value),
                minimum=str(err.minimum),
                maximum=str(err.maximum),
            ) from err
        await self._async_command(lambda: self.client.set_register(register, value))

    async def async_set_power(self, on: bool) -> None:
        """Turn the stove on or off, if its current state allows it."""

        async def command() -> None:
            # The polled state can be half a minute old: read it again.
            state = StoveState.from_payloads(
                [await self.client.get_registers(CATEGORY_MAIN)]
            )
            if on:
                if state.in_alarm:
                    raise _invalid("turn_on_in_alarm")
                if state.is_on:
                    return
            else:
                if state.is_igniting and state.flame == 0:
                    raise _invalid("turn_off_during_ignition")
                if state.status_code == 0:
                    return
            await self.client.set_power(on)

        await self._async_command(command)

    async def async_set_schedule_enabled(self, enabled: bool) -> None:
        """Change the global switch of the schedule."""
        await self._async_change_schedule(
            lambda schedule: schedule.with_enabled(enabled)
        )

    async def async_set_program(self, slot: int, program: ScheduleProgram) -> None:
        """Store one program in a slot, 1 to 6."""
        _check_slot(slot)
        try:
            program.validate()
        except ScheduleValidationError as err:
            raise _invalid(f"schedule_{err.key}") from err
        await self._async_change_schedule(
            lambda schedule: schedule.with_program(slot, program)
        )

    async def async_delete_program(self, slot: int) -> None:
        """Free one slot, 1 to 6."""
        _check_slot(slot)

        async def command() -> None:
            current = Schedule.from_payload(await self.client.get_schedule())
            if current.programs[slot - 1] is None:
                self._schedule = current
                return
            await self.client.delete_program(slot - 1)
            await self._async_verify_schedule(current.with_program(slot, None))

        await self._async_command(command)

    async def _async_change_schedule(
        self, change: Callable[[Schedule], Schedule]
    ) -> None:
        """Read the table, change it, write it and read it back."""

        async def command() -> None:
            current = Schedule.from_payload(await self.client.get_schedule())
            wanted = change(current)
            await self.client.set_schedule(wanted.to_fields())
            await self._async_verify_schedule(wanted)

        await self._async_command(command)

    async def _async_verify_schedule(self, wanted: Schedule) -> None:
        stored = Schedule.from_payload(await self.client.get_schedule())
        if stored != wanted:
            raise _failed("schedule_mismatch")
        self._schedule = stored

    async def async_sync_clock(self) -> None:
        """Set the stove clock to the local time of Home Assistant."""
        writes = encode_clock(dt_util.now())

        async def command() -> None:
            for register, value in writes:
                validate_write(self.model, register, value)
                await self.client.set_register(register, value)

        await self._async_command(command)

    async def async_read_diagnostics(self) -> dict[str, Any]:
        """Read every register category, the status and the schedule."""
        async with self._lock:
            categories = {
                str(category): await self.client.get_registers(category)
                for category in range(DIAGNOSTIC_CATEGORIES)
            }
            return {
                "system": await self.client.get_status(),
                "categories": categories,
                "schedule": await self.client.get_schedule(),
            }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_coordinator.py -v`
Expected: all tests pass.

If `test_polls_faster_after_a_command` fails on a poll count, print `coordinator.update_interval` after each tick: the expected sequence of intervals after the command is 2, 3, 5, 10, 10, 30 seconds, one poll per tick of 11 seconds.

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: every test passes and `All checks passed!`.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add coordinator with safety rules and schedule commands"
git checkout main
git merge --ff-only feature/coordinator
git branch -d feature/coordinator
```

---

### Task 6: Entry setup, user config flow and texts

**Branch:** `feature/config-flow`

**Files:**
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (replace the whole file)
- Create: `custom_components/ravelli_smart_wifi/config_flow.py`
- Create: `custom_components/ravelli_smart_wifi/translations/en.json`
- Create: `custom_components/ravelli_smart_wifi/translations/fr.json`
- Create: `custom_components/ravelli_smart_wifi/icons.json`
- Test: `tests/test_init.py`, `tests/test_config_flow.py`, `tests/test_translations.py`

**Interfaces:**
- Consumes: `WinetClient`, `WinetError`, `WinetConnectionError`, `WinetResponseError`, `is_winet_status`, `normalize_host` from `api.py`; `RavelliCoordinator`, `RavelliConfigEntry` from `coordinator.py`; `SUPPORTED_MODELS`, `StoveModel` from `models.py`; `DOMAIN`, `ISSUE_URL`, `SCAN_TIMEOUT`, `SCAN_CONCURRENCY`, `SCAN_MIN_PREFIX` from `const.py`; the fixtures of Task 4.
- Produces in `__init__.py`: `PLATFORMS: list[Platform]` (empty for now; each platform task appends to it), `async_setup_entry`, `async_unload_entry`. After setup, `entry.runtime_data` is the `RavelliCoordinator`.
- Produces in `config_flow.py`:
  - `CHOICE_MANUAL = "manual"`.
  - `ProbeResult(host: str, model: StoveModel, mac: str | None)`.
  - `ProbeError(Exception)` with `reason: str` (`cannot_connect`, `not_winet` or `unsupported_model`) and `model_code: object`.
  - `async_get_mac(hass, host: str) -> str | None`.
  - `async_probe(hass, host: str) -> ProbeResult`.
  - `async_local_networks(hass) -> list[IPv4Network]`.
  - `async_scan(hass) -> list[str]`.
  - `RavelliConfigFlow` with the steps `user` (menu), `scan`, `pick`, `manual`, and the helpers `_async_try(host, errors)`, `_async_create(probe)`, `_abort_unsupported(err)` that Task 7 reuses.
- Config entry data: `{CONF_HOST: str, CONF_MODEL: int, CONF_MAC: str | None}`. Unique id: the MAC address, or none. Title: `Ravelli <model name>`.
- The translation and icon files are complete from this task on: they already hold the texts of the entities, errors and actions that later tasks create. Later tasks do not edit them.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/config-flow
```

- [ ] **Step 2: Write the failing tests**

`tests/test_init.py`:

```python
"""Tests for the setup of a config entry."""

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
```

`tests/test_config_flow.py`:

```python
"""Tests for the config flow started by the user."""

from collections.abc import Generator
from ipaddress import IPv4Network
import re
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ravelli_smart_wifi.config_flow import (
    CHOICE_MANUAL,
    async_local_networks,
)
from custom_components.ravelli_smart_wifi.const import DOMAIN, ISSUE_URL

from .fake_module import HOST, MAC, PATH_STATUS, FakeModule

MAC_LOOKUP = "custom_components.ravelli_smart_wifi.config_flow.get_mac_address"
NETWORKS = "custom_components.ravelli_smart_wifi.config_flow.async_local_networks"
ADAPTERS = (
    "custom_components.ravelli_smart_wifi.config_flow.network.async_get_adapters"
)


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
```

`tests/test_translations.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_init.py tests/test_config_flow.py tests/test_translations.py -v`
Expected: collection errors, `ModuleNotFoundError: No module named 'custom_components.ravelli_smart_wifi.config_flow'` and `FileNotFoundError` for `translations/en.json`.

- [ ] **Step 4: Write the entry setup**

Replace `custom_components/ravelli_smart_wifi/__init__.py` with:

```python
"""Ravelli Smart Wi-Fi integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WinetClient, WinetError
from .const import DOMAIN, ISSUE_URL
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .models import SUPPORTED_MODELS

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: RavelliConfigEntry) -> bool:
    """Set one stove up."""
    client = WinetClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    try:
        info = await client.get_info()
    except WinetError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    code = info.get("model")
    model = SUPPORTED_MODELS.get(code) if isinstance(code, int) else None
    if model is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_model",
            translation_placeholders={"model": str(code), "issue_url": ISSUE_URL},
        )
    coordinator = RavelliCoordinator(hass, entry, client, model)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RavelliConfigEntry) -> bool:
    """Unload one stove."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 5: Write the config flow**

`custom_components/ravelli_smart_wifi/config_flow.py`:

```python
"""Config flow of the Ravelli Smart Wi-Fi integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from ipaddress import IPv4Network, ip_address
import logging
from typing import Any

from getmac import get_mac_address
import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    WinetClient,
    WinetConnectionError,
    WinetError,
    WinetResponseError,
    is_winet_status,
    normalize_host,
)
from .const import DOMAIN, ISSUE_URL, SCAN_CONCURRENCY, SCAN_MIN_PREFIX, SCAN_TIMEOUT
from .models import SUPPORTED_MODELS, StoveModel

_LOGGER = logging.getLogger(__name__)

CHOICE_MANUAL = "manual"
# What the lookup returns on some systems when it finds nothing.
_NO_MAC = "00:00:00:00:00:00"
_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """A supported module found at an address."""

    host: str
    model: StoveModel
    mac: str | None


class ProbeError(Exception):
    """The address cannot be used."""

    def __init__(self, reason: str, model_code: object = None) -> None:
        """Remember the reason, which is also the translation key."""
        super().__init__(reason)
        self.reason = reason
        self.model_code = model_code


async def async_get_mac(hass: HomeAssistant, host: str) -> str | None:
    """Look the MAC address of a host up; the module does not report it."""
    try:
        ip_address(host)
    except ValueError:
        lookup = partial(get_mac_address, hostname=host)
    else:
        lookup = partial(get_mac_address, ip=host)
    mac = await hass.async_add_executor_job(lookup)
    if not mac or mac == _NO_MAC:
        return None
    return format_mac(mac)


async def async_probe(hass: HomeAssistant, host: str) -> ProbeResult:
    """Check that a supported module answers at an address."""
    client = WinetClient(async_get_clientsession(hass), host)
    try:
        status = await client.get_status()
        if not is_winet_status(status):
            raise ProbeError("not_winet")
        info = await client.get_info()
    except WinetConnectionError as err:
        raise ProbeError("cannot_connect") from err
    except WinetResponseError as err:
        raise ProbeError("not_winet") from err
    code = info.get("model")
    model = SUPPORTED_MODELS.get(code) if isinstance(code, int) else None
    if model is None:
        raise ProbeError("unsupported_model", code)
    return ProbeResult(host=host, model=model, mac=await async_get_mac(hass, host))


async def async_local_networks(hass: HomeAssistant) -> list[IPv4Network]:
    """Return the local networks that are small enough to be searched."""
    networks: list[IPv4Network] = []
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for address in adapter["ipv4"]:
            if address["network_prefix"] < SCAN_MIN_PREFIX:
                continue
            found = IPv4Network(
                f"{address['address']}/{address['network_prefix']}", strict=False
            )
            if found.is_loopback or found.is_link_local or found in networks:
                continue
            networks.append(found)
    return networks


async def async_scan(hass: HomeAssistant) -> list[str]:
    """Return the addresses of the local networks where a module answers."""
    session = async_get_clientsession(hass)
    limit = asyncio.Semaphore(SCAN_CONCURRENCY)

    async def check(host: str) -> str | None:
        async with limit:
            try:
                status = await WinetClient(
                    session, host, timeout=SCAN_TIMEOUT
                ).get_status()
            except WinetError:
                return None
        return host if is_winet_status(status) else None

    hosts = [
        str(host)
        for found in await async_local_networks(hass)
        for host in found.hosts()
    ]
    return [host for host in await asyncio.gather(*map(check, hosts)) if host]


class RavelliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds a stove from the user interface."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing found."""
        self._scan_task: asyncio.Task[list[str]] | None = None
        self._found: list[str] = []
        self._scan_was_empty = False
        self._probe: ProbeResult | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the network search or the manual entry."""
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the local networks while showing a progress screen."""
        if self._scan_task is None:
            # Not eager: the first call must return the progress screen.
            self._scan_task = self.hass.async_create_task(
                async_scan(self.hass), eager_start=False
            )
        if not self._scan_task.done():
            return self.async_show_progress(
                step_id="scan", progress_action="scan", progress_task=self._scan_task
            )
        try:
            found = self._scan_task.result()
        except Exception:
            # A failed search must not block the manual entry.
            _LOGGER.exception("The network search failed")
            found = []
        self._scan_task = None
        configured = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        self._found = [host for host in found if host not in configured]
        if not self._found:
            self._scan_was_empty = True
            return self.async_show_progress_done(next_step_id="manual")
        return self.async_show_progress_done(next_step_id="pick")

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the modules found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_HOST] == CHOICE_MANUAL:
                return await self.async_step_manual()
            result = await self._async_try(user_input[CONF_HOST], errors)
            if result is not None:
                return result
        options = [SelectOptionDict(value=host, label=host) for host in self._found]
        options.append(
            SelectOptionDict(value=CHOICE_MANUAL, label="Enter the address manually")
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                        translation_key="host_choice",
                    )
                )
            }
        )
        return self.async_show_form(step_id="pick", data_schema=schema, errors=errors)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the address of the module."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            result = await self._async_try(host, errors)
            if result is not None:
                return result
        elif self._scan_was_empty:
            self._scan_was_empty = False
            errors["base"] = "none_found"
        return self.async_show_form(
            step_id="manual", data_schema=_MANUAL_SCHEMA, errors=errors
        )

    async def _async_try(
        self, host: str, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Probe an address: create the entry, abort, or fill the errors."""
        if not host:
            errors["base"] = "invalid_host"
            return None
        try:
            probe = await async_probe(self.hass, host)
        except ProbeError as err:
            if err.reason == "unsupported_model":
                return self._abort_unsupported(err)
            errors["base"] = err.reason
            return None
        return await self._async_create(probe)

    async def _async_create(self, probe: ProbeResult) -> ConfigFlowResult:
        """Create the entry unless the module is already known."""
        if probe.mac:
            await self.async_set_unique_id(probe.mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: probe.host})
        else:
            self._async_abort_entries_match({CONF_HOST: probe.host})
        return self.async_create_entry(
            title=f"Ravelli {probe.model.name}",
            data={
                CONF_HOST: probe.host,
                CONF_MODEL: probe.model.code,
                CONF_MAC: probe.mac,
            },
        )

    def _abort_unsupported(self, err: ProbeError) -> ConfigFlowResult:
        """Stop and say which model code is not supported."""
        return self.async_abort(
            reason="unsupported_model",
            description_placeholders={
                "model": str(err.model_code),
                "issue_url": ISSUE_URL,
            },
        )
```

- [ ] **Step 6: Write the English texts**

`custom_components/ravelli_smart_wifi/translations/en.json`:

```json
{
  "config": {
    "flow_title": "{name} ({host})",
    "step": {
      "user": {
        "title": "Ravelli Smart Wi-Fi",
        "description": "Choose how to find the Wi-Fi module of the stove.",
        "menu_options": {
          "scan": "Search the local network",
          "manual": "Enter the address manually"
        }
      },
      "pick": {
        "title": "Modules found",
        "data": {
          "host": "Module"
        },
        "data_description": {
          "host": "Wi-Fi module to add."
        }
      },
      "manual": {
        "title": "Module address",
        "data": {
          "host": "Host"
        },
        "data_description": {
          "host": "IP address or hostname of the Wi-Fi module."
        }
      },
      "discovery_confirm": {
        "title": "Ravelli stove found",
        "description": "Do you want to add the {model} stove found at {host}?"
      },
      "reconfigure": {
        "title": "Change the module address",
        "data": {
          "host": "Host"
        },
        "data_description": {
          "host": "New IP address or hostname of the Wi-Fi module."
        }
      }
    },
    "progress": {
      "scan": "Searching the local network for Wi-Fi modules. This can take up to a minute."
    },
    "error": {
      "cannot_connect": "Nothing answers at this address.",
      "invalid_host": "Enter an IP address or a hostname.",
      "none_found": "No module was found on the local network. Enter its address.",
      "not_winet": "A device answers at this address, but it is not a Ravelli Smart Wi-Fi module."
    },
    "abort": {
      "already_configured": "This module is already configured.",
      "already_in_progress": "The setup of this module is already in progress.",
      "cannot_connect": "Nothing answers at this address.",
      "not_winet": "The device is not a Ravelli Smart Wi-Fi module.",
      "reconfigure_successful": "The address was updated.",
      "unsupported_model": "Stove model {model} is not supported yet. Ask for it at {issue_url}.",
      "wrong_device": "The module at this address is not the one that was configured."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Ravelli Smart Wi-Fi options",
        "data": {
          "scan_interval": "Polling interval"
        },
        "data_description": {
          "scan_interval": "Seconds between two readings of the stove, from 10 to 300."
        }
      }
    }
  },
  "selector": {
    "host_choice": {
      "options": {
        "manual": "Enter the address manually"
      }
    },
    "weekday": {
      "options": {
        "mon": "Monday",
        "tue": "Tuesday",
        "wed": "Wednesday",
        "thu": "Thursday",
        "fri": "Friday",
        "sat": "Saturday",
        "sun": "Sunday"
      }
    }
  },
  "entity": {
    "binary_sensor": {
      "alarm": {
        "name": "Alarm"
      },
      "firmware_update": {
        "name": "Firmware update"
      },
      "flame": {
        "name": "Flame"
      }
    },
    "button": {
      "sync_clock": {
        "name": "Synchronize clock"
      }
    },
    "calendar": {
      "schedule": {
        "name": "Schedule"
      }
    },
    "climate": {
      "duct_left": {
        "name": "Ducting left",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "external_thermostat": "External thermostat"
            }
          }
        }
      },
      "duct_right": {
        "name": "Ducting right",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "external_thermostat": "External thermostat"
            }
          }
        }
      },
      "stove": {
        "name": "Stove",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "manual": "Manual"
            }
          }
        }
      },
      "water": {
        "name": "Water",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "manual": "Manual"
            }
          }
        }
      }
    },
    "number": {
      "comfort_delay": {
        "name": "Comfort climate delay"
      },
      "comfort_delta": {
        "name": "Comfort climate delta"
      },
      "power": {
        "name": "Power level"
      }
    },
    "sensor": {
      "alarm": {
        "name": "Alarm message",
        "state": {
          "none": "None"
        }
      },
      "ambient_temperature": {
        "name": "Ambient temperature"
      },
      "extractor_speed": {
        "name": "Extractor speed"
      },
      "flue_temperature": {
        "name": "Flue gas temperature"
      },
      "status": {
        "name": "Status",
        "state": {
          "off": "Off",
          "pellet_loading": "Loading pellets",
          "ignition": "Ignition",
          "waiting_flame": "Waiting for the flame",
          "flame_present": "Flame present",
          "working": "Working",
          "final_cleaning": "Final cleaning",
          "eco_stop": "Eco stop",
          "alarm": "Alarm",
          "alarm_memory": "Alarm memory"
        }
      },
      "wifi_signal": {
        "name": "Wi-Fi signal"
      }
    },
    "switch": {
      "schedule": {
        "name": "Schedule"
      }
    }
  },
  "exceptions": {
    "cannot_connect": {
      "message": "The Wi-Fi module of the stove does not answer."
    },
    "command_refused": {
      "message": "The Wi-Fi module refused the command."
    },
    "device_not_found": {
      "message": "The selected device is not a Ravelli stove that is set up and loaded."
    },
    "register_not_writable": {
      "message": "Register {register} cannot be written on this stove model."
    },
    "schedule_end_before_start": {
      "message": "The end of the program must be later than its start."
    },
    "schedule_mismatch": {
      "message": "The module did not store the schedule as it was sent. Check the programs on the module."
    },
    "schedule_name_characters": {
      "message": "The program name can only hold unaccented letters, digits, spaces and common punctuation."
    },
    "schedule_name_length": {
      "message": "The program name must hold 1 to 15 characters."
    },
    "schedule_no_time": {
      "message": "An enabled program needs a start time or an end time."
    },
    "schedule_no_weekday": {
      "message": "Select at least one day of the week."
    },
    "schedule_power_range": {
      "message": "The power level must be between 1 and 5."
    },
    "schedule_slot_range": {
      "message": "The program slot must be between 1 and 6."
    },
    "schedule_temperature_range": {
      "message": "The temperature must be between 5 and 40 °C."
    },
    "schedule_time_step": {
      "message": "Start and end times must fall on a quarter of an hour."
    },
    "temperature_required": {
      "message": "Give a temperature, or turn the manual mode on."
    },
    "turn_off_during_ignition": {
      "message": "The stove is igniting and the flame is not established. Wait before turning it off."
    },
    "turn_on_in_alarm": {
      "message": "The stove is in alarm. Turn it off to acknowledge the alarm, then turn it on."
    },
    "unsupported_model": {
      "message": "Stove model {model} is not supported yet. Ask for it at {issue_url}."
    },
    "value_out_of_range": {
      "message": "Value {value} is outside the allowed range, {minimum} to {maximum}."
    }
  },
  "services": {
    "delete_schedule_program": {
      "name": "Delete schedule program",
      "description": "Frees one of the six program slots of the stove.",
      "fields": {
        "device_id": {
          "name": "Stove",
          "description": "Stove whose schedule is changed."
        },
        "slot": {
          "name": "Slot",
          "description": "Program slot, from 1 to 6."
        }
      }
    },
    "set_schedule_program": {
      "name": "Set schedule program",
      "description": "Stores a program in one of the six slots of the stove. The other slots are kept.",
      "fields": {
        "device_id": {
          "name": "Stove",
          "description": "Stove whose schedule is changed."
        },
        "enabled": {
          "name": "Enabled",
          "description": "Whether the stove follows this program."
        },
        "end": {
          "name": "End",
          "description": "Time at which the stove turns off, on a quarter of an hour. Leave empty for a program that only starts the stove."
        },
        "manual": {
          "name": "Manual mode",
          "description": "Run at the chosen power without a target temperature."
        },
        "name": {
          "name": "Name",
          "description": "Name of the program, 1 to 15 characters, without accents."
        },
        "power": {
          "name": "Power level",
          "description": "Power level, from 1 to 5."
        },
        "slot": {
          "name": "Slot",
          "description": "Program slot, from 1 to 6."
        },
        "start": {
          "name": "Start",
          "description": "Time at which the stove turns on, on a quarter of an hour. Leave empty for a program that only stops the stove."
        },
        "temperature": {
          "name": "Temperature",
          "description": "Target temperature, from 5 to 40 °C. Not needed in manual mode."
        },
        "weekdays": {
          "name": "Days",
          "description": "Days of the week on which the program runs."
        }
      }
    }
  }
}
```

- [ ] **Step 7: Write the French texts**

`custom_components/ravelli_smart_wifi/translations/fr.json`:

```json
{
  "config": {
    "flow_title": "{name} ({host})",
    "step": {
      "user": {
        "title": "Ravelli Smart Wi-Fi",
        "description": "Choisissez comment trouver le module Wi-Fi du poêle.",
        "menu_options": {
          "scan": "Rechercher sur le réseau local",
          "manual": "Saisir l'adresse manuellement"
        }
      },
      "pick": {
        "title": "Modules trouvés",
        "data": {
          "host": "Module"
        },
        "data_description": {
          "host": "Module Wi-Fi à ajouter."
        }
      },
      "manual": {
        "title": "Adresse du module",
        "data": {
          "host": "Hôte"
        },
        "data_description": {
          "host": "Adresse IP ou nom d'hôte du module Wi-Fi."
        }
      },
      "discovery_confirm": {
        "title": "Poêle Ravelli trouvé",
        "description": "Voulez-vous ajouter le poêle {model} trouvé à l'adresse {host} ?"
      },
      "reconfigure": {
        "title": "Changer l'adresse du module",
        "data": {
          "host": "Hôte"
        },
        "data_description": {
          "host": "Nouvelle adresse IP ou nouveau nom d'hôte du module Wi-Fi."
        }
      }
    },
    "progress": {
      "scan": "Recherche des modules Wi-Fi sur le réseau local. Cela peut prendre jusqu'à une minute."
    },
    "error": {
      "cannot_connect": "Rien ne répond à cette adresse.",
      "invalid_host": "Saisissez une adresse IP ou un nom d'hôte.",
      "none_found": "Aucun module n'a été trouvé sur le réseau local. Saisissez son adresse.",
      "not_winet": "Un appareil répond à cette adresse, mais ce n'est pas un module Ravelli Smart Wi-Fi."
    },
    "abort": {
      "already_configured": "Ce module est déjà configuré.",
      "already_in_progress": "La configuration de ce module est déjà en cours.",
      "cannot_connect": "Rien ne répond à cette adresse.",
      "not_winet": "L'appareil n'est pas un module Ravelli Smart Wi-Fi.",
      "reconfigure_successful": "L'adresse a été mise à jour.",
      "unsupported_model": "Le modèle de poêle {model} n'est pas encore pris en charge. Demandez-le sur {issue_url}.",
      "wrong_device": "Le module à cette adresse n'est pas celui qui a été configuré."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Options de Ravelli Smart Wi-Fi",
        "data": {
          "scan_interval": "Intervalle de lecture"
        },
        "data_description": {
          "scan_interval": "Secondes entre deux lectures du poêle, de 10 à 300."
        }
      }
    }
  },
  "selector": {
    "host_choice": {
      "options": {
        "manual": "Saisir l'adresse manuellement"
      }
    },
    "weekday": {
      "options": {
        "mon": "Lundi",
        "tue": "Mardi",
        "wed": "Mercredi",
        "thu": "Jeudi",
        "fri": "Vendredi",
        "sat": "Samedi",
        "sun": "Dimanche"
      }
    }
  },
  "entity": {
    "binary_sensor": {
      "alarm": {
        "name": "Alarme"
      },
      "firmware_update": {
        "name": "Mise à jour du firmware"
      },
      "flame": {
        "name": "Flamme"
      }
    },
    "button": {
      "sync_clock": {
        "name": "Synchroniser l'horloge"
      }
    },
    "calendar": {
      "schedule": {
        "name": "Programmation"
      }
    },
    "climate": {
      "duct_left": {
        "name": "Canalisation gauche",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "external_thermostat": "Thermostat externe"
            }
          }
        }
      },
      "duct_right": {
        "name": "Canalisation droite",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "external_thermostat": "Thermostat externe"
            }
          }
        }
      },
      "stove": {
        "name": "Poêle",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "manual": "Manuel"
            }
          }
        }
      },
      "water": {
        "name": "Eau",
        "state_attributes": {
          "preset_mode": {
            "state": {
              "manual": "Manuel"
            }
          }
        }
      }
    },
    "number": {
      "comfort_delay": {
        "name": "Délai du confort climat"
      },
      "comfort_delta": {
        "name": "Écart du confort climat"
      },
      "power": {
        "name": "Puissance"
      }
    },
    "sensor": {
      "alarm": {
        "name": "Message d'alarme",
        "state": {
          "none": "Aucune"
        }
      },
      "ambient_temperature": {
        "name": "Température ambiante"
      },
      "extractor_speed": {
        "name": "Vitesse de l'extracteur"
      },
      "flue_temperature": {
        "name": "Température des fumées"
      },
      "status": {
        "name": "État",
        "state": {
          "off": "Éteint",
          "pellet_loading": "Chargement des granulés",
          "ignition": "Allumage",
          "waiting_flame": "Attente de la flamme",
          "flame_present": "Flamme présente",
          "working": "En chauffe",
          "final_cleaning": "Nettoyage final",
          "eco_stop": "Eco stop",
          "alarm": "Alarme",
          "alarm_memory": "Alarme mémorisée"
        }
      },
      "wifi_signal": {
        "name": "Signal Wi-Fi"
      }
    },
    "switch": {
      "schedule": {
        "name": "Programmation"
      }
    }
  },
  "exceptions": {
    "cannot_connect": {
      "message": "Le module Wi-Fi du poêle ne répond pas."
    },
    "command_refused": {
      "message": "Le module Wi-Fi a refusé la commande."
    },
    "device_not_found": {
      "message": "L'appareil sélectionné n'est pas un poêle Ravelli configuré et chargé."
    },
    "register_not_writable": {
      "message": "Le registre {register} ne peut pas être écrit sur ce modèle de poêle."
    },
    "schedule_end_before_start": {
      "message": "La fin du programme doit être postérieure à son début."
    },
    "schedule_mismatch": {
      "message": "Le module n'a pas enregistré la programmation telle qu'elle a été envoyée. Vérifiez les programmes sur le module."
    },
    "schedule_name_characters": {
      "message": "Le nom du programme ne peut contenir que des lettres sans accent, des chiffres, des espaces et la ponctuation courante."
    },
    "schedule_name_length": {
      "message": "Le nom du programme doit contenir de 1 à 15 caractères."
    },
    "schedule_no_time": {
      "message": "Un programme activé a besoin d'une heure de début ou d'une heure de fin."
    },
    "schedule_no_weekday": {
      "message": "Sélectionnez au moins un jour de la semaine."
    },
    "schedule_power_range": {
      "message": "La puissance doit être comprise entre 1 et 5."
    },
    "schedule_slot_range": {
      "message": "L'emplacement du programme doit être compris entre 1 et 6."
    },
    "schedule_temperature_range": {
      "message": "La température doit être comprise entre 5 et 40 °C."
    },
    "schedule_time_step": {
      "message": "Les heures de début et de fin doivent tomber sur un quart d'heure."
    },
    "temperature_required": {
      "message": "Indiquez une température, ou activez le mode manuel."
    },
    "turn_off_during_ignition": {
      "message": "Le poêle s'allume et la flamme n'est pas établie. Attendez avant de l'éteindre."
    },
    "turn_on_in_alarm": {
      "message": "Le poêle est en alarme. Éteignez-le pour acquitter l'alarme, puis rallumez-le."
    },
    "unsupported_model": {
      "message": "Le modèle de poêle {model} n'est pas encore pris en charge. Demandez-le sur {issue_url}."
    },
    "value_out_of_range": {
      "message": "La valeur {value} est hors de la plage autorisée, de {minimum} à {maximum}."
    }
  },
  "services": {
    "delete_schedule_program": {
      "name": "Supprimer un programme",
      "description": "Libère l'un des six emplacements de programme du poêle.",
      "fields": {
        "device_id": {
          "name": "Poêle",
          "description": "Poêle dont la programmation est modifiée."
        },
        "slot": {
          "name": "Emplacement",
          "description": "Emplacement du programme, de 1 à 6."
        }
      }
    },
    "set_schedule_program": {
      "name": "Définir un programme",
      "description": "Enregistre un programme dans l'un des six emplacements du poêle. Les autres emplacements sont conservés.",
      "fields": {
        "device_id": {
          "name": "Poêle",
          "description": "Poêle dont la programmation est modifiée."
        },
        "enabled": {
          "name": "Activé",
          "description": "Indique si le poêle suit ce programme."
        },
        "end": {
          "name": "Fin",
          "description": "Heure à laquelle le poêle s'éteint, sur un quart d'heure. Laissez vide pour un programme qui ne fait qu'allumer le poêle."
        },
        "manual": {
          "name": "Mode manuel",
          "description": "Fonctionne à la puissance choisie, sans température cible."
        },
        "name": {
          "name": "Nom",
          "description": "Nom du programme, de 1 à 15 caractères, sans accent."
        },
        "power": {
          "name": "Puissance",
          "description": "Puissance, de 1 à 5."
        },
        "slot": {
          "name": "Emplacement",
          "description": "Emplacement du programme, de 1 à 6."
        },
        "start": {
          "name": "Début",
          "description": "Heure à laquelle le poêle s'allume, sur un quart d'heure. Laissez vide pour un programme qui ne fait qu'éteindre le poêle."
        },
        "temperature": {
          "name": "Température",
          "description": "Température cible, de 5 à 40 °C. Inutile en mode manuel."
        },
        "weekdays": {
          "name": "Jours",
          "description": "Jours de la semaine où le programme s'applique."
        }
      }
    }
  }
}
```

- [ ] **Step 8: Write the icons**

`custom_components/ravelli_smart_wifi/icons.json`:

```json
{
  "entity": {
    "binary_sensor": {
      "flame": {
        "default": "mdi:fire-off",
        "state": {
          "on": "mdi:fire"
        }
      }
    },
    "button": {
      "sync_clock": {
        "default": "mdi:clock-check-outline"
      }
    },
    "calendar": {
      "schedule": {
        "default": "mdi:calendar-clock"
      }
    },
    "climate": {
      "duct_left": {
        "default": "mdi:air-filter"
      },
      "duct_right": {
        "default": "mdi:air-filter"
      },
      "stove": {
        "default": "mdi:fireplace"
      },
      "water": {
        "default": "mdi:water-boiler"
      }
    },
    "number": {
      "comfort_delay": {
        "default": "mdi:timer-outline"
      },
      "comfort_delta": {
        "default": "mdi:thermometer-lines"
      },
      "power": {
        "default": "mdi:fire"
      }
    },
    "sensor": {
      "alarm": {
        "default": "mdi:alert-circle-outline"
      },
      "extractor_speed": {
        "default": "mdi:fan"
      },
      "status": {
        "default": "mdi:fireplace"
      }
    },
    "switch": {
      "schedule": {
        "default": "mdi:calendar-clock"
      }
    }
  },
  "services": {
    "delete_schedule_program": {
      "service": "mdi:calendar-remove"
    },
    "set_schedule_program": {
      "service": "mdi:calendar-edit"
    }
  }
}
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `uv run pytest tests/test_init.py tests/test_config_flow.py tests/test_translations.py -v`
Expected: all tests pass.

If `test_scan_finds_the_module` fails on the type of the first result, check that the scan task is created with `eager_start=False`: an eager task finishes before the step returns when every answer is simulated, and the progress screen is skipped.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 10: Commit and integrate**

```bash
git add -A
git commit -m "feat: add entry setup, user config flow and translations"
git checkout main
git merge --ff-only feature/config-flow
git branch -d feature/config-flow
```

---

### Task 7: DHCP discovery, reconfiguration and options

**Branch:** `feature/flow-discovery-options`

**Files:**
- Modify: `custom_components/ravelli_smart_wifi/config_flow.py`
- Test: `tests/test_config_flow_discovery.py`, `tests/test_options_flow.py`

**Interfaces:**
- Consumes from Task 6: `async_probe`, `ProbeError`, `ProbeResult`, `RavelliConfigFlow._async_try`, `_async_create`, `_abort_unsupported`, the attribute `self._probe`; from `const.py`: `DEFAULT_SCAN_INTERVAL`, `MIN_SCAN_INTERVAL`, `MAX_SCAN_INTERVAL`.
- Produces: the flow steps `dhcp`, `discovery_confirm` and `reconfigure`; the class `RavelliOptionsFlow` with the step `init`. The option key is `CONF_SCAN_INTERVAL` (`"scan_interval"`), an `int` number of seconds.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/flow-discovery-options
```

- [ ] **Step 2: Write the failing tests**

`tests/test_config_flow_discovery.py`:

```python
"""Tests for the DHCP discovery and the reconfiguration."""

from unittest.mock import patch

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.config_entries import SOURCE_DHCP
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )
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
```

`tests/test_options_flow.py`:

```python
"""Tests for the options flow."""

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData


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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_config_flow_discovery.py tests/test_options_flow.py -v`
Expected: every test of the two files fails. The discovery tests get the user menu instead of the confirmation form, the reconfigure tests raise `UnknownStep`, and the options tests raise `UnknownHandler`.

- [ ] **Step 4: Write the implementation**

In `custom_components/ravelli_smart_wifi/config_flow.py`, replace these import lines

```python
from dataclasses import dataclass
```

```python
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
```

```python
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
```

```python
from .const import DOMAIN, ISSUE_URL, SCAN_CONCURRENCY, SCAN_MIN_PREFIX, SCAN_TIMEOUT
```

with, in the same order,

```python
from dataclasses import dataclass, replace
```

```python
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
```

```python
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
```

```python
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ISSUE_URL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_CONCURRENCY,
    SCAN_MIN_PREFIX,
    SCAN_TIMEOUT,
)
```

Add these methods to `RavelliConfigFlow`, right after `__init__`:

```python
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RavelliOptionsFlow:
        """Return the flow that edits the options."""
        return RavelliOptionsFlow()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a module seen on the network by the DHCP integration."""
        mac = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(mac)
        # A known module with a new lease: the entry follows it.
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        try:
            probe = await async_probe(self.hass, discovery_info.ip)
        except ProbeError as err:
            if err.reason == "unsupported_model":
                return self._abort_unsupported(err)
            return self.async_abort(reason=err.reason)
        self._probe = replace(probe, mac=mac)
        self.context["title_placeholders"] = {
            "name": f"Ravelli {probe.model.name}",
            "host": probe.host,
        }
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask before adding a module that was discovered."""
        assert self._probe is not None
        if user_input is not None:
            return await self._async_create(self._probe)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self._probe.model.name,
                "host": self._probe.host,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address of a module that is already set up."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            if not host:
                errors["base"] = "invalid_host"
            else:
                try:
                    probe = await async_probe(self.hass, host)
                except ProbeError as err:
                    if err.reason == "unsupported_model":
                        return self._abort_unsupported(err)
                    errors["base"] = err.reason
                else:
                    if entry.unique_id and probe.mac and probe.mac != entry.unique_id:
                        return self.async_abort(reason="wrong_device")
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            CONF_HOST: probe.host,
                            CONF_MODEL: probe.model.code,
                        },
                    )
        schema = vol.Schema(
            {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
```

Append this class at the end of the file:

```python
class RavelliOptionsFlow(OptionsFlowWithReload):
    """Edits the polling interval; the entry is reloaded when it changes."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the polling interval."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config_flow_discovery.py tests/test_options_flow.py tests/test_config_flow.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add DHCP discovery, reconfiguration and options flow"
git checkout main
git merge --ff-only feature/flow-discovery-options
git branch -d feature/flow-discovery-options
```

---

### Task 8: Base entity and sensors

**Branch:** `feature/sensors`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/entity.py`
- Create: `custom_components/ravelli_smart_wifi/sensor.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (the `PLATFORMS` line)
- Test: `tests/test_sensor.py`

**Interfaces:**
- Consumes: `RavelliCoordinator`, `RavelliConfigEntry`, `RavelliData` from `coordinator.py`; `REG_ALARM`, `STATUS_KEYS`, `STATUS_UNKNOWN` from `models.py`; `DOMAIN`, `MANUFACTURER` from `const.py`; `entity_id_for`, `advance` from `tests/helpers.py`.
- Produces in `entity.py`: `RavelliEntity(coordinator: RavelliCoordinator, key: str)`, a `CoordinatorEntity`. It sets `unique_id` to `<MAC or entry id>_<key>`, `translation_key` to `key`, `has_entity_name` to true and the device info. Every platform of the later tasks subclasses it.
- Produces in `sensor.py`: `ALARM_NONE = "none"` and the six sensors with the keys `status`, `alarm`, `ambient_temperature`, `flue_temperature`, `extractor_speed`, `wifi_signal`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/sensors
```

- [ ] **Step 2: Write the failing tests**

`tests/test_sensor.py`:

```python
"""Tests for the sensors and the device."""

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, FakeModule
from .helpers import advance, entity_id_for

STATUS_OPTIONS = [
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
]


async def test_sensors_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The capture of an idle stove at 22 degrees."""
    status = hass.states.get(entity_id_for(hass, "sensor", "status"))
    assert status.state == "off"
    assert status.attributes["raw_value"] == 0
    assert status.attributes["options"] == STATUS_OPTIONS
    assert status.attributes["device_class"] == "enum"

    alarm = hass.states.get(entity_id_for(hass, "sensor", "alarm"))
    assert alarm.state == "none"
    assert alarm.attributes["raw_value"] == 0

    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == "22.0"
    assert ambient.attributes["unit_of_measurement"] == "°C"
    assert ambient.attributes["device_class"] == "temperature"
    assert ambient.attributes["state_class"] == "measurement"

    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == "0"
    assert flue.attributes["unit_of_measurement"] == "°C"


@pytest.mark.parametrize("key", ["extractor_speed", "wifi_signal"])
async def test_sensors_that_are_off_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, key: str
) -> None:
    """They exist in the registry, disabled, and have no state."""
    entity_id = entity_id_for(hass, "sensor", key)

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("enable_all_entities")
async def test_sensors_once_enabled(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The extractor has no unit yet; the signal is in dBm."""
    extractor = hass.states.get(entity_id_for(hass, "sensor", "extractor_speed"))
    assert extractor.state == "0"
    assert "unit_of_measurement" not in extractor.attributes

    signal_id = entity_id_for(hass, "sensor", "wifi_signal")
    signal = hass.states.get(signal_id)
    assert signal.state == "-74"
    assert signal.attributes["unit_of_measurement"] == "dBm"
    assert signal.attributes["device_class"] == "signal_strength"
    entry = er.async_get(hass).async_get(signal_id)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_status_follows_the_stove(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The next poll shows the new status and temperatures."""
    fake_module.common[2] = 5
    fake_module.categories[2].update({0: 43, 4: 180})

    await advance(hass, freezer)

    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "working"
    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == "21.5"
    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == "180"


async def test_unknown_status_code(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A code outside the table gives the unknown state and keeps the code."""
    fake_module.common[2] = 42

    await advance(hass, freezer)

    status = hass.states.get(entity_id_for(hass, "sensor", "status"))
    assert status.state == STATE_UNKNOWN
    assert status.attributes["raw_value"] == 42


async def test_alarm_message(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The module sends the alarm text itself."""
    fake_module.common.update({2: 8, 3: 5})
    fake_module.extra["alr"] = "AL05 NO IGNITION"

    await advance(hass, freezer)

    alarm = hass.states.get(entity_id_for(hass, "sensor", "alarm"))
    assert alarm.state == "AL05 NO IGNITION"
    assert alarm.attributes["raw_value"] == 5
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "alarm"


async def test_missing_register_gives_an_unknown_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The other sensors keep working."""
    del fake_module.categories[2][0]
    del fake_module.categories[2][4]

    await advance(hass, freezer)

    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == STATE_UNKNOWN
    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == STATE_UNKNOWN
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "off"


async def test_sensors_follow_the_availability_of_the_module(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unplugging the stove makes the entities unavailable, not stale."""
    entity_id = entity_id_for(hass, "sensor", "status")

    fake_module.error = aiohttp.ClientConnectionError()
    await advance(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    fake_module.error = None
    await advance(hass, freezer)
    assert hass.states.get(entity_id).state == "off"


async def test_device(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """One device per module, tied to its MAC address."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})

    assert device is not None
    assert device.name == "Ravelli AIR-RDS"
    assert device.manufacturer == "Ravelli"
    assert device.model == "AIR-RDS"
    assert device.sw_version == "0.51"
    assert device.configuration_url == f"http://{HOST}"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}


async def test_entry_without_a_mac_address(
    hass: HomeAssistant, fake_module: FakeModule
) -> None:
    """The entry id replaces the MAC address in the identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli AIR-RDS",
        data={CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: None},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_status"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "off"
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device is not None
    assert device.connections == set()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_sensor.py -v`
Expected: every test fails with `AssertionError: no sensor entity for status` or with an entity or device that is `None`.

- [ ] **Step 4: Write the base entity**

`custom_components/ravelli_smart_wifi/entity.py`:

```python
"""Base entity."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import RavelliCoordinator


class RavelliEntity(CoordinatorEntity[RavelliCoordinator]):
    """Entity of one stove; unavailable when the module stops answering."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Name the entity after its key and attach it to the device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device_id = entry.unique_id or entry.entry_id
        mac = entry.data.get(CONF_MAC)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=coordinator.model.name,
            sw_version=coordinator.data.system.get("fwVer"),
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
```

- [ ] **Step 5: Write the sensors**

`custom_components/ravelli_smart_wifi/sensor.py`:

```python
"""Sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RavelliConfigEntry, RavelliCoordinator, RavelliData
from .entity import RavelliEntity
from .models import REG_ALARM, STATUS_KEYS, STATUS_UNKNOWN

ALARM_NONE = "none"


def _status(data: RavelliData) -> str | None:
    """Return the status key; None gives the unknown state."""
    key = data.state.status_key
    return None if key == STATUS_UNKNOWN else key


@dataclass(frozen=True, kw_only=True)
class RavelliSensorDescription(SensorEntityDescription):
    """Describes one sensor and where its value comes from."""

    value_fn: Callable[[RavelliData], StateType]
    raw_fn: Callable[[RavelliData], int | None] | None = None


SENSORS: tuple[RavelliSensorDescription, ...] = (
    RavelliSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_KEYS.values()),
        value_fn=_status,
        raw_fn=lambda data: data.state.status_code,
    ),
    RavelliSensorDescription(
        key="alarm",
        value_fn=lambda data: data.state.alarm_text or ALARM_NONE,
        raw_fn=lambda data: data.state.raw(REG_ALARM),
    ),
    RavelliSensorDescription(
        key="ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.ambient_temperature,
    ),
    RavelliSensorDescription(
        key="flue_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.state.flue_temperature,
    ),
    # The scale of this register is not verified: raw value, no unit.
    RavelliSensorDescription(
        key="extractor_speed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.state.extractor_speed,
    ),
    RavelliSensorDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.system.get("rssi"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of one stove."""
    async_add_entities(
        RavelliSensor(entry.runtime_data, description) for description in SENSORS
    )


class RavelliSensor(RavelliEntity, SensorEntity):
    """One value read from the stove."""

    entity_description: RavelliSensorDescription

    def __init__(
        self, coordinator: RavelliCoordinator, description: RavelliSensorDescription
    ) -> None:
        """Keep the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw code of the status and of the alarm."""
        if self.entity_description.raw_fn is None:
            return None
        return {"raw_value": self.entity_description.raw_fn(self.coordinator.data)}
```

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
PLATFORMS: list[Platform] = []
```

with

```python
PLATFORMS: list[Platform] = [Platform.SENSOR]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_sensor.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 7: Commit and integrate**

```bash
git add -A
git commit -m "feat: add base entity and sensors"
git checkout main
git merge --ff-only feature/sensors
git branch -d feature/sensors
```

---

### Task 9: Binary sensors

**Branch:** `feature/binary-sensors`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/binary_sensor.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (the `PLATFORMS` line)
- Test: `tests/test_binary_sensor.py`

**Interfaces:**
- Consumes: `RavelliEntity` from `entity.py`; `RavelliCoordinator`, `RavelliConfigEntry`, `RavelliData` from `coordinator.py`; the helpers and fixtures of Task 4.
- Produces: the binary sensors with the keys `alarm`, `flame` and `firmware_update`. `flame` exists only when the module reports a flame value.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/binary-sensors
```

- [ ] **Step 2: Write the failing tests**

`tests/test_binary_sensor.py`:

```python
"""Tests for the binary sensors."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC, FakeModule
from .helpers import advance, entity_id_for


async def test_binary_sensors_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """No alarm and no pending update."""
    alarm = hass.states.get(entity_id_for(hass, "binary_sensor", "alarm"))
    assert alarm.state == STATE_OFF
    assert alarm.attributes["device_class"] == "problem"

    update_id = entity_id_for(hass, "binary_sensor", "firmware_update")
    update = hass.states.get(update_id)
    assert update.state == STATE_OFF
    assert update.attributes["device_class"] == "update"
    entry = er.async_get(hass).async_get(update_id)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_flame_is_absent_when_the_board_does_not_report_it(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The AIR-RDS capture reports 255: no information."""
    registry = er.async_get(hass)

    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{MAC}_flame") is None


async def test_flame_follows_the_module(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The entity exists as soon as the module reports a flame value."""
    fake_module.extra["flame"] = 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_id_for(hass, "binary_sensor", "flame")
    assert hass.states.get(entity_id).state == STATE_OFF

    fake_module.extra["flame"] = 1
    await advance(hass, freezer)

    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize(
    ("status", "alarm_code"), [(8, 0), (9, 0), (5, 4), (8, 5)]
)
async def test_alarm(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    status: int,
    alarm_code: int,
) -> None:
    """An alarm status or an alarm code turns the sensor on."""
    fake_module.common.update({2: status, 3: alarm_code})

    await advance(hass, freezer)

    alarm = hass.states.get(entity_id_for(hass, "binary_sensor", "alarm"))
    assert alarm.state == STATE_ON


async def test_firmware_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The system status is read every ten minutes."""
    fake_module.system["fwUpdate"] = True

    await advance(hass, freezer, seconds=601)

    update = hass.states.get(entity_id_for(hass, "binary_sensor", "firmware_update"))
    assert update.state == STATE_ON
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_binary_sensor.py -v`
Expected: `test_flame_is_absent_when_the_board_does_not_report_it` passes because nothing exists yet; every other test fails with `AssertionError: no binary_sensor entity for ...`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/binary_sensor.py`:

```python
"""Binary sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator, RavelliData
from .entity import RavelliEntity


@dataclass(frozen=True, kw_only=True)
class RavelliBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one binary sensor and where its value comes from."""

    is_on_fn: Callable[[RavelliData], bool]
    exists_fn: Callable[[RavelliData], bool] = lambda data: True


BINARY_SENSORS: tuple[RavelliBinarySensorDescription, ...] = (
    RavelliBinarySensorDescription(
        key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data.state.has_alarm,
    ),
    RavelliBinarySensorDescription(
        key="flame",
        is_on_fn=lambda data: bool(data.state.flame),
        exists_fn=lambda data: data.state.flame is not None,
    ),
    RavelliBinarySensorDescription(
        key="firmware_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(data.system.get("fwUpdate")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors the stove has data for."""
    coordinator = entry.runtime_data
    async_add_entities(
        RavelliBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(coordinator.data)
    )


class RavelliBinarySensor(RavelliEntity, BinarySensorEntity):
    """One on/off fact read from the stove."""

    entity_description: RavelliBinarySensorDescription

    def __init__(
        self,
        coordinator: RavelliCoordinator,
        description: RavelliBinarySensorDescription,
    ) -> None:
        """Keep the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the fact."""
        return self.entity_description.is_on_fn(self.coordinator.data)
```

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
PLATFORMS: list[Platform] = [Platform.SENSOR]
```

with

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_binary_sensor.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add binary sensors"
git checkout main
git merge --ff-only feature/binary-sensors
git branch -d feature/binary-sensors
```

---

### Task 10: Numbers

**Branch:** `feature/numbers`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/number.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (the `PLATFORMS` line)
- Test: `tests/test_number.py`

**Interfaces:**
- Consumes: `RavelliEntity`; `RavelliCoordinator.async_write_register(register: int, value: int)`; `WRITE_BOUNDS`, `REG_POWER`, `REG_COMFORT_DELTA`, `REG_COMFORT_DELAY` from `models.py`.
- Produces: the numbers with the keys `power`, `comfort_delta` and `comfort_delay`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/numbers
```

- [ ] **Step 2: Write the failing tests**

`tests/test_number.py`:

```python
"""Tests for the numbers."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_number.py -v`
Expected: every test fails with `AssertionError: no number entity for ...`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/number.py`:

```python
"""Number platform."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import REG_COMFORT_DELAY, REG_COMFORT_DELTA, REG_POWER, WRITE_BOUNDS


@dataclass(frozen=True, kw_only=True)
class RavelliNumberDescription(NumberEntityDescription):
    """Describes one number and the register behind it."""

    register: int


NUMBERS: tuple[RavelliNumberDescription, ...] = (
    RavelliNumberDescription(
        key="power",
        register=REG_POWER,
        mode=NumberMode.SLIDER,
    ),
    RavelliNumberDescription(
        key="comfort_delta",
        register=REG_COMFORT_DELTA,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
    ),
    RavelliNumberDescription(
        key="comfort_delay",
        register=REG_COMFORT_DELAY,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the numbers of one stove."""
    async_add_entities(
        RavelliNumber(entry.runtime_data, description) for description in NUMBERS
    )


class RavelliNumber(RavelliEntity, NumberEntity):
    """One writable register, bounded like in the vendor UI."""

    entity_description: RavelliNumberDescription
    _attr_native_step = 1

    def __init__(
        self, coordinator: RavelliCoordinator, description: RavelliNumberDescription
    ) -> None:
        """Take the bounds from the register table."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        minimum, maximum = WRITE_BOUNDS[description.register]
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float | None:
        """Return the raw value of the register."""
        return self.coordinator.data.state.raw(self.entity_description.register)

    async def async_set_native_value(self, value: float) -> None:
        """Write the register."""
        await self.coordinator.async_write_register(
            self.entity_description.register, int(value)
        )
```

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
```

with

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_number.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add numbers for power and comfort climate"
git checkout main
git merge --ff-only feature/numbers
git branch -d feature/numbers
```

---

### Task 11: Stove thermostat

**Branch:** `feature/climate-stove`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/climate.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (the `PLATFORMS` list)
- Test: `tests/test_climate.py`

**Interfaces:**
- Consumes: `RavelliEntity`; `RavelliCoordinator.async_write_register(register, value)` and `async_set_power(on: bool)`; `StoveState` properties `is_on`, `status_code`, `ambient_temperature`, `power`, `raw()`; `MANUAL_SETPOINT`, `REG_SETPOINT`, `REG_POWER` from `models.py`; `DOMAIN` from `const.py`.
- Produces in `climate.py`:
  - `PRESET_MANUAL = "manual"`, `HVAC_ACTIONS: dict[int, HVACAction]`.
  - `RavelliSetpointClimate(coordinator, key)`: base thermostat backed by one set point register. Subclasses set the class attributes `_register: int`, `_presets: dict[int, str]` (raw special value to preset name), `_attr_min_temp`, `_attr_max_temp` and may set `_default_target: int` (20 by default). It provides `target_temperature`, `preset_mode`, `async_set_temperature`, `async_set_preset_mode` and the helper `_raw() -> int | None`.
  - `RavelliPowerClimate(RavelliSetpointClimate)`: adds `hvac_mode`, `async_set_hvac_mode`, `async_turn_on`, `async_turn_off`, all driving the stove itself.
  - `RavelliStoveClimate(coordinator)`: the thermostat with the key `stove`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/climate-stove
```

- [ ] **Step 2: Write the failing tests**

`tests/test_climate.py`:

```python
"""Tests for the stove thermostat."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from .fake_module import PATH_GET, PATH_SET, FakeModule
from .helpers import advance, entity_id_for


def stove(hass: HomeAssistant) -> State:
    """Return the state of the thermostat."""
    state = hass.states.get(entity_id_for(hass, "climate", "stove"))
    assert state is not None
    return state


async def call(hass: HomeAssistant, action: str, **data: Any) -> None:
    """Call a climate action on the thermostat."""
    await hass.services.async_call(
        "climate",
        action,
        {"entity_id": entity_id_for(hass, "climate", "stove"), **data},
        blocking=True,
    )


async def test_thermostat_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The capture of an idle stove at 22 degrees."""
    state = stove(hass)

    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["heat", "off"]
    assert state.attributes["hvac_action"] == "off"
    assert state.attributes["current_temperature"] == 22.0
    assert state.attributes["temperature"] == 22
    assert state.attributes["min_temp"] == 5
    assert state.attributes["max_temp"] == 40
    assert state.attributes["target_temp_step"] == 1
    assert state.attributes["fan_mode"] == "1"
    assert state.attributes["fan_modes"] == ["1", "2", "3", "4", "5"]
    assert state.attributes["preset_mode"] == "none"
    assert state.attributes["preset_modes"] == ["none", "manual"]


@pytest.mark.parametrize(
    ("status", "mode", "action"),
    [
        (0, "off", "off"),
        (1, "heat", "preheating"),
        (2, "heat", "preheating"),
        (3, "heat", "preheating"),
        (4, "heat", "preheating"),
        (5, "heat", "heating"),
        (6, "off", "off"),
        (7, "heat", "idle"),
        (8, "off", "off"),
        (9, "off", "off"),
        (42, "off", None),
    ],
)
async def test_mode_and_action_follow_the_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    status: int,
    mode: str,
    action: str | None,
) -> None:
    """Ignition shows as preheating and eco stop as idle."""
    fake_module.common[2] = status

    await advance(hass, freezer)

    assert stove(hass).state == mode
    assert stove(hass).attributes.get("hvac_action") == action


@pytest.mark.parametrize(("asked", "written"), [(23, 23), (23.4, 23), (5, 5), (40, 40)])
async def test_set_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: float,
    written: int,
) -> None:
    """The stove works in whole degrees."""
    await call(hass, "set_temperature", temperature=asked)

    assert fake_module.categories[2][50] == written
    assert stove(hass).attributes["temperature"] == written


@pytest.mark.parametrize("asked", [4, 41, 50])
async def test_temperature_outside_the_bounds_is_refused(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: int,
) -> None:
    """41 is the manual mode, not a temperature."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "set_temperature", temperature=asked)

    assert fake_module.count(PATH_SET) == 0


async def test_set_fan_mode_writes_the_power_level(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The fan modes are the five power levels, as in Agua IOT."""
    await call(hass, "set_fan_mode", fan_mode="3")

    assert fake_module.categories[2][51] == 3
    assert stove(hass).attributes["fan_mode"] == "3"


async def test_unknown_fan_mode_is_refused(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """There is no level 6."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "set_fan_mode", fan_mode="6")

    assert fake_module.count(PATH_SET) == 0


async def test_manual_preset_and_back(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Leaving the manual mode restores the last target."""
    await call(hass, "set_preset_mode", preset_mode="manual")

    assert fake_module.categories[2][50] == 41
    assert stove(hass).attributes["preset_mode"] == "manual"
    assert stove(hass).attributes["temperature"] is None

    await call(hass, "set_preset_mode", preset_mode="none")

    assert fake_module.categories[2][50] == 22
    assert stove(hass).attributes["preset_mode"] == "none"
    assert stove(hass).attributes["temperature"] == 22


async def test_leaving_manual_mode_without_a_known_target(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A stove found in manual mode goes back to 20 degrees."""
    fake_module.categories[2][50] = 41
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert stove(hass).attributes["preset_mode"] == "manual"

    await call(hass, "set_preset_mode", preset_mode="none")

    assert fake_module.categories[2][50] == 20


async def test_setting_a_temperature_leaves_the_manual_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A target temperature is a way out of the manual mode."""
    fake_module.categories[2][50] = 41
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "set_temperature", temperature=21)

    assert stove(hass).attributes["preset_mode"] == "none"
    assert stove(hass).attributes["temperature"] == 21


@pytest.mark.parametrize(
    ("action", "data"), [("turn_on", {}), ("set_hvac_mode", {"hvac_mode": "heat"})]
)
async def test_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    action: str,
    data: dict[str, str],
) -> None:
    """The thermostat shows the ignition at once."""
    await call(hass, action, **data)

    assert fake_module.count(PATH_GET, key="022", status="1") == 1
    assert stove(hass).state == "heat"
    assert stove(hass).attributes["hvac_action"] == "preheating"


@pytest.mark.parametrize(
    ("action", "data"), [("turn_off", {}), ("set_hvac_mode", {"hvac_mode": "off"})]
)
async def test_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    action: str,
    data: dict[str, str],
) -> None:
    """A working stove can be turned off."""
    fake_module.common[2] = 5
    await advance(hass, freezer)

    await call(hass, action, **data)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1
    assert stove(hass).state == "off"


async def test_turn_off_is_refused_during_ignition(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The message tells the user to wait for the flame."""
    fake_module.common[2] = 2
    fake_module.extra["flame"] = 0

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "turn_off")

    assert err.value.translation_key == "turn_off_during_ignition"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_turn_on_is_refused_in_alarm(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The message tells the user to acknowledge the alarm first."""
    fake_module.common[2] = 8

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "turn_on")

    assert err.value.translation_key == "turn_on_in_alarm"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_missing_registers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The thermostat stays up when the module omits its registers."""
    fake_module.categories[2] = {}

    await advance(hass, freezer)

    state = stove(hass)
    assert state.state == "off"
    assert state.attributes["current_temperature"] is None
    assert state.attributes["temperature"] is None
    assert state.attributes["fan_mode"] is None
    assert state.attributes["preset_mode"] == "none"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_climate.py -v`
Expected: every test fails with `AssertionError: no climate entity for stove`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/climate.py`:

```python
"""Climate platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import MANUAL_SETPOINT, REG_POWER, REG_SETPOINT

PRESET_MANUAL = "manual"

HVAC_ACTIONS: dict[int, HVACAction] = {
    0: HVACAction.OFF,
    1: HVACAction.PREHEATING,
    2: HVACAction.PREHEATING,
    3: HVACAction.PREHEATING,
    4: HVACAction.PREHEATING,
    5: HVACAction.HEATING,
    6: HVACAction.OFF,
    7: HVACAction.IDLE,
    8: HVACAction.OFF,
    9: HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the thermostats of one stove."""
    async_add_entities([RavelliStoveClimate(entry.runtime_data)])


class RavelliSetpointClimate(RavelliEntity, ClimateEntity):
    """Thermostat backed by one set point register with special values."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _register: int
    # Raw values of the register that are a mode, not a temperature.
    _presets: dict[int, str]
    _default_target = 20

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Remember the target the stove has when Home Assistant starts."""
        super().__init__(coordinator, key)
        self._attr_preset_modes = [PRESET_NONE, *self._presets.values()]
        self._last_target = self._numeric_target()

    def _raw(self) -> int | None:
        """Return the raw value of the set point register."""
        return self.coordinator.data.state.raw(self._register)

    def _numeric_target(self) -> int | None:
        """Return the set point when it is a temperature."""
        raw = self._raw()
        if raw is None or raw in self._presets:
            return None
        return raw if self.min_temp <= raw <= self.max_temp else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Keep the last temperature for the way back from a preset."""
        if (target := self._numeric_target()) is not None:
            self._last_target = target
        super()._handle_coordinator_update()

    @property
    def target_temperature(self) -> float | None:
        """Return the target, None while a preset replaces it."""
        return self._numeric_target()

    @property
    def preset_mode(self) -> str:
        """Return the preset the set point register stands for."""
        raw = self._raw()
        return PRESET_NONE if raw is None else self._presets.get(raw, PRESET_NONE)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Write a target in whole degrees."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        value = round(temperature)
        if not self.min_temp <= value <= self.max_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="value_out_of_range",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(self.min_temp),
                    "maximum": str(self.max_temp),
                },
            )
        await self.coordinator.async_write_register(self._register, value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Write the special value of a preset, or the last target."""
        if preset_mode == PRESET_NONE:
            value = self._last_target or self._default_target
        else:
            value = next(
                raw for raw, name in self._presets.items() if name == preset_mode
            )
        await self.coordinator.async_write_register(self._register, value)


class RavelliPowerClimate(RavelliSetpointClimate):
    """Thermostat whose mode is the on/off state of the stove."""

    @property
    def hvac_mode(self) -> HVACMode:
        """Return heat while the stove runs or is about to."""
        return HVACMode.HEAT if self.coordinator.data.state.is_on else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the stove on or off."""
        await self.coordinator.async_set_power(hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self) -> None:
        """Turn the stove on."""
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        """Turn the stove off."""
        await self.coordinator.async_set_power(False)


class RavelliStoveClimate(RavelliPowerClimate):
    """The stove: ambient target, power level and manual mode."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_fan_modes = ["1", "2", "3", "4", "5"]
    _attr_min_temp = 5
    _attr_max_temp = 40
    _attr_precision = PRECISION_HALVES
    _register = REG_SETPOINT
    _presets = {MANUAL_SETPOINT: PRESET_MANUAL}

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the thermostat of the stove."""
        super().__init__(coordinator, "stove")

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return what the stove is doing."""
        return HVAC_ACTIONS.get(self.coordinator.data.state.status_code)

    @property
    def current_temperature(self) -> float | None:
        """Return the ambient temperature."""
        return self.coordinator.data.state.ambient_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return the power level as a fan mode."""
        power = self.coordinator.data.state.power
        return None if power is None else str(power)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Write the power level."""
        await self.coordinator.async_write_register(REG_POWER, int(fan_mode))
```

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
]
```

with

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_climate.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add stove thermostat"
git checkout main
git merge --ff-only feature/climate-stove
git branch -d feature/climate-stove
```

---

### Task 12: Ducting and water thermostats

**Branch:** `feature/climate-zones`

**Files:**
- Modify: `custom_components/ravelli_smart_wifi/climate.py`
- Test: `tests/test_climate_zones.py`

**Interfaces:**
- Consumes from Task 11: `RavelliSetpointClimate`, `RavelliPowerClimate`, `PRESET_MANUAL`; from `models.py`: `DUCT_OFF`, `DUCT_EXTERNAL`, `WATER_MANUAL_SETPOINT`, `REG_DUCT_RIGHT_SETPOINT`, `REG_DUCT_LEFT_SETPOINT`, `REG_DUCT_RIGHT_TEMP`, `REG_DUCT_LEFT_TEMP`, `REG_WATER_SETPOINT`; `StoveModel.has_ducting`, `StoveModel.has_water`; `StoveState.water_temperature`.
- Produces in `climate.py`: `PRESET_EXTERNAL = "external_thermostat"`, `DUCTS: dict[str, tuple[int, int]]` (key to set point register and temperature register), `RavelliDuctClimate(coordinator, key)` for the keys `duct_right` and `duct_left`, `RavelliWaterClimate(coordinator)` for the key `water`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/climate-zones
```

- [ ] **Step 2: Write the failing tests**

`tests/test_climate_zones.py`:

```python
"""Tests for the ducting and water thermostats."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, PATH_GET, PATH_SET, FakeModule
from .helpers import entity_id_for


async def setup_model(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, model: int
) -> FakeModule:
    """Set the integration up against a stove of another model."""
    module = FakeModule(model=model)
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli",
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: model, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return module


def climate(hass: HomeAssistant, key: str) -> State:
    """Return the state of one thermostat."""
    state = hass.states.get(entity_id_for(hass, "climate", key))
    assert state is not None
    return state


def exists(hass: HomeAssistant, key: str) -> bool:
    """Tell whether a thermostat was created."""
    registry = er.async_get(hass)
    return registry.async_get_entity_id("climate", DOMAIN, f"{MAC}_{key}") is not None


async def call(hass: HomeAssistant, key: str, action: str, **data: Any) -> None:
    """Call a climate action on one thermostat."""
    await hass.services.async_call(
        "climate",
        action,
        {"entity_id": entity_id_for(hass, "climate", key), **data},
        blocking=True,
    )


@pytest.mark.parametrize("key", ["duct_right", "duct_left"])
async def test_ducting_is_off_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, key: str
) -> None:
    """The module does not tell whether the stove has ducting."""
    entity_id = entity_id_for(hass, "climate", key)

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_that_is_off(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Raw 5 is off; raw 0 is a probe without a reading."""
    state = climate(hass, "duct_right")

    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["heat", "off"]
    assert state.attributes["temperature"] is None
    assert state.attributes["current_temperature"] is None
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 41
    assert state.attributes["preset_mode"] == "none"
    assert state.attributes["preset_modes"] == ["none", "external_thermostat"]
    assert "fan_modes" not in state.attributes
    assert "hvac_action" not in state.attributes


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_in_use(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Right at 22 degrees, left on the external thermostat."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 6}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    right = climate(hass, "duct_right")
    assert right.state == "heat"
    assert right.attributes["temperature"] == 22
    assert right.attributes["current_temperature"] == 21
    assert right.attributes["preset_mode"] == "none"

    left = climate(hass, "duct_left")
    assert left.state == "heat"
    assert left.attributes["temperature"] is None
    assert left.attributes["current_temperature"] == 19
    assert left.attributes["preset_mode"] == "external_thermostat"


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_commands(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Off writes 5, the external thermostat writes 6, on restores the target."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 22}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "duct_right", "set_temperature", temperature=24)
    assert fake_module.categories[6][184] == 24
    assert fake_module.categories[6][185] == 22

    await call(hass, "duct_right", "turn_off")
    assert fake_module.categories[6][184] == 5
    assert climate(hass, "duct_right").state == "off"

    await call(hass, "duct_right", "turn_on")
    assert fake_module.categories[6][184] == 24

    await call(hass, "duct_left", "set_preset_mode", preset_mode="external_thermostat")
    assert fake_module.categories[6][185] == 6

    await call(hass, "duct_left", "set_preset_mode", preset_mode="none")
    assert fake_module.categories[6][185] == 22

    await call(hass, "duct_left", "set_hvac_mode", hvac_mode="off")
    assert fake_module.categories[6][185] == 5

    await call(hass, "duct_left", "set_hvac_mode", hvac_mode="heat")
    assert fake_module.categories[6][185] == 22


@pytest.mark.usefixtures("enable_all_entities")
async def test_turning_on_ducting_that_is_on_writes_nothing(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Turning on must not replace the external thermostat by a temperature."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 6}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "duct_left", "turn_on")

    assert fake_module.count(PATH_SET) == 0
    assert fake_module.categories[6][185] == 6


@pytest.mark.usefixtures("enable_all_entities")
async def test_turning_on_ducting_without_a_known_target(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Ducting found off starts at 20 degrees."""
    await call(hass, "duct_right", "turn_on")

    assert fake_module.categories[6][184] == 20


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize("asked", [6, 42])
async def test_ducting_temperature_outside_the_bounds(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: int,
) -> None:
    """5 and 6 are modes; the temperatures start at 7."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "duct_right", "set_temperature", temperature=asked)

    assert fake_module.count(PATH_SET) == 0


@pytest.mark.usefixtures("enable_all_entities")
async def test_stove_without_ducting_or_water(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """ECO-RDS has the stove thermostat only."""
    await setup_model(hass, aioclient_mock, 12)

    assert exists(hass, "stove")
    assert not exists(hass, "duct_right")
    assert not exists(hass, "duct_left")
    assert not exists(hass, "water")


@pytest.mark.usefixtures("enable_all_entities")
async def test_water_thermostat(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """HYDRO-RDS adds a water target and has no ducting."""
    module = await setup_model(hass, aioclient_mock, 11)

    assert exists(hass, "stove")
    assert not exists(hass, "duct_right")
    state = climate(hass, "water")
    assert state.state == "off"
    assert state.attributes["temperature"] == 60
    assert state.attributes["current_temperature"] == 45
    assert state.attributes["min_temp"] == 30
    assert state.attributes["max_temp"] == 80
    assert state.attributes["preset_modes"] == ["none", "manual"]

    await call(hass, "water", "set_temperature", temperature=65)
    assert module.categories[2][49] == 65

    await call(hass, "water", "set_preset_mode", preset_mode="manual")
    assert module.categories[2][49] == 81
    assert climate(hass, "water").attributes["temperature"] is None

    await call(hass, "water", "set_preset_mode", preset_mode="none")
    assert module.categories[2][49] == 65

    await call(hass, "water", "turn_on")
    assert module.count(PATH_GET, key="022", status="1") == 1
    assert climate(hass, "water").state == "heat"
    assert climate(hass, "stove").state == "heat"


@pytest.mark.usefixtures("enable_all_entities")
async def test_water_leaves_manual_mode_without_a_known_target(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """20 degrees is below the water range: the default is 60."""
    module = FakeModule(model=11)
    module.categories[2][49] = 81
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: 11, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "water", "set_preset_mode", preset_mode="none")

    assert module.categories[2][49] == 60
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_climate_zones.py -v`
Expected: `test_stove_without_ducting_or_water` passes; every other test fails with `AssertionError: no climate entity for ...`.

- [ ] **Step 4: Write the implementation**

In `custom_components/ravelli_smart_wifi/climate.py`, replace the import

```python
from .models import MANUAL_SETPOINT, REG_POWER, REG_SETPOINT
```

with

```python
from .models import (
    DUCT_EXTERNAL,
    DUCT_OFF,
    MANUAL_SETPOINT,
    REG_DUCT_LEFT_SETPOINT,
    REG_DUCT_LEFT_TEMP,
    REG_DUCT_RIGHT_SETPOINT,
    REG_DUCT_RIGHT_TEMP,
    REG_POWER,
    REG_SETPOINT,
    REG_WATER_SETPOINT,
    WATER_MANUAL_SETPOINT,
)
```

Replace

```python
PRESET_MANUAL = "manual"
```

with

```python
PRESET_MANUAL = "manual"
PRESET_EXTERNAL = "external_thermostat"

# Key of the entity: set point register, temperature register.
DUCTS: dict[str, tuple[int, int]] = {
    "duct_right": (REG_DUCT_RIGHT_SETPOINT, REG_DUCT_RIGHT_TEMP),
    "duct_left": (REG_DUCT_LEFT_SETPOINT, REG_DUCT_LEFT_TEMP),
}
```

Replace the body of `async_setup_entry`

```python
    """Create the thermostats of one stove."""
    async_add_entities([RavelliStoveClimate(entry.runtime_data)])
```

with

```python
    """Create the thermostats the stove model has."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = [RavelliStoveClimate(coordinator)]
    if coordinator.model.has_ducting:
        entities.extend(RavelliDuctClimate(coordinator, key) for key in DUCTS)
    if coordinator.model.has_water:
        entities.append(RavelliWaterClimate(coordinator))
    async_add_entities(entities)
```

Append at the end of the file:

```python
class RavelliDuctClimate(RavelliSetpointClimate):
    """One ducted air outlet; the module cannot tell whether it is fitted."""

    _attr_entity_registry_enabled_default = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 7
    _attr_max_temp = 41
    _presets = {DUCT_EXTERNAL: PRESET_EXTERNAL}

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Pick the registers of the right or of the left outlet."""
        self._register, self._temperature_register = DUCTS[key]
        super().__init__(coordinator, key)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return off for the raw value 5."""
        raw = self._raw()
        return HVACMode.OFF if raw is None or raw == DUCT_OFF else HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the temperature of the outlet, None without a reading."""
        return self.coordinator.data.state.raw(self._temperature_register) or None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the outlet off, or back on at its last target."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(self._register, DUCT_OFF)
        elif self.hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(
                self._register, self._last_target or self._default_target
            )

    async def async_turn_on(self) -> None:
        """Turn the outlet on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the outlet off."""
        await self.async_set_hvac_mode(HVACMode.OFF)


class RavelliWaterClimate(RavelliPowerClimate):
    """Water circuit of a hydro stove."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 30
    _attr_max_temp = 80
    _register = REG_WATER_SETPOINT
    _presets = {WATER_MANUAL_SETPOINT: PRESET_MANUAL}
    _default_target = 60

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the thermostat of the water circuit."""
        super().__init__(coordinator, "water")

    @property
    def current_temperature(self) -> float | None:
        """Return the water temperature."""
        return self.coordinator.data.state.water_temperature
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_climate_zones.py tests/test_climate.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add ducting and water thermostats"
git checkout main
git merge --ff-only feature/climate-zones
git branch -d feature/climate-zones
```

---

### Task 13: Schedule switch and clock button

**Branch:** `feature/switch-button`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/switch.py`
- Create: `custom_components/ravelli_smart_wifi/button.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py` (the `PLATFORMS` list)
- Test: `tests/test_switch.py`, `tests/test_button.py`

**Interfaces:**
- Consumes: `RavelliEntity`; `RavelliCoordinator.async_set_schedule_enabled(enabled: bool)` and `async_sync_clock()`; `RavelliData.schedule.enabled`.
- Produces: the switch with the key `schedule` and the button with the key `sync_clock`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/switch-button
```

- [ ] **Step 2: Write the failing tests**

`tests/test_switch.py`:

```python
"""Tests for the schedule switch."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .fake_module import FakeModule
from .helpers import entity_id_for

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]


async def turn(hass: HomeAssistant, action: str) -> None:
    """Flip the switch."""
    await hass.services.async_call(
        "switch",
        action,
        {"entity_id": entity_id_for(hass, "switch", "schedule")},
        blocking=True,
    )


async def test_switch_flips_the_global_flag(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The programs travel with the flag and come back unchanged."""
    entity_id = entity_id_for(hass, "switch", "schedule")
    assert hass.states.get(entity_id).state == STATE_ON
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category is EntityCategory.CONFIG

    await turn(hass, "turn_off")

    assert fake_module.schedule_enabled is False
    assert fake_module.programs[0] == EVENING_RAW
    assert hass.states.get(entity_id).state == STATE_OFF

    await turn(hass, "turn_on")

    assert fake_module.schedule_enabled is True
    assert fake_module.programs[0] == EVENING_RAW
    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_reports_a_write_the_module_ignored(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The switch does not show a state the stove does not have."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await turn(hass, "turn_off")

    assert err.value.translation_key == "schedule_mismatch"
    state = hass.states.get(entity_id_for(hass, "switch", "schedule"))
    assert state.state == STATE_ON
```

`tests/test_button.py`:

```python
"""Tests for the clock button."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fake_module import PATH_SET, FakeModule
from .helpers import entity_id_for


@pytest.mark.freeze_time("2026-09-29T16:57:30+00:00")
async def test_button_sets_the_clock_to_local_time(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """16:57 UTC on a Tuesday is 18:57 in Paris."""
    await hass.config.async_set_time_zone("Europe/Paris")
    fake_module.categories[4] = dict.fromkeys(range(59, 65), 0)
    entity_id = entity_id_for(hass, "button", "sync_clock")
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category is EntityCategory.CONFIG

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    assert fake_module.categories[4] == {
        59: 2,
        60: 0x18,
        61: 0x57,
        62: 0x29,
        63: 0x09,
        64: 0x26,
    }
    assert fake_module.count(PATH_SET) == 6
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_switch.py tests/test_button.py -v`
Expected: every test fails with `AssertionError: no switch entity for schedule` or `no button entity for sync_clock`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/switch.py`:

```python
"""Switch platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the switch of one stove."""
    async_add_entities([RavelliScheduleSwitch(entry.runtime_data)])


class RavelliScheduleSwitch(RavelliEntity, SwitchEntity):
    """Global switch of the schedule stored in the stove."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the switch."""
        super().__init__(coordinator, "schedule")

    @property
    def is_on(self) -> bool:
        """Return whether the stove follows its programs."""
        return self.coordinator.data.schedule.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Make the stove follow its programs."""
        await self.coordinator.async_set_schedule_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Make the stove ignore its programs."""
        await self.coordinator.async_set_schedule_enabled(False)
```

`custom_components/ravelli_smart_wifi/button.py`:

```python
"""Button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the button of one stove."""
    async_add_entities([RavelliSyncClockButton(entry.runtime_data)])


class RavelliSyncClockButton(RavelliEntity, ButtonEntity):
    """Sets the clock of the stove, which its schedule relies on."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the button."""
        super().__init__(coordinator, "sync_clock")

    async def async_press(self) -> None:
        """Write the local time of Home Assistant to the stove."""
        await self.coordinator.async_sync_clock()
```

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
]
```

with

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_switch.py tests/test_button.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add schedule switch and clock button"
git checkout main
git merge --ff-only feature/switch-button
git branch -d feature/switch-button
```

---

### Task 14: Schedule actions and calendar

**Branch:** `feature/schedule-actions`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/services.py`
- Create: `custom_components/ravelli_smart_wifi/services.yaml`
- Create: `custom_components/ravelli_smart_wifi/calendar.py`
- Modify: `custom_components/ravelli_smart_wifi/__init__.py`
- Test: `tests/test_services.py`, `tests/test_calendar.py`

**Interfaces:**
- Consumes: `RavelliCoordinator.async_set_program(slot: int, program: ScheduleProgram)` and `async_delete_program(slot: int)`; `ScheduleProgram`, `Schedule`, `WEEKDAYS`, `SLOT_COUNT`, `NAME_MAX_LENGTH`, `MANUAL_SETPOINT` from `models.py`; `RavelliEntity`; `DOMAIN`.
- Produces in `services.py`: `SERVICE_SET_PROGRAM = "set_schedule_program"`, `SERVICE_DELETE_PROGRAM = "delete_schedule_program"` and `async_setup_services(hass) -> None`.
- Produces in `calendar.py`: `schedule_events(schedule: Schedule, start: datetime, end: datetime) -> list[CalendarEvent]` and the calendar with the key `schedule`.
- Produces in `__init__.py`: `async_setup(hass, config) -> bool`, which registers the two actions once, and `CONFIG_SCHEMA`.
- Action fields: `device_id` (str, required), `slot` (1 to 6, required), `name` (1 to 15 characters, required), `enabled` (bool, default true), `start` and `end` (time, optional), `temperature` (5 to 40, optional), `manual` (bool, default false), `power` (1 to 5, required), `weekdays` (list of `mon` to `sun`, at least one, required). The delete action takes `device_id` and `slot`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/schedule-actions
```

- [ ] **Step 2: Write the failing tests of the actions**

`tests/test_services.py`:

```python
"""Tests for the schedule actions."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import FREE_PROGRAM, MAC, PATH_GET, FakeModule

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
MORNING_RAW = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]
MORNING: dict[str, Any] = {
    "slot": 2,
    "name": "Morning",
    "start": "06:30:00",
    "end": "08:00:00",
    "temperature": 21,
    "power": 3,
    "weekdays": ["mon", "tue", "wed", "thu", "fri"],
}


def stove_id(hass: HomeAssistant) -> str:
    """Return the device id of the stove."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})
    assert device is not None
    return device.id


async def set_program(hass: HomeAssistant, **changes: Any) -> None:
    """Store the morning program, with changes; None removes a field."""
    data = {"device_id": stove_id(hass), **MORNING, **changes}
    await hass.services.async_call(
        DOMAIN,
        "set_schedule_program",
        {key: value for key, value in data.items() if value is not None},
        blocking=True,
    )


async def delete_program(hass: HomeAssistant, slot: int) -> None:
    """Free one slot."""
    await hass.services.async_call(
        DOMAIN,
        "delete_schedule_program",
        {"device_id": stove_id(hass), "slot": slot},
        blocking=True,
    )


async def test_set_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The program is stored and the other slots are kept."""
    await set_program(hass)

    assert fake_module.programs[0] == EVENING_RAW
    assert fake_module.programs[1] == MORNING_RAW
    assert fake_module.programs[2] == FREE_PROGRAM
    schedule = init_integration.runtime_data.data.schedule
    assert schedule.programs[1].name == "Morning"


async def test_replacing_a_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Writing to a used slot replaces its program."""
    await set_program(hass, slot=1)

    assert fake_module.programs[0] == MORNING_RAW


@pytest.mark.parametrize(
    ("changes", "row"),
    [
        ({"enabled": False}, [0, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]),
        ({"end": None}, [1, 1, 6, 2, 0, 0, 0, 21, 3, 31, "Morning"]),
        ({"start": None}, [1, 0, 0, 0, 1, 8, 0, 21, 3, 31, "Morning"]),
        ({"start": "06:30"}, MORNING_RAW),
        (
            {"manual": True, "temperature": None},
            [1, 1, 6, 2, 1, 8, 0, 41, 3, 31, "Morning"],
        ),
        ({"manual": True}, [1, 1, 6, 2, 1, 8, 0, 41, 3, 31, "Morning"]),
        ({"weekdays": "sun"}, [1, 1, 6, 2, 1, 8, 0, 21, 3, 64, "Morning"]),
        ({"name": "A & B = C"}, [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "A & B = C"]),
    ],
)
async def test_program_variants(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
    row: list[Any],
) -> None:
    """Optional fields, manual mode and separators in the name."""
    await set_program(hass, **changes)

    assert fake_module.programs[1] == row
    assert fake_module.programs[0] == EVENING_RAW


@pytest.mark.parametrize(
    ("changes", "key"),
    [
        ({"temperature": None}, "temperature_required"),
        ({"name": "Café"}, "schedule_name_characters"),
        ({"end": "06:30:00"}, "schedule_end_before_start"),
        ({"end": "06:00:00"}, "schedule_end_before_start"),
        ({"start": "06:10:00"}, "schedule_time_step"),
        ({"start": None, "end": None}, "schedule_no_time"),
    ],
)
async def test_programs_that_break_a_rule(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
    key: str,
) -> None:
    """Each rule has its own message and nothing is sent."""
    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, **changes)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == key
    assert fake_module.count(PATH_GET, key="032") == 0
    assert fake_module.programs[1] == FREE_PROGRAM


@pytest.mark.parametrize(
    "changes",
    [
        {"slot": 0},
        {"slot": 7},
        {"name": ""},
        {"name": "x" * 16},
        {"temperature": 4},
        {"temperature": 41},
        {"power": 0},
        {"power": 6},
        {"weekdays": []},
        {"weekdays": ["mon", "someday"]},
        {"start": "25:00:00"},
        {"device_id": None},
    ],
)
async def test_fields_outside_the_schema(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
) -> None:
    """The schema of the action refuses them before any code runs."""
    data = {"device_id": stove_id(hass), **MORNING, **changes}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule_program",
            {key: value for key, value in data.items() if value is not None},
            blocking=True,
        )

    assert fake_module.count(PATH_GET, key="032") == 0


async def test_delete_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The slot is freed on the module and in the state."""
    await delete_program(hass, 1)

    assert fake_module.programs[0] == FREE_PROGRAM
    assert init_integration.runtime_data.data.schedule.programs[0] is None


async def test_write_the_module_ignored(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The read-back catches a module that answers yes and stores nothing."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await set_program(hass)

    assert err.value.translation_key == "schedule_mismatch"


async def test_unknown_device(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A device id that does not exist is refused."""
    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, device_id="not-a-device")

    assert err.value.translation_key == "device_not_found"


async def test_device_of_an_unloaded_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A stove that is not loaded has no coordinator to talk to."""
    device_id = stove_id(hass)
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, device_id=device_id)

    assert err.value.translation_key == "device_not_found"
```

- [ ] **Step 3: Write the failing tests of the calendar**

`tests/test_calendar.py`:

```python
"""Tests for the schedule calendar."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC, FakeModule
from .helpers import entity_id_for

MONDAY = "2026-09-28T00:00:00+02:00"
NEXT_MONDAY = "2026-10-05T00:00:00+02:00"


@pytest.fixture(autouse=True)
async def paris(hass: HomeAssistant) -> None:
    """Run every test in a time zone that is not UTC."""
    await hass.config.async_set_time_zone("Europe/Paris")


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up after the module was prepared."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def events(
    hass: HomeAssistant, start: str = MONDAY, end: str = NEXT_MONDAY
) -> list[dict[str, Any]]:
    """Ask the calendar for the events of a window."""
    entity_id = entity_id_for(hass, "calendar", "schedule")
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[entity_id]["events"]


async def test_week_of_a_daily_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The evening program runs every day from 18:00 to 22:30."""
    found = await events(hass)

    assert len(found) == 7
    assert found[0]["summary"] == "Evening"
    assert found[0]["start"] == "2026-09-28T18:00:00+02:00"
    assert found[0]["end"] == "2026-09-28T22:30:00+02:00"
    assert found[0]["description"] == "22 °C, power 1"
    assert found[6]["start"] == "2026-10-04T18:00:00+02:00"


async def test_programs_follow_their_weekdays(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A weekday program has five events, sorted with the others by start."""
    fake_module.programs[1] = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]
    await setup(hass, config_entry)

    found = await events(hass)

    assert len(found) == 12
    assert [event["summary"] for event in found[:3]] == [
        "Morning",
        "Evening",
        "Morning",
    ]
    assert found[0]["start"] == "2026-09-28T06:30:00+02:00"
    assert found[0]["end"] == "2026-09-28T08:00:00+02:00"
    assert [event["summary"] for event in found[-2:]] == ["Evening", "Evening"]


@pytest.mark.parametrize(
    ("row", "start", "end", "description"),
    [
        (
            [1, 1, 18, 0, 0, 0, 0, 22, 1, 127, "Evening"],
            "2026-09-28T18:00:00+02:00",
            "2026-09-28T18:15:00+02:00",
            "22 °C, power 1, start only",
        ),
        (
            [1, 0, 0, 0, 1, 22, 2, 22, 1, 127, "Evening"],
            "2026-09-28T22:30:00+02:00",
            "2026-09-28T22:45:00+02:00",
            "22 °C, power 1, stop only",
        ),
        (
            [1, 1, 18, 0, 1, 22, 2, 41, 4, 127, "Evening"],
            "2026-09-28T18:00:00+02:00",
            "2026-09-28T22:30:00+02:00",
            "manual, power 4",
        ),
    ],
)
async def test_event_shapes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    row: list[Any],
    start: str,
    end: str,
    description: str,
) -> None:
    """A program with one time lasts a quarter of an hour in the calendar."""
    fake_module.programs[0] = row
    await setup(hass, config_entry)

    found = await events(hass)

    assert len(found) == 7
    assert found[0]["start"] == start
    assert found[0]["end"] == end
    assert found[0]["description"] == description


async def test_disabled_program_has_no_events(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The stove ignores it, so the calendar does too."""
    fake_module.programs[0][0] = 0
    await setup(hass, config_entry)

    assert await events(hass) == []


async def test_disabled_schedule_has_no_events(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The global switch empties the calendar."""
    fake_module.schedule_enabled = False
    await setup(hass, config_entry)

    assert await events(hass) == []
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))
    assert state.state == STATE_OFF


async def test_window_that_starts_during_an_event(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An event that is under way belongs to the window."""
    found = await events(
        hass, start="2026-09-28T20:00:00+02:00", end="2026-09-29T12:00:00+02:00"
    )

    assert [event["start"] for event in found] == ["2026-09-28T18:00:00+02:00"]


async def test_window_given_in_another_time_zone(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The programs are in local time whatever the window is expressed in."""
    found = await events(
        hass, start="2026-09-28T15:00:00+00:00", end="2026-09-28T17:00:00+00:00"
    )

    assert [event["start"] for event in found] == ["2026-09-28T18:00:00+02:00"]


@pytest.mark.freeze_time("2026-09-29T17:00:00+00:00")
async def test_calendar_is_on_during_a_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """19:00 in Paris is inside the evening program."""
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))

    assert state.state == STATE_ON
    assert state.attributes["message"] == "Evening"
    assert state.attributes["start_time"] == "2026-09-29 18:00:00"
    assert state.attributes["end_time"] == "2026-09-29 22:30:00"


@pytest.mark.freeze_time("2026-09-29T08:00:00+00:00")
async def test_calendar_announces_the_next_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """10:00 in Paris is before the evening program."""
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))

    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Evening"
    assert state.attributes["start_time"] == "2026-09-29 18:00:00"


async def test_calendar_follows_the_actions(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A program stored by the action shows without waiting for a poll."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})
    assert device is not None
    await hass.services.async_call(
        DOMAIN,
        "set_schedule_program",
        {
            "device_id": device.id,
            "slot": 2,
            "name": "Morning",
            "start": "06:30:00",
            "end": "08:00:00",
            "temperature": 21,
            "power": 3,
            "weekdays": ["sat"],
        },
        blocking=True,
    )

    found = await events(hass)

    assert len(found) == 8
    assert [event["summary"] for event in found].count("Morning") == 1
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services.py tests/test_calendar.py -v`
Expected: the action tests fail with `ServiceNotFound`, and the calendar tests fail with `AssertionError: no calendar entity for schedule`.

- [ ] **Step 5: Write the actions**

`custom_components/ravelli_smart_wifi/services.py`:

```python
"""Actions that edit the schedule stored in the stove."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import RavelliCoordinator
from .models import (
    MANUAL_SETPOINT,
    NAME_MAX_LENGTH,
    SLOT_COUNT,
    WEEKDAYS,
    ScheduleProgram,
)

SERVICE_SET_PROGRAM = "set_schedule_program"
SERVICE_DELETE_PROGRAM = "delete_schedule_program"

ATTR_SLOT = "slot"
ATTR_ENABLED = "enabled"
ATTR_START = "start"
ATTR_END = "end"
ATTR_MANUAL = "manual"
ATTR_POWER = "power"
ATTR_WEEKDAYS = "weekdays"

_SLOT = vol.All(vol.Coerce(int), vol.Range(min=1, max=SLOT_COUNT))

SET_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_SLOT): _SLOT,
        vol.Required(ATTR_NAME): vol.All(
            cv.string, vol.Length(min=1, max=NAME_MAX_LENGTH)
        ),
        vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
        vol.Optional(ATTR_START): cv.time,
        vol.Optional(ATTR_END): cv.time,
        vol.Optional(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=MANUAL_SETPOINT - 1)
        ),
        vol.Optional(ATTR_MANUAL, default=False): cv.boolean,
        vol.Required(ATTR_POWER): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        vol.Required(ATTR_WEEKDAYS): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(WEEKDAYS)]
        ),
    }
)

DELETE_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_SLOT): _SLOT}
)


def _coordinator(hass: HomeAssistant, device_id: str) -> RavelliCoordinator:
    """Return the coordinator of a stove that is loaded."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and entry.state is ConfigEntryState.LOADED
            ):
                return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="device_not_found"
    )


async def _async_set_program(call: ServiceCall) -> None:
    """Store one program."""
    data = call.data
    if data[ATTR_MANUAL]:
        temperature = MANUAL_SETPOINT
    elif ATTR_TEMPERATURE in data:
        temperature = data[ATTR_TEMPERATURE]
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="temperature_required"
        )
    program = ScheduleProgram(
        name=data[ATTR_NAME],
        enabled=data[ATTR_ENABLED],
        start=data.get(ATTR_START),
        end=data.get(ATTR_END),
        temperature=temperature,
        power=data[ATTR_POWER],
        weekdays=frozenset(data[ATTR_WEEKDAYS]),
    )
    coordinator = _coordinator(call.hass, data[ATTR_DEVICE_ID])
    await coordinator.async_set_program(data[ATTR_SLOT], program)


async def _async_delete_program(call: ServiceCall) -> None:
    """Free one slot."""
    coordinator = _coordinator(call.hass, call.data[ATTR_DEVICE_ID])
    await coordinator.async_delete_program(call.data[ATTR_SLOT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions of the integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PROGRAM, _async_set_program, schema=SET_PROGRAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PROGRAM,
        _async_delete_program,
        schema=DELETE_PROGRAM_SCHEMA,
    )
```

`custom_components/ravelli_smart_wifi/services.yaml`:

```yaml
set_schedule_program:
  fields:
    device_id:
      required: true
      selector:
        device:
          integration: ravelli_smart_wifi
    slot:
      required: true
      selector:
        number:
          min: 1
          max: 6
          mode: box
    name:
      required: true
      selector:
        text:
    enabled:
      default: true
      selector:
        boolean:
    start:
      selector:
        time:
    end:
      selector:
        time:
    temperature:
      selector:
        number:
          min: 5
          max: 40
          unit_of_measurement: "°C"
    manual:
      default: false
      selector:
        boolean:
    power:
      required: true
      selector:
        number:
          min: 1
          max: 5
    weekdays:
      required: true
      selector:
        select:
          multiple: true
          translation_key: weekday
          options:
            - mon
            - tue
            - wed
            - thu
            - fri
            - sat
            - sun

delete_schedule_program:
  fields:
    device_id:
      required: true
      selector:
        device:
          integration: ravelli_smart_wifi
    slot:
      required: true
      selector:
        number:
          min: 1
          max: 6
          mode: box
```

- [ ] **Step 6: Write the calendar**

`custom_components/ravelli_smart_wifi/calendar.py`:

```python
"""Calendar platform: a read-only view of the schedule of the stove."""

from __future__ import annotations

from datetime import date, datetime, timedelta, tzinfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import MANUAL_SETPOINT, WEEKDAYS, Schedule, ScheduleProgram

# Length given to a program that only starts or only stops the stove.
SINGLE_TIME_LENGTH = timedelta(minutes=15)
# How far the entity looks for its next event: a week and a day.
LOOKAHEAD = timedelta(days=8)


def _event(program: ScheduleProgram, day: date, zone: tzinfo) -> CalendarEvent | None:
    """Return the event of a program on one day."""
    first = program.start or program.end
    if first is None:
        return None
    begin = datetime.combine(day, first, zone)
    if program.start is not None and program.end is not None:
        finish = datetime.combine(day, program.end, zone)
        note = ""
    else:
        finish = begin + SINGLE_TIME_LENGTH
        note = ", start only" if program.start is not None else ", stop only"
    target = (
        "manual"
        if program.temperature == MANUAL_SETPOINT
        else f"{program.temperature} °C"
    )
    return CalendarEvent(
        start=begin,
        end=finish,
        summary=program.name,
        description=f"{target}, power {program.power}{note}",
    )


def schedule_events(
    schedule: Schedule, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Return the events of the schedule that overlap a window."""
    if not schedule.enabled:
        return []
    start = dt_util.as_local(start)
    end = dt_util.as_local(end)
    zone = start.tzinfo
    assert zone is not None
    events: list[CalendarEvent] = []
    day = start.date()
    while day <= end.date():
        weekday = WEEKDAYS[day.weekday()]
        for program in schedule.programs:
            if program is None or not program.enabled:
                continue
            if weekday not in program.weekdays:
                continue
            event = _event(program, day, zone)
            if event is not None and event.end > start and event.start < end:
                events.append(event)
        day += timedelta(days=1)
    return sorted(events, key=lambda event: event.start)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the calendar of one stove."""
    async_add_entities([RavelliScheduleCalendar(entry.runtime_data)])


class RavelliScheduleCalendar(RavelliEntity, CalendarEntity):
    """Shows when the stove will run by itself."""

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the calendar."""
        super().__init__(coordinator, "schedule")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the event under way, or the next one."""
        now = dt_util.now()
        events = schedule_events(
            self.coordinator.data.schedule, now, now + LOOKAHEAD
        )
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events of a window."""
        return schedule_events(self.coordinator.data.schedule, start_date, end_date)
```

- [ ] **Step 7: Register the actions and the platform**

In `custom_components/ravelli_smart_wifi/__init__.py`, replace

```python
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WinetClient, WinetError
from .const import DOMAIN, ISSUE_URL
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .models import SUPPORTED_MODELS
```

with

```python
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import WinetClient, WinetError
from .const import DOMAIN, ISSUE_URL
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .models import SUPPORTED_MODELS
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
```

Replace

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
```

with

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, whatever the number of stoves."""
    async_setup_services(hass)
    return True
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services.py tests/test_calendar.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 9: Commit and integrate**

```bash
git add -A
git commit -m "feat: add schedule actions and read-only calendar"
git checkout main
git merge --ff-only feature/schedule-actions
git branch -d feature/schedule-actions
```

---

### Task 15: Diagnostics

**Branch:** `feature/diagnostics`

**Files:**
- Create: `custom_components/ravelli_smart_wifi/diagnostics.py`
- Test: `tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `RavelliCoordinator.async_read_diagnostics() -> dict[str, Any]` with the keys `system`, `categories` and `schedule`; `RavelliCoordinator.model`; `WinetError` from `api.py`.
- Produces: `async_get_config_entry_diagnostics(hass, entry) -> dict[str, Any]` with the keys `entry`, `model`, and either `system`, `categories` and `schedule`, or `error`.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/diagnostics
```

- [ ] **Step 2: Write the failing tests**

`tests/test_diagnostics.py`:

```python
"""Tests for the diagnostics download."""

import json

import aiohttp
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from custom_components.ravelli_smart_wifi.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .fake_module import HOST, MAC, FakeModule

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

    assert result["error"] == "WinetConnectionError"
    assert result["model"] == "AIR-RDS"
    assert "system" not in result
    assert HOST not in json.dumps(result, default=str)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_diagnostics.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'custom_components.ravelli_smart_wifi.diagnostics'`.

- [ ] **Step 4: Write the implementation**

`custom_components/ravelli_smart_wifi/diagnostics.py`:

```python
"""Diagnostics download."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .api import WinetError
from .coordinator import RavelliConfigEntry

REDACT_ENTRY = {CONF_HOST, CONF_MAC, "unique_id"}
REDACT_SYSTEM = {
    "network",
    "currentIp",
    "currentMask",
    "currentGw",
    "currentApIp",
    "eNowDevs",
}
REDACT_CATEGORY = {"name", "tsense"}
_NAME = 10


def _redact_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    """Hide the program names: they are free text typed by the owner."""
    programs = [
        [*program[:_NAME], REDACTED if program[_NAME] else ""]
        for program in schedule.get("programs", [])
        if isinstance(program, list) and len(program) > _NAME
    ]
    return {**schedule, "programs": programs}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RavelliConfigEntry
) -> dict[str, Any]:
    """Dump every register category of the stove, without personal data."""
    coordinator = entry.runtime_data
    result: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), REDACT_ENTRY),
        "model": coordinator.model.name,
    }
    try:
        raw = await coordinator.async_read_diagnostics()
    except WinetError as err:
        # The message of the error can hold the address of the module.
        return {**result, "error": type(err).__name__}
    return {
        **result,
        "system": async_redact_data(raw["system"], REDACT_SYSTEM),
        "categories": {
            category: async_redact_data(payload, REDACT_CATEGORY)
            for category, payload in raw["categories"].items()
        },
        "schedule": _redact_schedule(raw["schedule"]),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_diagnostics.py -v`
Expected: both tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 6: Commit and integrate**

```bash
git add -A
git commit -m "feat: add diagnostics download"
git checkout main
git merge --ff-only feature/diagnostics
git branch -d feature/diagnostics
```

---

### Task 16: Documentation

**Branch:** `feature/documentation`

**Files:**
- Modify: `README.md` (replace the whole file)
- Create: `docs/hardware-verification.md`
- Test: `tests/test_documentation.py`

**Interfaces:**
- Consumes: the names of the entities, actions and models produced by the earlier tasks.
- Produces: the user documentation, and the checklist that Task 17 runs on a real stove.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/documentation
```

- [ ] **Step 2: Write the failing test**

`tests/test_documentation.py`:

```python
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
        "Schedule",
        "Clock",
        "DHCP hostname",
    ):
        assert point in CHECKLIST, point
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_documentation.py -v`
Expected: collection error, `FileNotFoundError` for `docs/hardware-verification.md`.

- [ ] **Step 4: Write the README**

Replace `README.md` with:

````markdown
# Ravelli Smart Wi-Fi for Home Assistant

Unofficial Home Assistant integration for Ravelli pellet stoves fitted with
the **Ravelli Smart Wi-Fi** module. It talks to the module on your local
network: no cloud account, no extra hardware.

This project is not affiliated with Ravelli or with the maker of the module.

> **Your stove uses the "Ravelli Wi-Fi" app instead?** That is another
> module. Use [Micronova Agua IOT](https://github.com/vincentwolsink/home_assistant_micronova_agua_iot).

## Supported stoves

The module reports the electronic board of the stove. Support depends on the
board, not on the commercial name of the stove.

| Board | Status |
|---|---|
| AIR-RDS | Verified on a real stove |
| HYDRO-RDS | Written from the module's own web page, not tested |
| ECO-RDS | Written from the module's own web page, not tested |
| Any other board | Refused at setup |

To find your board, open `http://<address of the module>/` in a browser: the
name is at the top of the page.

If your board is refused, open an issue and attach the output of this command,
after removing your network name from it:

```bash
curl -X POST -H "Content-Type: application/json; charset=utf-8" \
  -d "key=020&category=2" http://192.0.2.10/ajax/get-registers
```

## What you get

| Entity | What it does |
|---|---|
| Thermostat "Stove" | On and off, target temperature (5 to 40 °C), power level (1 to 5) as fan mode, manual mode as preset, and what the stove is doing |
| Thermostats "Ducting right" and "Ducting left" | Target and temperature of each ducted outlet. Disabled by default: enable them if your stove has ducting. AIR-RDS only |
| Thermostat "Water" | Water target and temperature. HYDRO-RDS only |
| Sensor "Status" | Off, ignition, working, final cleaning, alarm and so on |
| Sensor "Alarm message" and binary sensor "Alarm" | The alarm text of the stove, and whether an alarm is active |
| Sensors "Ambient temperature" and "Flue gas temperature" | In °C |
| Sensor "Extractor speed" | Raw value, disabled by default until its scale is verified |
| Sensor "Wi-Fi signal" | In dBm, disabled by default |
| Binary sensor "Firmware update" | On when the module has an update to install |
| Number "Power level" | The same power level as the fan mode of the thermostat |
| Numbers "Comfort climate delta" and "Comfort climate delay" | The comfort climate settings of the stove |
| Switch "Schedule" | Makes the stove follow or ignore the programs it stores |
| Calendar "Schedule" | Shows when the stove will run by itself |
| Button "Synchronize clock" | Sets the clock of the stove to the time of Home Assistant |

## Installation

### With HACS

1. In HACS, open the menu at the top right and choose **Custom repositories**.
2. Add `https://github.com/Greite/ha-ravelli-smart-wifi` with the type
   **Integration**.
3. Search for **Ravelli Smart Wi-Fi**, download it and restart Home Assistant.

### By hand

Copy the folder `custom_components/ravelli_smart_wifi` into the
`custom_components` folder of your Home Assistant configuration, then restart
Home Assistant.

## Setup

1. Give the module a fixed address in your router.
2. In Home Assistant, go to **Settings > Devices & services > Add
   integration** and search for **Ravelli Smart Wi-Fi**.
3. Choose **Search the local network**, or enter the address yourself.

The search covers the networks Home Assistant is connected to, up to 1022
addresses each, and can take up to a minute.

To change the address later, use **Reconfigure** on the integration: the
entities and their history are kept.

The polling interval is in the options of the integration: 30 seconds by
default, from 10 to 300.

## Schedule actions

The stove stores six programs. Two actions edit them. Use the calendar to see
the result.

### `ravelli_smart_wifi.set_schedule_program`

```yaml
action: ravelli_smart_wifi.set_schedule_program
data:
  device_id: 0123456789abcdef0123456789abcdef
  slot: 2
  name: Morning
  start: "06:30:00"
  end: "08:00:00"
  temperature: 21
  power: 3
  weekdays: [mon, tue, wed, thu, fri]
```

| Field | Rule |
|---|---|
| `slot` | 1 to 6. A used slot is replaced |
| `name` | 1 to 15 characters, without accents |
| `enabled` | Optional, true by default |
| `start`, `end` | Optional, on a quarter of an hour. Give one of them at least. `end` must be later than `start` |
| `temperature` | 5 to 40 °C. Not needed when `manual` is true |
| `manual` | Optional. Runs at the chosen power without a target temperature |
| `power` | 1 to 5 |
| `weekdays` | One or more of `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` |

### `ravelli_smart_wifi.delete_schedule_program`

```yaml
action: ravelli_smart_wifi.delete_schedule_program
data:
  device_id: 0123456789abcdef0123456789abcdef
  slot: 2
```

## Safety

- **The module has no authentication.** Any device on your local network can
  turn the stove on. This is how the module works, with or without this
  integration. Keep it on a network you trust.
- The integration refuses to turn the stove off while it is igniting and the
  flame is not established, as the module's own page does.
- The integration refuses to turn the stove on while it is in alarm. Turn it
  off first: that acknowledges the alarm.
- A command is never sent twice. When the module does not answer, you get an
  error and nothing is retried.
- Only the settings listed above are written. There is no action that writes
  an arbitrary register.

A pellet stove is a combustion appliance. Do not start it remotely unless you
know the room is safe and the stove is ready to run.

## What is not verified yet

See [docs/hardware-verification.md](docs/hardware-verification.md) for the
list of points checked on a real stove and their results.

## Troubleshooting

| Message | Meaning |
|---|---|
| Nothing answers at this address | Wrong address, stove unplugged, or module not connected to the Wi-Fi |
| A device answers, but it is not a Ravelli Smart Wi-Fi module | The address belongs to another device |
| Stove model N is not supported yet | The board is not in the table above. Open an issue with the code N |

The diagnostics download of the device holds every register of the stove.
Network name, addresses and program names are removed from it.

## Development

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

Tests run against a simulator of the module, `tests/fake_module.py`. No stove
is needed.

## Licence

MIT. See [LICENSE](LICENSE).
````

- [ ] **Step 5: Write the hardware checklist**

`docs/hardware-verification.md`:

````markdown
# Hardware verification

The tests of this project run against a simulator. The points below can only
be checked on a real stove. Each release states which of them were checked,
on which board and firmware.

Never write a network name, an address or a program name in this file.

## Before you start

- The stove is clean, filled and ready to run.
- Someone is in the room during the whole session.
- The schedule stored in the stove was saved. Read it with the command below
  and keep the output outside the repository:

  ```bash
  curl -X POST -H "Content-Type: application/json; charset=utf-8" \
    -d "key=033" http://192.0.2.10/ajax/get-registers
  ```

## Checklist

| Point | How to check | Expected |
|---|---|---|
| On and off | Turn the thermostat on, wait for the status "Working", turn it off | The stove ignites. The status goes through ignition, working, final cleaning, off. Note every status code seen in the attribute `raw_value` |
| Turn-off rule | Turn the thermostat off right after turning it on | If the stove reports a flame value, the command is refused with the ignition message |
| Flue gas temperature | Compare the sensor with the value on the display of the stove, stove working | Same value |
| Extractor speed | Enable the sensor. Compare its raw value with the speed on the display of the stove | A constant ratio between the two |
| Manual mode | Choose the preset "Manual" | The display of the stove shows its manual mode. Choosing "None" restores the previous target |
| Schedule, write | Store a program in slot 6 with the action, then open the page of the module | The program is there, with the right times, days, temperature and power. The other programs are unchanged |
| Schedule, names | On the page of the module, create a program whose name holds an accented letter, then read the schedule with the command above | Note whether the name comes back unchanged |
| Schedule, switch | Flip the switch "Schedule" off and on | The page of the module shows the same state. The programs are unchanged |
| Schedule, delete | Delete slot 6 with the action | Slot 6 is free. The other programs are unchanged |
| Clock | Press "Synchronize clock" | The display of the stove shows the time of Home Assistant |
| DHCP hostname | Unplug the stove for ten seconds, plug it back, then read the name the module announced in the list of DHCP leases of the router | Note the pattern of the name, without the part that identifies the device |

## Results

| Date | Board | Firmware | Point | Result |
|---|---|---|---|---|
````

- [ ] **Step 6: Run the checks to verify they pass**

Run: `uv run pytest tests/test_documentation.py -v`
Expected: all tests pass.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

- [ ] **Step 7: Commit and integrate**

```bash
git add -A
git commit -m "docs: add user documentation and hardware checklist"
git checkout main
git merge --ff-only feature/documentation
git branch -d feature/documentation
```

---

### Task 17: Hardware verification and first release

**Branch:** `feature/hardware-verification`

This task is done with the owner of the stove. It starts a combustion appliance and writes to its settings: every step marked **Owner approval** needs an explicit yes from the owner before it is run, given for that step.

**Files:**
- Modify: `docs/hardware-verification.md` (the results table)
- Modify: `custom_components/ravelli_smart_wifi/sensor.py` (only if step 5 finds a scale)
- Modify: `custom_components/ravelli_smart_wifi/models.py` and `tests/test_schedule.py` (only if step 6 shows that accented names work)
- Modify: `custom_components/ravelli_smart_wifi/manifest.json` and `tests/test_manifest.py` (DHCP matcher if step 7 finds one; version in step 9)
- Modify: `docs/superpowers/specs/2026-09-29-ravelli-smart-wifi-integration-design.md` (status of the verified points)

**Interfaces:**
- Consumes: everything produced by Tasks 1 to 16.
- Produces: a verified integration, tagged for its first release.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git checkout -b feature/hardware-verification
```

- [ ] **Step 2: Install on a Home Assistant instance (Owner approval)**

Copy `custom_components/ravelli_smart_wifi` into the `custom_components` folder of the configuration of the instance, restart Home Assistant, then add the integration from **Settings > Devices & services** with **Search the local network**.

Expected: the module is listed, the entry is created with the title `Ravelli AIR-RDS`, and the entities show the values of the stove.

If the instance already reads the stove through YAML `rest`, `rest_command` or `template` entries, remove those entries in the same session, and check that no automation refers to their entity ids.

- [ ] **Step 3: Save the schedule of the stove**

Run the `curl` command of `docs/hardware-verification.md` with the address of the module and keep the output in a file outside the repository.

Expected: a JSON object with `enabled` and six `programs`.

- [ ] **Step 4: Run the checklist (Owner approval)**

Go through every row of the checklist of `docs/hardware-verification.md`, in order. Add one row per point to the results table, with the date, the board, the firmware version shown on the device page, and the result. Write no address, network name or program name.

- [ ] **Step 5: Apply the scale of the extractor speed**

Skip this step if the display of the stove does not show the extractor speed, or if the ratio between the displayed speed and the raw value is not constant over three readings. Record that in the results table.

Otherwise, the ratio is the number of revolutions per minute for one raw unit. Write the failing test first, in `tests/test_sensor.py`, replacing `RATIO` by the measured ratio:

```python
RATIO = 10  # revolutions per minute for one raw unit, measured on hardware


async def test_extractor_speed_is_in_revolutions_per_minute(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The scale was measured on an AIR-RDS stove."""
    fake_module.categories[2][5] = 120

    await advance(hass, freezer)

    extractor = hass.states.get(entity_id_for(hass, "sensor", "extractor_speed"))
    assert extractor.state == str(120 * RATIO)
    assert extractor.attributes["unit_of_measurement"] == "rpm"
```

Remove the extractor assertions from `test_sensors_that_are_off_by_default` and `test_sensors_once_enabled`: the first keeps `wifi_signal` only, the second keeps the signal assertions only.

Run: `uv run pytest tests/test_sensor.py -v`
Expected: the new test fails on the state.

Then, in `custom_components/ravelli_smart_wifi/sensor.py`, add `REVOLUTIONS_PER_MINUTE` to the import from `homeassistant.const`, add the constant and the function below `ALARM_NONE`, and replace the description of the sensor:

```python
# Revolutions per minute for one raw unit, measured on an AIR-RDS stove.
EXTRACTOR_RATIO = 10


def _extractor_speed(data: RavelliData) -> int | None:
    """Return the extractor speed in revolutions per minute."""
    raw = data.state.extractor_speed
    return None if raw is None else raw * EXTRACTOR_RATIO
```

```python
    RavelliSensorDescription(
        key="extractor_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_extractor_speed,
    ),
```

Use the measured ratio for `RATIO` and `EXTRACTOR_RATIO`; 10 is the value the examples above are written with.

Run: `uv run pytest tests/test_sensor.py -v`
Expected: all tests pass.

- [ ] **Step 6: Relax the rule on program names, if the stove allows it**

Skip this step unless the row "Schedule, names" of the checklist showed that a name with an accented letter comes back unchanged from the module.

In `tests/test_schedule.py`, move `({"name": "Café"}, "name_characters")` out of `test_invalid_programs_are_refused` and add `replace(EVENING, name="Café")` to the list of `test_valid_programs_pass`. In `tests/test_services.py`, move `({"name": "Café"}, "schedule_name_characters")` out of `test_programs_that_break_a_rule` and add `({"name": "Café"}, [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Café"])` to `test_program_variants`.

Run: `uv run pytest tests/test_schedule.py tests/test_services.py -v`
Expected: the two moved cases fail.

In `custom_components/ravelli_smart_wifi/models.py`, replace

```python
        if any(not " " <= char <= "~" for char in self.name):
            raise ScheduleValidationError("name_characters")
```

with

```python
        if any(not char.isprintable() for char in self.name):
            raise ScheduleValidationError("name_characters")
```

In both translation files, replace the message of `schedule_name_characters` and the description of the field `name` of `set_schedule_program`:

- English message: `The program name cannot hold control characters.`
- English description: `Name of the program, 1 to 15 characters.`
- French message: `Le nom du programme ne peut pas contenir de caractères de contrôle.`
- French description: `Nom du programme, de 1 à 15 caractères.`

In `README.md`, replace `1 to 15 characters, without accents` with `1 to 15 characters`.

Run: `uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Add the DHCP matcher, if the hostname allows it**

Skip this step if the hostname noted in the checklist is generic, which means it could belong to any device built on the same Wi-Fi chip. Record that in the results table: the network search stays the only discovery path.

Otherwise, with `PREFIX` the constant start of the hostname in lower case, update `tests/test_manifest.py`: replace

```python
    assert manifest["dhcp"] == [{"registered_devices": True}]
```

with, `PREFIX` replaced by its value,

```python
    assert manifest["dhcp"] == [
        {"registered_devices": True},
        {"hostname": "PREFIX*"},
    ]
```

Run: `uv run pytest tests/test_manifest.py -v`
Expected: the test fails on the `dhcp` key.

In `custom_components/ravelli_smart_wifi/manifest.json`, replace

```json
  "dhcp": [{ "registered_devices": true }],
```

with, `PREFIX` replaced by its value,

```json
  "dhcp": [{ "registered_devices": true }, { "hostname": "PREFIX*" }],
```

Run: `uv run pytest tests/test_manifest.py -v`
Expected: all tests pass. The DHCP step of the flow already probes a discovered host before offering it, so no other code changes.

- [ ] **Step 8: Record the results in the spec**

In `docs/superpowers/specs/2026-09-29-ravelli-smart-wifi-integration-design.md`, in the register table of section 3, replace the words `scale unverified` and `unverified` by `verified` for every register the checklist confirmed, and state the measured scale of register 5. In the subsection "Hardware verification" of section 10, add one line per point with its result.

- [ ] **Step 9: Set the version and commit**

Set `"version"` in `custom_components/ravelli_smart_wifi/manifest.json` to the year and month of the release, for example `"2026.10"`.

Run: `uv run ruff format . && uv run ruff check . && uv run pytest`
Expected: `All checks passed!` and every test passes.

```bash
git add -A
git commit -m "feat: apply the results of the hardware verification"
git checkout main
git merge --ff-only feature/hardware-verification
git branch -d feature/hardware-verification
```

- [ ] **Step 10: Check the repository for personal data**

Run:

```bash
git grep -nE '192\.168\.|\b10\.[0-9]+\.[0-9]+\.[0-9]+\b|172\.(1[6-9]|2[0-9]|3[01])\.' $(git rev-list --all) -- . ; echo "exit $?"
```

Expected: no line is printed and the last line is `exit 1`.

Read every file listed by `git ls-files` once, looking for a first name, a hostname, a network name or a MAC address that is not `aa:bb:cc:dd:ee:ff` or `11:22:33:44:55:66`. Read the output of `git log --format='%an %ae %s'` the same way: the author must be the identity the owner uses for public repositories.

- [ ] **Step 11: Publish (Owner approval)**

Ask the owner before each of these commands. They create a public repository and cannot be fully undone.

```bash
gh repo create Greite/ha-ravelli-smart-wifi --public --source . \
  --description "Home Assistant integration for the Ravelli Smart Wi-Fi module (unofficial)"
git push -u origin main
gh repo edit Greite/ha-ravelli-smart-wifi \
  --add-topic home-assistant --add-topic hacs --add-topic pellet-stove
```

Expected: the workflows `Test` and `Validate` run on the push. Read their results with `gh run list` and fix whatever hassfest or the HACS validation reports, each fix on its own `fix/<slug>` branch merged with `--ff-only`.

- [ ] **Step 12: Tag the release (Owner approval)**

Once both workflows are green, with `VERSION` the version of the manifest:

```bash
git tag -a vVERSION -m "First release"
git push origin vVERSION
gh release create vVERSION --title "vVERSION" --notes "First release. Supports the AIR-RDS board (verified), and the HYDRO-RDS and ECO-RDS boards (not tested)."
```

Expected: the release is listed by `gh release list`, and HACS offers the version when the repository is added as a custom repository.
