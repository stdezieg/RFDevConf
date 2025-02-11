import xml.etree.ElementTree as ET
import pandas as pd

input_xml = "../xml/005_Fast_AGC_readonly.xml"

def xml_to_dataframe(infile):
    df = pd.DataFrame()
    tree = ET.parse(infile)
    root = tree.getroot()

    for element in root.findall("./param[@name]"):
        for registers in element.findall(".//reg[@adr]"):
            registers.attrib.update({'bit width':len(element.findall(".//reg[@adr]"))*8})
            if len(registers.attrib['bitmask']) < registers.attrib['bit width']//4:      # update bitmask to correct length
                registers.attrib.update({'bitmask':registers.attrib['bitmask']*int(registers.attrib['bit width']//8)})
            break
        merged_dict = dict(element.attrib)
        merged_dict.update(registers.attrib)                                             # concentrate sub and main dict
        df = pd.concat([df, pd.DataFrame([merged_dict])], ignore_index=True)             # add dictionary to dataframe
    # print(df)
    print(df.to_string())
    return df

df = xml_to_dataframe(input_xml)
# for column in df:


columnSeriesObj = df['name']
# for i in range(len(columnSeriesObj.values)):
#     print(columnSeriesObj.values[i])

# print(columnSeriesObj.values[0])
# print(len(columnSeriesObj.values))



# list = []
# print(len(df))
#
# for index in df.index:
#     # print(df['name'])#
#     list.append(df['name'][index])
# print(list)
# print(list_of_widgets)
# print(list_of_param_name)
# print(data_frame)