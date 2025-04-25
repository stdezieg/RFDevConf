# RFDevConf_GUI version 0.1
# addresses from xml files are ignored, only widget order from gui is taken from the xml file
# changing the order of the xml file will result in invalid data transmission

import sys
import time
import glob
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
import xml.etree.ElementTree as ET
import RFDevConf
from bitstring import BitArray
import pandas as pd
import xmltodict
import copy
import traceback

def formatRegDiscription(MemAddress, MemContent16bitHex):
    # convert address from integer to 4 hexadecimal digits (i.e. 16 bit)
    hexAddress = format(MemAddress,'08x')[-4:]
    # add memory content, hexString has now 2+4+2+4a=12 hexadecimal digits
    hexString = '02' + hexAddress + '00' + MemContent16bitHex
    # calculate parity check
    b = 0
    for i in range(0,11,2):
        b = b + int(hexString[i:i+2], 16) # byte-wise summation
    hexParityCheck = hex((-b + (1 << 32)) % (1 << 32)) # calculate hex for -b assuming 32 bit
    hexParityCheck = hexParityCheck[len(hexParityCheck)-2:len(hexParityCheck)] # take only the last two hex digits
    # the return value has 1+12+2=15 hexadecimal digits
    return ':' + hexString.upper() + hexParityCheck.upper()

def open_main_window():
    app = QApplication(sys.argv)
    window = init_window()
    window.show()
    sys.exit(app.exec())

def print_dict(dictionary, indent=2):
    if isinstance(dictionary, dict):  # Überprüfen, ob es sich um ein Dictionary handelt
        for key, value in dictionary.items():
            print('  ' * indent + str(key) + ':', end='')
            if isinstance(value, dict):
                print()
                print_dict(value, indent + 1)
            elif isinstance(value, list):  # Falls der Wert eine Liste ist
                print()
                print_list(value, indent + 1)
            else:
                print(' ' + str(value))
    else:
        raise TypeError("Das übergebene Objekt ist kein Dictionary.")

def print_list(lst, indent=2):
    for item in lst:
        if isinstance(item, dict):  # Falls das Listenelement ein Dictionary ist
            print('  ' * indent + '- (Dictionary):')
            print_dict(item, indent + 1)
        elif isinstance(item, list):  # Falls das Listenelement eine Liste ist
            print('  ' * indent + '- (List):')
            print_list(item, indent + 1)
        else:  # Falls das Listenelement ein einfacher Wert ist
            print('  ' * indent + '- ' + str(item))


def xml_to_dataframe_xml2dict(infile):
    df = pd.DataFrame()

    with open(infile, 'r') as file:
        xml_inhalt = file.read()
    xmldict = xmltodict.parse(xml_inhalt, attr_prefix='')

    elem_cnt = 0
    for element in xmldict["unit"]["param"] :
        DF_dict = {} # clear DF_dict
        #Mandetory atributes
        DF_dict["name"]          = element["name"]
        DF_dict["visualization"] = element["visualization"]
        DF_dict["value"]         = element["value"]

        #optional atributes
        if 'unit'          in element.keys(): DF_dict["unit"]          = element["unit"]
        if 'scalefactor'   in element.keys(): DF_dict["scalefactor"]   = element["scalefactor"]
        if 'offset'        in element.keys(): DF_dict["offset"]        = element["offset"]

        #complex atributes: Register entrys
        if isinstance(element["reg"], dict): # single entry
            DF_dict["adr1"]     = element["reg"]["adr"]
            DF_dict["bitmask1"] = element["reg"]["bitmask"]
            DF_dict["regcnt"] = str(int(1))
        elif isinstance(element["reg"], list): # multi entry
            i=1
            for elem in element["reg"]:
                DF_dict["adr"+str(i)]     = elem["adr"]
                DF_dict["bitmask"+str(i)] = elem["bitmask"]
                i+=1
            DF_dict["regcnt"] = str(int(i-1))
        else:
            print("ERROR")

        #complex atributes: enumentry for drop down
        if 'enumentry' in element.keys():
            if isinstance(element["enumentry"], dict): # single entry
                DF_dict["ddown1"]     = element["enumentry"]["name"]
                DF_dict["ddvalue1"] = element["enumentry"]["value"]
                DF_dict["ddcnt"] = str(int(1))
            elif isinstance(element["enumentry"], list): # multi entry
                i=1
                for elem in element["enumentry"]:
                    DF_dict["ddown"+str(i)]     = elem["name"]
                    DF_dict["ddvalue"+str(i)] = elem["value"]
                    i+=1
                DF_dict["ddcnt"] = str(int(i-1))
            else:
                print("ERROR")

        df = pd.concat([df, pd.DataFrame([DF_dict])], ignore_index=True)   # transform to dataframe
        elem_cnt += 1

    # re order colums in Data frame
    cols = df.columns # get collums of Data frame
    adr_and_mask_list = [x for x in cols if "adr" in x or "bitmask" in x] #get all entrys relatet to addres or bitmask
    dd_list = [x for x in cols if "dd" in x] # get all entrys related to drop down menues
    new_cols = [x for x in cols if x not in adr_and_mask_list and x not in dd_list] #get su list without the elements from the other lists
    new_cols = new_cols+adr_and_mask_list+dd_list # fuse all together again
    df = df.reindex(columns=new_cols) # perform new order
    df = df.fillna('')
    # df.to_csv("dataframe_MH.csv", sep=';')
    return df


class RFDevConf_Reg_Data:

    class ReBiCo: # register and Bitmask Container
        def __init__(self):
            self.reg_adrr_list = [] # corresponding reg addr as int
            self.bit_mask_list = [] # bit mask as int value
            self.reg_value_list = [] # resulting value distributen to Bits in multiple registers
            self.wordsize = 16

        def merge_value(self,old_value,list_id):
            mask = self.bit_mask_list[list_id]
            merged_value = (old_value & ~mask) | (self.reg_value_list[list_id] & mask)
            return merged_value

        def re_distribute_value(self):
            value = int(0) #resulting value
            bit_position = 0 # bit pos in the resulting value

            for current_reg in range(len(self.reg_adrr_list)):
                mask = copy.deepcopy(self.bit_mask_list[current_reg]) #to be shure that the origin is untuched
                reg_value = int(self.reg_value_list[current_reg])
                shift = 0
                while mask: # loop until there are no more ones in the mask
                    if mask & 1:  # if the lowest bit in the mask shall be used (is 1)
                        if reg_value & (1 << shift):
                            value |= (1 << bit_position)
                        bit_position += 1 # one bit handled so go to next
                    mask >>= 1 # one bit of mask handled so go to next
                    shift += 1 # remember bit pos
            return int(value)

        def distribute_value(self, value):
            ones_cnt = self.ones_in_bit_mask() #how many bits are
            combined_Bit_Mask = 2**(ones_cnt)-1
            value = value & combined_Bit_Mask # shrink the value to the actual bitmask
            for current_reg_id in range(len(self.reg_adrr_list)): # go thrue all registers that are part of that value
                mask = copy.deepcopy(self.bit_mask_list[current_reg_id]) # get real copy of mask to be shure that the origin is untuched
                shift = 0 # each register start with shift 0

                while mask: # loop until there are no more ones in the mask
                    if mask & 1: # if the lowest bit in the mask shall be used (is 1)
                        if value & 1: # if the value has a one at the current position
                            self.reg_value_list[current_reg_id] |= (1 << shift) # set the  coresponding 1 in the reg value
                        value >>= 1 # go to next bit of value
                    mask >>= 1 # go to next bit of mask
                    shift += 1 # remember shift positon for this register


        def add_reg(self,addr, bitmask, reg_value=0):
            if addr != '':
                self.bit_mask_list.insert(0, self.hex2int(bitmask))
                self.reg_adrr_list.insert(0, addr)
                self.reg_value_list.insert(0, reg_value)

        def ones_in_bit_mask(self):
            counter=0
            for elem in self.bit_mask_list:
                counter += bin(elem).count('1')
            return counter

        def hex2bin(self,hex_string):
            return bin(int.from_bytes(bytes.fromhex(str(hex_string)), byteorder='big'))[2:]

        def hex2int(self,hex_string):
            try:
                # remove leading '0x' oder '0X', if exist
                return int(hex_string, 16)
            except ValueError:
                raise ValueError(f"Ungültiger Hex-String: {hex_string}")


    def __init__(self):
        self.wid_dict = {}
        self.reg_dict = {}
        self.already_build_reg_list = False

    def hex2int(self, hex_string):
        try:
            # remove leading '0x' oder '0X', if it exist
            return int(hex_string, 16)
        except ValueError:
            raise ValueError(f"Ungültiger Hex-String: {hex_string}")

    def int2hex(self, int_value):
        return hex(int(int_value))[2:]

    def get_reg_dict_as_df(self, c_e= False):
        proto_df=[]
        for reg in self.reg_dict.keys():
            adr   = self.int2hex(reg)
            value = self.reg_dict[reg]
            new_dict = {"adr": adr, "value":value}
            if c_e:
                new_dict["bitmask"] = "FFFF"
            proto_df.append(new_dict)
        return pd.DataFrame(proto_df)


    def build_register_list(self): # build a list of all appearing registers based on wid_dict
        reg_addr_list = []
        for elem in self.wid_dict : # go thrue all widgid entrys
            i=1 #counter variable for multiple register entrys
            while(True): #will break due to internal condition
                key = "adr"+str(i)
                if key in elem.keys() and elem[key] != '': # look if key exist for current Widgit and if it is filled
                    reg_adr = self.hex2int(elem[key]) #register addres as int
                    if not (reg_adr in reg_addr_list): # look if register was found already
                        reg_addr_list.append(reg_adr) # add new entry in register list
                else:
                    break #entry des not exist so quit searching
                i+=1 # increase counter for next register entry
        reg_addr_list.sort()
        return reg_addr_list

    def val_of_dict(self,dict, key ,default=1): # retruns the value corresponding to the key if it exist in the dict , otherwise returns default value
        if key in dict.keys():# check if key is iin list
            value = dict[key] # get value
            if value != '':   # chek if value is empty
                return int(value) # if not empty retrun value
        return default # key does not exist or value is empty so return default value

    def set_reg_from_wid(self, wid={}):
        # value = self.val_of_dict(wid,"value",0.0) * self.val_of_dict(wid,"scalefactor") + self.val_of_dict(wid,"offset",0.0)
        value = self.val_of_dict(wid,"value",0)
        my_ReBiCo = self.ReBiCo() #helper to handle bit distributen into register

        i=1 #counter variable for multiple register entrys
        look_for_last_reg_entry=1 # flag to terminate the while loop
        while(look_for_last_reg_entry): #will break due to internal condition
                addr_key = "adr"+str(i)
                mask_key = "bitmask"+str(i)
                if addr_key in wid.keys() and wid[addr_key] != '': # look if key exist for current Widgit and if it is filled
                    reg_adr  = self.hex2int(wid[addr_key]) #register addres as int
                    reg_mask = wid[mask_key] #register addres as int
                    my_ReBiCo.add_reg(reg_adr,reg_mask)
                else:
                    look_for_last_reg_entry=0 #entry does not exist so quit searching
                i+=1 # increase counter for next register entry


        #merge value with register content
        my_ReBiCo.distribute_value(value)# distribute value to tbits corresponding to mask
        for i in range(len(my_ReBiCo.reg_adrr_list)): #merge all registers seperatly
            addr     = my_ReBiCo.reg_adrr_list[i] # get the corresponding register address
            old_value = self.reg_dict[addr] # get the old value for
            self.reg_dict[addr] = my_ReBiCo.merge_value(old_value,i)# merge current value with the internal value for that register

        #self.reg_dict[self.hex2int(wid["adr1"])] = value


    def set_wid_from_reg(self, wid={}):
        my_ReBiCo = self.ReBiCo() #helper to handle bit distributen into register

        i=1 #counter variable for multiple register entrys
        look_for_last_reg_entry=1 # flag to terminate the while loop
        while(look_for_last_reg_entry): #will break due to internal condition
                addr_key = "adr"+str(i)
                mask_key = "bitmask"+str(i)
                if addr_key in wid.keys() and wid[addr_key] != '': # look if key exist for current Widgit and if it is filled
                    reg_adr   = self.hex2int(wid[addr_key]) #register addres as int
                    reg_mask  = wid[mask_key] #register addres as int
                    reg_value = self.reg_dict[reg_adr] #get value from local register
                    my_ReBiCo.add_reg(reg_adr,reg_mask, reg_value) # add register with address bitmask and value in helper
                else:
                    look_for_last_reg_entry=0 #entry does not exist so quit searching
                i+=1 # increase counter for next register entry
        new_value = my_ReBiCo.re_distribute_value() # recombine value with respekt to bitmask and register distribution
        return new_value # return new value for widgit



    def DataFrame2Reg(self, wid_df, compatibility_extensions=False):
        self.wid_dict = wid_df.to_dict("records") # create real dict from Pandas Data frame

        # build a sortet list of used registers if it not was done before
        if self.already_build_reg_list == False:
            self.reg_dict.clear() # make shure the register list is free
            for adr in self.build_register_list(): #create sortet list of used registers and iterate over them
                self.reg_dict[adr] = 0 # create registers with defined start value (zero)

        #go thrue all widigts and set corresponding bits in register map
        for elem in self.wid_dict:
            # print(elem)
            self.set_reg_from_wid(elem)


        return self.get_reg_dict_as_df(compatibility_extensions)

    def Reg2DataFrame(self,reg_df, compatibility_extensions=False):
        input_dict = reg_df.to_dict("records") # transform input register into internal data structure
        for elem in input_dict:
            self.reg_dict[self.hex2int(elem["adr"])]= int(elem["value"])

        for i in range(len(self.wid_dict)): # go thrue all widgeds
            new_value = self.set_wid_from_reg(self.wid_dict[i]) # get value for widgit from internal registers
            self.wid_dict[i]["value"]=int(new_value) #set new value into the current widget

        return pd.DataFrame(self.wid_dict) #retrun resulting dict as pandas data frame

class init_window(QWidget):                                     # START WINDOW -> Auto-Detect/Select Device or Hexflash

    def __init__(self):
        super().__init__()
        self.initMe()

    def initMe(self):
        layout = QVBoxLayout()                                  # window settings/layout
        self.setLayout(layout)
        self.setGeometry(300, 300, 300, 1)
        self.setWindowTitle("RFDevConf V1.0")
        self.setWindowIcon(QIcon("./png/index.png"))

        self.qr = self.frameGeometry()                          # window position (center)
        cp = self.screen().availableGeometry().center()
        self.qr.moveCenter(cp)
        self.move(self.qr.topLeft())

        self.scan_button = QPushButton("Auto-Detect Device", self)   # widget 1: scan devices button
        self.scan_button.clicked.connect(self.scan_device)

        layout.addWidget(self.scan_button)
        self.spacer_txt = QLabel("or choose XML config file:")
        layout.addWidget(self.spacer_txt)
        self.device_list = QComboBox()
        self.device_list.addItem("")                                    # list of available device types
        for file in glob.glob('xml\*.xml'):                             # dynamic xml read with path (needs match)
            self.device_list.addItem(file[4:])                          # cut path and add to device list
            # self.device_list.addItem(file)                          # cut path and add to device list
            # print(file[4:])

        layout.addWidget(self.device_list)
        self.confirm_button = QPushButton("Open Device Configuration", self)
        self.confirm_button.clicked.connect(self.open_device_config) #3
        layout.addWidget(self.confirm_button)
        self.spacer_empty = QLabel("")
        layout.addWidget(self.spacer_empty)
        self.hexflash_button = QPushButton("Open Hexflash App", self)
        layout.addWidget(self.hexflash_button)
        self.hexflash_button.clicked.connect(self.open_hexflash)

    def scan_device(self):
        print("coming soon!")

    def open_device_config(self):
        if self.device_list.currentText() == "":                               # error message if no device is selected
            self.finished_box = QMessageBox()
            self.finished_box.setWindowTitle("     ")
            self.finished_box.setWindowIcon(QIcon("./png/index.png"))
            self.finished_box.setInformativeText("No Device selected!     ")
            self.finished_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            self.finished_box.show()
        else:
            self.hide()
            self.open = RFDevConf_Mainwindow()                                 # open target device config
            self.open.initMe(self.device_list.currentText()) #4
            self.open.show()

    def open_hexflash(self):
        self.hide()
        self.open = CEL_hexflash()


class RFDevConf_Mainwindow(QMainWindow):                                       # Main Window for Device Config
    def __init__(self):
        super().__init__()

    def open_hexflash(self):                                                   # open hexflash application
        self.open = CEL_hexflash()

    def scan_device(self):                                                     # open device config selection
        self.hide()
        self.open = init_window() #5 ??
        self.open.show()

    def initMe(self,input_xml):                                             # window init params
        self.setWindowTitle('RFDevConf' + ' - ' + input_xml[4:-4])
        # self.setGeometry(300, 300, 325, 325)
        self.setGeometry(250, 250, 200, 1)
        self.setWindowIcon(QIcon("./png/index.png"))
        menubar = self.menuBar()
        start = menubar.addMenu("&Start")
        submenu1 = QAction("Device Type Configuration" , self)
        submenu1.setShortcut('CTRL+P')
        submenu1.triggered.connect(self.scan_device)
        start.addAction(submenu1)

        submenu2 = QAction("CEL hexflash" , self)
        submenu2.setShortcut('CTRL+O')
        submenu2.triggered.connect(self.open_hexflash)

        start.addAction(submenu2)

        my_widget = DeviceConfiguration()                                   # load device config into grid ##### #5
        self.setCentralWidget(my_widget)
        my_widget.initMe(input_xml)                                            #6

        self.qr = self.frameGeometry()                                      # center window
        cp = self.screen().availableGeometry().center()
        self.qr.moveCenter(cp)
        self.move(self.qr.topLeft())


class CEL_hexflash(QWidget):
    def __init__(self):
        super().__init__()
        self.initMe()

    def initMe(self):                                                       # window init params

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setGeometry(300, 300, 325, 1)
        # self.setGeometry(200, 200, 200, 1)

        self.setWindowIcon(QIcon("./png/index.png"))
        self.setWindowTitle("CEL Hexflash Application")

        self.qr = self.frameGeometry()                                         # center window
        cp = self.screen().availableGeometry().center()
        self.qr.moveCenter(cp)
        self.move(self.qr.topLeft())

        self.open_file_button = QPushButton("Choose hex-file", self)            # open hex file button
        self.open_file_button.clicked.connect(self.open_file)
        layout.addWidget(self.open_file_button)

        self.myTextBox = QLineEdit()                                            # spacer
        layout.addWidget(self.myTextBox)

        self.write_file_button = QPushButton("write hex-file to CEL", self)     # write hex file button
        self.write_file_button.setEnabled(False)
        self.write_file_button.clicked.connect(self.load_file)
        layout.addWidget(self.write_file_button)

        self.progress_bar = QProgressBar(self)                                  # progress bar
        layout.addWidget(self.progress_bar)

        self.device_button = QPushButton("Return to Device Config", self)       # return button
        self.device_button.clicked.connect(self.open_init_window)
        layout.addWidget(self.device_button)

        self.show()

    def open_file(self):

        path = QFileDialog.getOpenFileName(self, 'Open a file', '', 'All Files (*.*)')
        self.progress_bar.setValue(0)
        if path != ('', ''):
            print(path[0])
        self.myTextBox.setText(path[0])
        self.write_file_button.setEnabled(True)

    def load_file(self):
        self.completed = 0

        while self.completed < 100:
            self.completed += 0.0001
            self.progress_bar.setValue(self.completed)

        self.finished_box = QMessageBox()
        self.finished_box.setWindowTitle("     ")
        self.finished_box.setWindowIcon(QIcon("./png/index.png"))
        self.finished_box.setInformativeText("       Success!              ")
        self.finished_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.finished_box.show()

    def open_init_window(self):
        self.hide()
        self.open = init_window()
        self.open.show()


class DeviceConfiguration(QWidget):

    def __init__(self):
        super().__init__()

    def gen_data_string(self):
        data_out = ""
        self.wid_df = self.reg_data.Reg2DataFrame(self.reg_df)
        hidden = 0
        try: # def yield_widget_values(self)
            for i, row in self.wid_df.iterrows():
                if row['visualization'] == 'hidden':
                    hidden = hidden + 1
                elif isinstance(self.list_of_widgets[i-hidden], QLineEdit) == True:
########################################################################################### (6)

                    # if self.module_name == "FIB_AGC":
                    #     self.wid_df.loc[i, 'value'] = self.list_of_widgets[i-hidden].text()
                    # elif self.module_name == "APD":
                    #     self.wid_df.loc[i, 'value'] = float(self.list_of_widgets[i-hidden].text()) * round(1/float(row['scalefactor'])) # hier mal 1/scalefactor
                    # else:
                    #     self.wid_df.loc[i, 'value'] = self.list_of_widgets[i-hidden].text()
                    #     # pass

                    # print(type(self.list_of_widgets[i-hidden].text()), self.list_of_widgets[i-hidden].text())

                    # a = 50.0
                    # b = "50.0"
                    # print(float(a))
                    # print(float(b))
                    #idea:
                    if float(self.list_of_widgets[i-hidden].text()) % 1 == 0:       # this variable can be treatet as integer
                        # print(float(self.list_of_widgets[i-hidden].text()) % 1)
                        # print("remainder of this variable is zero! cast to int!")
                        self.wid_df.loc[i, 'value'] = int(float(self.list_of_widgets[i-hidden].text())) // int(float(row['scalefactor']))
                    else:                                                           # this variable is float
                        self.wid_df.loc[i, 'value'] = float(self.list_of_widgets[i-hidden].text()) // round(float(row['scalefactor']))



                elif isinstance(self.list_of_widgets[i-hidden], QCheckBox) == True:
                    if self.list_of_widgets[i-hidden].isChecked():
                        self.wid_df.loc[i, 'value'] = 1
                    else:
                        self.wid_df.loc[i, 'value'] = 0
                elif isinstance(self.list_of_widgets[i-hidden], QComboBox) == True:
                    self.wid_df.loc[i, 'value'] = row['ddvalue'+str(self.list_of_widgets[i-hidden].currentIndex()+1)]
        except Exception as e:
            print(e)

        print(self.wid_df.to_string())
        self.reg_df = self.reg_data.DataFrame2Reg(self.wid_df, False)
        print(self.reg_df)
########################################################################################### (7)
        for i, row in self.reg_df.iterrows():
            # data_out = data_out + "{:04X}".format(int(self.reg_df.loc[i + int(self.wid_df.iloc[0]["adr1"], 16), 'value']))
            data_out = data_out + "{:04X}".format(int(self.reg_df.loc[i, 'value'])) # welcher type liegt in reg_df?


        chunks, chunk_size = len(data_out), 32
        data_out = [data_out[i:i+chunk_size] for i in range(0, chunks, chunk_size)]
###########################################################################################
        return data_out

    def initMe(self, input_xml):                                    # widget init params

        #get_module_info = RFDevConf.read_request(0,0)                                                  ***** !!! disabled
        self.ser = RFDevConf.open_serial_port(RFDevConf.get_serial_ports())
        self.ser.flushInput()

        #self.ser.write(RFDevConf.bitstring_to_bytes(get_module_info))                                  *****
        # while True:
        #     if self.ser.inWaiting() > 24: # expecting 26 bytes at serial input                        *****
        #         data_in = BitArray(self.ser.read(25)).bin
        #         frame_in = RFDevConf.ReceiveFrame(data_in)
        #         frame_in = frame_in.cleanup[47:]
        #         # print("data only: ", '{:0{}X}'.format(int(frame_in, 2), len(frame_in) // 4))
        #         break                                                                                 *****

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.setLayout(self.grid)
        # self.setGeometry(300, 300, 325, 1)
        self.setGeometry(200, 200, 200, 1)

        self.make_form(input_xml)

    def send_hexfile(self):

        if self.flash_combobox.currentText() == "Flash":
            self.flash_flag = 1
        else:
            self.flash_flag = 0

        data_out = self.gen_data_string()

        if self.flash_flag == 1:
            print("Erasing flash memory. Please wait.")
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.erase_flash(1)))
            time.sleep(1.5)

        address = 65536 if self.flash_flag else 16  # Set initial address  @@@@@@@@ (7) sollte
        start_time = time.time()

        while data_out:
            # Exit if no response for too long
            if time.time() - start_time > 3.0:
                sys.exit("FPGA not responding... exiting program.")

            # Send first packet
            self.ser.write(RFDevConf.bitstring_to_bytes(
                RFDevConf.write_request(flash=self.flash_flag, address=address, data=data_out[0])))

            # Wait for response
            while self.ser.inWaiting() <= 6:
                if time.time() - start_time > 3.0:
                    sys.exit("FPGA not responding... exiting program.")

            # Read response and check checksum
            frame_in = RFDevConf.ReceiveFrame(BitArray(self.ser.read(7)).bin)
            checksum_out = bin(int(data_out[0], 16)).count('1')

            if frame_in.checksum == checksum_out:
                data_out.pop(0)  # Remove successfully sent data
                address += 16 if self.flash_flag else 8  # Update address

        print("data transmitted!")

        if self.flash_flag == 1:
            time.sleep(0.1) # die braucht er sonst gibts kein reset (warum auch immer...)
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.write_request(flash = 0, address = 0, data ="00000000000000000000133700000000"))) # reset!!!))
            print("resetting fpga...")
            time.sleep(3)
            print("FPGA reset done!")
            self.ser.flushInput()
            self.ser.flushOutput()
        print("---------- OPERATION COMPLETED ------------")

    def receive_hexfile(self):

        self.flash_flag = 1 if self.flash_combobox.currentText() == "Flash" else 0 # Set flash flag based on dropdown selection
        self.ser.flushInput() # Clear serial buffer
        address = 65536 if self.flash_flag else 16 # Set initial address based on flash flag
        self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=address)))

        data_in = []
        cnt = 0
        start_time = time.time()

        while True:
            if time.time() - start_time > 3.0: # Timeout check
                sys.exit("FPGA not responding... exiting program.")

            if self.ser.inWaiting() > 24:  # Read incoming data
                cnt += 1
                frame_in = RFDevConf.ReceiveFrame(BitArray(self.ser.read(25)).bin).cleanup[47:]
                data_in.append('{:0{}X}'.format(int(frame_in, 2), len(frame_in) // 4))

                if cnt == self.register_depth // 8 + (self.register_depth % 8 > 0):  # Break condition (dynamic based on application)
                    break

                address += 16 if self.flash_flag else 8
                self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=address)))

        data_in = ''.join(data_in)
        tmp_df = pd.DataFrame(columns=['adr', 'value']) # Create DataFrame from received values

        for i in range(self.register_depth):
            tmp_df.loc[i] = {'adr': "{:01x}".format(i + int(self.wid_df.iloc[0]["adr1"], 16)), 'value': int(data_in[:4], 16)}
            data_in = data_in[4:]

        self.reg_df = tmp_df
        self.wid_df = self.reg_data.Reg2DataFrame(self.reg_df)
        self.update_widgets() # Update instance variables and UI


    def update_widgets(self):
        try:
            hidden = 0
            for i, row in self.wid_df.iterrows():
                if row['visualization'] == 'hidden':
                    hidden = hidden + 1
                elif row['visualization'] == 'text':
                    if self.gui_init == 0:
                        self.grid.addWidget(QLabel(row['unit']), i, 3)
                        widget = QLabel(row['name'])
                        self.grid.addWidget(widget, i, 1)
                        widget = QLineEdit(row['value'])
                        self.list_of_widgets.append(widget)
                        self.grid.addWidget(widget, i, 2)
                    else:
########################################################################################### (6)
                        # if self.module_name == "APD":
                        #     self.list_of_widgets[i-hidden].setText(str(round((row['value'] * float(row['scalefactor'])),2)))
                        # elif self.module_name == "FIB_AGC":
                        #     self.list_of_widgets[i-hidden].setText(str(row['value']))
                        # else:
                        #     self.list_of_widgets[i-hidden].setText(str(row['value']))

                        if float(row['value']) % 1 == 0:       # this variable can be treatet as integer
                            # print(float(self.list_of_widgets[i-hidden].text()) % 1)
                            # print("remainder of this variable is zero! cast to int!")
                            self.wid_df.loc[i, 'value'] = int(float(row['value'])) * int(float(row['scalefactor'])) # muss eigentlich als das abgelegt werden was es am anfang war
                        else:                                                           # this variable is float
                            self.wid_df.loc[i, 'value'] = float(row['value']) * round(float(row['scalefactor']))

                elif row['visualization'] == 'chkbox':
                    if self.gui_init == 0:
                        widget = QLabel(row['name'])
                        self.grid.addWidget(widget, i, 1)
                        widget = QCheckBox()
                        self.grid.addWidget(widget, i, 2)
                        self.list_of_widgets.append(widget)
                    else:
                        if '1' in str(row['value']):
                            self.list_of_widgets[i-hidden].setChecked(True)
                        elif '0' in str(row['value']):
                            self.list_of_widgets[i-hidden].setChecked(False)

                elif row['visualization'] == 'dropdown':
                    if self.gui_init == 0:
                        widget = QLabel(row['name'])
                        self.grid.addWidget(widget, i, 1)
                        widget = QComboBox()
                        self.grid.addWidget(widget,i,2)
                        self.list_of_widgets.append(widget)
                        for i in range(int(row['ddcnt'])):
                            widget.addItem(row['ddown'+str(i+1)])
                    else:
                        self.list_of_widgets[i-hidden].setCurrentIndex(row['value'])
                        pass
            self.gui_init = 1
        except Exception as e:
            print(i,e)


    def make_form(self, input_xml):

        try:
            self.list_of_widgets = []
            self.xml_path = "xml/"
            self.input_xml_file = self.xml_path + input_xml
            self.module_name = input_xml[4:-4]
            print(self.module_name)
            self.wid_df = xml_to_dataframe_xml2dict(self.xml_path + input_xml)
            self.reg_data = RFDevConf_Reg_Data()
            self.reg_df = self.reg_data.DataFrame2Reg(self.wid_df, False)
            self.gui_init = 0
            self.register_depth = len(self.reg_df)
            self.update_widgets()
            write_button = QPushButton("Write")                     # append read/write buttons at the end
            read_button = QPushButton("Read")
            self.flash_combobox = QComboBox()
            self.flash_combobox.addItem("RAM")
            self.flash_combobox.addItem("Flash")
            self.flash_combobox.setCurrentIndex(0)
            write_button.clicked.connect(self.send_hexfile)
            read_button.clicked.connect(self.receive_hexfile)
            self.grid.addWidget(write_button, 1000, 1)
            self.grid.addWidget(read_button, 1000, 2)
            self.grid.addWidget(self.flash_combobox, 1000, 3)
            # self.grid.addWidget(QLabel("Flash"),14,3)
            self.receive_hexfile()
        except Exception as e:
            print(e)
            print(traceback.format_exc())

if __name__ == '__main__':
    open_main_window()

