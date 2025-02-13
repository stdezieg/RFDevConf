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

def xml_to_dataframe(infile):
    df = pd.DataFrame()
    tree = ET.parse(infile)
    root = tree.getroot()

    for element in root.findall("./param[@name]"):
        for registers in element.findall(".//reg[@adr]"):
            # print(registers.attrib.values())
            registers.attrib.update({'bit width':len(element.findall(".//reg[@adr]"))*8})
            # print("debug: ",registers.attrib)
            # print(element.findall(".//reg[@adr]"))
            if len(registers.attrib['bitmask']) < registers.attrib['bit width']//4:      # update bitmask to correct length
                registers.attrib.update({'bitmask':registers.attrib['bitmask']*int(registers.attrib['bit width']//8)})
            break

        i = 0
        for enumentry in element.findall(".//enumentry[@name]"):
            i = i + 1
            registers.attrib.update({"ddown" + str(i):enumentry.attrib['name']})

        merged_dict = dict(element.attrib)
        merged_dict.update(registers.attrib)
        df = pd.concat([df, pd.DataFrame([merged_dict])], ignore_index=True)             # add dictionary to dataframe

    # print(df)
    print(df.to_string())
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
                                                                                    # this is how to update field qlineedit
        self.list_of_widgets[0].setText(str(int(data_in[:4], 16)))                  # desired value ch1
        self.list_of_widgets[2].setText(str(int(data_in[4:8], 16)))                 # desired value ch2
        self.list_of_widgets[1].setText(str(int(data_in[8:12], 16)))                # actual value ch1
        self.list_of_widgets[3].setText(str(int(data_in[12:16], 16)))               # actual value ch2
        self.list_of_widgets[4].setText(str(int(data_in[18:20], 16)))               # manual gain ch1
        self.list_of_widgets[6].setText(str(int(data_in[22:24], 16)))               # manual gain ch2
        self.list_of_widgets[7].setText(str(int(data_in[26:28], 16)))               # actual gain ch2
        self.list_of_widgets[5].setText(str(int(data_in[30:32], 16)))               # actual gain ch1
        self.list_of_widgets[11].setText(str(int(data_in[32:36], 16)))              # amp_window
        self.list_of_widgets[10].setText(str(int(data_in[36:44], 16) // 50))        # update rate

        bin_tmp = "{:08b}".format(int(data_in[48:52], 16)) # addr 12

        try:
            if bin_tmp[0] == '1':
                self.list_of_widgets[13].setChecked(True)
            else:
                self.list_of_widgets[13].setChecked(False)
            if bin_tmp[5] == '1':
                self.list_of_widgets[8].setCurrentIndex(1)
            else:
                self.list_of_widgets[8].setCurrentIndex(0)
            if bin_tmp[6] == '1':
                self.list_of_widgets[9].setCurrentIndex(1)
            else:
                self.list_of_widgets[9].setCurrentIndex(0)
            if bin_tmp[7] == '1': # 12
                self.list_of_widgets[12].setChecked(True)
            else:
                self.list_of_widgets[12].setChecked(False)
        except Exception as e:
            print(e)


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

        self.parsed_xml = xml_to_dataframe(self.xml_path + input_xml)
        # print(self.parsed_xml)
        columnSeriesObj = self.parsed_xml['name']
        for i in range(len(columnSeriesObj.values)):
            print(columnSeriesObj.values[i])
        columnSeriesObj = self.parsed_xml['visualization']
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
                    self.grid.addWidget(widget, i, 2)
                    self.grid.addWidget(QLabel(row['unit']), i, 3)
                elif row['visualization'] == 'chkbox':
                    widget = QLabel(row['name'])
                    self.grid.addWidget(widget, i, 1)
                    widget = QCheckBox()
                    if '1' in row['value']:
                        widget.setChecked(True)
                    self.grid.addWidget(widget, i, 2)
                    # self.list_of_widgets.append(widget)
                elif row['visualization'] == 'dropdown':
                    widget = QLabel(row['name'])
                    self.grid.addWidget(widget, i, 1)
                    widget = QComboBox()
                    self.grid.addWidget(widget,i,2)
                    for i in range(len(self.parsed_xml.columns)-9):
                        widget.addItem(row[9+i])
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

