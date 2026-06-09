#ifndef SIMPLE_SERIAL_H
#define SIMPLE_SERIAL_H

#include <string>
#include <vector>
#include <cstdint>

class SimpleSerial {
private:
#ifdef _WIN32
    void* hSerial = nullptr; // HANDLE — avoids pulling windows.h into headers
#else
    int fd = -1;
#endif
    bool connected = false;

public:
    SimpleSerial();
    ~SimpleSerial();

    bool open(const std::string& portName, int baudRate = 115200);
    void close();
    bool isOpen() const { return connected; }

    int write(const std::vector<uint8_t>& data);
    int read(std::vector<uint8_t>& data, size_t maxLen, int timeoutMs = 500);
    int inWaiting();
};

#endif // SIMPLE_SERIAL_H
