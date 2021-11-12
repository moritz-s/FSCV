# -*- coding: utf-8 -*-
import time
import sys
import os
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
# import pyqtgraph.console
import pyqtgraph.dockarea as pqda
from pyqtgraph.parametertree import Parameter, ParameterTree
import configparser
from itertools import cycle
from pypylon import pylon
import tables as tb

import mo_dls


class Campy(QtGui.QMainWindow):
    def __init__(self, camera=None):
        # Create an instant camera object with the camera device found first.
        self.camera = camera
        if camera is None:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().
                                              CreateFirstDevice())

        # Print the model name of the camera.
        camString = self.camera.GetDeviceInfo().GetModelName() + ' ' +\
            self.camera.GetDeviceInfo().GetUserDefinedName()
        print "Using device ", camString
        self.camera.Open()
        self.camera.PixelFormat = "Mono8"

        # Parameter
        # self.updint = 500    # ms
        # GUI Settings
        measurement_tree = [
            {'name': 'Dataroot', 'type': 'str', 'readonly': True},
            {'name': 'Filename', 'type': 'str', 'readonly': True},
            {'name': 'Camera', 'type': 'str', 'readonly': True,
                'value': camString},
            {'name': 'Sample', 'type': 'str', 'value': ''},
            {'name': 'Save', 'type': 'list', 'values': {"None": 0,
                                                        "Contrasts": 1,
                                                        "Images": 2},
                'value': 2},
            # {'name': 'Save', 'type': 'bool', 'value': True},
            {'name': 'Loop', 'type': 'bool', 'value': False},
            {'name': 'N', 'type': 'int', 'value': '4'},
            {'name': 'n', 'type': 'int', 'value': '0', 'readonly': True},
            {'name': 'BloscLevel', 'type': 'int', 'value': 5,
                'limits': (0, 9)},
            {'name': 'Exposure', 'type': 'float', 'siPrefix': True,
                'suffix': 's', 'value': 0.01, 'limits': (16e-6, 1)},
            {'name': 'Interval', 'type': 'float', 'siPrefix': True,
                'suffix': 's', 'value': 0.5, 'limits': (1e-3, 1000)},
            {'name': 'ExposureFactors', 'type': 'str', 'value': '1'},
            {'name': 'T0', 'type': 'float', 'siPrefix': True, 'suffix': 's',
                'readonly': True},
            ]

        # GUI layout
        if 1:
            QtGui.QMainWindow.__init__(self)
            area = self.area = pqda.DockArea()
            self.setCentralWidget(area)
            self.resize(1200, 500)
            self.setWindowTitle('Campy')

            do_cont = pqda.Dock("Control", size=(100, 400))
            do_camera = pqda.Dock("Image view", size=(500, 400))

            area.addDock(do_cont)
            area.addDock(do_camera, 'right', do_cont)

            self.imv = pg.ImageView()
            self.himv = self.imv.getHistogramWidget()
            #self.himv.setYRange([0.0, 256.0])#, padding=0)
            self.himv.setHistogramRange(0, 256, padding=0.0)
            do_camera.addWidget(self.imv)

            # Control
            layout = pg.LayoutWidget()
            do_cont.addWidget(layout)
            # label = QtGui.QLabel(""" -- cospy -- """)
            # layout.addWidget(label, row=0, col=0)

            self.startBtn = startBtn = QtGui.QPushButton('Start')
            startBtn.clicked.connect(self.startCamMeasurement)
            layout.addWidget(startBtn, row=0, col=0)

            self.stopBtn = stopBtn = QtGui.QPushButton('Stop')
            stopBtn.clicked.connect(self.stopCamMeasurement)
            layout.addWidget(stopBtn, row=1, col=0)

            self.openresBtn = openresBtn = QtGui.QPushButton('Open Result')
            openresBtn.clicked.connect(self.openRes)
            layout.addWidget(openresBtn, row=2, col=0)

            # Create tree of Measurement Settings
            self.measurement = measurement_tree

            self.mtree = Parameter.create(name='measurement', type='group',
                                          children=self.measurement)
            self.mtree.sigTreeStateChanged.connect(self.pchange)
            self.t2 = ParameterTree()
            self.t2.setParameters(self.mtree, showTop=False)
            layout.addWidget(self.t2, row=3, col=0)

        self.createNewFolder()
        self.stopBtn.setDisabled(True)
        
        self.mtree.param('Exposure').setValue(0.1)
        self.expFcycl = False
        
        # Update Timer
        self.t = QtCore.QTimer()
        self.t.timeout.connect(self.update)
        self.t.start(np.int(1e3*self.mtree.param("Interval").value()))

    def update(self):
        if self.camera.IsGrabbing():
            # Wait for an image and then retrieve it. A timeout of 5000 ms is
            # used.
            grabResult = self.camera.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException)
            # Image grabbed successfully?
            if grabResult.GrabSucceeded():
                # print grabResult.GetImageFormat()
                self.grabResult = grabResult
                imgarr = grabResult.Array
                if imgarr.min()==imgarr.max():
                    # Workaround: Catch Histogramm Bug
                    imgarr = np.ones_like(imgarr)*np.linspace(0,100,imgarr.shape[1])
                    print 'Overload'
                
                if self.saving > 0:
                    self.array_ts.append(np.array([time.time()])[np.newaxis])
                    n = self.array_ts.shape[-1]
                    if self.expFcycl:
                         self.array_exps.append(np.array([self.thisExposure])[np.newaxis])
                    if self.saving == 1:
                        self.array_means.append(np.array([np.mean(imgarr)])[np.newaxis])
                        self.array_stds.append(np.array([np.std(imgarr)])[np.newaxis])
                    if self.saving == 2:
                        self.array_imgs.append(imgarr[:, :, np.newaxis])
                else:
                    #print 'exp: %3i ms , mean %3.0f'%(self.thisExposure, np.mean(imgarr))
                    self.n_imgcount += 1
                    n = self.n_imgcount
                self.imv.setImage(imgarr, autoLevels=False,
                                  autoHistogramRange=False, autoRange=False)
                # imageWindow.Show()
            else:
                print("Error: ", grabResult.ErrorCode)
                # grabResult.ErrorDescription does not work properly in python
                # could throw UnicodeDecodeError
            grabResult.Release()
            
            if self.expFcycl:
                efaktor = self.expFcycl.next()
                self.thisExposure = self.exposure*efaktor
                self.camera.ExposureTimeAbs.SetValue(self.thisExposure)
                gainn = int(self.gainF/efaktor)
                if gainn > 650:
                    gainn=650
                # print self.gainF, self.thisExposure
                # print 'g', gainn
                self.camera.GainRaw.SetValue(gainn)

            self.mtree.param('n').setValue(n)
            if n == np.int(self.mtree.param("N").value()):
                self.stopCamMeasurement()
                if self.mtree.param('Loop').value():
                    for i in range(4):
                        try:
                            time.sleep(2)
                            self.startCamMeasurement()
                            break
                        except RuntimeError:
                            print "Fuck"
                            continue

    def createNewFolder(self):
        dataroot = mo_dls.getNextFolderOfTheDay('CAM-')
        self.mtree.param('Dataroot').setValue(dataroot)
        self.i_file = 0
        self.mtree.param('Filename').setValue('CAM_%04i' % 0)

    def startCamMeasurement(self):
        # Start the grabbing of c_countOfImagesToGrab images.
        # The camera device is parameterized with a default configuration which
        # sets up free-running continuous acquisition.
        N = np.int(self.mtree.param("N").value())
        self.saving = np.int(self.mtree.param('Save').value())
        if self.saving > 0:
            try:
                fln = self.mtree.param('Filename').value()+'.h5'
                dataroot = self.mtree.param('Dataroot').value()
                fileh = tb.open_file(os.path.join(dataroot, fln), mode='w')
            except ValueError as e:
                print 'Could not open file %s, increasing filenumber.' % fln
                print str(e)
                self.i_file += 1
                self.mtree.param('Filename').setValue('CAM_%04i' % self.i_file)
                return

            ta = tb.FloatAtom()
            array_ts = fileh.create_earray(fileh.root, 'array_ts', ta,
                                           (1, 0), "Times", expectedrows=N)
            if self.expFcycl:
                array_exps = fileh.create_earray(fileh.root, 'array_exps', ta,
                                           (1, 0), "Exposures", expectedrows=N)
                self.array_exps = array_exps

            self.array_ts = array_ts
            
            if self.saving == 1:
                array_means = fileh.create_earray(
                    fileh.root, 'array_means', ta, (1, 0),
                    "Means", expectedrows=N)
                self.array_means = array_means
                array_stds = fileh.create_earray(
                    fileh.root, 'array_stds', ta, (1, 0),
                    "Stds", expectedrows=N)
                self.array_stds = array_stds
                print "Writing %s : N=%i  Only Contrasts!" % \
                    (fileh.filename, N)
            elif self.saving == 2:
                a = tb.UInt8Atom()
                H, W = self.camera.Height(), self.camera.Width()
                complevel = np.int(self.mtree.param("BloscLevel").value())
                filters = tb.Filters(complevel=complevel, complib='blosc')
                array_imgs = fileh.create_earray(fileh.root, 'array_imgs', a,
                                                 (H, W, 0), "Imgs",
                                                 filters=filters,
                                                 expectedrows=N)
                self.array_imgs = array_imgs
                print "Writing %s : %i x %i  N=%i  Compression: %i" % \
                    (fileh.filename, W, H, N, complevel)

            self.fileh = fileh
        else:
            self.n_imgcount = 0
            self.fileh = None

        self.startBtn.setDisabled(True)
        self.stopBtn.setDisabled(False)
        self.mtree.param('T0').setValue(time.time())
        self.camera.StartGrabbingMax(N, pylon.GrabStrategy_LatestImageOnly)

    def stopCamMeasurement(self):
        self.startBtn.setDisabled(False)
        self.stopBtn.setDisabled(True)
        self.camera.StopGrabbing()
        if self.saving > 0:
            vls = self.mtree.getValues()
            # Read all GUI Setting into Dictionary
            for k in vls:
                self.array_ts.attrs[k] = vls[k][0]
                # print k, vls[k], vls[k][0]
            print "Closing: ", self.fileh.filename
            self.fileh.close()
            self.i_file += 1
            self.mtree.param('Filename').setValue('CAM_%04i' % self.i_file)

    def pchange(self, param, changes):
        for param, change, data in changes:
            path = self.mtree.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            if str(childName) == "Exposure":
                exp_us = np.int(1e6*np.float(data))
                #self.camera.ExposureTimeAbs.SetValue(exp_us)
                self.exposure = exp_us
                self.thisExposure = exp_us
            if str(childName) == "Interval":
                self.t.setInterval(np.int(1e3*data))
            if str(childName) == "ExposureFactors":    
                expF = np.array(data.split(","), dtype=np.int)
                expMax = np.max(expF)
                self.gainF = expMax*100
                if len(expF) > 1:
                    self.expFcycl = cycle(expF)
                else:
                    self.expFcycl = False
            # print'parameter:%15s  change:%15s  data:%15s'%(str(childName),
            # str(change), str(data))

    def openRes(self):
        fn = QtGui.QFileDialog.getOpenFileName(
                           caption="Open Image Data",
                           filter="*.h5",
                           directory=self.mtree.param('Dataroot').value())
        if len(fn[0]) > 1:
            with tb.open_file(fn[0], mode='r') as fileh:
                im = np.array(fileh.root.array_imgs)
                pg.image(im, title=fn[0])

    def closeEvent(self, event):
        if 0:
            reply = QtGui.QMessageBox.question(self, 'Message',
                                               "Are you sure to quit?",
                                               QtGui.QMessageBox.Yes,
                                               QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.No:
                event.ignore()
                return
        self.t.stop()
        self.camera.StopGrabbing()
        # camera has to be closed manually
        self.camera.Close()
        event.accept()


def main(window_class=Campy, **kwargs):
    """Create a QT window in Python, or interactively in IPython with QT GUI
    event loop integration.
    """
    app_created = False
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
        app_created = True
    app.references = set()
    window = window_class(**kwargs)
    app.references.add(window)
    window.show()
    if app_created:
        app.exec_()
    return window, app


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(unicode("lab.config"))

    # Get the transport layer factory.
    tlFactory = pylon.TlFactory.GetInstance()

    # Get all attached devices and exit application if no device is found.
    devices = tlFactory.EnumerateDevices()
    if len(devices) == 0:
        raise pylon.RUNTIME_EXCEPTION("No camera present.")

    # Create an array of instant cameras for the found devices and avoid
    # exceeding a maximum number of devices.
    cameras = pylon.InstantCameraArray(min(len(devices), 3))
    nCameras = cameras.GetSize()
    print 'Found %i cameras.' % nCameras
    for i, cam in enumerate(cameras):
        cam.Attach(tlFactory.CreateDevice(devices[i]))
        print "%i: " % i, cam.GetDeviceInfo().GetModelName(),\
            cam.GetDeviceInfo().GetUserDefinedName()

    camera = None
    camID = config.get('Camera', 'DefaultCam', fallback='-1')

    if nCameras == 1:
        n = 0
    elif camID != '-1':
        n = camID
    else:
        n = raw_input('Select device: ')
    try:
        n = int(n)
        camera = cameras[n]
    except (ValueError, IndexError) as e:
        print 'Error selecting camera ', n, '. ', str(e)
    if camera is not None:
        campywin, app = main(camera=camera)
    app.exec_()
    # except RuntimeException
