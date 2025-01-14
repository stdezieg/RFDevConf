import time
import sys
import glob
import serial
import argparse
import random
import colorama

from alive_progress import alive_bar
from bitstring import BitArray



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



        if self.header[-4] == "1":
            self.flash = True
        else:
            self.flash = False

        # cut out don't care bits out of data section:
        # if self.header[0] == "1":
        #     self.data = self.data[:-(len(self.data) - ((int(self.header[2:7], 2) + 1 ) * 8))]

        # uncomment section below to print incoming data
        #################################################
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
                # print("checksum from fpga is:", self.checksum)
                # print("checksum from fpga is:", checksum_internal)
                # print("hey")
                return True
            else:
                # print("checksum from fpga is:", self.checksum)
                # print("checksum from fpga is:", checksum_internal)
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
            print("opened serial port '%s' with %d baudrate! :-)\n" % (input_port_list[-1],baudrate))
            break
        except:
            input_port_list.pop(-2) # drop list element
    return ser


def select_serial_port(input_port_list):
    print("available Ports:", input_port_list)
    print("which one should be opened?")

    for i in range(len(input_port_list)):
        print(i+1, "-->",  input_port_list[i])

    target_port = input("select port by entering a number...\n")
    baudrate=115200
    while True:
        try:
            ser = serial.Serial(port=input_port_list[int(target_port)-1], baudrate=115200, timeout=1)  # open serial port
            print("opened serial port '%s' with %d baudrate! :-)\n" % (input_port_list[int(target_port)-1],baudrate))
            break
        except Exception:
            if int(target_port) > len(input_port_list):
                print("selected port is not available... enter a new one!\n")
                target_port = input("select port by entering a number...\n")

    return ser


def bitstring_to_bytes(s):
    # converts "10101001010" (str) ->  b'' (bytes)
    return int(s, 2).to_bytes(len(s) // 8, byteorder='big')


def read_from_hex(input):
    lines, out_list = [], []

    with open(input) as file_in:                                  # read from .hex file
        lines = []
        for line in file_in:
            lines.append(line)
        lines = lines[0:16384]

    for i in range(len(lines)):
        out_list.append(lines[i][9:13])

    return out_list


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


def gen_random_hex_str(byte_amount):
    char_list = []
    for i in range(byte_amount * 2):
        data = hex(random.randint(0, 16))
        char_list.append(data[-1])
    return ''.join(char_list)


def format_to_hex(input_data, outfile):
    hexfile = open(outfile, "w")
    addr = 0

    for element in input_data:
        tmp = formatRegDiscription(int(hex(addr)[2:].zfill(4).upper(),16),element)
        hexfile.write(tmp + "\n")
        addr = addr + 1

    for i in range(16383):
        tmp = formatRegDiscription(int(hex(addr)[2:].zfill(4).upper(),16),"0000")
        hexfile.write(tmp + "\n")
        addr = addr + 1

    hexfile.write(formatRegDiscription(int(hex(32767)[2:].zfill(4).upper(),16),"1FFF") + "\n")

    hexfile.write(":00000001FF")
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
    return data_o.wrapped_packet

def enable_cel_core(on_off):
    if on_off == 0:
        data = 28*"FF"
    elif on_off == 1:
        data = 29*"FF"
    data_o = SendFrame(RnW=0, flash=1, address=int("00000000",16), data= data)
    return data_o.wrapped_packet

def get_silicon_id(): # currently unused
    data_o = SendFrame(RnW=0, flash=1, address=int("efffffff",16), data = 16*"FF")
    return data_o.wrapped_packet

def bridge_data_f():
    #data = 26*"FF" + 5*"00" + "1F"  # checksum of 213 (bridge data to sram)
    data_o = SendFrame(RnW=0, flash=0, address=int("00000000",16), erase = 0, data= "000000000000A5000000000000000000")
# packet_o =  write_request(flash = 1, address = 0,data = "00000000000000000000133700000000")
    return data_o.wrapped_packet

def read_request(flash, address):
    data_o = SendFrame(RnW=1, flash=flash, address=address, erase=0, data=None)
    return data_o.wrapped_packet

def write_request(flash, address, data):
    data_o = SendFrame(RnW=0, flash=flash, address=address, erase=0, data=data)
    return data_o.wrapped_packet


def CEL_read_write_param(infile, outfile, flash):
    counter, address = 0, 0
    data_list, packets = [], []

    if flash == 0:
        step = 8
        addr_offset = 49 # vorher 48

    elif flash == 1:
        step = 16
        addr_offset = 65536

    if args.command == "compare":
        try:
            input_file = open(infile, "r")
            input_file.close()
        except:
            print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Could not open hexfile. Please check for typos or the file directory and retry. " + colorama.Style.NORMAL + colorama.Back.RESET)
            sys.exit()

    elif args.command == 'write':
        input_hex = read_from_hex(infile)
        hex_slice = ''.join(input_hex[0:8])
        if flash == 1:
            print("erasing memory...")
            ser.write(bitstring_to_bytes(erase_flash(1))) # erase request
            while True:
                if ser.inWaiting() > 6:
                    frame_in = ReceiveFrame(BitArray(ser.read(7)).bin)
                    if frame_in.header == "0011100": ## erase response...
                        time.sleep(1)
                        print("writing flash in:\n...3")
                        time.sleep(1)
                        print("...2")
                        time.sleep(1)
                        print("...1")
                        time.sleep(1)
                        break

    with alive_bar(2048) as bar:
        start_time = time.time()
        send_timer = time.time()
        while True:
            if counter == 0:
                if args.command == 'write':
                    packet_o = write_request(flash, address + addr_offset, hex_slice)
                else:
                    packet_o = read_request(flash, address + addr_offset)
                ser.write(bitstring_to_bytes(packet_o))
                counter += 1
                bar()
            elif counter == 2048:
                if args.command == 'write':
                    break
                else:
                    tmp_in = BitArray(ser.read(25)).bin
                    frame_in = ReceiveFrame(tmp_in)
                    frame_in_hex = '{:0{}X}'.format(int(frame_in.data, 2), len(frame_in.data) // 4)
                    data_list.append(frame_in_hex)
                    data_list = ''.join(data_list)
                    packets = [data_list[i:i + 4] for i in range(0, len(data_list), 4)]
                    # print(packets)
                    break

            if args.command == 'write':
                if ser.inWaiting() > 6:
                    frame_in = ReceiveFrame(BitArray(ser.read(7)).bin)
                    if frame_in.header[1] == "1":  # error bit
                        print("FPGA detected error! Code:", '{:0{}X}'.format(int(frame_in.data, 2), len(frame_in.data) // 4), "Exiting program.")
                        sys.exit()

                    checksum_out = int(format(bin(int(hex_slice,16)).count('1'),"08b"),2)
                    if frame_in.checksum == checksum_out:

                        counter += 1
                        input_hex = input_hex[8:]
                        hex_slice = ''.join(input_hex[0:8])
                        address += step
                        packet_o = write_request(flash, address + addr_offset, hex_slice)
                        ser.write(bitstring_to_bytes(packet_o))
                        send_timer = time.time()
                        bar()
                    else:
                        print("checksum out is not the same as checksum in")

                elif (time.time() - send_timer) > 0.1:                  # resend if packet stuck/lost
                    ser.read(7)
                    packet_o = write_request(flash, address + addr_offset, hex_slice)
                    ser.write(bitstring_to_bytes(packet_o))
                    send_timer = time.time()
                    time.sleep(0.05)
                    pass

            else:  # read or compare
                if ser.inWaiting() > 24:
                    frame_in = ReceiveFrame(BitArray(ser.read(25)).bin)
                    if frame_in.header[1] == "1":  # error bit
                        print("FPGA detected error! Code:", '{:0{}X}'.format(int(frame_in.data, 2), len(frame_in.data) // 4), "Exiting program.")
                        sys.exit()
                    if frame_in.correct_checksum:
                        if (frame_in.address == address + addr_offset) and (flash == 1) or (frame_in.address == address + addr_offset) and (flash == 0): # why not working
                            counter += 1
                            address += step
                            packet_o = read_request(flash, address + addr_offset)
                            ser.write(bitstring_to_bytes(packet_o))
                            send_timer = time.time()
                            frame_in_hex = '{:0{}X}'.format(int(frame_in.data, 2), len(frame_in.data) // 4)
                            data_list.append(frame_in_hex)
                            bar()



                    else:
                        sys.exit("Error! Incorrect checksum. Exiting program.")
                elif (time.time() - send_timer) > 0.1:                  # resend if packet stuck/lost
                    print("resending packet!!!")
                    # print(ser.inWaiting())
                    ser.read(25)
                    packet_o = read_request(flash, address + addr_offset)
                    # data_o = SendFrame(1, flash, address + addr_offset, None)
                    # print(packet_o)
                    # print(data_o.frame)
                    ser.write(bitstring_to_bytes(packet_o))
                    send_timer = time.time()
                    time.sleep(0.05)


    colorama.init()
    if args.command == 'write':
        if flash == 1:
            ser.write(bitstring_to_bytes(write_request(flash = 0, address = 0,data = "0000000000A500000000000000000000"))) # reset!!!))
            print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "Input hex-file '" + infile + "' has been written to flash successfully! RAM will be updated in a few seconds." + colorama.Style.NORMAL + colorama.Back.RESET)

        else:
            print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "Input hex-file '" + infile + "' has been written to RAM successfully!" + colorama.Style.NORMAL + colorama.Back.RESET)
    elif args.command == 'read':
        format_to_hex(packets, outfile)
        print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "Hexfile read successfully! Written to '" + outfile + "'." + colorama.Style.NORMAL + colorama.Back.RESET)
    elif args.command == 'compare':
        if compare_hex(infile, packets):
            if flash == 1:
                print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "Input hex-file '" + infile + "' matches with flash memory content!" + colorama.Style.NORMAL + colorama.Back.RESET)
            else: print(colorama.Back.LIGHTGREEN_EX + colorama.Style.BRIGHT + "Input hex-file '" + infile + "' matches with RAM content!" + colorama.Style.NORMAL + colorama.Back.RESET)
        else:
            print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "Input hex-file '" + infile + "' does NOT match with target memory!" + colorama.Style.NORMAL + colorama.Back.RESET)

def agc_test():
    # def agc_test(infile, outfile, flash):
    print("hello")

if __name__ == '__main__':
    colorama.init()
    print(colorama.Back.LIGHTBLACK_EX + colorama.Style.BRIGHT + "RFDevConf has been started. (Rev. 1.0.0)" + colorama.Style.NORMAL + colorama.Back.RESET)

    ser = open_serial_port(get_serial_ports())

    read_help = "Usage: -r (-f) -o yourfilename.hex // Read command is used to read out the hex file from the CEL."
    write_help = "Usage: -w  (-f) -i yourhexfile.hex // Write command is used to load an input hexfile into the CEL."
    compare_help = "Usage: -c  (-f) -i yourhexfile.hex // Compare command checks whether the input hexfile is located in the target memory or not."
    flash_help = "'-f' flag is used in order to target the flash memory with read/write/compare commands."
    agc_help = "test"

    parser = argparse.ArgumentParser(description='Example list of options', add_help=True)
    parser.add_argument('-r', '--read', dest='command', action='store_const', const='read', help=read_help)
    parser.add_argument('-w', '--write', dest='command', action='store_const', const='write', help=write_help)
    parser.add_argument('-c', '--compare', dest='command', action='store_const', const='compare', help=compare_help)
    parser.add_argument('-f', '--flash', dest='flash_flag', action='store_const', const='flash', help=flash_help)
    parser.add_argument('-i', '--input', dest='infile', metavar='input_file', help='hexfile from user -> CEL')
    parser.add_argument('-o', '--output', action='store', dest='output', help='hexfile from CEL -> user')
    parser.add_argument('-agc', dest='module_type', action='store_const', const='fib_agc', help=agc_help)

    args = parser.parse_args()
    infile = args.infile
    outfile = args.output

    if args.command == 'write':
        if infile is None:
            print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: '-i' argument + input file missing! Please retry." + colorama.Style.NORMAL + colorama.Back.RESET)
            sys.exit()
        if args.flash_flag == 'flash':
            print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Executing write command (flash) with: " + infile + colorama.Style.NORMAL + colorama.Back.RESET)
            try:
                CEL_read_write_param(infile, None, 1)
            except Exception as e:
                print(e)
                # print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Could not open hexfile. Please check for typos or the file directory and retry." + colorama.Style.NORMAL + colorama.Back.RESET)
        else:
            print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Executing write command (RAM) with: " + infile + colorama.Style.NORMAL + colorama.Back.RESET)
            try:
                CEL_read_write_param(infile, None,0)
            except:
                print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Could not open hexfile. Please check for typos or the file directory and retry. " + colorama.Style.NORMAL + colorama.Back.RESET)

    elif args.command == 'read':
        if outfile is None:
            print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: '-o' argument + name for output file missing! Please retry." + colorama.Style.NORMAL + colorama.Back.RESET)
            sys.exit()
        if args.flash_flag == 'flash':
            try:
                print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Executing read command (flash). Writing to file: " + outfile + colorama.Style.NORMAL + colorama.Back.RESET)
                CEL_read_write_param(None, outfile,1)
            except:
                print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Transmission error occured, restart the program." + colorama.Style.NORMAL + colorama.Back.RESET)
        else:
            try:
                print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Executing read command (RAM). Writing to file: " + outfile + colorama.Style.NORMAL + colorama.Back.RESET)
                CEL_read_write_param(None, outfile,0)
            except Exception as e:
                print(e)
                # print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Transmission error occured, restart the program." + colorama.Style.NORMAL + colorama.Back.RESET)


    elif args.command == 'compare':
        if infile is None:
            print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: '-c' argument + input file missing! Please retry." + colorama.Style.NORMAL + colorama.Back.RESET)
            sys.exit()
        if args.flash_flag == 'flash':
            print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Comparing flash content with: " + infile + colorama.Style.NORMAL + colorama.Back.RESET)
            # try:
            CEL_read_write_param(infile, None, 1)
            # except Exception as e:
            #     print(e)
                #(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Could not open hexfile. Please check for typos or the file directory and retry." + colorama.Style.NORMAL + colorama.Back.RESET)
        else:
                # try:
            print(colorama.Back.LIGHTBLUE_EX + colorama.Style.BRIGHT + "Comparing RAM content with: " + infile + colorama.Style.NORMAL + colorama.Back.RESET)
            CEL_read_write_param(infile, None, 0)
                # except:
                # print(colorama.Back.LIGHTRED_EX + colorama.Style.BRIGHT + "ERROR: Could not open hexfile. Please check for typos or the file directory and retry." + colorama.Style.NORMAL + colorama.Back.RESET)

    elif args.module_type == 'fib_agc':
        agc_test()

    else:
        print(colorama.Back.LIGHTBLACK_EX + colorama.Style.BRIGHT + "Input argument for the command is missing!" + colorama.Style.NORMAL + colorama.Back.RESET)

