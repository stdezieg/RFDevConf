import matplotlib.pyplot as plt
import numpy as np

#S02BE1
# gdc_out = [0.29,0.92,1.30,1.56,1.81,2.00,2.19,2.35,2.56,2.65,2.79,2.92,3.04,3.16,3.28,3.39,3.50,3.61,3.72,3.83,3.93,4.04,4.15,4.25,4.36,4.47,4.59,4.70,4.93,5.17,5.42,5.68,5.96,6.25,6.58,6.91,7.29,7.71]
#S08BE2
gdc_out = [1.591,2.003,2.300,2.526,2.736,2.914,3.071,3.223,3.366,3.497,3.627,3.749,3.867,3.982,4.093,4.202,4.310,4.422,4.529,4.636,4.736,4.848,4.960,5.064,5.175,5.287,5.400,5.516,5.737,6.000,6.270,6.558,6.863,7.188,7.542,7.993,8.365,8.872]


freq = [0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3.0,3.1,3.2,3.3,3.4,3.6,3.8,4.0,4.2,4.4,4.6,4.8,5.0,5.2,5.4]



korrekturwert = []

for i in range(len(gdc_out)):
       korrekturwert.append(gdc_out[i]/freq[i])
# print(korrekturwert)

# plot 1: GDC CRFC Stellgröße
# fig, ax = plt.subplots()
# ax.plot(freq,gdc_out)
# ax.set(xlabel='Frequency (Mhz)', ylabel='Voltage (V)',
#        title='GDC CRFC Stellgröße (S08BE2)')
# ax.grid()
# plt.plot(freq,gdc_out, marker = 'o', color="black")
# plt.show()

# # plot2: Korrekturfaktor
# fig, ax = plt.subplots()
# ax.plot(freq,korrekturwert)
# ax.set(xlabel='Frequency (Mhz)', ylabel='Korrekturfaktor/1',
#        title='Vorsteuerkurve von S08BE2')
# ax.grid()
# plt.plot(freq,korrekturwert, marker = 'o', color="black")
# plt.show()