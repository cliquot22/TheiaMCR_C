# Theia Technologies Motor Control Board Interface

[Theia Technologies](https://www.theiatech.com/) offers the [MCR IQ 600 motor control board](https://www.theiatech.com/lenses/accessories/mcr/) (and similar MCR IQ 400 and MCR IQ 500 boards) for controlling Theia's motorized lenses. The board controls focus, zoom, iris, and IRC (IR cut filter) motors and connects to a host computer via USB, UART, or I2C. This software package supports virtual COM port (USB) connections.

---

## System Architecture

```
[Host PC]
    |
    | USB (virtual COM port)
    |
[MCR IQ 600 Board]
    |--- Focus motor
    |--- Zoom motor
    |--- Iris motor
    |--- IRC filter motor
```

The host PC communicates with the MCR IQ 600 board over a USB serial connection. The board drives each lens motor independently. Before any motor commands can be sent, the board and each motor must be initialized.

---

## Installation

```
pip install TheiaMCR
```

**Requirements:**
- Python 3.9 or later
- `pyserial`
- Windows, Linux

---

## Quick Start

```python
import TheiaMCR as mcr

# 1. Open the board connection
MCR = mcr.MCRControl('com4')
if not MCR.boardInitialized:
    print('Board not found. Check the COM port.')

# 2. Initialize motors (moves each motor to its home/PI position)
MCR.focusInit(steps=8390, pi=7959)
MCR.zoomInit(steps=3227, pi=3119)
MCR.irisInit(steps=75)
MCR.IRCInit()

# 3. Move motors
MCR.focus.moveAbs(4000)    # move focus to step 4000
MCR.zoom.moveRel(-500)     # move zoom 500 steps toward tele
MCR.iris.moveAbs(40)       # move iris to step 40
MCR.IRC.state(1)           # set IRC to visible (IR-blocking) filter

# 4. Close when done
MCR.close()
```

---

## Contents

| Page | Description |
|------|-------------|
| [Initialization functions](https://github.com/cliquot22/TheiaMCR/wiki/Initialization-functions) | Class and motor initialization |
| [Motor movement functions](https://github.com/cliquot22/TheiaMCR/wiki/Motor-movement-functions) | Moving motors: absolute, relative, home, IRC |
| [Information and setting functions](https://github.com/cliquot22/TheiaMCR/wiki/Information-and-setting-functions) | Reading board info, configuring motor speeds and limits |

---

## Important Classes and Variables

TheiaMCR exposes two main sub-classes after initialization:

| Class | Instance | Created by | Purpose |
|-------|----------|------------|---------|
| `motor` | `MCR.focus`, `MCR.zoom`, `MCR.iris`, `MCR.IRC` | `focusInit()`, `zoomInit()`, `irisInit()`, `IRCInit()` | Motor movement and per-motor configuration |
| `controllerClass` | `MCR.MCRBoard` | `MCRControl()` automatically | Board-level commands: firmware, serial number, communication path |

### motor class variables

Available on each motor instance (`MCR.focus`, `MCR.zoom`, `MCR.iris`):

| Variable | Description |
|----------|-------------|
| `motor.currentStep` | Current step position of the motor |
| `motor.currentSpeed` | Current motor speed in pulses per second (pps) |
| `motor.homingSpeed` | Speed used when moving to the home (PI) position |
| `motor.maxSteps` | Maximum step count for the full range of movement |
| `motor.PIStep` | Step number of the photo interrupter (PI) limit switch. After homing, `currentStep` is set to this value. |
| `motor.PISide` | Side of the range the PI is on: `-1` if PI is near step 0, `+1` if PI is near `maxSteps` |
| `motor.respectLimits` | `True` to prevent motor movement past the PI position (default); `False` to allow movement beyond the PI |
| `motor.initialized` | `True` if the motor was successfully initialized |

### MCRBoard (controllerClass) variables

Available on `MCR.MCRBoard` and also promoted to the top-level `MCR` instance:

| Variable | Access | Description |
|----------|--------|-------------|
| `MCRInitialized` | `MCR.MCRInitialized` | `True` when the class is initialized and logging has started |
| `boardInitialized` | `MCR.boardInitialized` | `True` when the board connection is open and ready |
| `boardCommunicationState` | `MCR.boardCommunicationState` | `True` when the COM port is open and the board is actively responding |
| `boardCommunicationRestarts` | `MCR.boardCommunicationRestarts` | Count of times the COM port has been automatically reconnected |

---

## Error Codes

Functions that return an integer status use the following error codes:

| Constant | Value | Meaning |
|----------|-------|---------|
| `ERR_OK` | `0` | No error |
| `ERR_BAD_MOVE` | `-62` | Motor move returned unsuccessful |
| `ERR_SERIAL_PORT` | `-64` | Serial port not open |
| `ERR_RANGE` | `-69` | Input parameter out of range |
| `ERR_NOT_INIT` | `-24` | Board or motor not initialized |
| `ERR_NO_COMMUNICATION` | `-31` | No response from MCR board |
| `ERR_MOVE_TIMEOUT` | `-32` | No response before timeout |
| `ERR_NOT_SUPPORTED` | `-73` | Function not supported for this motor type |

Import and check error codes directly:

```python
import TheiaMCR.errList as err

result = MCR.focus.moveAbs(1000)
if result != err.ERR_OK:
    print(f'Move failed: {err.decipher(result)}')
```

---

## Logging

TheiaMCR writes log messages through Python's standard `logging` module. Log files are saved to the user's local application data directory by default.  For example on Windows: C:\Users\<USER>\AppData\Local\TheiaMCR\log

- Set `moduleDebugLevel=True` in `MCRControl()` to enable DEBUG-level console output.
- Set `communicationDebugLevel=True` to print all serial port traffic (not recommended in production).
- Set `logFiles=False` to suppress log file creation.
