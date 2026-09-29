# Ravelli Smart Wi-Fi integration for Home Assistant: design

Date: 2026-09-29
Status: approved. Amended on 2026-09-29 during planning (section 12).

## 1. Goal

Provide a Home Assistant custom integration, installable through HACS, for
Ravelli pellet stoves fitted with the "Ravelli Smart Wi-Fi" module (made by
Net Software, also known as WiNET). The module is not supported by the
Micronova Agua IOT integration, which targets a different platform.

The integration talks to the module over its local HTTP API. It needs no cloud
account and no extra hardware. The feature target is parity with Micronova
Agua IOT wherever the module exposes the data, plus schedule editing and
network discovery.

Success criteria:

- A user adds the integration from the Home Assistant UI without editing YAML.
- The stove is controllable from a thermostat card: on/off, target
  temperature, power level.
- Entities become unavailable when the module stops answering.
- No write can leave the ranges the vendor UI itself enforces.
- The repository passes hassfest, HACS validation, ruff and pytest in CI.

## 2. Scope

### Supported stove boards

The module reports a numeric board model. Support is limited to the RDS
family, which shares one register layout in the vendor UI.

| Model code | Vendor name | Status |
|---|---|---|
| 7 | AIR-RDS | Verified on real hardware |
| 11 | HYDRO-RDS | Transcribed from the vendor UI, untested |
| 12 | ECO-RDS | Transcribed from the vendor UI, untested |

Every other model code (1, 2, 5, 6, 8, 9, 10, 14, 15) is refused during
setup with a message that names the code and points to the issue tracker.

### In scope

- Climate, sensor, binary sensor, number, switch, button and calendar
  platforms (section 5).
- Two actions to edit and delete schedule programs (section 8).
- Config flow with network scan, manual entry, DHCP discovery, reconfigure
  and options (section 6).
- Diagnostics download.
- English and French translations.

### Out of scope for the first release

- Netatmo and Telegram settings stored in the module.
- Module reboot and firmware upgrade.
- T-Sense wireless probes.
- Technical parameters behind the module PIN.
- The thermal history chart (Home Assistant records history itself).

## 3. Device protocol

All facts below were read from the vendor web UI shipped by the module and
confirmed against a live AIR-RDS module (firmware 0.51), unless marked
unverified.

### Transport

- Plain HTTP on port 80, no authentication, no TLS.
- Every call is a `POST`.
- The request carries the header
  `Content-Type: application/json; charset=utf-8` but the body is
  **form-urlencoded** (`key=020&category=2`). A JSON body is answered with
  `{"result": false}`.
- Responses are JSON.

### Endpoints

| Purpose | Path | Body |
|---|---|---|
| Module info | `/ajax/get-registers` | `key=019` |
| Read a register category | `/ajax/get-registers` | `key=020&category=N` |
| Turn on or off | `/ajax/get-registers` | `key=022&status=1` or `status=0` |
| Read schedule | `/ajax/get-registers` | `key=033` |
| Write schedule | `/ajax/get-registers` | `key=032` plus fields (below) |
| Delete a program | `/ajax/get-registers` | `key=034&index=N` (0 to 5) |
| Write one register | `/ajax/set-register` | `key=002&memory=1&regId=R&value=V&result=false` |
| System status | `/ajax/get-status` | empty |

A category read returns:

```json
{"params": [[0, 44], [2, 0], [50, 22], [51, 1]],
 "cat": 2, "model": 7, "signal": 3, "flame": 255,
 "chrono": 0, "alr": "", "name": "NO NAME", "authLevel": 0}
```

`params` is a list of `[register, raw value]` pairs. A successful write
returns `{"result": true}`.

System status returns, among others, `fwVer` (string), `rssi` (dBm),
`signal` (0 to 4), `fwUpdate` (bool), `board` (list whose first item is the
model code) and network details. The network details are personal data and
are never stored in fixtures or diagnostics unredacted.

### Registers, RDS family

| Register | Category | Meaning | Encoding | Access |
|---|---|---|---|---|
| 0 | 2 | Ambient temperature | raw × 0.5 °C | read |
| 1 | 2 | Water temperature (model 11) | raw °C, unverified | read |
| 2 | all | Stove status | code, table below | read |
| 3 | all | Alarm code | raw, 0 means none | read |
| 4 | 2 | Flue gas temperature | raw °C, scale unverified | read |
| 5 | 2 | Extractor speed | raw, scale unverified | read |
| 24, 25 | 6 | Ducting temperature right, left | raw °C, unverified | read |
| 49 | 2 | Water set point (model 11) | 30 to 80 °C, 81 = manual, unverified | read/write |
| 50 | 2 | Ambient set point | 5 to 40 °C, 41 = manual | read/write |
| 51 | 2 | Power level | 1 to 5 | read/write |
| 59 to 64 | 4 | Clock: weekday, hour, minute, day, month, year | weekday 1 to 7 (1 = Monday), others BCD, year is two digits | read/write |
| 73 | 11 | Comfort climate delay | 0 to 9 min, 0 = off | read/write |
| 74 | 11 | Comfort climate delta | 0 to 20 °C, 0 = off | read/write |
| 184, 185 | 6 | Ducting set point right, left | 5 = off, 6 = external thermostat, 7 to 41 °C | read/write |

Register 37 is returned in every category and is not identified. It is
reported in diagnostics only. Registers 300 and 301 (category 0) are not
identified either and are treated the same way.

Ducting (category 6) applies to model 7 only, as in the vendor UI.

### Status codes, RDS family

| Code | Key | Home Assistant `hvac_action` |
|---|---|---|
| 0 | `off` | off |
| 1 | `pellet_loading` | preheating |
| 2 | `ignition` | preheating |
| 3 | `waiting_flame` | preheating |
| 4 | `flame_present` | preheating |
| 5 | `working` | heating |
| 6 | `final_cleaning` | off |
| 7 | `eco_stop` | idle |
| 8 | `alarm` | off |
| 9 | `alarm_memory` | off |

Any other code gives the Home Assistant `unknown` state, with the raw code
exposed as an attribute.

### Schedule

The module stores six programs and one global enable flag.

Read format, one list per program:

```
[enabled, start_enabled, start_hour, start_quarter,
 stop_enabled, stop_hour, stop_quarter,
 set_temp, set_power, days_mask, name]
```

- `start_quarter` and `stop_quarter` are 0 to 3, in units of 15 minutes.
- `days_mask` bit 0 is Monday, bit 6 is Sunday.
- `name` is at most 15 characters.
- A slot is free when `set_power` is 0, `enabled` is greater than 1 or the
  name is empty. This is the test the vendor UI applies.
- `set_temp` is 5 to 40, or 41 for manual. `set_power` is 1 to 5.

Write format (`key=032`): the whole table is sent in one call. Fields for
slot `N` (1 to 6) are `p0N1` (enabled), `p0N2` and `p0N3` (start and stop,
each `(enabled << 7) | (hour << 2) | quarter`), `p0N4` (temperature), `p0N5`
(power), `p0N6` (days mask), `p0N7` (name), plus the global `enabled`.
Free slots are omitted. The global enable flag has no endpoint of its own:
toggling it writes the whole table.

The write path has not been exercised on real hardware yet.

## 4. Architecture

Everything lives in `custom_components/ravelli_smart_wifi/`.

| File | Responsibility | Depends on |
|---|---|---|
| `api.py` | HTTP client: status, register reads, register writes, on/off, schedule, clock. Raises `WinetConnectionError` and `WinetResponseError`. | `aiohttp` only |
| `models.py` | Per-model register tables (scale, bounds, special values), status table, schedule encoding and decoding, typed `StoveState` | nothing |
| `coordinator.py` | Polling, availability, serialized writes, fast refresh after a write | `api.py`, `models.py` |
| `config_flow.py` | User, DHCP, reconfigure and options flows | `api.py` |
| `entity.py` | Base entity: device info, availability, unique id | `coordinator.py` |
| `climate.py`, `sensor.py`, `binary_sensor.py`, `number.py`, `switch.py`, `button.py`, `calendar.py` | One platform each, entities declared with description tables | `entity.py` |
| `services.py`, `services.yaml`, `diagnostics.py`, `translations/`, `icons.json`, `manifest.json` | Actions, diagnostics, texts, icons, metadata | — |

`api.py` and `models.py` import nothing from Home Assistant, so they can be
unit-tested alone and extracted into a library later.

### Data flow

- **Read.** Every 30 seconds by default (option, 10 to 300), the coordinator
  reads the categories the model needs, one request at a time: 2, then 6 for
  model 7, then 11. System status and the schedule are read every 10 minutes
  and after any schedule write.
- **Write.** Writes take a lock shared with reads, so the module never
  handles two requests at once. After a write the coordinator reads the
  state at once, then polls at 2, 5, 10, 20 and 30 seconds, because the stove
  changes state slowly.
- **Timeout.** 10 seconds per request.

### Device registry

One device per module: manufacturer "Ravelli", model taken from the model
code, software version from `fwVer`, MAC address as connection when known.

## 5. Entities

Names are translated through `translation_key`. Entities marked "off by
default" are created disabled in the entity registry.

| Platform | Entity | Source | Notes |
|---|---|---|---|
| climate | Stove | status, registers 0, 50, 51 | Modes `heat` and `off`. Target 5 to 40 °C, step 1. Fan modes `1` to `5` map to the power level. Preset `manual` writes 41 to register 50; preset `none` restores the last numeric target, or 20 °C when none is known. |
| climate | Ducting right, ducting left | registers 184/24, 185/25 | Model 7 only. Off by default. Modes `heat` and `off` (raw 5). Preset `external_thermostat` (raw 6). Target 7 to 41 °C. |
| climate | Water | registers 49, 1 | Model 11 only. Target 30 to 80 °C. |
| sensor | Status | register 2 | Enum of the 10 keys; `unknown` state for any other code; attribute `raw_value`. |
| sensor | Alarm | register 3, `alr` | State is the module's alarm text, or `none`; attribute `raw_value`. |
| sensor | Ambient temperature | register 0 | °C, measurement. |
| sensor | Flue gas temperature | register 4 | °C, measurement. |
| sensor | Extractor speed | register 5 | Raw value with no unit until the scale is verified on hardware; off by default until then. |
| sensor | Wi-Fi signal | `rssi` | dBm, diagnostic, off by default. |
| binary_sensor | Alarm | status 8 or 9, or register 3 non-zero | Device class `problem`. |
| binary_sensor | Flame | `flame` | Created only when the module reports a value other than 255. |
| binary_sensor | Firmware update available | `fwUpdate` | Device class `update`, diagnostic. |
| number | Power level | register 51 | 1 to 5. Deliberate duplicate of the climate fan mode, as in Agua IOT. |
| number | Comfort climate delta | register 74 | 0 to 20 °C, config. |
| number | Comfort climate delay | register 73 | 0 to 9 min, config. |
| switch | Schedule | schedule `enabled` | Config. Toggling rewrites the table with the flag changed. |
| button | Synchronize clock | registers 59 to 64 | Config. Writes Home Assistant local time. |
| calendar | Schedule | schedule programs | Read-only, section 8. |

Agua IOT features with no equivalent on the RDS family, and therefore
absent: pressure, pellet level, working hours, real power, standby and
auto/natural/powerful mode switches, fan mode selects, Bluetooth mode.

## 6. Configuration

### Unique id

The module API exposes no serial number or MAC address. The integration
resolves the MAC address from the IP with the `getmac` library after a
successful probe and uses it as the config entry unique id. If the lookup
fails, the entry is created without a unique id and duplicates are blocked
by matching the host.

### User step

The step is a menu with two choices: search the local network, or enter the
address manually. The search shows a progress screen while it runs.

1. The flow lists the IPv4 networks of the enabled Home Assistant adapters
   and keeps those with a prefix of /22 or longer, to bound the scan.
2. It probes every host with `POST /ajax/get-status` (32 at a time, 1.5
   second timeout). A host is a candidate when the answer is JSON with both
   `fwVer` and `board`.
3. Candidates already configured are dropped. The rest are shown in a list,
   with a "enter the address manually" choice. When the scan finds nothing,
   the flow goes straight to manual entry.
4. The chosen host is probed again with `key=019` to read the model code.

Errors: `cannot_connect`, `not_winet` (answers, but not this API),
`unsupported_model` (with the code as a placeholder), `already_configured`.

### DHCP step

`manifest.json` declares `registered_devices: true`, so Home Assistant
updates the host by itself when a known module changes address.

Discovery of new modules needs a hostname matcher. The hostname the module
announces over DHCP is not known yet. The rule is:

- If the announced hostname is specific to the module, the manifest gets a
  matcher on it, and the DHCP step probes the host before offering it.
- If the hostname is generic, no matcher for new devices is declared and the
  network scan is the only discovery path.

### Reconfigure and options

- **Reconfigure** changes the host and keeps entities and history. It
  refuses a host that answers with a different MAC address.
- **Options** holds the polling interval (10 to 300 seconds, default 30).

## 7. Error handling and safety

| Situation | Behaviour |
|---|---|
| Module unreachable or timeout | `UpdateFailed`; entities unavailable; logged once |
| Write answered with `result: false` | `HomeAssistantError` with a translated message |
| Value outside the model bounds | `ServiceValidationError`, nothing is sent |
| Unsupported model at setup | Setup refused, message names the code |
| Unknown status code | State `unknown`, raw code as attribute |

Safety rules:

- Only registers listed in the model table are written. No action writes an
  arbitrary register.
- On and off commands read the stove state from the module first, so the
  rules below never rely on a state that is up to 30 seconds old.
- Turning off is refused while the stove is igniting and the module reports
  no flame (`flame == 0`), as the vendor UI does.
- Turning on is refused while the status is `alarm` or `alarm_memory`.
  Turning off in those states is allowed and acknowledges the alarm.
- Writes are never retried automatically.
- Schedule writes read the table, change it, write it, read it back and
  raise if the result differs.
- The README states that the module API is unauthenticated on the local
  network.

## 8. Schedule editing

### Actions

Both actions target the integration's device.

`ravelli_smart_wifi.set_schedule_program`

| Field | Type | Rule |
|---|---|---|
| `slot` | 1 to 6 | required |
| `name` | text | required, 1 to 15 printable ASCII characters |
| `enabled` | bool | default true |
| `start` | time | optional, minutes must be 0, 15, 30 or 45 |
| `end` | time | optional, same rule |
| `temperature` | 5 to 40 | required unless `manual` is true |
| `manual` | bool | default false, writes 41 |
| `power` | 1 to 5 | required |
| `weekdays` | list of `mon` to `sun` | at least one |

Validation mirrors the vendor UI: when both times are given, `end` must be
later than `start`; an enabled program needs at least one of the two.

`ravelli_smart_wifi.delete_schedule_program` takes `slot` (1 to 6).

### Calendar

A read-only calendar entity shows the programs over the requested range.

- One event per program and active weekday, named after the program, with
  temperature and power in the description.
- A program with only a start or only an end yields a 15-minute event at
  that time, described as "start only" or "stop only".
- Disabled programs yield no events. When the global flag is off, the
  calendar is empty.

## 9. Diagnostics

The download contains the config entry, the last system status, the raw
registers of every category and the schedule. Host, MAC address, network
name, IP addresses, gateway and device name are redacted.

## 10. Testing

Tests are written before the code they cover. They run with `pytest` and
`pytest-homeassistant-custom-component`, in an environment managed by `uv`.

| Level | Coverage |
|---|---|
| `api.py`, `models.py` | Register decoding, scales, status table, schedule encode/decode round trip, clock BCD, malformed answers, body encoding |
| Config flow | Scan with results, scan empty, manual entry, DHCP, reconfigure, unsupported model, cannot connect, not a WiNET module, duplicate |
| Coordinator | Unavailable on failure, recovery, fast refresh after write, request serialization |
| Platforms | State of every entity from fixtures, command sent by every writable entity, entities created per model |
| Safety | Bounds, turn-off during ignition, turn-on in alarm, schedule read-back mismatch |

Fixtures are JSON answers captured from a real module. Network name, IP
addresses and device name are replaced before the files enter the
repository.

### Hardware verification

These points need a running stove and are checked by hand before the first
release:

1. On and off commands.
2. Scale of the flue gas temperature and extractor speed.
3. Manual mode (register 50 set to 41).
4. Schedule write, including the global flag, after saving the existing
   programs.
5. Clock synchronization.
6. The hostname announced over DHCP.

## 11. Repository conventions

- **Licence:** MIT.
- **Language:** code, comments, commits and documentation in English.
- **Git:** `main` is the only permanent branch. Work happens on `feature/*`
  or `fix/*` branches, rebased on `main` and merged by fast-forward. No merge
  commits. Conventional commits.
- **Versions:** CalVer, annotated tags `vYYYY.MM` and `vYYYY.MM.N`. The
  manifest version follows the tag without the `v`.
- **Home Assistant:** 2026.9.0 or later, the version the tests run against.
- **CI:** hassfest, HACS validation, ruff (lint and format check) and pytest,
  on push and pull request.
- **Privacy:** no personal data in any file or commit message: no names, no
  hostnames, no private IP addresses, no network names. Examples use
  documentation addresses such as `192.0.2.10`.
- **Distribution:** HACS custom repository first. A request to join the HACS
  default store is a later, separate decision.

## 12. Amendments made during planning

| Topic | Change | Reason |
|---|---|---|
| Free schedule slot | Detected by `set_power` 0, `enabled` above 1 or empty name | It is the vendor UI rule; the name alone is not enough |
| Program names | Printable ASCII only | The module's handling of other characters is unknown; to be relaxed after hardware verification |
| `strings.json` | Not shipped; `translations/en.json` is the source | Custom integrations only load `translations/`; a copy would duplicate every text |
| User step | Menu, then search with a progress screen | A search of a /22 network can take close to a minute |
| Unknown status code | Home Assistant `unknown` state instead of an `unknown` enum option | `unknown` is a reserved state in Home Assistant |
| On and off commands | Fresh read of the stove state before the safety rules | The polled state can be 30 seconds old |
| Minimum Home Assistant version | 2026.9.0 | Only tested version |
| Calendar descriptions | In French when Home Assistant is in French, in English otherwise | Asked by the owner after the final review |
