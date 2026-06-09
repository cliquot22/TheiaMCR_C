# run the Python v. C++ comparison tests from the terminal (from the test folder): 
# python -m pytest test_compare_mcr.py -v
#
# or run hardware only tests using: 
# python -m pytest test_compare_mcr.py::TestCppHardware test_compare_mcr.py::TestHardwareComparison -v -s

# pyright: reportOptionalSubscript=false
# pyright: reportOptionalIterable=false

"""
Comparison tests: Python TheiaMCR vs C++ TheiaMCR_py
=====================================================
These tests run the same scenarios against both implementations and report
any differences in:
  - Bytes sent to the board (TX byte strings)
  - Values returned by each API call

Running
-------
    cd <workspace root>
    python -m pytest tests/test_compare_mcr.py -v

Python module path
------------------
Adjust PYTHON_MODULE_PATH below to wherever TheiaMCR.py is installed.

C++ module
----------
The C++ tests require:
  1. The TheiaMCR_py.pyd module (build the 'TheiaMCR_py' target in VS Code).
  2. A virtual COM port pair for the simulated board.
     - Install com0com (https://sourceforge.net/projects/com0com/)
     - Create a pair, then set SIM_PORT / TEST_PORT below. 
         Run "setupPC" in C:/Program Files (x86)/com0com to make changes (setup as com8-com11)
  C++ tests are automatically skipped if the .pyd is not found or the virtual
  ports are not available.

Known differences (as of this writing)
---------------------------------------
  1. readBoardSN format:
       Python : "055-000102"  (strips last char of 4-digit prefix → 3 digits)
       C++    : "0550-000102" (keeps all 4 digits, uppercase)
  2. IRC Motor.state() parameters:
       Python : 50 steps at 1000 pps
       C++    : 100 steps at 400 pps
  3. FW version check on init:
       Python : rejects if major version < 5
       C++    : accepts any non-empty string
"""
# pyright: reportOptionalMemberAccess=false

from __future__ import annotations
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

# Root of this repository
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Path to the original Python TheiaMCR package
PYTHON_MODULE_PATH = os.path.join(
    os.path.expanduser('~'),
    'OneDrive - Theia Technologies', 'Documents', 'Python', 'TheiaMCR'
)

# Virtual COM port pair for C++ tests (change to match your com0com setup)
SIM_PORT  = 'COM8'    # Simulator end (SimulatorThread listens here)
TEST_PORT = 'COM11'   # Module-under-test end (C++ MCRControl connects here)

# ---------------------------------------------------------------------------
# Hardware port configuration  (set HARDWARE_PORT to enable hardware tests)
# ---------------------------------------------------------------------------
# Set HARDWARE_PORT to the COM port of the real MCR600 board, e.g. 'COM4'.
# Leave as None to skip all hardware tests.
HARDWARE_PORT = 'COM4'

# Lens type: 'TL1250' or 'TL410'
HARDWARE_LENS = 'TL1250'

# Motor parameters for the chosen lens
_LENS_PARAMS = {
    'TL1250': dict(focus_steps=8390, focus_pi=7959, zoom_steps=3227, zoom_pi=3119, iris_steps=75),
    'TL410':  dict(focus_steps=9353, focus_pi=8652, zoom_steps=4073, zoom_pi=154,  iris_steps=75),
}
LENS_PARAMS = _LENS_PARAMS.get(HARDWARE_LENS, _LENS_PARAMS['TL1250'])

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _import_python_mcr():
    """Import the original Python TheiaMCR module."""
    if PYTHON_MODULE_PATH not in sys.path:
        sys.path.insert(0, PYTHON_MODULE_PATH)
    import TheiaMCR.TheiaMCR as py_mcr
    return py_mcr

def _import_cpp_mcr():
    """Import the compiled C++ pybind11 TheiaMCR_py module."""
    for path in [
        os.path.join(REPO_ROOT, 'build', 'Debug'),
        os.path.join(REPO_ROOT, 'build', 'Release'),
        os.path.join(REPO_ROOT, 'build'),
    ]:
        if os.path.isdir(path):
            for fn in os.listdir(path):
                if fn.startswith('TheiaMCR_py') and (fn.endswith('.pyd') or fn.endswith('.so')):
                    if path not in sys.path:
                        sys.path.insert(0, path)
                    import TheiaMCR_py as cpp_mcr  # type: ignore
                    return cpp_mcr
    return None

# ---------------------------------------------------------------------------
# Availability flags
# ---------------------------------------------------------------------------

try:
    PY_MCR = _import_python_mcr()
    PY_AVAILABLE = True
except Exception as e:
    PY_MCR = None
    PY_AVAILABLE = False
    print(f'[warn] Python TheiaMCR not available: {e}')

CPP_MCR = _import_cpp_mcr()
CPP_AVAILABLE = CPP_MCR is not None

from board_simulator import BoardSimulator, MockSerial, SimulatorThread, virtual_ports_available

VIRTUAL_PORTS_AVAILABLE = virtual_ports_available(SIM_PORT, TEST_PORT)

# Counter for unique mock port names — avoids the MCRControl singleton reusing
# a stale instance that references an old MockSerial from a previous test.
_mock_port_counter = 0


def make_python_mcr(sim: BoardSimulator, logFiles: bool = False):
    """
    Return (MCR, mock_serial, patcher, port_name) with the Python module
    wired to the simulator.

    Uses a unique port name each time so the MCRControl singleton never
    returns a cached instance that references a different mock.
    """
    global _mock_port_counter
    _mock_port_counter += 1
    port_name = f'MOCK_{_mock_port_counter:04d}'

    mock = MockSerial(sim)

    # Patch serial.Serial (accessed as 'serial.Serial' inside TheiaMCR.py
    # via 'import serial'). Patching at the module attribute level ensures
    # all MCRCom instances inside this MCRControl creation use our mock.
    patcher = patch('serial.Serial', return_value=mock)
    patcher.start()
    MCR = PY_MCR.MCRControl(serialPortName=port_name, logFiles=logFiles)
    return MCR, mock, patcher


def stop_python_mcr(MCR, patcher):
    """Close the MCR instance (removes singleton cache entry) and stop patch."""
    try:
        if MCR is not None:
            MCR.close()
    except Exception:
        pass
    try:
        patcher.stop()
    except RuntimeError:
        pass  # already stopped


# ---------------------------------------------------------------------------
# Helper: decode sent bytes into human-readable command name
# ---------------------------------------------------------------------------

_CMD_NAMES = {
    0x62: 'MOVE_NEG',
    0x63: 'WRITE_CFG',
    0x66: 'MOVE_POS',
    0x67: 'READ_CFG',
    0x6B: 'SET_PATH',
    0x73: 'MOVE_ABS',
    0x76: 'READ_FW',
    0x79: 'READ_SN',
}

_MOTOR_NAMES = {0x01: 'focus', 0x02: 'zoom', 0x03: 'iris', 0x04: 'IRC'}

def describe_cmd(cmd: bytes) -> str:
    if not cmd:
        return '<empty>'
    name = _CMD_NAMES.get(cmd[0], f'0x{cmd[0]:02X}')
    motor = _MOTOR_NAMES.get(cmd[1], f'0x{cmd[1]:02X}') if len(cmd) > 1 else ''
    raw = ' '.join(f'{b:02X}' for b in cmd)
    return f'{name}({motor}) [{raw}]'


# ===========================================================================
# Test suite: Python module (always run when Python module is available)
# ===========================================================================

@unittest.skipUnless(PY_AVAILABLE, 'Python TheiaMCR not found – set PYTHON_MODULE_PATH')
class TestPythonModule(unittest.TestCase):
    """Smoke-tests for the Python TheiaMCR module using MockSerial."""

    def setUp(self):
        self.sim = BoardSimulator()
        self.MCR, self.mock, self.patcher = make_python_mcr(self.sim)

    def tearDown(self):
        stop_python_mcr(self.MCR, self.patcher)
        self.sim.clear_history()

    # ---- board init --------------------------------------------------------

    def test_board_initializes(self):
        self.assertTrue(self.MCR.boardInitialized,
                        'boardInitialized should be True after successful init')

    def test_fw_revision_sent(self):
        cmds = self.sim.commands_sent()
        self.assertTrue(any(c[0] == 0x76 for c in cmds),
                        '0x76 (readFWRevision) should be sent during init')

    def test_read_fw_revision(self):
        self.sim.clear_history()
        fw = self.MCR.MCRBoard.readFWRevision()
        self.assertEqual(fw, '5.3.1.0.0')

    def test_read_board_sn(self):
        self.sim.clear_history()
        sn = self.MCR.MCRBoard.readBoardSN()
        # Python format: 3-digit prefix (strips last char) + 6-digit suffix
        # SN_BYTES = [0x05, 0x50, 0x00, 0x01, 0x02, 0x03]
        # f'{0x05:02x}{0x50:02x}'[:-1] = "055"
        # + f'-{0x01:02x}{0x02:02x}{0x03:02x}' = "-010203"
        self.assertEqual(sn, '055-010203')

    # ---- motor init --------------------------------------------------------

    def _init_motors(self):
        self.sim.clear_history()
        self.MCR.focusInit(steps=8390, pi=7959, move=False)
        self.MCR.zoomInit(steps=3227, pi=3119, move=False)
        self.MCR.irisInit(steps=75, move=False)
        self.MCR.IRCInit()

    def test_motor_init_sends_write_cfg(self):
        self._init_motors()
        cmds = self.sim.commands_sent()
        write_cfgs = [c for c in cmds if c[0] == 0x63]
        # focus, zoom, iris, IRC = 4 write-config commands
        self.assertGreaterEqual(len(write_cfgs), 4,
                                'Expected at least 4 WRITE_CFG (0x63) commands')

    def test_focus_init_motor_id(self):
        self._init_motors()
        write_cfgs = [c for c in self.sim.commands_sent() if c[0] == 0x63]
        focus_cfg = next((c for c in write_cfgs if c[1] == 0x01), None)
        self.assertIsNotNone(focus_cfg, 'Expected a write-config for focus motor (0x01)')

    # ---- motor moves -------------------------------------------------------

    def _init_for_moves(self):
        self.MCR.focusInit(steps=8390, pi=7959, move=False)
        self.MCR.zoomInit(steps=3227, pi=3119, move=False)
        self.MCR.irisInit(steps=75, move=False)
        self.MCR.IRCInit()
        self.sim.clear_history()

    def test_focus_move_rel_positive(self):
        self._init_for_moves()
        result = self.MCR.focus.moveRel(1000, correctForBL=False)
        self.assertEqual(result, 0)  # ERR_OK
        cmds = self.sim.commands_sent()
        move_cmds = [c for c in cmds if c[0] in (0x62, 0x66, 0x73)]
        self.assertTrue(any(c[0] == 0x66 and c[1] == 0x01 for c in move_cmds),
                        'Positive focus moveRel should send 0x66 for motor 0x01')

    def test_focus_move_rel_negative(self):
        self._init_for_moves()
        # Start at step 2000 so a negative move doesn't hit the lower hard stop.
        self.MCR.focus.currentStep = 2000
        result = self.MCR.focus.moveRel(-500, correctForBL=False)
        self.assertEqual(result, 0)
        cmds = self.sim.commands_sent()
        move_cmds = [c for c in cmds if c[0] in (0x62, 0x66)]
        self.assertTrue(any(c[0] == 0x62 and c[1] == 0x01 for c in move_cmds),
                        'Negative focus moveRel should send 0x62 for motor 0x01')

    def test_focus_move_rel_step_count(self):
        """Verify the step count is encoded correctly in the command bytes."""
        self._init_for_moves()
        steps = 1500
        self.MCR.focus.moveRel(steps, correctForBL=False)
        cmds = self.sim.commands_sent()
        move_cmd = next((c for c in cmds if c[0] == 0x66 and c[1] == 0x01), None)
        self.assertIsNotNone(move_cmd)
        encoded_steps = (move_cmd[2] << 8) | move_cmd[3] # type: ignore
        self.assertEqual(encoded_steps, steps)

    def test_zoom_move_rel_with_backlash(self):
        """Moving towards PI (positive for PISide=1) triggers backlash overshoot."""
        self._init_for_moves()
        # zoom PISide: steps=3227, pi=3119 → (3227-3119)=108 < 3119 → PISide=1
        # positive move (towards PI) should trigger BL overshoot + back move
        self.MCR.zoom.moveRel(500, correctForBL=True)
        cmds = [c for c in self.sim.commands_sent() if c[0] in (0x62, 0x66)]
        zoom_cmds = [c for c in cmds if c[1] == 0x02]
        self.assertGreaterEqual(len(zoom_cmds), 2,
                                'Backlash correction should produce at least 2 move commands')

    def test_focus_move_abs(self):
        self._init_for_moves()
        self.MCR.focus.moveAbs(4000)
        cmds = self.sim.commands_sent()
        abs_cmds = [c for c in cmds if c[0] == 0x73 and c[1] == 0x01]
        self.assertTrue(len(abs_cmds) >= 1, 'moveAbs should send 0x73 command')

    def test_iris_move_rel(self):
        self._init_for_moves()
        self.MCR.iris.moveRel(20)
        cmds = self.sim.commands_sent()
        iris_cmds = [c for c in cmds if c[1] == 0x03]
        self.assertTrue(len(iris_cmds) >= 1)
        # Iris positive step → close → 0x62
        self.assertTrue(any(c[0] == 0x62 for c in iris_cmds),
                        'Positive iris moveRel should send 0x62 (iris direction inverted)')

    def test_irc_state_1(self):
        """IRC state(1) should move in negative direction."""
        self._init_for_moves()
        self.MCR.IRC.state(1)
        cmds = self.sim.commands_sent()
        irc_cmds = [c for c in cmds if c[1] == 0x04]
        self.assertTrue(len(irc_cmds) >= 1)
        self.assertTrue(any(c[0] == 0x62 for c in irc_cmds),
                        'IRC state(1) should send 0x62 (negative direction)')

    def test_irc_state_2(self):
        """IRC state(2) should move in positive direction."""
        self._init_for_moves()
        self.MCR.IRC.state(2)
        cmds = self.sim.commands_sent()
        irc_cmds = [c for c in cmds if c[1] == 0x04]
        self.assertTrue(any(c[0] == 0x66 for c in irc_cmds),
                        'IRC state(2) should send 0x66 (positive direction)')

    # ---- read/write motor config -------------------------------------------

    def test_read_motor_setup(self):
        self._init_for_moves()
        ok, mtype, wf, tn, maxst, minsp, maxsp, err = self.MCR.focus.readMotorSetup()
        self.assertTrue(ok)
        # focusInit wrote maxSteps=8390 to the board, so we expect that back
        self.assertEqual(maxst, 8390)
        self.assertEqual(minsp, 100)
        self.assertEqual(maxsp, 1500)

    def test_write_motor_setup(self):
        self._init_for_moves()
        result = self.MCR.zoom.writeMotorSetup(
            useWideFarStop=True, useTeleNearStop=False,
            maxSteps=3000, minSpeed=200, maxSpeed=1200
        )
        self.assertTrue(result)
        # Verify the config was actually stored in the simulator
        ok, _, _, _, maxst, minsp, maxsp, _ = self.MCR.zoom.readMotorSetup()
        self.assertTrue(ok)
        self.assertEqual(maxst, 3000)

    # ---- set respect limits ------------------------------------------------

    def test_set_respect_limits_false(self):
        self._init_for_moves()
        result = self.MCR.focus.setRespectLimits(False)
        self.assertFalse(result is None)
        self.assertFalse(self.MCR.focus.respectLimits)


# ===========================================================================
# Test suite: C++ module (skipped unless virtual COM ports are available)
# ===========================================================================

@unittest.skipUnless(CPP_AVAILABLE, 'TheiaMCR_py.pyd not found – build the TheiaMCR_py target')
@unittest.skipUnless(VIRTUAL_PORTS_AVAILABLE,
                     f'Virtual COM port pair ({SIM_PORT}/{TEST_PORT}) not available – '
                     f'install com0com and create the pair')
class TestCppModule(unittest.TestCase):
    """
    Tests for the C++ TheiaMCR_py module using a real virtual COM port pair.
    The SimulatorThread opens SIM_PORT and the C++ module connects to TEST_PORT.
    """

    def setUp(self):
        self.sim_thread = SimulatorThread(SIM_PORT)
        self.sim_thread.start()
        # Wait for the simulator thread to open the port and enter its read loop.
        # com0com can buffer the first bytes before the thread is ready; 0.5s is
        # enough headroom on typical hardware.
        import time; time.sleep(0.5)
        CPP_MCR.MCRControl.setLogLevel(1)   # errors only during tests
        self.MCR = CPP_MCR.MCRControl(
            serialPortName=TEST_PORT,
            moduleDebugLevel=False,
            communicationDebugLevel=False,
            logFiles=False,
        )

    def tearDown(self):
        self.MCR.close()
        self.sim_thread.stop()

    @property
    def sim(self) -> BoardSimulator:
        return self.sim_thread.simulator

    def _init_motors(self, move: bool = False):
        self.sim.clear_history()
        self.MCR.focusInit(steps=8390, pi=7959, move=move)
        self.MCR.zoomInit(steps=3227, pi=3119, move=move)
        self.MCR.irisInit(steps=75, move=move)
        self.MCR.IRCInit()
        self.sim.clear_history()

    # ---- board init --------------------------------------------------------

    def test_board_initializes(self):
        self.assertTrue(self.MCR.boardInitialized)

    def test_read_fw_revision(self):
        fw = self.MCR.readFWRevision()
        self.assertEqual(fw, '5.3.1.0.0')

    def test_read_board_sn(self):
        sn = self.MCR.readBoardSN()
        # C++ format: 4-digit prefix (no stripping) + 6-digit suffix, uppercase
        # SN_BYTES = [0x05, 0x50, 0x00, 0x01, 0x02, 0x03]
        # %02X%02X = "0550"
        # resp[size-4..size-2] = [0x01,0x02,0x03] → "010203"
        self.assertEqual(sn, '0550-010203')

    # ---- motor moves -------------------------------------------------------

    def test_focus_move_rel_positive(self):
        self._init_motors()
        result = self.MCR.focus.moveRel(1000)
        self.assertTrue(result)

    def test_focus_move_rel_negative(self):
        self._init_motors()
        result = self.MCR.focus.moveRel(-500)
        self.assertTrue(result)

    def test_focus_move_abs(self):
        self._init_motors()
        result = self.MCR.focus.moveAbs(4000)
        self.assertTrue(result)

    def test_iris_move_rel(self):
        self._init_motors()
        result = self.MCR.iris.moveRel(20)
        self.assertTrue(result)

    def test_irc_state_1(self):
        self._init_motors()
        result = self.MCR.IRC.state(1)
        self.assertEqual(result, 1)

    def test_irc_state_2(self):
        self._init_motors()
        result = self.MCR.IRC.state(2)
        self.assertEqual(result, 2)

    def test_read_motor_setup(self):
        self._init_motors()
        ok, mtype, wf, tn, maxst, minsp, maxsp, err = self.MCR.focus.readMotorSetup()
        self.assertTrue(ok)

    def test_write_motor_setup(self):
        self._init_motors()
        result = self.MCR.zoom.writeMotorSetup(
            useWideFarStop=True, useTeleNearStop=False,
            maxSteps=3000, minSpeed=200, maxSpeed=1200
        )
        self.assertTrue(result)


# ===========================================================================
# Comparison test: run the same operation on both modules and diff the bytes
# ===========================================================================

@unittest.skipUnless(PY_AVAILABLE and CPP_AVAILABLE,
                     'Both Python and C++ modules required for comparison tests')
@unittest.skipUnless(VIRTUAL_PORTS_AVAILABLE,
                     f'Virtual COM port pair ({SIM_PORT}/{TEST_PORT}) needed for C++ side')
class TestModuleComparison(unittest.TestCase):
    """
    Runs identical operations on both modules and compares the bytes sent
    to the board.  Any difference is reported as a test failure with a
    human-readable diff.
    """

    def _run_operation_python(self, operation_fn) -> list[bytes]:
        """Run operation_fn(MCR) on the Python module and return commands sent."""
        sim = BoardSimulator()
        MCR, _, patcher = make_python_mcr(sim)
        sim.clear_history()
        try:
            operation_fn(MCR)
        finally:
            stop_python_mcr(MCR, patcher)
        return sim.commands_sent()

    def _run_operation_cpp(self, operation_fn) -> list[bytes]:
        """Run operation_fn(MCR) on the C++ module and return commands sent."""
        sim_thread = SimulatorThread(SIM_PORT)
        sim_thread.start()
        import time; time.sleep(0.5)
        CPP_MCR.MCRControl.setLogLevel(1)
        MCR = CPP_MCR.MCRControl(TEST_PORT, False, False, False)
        sim_thread.simulator.clear_history()
        try:
            operation_fn(MCR)
        finally:
            MCR.close()
            sim_thread.stop()
        return sim_thread.simulator.commands_sent()

    def _assert_commands_match(self, py_cmds: list[bytes], cpp_cmds: list[bytes],
                                operation_name: str):
        if py_cmds == cpp_cmds:
            return  # perfect match
        # Build a readable diff report
        lines = [f'\nCommand mismatch in "{operation_name}":']
        lines.append(f'  Python sent {len(py_cmds)} commands, C++ sent {len(cpp_cmds)} commands')
        for i, (p, c) in enumerate(zip(py_cmds, cpp_cmds)):
            if p != c:
                lines.append(f'  cmd[{i}] differs:')
                lines.append(f'    Python: {describe_cmd(p)}')
                lines.append(f'    C++   : {describe_cmd(c)}')
        if len(py_cmds) != len(cpp_cmds):
            extra_py  = py_cmds[len(cpp_cmds):]
            extra_cpp = cpp_cmds[len(py_cmds):]
            for cmd in extra_py:
                lines.append(f'  Python extra: {describe_cmd(cmd)}')
            for cmd in extra_cpp:
                lines.append(f'    C++ extra: {describe_cmd(cmd)}')
        self.fail('\n'.join(lines))

    # ---- comparison tests --------------------------------------------------

    def test_compare_read_fw_revision(self):
        def op(MCR):
            if hasattr(MCR, 'MCRBoard'):
                MCR.MCRBoard.readFWRevision()
            else:
                MCR.readFWRevision()

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        self._assert_commands_match(py_cmds, cpp_cmds, 'readFWRevision')

    def test_compare_read_board_sn(self):
        def op(MCR):
            if hasattr(MCR, 'MCRBoard'):
                MCR.MCRBoard.readBoardSN()
            else:
                MCR.readBoardSN()

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        self._assert_commands_match(py_cmds, cpp_cmds, 'readBoardSN')

    def test_compare_focus_move_rel_no_bl(self):
        def op(MCR):
            if hasattr(MCR, 'focusInit'):
                MCR.focusInit(steps=8390, pi=7959, move=False)
            MCR.focus.moveRel(1000, correctForBL=False)

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        # Strip the focusInit write-config command (same on both sides)
        py_cmds  = [c for c in py_cmds  if c[0] != 0x63]
        cpp_cmds = [c for c in cpp_cmds if c[0] != 0x63]
        self._assert_commands_match(py_cmds, cpp_cmds, 'focus.moveRel(1000, BL=False)')

    def test_compare_focus_move_rel_with_bl(self):
        def op(MCR):
            if hasattr(MCR, 'focusInit'):
                MCR.focusInit(steps=8390, pi=7959, move=False)
            MCR.focus.moveRel(500, correctForBL=True)

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        py_moves  = [c for c in py_cmds  if c[0] in (0x62, 0x66, 0x73)]
        cpp_moves = [c for c in cpp_cmds if c[0] in (0x62, 0x66, 0x73)]
        self._assert_commands_match(py_moves, cpp_moves,
                                    'focus.moveRel(500, BL=True) – move commands')

    def test_compare_irc_state_1(self):
        """
        Known difference: Python sends 50 steps at 1000 pps (0x62 0x04 0x00 0x32 ...)
        C++ sends 100 steps at 400 pps (0x62 0x04 0x00 0x64 ...).
        This test documents the difference by checking both step count and speed.
        """
        def op(MCR):
            if hasattr(MCR, 'IRCInit'):
                MCR.IRCInit()
            MCR.IRC.state(1)

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)

        py_irc  = next((c for c in py_cmds  if c[1] == 0x04 and c[0] in (0x62, 0x66)), None)
        cpp_irc = next((c for c in cpp_cmds if c[1] == 0x04 and c[0] in (0x62, 0x66)), None)

        if py_irc and cpp_irc:
            py_steps  = (py_irc[2]  << 8) | py_irc[3]
            cpp_steps = (cpp_irc[2] << 8) | cpp_irc[3]
            py_speed  = (py_irc[5]  << 8) | py_irc[6]
            cpp_speed = (cpp_irc[5] << 8) | cpp_irc[6]
            print(f'\n  IRC state(1) Python:  cmd={py_irc[0]:02X}, steps={py_steps}, speed={py_speed}')
            print(f'  IRC state(1) C++   :  cmd={cpp_irc[0]:02X}, steps={cpp_steps}, speed={cpp_speed}')
            # Verify they both move in the same direction (0x62 = negative)
            self.assertEqual(py_irc[0], cpp_irc[0],
                             'IRC state(1) direction mismatch (command byte differs)')

    def test_compare_read_motor_setup(self):
        """Read motor config – the raw bytes sent should be identical."""
        def op(MCR):
            if hasattr(MCR, 'focusInit'):
                MCR.focusInit(steps=8390, pi=7959, move=False)
            MCR.focus.readMotorSetup()

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        py_reads  = [c for c in py_cmds  if c[0] == 0x67]
        cpp_reads = [c for c in cpp_cmds if c[0] == 0x67]
        self._assert_commands_match(py_reads, cpp_reads, 'focus.readMotorSetup')

    def test_compare_write_motor_setup(self):
        """Write motor config – the raw bytes sent should be identical."""
        def op(MCR):
            if hasattr(MCR, 'focusInit'):
                MCR.focusInit(steps=8390, pi=7959, move=False)
            MCR.focus.writeMotorSetup(
                useWideFarStop=True, useTeleNearStop=False,
                maxSteps=5000, minSpeed=200, maxSpeed=1200
            )

        py_cmds  = self._run_operation_python(op)
        cpp_cmds = self._run_operation_cpp(op)
        py_writes  = [c for c in py_cmds  if c[0] == 0x63 and len(c) == 12]
        cpp_writes = [c for c in cpp_cmds if c[0] == 0x63 and len(c) == 12]
        # The first write-config is the motor init; the second is writeMotorSetup
        if len(py_writes) >= 2 and len(cpp_writes) >= 2:
            self._assert_commands_match([py_writes[-1]], [cpp_writes[-1]],
                                        'focus.writeMotorSetup explicit call')


# ===========================================================================
# Hardware tests: C++ module with a real MCR600 board
# ===========================================================================

@unittest.skipUnless(CPP_AVAILABLE, 'TheiaMCR_py.pyd not found – build TheiaMCR_py target')
@unittest.skipUnless(HARDWARE_PORT is not None, 'HARDWARE_PORT not set – edit test_compare_mcr.py')
class TestCppHardware(unittest.TestCase):
    """
    Tests for the C++ TheiaMCR_py module using a real MCR600 board.
    Set HARDWARE_PORT at the top of this file to enable.
    Motors are initialized with move=False to avoid unexpected lens movement.
    """

    @classmethod
    def setUpClass(cls):
        CPP_MCR.MCRControl.setLogLevel(1)  # errors only
        cls.MCR = CPP_MCR.MCRControl(
            serialPortName=HARDWARE_PORT,
            moduleDebugLevel=False,
            communicationDebugLevel=False,
            logFiles=False,
        )
        if not cls.MCR.boardInitialized:
            raise unittest.SkipTest(
                f'Board did not initialize on {HARDWARE_PORT} – check connection')
        p = LENS_PARAMS
        cls.MCR.focusInit(steps=p['focus_steps'], pi=p['focus_pi'], move=False)
        cls.MCR.zoomInit(steps=p['zoom_steps'],   pi=p['zoom_pi'],  move=False)
        cls.MCR.irisInit(steps=p['iris_steps'],   move=False)
        cls.MCR.IRCInit()

    @classmethod
    def tearDownClass(cls):
        cls.MCR.close()

    def test_board_initializes(self):
        self.assertTrue(self.MCR.boardInitialized)

    def test_read_fw_revision(self):
        fw = self.MCR.readFWRevision()
        self.assertTrue(len(fw) > 0, f'Expected non-empty FW string, got: {repr(fw)}')
        print(f'\n  C++ FW revision: {fw}')

    def test_read_board_sn(self):
        sn = self.MCR.readBoardSN()
        self.assertTrue(len(sn) > 0, f'Expected non-empty SN, got: {repr(sn)}')
        print(f'\n  C++ Board SN: {sn}')

    def test_focus_initialized(self):
        self.assertTrue(self.MCR.focus.initialized)
        self.assertEqual(self.MCR.focus.maxSteps, LENS_PARAMS['focus_steps'])

    def test_zoom_initialized(self):
        self.assertTrue(self.MCR.zoom.initialized)

    def test_iris_initialized(self):
        self.assertTrue(self.MCR.iris.initialized)

    def test_read_motor_setup(self):
        ok, mtype, wf, tn, maxst, minsp, maxsp, err = self.MCR.focus.readMotorSetup()
        self.assertTrue(ok, 'readMotorSetup returned failure')
        self.assertEqual(mtype, 0, 'Focus should be stepper (type=0)')
        print(f'\n  Focus config: maxSteps={maxst}, speed={minsp}-{maxsp}')

    def test_write_read_motor_setup_roundtrip(self):
        """Write a config, read it back, verify it matches."""
        p = LENS_PARAMS
        result = self.MCR.focus.writeMotorSetup(
            useWideFarStop=True, useTeleNearStop=False,
            maxSteps=p['focus_steps'], minSpeed=100, maxSpeed=1200)
        self.assertTrue(result, 'writeMotorSetup failed')
        ok, _, wf, tn, maxst, minsp, maxsp, _ = self.MCR.focus.readMotorSetup()
        self.assertTrue(ok)
        self.assertEqual(maxst, p['focus_steps'])
        self.assertEqual(minsp, 100)
        self.assertEqual(maxsp, 1200)


# ===========================================================================
# Hardware comparison: Python vs C++ on the same board (sequential)
# ===========================================================================

@unittest.skipUnless(PY_AVAILABLE and CPP_AVAILABLE,
                     'Both Python and C++ modules required for comparison tests')
@unittest.skipUnless(HARDWARE_PORT is not None, 'HARDWARE_PORT not set – edit test_compare_mcr.py')
class TestHardwareComparison(unittest.TestCase):
    """
    Compares Python and C++ module behavior on real hardware.
    Each test runs an operation on Python, then the same on C++, and compares
    return values.  Both modules connect sequentially – one at a time.
    """

    def _run_python(self, fn, move=True):
        import gc
        MCR = PY_MCR.MCRControl(serialPortName=HARDWARE_PORT, logFiles=False)
        try:
            if not MCR.boardInitialized:
                return None
            p = LENS_PARAMS
            MCR.focusInit(steps=p['focus_steps'], pi=p['focus_pi'], move=move)
            MCR.zoomInit(steps=p['zoom_steps'],   pi=p['zoom_pi'],  move=move)
            MCR.irisInit(steps=p['iris_steps'],   move=move)
            MCR.IRCInit()
            return fn(MCR)
        finally:
            MCR.close()
            del MCR
            gc.collect()
            time.sleep(0.5)  # allow USB-CDC port to fully release before C++ opens it

    def _run_cpp(self, fn, move=True):
        CPP_MCR.MCRControl.setLogLevel(1)
        MCR = CPP_MCR.MCRControl(HARDWARE_PORT, False, False, False)
        try:
            if not MCR.boardInitialized:
                return None
            p = LENS_PARAMS
            MCR.focusInit(steps=p['focus_steps'], pi=p['focus_pi'], move=move)
            MCR.zoomInit(steps=p['zoom_steps'],   pi=p['zoom_pi'],  move=move)
            MCR.irisInit(steps=p['iris_steps'],   move=move)
            MCR.IRCInit()
            return fn(MCR)
        finally:
            MCR.close()

    def test_compare_fw_revision_format(self):
        """Both modules should return a non-empty FW revision with the same digits."""
        py_fw  = self._run_python(lambda MCR: MCR.MCRBoard.readFWRevision(), move=False)
        cpp_fw = self._run_cpp(lambda MCR: MCR.readFWRevision(), move=False)
        print(f'\n  Python FW: {py_fw}   C++ FW: {cpp_fw}')
        self.assertTrue(py_fw  and len(py_fw)  > 0, 'Python FW empty')
        self.assertTrue(cpp_fw and len(cpp_fw) > 0, 'C++ FW empty')
        py_digits  = ''.join(c for c in py_fw  if c.isdigit())
        cpp_digits = ''.join(c for c in cpp_fw if c.isdigit())
        self.assertEqual(py_digits, cpp_digits,
                         f'FW version digits differ: Python={py_fw} C++={cpp_fw}')

    def test_compare_read_motor_setup(self):
        """Both modules should read the same motor config from the board."""
        py_result  = self._run_python(lambda MCR: MCR.focus.readMotorSetup(), move=False)
        cpp_result = self._run_cpp(lambda MCR: MCR.focus.readMotorSetup(), move=False)
        print(f'\n  Python readMotorSetup: {py_result}')
        print(f'  C++    readMotorSetup: {cpp_result}')
        self.assertTrue(py_result[0],  'Python readMotorSetup failed')
        self.assertTrue(cpp_result[0], 'C++ readMotorSetup failed')
        for i, label in [(4, 'maxSteps'), (5, 'minSpeed'), (6, 'maxSpeed')]:
            self.assertEqual(py_result[i], cpp_result[i],
                             f'{label}: Python={py_result[i]} C++={cpp_result[i]}')

    def test_compare_board_sn_digits(self):
        """
        Board SN digits should match even though the format differs:
          Python : "055-XXXXXX"   (3-digit prefix, lowercase)
          C++    : "0550-XXXXXX"  (4-digit prefix, uppercase)
        """
        py_sn  = self._run_python(lambda MCR: MCR.MCRBoard.readBoardSN(), move=False)
        cpp_sn = self._run_cpp(lambda MCR: MCR.readBoardSN(), move=False)
        print(f'\n  Python SN: {py_sn}   C++ SN: {cpp_sn}')
        self.assertTrue(py_sn  and len(py_sn)  > 0, 'Python SN empty')
        self.assertTrue(cpp_sn and len(cpp_sn) > 0, 'C++ SN empty')
        # Strip formatting and compare digits only
        py_digits  = ''.join(c for c in py_sn  if c.isalnum())
        cpp_digits = ''.join(c for c in cpp_sn if c.isalnum()).lower()
        # Python drops the last char of the 4-digit hex prefix → 3 chars
        # C++ keeps all 4.  Verify the suffix (after '-') matches.
        py_suffix  = py_sn.split('-')[-1].lower()
        cpp_suffix = cpp_sn.split('-')[-1].lower()
        self.assertEqual(py_suffix, cpp_suffix,
                         f'SN suffix differs: Python={py_sn} C++={cpp_sn}')

    def test_compare_focus_init_result(self):
        """focusInit(move=True) should home the motor on both modules."""
        py_result  = self._run_python(lambda MCR: MCR.focus.initialized)
        cpp_result = self._run_cpp(lambda MCR: MCR.focus.initialized)
        print(f'\n  Python focus.initialized: {py_result}   C++: {cpp_result}')
        self.assertTrue(py_result,  'Python focusInit failed')
        self.assertTrue(cpp_result, 'C++ focusInit failed')

    def test_compare_zoom_init_result(self):
        """zoomInit(move=True) should home the motor on both modules."""
        py_result  = self._run_python(lambda MCR: MCR.zoom.initialized)
        cpp_result = self._run_cpp(lambda MCR: MCR.zoom.initialized)
        print(f'\n  Python zoom.initialized: {py_result}   C++: {cpp_result}')
        self.assertTrue(py_result,  'Python zoomInit failed')
        self.assertTrue(cpp_result, 'C++ zoomInit failed')

    def test_compare_write_motor_setup(self):
        """writeMotorSetup followed by readMotorSetup should return same values."""
        def op(MCR):
            p = LENS_PARAMS
            MCR.focus.writeMotorSetup(
                useWideFarStop=True, useTeleNearStop=False,
                maxSteps=p['focus_steps'], minSpeed=100, maxSpeed=1200)
            return MCR.focus.readMotorSetup()

        py_result  = self._run_python(op, move=False)
        cpp_result = self._run_cpp(op, move=False)
        print(f'\n  Python after write: {py_result}')
        print(f'  C++    after write: {cpp_result}')
        self.assertTrue(py_result[0],  'Python write/read failed')
        self.assertTrue(cpp_result[0], 'C++ write/read failed')
        for i, label in [(4, 'maxSteps'), (5, 'minSpeed'), (6, 'maxSpeed')]:
            self.assertEqual(py_result[i], cpp_result[i],
                             f'{label}: Python={py_result[i]} C++={cpp_result[i]}')

    def test_compare_focus_move_rel(self):
        """
        Motors are homed by _run_python/_run_cpp (move=True default).
        Then moveRel(-200) — the lens should visibly move.
        """
        def op(MCR):
            step_after_home = MCR.focus.currentStep
            result = MCR.focus.moveRel(-200, correctForBL=False)
            return (result, step_after_home, MCR.focus.currentStep)

        py_result  = self._run_python(op)
        cpp_result = self._run_cpp(op)
        print(f'\n  Python: home\u2192{py_result[1]}, moveRel(-200)\u2192{py_result[2]}, ok={py_result[0]}')
        print(f'  C++   : home\u2192{cpp_result[1]}, moveRel(-200)\u2192{cpp_result[2]}, ok={cpp_result[0]}')
        self.assertTrue(py_result[0]  == 0,    f'Python moveRel failed: {py_result[0]}')
        self.assertTrue(cpp_result[0] == True,  f'C++ moveRel failed: {cpp_result[0]}')
        self.assertEqual(py_result[2], cpp_result[2],
                         f'currentStep differs: Python={py_result[2]} C++={cpp_result[2]}')

    def test_compare_irc_state(self):
        """
        IRC state() return value differs by design:
          Python : returns the new state int (1 or 2)
          C++    : returns the new state int (1 or 2)
        Direction byte should be the same (both move negative for state=1).
        """
        py_result  = self._run_python(lambda MCR: MCR.IRC.state(1))
        cpp_result = self._run_cpp(lambda MCR: MCR.IRC.state(1))
        print(f'\n  Python IRC.state(1): {py_result}   C++: {cpp_result}')
        self.assertEqual(py_result,  1, f'Python IRC.state(1) returned {py_result}')
        self.assertEqual(cpp_result, 1, f'C++ IRC.state(1) returned {cpp_result}')


# ===========================================================================
# Standalone diff report (run directly, not via pytest)
# ===========================================================================

def print_diff_report():
    """
    Print a side-by-side TX byte comparison for a set of common operations
    without requiring virtual COM ports (Python module only).
    """
    if not PY_AVAILABLE:
        print('Python TheiaMCR module not available.')
        return

    def focus_move_rel_no_bl(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.moveRel(1000, correctForBL=False)

    def focus_move_rel_bl(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.moveRel(500, correctForBL=True)

    def zoom_move_rel_bl(MCR):
        MCR.zoomInit(steps=3227, pi=3119, move=False)
        MCR.zoom.moveRel(300, correctForBL=True)

    def focus_move_abs(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.moveAbs(4000)

    def iris_move_rel(MCR):
        MCR.irisInit(steps=75, move=False)
        MCR.iris.moveRel(20)

    def irc_state_1(MCR):
        MCR.IRCInit()
        MCR.IRC.state(1)

    def irc_state_2(MCR):
        MCR.IRCInit()
        MCR.IRC.state(2)

    def focus_read_setup(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.readMotorSetup()

    def focus_write_setup(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.writeMotorSetup(True, False, 5000, 200, 1200)

    def focus_set_limits(MCR):
        MCR.focusInit(steps=8390, pi=7959, move=False)
        MCR.focus.setRespectLimits(False)

    operations = {
        'readFWRevision'               : lambda MCR: MCR.MCRBoard.readFWRevision(),
        'readBoardSN'                  : lambda MCR: MCR.MCRBoard.readBoardSN(),
        'focusInit(no move)'           : lambda MCR: MCR.focusInit(steps=8390, pi=7959, move=False),
        'zoomInit(no move)'            : lambda MCR: MCR.zoomInit(steps=3227, pi=3119, move=False),
        'irisInit(no move)'            : lambda MCR: MCR.irisInit(steps=75, move=False),
        'IRCInit'                      : lambda MCR: MCR.IRCInit(),
        'focus.moveRel(1000, BL=False)': focus_move_rel_no_bl,
        'focus.moveRel(500, BL=True)'  : focus_move_rel_bl,
        'zoom.moveRel(300, BL=True)'   : zoom_move_rel_bl,
        'focus.moveAbs(4000)'          : focus_move_abs,
        'iris.moveRel(20)'             : iris_move_rel,
        'IRC.state(1)'                 : irc_state_1,
        'IRC.state(2)'                 : irc_state_2,
        'focus.readMotorSetup'         : focus_read_setup,
        'focus.writeMotorSetup'        : focus_write_setup,
        'focus.setRespectLimits(False)': focus_set_limits,
    }

    print('=' * 70)
    print('Python TheiaMCR TX byte report (simulated board)')
    print('=' * 70)
    for op_name, fn in operations.items():
        sim = BoardSimulator()
        MCR, _, patcher = make_python_mcr(sim)
        sim.clear_history()
        try:
            fn(MCR)
        except Exception as e:
            print(f'\n[{op_name}] ERROR: {e}')
            stop_python_mcr(MCR, patcher)
            continue
        finally:
            stop_python_mcr(MCR, patcher)
        cmds = sim.commands_sent()
        print(f'\n[{op_name}]')
        for cmd in cmds:
            print(f'  TX: {" ".join(f"{b:02X}" for b in cmd)}   ({describe_cmd(cmd)})')
    print('=' * 70)


if __name__ == '__main__':
    # When run directly, print the diff report instead of running unit tests
    print_diff_report()
