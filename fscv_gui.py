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

try:
    from pymeasure.instruments.agilent import Agilent33220A
    AGILENT_CONNECTED = True
except ModuleNotFoundError:
    AGILENT_CONNECTED = False

try:
    from ecu import ECUManager
    VALVES_CONNECTED = True
except ModuleNotFoundError:
    VALVES_CONNECTED = False

import labtools
import fscv_daq


class FscvWin(QtWidgets.QMainWindow):
    """Main window for the FSCV measurement"""
    def __init__(self):
        # Load config file
        self.config = labtools.getConfig()
        self.datapath = Path(self.config.get('datapath', fallback='data'))

        self.symphonies = labtools.getConfig(None)

        self.background_current = None
        if AGILENT_CONNECTED:
            self.function_generator = Agilent33220A(
                'USB0::0x0957::0x0407::MY43004373::INSTR')

        if VALVES_CONNECTED:
            print('Valves connected.')
            self.ecu_manager = ECUManager()


        # Build Gui
        #QtGui.QMainWindow.__init__(self)
        QtWidgets.QMainWindow.__init__(self)
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
            ]},

            {'name': 'GUI', 'type': 'group', 'children': [
                {'name': 'GUI update period', 'type': 'float', 'value': 0.1,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.02, 1e2)},
                {'name': 'Live waterfall', 'type': 'bool', 'value': True},
                {'name': 'Waterfall update period', 'type': 'float', 'value': 1,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.05, 1e2)},
                {'name': 'Waterfall n scans', 'type': 'int', 'value': 100, 'limits':(1, 1e4)},
                {'name': 'Live background subtraction', 'type': 'bool', 'value': False, 'readonly': True},
                {'name': 'Background file', 'type': 'str', 'value': 'None', 'readonly': True},
                {'name': 'Load background', 'type': 'action'},

            ]},
            {'name': 'Monitor', 'type': 'group', 'children': [
                {'name': 'N scans acquired', 'type': 'int', 'value': 0, 'readonly': True},
                {'name': 'Aquisition period', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
                {'name': 'Aquisition period min', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
                {'name': 'Aquisition period max', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 's',
                 'readonly': True},
            ]},
            {'name': 'Data storage', 'type': 'group', 'children': [
                {'name': 'Data path', 'type': 'str', 'value': self.datapath.absolute().as_posix(),
                 'readonly': True},
                {'name': 'Data file', 'type': 'str', 'value': '',
                 'readonly': True},
                {'name': 'Blosc compression level', 'type': 'int', 'value': 5,
                        'limits': (0, 9)},
            ]},
            {'name': 'Valve control', 'type': 'group', 'children': [
                {'name': 'Symphony', 'type': 'list', 'values': self.symphonies.sections(),
                 'value': 2},
                {'name': 'State', 'type': 'str', 'value': '', 'readonly': True},
            ]},
            ]

        ## Create tree of Parameter objects
        self.p = p = Parameter.create(name='gui_parameter_dict', type='group', children=gui_parameter_dict)

        # Connect the GUI Buttons to its functions
        p.param('Run', 'Start').sigActivated.connect(self.start_recording)
        p.param('Run', 'Stop').sigActivated.connect(self.stop_recording)
        p.param('GUI', 'Load background').sigActivated.connect(self.load_background)

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

    def load_background(self):
        path_today = str(labtools.get_folder_of_the_day(self.config).absolute())
        bg_filename, _ = QtGui.QFileDialog.getOpenFileName(self, caption='Select background recording',
                                                    directory=path_today, filter='*.h5')
        if bg_filename == '':
            return

        with tb.open_file(bg_filename, mode='r') as bg_file:
            self.background_current = np.mean(bg_file.root.array_scans, 0)

        short_filename = os.path.sep.join(bg_filename.split(os.path.sep)[-2:])
        self.p.param('GUI').param('Background file').setValue(short_filename)
        self.p.param('GUI').param('Live background subtraction').setValue(True)
        self.p.param('GUI').param('Live background subtraction').setOpts(readonly=False)

    def start_recording(self):
        """ This function starts a new recording. h5 storage, NiDAQ and the
        recording timer are inititalized"""

        symphony_name = self.p.param('Valve control').param('Symphony').value()
        self.symphony = self.symphonies[symphony_name]
        self.chordtimers = []
        self.chords = []

        for k in sorted(self.symphony, reverse=True):
            if not k.lower().startswith('t-'):
                continue

            chord = self.symphony[k].strip().replace(' ', '')
            self.chords.append(chord)

            chordtime = float(k[2:])*1e3
            timer = QtCore.QTimer()
            timer.timeout.connect(self.update_valves)
            timer.setSingleShot(True)
            timer.start(chordtime)
            #print("timer started ", chordtime)
            self.chordtimers.append(timer)

        # Read GUI values
        # U_0 = self.p.param('Config').param('U_0').value()
        # U_1 = self.p.param('Config').param('U_1').value()
        # T_pre = self.p.param('Config').param('Pre ramp time').value()
        # T_pulse = self.p.param('Config').param('Total ramp time').value()
        # T_post = self.p.param('Config').param('Post ramp time').value()
        self.rate = self.p.param('Config').param('Sampling rate').value()
        self.samples_per_scan = self.p.param('Config').param('Samples per scan').value()
        # line_scan_period = self.p.param('Config').param('Line scan period').value()
        complevel = int(self.p.param('Data storage').param('Blosc compression level').value())

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
        self.p.param('Data storage').param('Data path').setValue(datafile_folder)
        self.p.param('Data storage').param('Data file').setValue(datafile_name)

        #print('start recording: ', datafile_path.absolute())
        #self.fileh = tb.open_file(datafile_path.absolute().as_posix(), mode='w')
        #self.fileh = tb.open_file(datafile_path, mode='w')

        n_scans_limit = self.p.param('Run').param('N scans limit').value()
        if n_scans_limit == 0:
            # No line limit given, guessing a reasonable total number of scans
            expectedrows = 500
        else:
            expectedrows = n_scans_limit

        self.grabber = fscv_daq.NIGrabber(complevel=complevel, expectedrows=expectedrows,
                                            samples_per_scan=self.samples_per_scan, rate=self.rate,
                                            filename=datafile_path.absolute())


        # Store all GUI values in datafile
        gui_params = self.p.getValues()
        for section in gui_params:
            prms = gui_params[section][1]
            for p in prms:
                # TODO
                #self.grabber.fileh.root.attrs[p.replace(' ', '_')] = prms[p][0]
                self.grabber.array_scans.attrs[p.replace(' ', '_')] = prms[p][0]

        self.grabber.start_grabbing()

        # Line and duck plot timer
        gui_period_ms = self.p.param('GUI').param('GUI update period').value()*1e3
        self.gui_timer = QtCore.QTimer()
        self.gui_timer.timeout.connect(self.update)
        self.gui_timer.start(int(gui_period_ms))

        # Image timer
        image_period_ms = self.p.param('GUI').param('Waterfall update period').value()*1e3
        self.image_timer = QtCore.QTimer()
        self.image_timer.timeout.connect(self.update_waterfall)
        self.image_timer.start(int(image_period_ms))


        # Activate output of function generator
        if AGILENT_CONNECTED:
            self.function_generator.output = True

        #self.lastUpdate = time.perf_counter()

    def set_valves(self, chord):
        """Set the valves to a given chord"""
        #print('Playing chord ', end='')
        #print(chord)
        if VALVES_CONNECTED:
            for i_ecu, ecu in enumerate(self.ecu_manager.get_all()):
                #print(ecu)
                for channel in [1, 2]:
                    i_total = i_ecu * 2 + channel - 1
                    if chord[i_total] == "0":
                        ecu.disable(channel)
                    elif chord[i_total] == "1":
                        ecu.enable(channel)
                    else:
                        print("Error in symphony: ", chord)
            i_ecu += 1
        else:
            i_ecu=0

        actual_chord = chord[:i_ecu*2]
        self.p.param('Valve control').param('State').setValue("%s (%s)"%(actual_chord, chord))

    def update_valves(self):
        """Update all the valves to the next chord in the symphony"""
        chord = self.chords.pop()
        self.set_valves(chord)

    def update_waterfall(self):
        """Update the waterfall plot"""
        if self.p.param('GUI').param('Live waterfall').value():
            n_limit = self.p.param('GUI').param('Waterfall n scans').value()
            currents = np.array(self.grabber.array_scans)[-n_limit:]

            if self.p.param('GUI').param('Live background subtraction').value():
                try:
                    currents -= self.background_current
                except ValueError:
                    # Possibly number of samples per scan changed
                    self.background_current = None
                    self.p.param('GUI').param('Live background subtraction').setValue(False)
                    self.p.param('GUI').param('Live background subtraction').setOpts(readonly=True)
                    self.p.param('GUI').param('Background file').setValue('Cleared')
                    return

            self.im_plot.setImage(currents,
                                  autoLevels=False,
                                  autoHistogramRange=False,
                                  autoRange=True)

    def update(self):
        """This is the central function that is called in a loop. Data is
        acquired and shown in the GUI"""

        # Plot last recording
        current = self.grabber.array_scans[:, -1]
        command = self.grabber.array_command[:, -1]

        if len(current.shape) == 2:
            print('DAQ failed: empty data')
            return

        if self.p.param('GUI').param('Live background subtraction').value():
            try:
                current -= self.background_current
            except ValueError:
                # Possibly number of samples per scan changed
                self.background_current = None
                self.p.param('GUI').param('Background file').setValue('Cleared')
                self.p.param('GUI').param('Live background subtraction').setValue(False)
                self.p.param('GUI').param('Live background subtraction').setOpts(readonly=True)
                return

        self.remote_current_plot.plot(current, clear=True, _callSync='off')
        self.remote_command_plot.plot(command, clear=True, _callSync='off')
        self.remote_duck_plot.plot(x=command, y=current,
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
        self.p.param('Monitor').param('N scans acquired').setValue(n_scans_acquired)

        # Check if measurement is finished
        n_scans_limit = self.p.param('Run').param('N scans limit').value()
        if n_scans_limit != 0:
            if n_scans_acquired >= n_scans_limit:
                self.stop_recording()

    def stop_recording(self):
        """Stop the recording: Update GUI, close file and stop DAQ"""
        # Disable output of function generator

        if AGILENT_CONNECTED:
            self.function_generator.output = False

        self.p.param('Run').param('Start').setOpts(enabled=True)
        self.p.param('Run').param('Stop').setOpts(enabled=False)
        self.grabber.stop_grab()
        self.gui_timer.stop()
        self.image_timer.stop()

        for timer in self.chordtimers:
            timer.stop()

        if self.symphony.get('final_chord') is not None:
            self.set_valves(self.symphony.get('final_chord'))

    def closeEvent(self, event):
        """Window is beeing closed: stop measurement if it is running"""
        if self.p.param('Run').param('Stop').opts['enabled']:
            self.stop_recording()

        self.remote_current_view.close()
        self.remote_command_view.close()
        self.remote_duck_view.close()
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
        #QtGui.QApplication.instance().exec_()
        QtWidgets.QApplication.instance().exec_()
    #finally:
    # Stop
    #window.taskI.close()
    #window.taskO.close()
