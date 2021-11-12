# -*- coding: utf-8 -*-
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
# import pyqtgraph.console
import pyqtgraph.dockarea as pqda
from pyqtgraph.parametertree import Parameter, ParameterTree
import tables as tb

import sys
import numpy as np

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.widgets.RemoteGraphicsView


class FscvWin(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        view = pg.widgets.RemoteGraphicsView.RemoteGraphicsView()
        #pg.setConfigOptions(antialias=True)  ## this will be expensive for the local plot
        view.pg.setConfigOptions(antialias=True)  ## prettier plots at no cost to the main process!
        view.setWindowTitle('pyqtgraph example: RemoteSpeedTest')

        self.label = QtGui.QLabel()
        rcheck = QtGui.QCheckBox('plot remote')
        rcheck.setChecked(True)
        lcheck = QtGui.QCheckBox('plot local')

        lplt = pg.PlotWidget()
        layout = pg.LayoutWidget()
        layout.addWidget(rcheck)
        layout.addWidget(lcheck)
        layout.addWidget(self.label)
        layout.addWidget(view, row=1, col=0, colspan=3)
        layout.addWidget(lplt, row=2, col=0, colspan=3)
        layout.resize(800, 800)
        layout.show()

        ## Create a PlotItem in the remote process that will be displayed locally
        rplt = view.pg.PlotItem()
        rplt._setProxyOptions(deferGetattr=True)  ## speeds up access to rplt.plot
        view.setCentralItem(rplt)

        self.lastUpdate = pg.ptime.time()
        self.avgFps = 0.0

    def update(self):
        data = np.random.normal(size=(10000, 50)).sum(axis=1)
        data += 5 * np.sin(np.linspace(0, 10, data.shape[0]))

        if rcheck.isChecked():
            rplt.plot(data, clear=True, _callSync='off')  ## We do not expect a return value.
            ## By turning off callSync, we tell
            ## the proxy that it does not need to
            ## wait for a reply from the remote
            ## process.
        if lcheck.isChecked():
            lplt.plot(data, clear=True)

        now = pg.ptime.time()
        fps = 1.0 / (now - self.lastUpdate)
        self.lastUpdate = now
        self.avgFps = self.avgFps * 0.8 + fps * 0.2
        label.setText("Generating %0.2f fps" % self.avgFps)


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
    if app is None:
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
    window, app = main()

    timer = QtCore.QTimer()
    timer.timeout.connect(window.update)
    timer.start(0)

    #if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #    QtGui.QApplication.instance().exec_()

