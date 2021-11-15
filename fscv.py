# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
import tables as tb

import pyqtgraph as pg
import pyqtgraph.dockarea as pqda
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph.widgets.RemoteGraphicsView


class FscvWin(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
############################## ##############################
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
                {'name': 'U_1', 'type': 'float', 'value': -1.0, 'step': 1e-2, 'limits': (-2, 2), 'siPrefix': True,
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
                {'name': 'Stop', 'type': 'action'},
                {'name': 'Limit (N)', 'type': 'int', 'value': 0},
            ]},
            {'name': 'Monitor', 'type': 'group', 'children': [
                {'name': 'Aquisition frequency', 'type': 'float', 'value': 0, 'siPrefix': True, 'suffix': 'Hz',
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
        #p.param('Run', 'Stop').sigActivated.connect(restore)
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

        self.lastUpdate = pg.ptime.time()
        self.avgFps = 0.0
        self.start_recording()

    def update(self):
        data = np.random.normal(size=(100, 50)).sum(axis=1)
        data += 5 * np.sin(np.linspace(0, 10, data.shape[0]))

        self.rplt.plot(data, clear=True, _callSync='off')

        self.array_scans.append(data[:, np.newaxis])

        #self.im_rplt.setImage(self.array_imgs)#np.ascontiguousarray(im_data))
        self.im_rplt.setImage(np.array(self.array_scans))#np.ascontiguousarray(im_data))


        now = pg.ptime.time()
        fps = 1.0 / (now - self.lastUpdate)
        self.lastUpdate = now
        self.avgFps = self.avgFps * 0.8 + fps * 0.2
        self.p.param('Monitor').param('Aquisition frequency').setValue(self.avgFps)
        #self.label.setText("Generating %0.2f fps" % self.avgFps)

    def start_recording(self):
        fln = "test.h5" #self.mtree.param('Filename').value() + '.h5'
        dataroot = "." #self.mtree.param('Dataroot').value()
        self.fileh = tb.open_file(os.path.join(dataroot, fln), mode='w')

        H = 100
        complevel = 5#np.int(self.mtree.param("BloscLevel").value())
        filters = tb.Filters(complevel=complevel, complib='blosc')
        self.array_scans = self.fileh.create_earray(self.fileh.root, 'array_imgs', tb.FloatAtom(),
                                              (H, 0), "Imgs",
                                              filters=filters,
                                              expectedrows=500)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(10)


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
    #window, app = main()
    app = QtGui.QApplication(sys.argv)
    window = FscvWin()
    window.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()

