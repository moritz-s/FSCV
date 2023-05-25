# FSCV

![til](./fscv-gui.gif)

A GUI to perform Fast Scanning Cyclic Voltammetry (FSCV).
The GUI integrates the following Hardware:
  - Ni Hardware for data acquisition (Ni-PXIe 1062Q) connected to ![NPI VA-10x](https://www.npielectronic.com/product/va-10/) amplifier. (via ![nidaqmx-python](https://nidaqmx-python.readthedocs.io/en/latest/))
  - Agilent 33220A (via ![PyMeasure](https://pymeasure.readthedocs.io/en/latest/))
  - Microfluidic flow cell by ![Memetis manifold](https://www.memetis.com/) controlled via ![ECU-P](https://gitlab.com/memetis/ecu-p/python)

## Requirements
General requirements:
 - pyqtgraph
 - pytables
 - nidaqmx

Lab-Computer: 
 - python=3.7.11
 - pyqtgraph=0.12.3
 - pytables=3.6.1
 - nidaqmx-python=0.5.7

(see also environment.yml, but note that this contains quite an overhead, like pypylon for Basler cameras etc.)

## Config

To set the data folder use a config.ini file, e.g.:

```dosini
[DEFAULT]
datapath = C:\data
```

## Manifold valve control (symphonies)
A manifold with 8 valves is controlled. The valves are programmed with a .ini file.
Syntax example:

3 = 0010 0000 (3 seconds after start: valve number 3 is opened, all others are closed)

Example symphony.ini file:
```dosini
[DEFAULT]
# Default chords are applied in every symphony
0 = 0000 0000
# The final chord is always applied when a measurement is stopped
final_chord = 0000 0000

[Test 1]
1= 0000 0000
2= 1111 0000
3= 0000 1111
4= 1111 1111

[Test 2]
5  = 1000 0000
10 = 0100 0000
```


