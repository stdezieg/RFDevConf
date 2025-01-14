import time
import sys
import glob
import serial
import argparse
import random
import math

from bitstring import BitArray
from itertools import islice
from alive_progress import alive_bar


def get_serial_ports():
    # scanning all available serial ports
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    port_list = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            port_list.append(port)
        except (OSError, serial.SerialException):
            pass
    return port_list


def open_serial_port(input_port_list):
    # opens first available serial port from input_port_list
    print("available Ports:", input_port_list)
    baudrate = 115200
    while True:
        try:
            ser = serial.Serial(port=input_port_list[0], baudrate=115200, timeout=1)  # open serial port
            print("opened serial port '%s' with %d baudrate! :-)\n" % (input_port_list[0],baudrate))
            port_open = 1
            break
        except Exception as e:
            input_port_list.pop(0) # drop list element
    return ser


def bitstring_to_bytes(s):
    # converts "10101001010" (str) ->  b'' (bytes)
    return int(s, 2).to_bytes(len(s) // 8, byteorder='big')


def read_from_hex(input_hexfile):
    # stores hex file content in list
    with open(input_hexfile) as file_in:
        lines = []
        for line in file_in:
            lines.append(line)  # append hex file row to list
        lines = lines[0:-1]     # drop end of file row
    # print(lines)
    return lines


def formatRegDiscription(MemAddress, MemContent16bitHex):
    # convert address from integer to 4 hexadecimal digits (i.e. 16 bit)
    hexAddress = format(MemAddress,'08x')[-4:]
    # add memory content, hexString has now 2+4+2+4=12 hexadecimal digits
    hexString = '02' + hexAddress + '00' + MemContent16bitHex
    # calculate parity check
    b = 0
    for i in range(0,11,2):
        b = b + int(hexString[i:i+2], 16) # byte-wise summation
    hexParityCheck = hex((-b + (1 << 32)) % (1 << 32)) # calculate hex for -b assuming 32 bit
    hexParityCheck = hexParityCheck[len(hexParityCheck)-2:len(hexParityCheck)] # take only the last two hex digits
    # the return value has 1+12+2=15 hexadecimal digits
    return ':' + hexString.upper() + hexParityCheck.upper()
# by Dieter Lens


def gen_hexfile(hexfile_data_as_list):
    # takes list of data (2 bytes per element) and converts it to hex file
    hexfile = open("output.hex", "w")
    local_addr = 0
    for element in hexfile_data_as_list:
        tmp = hex(local_addr)[2:].zfill(4).upper()
        tmp2 = formatRegDiscription(int(tmp,16),element)
        hexfile.write(tmp2 + "\n")
        local_addr = local_addr + 1
        hexfile.write(":00000001FF")
        hexfile.close()
    print("... written to output.hex")


def mergeFrameContent(header, device_id, address, checksum, data):
    #  merge all strings into 1 chunk (no leading zeros + dont care bits)
    return header + device_id + address + checksum + data


def genChecksum(input_binary_string):
    # take binary input string (max len: 256) -> count all "1" -> return value as binary string in 8 bit format
    checksum_int = bin(int(input_binary_string,16)).count('1')
    output_binary_string = format(checksum_int,"08b")
    if len(output_binary_string) == 9:
        return output_binary_string[1:]
    else:
        return output_binary_string


def genHeader(RnW, error, Number_of_bytes, answ, flash):
    # generate 8-bit (str) header for protocol frame
    header_frame = str(RnW) + str(error) + format(Number_of_bytes-1, "05b") + str(answ) + str(flash)
    return header_frame


def genNumberOfBytes(input_int):
    # get number of bytes (max 31) as binary string (5-bit)
    return format(input_int, "05b")


def genAddress(input_address_as_integer):
    # get address as int -> format to 24-bit binary string
    return format(input_address_as_integer, "024b")


def genDeviceID(input_device_as_integer):
    # get device_id as int -> format to 8-bit binary string
    return format(input_device_as_integer, "08b")


def genDataFrame(input_data_as_string):
    # take string (hex-format) and convert it to binary string (max 32 byte)
    data = format(int(input_data_as_string, 16), "0256b")
    x =  len(input_data_as_string)
    data = data[256-(x*4):]
    return data


def writeRequest(address, device_id , data, flash):
    byte_amount = len(data) // 2
    remainder = len(data) % 2
    if remainder == 0:
        v1 = genHeader(0, 0, byte_amount, "0", flash)
        v2 = genDeviceID(device_id)
        v3 = genAddress(address)
        v5 = genDataFrame(data)
        v4 = genChecksum(data)
        # print("checksum (bin) is:",v4)
        return v1 + v2 + v3 + v4 + v5
    else:
        print("error: input data contains incomplete byte!")


def readRequest(address = 0, device_id = 255, byte_amount_int=1, flash = 0):
    #   generating read request string (without frame indicator bits)
    v1 = genHeader(1, 0, byte_amount_int, 0, flash)
    v2 = genDeviceID(device_id)
    v3 = genAddress(address)
    return v1 + v2 + v3


def expectedValue(number_of_bytes_as_int):
    #   header(7) + answ & flash (2) + device_id (8) + address (24) + checksum (8) + ...
    return  7 + 2 + 8 + 24 + 8 + number_of_bytes_as_int * 8


def writeRequest_wFI(input_raw_frame):
    # taking write request and adding frame indicator bits & don't care bits at the end of the frame
        output_frame = []
        iterations = int(math.ceil(len(input_raw_frame)/7))

        for i in range(iterations): # !!!
            left_boundary = i*7
            right_boundary = (i*7)+7
            if i == 0:
                output_frame.append("1" + input_raw_frame[left_boundary:right_boundary])
            else:
                output_frame.append("0" + input_raw_frame[left_boundary:right_boundary])

        if len(output_frame[-1]) < 8:
            output_frame[-1] = output_frame[-1] + "0" * (8-len(output_frame[-1]))
            # print("hey" ,output_frame[-1])

        return ''.join(map(str, output_frame))


def readRequest_wFI(input_raw_frame):
        # taking read request and adding frame indicator bits & don't care bits at the end of the frame
        output_frame = []
        for i in range(6):
            left_boundary = i*7
            right_boundary = (i*7)+7
            if i == 0:
                output_frame.append("1" + input_raw_frame[left_boundary:right_boundary])
            elif i == 5:
                output_frame.append("0" + input_raw_frame[left_boundary:right_boundary] + "0")
                # output_frame.append("0" + input_raw_frame[left_boundary:right_boundary])
                pass
            else:
                output_frame.append("0" + input_raw_frame[left_boundary:right_boundary])
        # print(output_frame)
        # print(''.join(map(str, output_frame)))
        return ''.join(map(str, output_frame))


def displayProtocolFrame(inputFrame):
    # displaying protocol frame (without leading zeros and don't care bits) for debugging purposes
    test = []
    frame_size = 7
    frame_offset = 0

    for i in range((len(inputFrame) // frame_size + 1)) :
        left_boundary = i*7
        right_boundary = (i*7)+7
        test.append(inputFrame[left_boundary:right_boundary])
    try:
        for i in range((len(inputFrame) // frame_size + 1)):
            # print(test[i])
            # print("-")
            pass
    except Exception as e:
        print(e)
    print(test)

def readSerial():
    if ser.inWaiting() > 0:
        input_data = ser.read(44)
        #transform = BitArray(input_data)
        return BitArray(input_data).bin

def cutInputFrame():
    # read dataframe (max 44 byte) if data is waiting at serial port
    raw_data = []
    if ser.inWaiting() > 0:
        input_data = ser.read(44)       # evtl dynamisch implementieren??
        # print("raw data is:",input_data)

        transform = BitArray(input_data)
        transform = transform.bin
        # print(transform)
        # print("len of transform is:",len(transform))

        for i in range((len(transform)//8)):
            transform = transform [1:]
            # print("1# transform is:",transform)
            raw_data.append(transform[:7])
            # print("raw_data is:",raw_data)
            transform = transform [7:]
            # print("2# transform is:",transform)
        # print(len(raw_data))
        info = len(raw_data)

        final_output = ''.join(map(str, raw_data))

        # print(len(final_output),final_output)
        # print(final_output[49:])
        nr_bytes = int(final_output[2:7], 2) + 1 # unnötig?!
        # print(nr_bytes)

        # print(final_output[0:49+(8*nr_bytes)])
        # final_output = final_output[:nr_bytes*8]
        # print(final_output[:len(final_output)-(nr_bytes*8)])
        # print(final_output[:-1])
        return final_output


def evaluateInputFrame(input_frame_raw):
    # extracting data from input frame
    RnW = input_frame_raw[1]
    error = input_frame_raw[2]
    Number_of_Bytes = int(input_frame_raw[2:7], 2) + 1
    device_id = int(input_frame_raw[8:17], 2)
    address = int(input_frame_raw[17:41], 2)
    checksum = int(input_frame_raw[41:49], 2)
    # print(input_frame_raw[41:49])

    output_list = [RnW, error, Number_of_Bytes, device_id,address, checksum]
    # print(RnW, error, Number_of_Bytes, device_id,address, checksum)
    # print(output_list)
    return output_list

def byte_string32_to_bitstring(bytestring_32):
    return format(int(bytestring_32, 16), "0256b")


def hexflash(hexfile_as_list):
    hex_file_data = []
    for i in range(len(hexfile_as_list)):
        hex_file_data.append(hexfile_as_list[i][9:-3])
    hex_file_data = ''.join(hex_file_data)

    # print(hex_file_data)
    # print(len(hex_file_data)//4) # hex file complete? needs to match with hex file line count...

    byte_packet_32 =  hex_file_data[0:64]
    print(len(byte_packet_32), byte_packet_32)
    # print(len(hex_file_data)//2)
    hex_file_data = hex_file_data[64:]

    data_out = bitstring_to_bytes(byte_string32_to_bitstring(byte_packet_32))
    # print(data_out)
    ser.write(data_out)

    time.sleep(0.2)

    print(ser.inWaiting())
    data_in = BitArray(ser.read(32))

    print(data_in)

# transform = BitArray(input_data)
#         transform = transform.bin
def extractData(cut_inputframe):
    return cut_inputframe[49:-3]


def fpga_frame_test(): # send request to fpga and verify answer

    read_request = readRequest_wFI(readRequest(0,0,32,0))
    write_request = writeRequest_wFI(writeRequest(0,0,"FF"*32, 0))

    RnW = 1

    if RnW == 0:
        ser.write(bitstring_to_bytes(write_request))
    else:
        ser.write(bitstring_to_bytes(read_request))

    time.sleep(0.1)
    print(ser.inWaiting())
    input = readSerial()
    print(len(input),input)
    for i in range(6):  # print read request differently (8 bytes per line)
        print(input[8*i:(8*i)+8])


class receive_frame:
    def __init__(self, raw_input_frame): # evtl noch von bytes in bitstring wandeln?
        # print(raw_input_frame)
        self.cleanup = self.drop_frame_indicator(raw_input_frame)
        self.header = self.cleanup[:9]       # [0] = RnW; [1] = Error; [2-6] = Byte Amount; [7] = Answ;
        self.address = int(self.cleanup[9:41], 2)
        self.checksum = int(self.cleanup[41:49], 2)
        self.data = self.cleanup[49:]
        # print("Header:", self.header[:-2])

        if self.header[0] == "1":
            self.checksum_internal = int(format(bin(int(self.data,16)).count('1'),"08b"),2)
            if self.checksum == self.checksum_internal:
                self.correct_checksum = True
            else:
                self.correct_checksum = False


        if self.header[-1] == "1":
            self.flash = True
        else:
            self.flash = False

        ### cut out dont care bits out of data section:
        if self.header[0] == "1":
            self.data = self.data[:-(len(self.data) - ((int(self.header[2:7], 2) + 1 ) * 8))]
        #
        #print("Header:", self.header[:-2])
        #print("Flash:", self.flash)
        print("Address:", self.address)
        if self.header[0] == "1":
            #print("Checksum pass:", self.correct_checksum)
            pass
        else:
            print("Checksum:", self.checksum)
        if self.header[0] != "0":
            print("Data:",'{:0{}X}'.format(int(self.data, 2), len(self.data) // 4))


    def drop_frame_indicator(self, raw_input_frame):
        data = list(raw_input_frame)
        del data[::8]
        data = ''.join(data)
        return data

class send_frame:

    def __init__(self, RnW, flash, address, data = None): # input parameters all type int
        self.checksum = ""
        self.frame = self.construct_frame(RnW, 16, flash, address, data)
        # print("    "+ self.frame)
        self.wrapped_packet = self.add_frame_indicators(self.frame)
        # self.send_frame(self.wrap_packet)
        print(len(self.wrapped_packet)//8, self.wrapped_packet)

        pass

    def construct_frame(self, RnW, nbr_of_byts, flash, address, data = None):
        if RnW == 0:
            self.header = "00" + format(nbr_of_byts-1, "05b") + "0" + str(flash)
            # self.address = address
            self.address = format(address, "032b")
            self.checksum = format(bin(int(data,16)).count('1'),"08b")
            if len(self.checksum) == 9:
                self.checksum = self.checksum[1:]

                # print(self.checksum)
            # print(self.checksum)
            if int(self.checksum,2) > 128:
                # print(int(self.checksum,2), "over 128!")
                # print(header + address + self.checksum)
                return self.header + self.address + self.checksum
            else:
            # print(bin(int('1'+ data, 16))[3:])
                return self.header + self.address + self.checksum + bin(int('1'+ data, 16))[3:]

        elif RnW == 1:
            self.header = "10" + format(nbr_of_byts-1, "05b") + "0" + str(flash)
            self.address = format(address, "032b")
            # print(len(self.address), self.address)
            return self.header + self.address + "0"


    def add_frame_indicators(self, raw_frame):
        tmp_list = []
        for i in range(len(raw_frame)//7): # hier schneide ich die packets zurecht... vorher muss geprüft werden!
            if i == 0:
                tmp_list.append("1" + raw_frame[:7])
            else:
                tmp_list.append("0" + raw_frame[:7])
            raw_frame = raw_frame[7:]

        if len(raw_frame) > 0:
            # print(len(raw_frame), "!!!")
            tmp_list.append("0" + raw_frame + (7 - len(raw_frame) % 8) * "0")

        tmp_list = ''.join(tmp_list)
        return tmp_list

    def send_frame(self, wrapped_packet):
        pass

if __name__ == '__main__':

    pass