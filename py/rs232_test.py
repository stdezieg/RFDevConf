import serial
import time
import sys
import glob

import random

ser = serial.Serial(port='COM7', baudrate=115200, timeout=1)   # max rating about 1 Mbaud/s
print("found serial port 'COM7' ... opening ... success!!!")    # (DIGITUS, USB <-> RS232)


test_string = "AAFF01FF02FF03FF04FF05FF06FF07FF08FF09FF0AFF0BFF0CFF0DFF0EFFAAFF"

mod_test_string = format(int(test_string, 16), "0256b")
print(len(mod_test_string),mod_test_string)

test_checksum = mod_test_string.count('1')
print("test checksum is:", test_checksum)



time.sleep(10)

while True:
    rand_int = random.randint(0,255)
    ser.write(rand_int.to_bytes(1,'big'))
    print(rand_int.to_bytes(1,'big'))
    #ser.write(b'\x1a')
    time.sleep(3)
    #print("triggered")
    #ser.read(1)
    print("bytes waiting at input:", ser.inWaiting())
    if ser.inWaiting() > 10:
        print(ser.read(10))
