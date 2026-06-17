"""
MCR600 Board Simulator
======================
Simulates the MCR600 series board serial protocol so that both the Python
TheiaMCR module and the C++ TheiaMCR_py module can be tested without real
hardware.

Usage (Python module – via MockSerial):
    sim = BoardSimulator()
    mock = MockSerial(sim)
    with patch('TheiaMCR.TheiaMCR.serial.Serial', return_value=mock):
        MCR = TheiaMCR.MCRControl('MOCK', logFiles=False)

Usage (C++ module – via SimulatorThread on a virtual COM port pair):
    # Requires com0com or similar virtual COM port pair, e.g. COM10 <-> COM11
    thread = SimulatorThread('COM10')   # simulator end
    thread.start()
    MCR = TheiaMCR_py.MCRControl('COM11')   # module under test
    thread.stop()

Protocol quick reference
------------------------
  0x76 0x0D                         -> FW revision (7 bytes)
  0x79 0x0D                         -> Board SN (8 bytes)
  0x63 <motor> ... 0x0D (12 bytes)  -> Write motor config  -> [0x63, 0x00, 0x0D]
  0x67 <motor> 0x0D                 -> Read motor config   -> 12-byte reply
  0x62/0x66/0x73 <motor>... 0x0D   -> Motor move          -> [cmd, 0x00, 0x0D]
  0x6B <path> 0x0D                  -> Set comm path       -> no response (handled specially)
"""
# pyright: reportOptionalMemberAccess=false

from __future__ import annotations
import threading
import queue
import time
from typing import Optional


# ---------------------------------------------------------------------------
# Board Simulator – pure protocol logic, no I/O
# ---------------------------------------------------------------------------

class BoardSimulator:
    """
    Translates MCR600 command byte strings into board response byte strings.

    The simulator maintains a simple motor configuration store so that
    0x63 (write) / 0x67 (read) config commands are coherent within a session.
    All motor move commands (0x62, 0x66, 0x73) succeed immediately.
    """

    # Default FW revision bytes (produces "5.3.1.0.0" in both Python and C++)
    FW_BYTES: list[int] = [0x05, 0x03, 0x01, 0x00, 0x00]

    # Default board SN bytes [A, B, C, D, E, F]
    # Python:  f'{A:02x}{B:02x}'[:-1] + f'-{D:02x}{E:02x}{F:02x}'  -> "055-000102"
    # C++:     "%02X%02X-%02X%02X%02X"                               -> "0550-000102"
    SN_BYTES: list[int] = [0x05, 0x50, 0x00, 0x01, 0x02, 0x03]

    def __init__(self) -> None:
        # Motor configuration store (mirrors board EEPROM state)
        self._motors: dict[int, dict] = {
            0x01: {'type': 0, 'wideFar': 1, 'teleNear': 0, 'maxSteps': 9353, 'minSpeed': 100, 'maxSpeed': 1500},
            0x02: {'type': 0, 'wideFar': 1, 'teleNear': 0, 'maxSteps': 4073, 'minSpeed': 100, 'maxSpeed': 1500},
            0x03: {'type': 0, 'wideFar': 0, 'teleNear': 0, 'maxSteps': 75,   'minSpeed': 10,  'maxSpeed': 200},
            0x04: {'type': 1, 'wideFar': 0, 'teleNear': 0, 'maxSteps': 1000, 'minSpeed': 10,  'maxSpeed': 1000},
        }
        # All (command, response) pairs captured during this session
        self.history: list[tuple[bytes, bytes]] = []

    # ------------------------------------------------------------------
    def respond(self, cmd: bytes) -> bytes:
        """Return the board's response bytes for a given command."""
        if not cmd:
            return bytes([0x74, 0x01, 0x0D])  # error / no-op

        b0 = cmd[0]

        # ---- FW revision ----
        if b0 == 0x76:
            resp = bytes([0x76] + self.FW_BYTES + [0x0D])

        # ---- Board serial number ----
        elif b0 == 0x79:
            resp = bytes([0x79] + self.SN_BYTES + [0x0D])

        # ---- Write motor config ----
        elif b0 == 0x63 and len(cmd) >= 12:
            mid = cmd[1]
            if mid in self._motors:
                self._motors[mid] = {
                    'type':     cmd[2],
                    'wideFar':  cmd[3],
                    'teleNear': cmd[4],
                    'maxSteps': (cmd[5] << 8) | cmd[6],
                    'minSpeed': (cmd[7] << 8) | cmd[8],
                    'maxSpeed': (cmd[9] << 8) | cmd[10],
                }
                resp = bytes([0x63, 0x00, 0x0D])
            else:
                resp = bytes([0x63, 0x01, 0x0D])  # unknown motor id

        # ---- Read motor config ----
        elif b0 == 0x67 and len(cmd) >= 3:
            mid = cmd[1]
            if mid in self._motors:
                m = self._motors[mid]
                resp = bytes([
                    0x67, mid, m['type'],
                    m['wideFar'], m['teleNear'],
                    (m['maxSteps'] >> 8) & 0xFF, m['maxSteps'] & 0xFF,
                    (m['minSpeed'] >> 8) & 0xFF, m['minSpeed'] & 0xFF,
                    (m['maxSpeed'] >> 8) & 0xFF, m['maxSpeed'] & 0xFF,
                    0x0D,
                ])
            else:
                # invalid motor id
                resp = bytes([0x67, 0xFF, 0xFF, 0xFF, 0xFF,
                              0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x0D])

        # ---- Motor move commands ----
        elif b0 in (0x62, 0x66, 0x73):
            resp = bytes([b0, 0x00, 0x0D])
            # Simulate motor travel time: delay = steps / speed (seconds).
            # cmd layout: [cmd, motor_id, steps_hi, steps_lo, 0x01, spd_hi, spd_lo, 0x0D]
            if len(cmd) >= 7:
                steps = (cmd[2] << 8) | cmd[3]
                speed = (cmd[5] << 8) | cmd[6]
                if speed > 0:
                    delay = steps / speed  # seconds
                    time.sleep(delay)

        # ---- Set communication path (board reboots; no real response) ----
        elif b0 == 0x6B:
            # The Python module forces a synthetic success response for this command.
            # The C++ implementation waits for a response that never comes, so keep
            # it short but valid-looking.
            resp = bytes([0x6B, 0x00, 0x0D])

        else:
            resp = bytes([0x74, 0x01, 0x0D])  # unknown command

        self.history.append((bytes(cmd), resp))
        return resp

    def clear_history(self) -> None:
        self.history.clear()

    def commands_sent(self) -> list[bytes]:
        """Return the list of commands received by the simulator."""
        return [h[0] for h in self.history]

    def format_history(self) -> str:
        """Human-readable log of all TX/RX pairs."""
        lines = []
        for cmd, resp in self.history:
            tx = ' '.join(f'{b:02X}' for b in cmd)
            rx = ' '.join(f'{b:02X}' for b in resp)
            lines.append(f'  TX: {tx}\n  RX: {rx}')
        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# MockSerial – drop-in replacement for serial.Serial (Python module tests)
# ---------------------------------------------------------------------------

class MockSerial:
    """
    Wraps a BoardSimulator and presents a pyserial-compatible interface so
    the Python TheiaMCR module can be tested without a real COM port.

    Patch into the Python module like this::

        with patch('TheiaMCR.TheiaMCR.serial.Serial', return_value=MockSerial(sim)):
            MCR = TheiaMCR.MCRControl('MOCK', logFiles=False)
    """

    def __init__(self, simulator: BoardSimulator) -> None:
        self.simulator = simulator
        self._buf = bytearray()
        self.is_open = True

    # pyserial interface -------------------------------------------------------

    def write(self, data) -> int:
        response = self.simulator.respond(bytes(data))
        self._buf.extend(response)
        return len(data)

    @property
    def in_waiting(self) -> int:
        return len(self._buf)

    def readline(self) -> bytes:
        idx = self._buf.find(0x0D)
        if idx == -1:
            data = bytes(self._buf)
            self._buf.clear()
        else:
            data = bytes(self._buf[: idx + 1])
            del self._buf[: idx + 1]
        return data

    def read(self, size: int = 1) -> bytes:
        data = bytes(self._buf[:size])
        del self._buf[:size]
        return data

    def close(self) -> None:
        self.is_open = False

    def flush(self) -> None:
        pass


# ---------------------------------------------------------------------------
# SimulatorThread – runs a BoardSimulator on one side of a virtual COM pair
# ---------------------------------------------------------------------------

class SimulatorThread:
    """
    Opens a real (virtual) COM port and runs a BoardSimulator in a background
    thread.  Designed for C++ module tests that require a real serial handle.

    Requires a virtual COM port pair, e.g. from com0com:
        COM10  <-->  COM11
    Pass the *simulator* end (e.g. COM10) to this class and point the module
    under test at the *other* end (e.g. COM11).

    Installation (one-time, Windows):
        1. Download com0com from https://sourceforge.net/projects/com0com/
        2. Install and create a pair, e.g. COM10 <-> COM11
    """

    def __init__(self, port_name: str, baud: int = 115200) -> None:
        self.port_name = port_name
        self.baud = baud
        self.simulator = BoardSimulator()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._port = None

    def start(self) -> None:
        """Open the COM port and start the simulator thread."""
        import serial  # type: ignore
        self._port = serial.Serial(
            port=self.port_name,
            baudrate=self.baud,
            bytesize=8,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
        )
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._port and self._port.is_open:
            self._port.close()

    def _run(self) -> None:
        # Flush any stale bytes left in the com0com buffer from a previous session
        try:
            self._port.reset_input_buffer()
        except Exception:
            pass
        buf = bytearray()
        while not self._stop_event.is_set():
            try:
                chunk = self._port.read(64)
            except Exception:
                break
            if chunk:
                buf.extend(chunk)
                # Process complete commands (terminated by 0x0D)
                while 0x0D in buf:
                    idx = buf.index(0x0D)
                    cmd = bytes(buf[: idx + 1])
                    del buf[: idx + 1]
                    response = self.simulator.respond(cmd)
                    # Small delay to mimic real board processing time
                    time.sleep(0.002)
                    try:
                        self._port.write(response)
                    except Exception:
                        return


# ---------------------------------------------------------------------------
# Convenience: check whether a virtual COM port pair is available
# ---------------------------------------------------------------------------

def virtual_ports_available(port_a: str, port_b: str) -> bool:
    """Return True if both ports can be opened (i.e. com0com pair exists)."""
    try:
        import serial  # type: ignore
        with serial.Serial(port=port_a, baudrate=115200, timeout=0.1):
            pass
        with serial.Serial(port=port_b, baudrate=115200, timeout=0.1):
            pass
        return True
    except Exception:
        return False
