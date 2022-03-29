# -*- coding: utf-8 -*-
import os
import sys
import time
import numpy as np
import tables as tb
from pathlib import Path

import pyqtgraph as pg
import pyqtgraph.dockarea as pqda
import pyqtgraph.widgets.RemoteGraphicsView
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

import labtools

try:
    import nidaqmx
    from nidaqmx import stream_writers  # Explicit import Required !
    from nidaqmx import stream_readers  # Explicit import Required !
    REAL_DATA = True
except ModuleNotFoundError:
    # If nidaqmx is not installed, random data is generated
    REAL_DATA = False



class FscvWin(QtWidgets.QMainWindow):
    """Main window for the FSCV measurement"""
    def __init__(self):
        # Load config file
        self.config = labtools.getConfig()
        self.datapath = Path(self.config.get('datapath', fallback='data'))

        # Build Gui
        QtGui.QMainWindow.__init__(self)
        area = self.area = pqda.DockArea()
        self.setCentralWidget(area)
        self.resize(1200, 500)
        self.setWindowTitle('FSCV')
        control_gui_element = pqda.Dock("Control", size=(150, 400))
        scan_view_gui_element = pqda.Dock("Scan view", size=(500, 400))
        image_view_gui_element = pqda.Dock("Image view", size=(500, 400))
        area.addDock(control_gui_element)
        area.addDock(scan_view_gui_element, 'right', control_gui_element)
        area.addDock(image_view_gui_element, 'bottom', scan_view_gui_element)

        # Configuration and Controll is done with a Parameter Tree object.
        gui_parameter_dict = [
            {'name': 'Config', 'type': 'group', 'children': [
                {'name': 'U_0', 'type': 'float', 'value': -0.4, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                 'suffix': 'V'},
                {'name': 'U_1', 'type': 'float', 'value': 1.0, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                 'suffix': 'V'},
                {'name': 'Pre ramp time', 'type': 'float', 'value': 5e-3, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Total ramp time', 'type': 'float', 'value': 10e-3, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Post ramp time', 'type': 'float', 'value': 10e-3, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Sampling rate', 'type': 'float', 'value': 100e3, 'siPrefix': True, 'suffix': 'Hz'},
                {'name': 'Line scan period', 'type': 'float', 'value': 0.1, 'siPrefix': True, 'suffix': 's'},
            ]},
            {'name': 'Run', 'type': 'group', 'children': [
                {'name': 'Start', 'type': 'action'},
                {'name': 'Stop', 'type': 'action', 'enabled': False},
                {'name': 'N scans limit', 'type': 'int', 'value': 0},
                {'name': 'N scans acquired', 'type': 'int', 'value': 0, 'readonly': True},
            ]},
            {'name': 'Monitor', 'type': 'group', 'children': [
                {'name': 'Aquisition frequency', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 'Hz',
                 'readonly': True},
                {'name': 'samples per scan', 'type': 'int',# 'value': 0, 'siPrefix': True, 'suffix': 'Hz',
                 'readonly': True},
            ]},
            {'name': 'DAQ', 'type': 'group', 'children': [
                {'name': 'Data path', 'type': 'str', 'value': self.datapath.absolute().as_posix(),
                 'readonly': True},
                {'name': 'Data file', 'type': 'str', 'value': '',
                 'readonly': True},
                {'name': 'Blosc compression level', 'type': 'int', 'value': 5,
                        'limits': (0, 9)},
            ]},
            ]

        ## Create tree of Parameter objects
        self.p = p = Parameter.create(name='gui_parameter_dict', type='group', children=gui_parameter_dict)

        # Connect the GUI Buttons to its functions
        p.param('Run', 'Start').sigActivated.connect(self.start_recording)
        p.param('Run', 'Stop').sigActivated.connect(self.stop_recording)

        # Add parameter gui element
        parameter_gui_element = ParameterTree()
        parameter_gui_element.setParameters(p, showTop=False)
        parameter_gui_element.setWindowTitle('pyqtgraph example: Parameter Tree')
        control_gui_element.addWidget(parameter_gui_element)


        # Set up plotting with multithreading
        self.view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        # Prettier plots at no cost to the main process!
        self.view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process that will be displayed locally
        self.remote_line_plot = self.view.pg.PlotItem()
        self.remote_line_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to remote_line_plot.plot
        self.view.setCentralItem(self.remote_line_plot)
        # add plot to the GUI
        scan_view_gui_element.addWidget(self.view)

        # Image View Remote (somwhow not working)
        #self.imv = pg.ImageView()
        #self.himv = self.imv.getHistogramWidget()
        ## self.himv.setYRange([0.0, 256.0])#, padding=0)
        #self.himv.setHistogramRange(0, 256, padding=0.0)
        #scan_view_gui_element.addWidget(self.imv)
        #self.im_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        #self.im_view.pg.setConfigOptions(antialias=True)  ## prettier plots at no cost to the main process!
        ### Create a PlotItem in the remote process that will be displayed locally
        #self.im_plot = self.im_view.pg.ImageItem()
        #self.im_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to remote_line_plot.plot
        #self.im_view.setCentralItem(self.im_plot)
        #self.im_plot = self.im_view.pg.ImageView()

        # Create basic image plot
        self.im_plot = pg.ImageView()
        self.im_plot.view.setAspectLocked(False)
        image_view_gui_element.addWidget(self.im_plot)
        im_data = np.ones((100, 200)) * np.linspace(-5, 5, 200)
        self.im_plot.setImage(im_data.T)


    def keyPressEvent(self, event):
        # Pressing SPACE starts the measurement, q stops
        if event.key() == QtCore.Qt.Key_Space:
            if self.p.param('Run').param('Start').opts['enabled']:
                self.start_recording()
        if event.key() == QtCore.Qt.Key_Q:
            if self.p.param('Run').param('Stop').opts['enabled']:
                self.stop_recording()

    def start_recording(self):
        """ This function starts a new recording. h5 storage, NiDAQ and the
        recording timer are inititalized"""

        # Read GUI values
        U_0 = self.p.param('Config').param('U_0').value()
        U_1 = self.p.param('Config').param('U_1').value()
        T_pre = self.p.param('Config').param('Pre ramp time').value()
        T_pulse = self.p.param('Config').param('Total ramp time').value()
        T_post = self.p.param('Config').param('Post ramp time').value()
        self.n_scans = n_scans_limit = self.p.param('Run').param('N scans limit').value()
        self.fs = self.p.param('Config').param('Sampling rate').value()
        line_scan_period = self.p.param('Config').param('Line scan period').value()
        complevel = int(self.p.param('DAQ').param('Blosc compression level').value())

        # Update Gui state
        self.p.param('Run').param('Start').setOpts(enabled=False)
        self.p.param('Run').param('Stop').setOpts(enabled=True)

        # Prepare Pulse form
        base_pre = np.ones(int(T_pre * self.fs)) * U_0
        base_post = np.ones(int(T_post * self.fs)) * U_0
        ramp = np.linspace(U_0, U_1, int(T_pulse/2 * self.fs))
        out = 5.0 * np.hstack([base_pre, ramp, ramp[::-1], base_post])
        self.samples_per_scan = len(out)
        self.p.param('Monitor').param('samples per scan').setValue(
            self.samples_per_scan)

        self.avgFps = 1/line_scan_period

        datafile_path = labtools.getNextFile(self.config)
        datafile_folder, datafile_name = os.path.split(datafile_path.absolute())
        self.p.param('DAQ').param('Data path').setValue(datafile_folder)
        self.p.param('DAQ').param('Data file').setValue(datafile_name)

        print(datafile_path.absolute())
        #self.fileh = tb.open_file(datafile_path.absolute().as_posix(), mode='w')
        self.fileh = tb.open_file(datafile_path, mode='w')

        if n_scans_limit == 0:
            # No line limit given, guessing a reasonable total number of scans
            expectedrows = 500
        else:
            expectedrows = n_scans_limit

        # Array that holds timestanps for each scan
        self.array_ts = self.fileh.create_earray(self.fileh.root,
                                                 'array_ts',
                                                 tb.FloatAtom(),
                                                 (1, 0),
                                                 "Times",
                                                 expectedrows=expectedrows)

        # Recorded preamp output
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root,
                                                    'array_scans',
                                                    tb.FloatAtom(),
                                                    (self.samples_per_scan, 0),
                                                    "Scans", filters=filters,
                                                    expectedrows=expectedrows)
        # Recorded command voltage
        self.array_command = self.fileh.create_earray(self.fileh.root,
                                                      'array_command',
                                                      tb.FloatAtom(),
                                                      (self.samples_per_scan, 0),
                                                      "Command",
                                                      filters=filters,
                                                      expectedrows=expectedrows)
        # Store all GUI values in datafile
        gui_params = self.p.getValues()
        for section in gui_params:
            prms = gui_params[section][1]
            for p in prms:
                self.array_scans.attrs[p.replace(' ', '_')] = prms[p][0]


        # Acquire data
        if REAL_DATA:
            taskI = nidaqmx.Task()
            taskO = nidaqmx.Task()

            # Configure out Channel
            taskO.ao_channels.add_ao_voltage_chan("Dev2/ao0")
            taskO.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.ALLOW_REGENERATION
            taskO.timing.cfg_samp_clk_timing(rate=self.fs,
                                             sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                             samps_per_chan=self.samples_per_scan)
            # Configure In Channels
            min_val = -10
            max_val = 10
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 0, min_val=min_val, max_val=max_val)
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 1, min_val=min_val, max_val=max_val)
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 2, min_val=min_val, max_val=max_val)
            taskI.timing.cfg_samp_clk_timing(rate=self.fs,
                                             sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                             samps_per_chan=self.samples_per_scan)

            # create writer and reader
            writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(taskO.out_stream, auto_start=False)
            writer.write_many_sample(out)

            self.taskI = taskI
            self.taskO = taskO
            self.reader = nidaqmx.stream_readers.AnalogMultiChannelReader(taskI.in_stream)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(line_scan_period*1e3))
        self.lastUpdate = time.perf_counter()

    def update(self):
        """This is the central function that is called in a loop. Data is
        acquired and shown in the GUI"""
        if REAL_DATA:
            # DAQStart
            self.taskI.start()
            self.taskO.start()

            # Acquire data
            data = np.zeros((3, self.samples_per_scan))
            self.reader.read_many_sample(
                    data,
                    nidaqmx.constants.READ_ALL_AVAILABLE,
                    timeout=((2+self.samples_per_scan) / self.fs))

            # Wait for acquisition to complete (possibly redundant)
            time.sleep(0.005)

            # Stop
            self.taskI.stop()
            self.taskO.stop()
        else:
            # Delay as in real acquisition
            time.sleep(0.005)

            # Generate random data
            data = np.random.normal(size=(3, self.samples_per_scan))


        # Append new data to data storage
        self.array_ts.append(np.array([time.time()])[np.newaxis])
        self.array_command.append(data[0][:, np.newaxis])
        self.array_scans.append(data[1][:, np.newaxis])

        # Plot single recording
        self.remote_line_plot.plot(data[1], clear=True, _callSync='off')
        #self.remote_line_plot.plot(data[0], clear=True, _callSync='off')

        # Plot image
        self.im_plot.setImage(np.array(self.array_scans)[-50:], autoLevels = False,
                              autoHistogramRange = False, autoRange = False)

        # Calculate show sampling frequency
        now = time.perf_counter()
        fps = 1.0 / (now - self.lastUpdate)
        self.lastUpdate = now
        self.avgFps = self.avgFps * 0.9 + fps * 0.1
        self.p.param('Monitor').param('Aquisition frequency').setValue(self.avgFps)

        # Update GUI values
        n_scans_acquired = self.array_ts.shape[-1]
        self.p.param('Run').param('N scans acquired').setValue(n_scans_acquired)

        # Check if measurement is finished
        #n_scans_limit = self.p.param('Run').param('N scans limit').value()
        if self.n_scans != 0:
            if n_scans_acquired >= self.n_scans:
                self.stop_recording()


    def stop_recording(self):
        """Stop the recording: Update GUI, close file and stop DAQ"""
        self.p.param('Run').param('Start').setOpts(enabled=True)
        self.p.param('Run').param('Stop').setOpts(enabled=False)
        self.timer.stop()
        self.fileh.close()

        if REAL_DATA:
            self.taskI.close()
            self.taskO.close()

    def closeEvent(self, event):
        """Window is beeing closed: stop measurement if it is running"""
        if self.p.param('Run').param('Stop').opts['enabled']:
            self.stop_recording()

        self.view.close()
        event.accept()


## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    # Hide error from QMessageBox
    # os.environ["QT_LOGGING_RULES"] = ''#*.debug=false;qt.qpa.*=false'
    app = QtWidgets.QApplication(sys.argv)
    window = FscvWin()

    #try:
    window.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
    #finally:
        # Stop
        #window.taskI.close()
        #window.taskO.close()
