def compare_hex(input_file1, input_file2):

    file1 = open(input_file1)
    file2 = open(input_file2)

    if file1 == file2:
        print("files match! :-)")
    else:
        print("!!! files do not match !!!")


if __name__ == '__main__':
    in1 = "Cryring_CEL_no_offset_glitches_rechts.hex"
    in2 = "Cryring_CEL_no_offset_glitches.hex"
    compare_hex(in1, in2)