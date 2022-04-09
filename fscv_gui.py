# -*- coding: utf-8 -*-
import os
import sys
import time
from pathlib import Path
import configparser
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

NO_SYMPHONY_NAME = "None"
space = " "*20
lspace = " "*40
STOP_BTN_NAME = lspace+"Stop"+lspace
START_BTN_NAME = lspace+"Start"+lspace
START_BACKGROUND_BTN_NAME = space+"Measure background"+space
FINAL_CHORD = "final_chord"

class FscvWin(QtWidgets.QMainWindow):
    """Main window for the FSCV measurement"""
    def __init__(self):
        # Load config file
        self.config = labtools.getConfig()

        self.is_background = False
        self.datapath = Path(self.config.get('datapath', fallback='data'))

        # Load ECU config
        self.ecu_config = labtools.getConfig('ECUS')

        # Connect to Function generator
        self.background_current = None
        if AGILENT_CONNECTED:
            self.function_generator = Agilent33220A(
                'USB0::0x0957::0x0407::MY43004373::INSTR')

        # Connect to valves
        if VALVES_CONNECTED:
            self.ecu_manager = ECUManager()
            for state, ecu in enumerate(self.ecu_manager.get_all()):
                print('Connected: ', ecu)#, "UUID: ",ecu.uuid)

            self.ecus = [None, None, None, None]
            ecu_errors = []
            for i in range(4):
                try:
                    self.ecus[i] = self.ecu_manager.get_by_uuid(
                                                    self.ecu_config['ECU_%i'%(i+1)])
                    print("Identified ecu position %i"%(i+1), self.ecus[i])
                except KeyError:
                    print("Ecu position %i not configured"%(i+1))
                except ValueError as e:
                    ecu_error = "Ecu %s not connected"%self.ecu_config['ECU_%i' % (i + 1)]
                    print(ecu_error)
                    ecu_errors.append(ecu_error)
            if ecu_errors != []:
                pg.QtGui.QMessageBox.critical(self, "Valve ECU connection error", str(ecu_errors))



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
                {'name': START_BTN_NAME, 'type': 'action'},
                {'name': STOP_BTN_NAME, 'type': 'action', 'enabled': False},
                {'name': START_BACKGROUND_BTN_NAME, 'type': 'action'},
                {'name': 'N scans limit', 'type': 'int', 'value': 0},
                {'name': 'n scans background', 'type': 'int', 'value': 50, 'limits':(1, 1e4)},
            ]},

            {'name': 'GUI', 'type': 'group', 'children': [
                {'name': 'GUI update period', 'type': 'float', 'value': 0.1,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.02, 1e2)},
                {'name': 'Live waterfall', 'type': 'bool', 'value': True},
                {'name': 'Waterfall update period', 'type': 'float', 'value': 0.3,
                         'siPrefix': True, 'suffix': 's', 'limits':(0.05, 1e2)},
                {'name': 'Waterfall n scans', 'type': 'int', 'value': 600, 'limits':(1, 1e4)},
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
                {'name': 'Symphony', 'type': 'list', 'values': [NO_SYMPHONY_NAME]},
                {'name': 'Reload symphonies', 'type': 'action', 'value': None},
                {'name': 'State', 'type': 'str', 'value': '', 'readonly': True},
            ]},
            ]

        ## Create tree of Parameter objects
        self.p = p = Parameter.create(name='gui_parameter_dict', type='group', children=gui_parameter_dict)

        # Connect the GUI Buttons to its functions
        p.param('Run', START_BTN_NAME).sigActivated.connect(self.start_recording)
        p.param('Run', STOP_BTN_NAME).sigActivated.connect(self.stop_recording)
        p.param('Run', START_BACKGROUND_BTN_NAME).sigActivated.connect(self.start_background_recording)

        p.param('GUI', 'Load background').sigActivated.connect(self.load_background)
        p.param('Valve control', 'Reload symphonies').sigActivated.connect(self.load_symphonies)

        # Add parameter gui element
        parameter_gui_element = ParameterTree()
        parameter_gui_element.setParameters(p, showTop=False)
        parameter_gui_element.setWindowTitle('FSCV Settings')
        control_gui_element.addWidget(parameter_gui_element)


        # Set up plotting with multithreading
        # Current plot
        self.remote_current_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_current_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_current_plot = self.remote_current_view.pg.PlotItem()
        self.remote_current_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_current_view.setCentralItem(self.remote_current_plot)
        current_view_gui_element.addWidget(self.remote_current_view)
        # command plot
        self.remote_command_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_command_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_command_plot = self.remote_command_view.pg.PlotItem()
        self.remote_command_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_command_view.setCentralItem(self.remote_command_plot)
        command_view_gui_element.addWidget(self.remote_command_view)
        # duck plot
        self.remote_duck_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.remote_duck_view.pg.setConfigOptions(antialias=True) ## Create a PlotItem in the remote process
        self.remote_duck_plot = self.remote_duck_view.pg.PlotItem()
        self.remote_duck_plot._setProxyOptions(deferGetattr=True)  ## speeds up access to plot
        self.remote_duck_view.setCentralItem(self.remote_duck_plot)
        duck_view_gui_element.addWidget(self.remote_duck_view)

        # Waterfall plot
        self.im_plot = pg.ImageView()
        self.im_plot.view.setAspectLocked(False)
        self.im_plot.setColorMap(pg.colormap.get('viridis'))
        image_view_gui_element.addWidget(self.im_plot)
        im_data = np.ones((100, 200)) * np.linspace(-5, 5, 200)
        self.im_plot.setImage(im_data.T)

        # Load symphonies.ini file
        self.load_symphonies()



    def keyPressEvent(self, event):
        # Pressing SPACE starts the measurement, q stops
        if event.key() == QtCore.Qt.Key_Space:
            if self.p.param('Run', START_BTN_NAME).opts['enabled']:
                self.start_recording()
        if event.key() == QtCore.Qt.Key_Q:
            if self.p.param('Run', STOP_BTN_NAME).opts['enabled']:
                self.stop_recording()


    def load_symphonies(self):
        """Loads the valve control pattern from symphonies.ini file"""
        self.symphonies = configparser.ConfigParser()
        try:
            self.symphonies.read("symphonies.ini")
            self.p.param('Valve control', 'Symphony').setLimits([NO_SYMPHONY_NAME,
                                                                *self.symphonies.sections()])
        except configparser.Error as e:
            pg.QtGui.QMessageBox.critical(self, "Parsing error in symphonies.ini", str(e))
            self.symphonies = None
            self.p.param('Valve control', 'Symphony').setLimits([NO_SYMPHONY_NAME])
            #self.p.param('Valve control', 'Symphony').value()

    def load_background(self, bg_filename = None):

        if bg_filename is None:
            path_today = str(labtools.get_folder_of_the_day(self.config).absolute())
            bg_filename, _ = QtGui.QFileDialog.getOpenFileName(self, caption='Select background recording',
                                                        directory=path_today, filter='*.h5')
        if bg_filename == '':
            return

        with tb.open_file(bg_filename, mode='r') as bg_file:
            self.background_current = np.mean(bg_file.root.array_scans, 0)

        short_filename = os.path.sep.join(bg_filename.split(os.path.sep)[-2:])
        self.p.param('GUI', 'Background file').setValue(short_filename)
        self.p.param('GUI', 'Live background subtraction').setValue(True)
        self.p.param('GUI', 'Live background subtraction').setOpts(readonly=False)

    def play_symphony(self, symphony_name):
        """Parsing of .ini file, creation of chord list and timers"""
        self.symphony = self.symphonies[symphony_name]
        self.chordtimers = []
        self.chords = []

        try:
            for k in sorted(self.symphony, reverse=True):
                if k == FINAL_CHORD:
                    # Final chord is not appended to the list.
                    continue

                chord = self.symphony[k].strip()
                chordtime = float(k)*1e3

                if chord.replace('0', '').replace('1', '').strip() != '':
                    raise ValueError('Invalid character in chord: %s . Only 0 and 1 allowed.'%chord)
                self.chords.append(chord)

                timer = QtCore.QTimer()
                timer.timeout.connect(self.next_chord)
                timer.setSingleShot(True)
                timer.start(int(chordtime))
                self.chordtimers.append(timer)
        except ValueError as e:
            for timer in self.chordtimers:
                timer.stop()
            raise e

    def start_recording(self):
        """ This function starts a new recording. h5 storage, NiDAQ and the
        recording timer are inititalized"""

        # Ignore symphony in background mode
        if not self.is_background:
            symphony_name = self.p.param('Valve control', 'Symphony').value()
        else:
            symphony_name = NO_SYMPHONY_NAME

        # Load symphony
        if symphony_name != NO_SYMPHONY_NAME:
            # Store symphony
            try:
                self.play_symphony(symphony_name)
            except ValueError as e:
                pg.QtGui.QMessageBox.critical(self, 
                        "Parsing error in symphony: %s"%symphony_name+space,
                        "In section %s"%symphony_name+'\n'+str(e))
                self.symphony = None
                return
        else:
            self.symphony = None


        # Read gui values
        self.rate = self.p.param('Config', 'Sampling rate').value()
        self.samples_per_scan = self.p.param('Config', 'Samples per scan').value()
        complevel = int(self.p.param('Data storage', 'Blosc compression level').value())

        # Update Gui state
        self.p.param('Run', START_BTN_NAME).setOpts(enabled=False)
        self.p.param('Run', START_BACKGROUND_BTN_NAME).setOpts(enabled=False)
        self.p.param('Run', STOP_BTN_NAME).setOpts(enabled=True)
        self.p.param('Config', 'Sampling rate').setOpts(enabled=False)
        self.p.param('Config', 'Samples per scan').setOpts(enabled=False)
        self.p.param('Data storage', 'Blosc compression level').setOpts(enabled=False)

        datafile_path = labtools.getNextFile(self.config)
        datafile_folder, datafile_name = os.path.split(datafile_path.absolute())
        self.p.param('Data storage', 'Data path').setValue(datafile_folder)
        self.p.param('Data storage', 'Data file').setValue(datafile_name)

        n_scans_limit = self.p.param('Run', 'N scans limit').value()
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
                if p in [START_BACKGROUND_BTN_NAME , START_BTN_NAME, STOP_BTN_NAME]:
                    continue
                self.grabber.array_ts.attrs[p.replace(' ', '_')] = prms[p][0]

        if symphony_name != NO_SYMPHONY_NAME:
            for k in sorted(self.symphony, reverse=True):
                if k == FINAL_CHORD:
                    continue
                chord = self.symphony[k].strip()
                chordtime = int(float(k)*1e3)
                self.grabber.array_ts.attrs['valve_pattern_at_%i_ms'%chordtime] = chord

        self.grabber.start_grabbing()

        # Line and duck plot timer
        gui_period_ms = self.p.param('GUI', 'GUI update period').value()*1e3
        self.gui_timer = QtCore.QTimer()
        self.gui_timer.timeout.connect(self.update)
        self.gui_timer.start(int(gui_period_ms))

        # Image timer
        image_period_ms = self.p.param('GUI', 'Waterfall update period').value()*1e3
        self.image_timer = QtCore.QTimer()
        self.image_timer.timeout.connect(self.update_waterfall)
        self.image_timer.start(int(image_period_ms))


        # Activate output of function generator
        if AGILENT_CONNECTED:
            self.function_generator.output = True
        #self.lastUpdate = time.perf_counter()

    def start_background_recording(self):
        self.n_scans_pre = self.p.param('Run', 'N scans limit').setOpts(enabled=False)
        self.n_scans_pre = self.p.param('Run', 'N scans limit').value()
        self.p.param('Run', 'N scans limit').setValue(self.p.param('Run',
                                                                   'n scans background').value())
        self.is_background = True
        self.start_recording()

    def set_valves(self, chord):
        """Set the valves to a given chord, """
        bool_chord = [x=="1" for x in chord.replace(' ', '')]

        if VALVES_CONNECTED:
            for i, ecu in enumerate(self.ecus):
                if ecu is None:
                    continue
                self.ecus[i].set_enabled(1, bool_chord[i*2])
                self.ecus[i].set_enabled(2, bool_chord[1+i*2])

        self.p.param('Valve control', 'State').setValue("%s"%chord.replace(' ', '_'))

    def next_chord(self):
        """Update all the valves to the next chord in the symphony"""
        chord = self.chords.pop()
        self.set_valves(chord)

    def update_waterfall(self):
        """Update the waterfall plot"""
        if self.p.param('GUI', 'Live waterfall').value():
            n_limit = self.p.param('GUI', 'Waterfall n scans').value()
            currents = np.array(self.grabber.array_scans)[-n_limit:]

            if self.p.param('GUI', 'Live background subtraction').value():
                try:
                    currents -= self.background_current
                except ValueError:
                    # Possibly number of samples per scan changed
                    self.background_current = None
                    self.p.param('GUI', 'Live background subtraction').setValue(False)
                    self.p.param('GUI', 'Live background subtraction').setOpts(readonly=True)
                    self.p.param('GUI', 'Background file').setValue('Cleared')
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

        if self.p.param('GUI', 'Live background subtraction').value():
            try:
                current -= self.background_current
            except ValueError:
                # Possibly number of samples per scan changed
                self.background_current = None
                self.p.param('GUI', 'Background file').setValue('Cleared')
                self.p.param('GUI', 'Live background subtraction').setValue(False)
                self.p.param('GUI', 'Live background subtraction').setOpts(readonly=True)
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

        #self.p.param('Monitor', 'Aquisition frequency').setValue(self.avgFps)
        # Update GUI values
        try:
            self.p.param('Monitor', 'Aquisition period').setValue(self.grabber.delta_t)
            self.p.param('Monitor', 'Aquisition period min').setValue(self.grabber.delta_t_min)
            self.p.param('Monitor', 'Aquisition period max').setValue(self.grabber.delta_t_max)
        except TypeError:
            # Not yet calculated
            self.p.param('Monitor', 'Aquisition period').setValue(0)
            self.p.param('Monitor', 'Aquisition period min').setValue(0)
            self.p.param('Monitor', 'Aquisition period max').setValue(0)

        n_scans_acquired = self.grabber.n_scans_acquired
        self.p.param('Monitor', 'N scans acquired').setValue(n_scans_acquired)

        # Check if measurement is finished
        n_scans_limit = self.p.param('Run', 'N scans limit').value()
        if n_scans_limit != 0:
            if n_scans_acquired >= n_scans_limit:
                self.stop_recording()

    def stop_recording(self):
        """Stop the recording: Update GUI, close file and stop DAQ"""

        # Switch off function generator output
        if AGILENT_CONNECTED:
            self.function_generator.output = False

        # Stop recording and close file
        last_filename = self.grabber.stop_grab()

        # If background recording, use result for background subtraction in plots
        if self.is_background:
            self.p.param('Run', 'N scans limit').setValue(self.n_scans_pre)
            self.p.param('Run', 'N scans limit').setOpts(enabled=True)
            self.load_background(bg_filename = last_filename)
            self.is_background = False

        # Update gui state
        self.p.param('Run', START_BTN_NAME).setOpts(enabled=True)
        self.p.param('Run', START_BACKGROUND_BTN_NAME).setOpts(enabled=True)
        self.p.param('Run', STOP_BTN_NAME).setOpts(enabled=False)
        self.p.param('Config', 'Sampling rate').setOpts(enabled=True)
        self.p.param('Config', 'Samples per scan').setOpts(enabled=True)
        self.p.param('Data storage',
                     'Blosc compression level').setOpts(enabled=True)

        # Stop timers
        self.gui_timer.stop()
        self.image_timer.stop()

        # Stop symphony and apply final chord
        if self.symphony is not None:
            # Stop all timers
            for timer in self.chordtimers:
                timer.stop()
            # Apply final chord
            if self.symphony.get(FINAL_CHORD) is not None:
                self.set_valves(self.symphony.get(FINAL_CHORD))

    def closeEvent(self, event):
        """Window is beeing closed: stop measurement if it is running"""
        if self.p.param('Run', STOP_BTN_NAME).opts['enabled']:
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
