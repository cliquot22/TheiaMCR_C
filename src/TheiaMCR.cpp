#include "TheiaMCR.h"
#include <iostream>
#include <chrono>
#include <thread>
#include <cmath>
#include <spdlog/spdlog.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/sinks/null_sink.h>

// Internal logging helpers — not exposed in the public header
#define MCR_LOG_INFO(...)  do { if(g_logger) g_logger->info(__VA_ARGS__);  } while(0)
#define MCR_LOG_WARN(...)  do { if(g_logger) g_logger->warn(__VA_ARGS__);  } while(0)
#define MCR_LOG_ERROR(...) do { if(g_logger) g_logger->error(__VA_ARGS__); } while(0)
#define MCR_LOG_DEBUG(...) do { if(g_logger) g_logger->debug(__VA_ARGS__); } while(0)
#define MCR_LOG_TRACE(...) do { if(g_logger) g_logger->trace(__VA_ARGS__); } while(0)

namespace {
    std::shared_ptr<spdlog::logger> g_logger;
    std::shared_ptr<spdlog::sinks::rotating_file_sink_mt> g_fileSink;

    std::string getLogDir() {
#ifdef _WIN32
        const char* base = std::getenv("LOCALAPPDATA");
        return std::string(base ? base : ".") + "\\TheiaMCR\\log";
#else
        const char* home = std::getenv("HOME");
        return std::string(home ? home : ".") + "/.local/share/TheiaMCR/log";
#endif
    }

    void initLogger(bool logFiles, bool moduleDebugLevel, bool communicationDebugLevel) {
        // Determine log level
        spdlog::level::level_enum level = spdlog::level::info;
        if (communicationDebugLevel)
            level = spdlog::level::trace;
        else if (moduleDebugLevel)
            level = spdlog::level::debug;

        std::vector<spdlog::sink_ptr> sinks;

        // Console sink (always on)
        auto consoleSink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
        consoleSink->set_level(level);
        consoleSink->set_pattern("[%H:%M:%S.%e] [%^%5l%$] TheiaMCR: %v");
        sinks.push_back(consoleSink);

        // File sink (only when logFiles=true)
        if (logFiles) {
            try {
                std::string logDir = getLogDir();
                std::filesystem::create_directories(logDir);
                std::string logPath = logDir +
#ifdef _WIN32
                    "\\TheiaMCR.log";
#else
                    "/TheiaMCR.log";
#endif
                g_fileSink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
                    logPath, 1024 * 1024 * 2, 5); // 2MB, 5 rotating files
                g_fileSink->set_level(level);
                g_fileSink->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%l] TheiaMCR: %v");
                sinks.push_back(g_fileSink);
            } catch (const std::exception& e) {
                std::cerr << "TheiaMCR: Could not create log file: " << e.what() << "\n";
            }
        }

        g_logger = std::make_shared<spdlog::logger>("TheiaMCR", sinks.begin(), sinks.end());
        g_logger->set_level(level);
        g_logger->flush_on(spdlog::level::warn);
        spdlog::register_logger(g_logger);
    }
} // anonymous namespace

namespace TheiaMCR {

// Motor implementation
Motor::Motor() : parent(nullptr), motorID(0) {}

Motor::Motor(MCRControl* parent, uint8_t id) : parent(parent), motorID(id) {}

Motor::Motor(MCRControl* parent, uint8_t id, int steps, int pi)
    : parent(parent), motorID(id), maxSteps(steps), PIStep(pi), initialized(true) {
    PISide = ((steps - pi) < pi) ? 1 : -1;
}

bool Motor::moveAbs(int steps, int speed) {
    if (!parent || !initialized) return false;
    if (speed == 0) speed = currentSpeed;
    if (speed == 0) speed = (motorID == 0x03) ? 100 : 1200;
    MCR_LOG_DEBUG("moveAbs motor={:#04x} steps={} speed={}", motorID, steps, speed);

    static const int MCR_HARDSTOP_TOLERANCE = 200;

    uint8_t cmdByte = 0x73; // Built-in absolute move command
    int stepDist = std::abs(PIStep - steps);

    if (motorID == 0x03) { // Iris
        // Iris has no home switch, so move home (0x66 max) first, then relative back
        uint8_t homeCmd[8] = {0x66, motorID, static_cast<uint8_t>((maxSteps >> 8) & 0xFF), static_cast<uint8_t>(maxSteps & 0xFF), 1, static_cast<uint8_t>((speed >> 8) & 0xFF), static_cast<uint8_t>(speed & 0xFF), 0x0D};
        std::vector<uint8_t> irisCmd(homeCmd, homeCmd + 8);
        std::vector<uint8_t> irisResp;
        // v.3.5.1 bug fix: check error propagation from sendCmd
        if (!parent->sendCmd(irisCmd, irisResp, 1000)) {
            MCR_LOG_WARN("moveAbs motor={:#04x} iris home command failed", motorID);
            return false;
        }

        cmdByte = 0x62;
        stepDist = steps;
    }

    std::vector<uint8_t> cmd(8);
    cmd[0] = cmdByte;
    cmd[1] = motorID;
    cmd[2] = (stepDist >> 8) & 0xFF;
    cmd[3] = stepDist & 0xFF;
    cmd[4] = 1;
    cmd[5] = (speed >> 8) & 0xFF;
    cmd[6] = speed & 0xFF;
    cmd[7] = 0x0D;

    // For focus/zoom: if current position is past the PI switch, move back first so 0x73 can seek PI.
    // This matches Python moveAbs pre-move logic when calling moveAbs directly (not via home()).
    if (motorID != 0x03) {
        bool pastPI = (PISide == 1 && currentStep > PIStep) ||
                      (PISide == -1 && currentStep < PIStep);
        if (pastPI && steps <= PIStep) {
            int awaySteps = std::abs(currentStep - PIStep) + MCR_HARDSTOP_TOLERANCE;
            uint8_t backDir = (PISide == 1) ? 0x62 : 0x66;
            std::vector<uint8_t> backCmd(8);
            backCmd[0] = backDir;
            backCmd[1] = motorID;
            backCmd[2] = (awaySteps >> 8) & 0xFF;
            backCmd[3] = awaySteps & 0xFF;
            backCmd[4] = 1;
            backCmd[5] = (speed >> 8) & 0xFF;
            backCmd[6] = speed & 0xFF;
            backCmd[7] = 0x0D;
            std::vector<uint8_t> backResp;
            int backWait = static_cast<int>((awaySteps / static_cast<double>(speed)) * 1000 * 1.15) + 500;
            MCR_LOG_DEBUG("moveAbs motor={:#04x} backing away {} steps before homing", motorID, awaySteps);
            // v.3.5.1 bug fix: check error propagation from sendCmd
            if (!parent->sendCmd(backCmd, backResp, backWait)) {
                MCR_LOG_WARN("moveAbs motor={:#04x} backing away command failed", motorID);
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
    }

    std::vector<uint8_t> resp;
    int waitTimeMs = static_cast<int>(((stepDist + maxSteps) / static_cast<double>(speed)) * 1000 * 1.30);
    bool success = parent->sendCmd(cmd, resp, waitTimeMs);
    if (success) {
        currentStep = steps;
        MCR_LOG_DEBUG("moveAbs motor={:#04x} arrived at step={}", motorID, currentStep);
    } else {
        MCR_LOG_WARN("moveAbs motor={:#04x} failed", motorID);
    }
    return success;
}

bool Motor::moveRel(int steps, int speed, bool correctForBL) {
    if (!parent || !initialized || steps == 0) return false;
    if (speed == 0) speed = currentSpeed;
    if (speed == 0) speed = (motorID == 0x03) ? 100 : 1200;
    MCR_LOG_DEBUG("moveRel motor={:#04x} steps={} speed={} BL={}", motorID, steps, speed, correctForBL);

    static const int MCR_BACKLASH_OVERSHOOT = 60;

    uint8_t cmdByte;
    int absSteps = std::abs(steps);

    if (motorID == 0x03) { // Iris
        cmdByte = (steps >= 0) ? 0x62 : 0x66;
    } else {
        cmdByte = (steps >= 0) ? 0x66 : 0x62;
    }

    std::vector<uint8_t> cmd(8);
    cmd[0] = cmdByte;
    cmd[1] = motorID;
    cmd[2] = (absSteps >> 8) & 0xFF;
    cmd[3] = absSteps & 0xFF;
    cmd[4] = 1;
    cmd[5] = (speed >> 8) & 0xFF;
    cmd[6] = speed & 0xFF;
    cmd[7] = 0x0D;

    std::vector<uint8_t> resp;
    int waitTimeMs = static_cast<int>((absSteps / static_cast<double>(speed)) * 1000 * 1.15);

    // Backlash correction: if moving towards PI, overshoot then move back
    bool movingTowardPI = (steps * PISide > 0);
    if (correctForBL && movingTowardPI && motorID != 0x03) {
        int limitPos = respectLimits ? PIStep : (PISide == 1 ? maxSteps : 0);
        int blCorrection = std::max(0, std::min(MCR_BACKLASH_OVERSHOOT,
            std::abs(limitPos - (currentStep + steps))));

        // Overshoot move
        int overshootSteps = absSteps + blCorrection;
        cmd[2] = (overshootSteps >> 8) & 0xFF;
        cmd[3] = overshootSteps & 0xFF;
        int overshootWait = static_cast<int>((overshootSteps / static_cast<double>(speed)) * 1000 * 1.15);
        bool success = parent->sendCmd(cmd, resp, overshootWait);
        if (success && blCorrection > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            // Move back by blCorrection
            uint8_t backCmd = (cmdByte == 0x66) ? 0x62 : 0x66;
            cmd[0] = backCmd;
            cmd[2] = (blCorrection >> 8) & 0xFF;
            cmd[3] = blCorrection & 0xFF;
            int backWait = static_cast<int>((blCorrection / static_cast<double>(speed)) * 1000 * 1.15);
            success = parent->sendCmd(cmd, resp, backWait);
        }
        if (success) currentStep += steps;
        return success;
    }

    bool success = parent->sendCmd(cmd, resp, waitTimeMs);
    if (success) {
        currentStep += steps;
    }
    return success;
}

bool Motor::home() {
    if (!parent || !initialized) return false;
    if (motorID == 0x03) { // Iris uses moveAbs directly
        int speed = 100;
        return moveAbs(0, speed);
    }

    static const int MCR_HARDSTOP_TOLERANCE = 200;
    int speed = (homingSpeed > 0) ? homingSpeed : (currentSpeed > 0 ? currentSpeed : 1200);

    // Re-enable limit switch if currently disabled — 0x73 requires the PI switch to be active
    bool restoreLimits = false;
    if (!respectLimits) {
        restoreLimits = true;
        setRespectLimits(true);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    // If motor is past the PI position, back away first so 0x73 can seek PI from the correct side
    if ((PISide == 1 && currentStep > PIStep) || (PISide == -1 && currentStep < PIStep)) {
        int awaySteps = std::abs(currentStep - PIStep) + MCR_HARDSTOP_TOLERANCE;
        uint8_t backDir = (PISide == 1) ? 0x62 : 0x66;
        std::vector<uint8_t> backCmd(8);
        backCmd[0] = backDir;
        backCmd[1] = motorID;
        backCmd[2] = (awaySteps >> 8) & 0xFF;
        backCmd[3] = awaySteps & 0xFF;
        backCmd[4] = 1;
        backCmd[5] = (speed >> 8) & 0xFF;
        backCmd[6] = speed & 0xFF;
        backCmd[7] = 0x0D;
        std::vector<uint8_t> backResp;
        int backWait = static_cast<int>((awaySteps / static_cast<double>(speed)) * 1000 * 1.15) + 500;
        MCR_LOG_DEBUG("home motor={:#04x} backing {} steps before seek", motorID, awaySteps);
        // v.3.5.1 bug fix: check error propagation from sendCmd
        if (!parent->sendCmd(backCmd, backResp, backWait)) {
            MCR_LOG_WARN("home motor={:#04x} backing away command failed", motorID);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    // Issue 0x73 with stepDist=0 — motor seeks PI switch and stops
    std::vector<uint8_t> cmd(8);
    cmd[0] = 0x73;
    cmd[1] = motorID;
    cmd[2] = 0; cmd[3] = 0; // stepDist = 0 (stop at PI)
    cmd[4] = 1;
    cmd[5] = (speed >> 8) & 0xFF;
    cmd[6] = speed & 0xFF;
    cmd[7] = 0x0D;

    std::vector<uint8_t> resp;
    int waitTimeMs = static_cast<int>((maxSteps / static_cast<double>(speed)) * 1000 * 1.30) + 500;
    MCR_LOG_DEBUG("home motor={:#04x} seeking PI", motorID);
    bool success = parent->sendCmd(cmd, resp, waitTimeMs);

    if (success) {
        currentStep = PIStep;
        MCR_LOG_DEBUG("home motor={:#04x} arrived at PIStep={}", motorID, PIStep);
    } else {
        MCR_LOG_WARN("home motor={:#04x} failed", motorID);
    }

    // Restore disabled-limits state if it was off before homing
    if (restoreLimits) {
        setRespectLimits(false);
    }

    return success;
}

int Motor::setMotorSpeed(int speed) {
    if (motorID == 0x01 || motorID == 0x02) {
        if (speed < 100 || speed > 1500) {
            MCR_LOG_WARN("setMotorSpeed: speed {} out of range 100-1500 for motor {:#04x}", speed, motorID);
            return -1;
        }
    } else if (motorID == 0x03) {
        if (speed < 10 || speed > 200) {
            MCR_LOG_WARN("setMotorSpeed: speed {} out of range 10-200 for iris", speed);
            return -1;
        }
    }
    currentSpeed = speed;
    MCR_LOG_DEBUG("setMotorSpeed motor={:#04x} speed={}", motorID, currentSpeed);
    return 0;
}

int Motor::setHomingSpeed(int speed) {
    if (motorID == 0x01 || motorID == 0x02) {
        if (speed < 100 || speed > 1500) {
            MCR_LOG_WARN("setHomingSpeed: speed {} out of range 100-1500 for motor {:#04x}", speed, motorID);
            return -1;
        }
    } else if (motorID == 0x03) {
        if (speed < 10 || speed > 200) {
            MCR_LOG_WARN("setHomingSpeed: speed {} out of range 10-200 for iris", speed);
            return -1;
        }
    }
    homingSpeed = speed;
    MCR_LOG_DEBUG("setHomingSpeed motor={:#04x} speed={}", motorID, homingSpeed);
    return 0;
}

bool Motor::setRespectLimits(bool state) {
    respectLimits = state;
    if (!parent || (motorID != 0x01 && motorID != 0x02)) return false; // focus/zoom only

    // Read current motor config from board
    std::vector<uint8_t> getCmd = {0x67, motorID, 0x0D};
    std::vector<uint8_t> res;
    if (!parent->sendCmd(getCmd, res, 100) || res.size() < 11) return false;

    // Build write command from the read response, modifying only the stop bits
    std::vector<uint8_t> setCmd(res.begin(), res.begin() + 12);
    setCmd[0] = 0x63;
    setCmd[3] = 0;
    setCmd[4] = 0;
    if (state) {
        if (PISide == 1)
            setCmd[3] = 1; // use wide/far (left) stop
        else
            setCmd[4] = 1; // use tele/near (right) stop
    }

    std::vector<uint8_t> resp;
    if (!parent->sendCmd(setCmd, resp, 100)) return false;
    return (resp.size() >= 2 && resp[1] == 0x00);
}

int Motor::state(int newState) {
    if (!parent || motorID != 0x04) return 0; // IRC only
    int switchTime = 50;   // MCR_IRC_SWITCH_TIME (ms) - matches Python
    int speed = 1000;      // MCR_IRC_DEFAULT_SPEED (pps) - matches Python
    int steps = (newState == 1) ? -switchTime : switchTime;
    std::vector<uint8_t> cmd(8);
    uint8_t cmdByte = (steps >= 0) ? 0x66 : 0x62;
    int absSteps = std::abs(steps);
    cmd[0] = cmdByte;
    cmd[1] = motorID;
    cmd[2] = (absSteps >> 8) & 0xFF;
    cmd[3] = absSteps & 0xFF;
    cmd[4] = 1;
    cmd[5] = (speed >> 8) & 0xFF;
    cmd[6] = speed & 0xFF;
    cmd[7] = 0x0D;
    std::vector<uint8_t> resp;
    if (!parent->sendCmd(cmd, resp, 500)) return 0;
    return newState;
}

std::tuple<bool, int, bool, bool, int, int, int, int> Motor::readMotorSetup() {
    auto err = std::make_tuple(false, -1, false, false, -1, -1, -1, -1);
    if (!parent) return err;

    std::vector<uint8_t> cmd = {0x67, motorID, 0x0D};
    std::vector<uint8_t> resp;
    if (!parent->sendCmd(cmd, resp, 100)) return err;
    if (resp.size() < 11 || resp[1] == 0xFF) return err;

    int motorType       = resp[2];
    bool useWideFarStop = resp[3] != 0;
    bool useTeleNear    = resp[4] != 0;
    int maxStepsVal     = (resp[5] << 8) | resp[6];
    int minSpeedVal     = (resp[7] << 8) | resp[8];
    int maxSpeedVal     = (resp[9] << 8) | resp[10];

    return std::make_tuple(true, motorType, useWideFarStop, useTeleNear, maxStepsVal, minSpeedVal, maxSpeedVal, 0);
}

bool Motor::writeMotorSetup(bool useWideFarStop, bool useTeleNearStop, int maxStepsVal, int minSpeedVal, int maxSpeedVal) {
    if (!parent) return false;

    uint8_t motorType = (motorID == 0x04) ? 0x01 : 0x00; // IRC is DC motor
    std::vector<uint8_t> cmd = {
        0x63,
        motorID,
        motorType,
        (uint8_t)(useWideFarStop ? 1 : 0),
        (uint8_t)(useTeleNearStop ? 1 : 0),
        (uint8_t)((maxStepsVal >> 8) & 0xFF),
        (uint8_t)(maxStepsVal & 0xFF),
        (uint8_t)((minSpeedVal >> 8) & 0xFF),
        (uint8_t)(minSpeedVal & 0xFF),
        (uint8_t)((maxSpeedVal >> 8) & 0xFF),
        (uint8_t)(maxSpeedVal & 0xFF),
        0x0D
    };
    std::vector<uint8_t> resp;
    if (!parent->sendCmd(cmd, resp, 100)) return false;
    return (resp.size() >= 2 && resp[1] == 0x00);
}


// MCRControl implementation
MCRControl::MCRControl(const std::string& portName, bool logFiles, bool moduleDebugLevel, bool communicationDebugLevel)
    : serialPortName(portName), focus(this, 0x01), zoom(this, 0x02), iris(this, 0x03), IRC(this, 0x04) {

    // Initialize logger if not already done
    if (!g_logger) {
        initLogger(logFiles, moduleDebugLevel, communicationDebugLevel);
    } else {
        // Re-apply level if parameters differ from default
        spdlog::level::level_enum level = spdlog::level::info;
        if (communicationDebugLevel) level = spdlog::level::trace;
        else if (moduleDebugLevel)   level = spdlog::level::debug;
        g_logger->set_level(level);
    }

    MCR_LOG_INFO("TheiaMCR module version {}", MCR_REVISION);
    MCR_LOG_INFO("Opening serial port: {}", portName);
    if (serial.open(portName)) {
        boardInitialized = true;
        // Send test command to verify board is responsive (mirrors Python __init__ behaviour)
        std::string fw = readFWRevision();
        if (fw.empty()) {
            MCR_LOG_ERROR("No response from board on {} — check connection and power", portName);
            boardInitialized = false;
        } else {
            MCR_LOG_INFO("Board connected on {} | FW revision: {}", portName, fw);
        }
    } else {
        MCR_LOG_ERROR("Failed to open serial port: {}", portName);
    }
}

MCRControl::~MCRControl() {
    close();
}

void MCRControl::close() {
    MCR_LOG_INFO("Closing board connection on {}", serialPortName);
    
    // v.3.5.1 bug fix: properly release all resources
    if (boardInitialized) {
        // Flush and close serial port
        serial.close();
        
        // Reset motor objects to non-initialized state
        focus = Motor();
        zoom = Motor();
        iris = Motor();
        IRC = Motor();
        
        boardInitialized = false;
        
#ifdef _WIN32
        // Give Windows time to fully release the COM port handle
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
#endif
    }
}

void MCRControl::closeLogFiles() {
    if (g_fileSink) {
        MCR_LOG_INFO("Closing log file");
        g_fileSink->flush();
        if (g_logger) {
            // Remove the file sink from the logger, keep console
            auto& sinks = g_logger->sinks();
            sinks.erase(std::remove(sinks.begin(), sinks.end(),
                std::static_pointer_cast<spdlog::sinks::sink>(g_fileSink)), sinks.end());
        }
        g_fileSink.reset();
    }
}

void MCRControl::setLogLevel(int level) {
    spdlog::level::level_enum spdLevel;
    switch (level) {
        case 0: spdLevel = spdlog::level::off;      break;
        case 1: spdLevel = spdlog::level::err;       break;
        case 2: spdLevel = spdlog::level::warn;      break;
        case 3: spdLevel = spdlog::level::info;      break;
        case 4: spdLevel = spdlog::level::debug;     break;
        case 5: spdLevel = spdlog::level::trace;     break;
        default: spdLevel = spdlog::level::info;     break;
    }
    if (g_logger) {
        g_logger->set_level(spdLevel);
        for (auto& sink : g_logger->sinks())
            sink->set_level(spdLevel);
    }
}

bool MCRControl::focusInit(int steps, int pi, bool move, int accel, int homingSpeed) {
    if (!boardInitialized) return false;
    MCR_LOG_INFO("Focus init: maxSteps={}, PIStep={}", steps, pi);
    focus = Motor(this, 0x01, steps, pi);
    focus.currentSpeed = 1200;
    focus.homingSpeed  = (homingSpeed >= 100 && homingSpeed <= 1500) ? homingSpeed : 1200;
    if (move) {
        MCR_LOG_DEBUG("Focus homing to PI position {}", pi);
        return focus.home();
    }
    return true;
}

bool MCRControl::zoomInit(int steps, int pi, bool move, int accel, int homingSpeed) {
    if (!boardInitialized) return false;
    MCR_LOG_INFO("Zoom init: maxSteps={}, PIStep={}", steps, pi);
    zoom = Motor(this, 0x02, steps, pi);
    zoom.currentSpeed = 1200;
    zoom.homingSpeed  = (homingSpeed >= 100 && homingSpeed <= 1500) ? homingSpeed : 1200;
    if (move) {
        MCR_LOG_DEBUG("Zoom homing to PI position {}", pi);
        return zoom.home();
    }
    return true;
}

bool MCRControl::irisInit(int steps, bool move, int homingSpeed) {
    if (!boardInitialized) return false;
    MCR_LOG_INFO("Iris init: maxSteps={}", steps);
    iris = Motor(this, 0x03, steps, 0);
    iris.currentSpeed = 100;
    iris.homingSpeed  = (homingSpeed >= 10 && homingSpeed <= 200) ? homingSpeed : 100;
    if (move) {
        MCR_LOG_DEBUG("Iris homing");
        return iris.home();
    }
    return true;
}

bool MCRControl::IRCInit() {
    if (!boardInitialized) return false;
    MCR_LOG_INFO("IRC init");
    IRC = Motor(this, 0x04, 1000, 0);
    IRC.currentSpeed = 1000;  // MCR_IRC_DEFAULT_SPEED - matches Python
    IRC.homingSpeed = 1000;   // MCR_IRC_DEFAULT_SPEED - matches Python
    return true;
}

bool MCRControl::sendCmd(const std::vector<uint8_t>& cmd, std::vector<uint8_t>& response, int waitTimeMs) {
    if (!boardInitialized) return false;

    // v.3.5.1 bug fix: check for 0-length command
    if (cmd.empty()) {
        MCR_LOG_ERROR("Command string is empty");
        response = {0x74, 0x01, 0x0D};
        return false;
    }

    // Log outgoing bytes at trace level (communicationDebugLevel)
    if (g_logger && g_logger->level() <= spdlog::level::trace) {
        std::string hex;
        for (auto b : cmd) { char buf[4]; snprintf(buf, sizeof(buf), "%02X ", b); hex += buf; }
        MCR_LOG_TRACE("TX: {}", hex);
    }

    // Clear any leftover data in serial rx buffer
    std::vector<uint8_t> dummy;
    while (serial.inWaiting() > 0) {
        serial.read(dummy, 64, 5);
    }

    if (serial.write(cmd) < 0) {
        return false;
    }

    // Read the response byte-by-byte.
    //
    // com0com quirk: the virtual port driver only flushes its internal write
    // buffer to the other side when the sending end's overlapped ReadFile
    // completes (or is cancelled).  Using one long blocking read (e.g. 1000 ms)
    // means the data never arrives during the wait.  Polling with a short
    // interval (POLL_MS) causes the ReadFile to cancel and re-issue every
    // POLL_MS, which triggers the flush.  On real USB-CDC hardware the extra
    // cancel/re-issue overhead is negligible (<< 1 ms per cycle).
    //
    response.clear();
    static const int POLL_MS = 50;   // flush interval for com0com compatibility
    auto deadline = std::chrono::steady_clock::now()
                    + std::chrono::milliseconds(waitTimeMs + 2000);

    while (response.size() < 12) {
        std::vector<uint8_t> byteBuffer;
        // After the first byte arrives use a generous inter-byte timeout so a
        // slow board doesn't split the packet across poll boundaries.
        int tmo = response.empty() ? POLL_MS : 200;
        if (serial.read(byteBuffer, 1, tmo) > 0) {
            response.push_back(byteBuffer[0]);
            if (byteBuffer[0] == 0x0D) {
                break; // Complete response received
            }
        } else if (!response.empty()) {
            break; // Inter-byte timeout after first byte — treat as end of packet
        }
        if (std::chrono::steady_clock::now() >= deadline) {
            break; // Overall deadline exceeded
        }
    }

    // Log response bytes at trace level
    if (g_logger && g_logger->level() <= spdlog::level::trace && !response.empty()) {
        std::string hex;
        for (auto b : response) { char buf[4]; snprintf(buf, sizeof(buf), "%02X ", b); hex += buf; }
        MCR_LOG_TRACE("RX: {}", hex);
    }

    return !response.empty();
}

std::string MCRControl::readFWRevision() {
    if (!boardInitialized) return "";
    std::vector<uint8_t> cmd = {0x76, 0x0D};
    std::vector<uint8_t> resp;
    if (sendCmd(cmd, resp)) {
        std::string fw = "";
        for (size_t i = 1; i < resp.size() - 1; ++i) {
            char hexStr[4];
            snprintf(hexStr, sizeof(hexStr), "%X", resp[i]);
            if (!fw.empty()) fw += ".";
            fw += hexStr;
        }
        MCR_LOG_DEBUG("FW revision: {}", fw);
        return fw;
    }
    MCR_LOG_WARN("readFWRevision: no response from board");
    return "";
}

std::string MCRControl::readBoardSN() {
    if (!boardInitialized) return "";
    std::vector<uint8_t> cmd = {0x79, 0x0D};
    std::vector<uint8_t> resp;
    if (sendCmd(cmd, resp) && resp.size() >= 6) {
        char snStr[32];
        snprintf(snStr, sizeof(snStr), "%02X%02X-%02X%02X%02X",
                 resp[1], resp[2], resp[resp.size() - 4], resp[resp.size() - 3], resp[resp.size() - 2]);
        MCR_LOG_INFO("Board SN: {}", snStr);
        return std::string(snStr);
    }
    MCR_LOG_WARN("readBoardSN: no response from board");
    return "";
}

} // namespace TheiaMCR
