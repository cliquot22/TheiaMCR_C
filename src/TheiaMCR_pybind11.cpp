#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "TheiaMCR.h"

namespace py = pybind11;

PYBIND11_MODULE(TheiaMCR_py, m) {
    m.doc() = "TheiaMCR C++ Python Bindings (Native pybind11 Module)";

    py::class_<TheiaMCR::Motor>(m, "Motor")
        .def_readwrite("motorID", &TheiaMCR::Motor::motorID)
        .def_readwrite("currentStep", &TheiaMCR::Motor::currentStep)
        .def_readwrite("maxSteps", &TheiaMCR::Motor::maxSteps)
        .def_readwrite("PIStep", &TheiaMCR::Motor::PIStep)
        .def_readwrite("currentSpeed", &TheiaMCR::Motor::currentSpeed)
        .def_readwrite("homingSpeed", &TheiaMCR::Motor::homingSpeed)
        .def_readwrite("initialized", &TheiaMCR::Motor::initialized)
        .def_readwrite("respectLimits", &TheiaMCR::Motor::respectLimits)
        .def_readwrite("PISide", &TheiaMCR::Motor::PISide)
        .def("moveAbs", &TheiaMCR::Motor::moveAbs, py::arg("steps"), py::arg("speed") = 0)
        .def("moveRel", &TheiaMCR::Motor::moveRel, py::arg("steps"), py::arg("speed") = 0, py::arg("correctForBL") = true)
        .def("home", &TheiaMCR::Motor::home)
        .def("setMotorSpeed", &TheiaMCR::Motor::setMotorSpeed, py::arg("speed"))
        .def("setHomingSpeed", &TheiaMCR::Motor::setHomingSpeed, py::arg("speed"))
        .def("setRespectLimits", &TheiaMCR::Motor::setRespectLimits, py::arg("state"))
        .def("state", &TheiaMCR::Motor::state, py::arg("state"))
        .def("readMotorSetup", &TheiaMCR::Motor::readMotorSetup)
        .def("writeMotorSetup", &TheiaMCR::Motor::writeMotorSetup,
             py::arg("useWideFarStop"), py::arg("useTeleNearStop"),
             py::arg("maxSteps"), py::arg("minSpeed"), py::arg("maxSpeed"));

    py::class_<TheiaMCR::MCRControl>(m, "MCRControl")
        .def(py::init([](const std::string& serialPortName,
                         bool moduleDebugLevel,
                         bool communicationDebugLevel,
                         bool logFiles) {
                return std::make_unique<TheiaMCR::MCRControl>(
                    serialPortName, logFiles, moduleDebugLevel, communicationDebugLevel);
             }),
             py::arg("serialPortName"),
             py::arg("moduleDebugLevel") = false,
             py::arg("communicationDebugLevel") = false,
             py::arg("logFiles") = true)
        .def_property_readonly("boardInitialized", &TheiaMCR::MCRControl::isInitialized)
        .def_property_readonly("MCRInitialized", &TheiaMCR::MCRControl::isInitialized)
        .def("isInitialized", &TheiaMCR::MCRControl::isInitialized)
        .def("readFWRevision", &TheiaMCR::MCRControl::readFWRevision)
        .def("readBoardSN", &TheiaMCR::MCRControl::readBoardSN)
        .def_readonly("focus", &TheiaMCR::MCRControl::focus)
        .def_readonly("zoom", &TheiaMCR::MCRControl::zoom)
        .def_readonly("iris", &TheiaMCR::MCRControl::iris)
        .def_readonly("IRC", &TheiaMCR::MCRControl::IRC)
        .def("close", &TheiaMCR::MCRControl::close)
        .def("closeLogFiles", &TheiaMCR::MCRControl::closeLogFiles)
        .def("focusInit", &TheiaMCR::MCRControl::focusInit, py::arg("steps"), py::arg("pi"), py::arg("move") = true, py::arg("accel") = 0, py::arg("homingSpeed") = -1)
        .def("zoomInit", &TheiaMCR::MCRControl::zoomInit, py::arg("steps"), py::arg("pi"), py::arg("move") = true, py::arg("accel") = 0, py::arg("homingSpeed") = -1)
        .def("irisInit", &TheiaMCR::MCRControl::irisInit, py::arg("steps"), py::arg("move") = true, py::arg("homingSpeed") = -1)
        .def("IRCInit", &TheiaMCR::MCRControl::IRCInit)
        .def_static("setLogLevel", &TheiaMCR::MCRControl::setLogLevel, py::arg("level"),
            "Set library log level: 0=off 1=error 2=warn 3=info 4=debug 5=trace(comm)");

    // Module-level convenience function
    m.def("setLogLevel", &TheiaMCR::MCRControl::setLogLevel, py::arg("level"),
        "Set library log level: 0=off 1=error 2=warn 3=info 4=debug 5=trace(comm)");

    // Module revision string (matches Python MCR_REVISION)
    m.attr("MCR_REVISION") = TheiaMCR::MCR_REVISION;
}
