def compare_hex(input_file1, input_file2):

    file1 = open(input_file1)
    file2 = open(input_file2)

    if file1 == file2:
        print("files match! :-)")
    else:
        print("!!! files do not match !!!")

def compare_by_line(in1, in2):

    f1 = open(in1, mode="rb")
    f2 = open(in2, mode="rb")

    f1_data = f1.readlines()
    f2_data = f2.readlines()

    i = 0

    for line1 in f1_data:
        i += 1

        for line2 in f2_data:

            # matching line1 from both files
            if line1 == line2:
                # print IDENTICAL if similar
                print("Line ", i, ": IDENTICAL")
            else:
                print("Line ", i, ":")
                # else print that line from both files
                # print("\tFile 1:", line1, end='')
                # print("\tFile 2:", line2, end='')
            break

    # closing files
    f1.close()
    f2.close()


if __name__ == '__main__':
    in1 = "fib_agc_top_FW05.03.rpd"
    in2 = "output_file.rpd"
    compare_hex(in1, in2)
    # compare_by_line(in1, in2)



