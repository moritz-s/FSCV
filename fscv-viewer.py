import sys
import os
import numpy as np
import pyqtgraph as pg
import tables as tb

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

import labtools

class Widget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        hlay = QHBoxLayout(self)
        self.treeview = QTreeView()
        self.listview = QListView()
        hlay.addWidget(self.treeview)
        hlay.addWidget(self.listview)

        config = labtools.getConfig()
        self.datapath = datapath = config['datapath']#QDir.rootPath()

        self.dirModel = QFileSystemModel()
        self.dirModel.setRootPath(datapath)#QDir.rootPath())
        self.dirModel.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs)

        self.fileModel = QFileSystemModel()
        self.fileModel.setFilter(QDir.NoDotAndDotDot |  QDir.Files)

        self.treeview.setModel(self.dirModel)
        self.listview.setModel(self.fileModel)

        self.treeview.setRootIndex(self.dirModel.index(datapath))
        self.listview.setRootIndex(self.fileModel.index(datapath))

        self.treeview.clicked.connect(self.on_clicked)
        self.listview.clicked.connect(self.list_clicked)

    def on_clicked(self, index):
        self.selected_path = path = self.dirModel.fileInfo(index).absoluteFilePath()
        self.listview.setRootIndex(self.fileModel.setRootPath(path))

    def list_clicked(self, index):
        data_filename = os.path.join(self.datapath, self.selected_path, index.data())
        data_file = tb.open_file(data_filename)
        dat = data_file.root.array_scans
        pg.image(np.array(dat))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Widget()
    w.show()
    sys.exit(app.exec_())
