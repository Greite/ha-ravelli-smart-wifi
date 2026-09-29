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
