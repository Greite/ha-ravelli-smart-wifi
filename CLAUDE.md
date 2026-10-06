# ha-ravelli-smart-wifi

Home Assistant custom integration for stoves fitted with the WiNET Wi-Fi module
(local HTTP API). It turns a combustion appliance on and off: never relax a
refusal, a bound or a safety rule.

## Commands

- `uv sync` - install the tools
- `uv run ruff format . && uv run ruff check .` - before every commit (`docs/` is excluded on purpose)
- `uv run pytest` - whole suite, no stove needed
- `uv run pytest tests/test_coordinator.py -k turn_off` - one area

## Code

- `api.py` and `models.py` import nothing from Home Assistant.
- Tests go through the HTTP simulator `tests/fake_module.py`: change the simulator, never mock the client. Write the failing test first.
- Every text shown to the user lives in `translations/en.json` and `fr.json`; `tests/test_translations.py` keeps them in step.
- `tests/test_documentation.py` checks the claims of the README: update both together.
- Home Assistant 2026.9: `DeviceRegistry.async_get_device(identifiers=...)` raises; use `async_get_device_by_identifier`.

## Hardware facts

- Only what was read on a real stove counts; it is in `docs/hardware-verification.md`. The web page of the module is wrong for four status codes.
- Never give a meaning to a status code that was not seen (5, 8, 9): it stays `unknown` and counts as on.
- Commands are form-urlencoded although the header says JSON, and each must answer `{"result": true}`.

## Git

- `main` only. `feature/*` and `fix/*` branches, merged with `--ff-only`.
- Conventional commits in English, no attribution trailer. CalVer: tag `vYYYY.MM`, same as `manifest.json`.

## Privacy (public repository)

- No name, hostname, private address, network name, MAC address or real program name in a file or a commit message. Examples use `192.0.2.x` and `aa:bb:cc:dd:ee:ff`.
- Answers of a real module hold such values: replace them before they enter a fixture.

## Gotchas

- An entity that changes unit or disappears leaves an orphan in the entity registry and statistics issues on installs that upgrade.
- Brand images are in `custom_components/ravelli_smart_wifi/brand/`; Home Assistant sees the folder only after a restart.
