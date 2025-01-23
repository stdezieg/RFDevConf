import time
import sys
import glob
import serial
from bitstring import BitArray
import RFDevConf_lib
import colorama
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
    print("available Ports:", input_port_list)
    baudrate=115200
    while True:
        try:
            ser = serial.Serial(port=input_port_list[-1], baudrate=115200, timeout=1)  # open serial port
            # print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "opened serial port '%s' with %d baudrate! :-)\n" % (input_port_list[-1],baudrate) + colorama.Style.NORMAL + colorama.Back.RESET)
            break
        except:
            input_port_list.pop(-2) # drop list element
    return ser


def select_serial_port(input_port_list):
    # opens first available serial port from input_port_list
    print("available Ports:", input_port_list)
    print("which one should be opened?")

    for i in range(len(input_port_list)):
        print(i+1,"-->",  input_port_list[i])

    target_port = input("select port by entering a number...\n")
    # print(type(target_port))
    # time.sleep(10)
    baudrate = 115200
    # print(input_port_list)
    while True:
        try:
            ser = serial.Serial(port=input_port_list[int(target_port)-1], baudrate=115200, timeout=1)  # open serial port
            print("opened serial port '%s' with %d baudrate! :-)\n" % (input_port_list[int(target_port)-1],baudrate))
        except Exception:
            if int(target_port) > len(input_port_list):
                print("selected port is not available... enter a new one!\n")
                target_port = input("select port by entering a number...\n")

    return ser

def format_to_hex(module_type, input_data, outfile): # input_data = Liste mit Strings aus 4 hex values z.b. '1337', '0000'
    hexfile = open(outfile, "w")
    addr = 0

    if module_type == "cel":
        end_address = 16383 # 32768
    elif module_type == "fib-agc":
        end_address = 48


    for element in input_data: # first part hex-file
        tmp = formatRegDiscription(int(hex(addr)[2:].zfill(4).upper(),16),element)
        hexfile.write(tmp + "\n")
        addr = addr + 1

    if module_type == "cel":
        for i in range(16383):  # second part hex-file... unused in fpga
            tmp = formatRegDiscription(int(hex(addr)[2:].zfill(4).upper(),16),"0000")
            hexfile.write(tmp + "\n")
            addr = addr + 1
        hexfile.write(formatRegDiscription(int(hex(32767)[2:].zfill(4).upper(),16),"1FFF") + "\n") # last line of hex file with valid data "1FFF"

    hexfile.write(":00000001FF") # end of file marker
    hexfile.close()


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



def bitstring_to_bytes(s):
    # converts "10101001010" (str) ->  b'' (bytes)
    return int(s, 2).to_bytes(len(s) // 8, byteorder='big')


def compare_hex(input_file, hexfile): #hey
    out_list = []
    with open(input_file) as file_in:
        global lines
        lines = []
        for line in file_in:
            lines.append(line)
            # print(line)

    for i in range(len(hexfile)+1):
        out_list.append(lines[i][9:13])

    out_list = out_list[:-1] # cut off end of file line

    if out_list == hexfile:
        return True
    else:
        return False


class ReceiveFrame:
    def __init__(self, raw_input_frame):
        self.raw = raw_input_frame
        self.cleanup = self.drop_frame_indicator(raw_input_frame)
        self.header = self.cleanup[:7]       # [0] = RnW; [1] = Error; [2-6] = Byte Amount; [7] = Answ;
        self.address = int(self.cleanup[7:39], 2)
        self.checksum = int(self.cleanup[39:47], 2)
        self.data = self.cleanup[47:]
        self.erase = self.header[-3] # self.cleanup[?] coming soon
        self.correct_checksum = self.eval_checksum(self.data, self.header[0])
        # print(self.correct_checksum)
        # print("Header:", self.header[:-2])
        # print("address (int) in frame:", self.address)
        # print("address (bin) in frame:", self.cleanup[7:39])
        # print("raw", raw_input_frame)

        # print("0 - ",self.raw[:8])
        # print("1 - ",self.raw[8:16])
        # print("2 - ",self.raw[16:24])
        # print("3 - ",self.raw[24:32])
        # print("4 - ",self.raw[32:40])
        # print("5 - ",self.raw[40:48])
        # print(self.raw[48:56])

        if self.header[-4] == "1":
            self.flash = True
        else:
            self.flash = False

        # cut out don't care bits out of data section:
        # if self.header[0] == "1":
        #     self.data = self.data[:-(len(self.data) - ((int(self.header[2:7], 2) + 1 ) * 8))]

        # uncomment section below to print incoming data
        # print("Header:", self.header[:-2])
        # print("Header:", self.header)
        #
        # print("Flash:", self.flash)
        # print("Address:", self.address, format(self.address, "032b"))
        # if self.header[0] == "1":
        #     print("Checksum pass:", self.correct_checksum, format(self.checksum, "08b"))
        # else:
        #     print("Checksum:", self.checksum, format(self.checksum, "08b"))
        # if self.header[0] != "0":
        #     print("Data:",'{:0{}X}'.format(int(self.data, 2), len(self.data) // 4))

    def eval_checksum(self, data_in, RnW):
        if RnW == "1":
            checksum_internal = int(format(bin(int(data_in,16)).count('1'),"08b"),2)
            # print(checksum_internal)
            if self.checksum == checksum_internal:
                # print("checksum (fpga) is:", self.checksum)
                # print("checksum (python) is:", checksum_internal)
                # print("checksum ok")
                return True
            else:
                # print("checksum (fpga) is:", self.checksum)
                # print("checksum (python) is:", checksum_internal)
                # print("checksum NOT ok")

                return False

    def drop_frame_indicator(self, raw_input_frame):
        # print("incoming frame w/ fi", raw_input_frame)
        data = list(raw_input_frame)
        fi_list = data[::8]

        for i in range(len(fi_list)):
            if fi_list[0] == '1':
                pass
            elif fi_list[i] == '1':
                error = True
                print(fi_list)
                sys.exit("Error! received frame with incorrect frame indicators")

        del data[::8]
        data = ''.join(data)
        return data

class SendFrame:
    # input parameters all type int
    def __init__(self, RnW, flash, erase, address, data=None):
        self.checksum = ""
        #self.address = format(address, "032b")
        self.frame = self.construct_frame(RnW, flash, erase, address, data)
        self.wrapped_packet = self.add_frame_indicators(self.frame)
        self.address = format(address, "032b")
        self.header = ""
        # print(self.address)

    def construct_frame(self, RnW, flash, erase, address, data=None):
        if RnW == 0:
            self.header = "000" + str(flash) + str(erase) + "00"
            self.address = format(address, "032b")

            if data is None:
                return self.header + self.address
            elif len(data) < 32:
                data = data + (32-(len(data))) * "0"
            # else:
            self.checksum = format(bin(int(data, 16)).count('1'), "08b")
            if len(self.checksum) == 9:
                self.checksum = self.checksum[1:]
            return self.header + self.address + self.checksum + bin(int('1' + data, 16))[3:]

        elif RnW == 1:
            self.header = "100" + str(flash) + str(erase) + "00"
            self.address = format(address, "032b")
            return self.header + self.address + "000"


    def add_frame_indicators(self, raw_frame):
        tmp_list = []
        for i in range(len(raw_frame)//7):  # hier schneide ich die packets zurecht... vorher muss geprüft werden!
            if i == 0:
                tmp_list.append("1" + raw_frame[:7])
            else:
                tmp_list.append("0" + raw_frame[:7])
            raw_frame = raw_frame[7:]

        if len(raw_frame) > 0:
            tmp_list.append("0" + raw_frame + (7 - len(raw_frame) % 8) * "0")

        tmp_list = ''.join(tmp_list)
        # print("frame out w/ fi:    ", tmp_list)
        return tmp_list


    def send_frame(self, wrapped_packet):
        pass

def erase_flash(sector):
    if sector == 0:
        address = int("00000000", 16)                                   # address sector 0 : 0x00000 - 0x0FFFF
    elif sector == 1:
        address = int("00010000", 16)                                   # address sector 1 : 0x10000 - 0x1FFFF
    elif sector == 2:
        address = int("00020000", 16)                                   # address sector 2 : 0x20000 - 0x2FFFF
    elif sector == 3:
        address = int("00030000", 16)                                   # address sector 3 : 0x30000 - 0x3FFFF
    elif sector == 4:
        address = int("00040000", 16)                                   # address sector 4 : 0x40000 - 0x4FFFF
    elif sector == 5:
        address = int("00050000", 16)                                   # address sector 5 : 0x50000 - 0x5FFFF
    elif sector == 6:
        address = int("00060000", 16)                                   # address sector 6 : 0x60000 - 0x6FFFF
    elif sector == 7:
        address = int("00070000", 16)                                   # address sector 7 : 0x70000 - 0x7FFFF
    data_o = SendFrame(RnW=0, flash=1, erase=1, address=address, data=None)
    # ser.write(bitstring_to_bytes(data_o.wrapped_packet))
    # print(data_o)
    return data_o.wrapped_packet


def get_silicon_id():
    data_o = RFDevConf_lib.send_frame(RnW=0, flash=1, address=int("efffffff", 16), data =16 * "FF")
    # print(type(data_o.wrapped_packet), data_o.wrapped_packet)
    return data_o.wrapped_packet

def cel_core_dis():
    data = 28*"FF" + 4*"00"
    data_o = RFDevConf_lib.send_frame(RnW=0, flash=1, address=int("00000000", 16), data = data)
    # print(type(data_o.wrapped_packet), data_o.wrapped_packet)
    return data_o.wrapped_packet

def cel_core_en():
    data = 29*"FF" + 3*"00"
    data_o = RFDevConf_lib.send_frame(RnW=0, flash=1, address=int("00000000", 16), data = data)
    # print(type(data_o.wrapped_packet), data_o.wrapped_packet)
    return data_o.wrapped_packet

def read_request(flash, address):
    data_o = SendFrame(RnW=1, flash=flash, address=address, erase=0, data=None)
    return data_o.wrapped_packet

def write_request(flash, address, data):
    data_o = SendFrame(RnW=0, flash=flash, address=address, erase=0, data=data)
    return data_o.wrapped_packet

# def send_request(RnW, flash, address, data = None):
#     data = decode_Frame()
# def write_request(flash, address, data):
#     data_o = RFDevConf_lib.send_frame(RnW=0, flash=flash, address=address, data=data)
#     return data_o.wrapped_packet

def agc_test():
    # def agc_test(infile, outfile, flash):
    print("hello")

def read_from_hex(input, cut_hex = True):
    out_list = []
    with open(input) as file_in:                                  # read from .hex file
        global lines
        lines = []
        for line in file_in:
            lines.append(line)

        if cut_hex == True:
            lines = lines[0:16384]

    # for i in lines:
    for i in range(len(lines)):
        out_list.append(lines[i][9:13])

    return out_list

def get_module_type():
    packet_o = (read_request(flash=0, address=0))
    ser.write(bitstring_to_bytes(packet_o))

    while True:
        if ser.inWaiting() > 23:
            tmp_in = BitArray(ser.read(40)).bin
            frame_in = ReceiveFrame(tmp_in)
            # xxx = frame_in.cleanup[47:]
            frame_in_hex = '{:0{}X}'.format(int(frame_in.data, 2), len(frame_in.data) // 4)
            break

    if frame_in_hex[12:16] == "1144":
    # if frame_in_hex[12:16] == "1122":
        module_type = "CEL"

    elif frame_in_hex[12:16] == "1122":
    # elif frame_in_hex[12:16] == "1144":
        module_type = "FIB-AGC"
    print("Detected the following module:", module_type,"\n")
    return module_type

def check_input_and_target(module_type, infile):

    if (module_type == "CEL") and (len(read_from_hex(infile)) == 16384):
        return True
    elif (module_type == "FIB-AGC") and (len(read_from_hex(infile)) == 48): # 16 + 32 (20 used out of 32)
        return True
    else:
        return False


if __name__ == '__main__':
    ser = open_serial_port(get_serial_ports())

    #DDAAFF1337FF112233445566778899D7
    #177017700038003400060030004F004F
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 32,data="02BC0001E84800000028000000000000")))

    # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 8,data="01020304050607080910111213141516")))
    # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 8,data="1F40065A13880842000075300384FFFF")))
    #
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=16))) # returns 17701770003C003200060030004F004F on valid agc
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=32))) # returns 02BC0001E84800000000000000000000 on valid agc


    # ser.write(bitstring_to_bytes(erase_flash(1)))
		
    ###############################################################################################################################
    # flash agc with correct parameters:
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 0,data="DDAAFF1337FF112233445566778899D7")))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 16,data="00000000000000000000000000000000")))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 32,data="02BC0001E84800000000000000000000")))
    # verify agc parameters (flash):
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=0))) # returns DDAAFF1337FF112233445566778899D7 on valid agc
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=16))) # returns 17701770003C003200060030004F004F on valid agc
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=32))) # returns 02BC0001E84800000000000000000000 on valid agc
    # verify agc parameters (ram):
    # ser.write(bitstring_to_bytes(read_request(flash=0, address=0))) # returns DDAAFF1337FF112233445566778899D7 on valid agc
    # ser.write(bitstring_to_bytes(read_request(flash=0, address=8))) # returns 17701770003C003200060030004F004F on valid agc
    # ser.write(bitstring_to_bytes(read_request(flash=0, address=16))) # returns 02BC0001E84800000000000000000000 on valid agc
    ##############################################################################################################################
    # 65536
    # ser.write(bitstring_to_bytes(read_request(flash=0, address=0)))
    # ser.write(bitstring_to_bytes(read_request(flash=0, address=16)))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 16,data="DDAAFF1337FF112233445566778899D7")))


    # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 0,data="DDAAFF1337FF112233445566778899D7")))
    # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 0,data="DDAAFF1337FF112233445566778899D7")))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 0,data="DDAAFF1337FF112233445566778899D7")))
    # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 16,data="01020304050607080910111213141516")))

	#
    #
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=65536))) # read param 1 set
    # ser.write(bitstring_to_bytes(read_request(flash=1, address=65552))) # read param 2 set

    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 65536,data="17701770003C003200060030004F004F")))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 65552,data="02BC0001E84800000000000000000000")))


    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 65536,data="01020304050607080910111213141516")))
    # ser.write(bitstring_to_bytes(write_request(flash = 1, address = 16,data="01020304050607080910111213141516")))


    ser.write(bitstring_to_bytes(write_request(flash = 0, address = 0,data="00000000000000000000133700000000")))
    # ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.write_request(flash = 0, address = 0, data ="00000000000000000000133700000000"))) # reset!!!))


    data_in = []
    cnt = 0
    error_cnt = 0

    while True:
        time.sleep(0.25)
        print(ser.inWaiting())
        if ser.inWaiting() > 6: # expecting 26 bytes at serial input
            cnt = cnt + 1
            data_buffer_in = BitArray(ser.read(25)).bin
            # print(type(data_buffer_in[2]))
            if data_buffer_in[2] == '1':
                print("error response!")
                error_cnt = error_cnt +1
            # print(data_buffer_in)
            frame_in = ReceiveFrame(data_buffer_in)
            # print(frame_in.data)
            frame_in = frame_in.cleanup[47:]
            data_in.append('{:0{}X}'.format(int(frame_in, 2), len(frame_in) // 4))

            break
            # loop -> write request
            # print("-",cnt,"-", " error count:", error_cnt)
            # ser.write(bitstring_to_bytes(write_request(flash = 0, address = 13,data="01020304050607080910111213141516")))

    data_in = data_in[:40]
    print(data_in)

    #############################################################################################################################
