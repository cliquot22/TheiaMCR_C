These functions move the focus, zoom, and iris stepper motors, and set the IRC filter position. All movement functions are called on the motor instance (e.g. `MCR.focus.moveAbs(1000)`).

> **Note:** The iris motor does not have a photo interrupter (PI) limit switch. The IRC motor is a DC motor and only supports the `state()` function — not `home()`, `moveAbs()`, or `moveRel()`.

---

## Move Responses

Every movement command returns an integer status code. A return value of `0` (`ERR_OK`) indicates success. Negative values indicate an error. See the [error code table](https://github.com/cliquot22/TheiaMCR/wiki#error-codes) on the Home page.

**Checking for stale responses:** The MCR board response buffer is not automatically cleared. To confirm a response belongs to the most recent move command, request the firmware revision or board serial number immediately before reading the move response. This changes the first response byte from `0x74` (move response) to a different value, so a leading `0x74` byte can be confidently attributed to the latest move.

```python
MCR.focus.home()                        # response starts with 0x74
MCR.MCRBoard.readFWRevision()           # response starts with 0x76
MCR.focus.moveAbs(1000)                 # response starts with 0x74
```

If a move fails, check `MCR.boardCommunicationState` to see whether the COM port is still connected. The number of automatic reconnections is counted in `MCR.boardCommunicationRestarts`.

---

## home

```python
home() -> int
```

`motor` class function. Send the motor to its home position — the step number of the photo interrupter (PI) limit switch position. After a successful home move, `motor.currentStep` is set to `motor.PIStep`.

If the current step is already beyond the PI position, the motor first moves away from the PI before seeking it again. This ensures the PI trigger is a clean approach.

The `respectLimits` flag is temporarily set to `True` for the homing move and then restored to its previous value.

> Not supported for the IRC motor.

**Parameters** None.

**Returns**

| Value | Meaning |
|-------|---------|
| `0` | Success |
| `-62` (`ERR_BAD_MOVE`) | PI was not triggered (call motor init first, or check wiring) |
| `-73` (`ERR_NOT_SUPPORTED`) | Function not supported for this motor |

**Example**

```python
result = MCR.focus.home()
if result == 0:
    print(f'Focus homed to step {MCR.focus.currentStep}')
```

---

## moveAbs

```python
moveAbs(step) -> int
```

`motor` class function. Move the motor to an absolute step position. The firmware uses the PI limit switch as a reference: the motor first travels to the home (PI) position and then moves to the target step from there. This approach guarantees accurate, repeatable absolute positioning regardless of where the motor started.

If `respectLimits` is `True` (the default), the target step cannot exceed the PI step position. If `respectLimits` is `False`, the motor can move beyond the PI position in two segments: the first move goes to the PI, and the second continues past it to reach the target.

> Not supported for the IRC motor.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `step` | `int` | Target step number to move to. Must be ≥ 0 and ≤ `motor.maxSteps`. |

**Returns**

| Value | Meaning |
|-------|---------|
| `0` | Success |
| `-62` (`ERR_BAD_MOVE`) | Move failed (homing error or communication error) |
| `-69` (`ERR_RANGE`) | Target step is negative (out of range) |
| `-73` (`ERR_NOT_SUPPORTED`) | Function not supported for this motor |

> If the target exceeds `maxSteps`, it is silently clipped to `maxSteps` with a warning logged.

**Example**

```python
# Move focus to step 4000
result = MCR.focus.moveAbs(4000)
```

---

## moveRel

```python
moveRel(steps, correctForBL=True) -> int
```

`motor` class function. Move the motor by a relative number of steps from its current position. 

**Backlash correction:** When moving toward the PI position (`correctForBL=True`), the motor overshoots by up to 60 steps and then moves back. This compensates for mechanical backlash and ensures the final position is approached consistently from the same direction.  When moving away from the PI home position, there is no overshoot process and the motor ends at the target position.  

If `respectLimits` is `True`, the move is clipped to the PI step position limit. If `respectLimits` is `False`, the move is clipped to the hard stop (`maxSteps` / 0). Exceeding the hard stop will cause the step counter to be incorrect, requiring re-initialization.

> Not supported for the IRC motor.

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `steps` | `int` | — | Number of steps to move. Positive = away from PI; negative = toward PI. |
| `correctForBL` | `bool` | `True` | Set `True` to apply backlash compensation when moving toward the PI. |

**Returns**

| Value | Meaning |
|-------|---------|
| `0` | Success |
| `-62` (`ERR_BAD_MOVE`) | Move failed |
| `-73` (`ERR_NOT_SUPPORTED`) | Function not supported for this motor |

**Example**

```python
# Move focus +500 steps (with default backlash correction)
result = MCR.focus.moveRel(500)

# Move zoom -200 steps with no backlash correction
result = MCR.zoom.moveRel(-200, correctForBL=False)
```

---

## IRC.state

```python
IRC.state(state) -> int
```

`motor` class function. Set the IRC (IR cut filter) switch to the visible or clear filter position (or other internal filters depending on the lens model). The IRC motor is a DC motor that activates for a fixed time — it is not position-controlled like the stepper motors. The activation duration is set by `IRCInit()` (default: 50 ms).

> Only supported for the IRC motor. Calling `state()` on a stepper motor returns `ERR_NOT_SUPPORTED`.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `state` | `int` | `1` = visible (IR-blocking) filter; `2` = clear filter |

**Returns**

| Value | Meaning |
|-------|---------|
| `1` or `2` | New state (matches the input on success) |
| `-62` (`ERR_BAD_MOVE`) | Move failed |
| `-73` (`ERR_NOT_SUPPORTED`) | Called on a non-IRC motor |

**Example**

```python
# Switch to IR-blocking (visible light) filter
MCR.IRC.state(1)

# Switch to clear (full spectrum) filter
MCR.IRC.state(2)
```
