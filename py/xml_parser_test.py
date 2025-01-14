import xml.etree.ElementTree as ET

def extract_data(file_name):
    values = []
    addresses = []
    bitmasks_of_duplicates = []

    try:
        # Parse the XML file
        tree = ET.parse(file_name)
        root = tree.getroot()

        # Create dictionaries to store addresses and their corresponding bitmasks
        address_bitmasks = {}

        # Iterate over param elements
        for param in root.iter('param'):
            visualization = param.attrib.get("visualization")
            if visualization != "hidden":
                # Extract value and scale factor
                value = param.attrib.get("value")
                if value is not None:
                    value = 50 if float(value) == 1.0 else 1  # Update value based on conditions
                    values.append(value)

                    # Extract addresses and bitmasks
                    for reg in param.findall('reg'):
                        adr = reg.attrib.get("adr")
                        addresses.append(adr)

                        bitmask = reg.attrib.get("bitmask")
                        if bitmask != "ff":
                            if adr not in address_bitmasks:
                                address_bitmasks[adr] = []
                            address_bitmasks[adr].append(bitmask)

        # Check for duplicate addresses and collect their bitmasks
        for adr, bitmask_list in address_bitmasks.items():
            if len(bitmask_list) > 1:  # If there are duplicates
                bitmasks_of_duplicates.extend(bitmask_list)

        # XOR values of duplicate addresses with their specific bitmask
        xor_values = []
        for adr, bitmask_list in address_bitmasks.items():
            xor_value = values[addresses.index(adr)]
            if len(bitmask_list) > 1:  # If there are duplicates
                for bitmask in bitmask_list:
                    xor_value ^= int(bitmask, 16)
            xor_values.append(xor_value)

    except ET.ParseError as e:
        print("XML parsing error:", e)

    return xor_values, addresses, bitmasks_of_duplicates

def print_values_for_address(addresses, values):
    for adr, val in zip(addresses, values):
        print(f"{adr},{val}")

def main():
    # Provide the file name of your XML file
    file_name = '005_Fast_AGC_readonly.xml'
    values, addresses, _ = extract_data(file_name)

    # Print values for each address
    print_values_for_address(addresses, values)

if __name__ == "__main__":
    main()

