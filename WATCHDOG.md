# Review priorities - ha-ravelli-smart-wifi

Reviewer for a Home Assistant custom integration that drives pellet stoves through the local HTTP API of their Wi-Fi module. It turns a combustion appliance on and off, in a public repository. Contributor context is in `AGENTS.md`. Check the code before asserting; flag first what can start or keep a stove running against the user's intent, then what leaks the home. Pure style stays a `nit`.

## Blocker: the stove does something the user did not ask

- **A status code given a meaning nobody read on a stove.** `STATUS_KEYS` in `models.py` holds only the codes read on the display of a real stove; the web page of the module was wrong for four of them. The codes 5, 8 and 9 have no key. A new key, or a new meaning, needs a dated row in `docs/hardware-verification.md`.
- **A stove that runs while Home Assistant says off.** Every code outside `STATUS_NOT_ON` counts as on, unknown codes included, so an off command can always be sent. Eco stop (7) is on and idle: the stove restarts by itself. A mapping that shows off for 7 or for an unknown code is a blocker.
- **A turn-on that is not refused, or a turn-off that is not sent.** `async_set_power` reads the stove first, refuses on when `has_alarm` (status 8 or 9, or alarm register not 0) and sends off in every state except "off without alarm". The only refused off is during ignition with `flame == 0`. Check each combination, not each rule alone: the case "off and in alarm" was a dead end once.
- **A refusal with no way out.** When a command is refused, the action its message asks for must really be sent. Read the message and the code path together.
- **A write outside the table.** Only registers of `WRITE_BOUNDS` are written, through `validate_write`; no action writes an arbitrary register; a write is never retried; every command goes through `WinetClient._command` and needs `{"result": true}`.
- **A schedule write without read-back.** The table is read, changed, written and read again (`_async_verify_schedule`, `schedule_mismatch`). The global flag is parsed strictly: a misread flag written back as enabled makes the stove start on its programs. Programs created on the page of the module must come back unchanged, name included.
- **Commands after a model mismatch.** A poll that reports another board fails the update; nothing may be sent from the wrong register table.

## Concern: privacy

- **Diagnostics are an allow-list.** `KEEP_SYSTEM`, `KEEP_CATEGORY` and `KEEP_SCHEDULE` in `diagnostics.py`: a key added there must not identify a home; program names stay redacted; an error is recorded by its class, never by its message.
- **Logs.** The debug record of `_post` holds the path, the HTTP status and the answer, never the host. Decode errors describe the shape of a row, never its content.
- **Files and commits.** No name of a person, hostname, private address, network name, MAC address or real program name; examples use `192.0.2.x` and `aa:bb:cc:dd:ee:ff`. The DHCP hostname of a module holds the end of its MAC address: write the pattern only.
- **Fixtures captured on a real module.** Replacing the names is not enough: times, temperatures and dates of a capture describe a household too. Say what was kept on purpose.

## Concern: recurring omissions

- Entity added, removed, renamed or given another unit without both translation files, the README table "What you get" and the spec (section 5, and a row in section 12). A removal or a unit change also leaves an orphan entity and a statistics issue on installs that upgrade: the change must say how they are handled.
- A fact about the stove stated in the README or the spec without its row in `docs/hardware-verification.md`, or the lists of what is not verified (README, spec section 10) left out of date.
- A text in one language only. The French labels of the states are the words of the display of the stove.
- An import of Home Assistant in `api.py` or `models.py`; a test that mocks the client instead of extending `tests/fake_module.py`; a simulator that answers what the real module does not.
- `docs/` reformatted by a tool (it is excluded from `ruff` on purpose), or the plan under `docs/superpowers/plans/` edited after the fact.
- A file in `custom_components/ravelli_smart_wifi/brand/` whose name Home Assistant does not know: the placeholder comes back without any error.
- `manifest.json`: version not `YYYY.MM`, or not the one of the tag.

## Evidence expected before "done"

- `uv run ruff format --check . && uv run ruff check . && uv run pytest` (what CI runs), with the number of tests and a clean output.
- For a change of behaviour: the test failing first, then passing, written at the HTTP level (the body sent to the simulator, such as `key=022&status=0`).
- A claim about hardware needs a reading on a real stove, with board, firmware and date. Tests against the simulator, the web page of the module and a manual are not that evidence; without it the claim is written as "not verified".
- One observation is not a cause, and one reading is not a scale: ask for the second run without the change, or for several readings that agree.
- What an install shows (entities, units, discovery, brand images) needs a run on a real Home Assistant instance, with the log lines of the integration read: the test suite does not show registry orphans or statistics issues.
- No test or review step sends a command to a real stove. Hardware checks are made by a person in the room, following `docs/hardware-verification.md`.
- A change to the safety rules of `coordinator.py` or to `diagnostics.py` is reviewed on its own, not folded into a larger review.
- Conventional commit in English, no attribution trailer; branch merged with `--ff-only`. Release: both workflows green before the tag `vYYYY.MM`.
