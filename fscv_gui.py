# -*- coding: utf-8 -*-
import os
import sys
import time
from pathlib import Path
import numpy as np
import tables as tb

import pyqtgraph as pg
import pyqtgraph.dockarea as pqda
import pyqtgraph.widgets.RemoteGraphicsView
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

import labtools
import fscv_daq

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
        self.resize(1200, 800)
        self.setWindowTitle('FSCV')
        control_gui_element = pqda.Dock("Control", size=(250, 600))
        current_view_gui_element = pqda.Dock("Scan view", size=(500, 400))
        command_view_gui_element = pqda.Dock("Command view", size=(500, 400))
        duck_view_gui_element = pqda.Dock("Duck view", size=(500, 400))
        image_view_gui_element = pqda.Dock("Image view", size=(500, 400))
        area.addDock(control_gui_element)
        area.addDock(current_view_gui_element, 'right', control_gui_element)
        area.addDock(command_view_gui_element, 'bottom', current_view_gui_element)
        area.addDock(duck_view_gui_element, 'bottom', command_view_gui_element)
        area.addDock(image_view_gui_element, 'bottom', duck_view_gui_element)

        # Configuration and Controll is done with a Parameter Tree object.
        gui_parameter_dict = [
            {'name': 'Config', 'type': 'group', 'children': [
                #{'name': 'U_0', 'type': 'float', 'value': -0.4, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                # 'suffix': 'V'},
                #{'name': 'U_1', 'type': 'float', 'value': 1.0, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                # 'suffix': 'V'},
                #{'name': 'Pre ramp time', 'type': 'float', 'value': 5e-3, 'step': 1e-3, 'limits': (0, 1e3),
                # 'siPrefix': True, 'suffix': 's'},
                #{'name': 'Total ramp time', 'type': 'float', 'value': 10e-3, 'step': 1e-3, 'limits': (0, 1e3),
                # 'siPrefix': True, 'suffix': 's'},
                #{'name': 'Post ramp time', 'type': 'float', 'value': 10e-3, 'step': 1e-3, 'limits': (0, 1e3),
                # 'siPrefix': True, 'suffix': 's'},
                {'name': 'Sampling rate', 'type': 'float', 'value': 100e3, 'siPrefix': True, 'suffix': 'Hz'},
                {'name': 'Samples per scan', 'type': 'int', 'value': 1000},
                #{'name': 'Line scan period', 'type': 'float', 'value': 0.1, 'siPrefix': True, 'suffix': 's'},
            ]},
            {'name': 'Run', 'type': 'group', 'children': [
                {'name': 'Start', 'type': 'action'},
                {'name': 'Stop', 'type': 'action', 'enabled': False},
                {'name': 'N scans limit', 'type': 'int', 'value': 0},
                {'name': 'N scans acquired', 'type': 'int', 'value': 0, 'readonly': True},
            ]},
            {'name': 'Monitor', 'type': 'group', 'children': [
                {'name': 'GUI update period', 'type': 'float', 'value': 0.1,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.02, 1e2)},
                {'name': 'Live waterfall', 'type': 'bool', 'value': True},
                {'name': 'Waterfall update period', 'type': 'float', 'value': 1,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.05, 1e2)},
                {'name': 'Aquisition period', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
                {'name': 'Aquisition period min', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
                {'name': 'Aquisition period max', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
                #{'name': 'samples per scan', 'type': 'int',# 'value': 0, 'siPrefix': True, 'suffix': 'Hz',
                # 'readonly': True},
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
        parameter_gui_element.setWindowTitle('FSCV Settings')
        control_gui_element.addWidget(parameter_gui_element)


        # Set up plotting with multithreading
        # Current
        self.remote_current_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_current_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_current_plot = self.remote_current_view.pg.PlotItem()
        self.remote_current_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_current_view.setCentralItem(self.remote_current_plot)
        current_view_gui_element.addWidget(self.remote_current_view)
        # command
        self.remote_command_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_command_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_command_plot = self.remote_command_view.pg.PlotItem()
        self.remote_command_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_command_view.setCentralItem(self.remote_command_plot)
        command_view_gui_element.addWidget(self.remote_command_view)
        # duck
        self.remote_duck_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_duck_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_duck_plot = self.remote_duck_view.pg.PlotItem()
        self.remote_duck_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_duck_view.setCentralItem(self.remote_duck_plot)
        duck_view_gui_element.addWidget(self.remote_duck_view)

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
        # U_0 = self.p.param('Config').param('U_0').value()
        # U_1 = self.p.param('Config').param('U_1').value()
        # T_pre = self.p.param('Config').param('Pre ramp time').value()
        # T_pulse = self.p.param('Config').param('Total ramp time').value()
        # T_post = self.p.param('Config').param('Post ramp time').value()
        self.n_scans = n_scans_limit = self.p.param('Run').param('N scans limit').value()
        self.rate = self.p.param('Config').param('Sampling rate').value()
        self.samples_per_scan = self.p.param('Config').param('Samples per scan').value()
        # line_scan_period = self.p.param('Config').param('Line scan period').value()
        complevel = int(self.p.param('DAQ').param('Blosc compression level').value())

        # Update Gui state
        self.p.param('Run').param('Start').setOpts(enabled=False)
        self.p.param('Run').param('Stop').setOpts(enabled=True)

        # # Prepare Pulse form
        # base_pre = np.ones(int(T_pre * self.fs)) * U_0
        # base_post = np.ones(int(T_post * self.fs)) * U_0
        # ramp = np.linspace(U_0, U_1, int(T_pulse/2 * self.fs))
        # out = 5.0 * np.hstack([base_pre, ramp, ramp[::-1], base_post])
        #
        # self.samples_per_scan = len(out)
        # self.p.param('Monitor').param('samples per scan').setValue(
        #     self.samples_per_scan)

        # self.avgFps = 1/line_scan_period

        datafile_path = labtools.getNextFile(self.config)
        datafile_folder, datafile_name = os.path.split(datafile_path.absolute())
        self.p.param('DAQ').param('Data path').setValue(datafile_folder)
        self.p.param('DAQ').param('Data file').setValue(datafile_name)

        #print('start recording: ', datafile_path.absolute())
        #self.fileh = tb.open_file(datafile_path.absolute().as_posix(), mode='w')
        #self.fileh = tb.open_file(datafile_path, mode='w')

        if n_scans_limit == 0:
            # No line limit given, guessing a reasonable total number of scans
            expectedrows = 500
        else:
            expectedrows = n_scans_limit

        self.grabber = fscv_daq.NIGrabber(complevel=complevel, expectedrows=expectedrows,
                                            samples_per_scan=self.samples_per_scan, rate=self.rate,
                                            filename=datafile_path.absolute())


        # TODO
        # Store all GUI values in datafile
        gui_params = self.p.getValues()
        for section in gui_params:
            prms = gui_params[section][1]
            for p in prms:
                #self.grabber.fileh.root.attrs[p.replace(' ', '_')] = prms[p][0]
                self.grabber.array_scans.attrs[p.replace(' ', '_')] = prms[p][0]


        self.grabber.start_grabbing()

        # Line and duck plot timer
        gui_period_ms = self.p.param('Monitor').param('GUI update period').value()*1e3
        self.gui_timer = QtCore.QTimer()
        self.gui_timer.timeout.connect(self.update)
        self.gui_timer.start(int(gui_period_ms))

        # Image timer
        image_period_ms = self.p.param('Monitor').param('Waterfall update period').value()*1e3
        self.image_timer = QtCore.QTimer()
        self.image_timer.timeout.connect(self.update_waterfall)
        self.image_timer.start(int(image_period_ms))

        #self.lastUpdate = time.perf_counter()

    def update_waterfall(self):
        # Plot image
        if self.p.param('Monitor').param('Live waterfall').value():
            self.im_plot.setImage(np.array(self.grabber.array_scans)[-50:], autoLevels = False,
                                autoHistogramRange = False, autoRange = False)

    def update(self):
        """This is the central function that is called in a loop. Data is
        acquired and shown in the GUI"""

        # Plot single recording
        #self.remote_current_plot.plot(self.grabber.last_data[1], clear=True, _callSync='off')
        #self.remote_command_plot.plot(self.grabber.last_data[0], clear=True, _callSync='off')
        #self.remote_duck_plot.plot(x=self.grabber.last_data[0],
        #                           y=self.grabber.last_data[1],
        #                           clear=True, _callSync='off')
        self.remote_current_plot.plot(self.grabber.array_scans[:, -1], clear=True, _callSync='off')
        self.remote_command_plot.plot(self.grabber.array_command[:, -1], clear=True, _callSync='off')
        self.remote_duck_plot.plot(x=self.grabber.array_command[:, -1],
                                   y=self.grabber.array_scans[:, -1],
                                   clear=True, _callSync='off')


        # Calculate show sampling frequency


        #now = time.perf_counter()
        #fps = 1.0 / (now - self.lastUpdate)
        #self.lastUpdate = now

        #self.avgFps = self.avgFps * 0.9 + fps * 0.1

        #self.p.param('Monitor').param('Aquisition frequency').setValue(self.avgFps)
        # Update GUI values
        try:
            self.p.param('Monitor').param('Aquisition period').setValue(self.grabber.delta_t)
            self.p.param('Monitor').param('Aquisition period min').setValue(self.grabber.delta_t_min)
            self.p.param('Monitor').param('Aquisition period max').setValue(self.grabber.delta_t_max)
        except TypeError:
            # Not yet calculated
            self.p.param('Monitor').param('Aquisition period').setValue(0)
            self.p.param('Monitor').param('Aquisition period min').setValue(0)
            self.p.param('Monitor').param('Aquisition period max').setValue(0)

        n_scans_acquired = self.grabber.n_scans_acquired
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
        self.grabber.stop_grab()
        self.gui_timer.stop()
        self.image_timer.stop()

    def closeEvent(self, event):
        """Window is beeing closed: stop measurement if it is running"""
        if self.p.param('Run').param('Stop').opts['enabled']:
            self.stop_recording()

        self.remote_current_view.close()
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
