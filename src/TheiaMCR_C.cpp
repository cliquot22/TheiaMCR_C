#include "TheiaMCR_C.h"
#include "TheiaMCR.h"
#include <cstring>

extern "C" {

MCRControlHandle MCR_Create(const char* portName) {
    if (!portName) return nullptr;
    return static_cast<MCRControlHandle>(new TheiaMCR::MCRControl(portName));
}

MCRControlHandle MCR_CreateEx(const char* portName, int logFiles, int moduleDebugLevel, int communicationDebugLevel) {
    if (!portName) return nullptr;
    return static_cast<MCRControlHandle>(new TheiaMCR::MCRControl(
        portName, logFiles != 0, moduleDebugLevel != 0, communicationDebugLevel != 0));
}

void MCR_Destroy(MCRControlHandle handle) {
    if (handle) {
        delete static_cast<TheiaMCR::MCRControl*>(handle);
    }
}

void MCR_SetLogLevel(int level) {
    TheiaMCR::MCRControl::setLogLevel(level);
}

int MCR_IsInitialized(MCRControlHandle handle) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->isInitialized() ? 1 : 0;
}

int MCR_ReadFWRevision(MCRControlHandle handle, char* buffer, int maxLen) {
    if (!handle || !buffer || maxLen <= 0) return 0;
    auto fw = static_cast<TheiaMCR::MCRControl*>(handle)->readFWRevision();
    std::strncpy(buffer, fw.c_str(), maxLen);
    buffer[maxLen - 1] = '\0';
    return 1;
}

int MCR_ReadBoardSN(MCRControlHandle handle, char* buffer, int maxLen) {
    if (!handle || !buffer || maxLen <= 0) return 0;
    auto sn = static_cast<TheiaMCR::MCRControl*>(handle)->readBoardSN();
    std::strncpy(buffer, sn.c_str(), maxLen);
    buffer[maxLen - 1] = '\0';
    return 1;
}

int MCR_Focus_MoveAbs(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->focus.moveAbs(steps, speed) ? 1 : 0;
}

int MCR_Focus_MoveRel(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->focus.moveRel(steps, speed) ? 1 : 0;
}

int MCR_Focus_GetCurrentStep(MCRControlHandle handle) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->focus.currentStep;
}

int MCR_Zoom_MoveAbs(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->zoom.moveAbs(steps, speed) ? 1 : 0;
}

int MCR_Zoom_MoveRel(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->zoom.moveRel(steps, speed) ? 1 : 0;
}

int MCR_Zoom_GetCurrentStep(MCRControlHandle handle) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->zoom.currentStep;
}

int MCR_Iris_MoveAbs(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->iris.moveAbs(steps, speed) ? 1 : 0;
}

int MCR_Iris_MoveRel(MCRControlHandle handle, int steps, int speed) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->iris.moveRel(steps, speed) ? 1 : 0;
}

int MCR_Iris_GetCurrentStep(MCRControlHandle handle) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->iris.currentStep;
}

int MCR_IRC_SetState(MCRControlHandle handle, int state) {
    if (!handle) return 0;
    return static_cast<TheiaMCR::MCRControl*>(handle)->IRC.state(state);
}

}
