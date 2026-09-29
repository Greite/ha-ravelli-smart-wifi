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
| AIR-RDS | Reads verified on a real stove; commands not verified yet |
| HYDRO-RDS | Written from the module's own web page, not tested |
| ECO-RDS | Written from the module's own web page, not tested |
| Any other board | Refused at setup |

To find your board, open `http://<address of the module>/` in a browser: the
name is at the top of the page.

To report a problem with a stove that is set up, open an issue and attach the
diagnostics download of the device: it is made for that, and personal data is
removed from it.

If your board is refused at setup, there is no device to download from. Open
an issue and attach the output of this command, after removing the values of
`name`, `netatmo` and `tsense` from it:

```bash
curl -X POST -H "Content-Type: application/json; charset=utf-8" \
  -d "key=020&category=2" http://192.0.2.10/ajax/get-registers
```

## What you get

| Entity | What it does |
|---|---|
| Thermostat "Stove" | On and off, target temperature (5 to 40 °C), power level (1 to 5) as fan mode, manual mode as preset, and what the stove is doing |
| Thermostats "Ducting right" and "Ducting left" | Target (7 to 41 °C) and temperature of each ducted outlet, and the preset "External thermostat". Disabled by default: enable them if your stove has ducting. AIR-RDS only |
| Thermostat "Water" | Water target and temperature. HYDRO-RDS only |
| Sensor "Status" | Off, ignition, working, final cleaning, alarm and so on |
| Sensor "Alarm message" and binary sensor "Alarm" | The alarm text of the stove, and whether an alarm is active |
| Sensors "Ambient temperature" and "Flue gas temperature" | In °C |
| Sensor "Extractor speed" | Raw value, disabled by default until its scale is verified |
| Sensor "Wi-Fi signal" | In dBm, disabled by default |
| Binary sensor "Flame" | Whether the flame is lit. Created only if your stove reports it |
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
| Nothing answers at this address. | Wrong address, stove unplugged, or module not connected to the Wi-Fi |
| A device answers at this address, but it is not a Ravelli Smart Wi-Fi module. | The address belongs to another device |
| Stove model N is not supported yet. Ask for it at https://github.com/Greite/ha-ravelli-smart-wifi/issues. | The board is not in the table above. Open an issue with the code N |

The diagnostics download of the device holds every register of the stove.
Network name, addresses and program names are removed from it.

### Debug logging

To see every answer of the module in the log, add this to
`configuration.yaml` and restart Home Assistant, or use **Enable debug
logging** on the page of the integration:

```yaml
logger:
  logs:
    custom_components.ravelli_smart_wifi: debug
```

Each request then logs its path, the HTTP status and the answer of the module.
The address of the module is never logged, and neither is the system status,
which holds the network name. The other answers hold the name given to the
stove, the names of the programs, `netatmo` (a free text) and `tsense` (the
MAC addresses of wireless probes): remove them before you post a log, or post
the diagnostics download instead of a debug log.

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
