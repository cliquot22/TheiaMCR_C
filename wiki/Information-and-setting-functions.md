These functions read board information, configure motor speeds and limit behavior, read and write motor configuration stored on the board, and manage the serial port connection.

---

## Board Firmware Revision

```python
MCR.MCRBoard.readFWRevision() -> str
```

`controllerClass` function. Read the firmware version string from the board.

**Returns** Firmware version as a string (e.g. `'5.3.1.0.0'`), or `None` if no response.

**Example**

```python
fw = MCR.MCRBoard.readFWRevision()
print(f'Firmware version: {fw}')
```

---

## Board Serial Number

```python
MCR.MCRBoard.readBoardSN() -> str
```

`controllerClass` function. Read the serial number of the MCR600 board.

**Returns** Serial number as a string (e.g. `'055-001234'`), or an empty string if no response.

**Example**

```python
sn = MCR.MCRBoard.readBoardSN()
print(f'Board SN: {sn}')
```

---

## Set Motor Speed

```python
motor.setMotorSpeed(speed) -> int
```

`motor` class function. Set the speed used for all subsequent moves on this motor. The speed is stored in the module only — it is not written to the board EEPROM. It should be within the speed range stored on the board (see `readMotorSetup()`).

**Speed ranges:**
- Focus / zoom: 100 – 1500 pps
- Iris: 10 – 200 pps

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `speed` | `int` | New speed in pulses per second (pps) |

**Returns**

| Value | Meaning |
|-------|---------|
| `0` | Success |
| `-69` (`ERR_RANGE`) | Speed is outside the acceptable range |

**Example**

```python
MCR.focus.setMotorSpeed(800)
MCR.zoom.setMotorSpeed(1200)
MCR.iris.setMotorSpeed(50)
```

---

## Set Homing Speed

```python
motor.setHomingSpeed(speed) -> int
```

`motor` class function. Set the speed used when homing the motor (seeking the PI limit switch). This applies to focus and zoom motors only. Like `setMotorSpeed()`, this is stored in the module and not written to the board EEPROM, but it should be within the board's configured speed range.

**Speed ranges:**
- Focus / zoom: 100 – 1500 pps

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `speed` | `int` | Homing speed in pulses per second (pps) |

**Returns**

| Value | Meaning |
|-------|---------|
| `0` | Success |
| `-69` (`ERR_RANGE`) | Speed is outside the acceptable range |

**Example**

```python
MCR.focus.setHomingSpeed(600)
```

---

## Set Respect Limits

```python
motor.setRespectLimits(state) -> bool | None
```

`motor` class function. Control whether the motor stops at the PI limit switch position or is allowed to move past it.

When `True` (the default), `moveAbs()` and `moveRel()` will not allow the motor to cross the PI position. Set to `False` when a target step requires moving past the PI, such as accessing the full range on the far side of the limit switch.  When moving past the PI position, backlash it not automatically handled due to the possibility of the motor hitting the hard stop and losing it's position information.  

> Only applicable to focus and zoom motors. Returns `None` for iris and IRC.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `state` | `bool` | `True` to enforce the PI limit; `False` to allow movement past it |

**Returns** The new `respectLimits` state (`True`/`False`), or `None` if the motor has no PI.

**Example**

```python
# Allow focus to move past the PI limit
MCR.focus.setRespectLimits(False)
MCR.focus.moveRel(100)
MCR.focus.setRespectLimits(True)
```

---

## Read Motor Configuration

```python
motor.readMotorSetup() -> tuple
```

`motor` class function. Read the motor configuration stored in the MCR IQ 600 board EEPROM. This includes the motor type, limit switch enable flags, step range, and speed range.

**Returns** An 8-element tuple:

| Index | Name | Type | Description |
|-------|------|------|-------------|
| 0 | `success` | `bool` | `True` if the board returned a valid response |
| 1 | `motorType` | `int` | `0` = stepper motor, `1` = DC motor; or error code if `success` is `False` |
| 2 | `useWideFarStop` | `bool` | Left (wide/far) limit stop enabled |
| 3 | `useTeleNearStop` | `bool` | Right (tele/near) limit stop enabled |
| 4 | `maxSteps` | `int` | Maximum number of steps |
| 5 | `minSpeed` | `int` | Minimum speed (pps) |
| 6 | `maxSpeed` | `int` | Maximum speed (pps) |
| 7 | `errorVal` | `int` | `0` (`ERR_OK`) or error code |

> All values may be `-1` or `False` if `success` is `False`.

**Example**

```python
success, motorType, wideFarStop, teleNearStop, maxSteps, minSpeed, maxSpeed, errVal = MCR.zoom.readMotorSetup()
if success:
    print(f'Zoom: max steps={maxSteps}, speed range={minSpeed}-{maxSpeed} pps')
```

---

## Write Motor Configuration

```python
motor.writeMotorSetup(useWideFarStop, useTeleNearStop, maxSteps, minSpeed, maxSpeed) -> bool
```

`motor` class function. Write the motor configuration to the MCR IQ 600 board EEPROM. The configuration persists after a board power cycle.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `useWideFarStop` | `bool` | Enable the left (wide/far) limit stop |
| `useTeleNearStop` | `bool` | Enable the right (tele/near) limit stop |
| `maxSteps` | `int` | Maximum number of steps |
| `minSpeed` | `int` | Minimum speed (pps) |
| `maxSpeed` | `int` | Maximum speed (pps) |

**Returns** `True` if the board confirmed the write, `False` otherwise.

**Example**

```python
success = MCR.zoom.writeMotorSetup(
    useWideFarStop=True,
    useTeleNearStop=False,
    maxSteps=3227,
    minSpeed=100,
    maxSpeed=1500
)
```

---

## Check and Restart Board Communication

```python
MCR.checkBoardCommunication() -> bool
```

Top-level function. Verify that the serial port is open and the MCR board is responding. If the initial check fails, the serial port is closed and reopened, and the board is tested again. Returns the result of the final communication test.

Use this function to detect and recover from temporary USB disconnections in long-running applications.

**Returns** `True` if communication with the board is working, `False` if it cannot be restored.

**Example**

```python
if not MCR.checkBoardCommunication():
    print('Board communication lost — check USB connection')
else:
    print(f'Communication OK (restarts so far: {MCR.boardCommunicationRestarts})')
```

---

## Board Communication Path

```python
MCR.MCRBoard.setCommunicationPath(path) -> bool
```

`controllerClass` function. Change the communication interface used by the board. The first connection when receiving the board (or factory resetting the board) will be made over USB. Once connected, this function can switch the board to I2C or UART for subsequent sessions. After setting a new path, the board reboots — wait at least 700 ms before sending further commands. The original USB connection will no longer be active after this command. 

This TheiaMCR module will no longer be available without user modification to the sendCmd() function.  This function must be modified to support the new I2C or UART protocol by the user.  

See [Theia motor driver instructions](https://theiatech.com/mcr) for wiring details for UART and I2C connections.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `path` | `int` or `str` | New communication path: `'I2C'` or `0`, `'USB'` or `1`, `'UART'` or `2` |

**Returns** `True` if the command was sent successfully. The board reboots and the current connection is lost regardless of return value.

**Example**

```python
import TheiaMCR as mcr
import time

MCR = mcr.MCRControl('com4')

# Switch to UART communication
MCR.MCRBoard.setCommunicationPath('UART')

# Wait for board reboot (>700 ms)
time.sleep(1)
# Reconnect on the new path
```
