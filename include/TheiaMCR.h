#ifndef THEIAMCR_H
#define THEIAMCR_H

#include <string>
#include <vector>
#include <memory>
#include <tuple>
#include <cstdint>
#include <filesystem>
#include "SimpleSerial.h"

namespace TheiaMCR {

constexpr const char* MCR_REVISION = "v.3.5.0";

class MCRControl; // Forward declaration

class Motor {
private:
    MCRControl* parent = nullptr;

public:
    uint8_t motorID = 0;
    int currentStep = 0;
    int maxSteps = 0;
    int PIStep = 0;
    int currentSpeed = 0;
    int homingSpeed = 0;   // speed used when seeking the PI home position
    int PISide = 1;        // 1 = PI at high end, -1 = PI at low end
    bool initialized = false;
    bool respectLimits = true;

    Motor();
    Motor(MCRControl* parent, uint8_t id);
    Motor(MCRControl* parent, uint8_t id, int steps, int pi);

    bool moveAbs(int steps, int speed = 0);
    bool moveRel(int steps, int speed = 0, bool correctForBL = true);
    bool home();
    int  setMotorSpeed(int speed);  // returns 0 on success, -1 if out of range
    int  setHomingSpeed(int speed);  // returns 0 on success, -1 if out of range
    bool setRespectLimits(bool state);  // focus/zoom only
    int state(int newState);  // IRC only: 1=visible, 2=clear filter
    std::tuple<bool, int, bool, bool, int, int, int, int> readMotorSetup();
    bool writeMotorSetup(bool useWideFarStop, bool useTeleNearStop, int maxSteps, int minSpeed, int maxSpeed);
};

class MCRControl {
    friend class Motor;

private:
    std::string serialPortName;
    bool boardInitialized = false;
    bool sendCmd(const std::vector<uint8_t>& cmd, std::vector<uint8_t>& response, int waitTimeMs = 10);

public:
    SimpleSerial serial;
    Motor focus;
    Motor zoom;
    Motor iris;
    Motor IRC;

    MCRControl(const std::string& portName,
               bool logFiles = true,
               bool moduleDebugLevel = false,
               bool communicationDebugLevel = false);
    ~MCRControl();

    bool isInitialized() const { return boardInitialized; }
    std::string readFWRevision();
    std::string readBoardSN();
    void close();
    void closeLogFiles();

    // Library-wide logging control (affects all instances)
    static void setLogLevel(int level); // 0=off 1=error 2=warn 3=info 4=debug 5=trace(comm)

    // Motor initialization methods
    bool focusInit(int steps, int pi, bool move = true, int accel = 0, int homingSpeed = -1);
    bool zoomInit(int steps, int pi, bool move = true, int accel = 0, int homingSpeed = -1);
    bool irisInit(int steps, bool move = true, int homingSpeed = -1);
    bool IRCInit();
};

} // namespace TheiaMCR

#endif // THEIAMCR_H
