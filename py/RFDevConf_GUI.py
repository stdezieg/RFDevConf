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

def get_indices(element, lst):
    return [i for i in range(len(lst)) if lst[i] == element]

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
                self.reg_adrr_list.append(addr)
                self.bit_mask_list.append(self.hex2int(bitmask))
                self.reg_value_list.append(reg_value)

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
        #value = self.val_of_dict(wid,"value",0.0) * self.val_of_dict(wid,"scalefactor") + self.val_of_dict(wid,"offset",0.0)
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


# def xml_to_dataframe(infile):
#     df = pd.DataFrame()
#     tree = ET.parse(infile)
#     root = tree.getroot()

    # for element in root.findall("./param[@name]"):
    #     merged_dict = dict(element.attrib)
    #     merged_dict_list = list(merged_dict.items())
    #     # print(merged_dict_list)
    #     for registers in element.findall(".//reg[@adr]"):
    #         merged_dict.update(registers.attrib)
    #         merged_dict_list.append(list(registers.attrib.items()))
    #         # merged_dict_list
    #         # print(merged_dict_list)
    #     i = 0
    #     for enumentry in element.findall(".//enumentry[@name]"):
    #         i = i + 1
    #         # registers.attrib.update({"ddown" + str(i):enumentry.attrib['name']})
    #         merged_dict.update({"ddown" + str(i):enumentry.attrib['name']})
    #
    #         # tmp_dict = registers.attrib.update({"ddown" + str(i):enumentry.attrib['name']})
    #         merged_dict_list.append(list(registers.attrib.items()))
    #         # merged_dict_list.append(list(tmp_dict))
    #
    #     # print(merged_dict_list)
    #     new_dict = dict(merged_dict_list)
    #     print(new_dict)
    #     # print(merged_dict)
    #     df = pd.concat([df, pd.DataFrame([merged_dict])], ignore_index=True)             # add dictionary to dataframe
    #     # df = pd.concat([df, pd.DataFrame([new_dict])], ignore_index=True)             # add dictionary to dataframe
    #
    # df = df.fillna('')
    # # print(df.to_string())
    # return df

def xml_to_dataframe(infile):
    df = pd.DataFrame()
    tree = ET.parse(infile)
    root = tree.getroot()

    for element in root.findall("./param[@name]"): # parse xml by <param name
        for registers in element.findall(".//reg[@adr]"): # parse xml by <reg adr
            registers.attrib.update({'bit width':len(registers.attrib['bitmask'])*4}) # add bit width of widget to dict
            break
        i = 0
        for enumentry in element.findall(".//enumentry[@name]"): # parse xml by <enumentry name
            i = i + 1
            registers.attrib.update({"ddown" + str(i):enumentry.attrib['name']}) # add dropdown options to dict

        merged_dict = dict(element.attrib)
        merged_dict.update(registers.attrib)
        # print(merged_dict)
        df = pd.concat([df, pd.DataFrame([merged_dict])], ignore_index=True)   # transform to dataframe

    df = df.fillna('')
    print(df.to_string())
    # df.to_csv("dataframe.csv", sep=';')
    return df

def list_duplicates(seq):
  seen = set()
  seen_add = seen.add
  seen_twice = list(set(x for x in seq if x in seen or seen_add(x)))
  return seen_twice

def open_main_window():
    app = QApplication(sys.argv)
    window = init_window() #2
    window.show()
    sys.exit(app.exec())

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
        self.setGeometry(300, 300, 325, 325)
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
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[0].text())) # desired value 1
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[2].text())) # desired value 2
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[1].text())) # actual value 1
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[3].text())) # actual value 2
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[4].text())) # manual gain ch1
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[6].text())) # manual gain ch2
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[7].text())) # actual gain ch2
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[5].text())) # actual gain ch1
        data_out = data_out + "{:04X}".format(int(self.list_of_widgets[11].text()))  # amplutude window
        data_out = data_out + "{:08X}".format(int(self.list_of_widgets[10].text())*50) # update rate

        bin_tmp = 0
        if self.list_of_widgets[8].currentText() == "Auto":
            bin_tmp = bin_tmp + 0
        else:
            bin_tmp = bin_tmp + 4
        if self.list_of_widgets[9].currentText() == "Auto":
            bin_tmp = bin_tmp + 0
        else:
            bin_tmp = bin_tmp + 2
        if self.list_of_widgets[12].isChecked():
            bin_tmp = bin_tmp + 1
        else:
            bin_tmp = bin_tmp + 0
        if self.list_of_widgets[13].isChecked():
            bin_tmp = bin_tmp + 128
        else:
            bin_tmp = bin_tmp + 0

        data_out = data_out + "00" +"{:02X}".format(bin_tmp) # control register
        chunks, chunk_size = len(data_out), 32
        data_out = [data_out[i:i+chunk_size] for i in range(0, chunks, chunk_size)]

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
        self.setGeometry(300, 300, 325, 1)
        self.make_form(input_xml)

    def send_hexfile(self):

        if self.flash_combobox.currentText() == "Flash":
            self.flash_flag = 1
        else:
            self.flash_flag = 0

        data_out = self.gen_data_string()

        if self.flash_flag == 1:
            print("erasing flash memory. please wait.")
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.erase_flash(1)))
            time.sleep(1.5)

        if self.flash_flag == 1:
            self.ser.write(RFDevConf.bitstring_to_bytes(
                RFDevConf.write_request(flash=self.flash_flag, address=65536, data=data_out[0])))
        elif self.flash_flag == 0:
            self.ser.write(RFDevConf.bitstring_to_bytes(
                RFDevConf.write_request(flash=self.flash_flag, address=16, data=data_out[0])))
        # self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.write_request(flash=self.flash_flag, address=16, data="DDAAFF1337FF112233445566778899D7")))
        # print("data_out[0]", data_out[0])
        start_time = time.time()
        while True:
            if time.time() - start_time > 3.0:
                print("FPGA not responding... exiting program.")
                sys.exit("FPGA not responding... exiting program.")
            elif self.ser.inWaiting() > 6: # expecting 26 bytes at serial input
                time.sleep(1)
                # print("data_out[1]", data_out[1])
                if self.flash_flag == 1:
                    self.ser.write(RFDevConf.bitstring_to_bytes(
                        RFDevConf.write_request(flash=self.flash_flag, address=65552, data=data_out[1])))
                elif self.flash_flag == 0:
                    self.ser.write(RFDevConf.bitstring_to_bytes(
                        RFDevConf.write_request(flash=self.flash_flag, address=24, data=data_out[1])))
                break
        print("data transmitted!")

        if self.flash_flag == 1:
            time.sleep(0.1) # die braucht er sonst gibts kein reset (warum auch immer...)
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.write_request(flash = 0, address = 0, data ="00000000000000000000133700000000"))) # reset!!!))
            print("resetting fpga...")
            time.sleep(3)
            print("FPGA reset done!")
            # self.ser.flushInput()
            # self.ser.flushOutput()

        print("---------- OPERATION COMPLETED ------------")

    def receive_hexfile(self):

        if self.flash_combobox.currentText() == "Flash":
            self.flash_flag = 1
        else:
            self.flash_flag = 0

        self.ser.flushInput()

        if self.flash_flag == 1:
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=65536)))
        elif self.flash_flag == 0:
            self.ser.write(RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=16)))

        data_in = []
        cnt = 0
        start_time = time.time()

        while True:
            if time.time() - start_time > 3.0:
                print("FPGA not responding... exiting program.")
                sys.exit("FPGA not responding... exiting program.")
            elif self.ser.inWaiting() > 24: # expecting 26 bytes at serial input
                cnt = cnt + 1
                data_buffer_in = BitArray(self.ser.read(25)).bin
                frame_in = RFDevConf.ReceiveFrame(data_buffer_in)
                frame_in = frame_in.cleanup[47:]
                data_in.append('{:0{}X}'.format(int(frame_in, 2), len(frame_in) // 4))
                if cnt == 2:
                    break
                else:
                    if self.flash_flag == 1:
                        self.ser.write(
                            RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=65552)))
                    elif self.flash_flag == 0:
                        self.ser.write(
                            RFDevConf.bitstring_to_bytes(RFDevConf.read_request(flash=self.flash_flag, address=24)))

        data_in = ''.join(data_in)
        data_in = data_in[:52]

        max_addr = 0

        for i in range(len(self.parsed_xml)):
            if max_addr < int(self.parsed_xml['adr'][i], 16):
                max_addr = int(self.parsed_xml['adr'][i], 16)

        print("max_addr is: ", max_addr)

        i = 0
        addr = 0
        print(data_in)
        while True:
            data_in_cut = data_in[0:(self.parsed_xml['bit width'][i])//4]
            # data_in_cut = data_in[0:(self.parsed_xml['bit width'][i])//4]
            if addr == int(self.parsed_xml['adr'][i], 16):
                # print(addr, ":", data_in_cut)
                if "ff" not in self.parsed_xml['bitmask'][i]:
                    duplicates = self.parsed_xml[self.parsed_xml['adr'].duplicated(keep=False)]
                    if self.parsed_xml['visualization'][i] == 'dropdown':
                        # print(data_in_cut)
                        # problem: nehme werte aus XML, eigentlich will ich aus data_in_cut
                        # print(int(self.parsed_xml['value'][i]))
                        self.list_of_widgets[i].setCurrentIndex(int(self.parsed_xml['value'][i]))

                        print(duplicates)

                        for i in range(len(duplicates)):
                            hex_mask = duplicates['bitmask'].iloc[i]
                            hex_data = data_in_cut
                            bin_mask = bin(int(hex_mask, 16))[2:].zfill(16)
                            bin_data = bin(int(hex_data, 16))[2:].zfill(16)
                            print(bin_mask)
                            print(bin_data)
                            print()
                            print("------------------")

                            self.list_of_widgets[i].setCurrentIndex(bin)

                            # pseudocode
                            # 1. get index of active bits in bitmask
                            # 2. loop

                        pass
                else:
                    if self.parsed_xml['visualization'][i] == 'text':
                        self.list_of_widgets[i].setText(str(int(data_in_cut, 16)))
                        data_in = data_in[(self.parsed_xml['bit width'][i])//4:]

                if addr == max_addr:
                    break
                else:
                    addr = addr + len(self.parsed_xml['bitmask'][i])//4
                    # print(addr)
                i = 0

            # elif addr == max_addr:
            #     print("reached max address... exiting looop")
            #     break

            else:
                i = i + 1


            # data_in_cut = data_in[0:(i['bit width'])//4]
            # # if (row['bit width'])
            # if "ff" not in i['bitmask']:
            #     # print("hey!")
            #     duplicates = self.parsed_xml[self.parsed_xml['adr'].duplicated(keep=False)]
            #     print(duplicates.to_string())
            #     # print(data_in_cut)
            # else:
            #     if i['visualization'] == "text":
            #         self.list_of_widgets[i].setText(str(int(data_in_cut, 16)))
            #
            #     elif i['visualization'] == "dropdown":
            #         print("dropdown!")
            #         print(data_in_cut)
            #
            #
            #         # self.list_of_widgets[]
            #
            #     elif i['visualization'] == "chkbox":
            #         print("checkbox!")
            #         print(data_in_cut)
            #
            # data_in = data_in[(i['bit width'])//4:]



        # duplicates = self.parsed_xml[self.parsed_xml['adr'].duplicated(keep=False)]
        # print(duplicates.to_string())
        # sum = 0
        # for i in range(len(duplicates)):
        #     # print("iloc: ", duplicates.iloc[i]['bitmask'])
        #     sum += int(duplicates.iloc[i]['bitmask'], 16)
        #     print(sum)

        # print(self.parsed_xml[self.parsed_xml.index.duplicated(keep=False)])
                                # print("test debug:", self.parsed_xml.index)
                # print(self.parsed_xml.index[self.parsed_xml['adr']].tolist())
        # print(len(self.parsed_xml))
        # check for addr -> check for bitmask (duplicates) -> update widget

        # pseudocode für read -> fill widgets
        # 1. take address i -> check for duplicates -> get indexes of duplicates

                                                                                    # this is how to update field qlineedit
        # self.list_of_widgets[0].setText(str(int(data_in[:4], 16)))                  # desired value ch1
        # self.list_of_widgets[2].setText(str(int(data_in[4:8], 16)))                 # desired value ch2
        # self.list_of_widgets[1].setText(str(int(data_in[8:12], 16)))                # actual value ch1
        # self.list_of_widgets[3].setText(str(int(data_in[12:16], 16)))               # actual value ch2
        # self.list_of_widgets[4].setText(str(int(data_in[18:20], 16)))               # manual gain ch1
        # self.list_of_widgets[6].setText(str(int(data_in[22:24], 16)))               # manual gain ch2
        # self.list_of_widgets[7].setText(str(int(data_in[26:28], 16)))               # actual gain ch2
        # self.list_of_widgets[5].setText(str(int(data_in[30:32], 16)))               # actual gain ch1
        # self.list_of_widgets[11].setText(str(int(data_in[32:36], 16)))              # amp_window
        # self.list_of_widgets[10].setText(str(int(data_in[36:44], 16) // 50))        # update rate

        # bin_tmp = "{:08b}".format(int(data_in[48:52], 16)) # addr 12

        # try:
        #     bin_tmp = "{:08b}".format(int(data_in[48:52], 16)) # addr 12
        #     if bin_tmp[0] == '1':
        #         self.list_of_widgets[13].setChecked(True)
        #     else:
        #         self.list_of_widgets[13].setChecked(False)
        #     if bin_tmp[5] == '1':
        #         self.list_of_widgets[8].setCurrentIndex(1)
        #     else:
        #         self.list_of_widgets[8].setCurrentIndex(0)
        #     if bin_tmp[6] == '1':
        #         self.list_of_widgets[9].setCurrentIndex(1)
        #     else:
        #         self.list_of_widgets[9].setCurrentIndex(0)
        #     if bin_tmp[7] == '1': # 12
        #         self.list_of_widgets[12].setChecked(True)
        #     else:
        #         self.list_of_widgets[12].setChecked(False)
        # except Exception as e:
        #     print(e)


    def make_form(self, input_xml):

        self.list_of_widgets = []
        self.list_of_param_name = []
        self.list_of_reg_adr = []
        self.xml_path = "xml/"
        self.input_xml_file = self.xml_path + input_xml
        tree = ET.parse(self.input_xml_file)                             # extract xml data
        root = tree.getroot()
        self.xml_data_list = []

        # print(self.input_xml_file)
        # print(input_xml)

        for element in root.findall("./param[@name]"):
            self.list_of_param_name.append(element.attrib)
            # print(element.attrib)
            #self.xml_data_list.append(element.attrib)

            for registers in element.findall(".//reg[@adr]"):
                self.xml_data_list.append(registers.attrib)
        for element in root.findall(".//reg[@adr]"):
            self.list_of_reg_adr.append(element.attrib)

        # self.parsed_xml = xml_to_dataframe(self.xml_path + input_xml)
        self.parsed_xml = xml_to_dataframe_xml2dict(self.xml_path + input_xml)
        print(self.parsed_xml.to_string())

        # jetzt dataframe -> widgetframe mappen mit martins klasse!


        # print(self.parsed_xml)
        # columnSeriesObj = self.parsed_xml['name']
        # for i in range(len(columnSeriesObj.values)):
        #     print(columnSeriesObj.values[i])
        # columnSeriesObj = self.parsed_xml['visualization']
            # self.list_of_param_name.append(columnSeriesObj.values[i])
        # print(self.list_of_param_name)
        # for index in self.parsed_xml.index:
        #     self.list_of_param_name.append(self.parsed_xml['name'][index])

        try:
            # print(self.list_of_param_name) # need to rework the bottom parser....!
            for i, row in self.parsed_xml.iterrows():
                if row['visualization'] == 'hidden':
                    print("hidden parameter!")
                elif row['visualization'] == 'text':
                    widget = QLabel(row['name'])
                    self.grid.addWidget(widget, i, 1)
                    widget = QLineEdit(row['value'])
                    self.list_of_widgets.append(widget)
                    self.grid.addWidget(widget, i, 2)
                    self.grid.addWidget(QLabel(row['unit']), i, 3)
                elif row['visualization'] == 'chkbox':
                    widget = QLabel(row['name'])
                    self.grid.addWidget(widget, i, 1)
                    widget = QCheckBox()
                    if '1' in row['value']:
                        widget.setChecked(True)
                    self.grid.addWidget(widget, i, 2)
                    self.list_of_widgets.append(widget)
                    # self.list_of_widgets.append(widget)
                elif row['visualization'] == 'dropdown':
                    widget = QLabel(row['name'])
                    self.grid.addWidget(widget, i, 1)
                    widget = QComboBox()
                    self.grid.addWidget(widget,i,2)
                    self.list_of_widgets.append(widget)
                    print(row['ddcnt'])
                    for i in range(int(row['ddcnt'])):
                        widget.addItem(row['ddown'+str(i+1)])
        except Exception as e:
            print(e)


        # time.sleep(100)





        # for i in range(len(self.list_of_param_name)): # old parser
        #     if "hidden" not in list(self.list_of_param_name[i].values()):     # check xml file for "name" value
        #         widget = QLabel(self.list_of_param_name[i]['name'])
        #         self.grid.addWidget(widget,i,1)
        #
        #     if "text" in list(self.list_of_param_name[i].values()):           # check xml file for "text" value
        #         widget = QLineEdit(self.list_of_param_name[i]['value'])
        #         self.list_of_widgets.append(widget)
        #         self.grid.addWidget(widget,i,2)
        #         widget = self.grid.addWidget(QLabel(self.list_of_param_name[i]['unit']),i,3) # [third column]
        #
        #     if "chkbox" in list(self.list_of_param_name[i].values()):         # check xml file for "chkbox" value
        #         widget = QCheckBox()
        #         if '1' in list(self.list_of_param_name[i].values()):
        #             widget.setChecked(True)
        #         self.grid.addWidget(widget,i,2)
        #         self.list_of_widgets.append(widget)
        #
        #     if "dropdown" in list(self.list_of_param_name[i].values()):       # check xml file for "dropdown" value
        #         widget = QComboBox()
        #         self.grid.addWidget(widget,i,2)
        #         self.list_of_widgets.append(widget)
        #
        #     try:                                                           #
        #         x = list(root[i].attrib.values())
        #         # print(x)
        #         if "dropdown" in x:
        #             dropdown_elements = []
        #             for e in range(16):
        #                 try:
        #                     if "name" in list(root[i][e].attrib):
        #                         tmp = list(root[i][e].attrib.values())
        #                         dropdown_elements.append(tmp[0])
        #                 except Exception as e:
        #                     pass
        #             for element in dropdown_elements:
        #                 widget.addItem(element)
        #     except Exception as e:
        #         print(e)
        #     else:
        #         pass

        write_button = QPushButton("Write")                     # append read/write buttons at the end
        read_button = QPushButton("Read")
        self.flash_combobox = QComboBox()
        self.flash_combobox.addItem("RAM")
        self.flash_combobox.addItem("Flash")
        self.flash_combobox.setCurrentIndex(0)
        # write_button.clicked.connect(self.send_hexfile)
        write_button.clicked.connect(self.send_hexfile)
        read_button.clicked.connect(self.receive_hexfile)
        self.grid.addWidget(write_button, 1000, 1)
        self.grid.addWidget(read_button, 1000, 2)
        self.grid.addWidget(self.flash_combobox, 1000, 3)
        # self.grid.addWidget(QLabel("Flash"),14,3)
        # self.receive_hexfile()

if __name__ == '__main__':
    open_main_window()

