// Example for using the TheiaMCR C++ module (native C++ API).
// This example uses TheiaMCR.h directly — the same C++ class that pybind11 exposes to Python.
//
// BUILD THIS EXAMPLE:
//   cd build
//   cmake -DBUILD_EXAMPLES=ON ..
//   cmake --build .
//   Run the compiled binary: build/Debug/Example_3.5.exe  (Windows)
//                            build/Example_3.5            (Linux)
//
// NOTE: C++ examples must be compiled before running — unlike Python scripts
//       they cannot be executed directly from the terminal without building first.
//
// A MCR600-series control board must be connected to the computer via USB.
// Set the 'comport' variable in main() below.
//
// Updated for MCR version 3.4

#include "TheiaMCR.h"
#include <iostream>
#include <string>
#include <thread>
#include <chrono>

static void sleep_ms(int ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

// Initialize board and motors.
// Returns a heap-allocated MCRControl pointer, or nullptr on failure.
// Caller must call MCR->close() and delete MCR when done.
TheiaMCR::MCRControl* init(const std::string& comport,
                            const std::string& lensType = "TL1250",
                            bool moduleDebugLevel = false) {
    auto* MCR = new TheiaMCR::MCRControl(comport, true, moduleDebugLevel, false);
    if (!MCR->isInitialized()) {
        std::cerr << "Error: Board not initialized. Check com port: " << comport << "\n";
        delete MCR;
        return nullptr;
    }

    std::cout << "Firmware: " << MCR->readFWRevision() << "\n";

    // Initialize motors (lens-specific step counts and PI home positions).
    // These values come from the lens specification sheet.
    if (lensType == "TL1250") {
        MCR->focusInit(8390, 7959);   // steps, PI home position
        MCR->zoomInit(3227, 3119);
    } else {  // TL410
        MCR->focusInit(9353, 8652);
        MCR->zoomInit(4073, 154);
    }
    MCR->irisInit(75);
    MCR->IRCInit();

    std::cout << "Board initialized: " << MCR->isInitialized() << "\n";
    sleep_ms(1000);
    return MCR;
}

// Example 1: Initialize board and confirm firmware
void initExample(const std::string& comport, const std::string& lensType) {
    auto* MCR = init(comport, lensType);
    if (!MCR) return;

    char snBuf[32] = {};
    std::string sn = MCR->readBoardSN();
    std::cout << "Board SN: " << sn << "\n";

    MCR->close();
    delete MCR;
}

// Example 2: Move motors — focus, zoom, iris, IRC
void moveMotorsExample(const std::string& comport, const std::string& lensType) {
    auto* MCR = init(comport, lensType);
    if (!MCR) return;

    // Move focus motor to an absolute step position
    std::cout << "Moving focus absolute to step 6000\n";
    MCR->focus.moveAbs(6000);
    std::cout << "Focus step: " << MCR->focus.currentStep << "\n";
    sleep_ms(1000);

    // Move focus motor by a relative number of steps
    std::cout << "Moving focus relative -1000 steps\n";
    MCR->focus.moveRel(-1000);
    std::cout << "Focus step: " << MCR->focus.currentStep << "\n";
    sleep_ms(2000);

    // Move zoom motor at a reduced speed
    int direction = (lensType == "TL1250") ? -1 : 1;
    std::cout << "Moving zoom " << direction * 600 << " steps at 600 pps\n";
    MCR->zoom.setMotorSpeed(600);
    MCR->zoom.moveRel(direction * 600);
    std::cout << "Zoom step: " << MCR->zoom.currentStep << "\n";
    sleep_ms(2000);

    // Close iris by 40 steps
    std::cout << "Closing iris 40 steps\n";
    MCR->iris.moveRel(40);
    std::cout << "Iris step: " << MCR->iris.currentStep << "\n";
    sleep_ms(2000);

    // Switch IRC filter (1 = visible/IR-cut, 2 = clear filter)
    std::cout << "Setting IRC state 1\n";
    MCR->IRC.state(1);
    sleep_ms(1000);

    // Reset to defaults
    MCR->zoom.setMotorSpeed(1200);
    MCR->iris.home();
    MCR->IRC.state(0);
    std::cout << "Reset complete. Focus and zoom remain at set positions.\n";

    MCR->close();
    delete MCR;
}

// Example 3: Read and write motor configuration (EEPROM)
void motorConfigurationExample(const std::string& comport) {
    auto* MCR = init(comport);
    if (!MCR) return;

    // Write configuration to the zoom motor
    int setMaxSteps = 9000, setMinSpeed = 200, setMaxSpeed = 1200;
    std::cout << "Writing zoom config: maxSteps=" << setMaxSteps
              << " speed=(" << setMinSpeed << "," << setMaxSpeed << ")\n";
    MCR->zoom.writeMotorSetup(true, false, setMaxSteps, setMinSpeed, setMaxSpeed);
    sleep_ms(500);

    // Read it back
    auto [ok, motorType, leftStop, rightStop, maxSteps, minSpeed, maxSpeed, errorVal]
        = MCR->zoom.readMotorSetup();
    if (ok) {
        std::cout << "Motor type: " << motorType
                  << "  maxSteps: " << maxSteps
                  << "  speed: (" << minSpeed << "," << maxSpeed << ")\n";
    } else {
        std::cerr << "Error reading motor config\n";
    }

    MCR->close();
    delete MCR;
}

// Example 4: Disable PI limit to allow movement past the home position
void limitsExample(const std::string& comport, const std::string& lensType) {
    auto* MCR = init(comport, lensType);
    if (!MCR) return;

    // Home focus motor
    std::cout << "Homing focus motor to PI position " << MCR->focus.PIStep << "\n";
    MCR->focus.home();
    std::cout << "Focus at " << MCR->focus.currentStep << " (home)\n";
    sleep_ms(1000);

    // Move beyond PI position (limits must be disabled first)
    std::cout << "Disabling PI limit and moving 200 steps past home\n";
    MCR->focus.setRespectLimits(false);
    MCR->focus.moveRel(200, 0, false);  // correctForBL=false to avoid backlash adjustment
    std::cout << "Focus at " << MCR->focus.currentStep << "\n";
    sleep_ms(2000);

    // Return to home and re-enable limits
    MCR->focus.home();
    MCR->focus.setRespectLimits(true);
    std::cout << "Focus at " << MCR->focus.currentStep << " (home)\n";

    MCR->close();
    delete MCR;
}


int main() {
    // ---------------------------------------------------------------
    // Set your com port:
    //   Windows: "COM4"   (check Device Manager for the correct port)
    //   Linux:   "/dev/ttyUSB0"
    // ---------------------------------------------------------------
    const std::string comport = "COM4";

    // Lens type: "TL1250" or "TL410"
    const std::string lensType = "TL1250";

    // ---------------------------------------------------------------
    // Uncomment the example(s) you want to run:
    // ---------------------------------------------------------------

    // Example 1: Initialize board and print firmware / serial number
    // initExample(comport, lensType);

    // Example 2: Move focus, zoom, iris, and IRC motors
    moveMotorsExample(comport, lensType);

    // Example 3: Read / write motor configuration from EEPROM
    // motorConfigurationExample(comport);

    // Example 4: Move past the PI home position (limits disabled)
    // limitsExample(comport, lensType);

    return 0;
}
