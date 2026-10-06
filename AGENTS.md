# ha-ravelli-smart-wifi

Home Assistant custom integration (`ravelli_smart_wifi`) for pellet stoves fitted with the WiNET Wi-Fi module, through its local HTTP API. It turns a combustion appliance on and off: never relax a refusal, a bound or a safety rule. User-facing docs are in README.md; this file only covers what a contributor needs beyond it. Review priorities are in WATCHDOG.md.

## Commands

```bash
uv sync                                                        # install the tools
uv run ruff format . && uv run ruff check . && uv run pytest   # before every commit; CI runs the same with `format --check`
uv run pytest tests/test_coordinator.py -k turn_off            # one area
```

## Layout

- `custom_components/ravelli_smart_wifi/api.py` — `WinetClient`, the HTTP client. `models.py` — register table of each board, status table, write bounds, schedule encoding. Neither imports Home Assistant.
- `coordinator.py` — the one `DataUpdateCoordinator`: polling, the lock, every command and its safety rules (`async_set_power`, schedule writes with read-back).
- `config_flow.py` — network search, manual entry, DHCP discovery, reconfigure, options.
- Platforms: `climate.py`, `sensor.py`, `binary_sensor.py`, `number.py`, `switch.py`, `button.py`, `calendar.py`. `services.py` holds the two schedule actions. `diagnostics.py` is an allow-list.
- `brand/` — the images Home Assistant shows for the integration.
- `tests/fake_module.py` — simulator of the module at the HTTP level. `tests/fixtures/` — answers of a real module, anonymized.
- `docs/hardware-verification.md` — what was checked on a real stove, per board and firmware.
- `docs/superpowers/` — the design spec, kept true (amendments in its section 12), and the implementation plan, historical.

## Conventions

- Write the failing test first, at the HTTP level through the simulator: change the simulator, never mock the client.
- Every text shown to the user lives in `translations/en.json` and `fr.json`; `tests/test_translations.py` keeps them in step. `tests/test_documentation.py` checks the claims of the README: update both together.
- Only what was read on a real stove counts as a hardware fact, with its row in `docs/hardware-verification.md`. Never give a meaning to a status code that was not seen (5, 8, 9): it stays `unknown` and counts as on.
- Code, comments and docs in English (public repo).
- No name, hostname, private address, network name, MAC address or real program name in a file or a commit message. Examples use `192.0.2.x` and `aa:bb:cc:dd:ee:ff`. Answers of a real module hold such values: replace them before they enter a fixture.
- Git: `main` only; `feature/*` and `fix/*` branches merged with `--ff-only`; conventional commits in English, no attribution trailer.
- Release: CalVer. `manifest.json` carries `YYYY.MM`; the annotated tag `vYYYY.MM` is pushed once the `Test` and `Validate` workflows are green.

## Gotchas

- The module wants form-urlencoded bodies although the header says JSON (it answers `{"result":false}` to a JSON body), and it answers `{"result":true}` to every command it accepts.
- The web page of the module is wrong for four status codes of the AIR-RDS board. The table of `models.py` was read on the display of the stove.
- From eco stop the stove restarts by itself: that state is on and idle, never off.
- Home Assistant 2026.9: `DeviceRegistry.async_get_device(identifiers=...)` raises; use `async_get_device_by_identifier((DOMAIN, id), entry_id)`.
- `docs/` is excluded from `ruff` on purpose: the plan holds code blocks that must not be reformatted.
- An entity that changes unit or disappears leaves an orphan in the entity registry and statistics issues on installs that upgrade.
- Home Assistant sees the `brand/` folder only after a restart, and serves only `icon.png`, `logo.png` and their `@2x` and `dark_` variants.
