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

Choose the installation method based on your language and requirements:

### Option 1: C++ (Native)

Build the native C++ library and examples:

```bash
cd build
cmake -DBUILD_EXAMPLES=ON ..
cmake --build .
```

**Requirements:**
- C++17 compatible compiler (MSVC, GCC, or Clang)
- CMake 3.15 or later
- Windows, Linux, or macOS

### Option 2: Python (pip — pure Python, no compilation)

For maximum simplicity with no build step required:

```bash
pip install TheiaMCR
```

**Requirements:**
- Python 3.9 or later
- `pyserial`

This is the recommended approach for most Python users.

### Option 3: Python (pybind11 — compiled, maximum performance)

Build the high-performance Python module from this C++ source:

```bash
cd build
cmake ..
cmake --build .
```

Then import the module:

```python
import sys
sys.path.append("build/Debug")  # or build/Release on Linux
import TheiaMCR_py as mcr
```

**Requirements:**
- C++17 compatible compiler
- CMake 3.15 or later
- Python 3.9 or later

This option provides near-C++ performance and is useful if you need advanced features or maximum speed.

---

## Quick Start

### C++ Example

```cpp
#include "TheiaMCR.h"
#include <iostream>
#include <thread>
#include <chrono>

int main() {
    const char* comport = "COM4";  // Set to your board's COM port
    
    // 1. Create MCRControl instance (opens the board connection)
    auto MCR = new TheiaMCR::MCRControl(comport, true, false, false);
    if (!MCR->isInitialized()) {
        std::cerr << "Board not found. Check the COM port." << std::endl;
        delete MCR;
        return 1;
    }
    
    // 2. Initialize motors (TL1250 lens)
    MCR->focusInit(8390, 7959);
    MCR->zoomInit(3227, 3119);
    MCR->irisInit(75);
    MCR->IRCInit();
    
    // 3. Move motors
    MCR->focus.moveAbs(4000);     // move focus to step 4000
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    MCR->zoom.moveRel(-500);      // move zoom 500 steps toward tele
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    MCR->iris.moveAbs(40);        // move iris to step 40
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    MCR->IRC.state(1);            // set IRC to visible (IR-blocking) filter
    
    // 4. Close when done
    MCR->close();
    delete MCR;
    return 0;
}
```

### Python Example (pip or pybind11)

For the pure Python `TheiaMCR` package from PyPI:

```python
import TheiaMCR as mcr

# 1. Open the board connection
MCR = mcr.MCRControl('COM4')
if not MCR.boardInitialized:
    print('Board not found. Check the COM port.')

# 2. Initialize motors (TL1250 lens)
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

For the compiled pybind11 module, use the same Python code but import as:

```python
import sys
sys.path.append("build/Debug")  # Path to compiled module
import TheiaMCR_py as mcr
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

Check error codes directly:

```cpp
#include "TheiaMCR.h"
#include <iostream>

int main() {
    auto MCR = new TheiaMCR::MCRControl("COM4", true, false, false);
    MCR->focusInit(8390, 7959);
    
    int result = MCR->focus.moveAbs(1000);
    if (result != 0) {  // 0 = ERR_OK
        std::cerr << "Move failed: " << result << std::endl;
    }
    
    MCR->close();
    delete MCR;
    return 0;
}
```

---

## Logging

TheiaMCR uses [spdlog](https://github.com/gabime/spdlog) for logging. Log files are saved to the user's local application data directory by default. For example on Windows: C:\Users\<USER>\AppData\Local\TheiaMCR\log

Control logging behavior when creating the MCRControl instance:

```cpp
// Enable debug-level console output
auto MCR = new TheiaMCR::MCRControl("COM4", true, false, false);

// Show all serial port traffic (not recommended in production)
auto MCR = new TheiaMCR::MCRControl("COM4", false, true, false);

// Disable log file creation
auto MCR = new TheiaMCR::MCRControl("COM4", false, false, false);
```

Set the library-wide log level:

```cpp
// Log levels: 0=off, 1=error, 2=warn, 3=info, 4=debug, 5=trace
TheiaMCR::MCRControl::setLogLevel(3);  // 3 = info
```
