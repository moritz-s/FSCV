import sys
import numpy as np

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.dockarea as pqda

class FscvWin(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        ############################## ##############################
        area = self.area = pqda.DockArea()
        self.setCentralWidget(area)
        self.resize(1200, 500)
        self.setWindowTitle('Campy')

        do_cont = pqda.Dock("Control", size=(100, 400))
        do_figures = pqda.Dock("Image view", size=(500, 400))

        area.addDock(do_cont)
        area.addDock(do_figures, 'right', do_cont)

        do_figures.addWidget(pg.ImageView())
        do_cont.addWidget(pg.ImageView())

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    #window, app = main()
    app = QtGui.QApplication(sys.argv)
    window = FscvWin()
    window.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
