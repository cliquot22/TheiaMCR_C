#ifndef THEIAMCR_C_H
#define THEIAMCR_C_H

#ifdef _WIN32
    #ifdef THEIAMCR_C_EXPORTS
        #define THEIAMCR_API __declspec(dllexport)
    #else
        #define THEIAMCR_API __declspec(dllimport)
    #endif
#else
    #define THEIAMCR_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef void* MCRControlHandle;

// Constructor and Destructor
THEIAMCR_API MCRControlHandle MCR_Create(const char* portName);
THEIAMCR_API MCRControlHandle MCR_CreateEx(const char* portName, int logFiles, int moduleDebugLevel, int communicationDebugLevel);
THEIAMCR_API void MCR_Destroy(MCRControlHandle handle);

// Logging control: 0=off, 1=error, 2=warn, 3=info, 4=debug, 5=trace(comm)
THEIAMCR_API void MCR_SetLogLevel(int level);

// Board Functions
THEIAMCR_API int MCR_IsInitialized(MCRControlHandle handle);
THEIAMCR_API int MCR_ReadFWRevision(MCRControlHandle handle, char* buffer, int maxLen);
THEIAMCR_API int MCR_ReadBoardSN(MCRControlHandle handle, char* buffer, int maxLen);

// Motor Functions
THEIAMCR_API int MCR_Focus_MoveAbs(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Focus_MoveRel(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Focus_GetCurrentStep(MCRControlHandle handle);

THEIAMCR_API int MCR_Zoom_MoveAbs(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Zoom_MoveRel(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Zoom_GetCurrentStep(MCRControlHandle handle);

THEIAMCR_API int MCR_Iris_MoveAbs(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Iris_MoveRel(MCRControlHandle handle, int steps, int speed);
THEIAMCR_API int MCR_Iris_GetCurrentStep(MCRControlHandle handle);

// IRC state: 1 = visible (IR-cut), 2 = clear filter. Returns new state, or 0 on error.
THEIAMCR_API int MCR_IRC_SetState(MCRControlHandle handle, int state);

#ifdef __cplusplus
}
#endif

#endif // THEIAMCR_C_H
