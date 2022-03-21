# FSCV

A GUI to perform Fast Scanning Cyclic Voltammetry (FSCV). It uses Ni Hardware for data acquisition (Ni-PXIe 1062Q) and a NPI VA-10x amplifier.

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
