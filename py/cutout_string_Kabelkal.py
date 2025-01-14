import re

infile = open("CAL374_20240123_00001_SIS18_GS08BE2_DSP_HFPC049_STAT_start.csv", "r")
content_infile = infile.read()

cleared_infile = content_infile[453:].replace(' ', '')      # cut off unimportant section of text file
cleared_infile = cleared_infile.replace('\n', '\t')         # replace newlines with tabulator
infile_list = re.split(r'\t+', cleared_infile.rstrip('\t')) # split by tabulator

for i in range(len(infile_list)):
    infile_list[i] = infile_list[i].replace(',', '') # remove all ","
    infile_list[i] = float(infile_list[i])           # convert strings to floats

print(infile_list)

print(infile_list[0])
outfile = open("CAL374_20240123_00001_SIS18_GS08BE2_DSP_HFPC049_STAT_start_cut.csv", "a")

if len(infile_list) < 17:
    for i in range(0, 8, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")
    for i in range(8, 16, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")
elif len(infile_list) > 17:
    for i in range(0, 8, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")
    for i in range(8, 16, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")
    for i in range(16, 24, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")
    for i in range(24, 32, 1):
        outfile.write(str(infile_list[i]) + "; ")
    outfile.write("\n")


