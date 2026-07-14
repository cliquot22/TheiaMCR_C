#include "SimpleSerial.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#endif

SimpleSerial::SimpleSerial() {
#ifdef _WIN32
    hSerial = INVALID_HANDLE_VALUE;
#else
    fd = -1;
#endif
}

SimpleSerial::~SimpleSerial() {
    close();
}

bool SimpleSerial::open(const std::string& portName, int baudRate) {
    close();

#ifdef _WIN32
    std::string fullPortName = "\\\\.\\" + portName;
    HANDLE hComm = CreateFileA(fullPortName.c_str(),
        GENERIC_READ | GENERIC_WRITE, 0, NULL,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hComm == INVALID_HANDLE_VALUE) {
        return false;
    }
    hSerial = hComm;

    DCB dcb = {0};
    dcb.DCBlength = sizeof(dcb);
    if (!GetCommState(static_cast<HANDLE>(hSerial), &dcb)) {
        close();
        return false;
    }
    dcb.BaudRate          = CBR_115200;
    dcb.ByteSize          = 8;
    dcb.StopBits          = ONESTOPBIT;
    dcb.Parity            = NOPARITY;
    dcb.fOutxCtsFlow      = FALSE;
    dcb.fOutxDsrFlow      = FALSE;
    dcb.fDtrControl       = DTR_CONTROL_ENABLE;
    dcb.fDsrSensitivity   = FALSE;
    dcb.fTXContinueOnXoff = TRUE;
    dcb.fOutX             = FALSE;
    dcb.fInX              = FALSE;
    dcb.fRtsControl       = RTS_CONTROL_ENABLE;
    if (!SetCommState(static_cast<HANDLE>(hSerial), &dcb)) {
        close();
        return false;
    }

    // ReadTotalTimeoutConstant is overridden per-call in read().
    COMMTIMEOUTS timeouts = {0};
    timeouts.ReadTotalTimeoutConstant = 500;
    SetCommTimeouts(static_cast<HANDLE>(hSerial), &timeouts);

#else
    fd = ::open(portName.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
    if (fd == -1) {
        return false;
    }
    fcntl(fd, F_SETFL, 0); // Clear non-blocking

    struct termios tty;
    if (tcgetattr(fd, &tty) != 0) {
        ::close(fd);
        fd = -1;
        return false;
    }

    cfsetospeed(&tty, B115200);
    cfsetispeed(&tty, B115200);

    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_iflag &= ~IGNBRK;
    tty.c_lflag = 0; // Raw input
    tty.c_oflag = 0; // Raw output
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 1; // 100ms timeout
    tty.c_cflag |= (CLOCAL | CREAD);
    tty.c_cflag &= ~(PARENB | PARODD);
    tty.c_cflag &= ~CSTOPB;
    tty.c_cflag &= ~CRTSCTS;

    if (tcsetattr(fd, TCSANOW, &tty) != 0) {
        ::close(fd);
        fd = -1;
        return false;
    }
#endif

    connected = true;
    return true;
}

void SimpleSerial::close() {
    if (!connected) return;

#ifdef _WIN32
    if (hSerial != INVALID_HANDLE_VALUE) {
        // v.3.5.1 bug fix: flush buffers before closing
        PurgeComm(static_cast<HANDLE>(hSerial), 
                  PURGE_RXABORT | PURGE_RXCLEAR | PURGE_TXABORT | PURGE_TXCLEAR);
        CloseHandle(static_cast<HANDLE>(hSerial));
        hSerial = INVALID_HANDLE_VALUE;
    }
#else
    if (fd != -1) {
        // v.3.5.1 bug fix: flush buffers before closing
        tcdrain(fd);  // Wait for output to drain
        tcflush(fd, TCIOFLUSH);  // Flush input and output
        ::close(fd);
        fd = -1;
    }
#endif

    connected = false;
}

int SimpleSerial::write(const std::vector<uint8_t>& data) {
    if (!connected) return -1;

#ifdef _WIN32
    DWORD bytesWritten = 0;
    if (!WriteFile(static_cast<HANDLE>(hSerial),
                   data.data(), static_cast<DWORD>(data.size()),
                   &bytesWritten, NULL)) {
        return -1;
    }
    return static_cast<int>(bytesWritten);
#else
    return ::write(fd, data.data(), data.size());
#endif
}

int SimpleSerial::read(std::vector<uint8_t>& data, size_t maxLen, int timeoutMs) {
    if (!connected) return -1;

    data.clear();
#ifdef _WIN32
    // Set the total read timeout, then do a plain synchronous ReadFile.
    // This works reliably on real USB-CDC hardware (the original approach).
    COMMTIMEOUTS ct = {0};
    ct.ReadTotalTimeoutConstant = static_cast<DWORD>(timeoutMs > 0 ? timeoutMs : 1);
    SetCommTimeouts(static_cast<HANDLE>(hSerial), &ct);

    DWORD bytesRead = 0;
    std::vector<uint8_t> buffer(maxLen);
    if (!ReadFile(static_cast<HANDLE>(hSerial),
                  buffer.data(), static_cast<DWORD>(maxLen),
                  &bytesRead, NULL)) {
        return -1;
    }
    buffer.resize(bytesRead);
    data = buffer;
    return static_cast<int>(bytesRead);
#else
    struct timeval timeout;
    timeout.tv_sec = timeoutMs / 1000;
    timeout.tv_usec = (timeoutMs % 1000) * 1000;

    fd_set read_fds;
    FD_ZERO(&read_fds);
    FD_SET(fd, &read_fds);

    int r = select(fd + 1, &read_fds, NULL, NULL, &timeout);
    if (r <= 0) return r; // 0 for timeout, -1 for error

    std::vector<uint8_t> buffer(maxLen);
    int n = ::read(fd, buffer.data(), maxLen);
    if (n < 0) return -1;
    buffer.resize(n);
    data = buffer;
    return n;
#endif
}

int SimpleSerial::inWaiting() {
    if (!connected) return -1;

#ifdef _WIN32
    DWORD errors;
    COMSTAT status;
    if (ClearCommError(static_cast<HANDLE>(hSerial), &errors, &status)) {
        return static_cast<int>(status.cbInQue);
    }
    return -1;
#else
    int bytes = 0;
    if (ioctl(fd, FIONREAD, &bytes) == 0) {
        return bytes;
    }
    return -1;
#endif
}
