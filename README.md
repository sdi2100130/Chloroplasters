# Chloroplasters
# Clever Tower Garden 🌱

Autonomous hydroponic tower with closed-loop pH, EC and temperature control.

## Overview

A 1.90m vertical hydroponic system that automatically maintains optimal growing
conditions for 30 plants (6 levels × 5 plants) using sensor feedback and 
syringe-based chemical dosing.

## Features

- **Adaptive irrigation** — interval adjusts to room temperature/humidity
- **pH homeostasis** — automatic dosing of citric acid (pH↓) or potassium bicarbonate (pH↑)
- **EC homeostasis** — automatic fertilizer dosing or fresh-water dilution
- **Thermal protection** — fan-based cooling above 30°C, off at 26°C
- **Emergency safe mode** — button-triggered shutdown of pumps & fan
- **Data logging** — CSV log of all sensor readings and dosing actions

## Hardware

See [hardware/BOM.md](hardware/BOM.md) for the full Bill of Materials.

**Key components:**
- XRP Robotics Controller (RP2040 + MicroPython)
- pH, EC, turbidity, water temp, flow, air temp/humidity sensors
- 3× medical syringes with servo actuation for chemical dosing
- 12V submersible pump (relay-controlled)
- 12V fan for evaporative tank cooling

## Software

MicroPython firmware running on the XRP. State machine with the following modes:
`IDLE → IRRIGATING → MEASURING → DOSING → IDLE`

Plus orthogonal safety states: `NORMAL` ↔ `SAFE`

See [docs/architecture.md](docs/architecture.md) for details.

## Quickstart

1. Flash MicroPython on the XRP (instructions in `docs/setup.md`)
2. Copy contents of `firmware/` to the device
3. Calibrate sensors using scripts in `calibration/`
4. Update `firmware/config.py` with your calibration values
5. Power on — green LED indicates normal operation

## Safety ⚠️

- **GFCI/RCD adapter is mandatory** — electricity + water
- Pumps run on **12V DC only**, never mains
- Chemical solutions are mild but use gloves & goggles when refilling
- See [docs/safety-checklist.md](docs/safety-checklist.md) before every run

## Team

Built by 

## License

MellonLab

