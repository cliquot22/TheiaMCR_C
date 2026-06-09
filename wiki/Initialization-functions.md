The board must be initialized before any commands can be sent. After the board is initialized, each motor must be initialized individually. Motor initialization creates a motor instance (e.g. `MCR.focus`) that gives access to all movement and configuration functions for that motor.

**Initialization sequence:**
1. `MCRControl()` — open the board connection and initialize the controller sub-class
2. `focusInit()`, `zoomInit()`, `irisInit()`, `IRCInit()` — initialize each motor sequentially
3. `close()` — release the connection when done (unless done automatically when the program is terminated)

---

## Class Initialization

```python
MCRControl(serialPortName, moduleDebugLevel=False, communicationDebugLevel=False, logFiles=True)
```

Top-level class for all interactions with the MCR600 series boards. Opens the serial port and confirms the connection by reading the board firmware version. The `controllerClass` sub-class is created automatically as `MCR.MCRBoard`.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `serialPortName` | `str` | — | Serial port name (e.g. `'com4'` or `'/dev/ttyAMA0'`) |
| `moduleDebugLevel` | `bool` | `False` | Set `True` to enable DEBUG-level console logging (default is INFO) |
| `communicationDebugLevel` | `bool` | `False` | Set `True` to print all serial port traffic to the console. Implies `moduleDebugLevel=True`. Not recommended in production. |
| `logFiles` | `bool` | `True` | Set `True` to write log files to the user's local application data directory |

**Class variables**

| Variable | Description |
|----------|-------------|
| `MCRInitialized` | `True` when the class is successfully initialized (logging started) |
| `boardInitialized` | `True` when this board instance is initialized and the COM port is open |
| `boardCommunicationState` | `True` when the COM port is open and the board is responding |
| `boardCommunicationRestarts` | Count of times the COM port has been automatically reconnected |

**Sub-classes**

| Sub-class | Access | Description |
|-----------|--------|-------------|
| `motor` | `MCR.focus`, `MCR.zoom`, `MCR.iris`, `MCR.IRC` | Motor movement and configuration (created by each motor init function) |
| `controllerClass` | `MCR.MCRBoard` | Board-level commands (firmware revision, serial number, communication path) |
| `MCRCom` | internal | Serial port communication — not for direct use |

**Example**

```python
import TheiaMCR as mcr

MCR = mcr.MCRControl('com4')
if not MCR.boardInitialized:
    print('Board not found. Check the COM port.')
else:
    print(f'Board initialized: {MCR.MCRInitialized}')
```

---

## Motor Initialization

### focusInit

```python
focusInit(steps, pi, move=True, accel=0, homingSpeed=-1) -> bool
```

Initialize the focus motor. Creates the `MCR.focus` motor instance. Must be called after board initialization.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `steps` | `int` | — | Maximum number of steps for the full focus range |
| `pi` | `int` | — | Step position of the photo interrupter (PI) limit switch |
| `move` | `bool` | `True` | `True` to move the motor to the home (PI) position during initialization; `False` to initialize without moving |
| `accel` | `int` | `0` | Motor acceleration steps. See firmware documentation for support (not currently supported v.5.3.1.2.0). |
| `homingSpeed` | `int` | `-1` | Speed (pps) to use when homing. Uses the default speed if set to `-1` or out of range. Defaults to 1200pps. |

**Returns** `True` if initialization succeeded, `False` otherwise.

**Example**

```python
# TL1250 lens
success = MCR.focusInit(steps=8390, pi=7959)

# Initialize without moving to home
success = MCR.focusInit(steps=8390, pi=7959, move=False)

# Set a custom homing speed
success = MCR.focusInit(steps=8390, pi=7959, homingSpeed=800)
```

---

### zoomInit

```python
zoomInit(steps, pi, move=True, accel=0, homingSpeed=-1) -> bool
```

Initialize the zoom motor. Creates the `MCR.zoom` motor instance. Must be called after board initialization.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `steps` | `int` | — | Maximum number of steps for the full zoom range |
| `pi` | `int` | — | Step position of the photo interrupter (PI) limit switch |
| `move` | `bool` | `True` | `True` to move the motor to the home (PI) position during initialization; `False` to initialize without moving |
| `accel` | `int` | `0` | Motor acceleration steps. See firmware documentation for support (not currently supported v.5.3.1.2.0). |
| `homingSpeed` | `int` | `-1` | Speed (pps) to use when homing. Uses the default speed if set to `-1` or out of range. Defaults to 1200pps. |

**Returns** `True` if initialization succeeded, `False` otherwise.

**Example**

```python
# TL1250 lens
success = MCR.zoomInit(steps=3227, pi=3119)

# TL410 lens (PI near step 0)
success = MCR.zoomInit(steps=4073, pi=154)
```

---

### irisInit

```python
irisInit(steps, move=True, homingSpeed=-1) -> bool
```

Initialize the iris motor. Creates the `MCR.iris` motor instance. The iris motor does not have a photo interrupter limit switch; it uses a hard stop at step 0 (fully open) for homing. Must be called after board initialization.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `steps` | `int` | — | Maximum number of steps (fully closed position) |
| `move` | `bool` | `True` | `True` to move the iris to the fully open (home) position during initialization; `False` to initialize without moving |
| `homingSpeed` | `int` | `-1` | Speed (pps) to use when homing. Uses the default speed if set to `-1` or out of range. Defaults to 100pps. |

**Returns** `True` if initialization succeeded, `False` otherwise.

**Example**

```python
success = MCR.irisInit(steps=75)
```

---

### IRCInit

```python
IRCInit() -> bool
```

Initialize the IRC (IR cut filter) motor. Creates the `MCR.IRC` motor instance. The IRC motor is a DC motor and is controlled differently from the stepper motors: it is driven for a fixed activation time rather than a step count.

At the default speed of 1000 pps, each step corresponds to approximately 1 ms of activation time. The maximum of 1000 steps gives 1 second of activation.

**Returns** `True` if initialization succeeded, `False` otherwise.

**Example**

```python
success = MCR.IRCInit()
```

---

## Closing the Connection

### close

```python
close()
```

Close the serial port and release all resources held by the MCR board instance. After calling `close()`, the `MCR` instance cannot be used again — create a new instance to reconnect.

**Example**

```python
MCR.close()
```

---

## Complete Initialization Example

```python
import TheiaMCR as mcr

# Initialize board
MCR = mcr.MCRControl('com4')
if not MCR.boardInitialized:
    print('Board not found')
    exit()

# Initialize motors (TL1250 lens)
MCR.focusInit(steps=8390, pi=7959)
MCR.zoomInit(steps=3227, pi=3119)
MCR.irisInit(steps=75)
MCR.IRCInit()

print(f'Focus at step: {MCR.focus.currentStep}')
print(f'Zoom at step:  {MCR.zoom.currentStep}')

# ... use the motors ...

MCR.close()
```
