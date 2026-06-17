# TheiaMCR_C — C++ Motor Control Board Interface

[Theia Technologies](https://www.theiatech.com) offers the [MCR IQ 400 motor control board](https://www.theiatech.com/lenses/accessories/mcr/) for controlling motorized lenses. This board drives focus, zoom, iris, and IRC filter motors and connects to a host computer over USB, UART, or I2C.

This repository is the C++ port of the [TheiaMCR Python module](https://github.com/cliquot22/TheiaMCR). It provides:
- A native **C++ library** (`TheiaMCR.h / TheiaMCR.cpp`) with the full motor control API
- A **C-linkage shared library** (`TheiaMCR_C.dll` / `libTheiaMCR_C.so`) callable from C, C++, or any language that loads shared libraries (e.g. Python `ctypes`, LabVIEW, MATLAB)
- A **pybind11 Python module** (`TheiaMCR_py.pyd`) with native-speed Python bindings to the same C++ class

---

## Which version should I use?

| Use case | Recommended module |
|---|---|
| Writing a **C++ application** | `TheiaMCR.h` — native C++ class, full API |
| Calling from **C**, LabVIEW, MATLAB, or any non-Python language | `TheiaMCR_C.dll` — C-linkage shared library via `TheiaMCR_C.h` |
| Writing a **Python script** that needs maximum performance or access to the full C++ API | `TheiaMCR_py` — pybind11 module (built alongside the C library) |
| Writing a **Python script** using only pip, no compilation needed | [`TheiaMCR` on PyPI](https://github.com/cliquot22/TheiaMCR) — pure-Python package |

**TheiaMCR_C.cpp** implements the flat C-linkage wrapper (`MCR_Create`, `MCR_Focus_MoveAbs`, etc.). Use it when you need a stable ABI that any language can call without a C++ compiler or Python interpreter on the target.

**TheiaMCR_pybind11.cpp** exposes the native C++ class directly to Python. The resulting `TheiaMCR_py` module mirrors the Python `TheiaMCR` package API almost exactly, so existing Python code is easy to port, while running at native C++ speed. Choose this when Python is your target language and you want the full feature set with no pip dependency.

---

## Getting theiaMCR_C

Unlike other languages, C++ does not have a standard built-in package manager like Python's pip. Because of this, the standard and most direct method to integrate the `theiaMCR_C` library into your project is to download the package structure directly without requiring external registries.

### 1. Download prebuilt packages
Prebuilt binaries compiled for common platforms are published with each release. 
1. Navigate to the [Releases](https://github.com/cliquot22/TheiaMCR_C/releases) page on GitHub.
2. Under **Assets** for the latest release, download the package matching your environment:
   - `theiaMCR_C-v{version}-windows-x64.zip` (for 64-bit Windows)
   - `theiaMCR_C-v{version}-linux-x64.zip` (for 64-bit Linux)
   - `theiaMCR_C-v{version}-source.zip` (if you wish to build it yourself from source)
3. Extract the downloaded `.zip` file. The archive contains:
   - `include/` — All header files needed to reference functions in your code.
   - `lib/` — Compiled library binaries (`.dll` and `.lib` for Windows, `.so` for Linux).

---

## Integrating Prebuilt Binaries into Your Project

To use the prebuilt binaries in your own projects, you simply need to point your build tool or IDE to the unzipped folders:

### Option A: Using CMake (Recommended)
If your project uses CMake, add the following pattern to your `CMakeLists.txt` (substituting the path to where you unzipped the package):

```cmake
# Define the path to your extracted package
set(THEIA_SDK_DIR "/path/to/extracted/theiaMCR_C")

# Include the headers directory
target_include_directories(your_target PRIVATE "${THEIA_SDK_DIR}/include")

# Link the binary library
# On Windows, you link the .lib import library and ensure the .dll is placed alongside your executable.
# On Linux, link the shared object (.so) directly.
find_library(THEIA_MCR_LIB TheiaMCR_C HINTS "${THEIA_SDK_DIR}/lib")
target_link_libraries(your_target PRIVATE ${THEIA_MCR_LIB})
```

### Option B: Using Visual Studio (Windows)
1. Open your project **Properties** in Visual Studio.
2. Go to **C/C++ -> General -> Additional Include Directories** and add the path to the unzipped `include/` directory.
3. Go to **Linker -> General -> Additional Library Directories** and add the path to the unzipped `lib/` directory.
4. Go to **Linker -> Input -> Additional Dependencies** and append `TheiaMCR_C.lib`.
5. Ensure `TheiaMCR_C.dll` is copied into your final output directory alongside your compiled `.exe` before running.

---

## Building from Source

If you want to build the SDK from source instead of using prebuilt binaries:

### Prerequisites
- A C++ compiler: MSVC (Visual Studio) on Windows, or GCC/Clang on Linux.
- CMake ≥ 3.15.

### Building
1. Download and unzip the `theiaMCR_C-v{version}-source.zip` or clone the repository.
2. From the root directory, configure and build using CMake:

```bash
# Configure the build system (produces Release configuration files)
cmake -B build -DCMAKE_BUILD_TYPE=Release

# Compile the library
cmake --build build --config Release
```

The resulting library binaries will be located under your `build/` (or `build/Release/`) folder.

---

## Features

The MCR IQ 400 board (and MCR IQ 600, MCR IQ 500, and others in the MCR series) uses a proprietary byte-string command protocol. This library formats and sends those commands automatically. For example, calling `focus.moveAbs(6000)` converts the request into the correct byte string and sends it over the USB virtual COM port, causing the lens motor to move to step 6000.

### Motor initialization

After creating the control object, initialize each motor with its lens-specific step count and PI home position (from the lens specification sheet):

**C++ (native API)**
```cpp
#include "TheiaMCR.h"
TheiaMCR::MCRControl MCR("COM4");
// TL1250 lens parameters:
MCR.focusInit(8390, 7959);
MCR.zoomInit(3227, 3119);
MCR.irisInit(75);
MCR.IRCInit();
```

**Python (pybind11 module)**
```python
import sys; sys.path.append("build/Debug")
import TheiaMCR_py as mcr
MCR = mcr.MCRControl("COM4")
MCR.focusInit(8390, 7959)
MCR.zoomInit(3227, 3119)
MCR.irisInit(75)
MCR.IRCInit()
```

**Python (ctypes, C-linkage library)**
```python
import ctypes
lib = ctypes.CDLL("./TheiaMCR_C.dll")  # or libTheiaMCR_C.so on Linux
lib.MCR_Create.restype = ctypes.c_void_p
lib.MCR_Create.argtypes = [ctypes.c_char_p]
lib.MCR_Focus_MoveAbs.restype = ctypes.c_int
lib.MCR_Focus_MoveAbs.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

handle = lib.MCR_Create(b"COM4")
if lib.MCR_IsInitialized(handle):
    lib.MCR_Focus_MoveAbs(handle, 6000, 1200)
lib.MCR_Destroy(handle)
```

---

## Motor limits (lens parameters)

| Lens | `focusInit` | `zoomInit` | `irisInit` |
|---|---|---|---|
| TL1250 (-N) | `focusInit(8390, 7959)` | `zoomInit(3227, 3119)` | `irisInit(75)` |
| TL410 (-R) | `focusInit(9353, 8652)` | `zoomInit(4073, 154)` | `irisInit(75)` |

The PI position is the photo-interrupter home step. After homing, `currentStep` is set to `PIStep`. The motor can then travel from 0 (hard stop) through `PIStep` to `maxSteps` (hard stop). Hitting either hard stop causes a step-count mismatch; re-home the lens to recover.

Motor init parameters (all motors):
- `steps` — total steps in the full range of movement
- `pi` — photo-interrupter home step position
- `move` (default `true`) — move to home position during initialization
- `homingSpeed` (default: motor default) — speed in pps used when homing
- `accel` (focus/zoom, default `0`) — acceleration steps (reserved for future hardware)

---

## Motor functions

Each motor (`focus`, `zoom`, `iris`) supports:

| Function | Description |
|---|---|
| `motor.home()` | Move to the PI limit-switch home position |
| `motor.moveAbs(step)` | Move to an absolute step number |
| `motor.moveRel(steps, correctForBL=true)` | Move by a relative number of steps with optional backlash correction |
| `motor.setMotorSpeed(speed)` | Set speed in pps (focus/zoom: 100–1500; iris: 10–200) |
| `motor.setHomingSpeed(speed)` | Set homing speed in pps |
| `motor.setRespectLimits(state)` | Enable/disable enforcement of the PI limit position |
| `motor.readMotorSetup()` | Read motor configuration from board EEPROM |
| `motor.writeMotorSetup(...)` | Write motor configuration to board EEPROM |

IRC filter: `MCR.IRC.state(1)` (visible/IR-cut) or `MCR.IRC.state(2)` (clear filter).

### Motor variables

| Variable | Description |
|---|---|
| `currentStep` | Current motor step number |
| `currentSpeed` | Current speed in pps |
| `homingSpeed` | Speed used when homing to PI position |
| `maxSteps` | Maximum steps for the full travel range |
| `PIStep` | PI limit-switch step position |
| `PISide` | `1` if PI is on the high step side, `-1` if on the low side |
| `respectLimits` | When `true`, moves are prevented from passing the PI limit |

---

## Board functions

| Function | Description |
|---|---|
| `MCR.readFWRevision()` | Returns firmware version string (e.g. `"5.3.1.0.0"`) |
| `MCR.readBoardSN()` | Returns board serial number string |
| `MCR.close()` | Close the serial port and release resources |
| `MCR.closeLogFiles()` | Stop logging to file; console logging continues |
| `MCRControl::setLogLevel(level)` | Library-wide log level: 0=off 1=error 2=warn 3=info 4=debug 5=trace |

---

## Examples

See the `Examples/` folder:

| File | Description |
|---|---|
| `Examples/cpp/Example_3.5.cpp` | Native C++ example — build with `cmake -DBUILD_EXAMPLES=ON ..` |
| `Examples/python/Example_3.5.py` | Python pybind11 example — run after building the `TheiaMCR_py` target |

---

## Logging

The library uses [spdlog](https://github.com/gabime/spdlog) for logging. Control the log level:

```cpp
// C++
TheiaMCR::MCRControl::setLogLevel(3);  // 3 = info
```
```python
# Python (pybind11)
mcr.setLogLevel(3)
```

Log levels: 0=off, 1=error, 2=warn, 3=info, 4=debug, 5=trace (shows raw byte communication).

---

## See also

- [TheiaMCR Python package (PyPI)](https://github.com/cliquot22/TheiaMCR) — pure-Python version, install with `pip install TheiaMCR`
- [MCR IQ 400 documentation](https://www.theiatech.com/lenses/accessories/mcr/)

---

## License

[Theia Technologies BSD-3-Clause license](https://github.com/cliquot22/TheiaMCR/blob/main/LICENSE)  
Copyright 2023–2026 Theia Technologies

## Contact

Mark Peterson — Theia Technologies  
[mpeterson@theiatech.com](mailto:mpeterson@theiatech.com)

## Revision

v.3.5
