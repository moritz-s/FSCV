# -*- coding: utf-8 -*-
import os
import sys
import time
import numpy as np
import tables as tb

import pyqtgraph as pg
import pyqtgraph.dockarea as pqda
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph.widgets.RemoteGraphicsView

import nidaqmx
from nidaqmx import stream_writers  # Explicit import Required !
from nidaqmx import stream_readers  # Explicit import Required !

class FscvWin(QtGui.QMainWindow):
    """Main window for the FSCV measurement"""
    def __init__(self):
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
            {'name': 'Pulse config', 'type': 'group', 'children': [
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
            ]},
            {'name': 'Run', 'type': 'group', 'children': [
                {'name': 'Start', 'type': 'action'},
                {'name': 'Stop', 'type': 'action', 'enabled': False},
                {'name': 'Limit (N)', 'type': 'int', 'value': 0},
            ]},
            {'name': 'Monitor', 'type': 'group', 'children': [
                {'name': 'Aquisition frequency', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 'Hz',
                 'readonly': True},
            ]},
            {'name': 'DAQ', 'type': 'group', 'children': [
                {'name': 'Database', 'type': 'str', 'value': '',
                 'readonly': True},
            ]},
            ]
        ## Create tree of Parameter objects
        self.p = p = Parameter.create(name='params', type='group', children=params)

        ## If anything changes in the tree, print a message
        def change(param, changes):
            print("tree changes:")
            for param, change, data in changes:
                path = p.childPath(param)
                if path is not None:
                    childName = '.'.join(path)
                else:
                    childName = param.name()
                print('  parameter: %s' % childName)
                print('  change:    %s' % change)
                print('  data:      %s' % str(data))
                print('  ----------')

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
        # TODO get from gui

        #{'name': 'Pulse config', 'type': 'group', 'children': [
        #    {'name': 'U_0', 'type': 'float', 'value': -0.4, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
        #     'suffix': 'V'},
        #    {'name': 'U_1', 'type': 'float', 'value': -1.0, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
        #     'suffix': 'V'},
        #    {'name': 'Pre ramp time', 'type': 'float', 'value': 1e-2, 'step': 1e-3, 'limits': (0, 1e3),
        #     'siPrefix': True, 'suffix': 's'},
        #    {'name': 'Total ramp time', 'type': 'float', 'value': 1e-2, 'step': 1e-3, 'limits': (0, 1e3),
        #     'siPrefix': True, 'suffix': 's'},
        #    {'name': 'Post ramp time', 'type': 'float', 'value': 8e-2, 'step': 1e-3, 'limits': (0, 1e3),
        #     'siPrefix': True, 'suffix': 's'},

        U_0 = self.p.param('Pulse config').param('U_0').value()
        U_1 = self.p.param('Pulse config').param('U_1').value()
        T_pre = self.p.param('Pulse config').param('Pre ramp time').value()
        T_pulse = self.p.param('Pulse config').param('Total ramp time').value()
        T_post = self.p.param('Pulse config').param('Post ramp time').value()
        self.fs = 50000.0

        #umax = 1.2
        #umin = -0.4
        #Tramp = 0.01
        #Tbase = 0.1
        #base = np.ones(int(Tbase * self.fs)) * umin
        #ramp = np.linspace(umin, umax, int(Tramp * self.fs))
        #out = 5.0 * np.hstack([ramp, ramp[::-1], base])
        #self.nTotal = len(out)

        base_pre = np.ones(int(T_pre * self.fs)) * U_0
        base_post = np.ones(int(T_post * self.fs)) * U_0
        ramp = np.linspace(U_0, U_1, int(T_pulse/2 * self.fs))
        out = 5.0 * np.hstack([base_pre, ramp, ramp[::-1], base_post])
        self.nTotal = len(out)

        # GUI settings
        self.p.param('Run').param('Start').setOpts(enabled=False)
        self.p.param('Run').param('Stop').setOpts(enabled=True)

        fln = "test.h5" #self.mtree.param('Filename').value() + '.h5'
        dataroot = "." #self.mtree.param('Dataroot').value()
        self.fileh = tb.open_file(os.path.join(dataroot, fln), mode='w')

        complevel = 5#np.int(self.mtree.param("BloscLevel").value())
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root, 'array_scans', tb.FloatAtom(),
                                              (self.nTotal, 0), "Scans",
                                              filters=filters,
                                              expectedrows=500)

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
        self.timer.start(500)

    def update(self):
        # DAQStart
        self.taskI.start()
        self.taskO.start()

        # Acquire data
        data = np.zeros((3, self.nTotal))

        self.reader.read_many_sample(data, nidaqmx.constants.READ_ALL_AVAILABLE, timeout=((2+self.nTotal) / self.fs))
        time.sleep(0.005)

        # Stop
        self.taskI.stop()
        self.taskO.stop()

        #data = np.random.normal(size=(100, 50)).sum(axis=1)
        #data += 5 * np.sin(np.linspace(0, 10, data.shape[0]))

        self.rplt.plot(data[0], clear=True, _callSync='off')
        self.rplt.plot(data[1], clear=True, _callSync='off')

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


    def stop_recording(self):
        self.p.param('Run').param('Start').setOpts(enabled=True)
        self.p.param('Run').param('Stop').setOpts(enabled=False)
        self.timer.stop()
        self.fileh.close()

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
    app = QtGui.QApplication(sys.argv)
    window = FscvWin()

    #try:
    window.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
    #finally:
        # Stop
        #window.taskI.close()
        #window.taskO.close()
