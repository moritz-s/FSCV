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
        self.setWindowTitle('Campy')

        do_cont = pqda.Dock("Control", size=(150, 400))
        do_figures = pqda.Dock("Trace view", size=(500, 400))
        do_image = pqda.Dock("Image view", size=(500, 400))

        area.addDock(do_cont)
        area.addDock(do_figures, 'right', do_cont)
        area.addDock(do_image, 'bottom', do_figures)

        params = [
            {'name': 'Config', 'type': 'group', 'children': [
                {'name': 'U_0', 'type': 'float', 'value': -0.4, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                 'suffix': 'V'},
                {'name': 'U_1', 'type': 'float', 'value': 1.0, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
                 'suffix': 'V'},
                {'name': 'Pre ramp time', 'type': 'float', 'value': 1e-2, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Total ramp time', 'type': 'float', 'value': 1e-2, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Post ramp time', 'type': 'float', 'value': 8e-2, 'step': 1e-3, 'limits': (0, 1e3),
                 'siPrefix': True, 'suffix': 's'},
                {'name': 'Sampling rate', 'type': 'float', 'value': 50e3, 'siPrefix': True, 'suffix': 'Hz'},
                {'name': 'Line scan period', 'type': 'float', 'value': 0.1, 'siPrefix': True, 'suffix': 's'},
            ]
            },
            {'name': 'Run', 'type': 'group', 'children': [
                {'name': 'Start', 'type': 'action'},
                {'name': 'Stop', 'type': 'action', 'enabled': False},
                {'name': 'Total scans', 'type': 'int', 'value': 0},
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
        self.p = p = Parameter.create(name='params', type='group', children=params)

        #p.sigTreeStateChanged.connect(change)
        p.param('Run', 'Start').sigActivated.connect(self.start_recording)
        p.param('Run', 'Stop').sigActivated.connect(self.stop_recording)
        t = ParameterTree()
        t.setParameters(p, showTop=False)
        t.setWindowTitle('pyqtgraph example: Parameter Tree')
        do_cont.addWidget(t)


        self.view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        self.view.pg.setConfigOptions(antialias=True)  ## prettier plots at no cost to the main process!
        ## Create a PlotItem in the remote process that will be displayed locally
        self.rplt = self.view.pg.PlotItem()
        self.rplt._setProxyOptions(deferGetattr=True)  ## speeds up access to rplt.plot
        self.view.setCentralItem(self.rplt)
        do_figures.addWidget(self.view)

        # Image View
        #self.imv = pg.ImageView()
        #self.himv = self.imv.getHistogramWidget()
        ## self.himv.setYRange([0.0, 256.0])#, padding=0)
        #self.himv.setHistogramRange(0, 256, padding=0.0)
        #do_figures.addWidget(self.imv)
        #
        # Remote (somwhow not working)
        #self.im_view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        #self.im_view.pg.setConfigOptions(antialias=True)  ## prettier plots at no cost to the main process!
        ### Create a PlotItem in the remote process that will be displayed locally
        #self.im_rplt = self.im_view.pg.ImageItem()
        #self.im_rplt._setProxyOptions(deferGetattr=True)  ## speeds up access to rplt.plot
        #self.im_view.setCentralItem(self.im_rplt)
        #self.im_rplt = self.im_view.pg.ImageView()

        self.im_rplt = pg.ImageView()
        self.im_rplt.view.setAspectLocked(False)
        do_image.addWidget(self.im_rplt)

        im_data = np.ones((100, 200)) * np.linspace(0, 100, 200)
        self.im_rplt.setImage(im_data.T)#np.ascontiguousarray(im_data))

        self.lastUpdate = time.perf_counter()
        self.avgFps = 0.0
        #self.start_recording()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Space:
            if self.p.param('Run').param('Start').opts['enabled']:
                self.start_recording()
        if event.key() == QtCore.Qt.Key_Q:
            if self.p.param('Run').param('Stop').opts['enabled']:
                self.stop_recording()

    def start_recording(self):
        """Prepare h5 storage
           Prepare NiDAQ
           Start Recording timer"""

        # Prepare Pulse form
        # TODO save in file

        U_0 = self.p.param('Config').param('U_0').value()
        U_1 = self.p.param('Config').param('U_1').value()
        T_pre = self.p.param('Config').param('Pre ramp time').value()
        T_pulse = self.p.param('Config').param('Total ramp time').value()
        T_post = self.p.param('Config').param('Post ramp time').value()
        self.fs = self.p.param('Config').param('Sampling rate').value()
        line_scan_period = self.p.param('Config').param('Line scan period').value()
        complevel = int(self.p.param('DAQ').param('Blosc compression level').value())

        base_pre = np.ones(int(T_pre * self.fs)) * U_0
        base_post = np.ones(int(T_post * self.fs)) * U_0
        ramp = np.linspace(U_0, U_1, int(T_pulse/2 * self.fs))
        out = 5.0 * np.hstack([base_pre, ramp, ramp[::-1], base_post])
        self.nTotal = len(out)
        self.p.param('Monitor').param('samples per scan').setValue(self.nTotal)

        # GUI settings
        self.p.param('Run').param('Start').setOpts(enabled=False)
        self.p.param('Run').param('Stop').setOpts(enabled=True)

        datafile_path = labtools.getNextFile(self.config)
        datafile_folder, datafile_name = os.path.split(datafile_path.absolute())
        self.p.param('DAQ').param('Data path').setValue(datafile_folder)
        self.p.param('DAQ').param('Data file').setValue(datafile_name)

        print(datafile_path.absolute())
        #self.fileh = tb.open_file(datafile_path.absolute().as_posix(), mode='w')
        self.fileh = tb.open_file(datafile_path, mode='w')

        #complevel = 5#np.int(self.mtree.param("BloscLevel").value())
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root, 'array_scans', tb.FloatAtom(),
                                              (self.nTotal, 0), "Scans",
                                              filters=filters,
                                              expectedrows=500)
        self.array_command = self.fileh.create_earray(self.fileh.root, 'array_command', tb.FloatAtom(),
                                                    (self.nTotal, 0), "Command",
                                                    filters=filters,
                                                    expectedrows=500)
        gui_params = self.p.getValues()

        for section in gui_params:
            prms = gui_params[section][1]
            for p in prms:
                self.array_scans.attrs[p.replace(' ', '_')] = prms[p][0]


        if REAL_DATA:
            taskI = nidaqmx.Task()
            taskO = nidaqmx.Task()

            # Configure out Channel
            taskO.ao_channels.add_ao_voltage_chan("Dev2/ao0")
            taskO.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.ALLOW_REGENERATION
            taskO.timing.cfg_samp_clk_timing(rate=self.fs,
                                             sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                             samps_per_chan=self.nTotal)
            # Configure In Channels
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 0)
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 1)
            taskI.ai_channels.add_ai_voltage_chan("PXI1Slot4_2/ai%i" % 2)
            taskI.timing.cfg_samp_clk_timing(rate=self.fs,
                                             sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                             samps_per_chan=self.nTotal)

            # create writer and reader
            writer = nidaqmx.stream_writers.AnalogSingleChannelWriter(taskO.out_stream, auto_start=False)
            writer.write_many_sample(out)

            self.taskI = taskI
            self.taskO = taskO
            self.reader = nidaqmx.stream_readers.AnalogMultiChannelReader(taskI.in_stream)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(line_scan_period*1e3))

    def update(self):
        if REAL_DATA:
            # DAQStart
            self.taskI.start()
            self.taskO.start()

            # Acquire data
            data = np.zeros((3, self.nTotal))
            self.reader.read_many_sample(
                    data, 
                    nidaqmx.constants.READ_ALL_AVAILABLE,
                    timeout=((2+self.nTotal) / self.fs))

            # Wait for acquisition to complete (possibly redundant)
            time.sleep(0.005)

            # Stop
            self.taskI.stop()
            self.taskO.stop()
        else:
            # Delay as in real acquisition
            time.sleep(0.005)

            # Generate random data
            data = np.random.normal(size=(3, self.nTotal))

        self.rplt.plot(data[0], clear=True, _callSync='off')
        self.rplt.plot(data[1], clear=True, _callSync='off')

        self.array_command.append(data[0][:, np.newaxis])
        self.array_scans.append(data[1][:, np.newaxis])

        #self.im_rplt.setImage(self.array_imgs)#np.ascontiguousarray(im_data))
        self.im_rplt.setImage(np.array(self.array_scans), autoLevels = False,
                              autoHistogramRange = False)#, autoRange = False)
        #np.ascontiguousarray(im_data))
        #self.imv.setImage(imgarr, autoLevels=False,
        #                 autoHistogramRange=False, autoRange=False)

        now = time.perf_counter()
        fps = 1.0 / (now - self.lastUpdate)
        self.lastUpdate = now
        self.avgFps = self.avgFps * 0.8 + fps * 0.2
        self.p.param('Monitor').param('Aquisition frequency').setValue(self.avgFps)
        #self.label.setText("Generating %0.2f fps" % self.avgFps)
        total_scans = self.p.param('Run').param('Total scans').value()
        if total_scans != 0:
            if self.array_scans.shape[1] >= total_scans:
                self.stop_recording()


    def stop_recording(self):
        self.p.param('Run').param('Start').setOpts(enabled=True)
        self.p.param('Run').param('Stop').setOpts(enabled=False)
        self.timer.stop()
        self.fileh.close()

        if REAL_DATA:
            self.taskI.close()
            self.taskO.close()

    def closeEvent(self, event):
        if 0:
            reply = QtGui.QMessageBox.question(self, 'Message',
                                               "Are you sure to quit?",
                                               QtGui.QMessageBox.Yes,
                                               QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.No:
                event.ignore()
                return

        if self.p.param('Run').param('Stop').opts['enabled']:
            self.stop_recording()
        #self.timer.stop()
        self.view.close()
        #self.camera.StopGrabbing()
        # camera has to be closed manually
        #self.camera.Close()
        event.accept()

#app = pg.mkQApp()
#window = FscvWin()
#app.references.add(window)
#window.show()


def main(**kwargs):
    """Create a QT window in Python, or interactively in IPython with QT GUI
    event loop integration.
    """
    app_created = False
    app = QtCore.QCoreApplication.instance()
    if  app is None:
        print(12321)
        app = QtGui.QApplication(sys.argv)
        app_created = True
    app.references = set()
    window = FscvWin(**kwargs)
    app.references.add(window)
    window.show()
    if app_created:
        app.exec_()
    return window, app

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    # Hide error from QMessageBox
    #os.environ["QT_LOGGING_RULES"] = "*.debug=false"
    os.environ["QT_LOGGING_RULES"] = ''#*.debug=false;qt.qpa.*=false'

    #window, app = main()
    #app = QtGui.QApplication(sys.argv)
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

