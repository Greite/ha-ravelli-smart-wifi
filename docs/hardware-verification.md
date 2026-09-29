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

## Raw answers

Keep these outputs outside the repository too.

```bash
# System status
curl -X POST -H "Content-Type: application/json; charset=utf-8" \
  http://192.0.2.10/ajax/get-status
# Register category 2
curl -X POST -H "Content-Type: application/json; charset=utf-8" \
  -d "key=020&category=2" http://192.0.2.10/ajax/get-registers
```

## Checklist

| Point | How to check | Expected |
|---|---|---|
| On and off | Turn the thermostat on, wait for the status "Working", turn it off | The stove ignites. The status goes through ignition, working, final cleaning, off. Note every status code seen in the attribute `raw_value` |
| Turn-off rule | Turn the thermostat off right after turning it on | If the stove reports a flame value, the command is refused with the ignition message |
| Flue gas temperature | Compare the sensor with the value on the display of the stove, stove working | Same value |
| Extractor speed | Enable the sensor. Compare its raw value with the speed on the display of the stove | A constant ratio between the two |
| Manual mode | Choose the preset "Manual" | The display of the stove shows its manual mode. Choosing "None" restores the previous target |
| Schedule, names | On the page of the module, create a program whose name holds an accented letter, then read the schedule with the command above | Note whether the name comes back unchanged |
| Schedule, write | Store a program in slot 6 with the action, then open the page of the module | The program is there, with the right times, days, temperature and power. The other programs are unchanged |
| Schedule, switch | Flip the switch "Schedule" off and on | The page of the module shows the same state. The programs are unchanged |
| Schedule, switch with a foreign program | Keep the program with an accented name created on the page of the module, then flip the switch "Schedule" off and on | The program with the accented name is unchanged, name included |
| Schedule, delete | Delete slot 6 with the action | Slot 6 is free. The other programs are unchanged |
| Clock | Press "Synchronize clock" | The display of the stove shows the time of Home Assistant |
| Answers to commands | Turn debug logging on (see the README). Turn the stove on and off, flip the switch "Schedule", delete slot 6. Read the log lines `/ajax/get-registers answered HTTP` of each command | Note the JSON answer of the module to `key=022` (on and off), `key=032` (schedule write) and `key=034` (program delete) |
| Diagnostics | Download the diagnostics of the device. Read one raw system status and one raw category with the commands of the section "Raw answers" | Every register of the raw answers is in the download. No network name, address, device name, program name or other value that identifies the home appears in it |
| French interface | Set the language of your profile to French, then add the integration and choose the network search | In the list of modules found, the manual choice is shown in French |
| Thermostat card | Open the card of the thermostat "Stove" | The target moves by whole degrees. The current temperature shows half degrees |
| Soak | Leave the integration polling for one hour, stove on or off | The log holds no "unavailable" and no failed update |
| DHCP hostname | Unplug the stove for ten seconds, plug it back, then read the name the module announced in the list of DHCP leases of the router | Note the pattern of the name, without the part that identifies the device |

## Results

| Date | Board | Firmware | Point | Result |
|---|---|---|---|---|
| 2026-09-29 | AIR-RDS | 0.51 | French interface | Pass. The manual choice of the list of modules is shown in French |
| 2026-09-29 | AIR-RDS | 0.51 | Diagnostics | Pass. The 13 categories are in the download, the registers equal the raw answer, and no address, network name, device name, program name or MAC address appears |
| 2026-09-29 | AIR-RDS | 0.51 | Clock | Pass. Six register writes confirmed by the module. The display is within one minute of the reference: the module has no register for the seconds |
| 2026-09-29 | AIR-RDS | 0.51 | Target and power | Pass. Registers 50 and 51 written and read back. The power is shown on the home screen of the stove; the target is read with key 1. Values outside the bounds are refused and nothing is sent |
| 2026-09-29 | AIR-RDS | 0.51 | Manual mode | Pass. The set temperature screen shows MAN. Choosing "None" restores the previous target |
| 2026-09-29 | AIR-RDS | 0.51 | Schedule, names | Pass. A name with an accented letter comes back unchanged |
| 2026-09-29 | AIR-RDS | 0.51 | Schedule, write | Pass. The other programs are unchanged |
| 2026-09-29 | AIR-RDS | 0.51 | Schedule, switch | Pass, off then on. The programs are unchanged |
| 2026-09-29 | AIR-RDS | 0.51 | Schedule, switch with a foreign program | Pass. The program with the accented name is unchanged, name included |
| 2026-09-29 | AIR-RDS | 0.51 | Schedule, delete | Pass. The module clears the name, the power and the enabled flag of the freed row and leaves its stop time in place; the row is free by the rule of the page of the module |
| 2026-09-29 | AIR-RDS | 0.51 | Answers to commands | The module answers `{"result":true}` to `key=002` (register write), `key=022` (on and off), `key=032` (schedule write) and `key=034` (program delete) |
| 2026-09-29 | AIR-RDS | 0.51 | On and off | Partial. The on command ignites the stove; the status codes 1, 2 and 3 were seen in that order. The stove was then turned off from its own button before it reached "Working", and the status code 6 followed. The status codes 4, 5 and 7 and the off command are not verified |
| 2026-09-29 | AIR-RDS | 0.51 | Turn-off rule | Not applicable. The board reports 255 as its flame value during the whole cycle, which means "no information" |
| 2026-09-29 | AIR-RDS | 0.51 | Flue gas temperature | Fail. Register 4 stays at 0 while the display of the stove shows 106 °C. The value is in no register of the categories 0 to 20 at the access level of the integration |
| 2026-09-29 | AIR-RDS | 0.51 | Extractor speed | One reading only: raw 253 for 2780 rpm on the display, which fits `raw × 10 + 250`. Two more readings are needed |
| 2026-09-29 | AIR-RDS | 0.51 | Thermostat card, Soak, DHCP hostname | Not checked yet |
