# -*- coding: utf-8 -*-
import os
import time
import configparser
from pathlib import Path

def getConfig():
    config = configparser.ConfigParser()
    config.read("lab.config")
    return config

def getNextFile(fileformatstring ="fscv%04i.h5"):
    data_path = Path(
        getConfig().get('DEFAULT', 'data_root_path', fallback='data'),  # data root path
        time.strftime("%Y-%m-%d", time.localtime())  # today's folder
    )
    #i0 = len(os.listdir(data_path))
    print(data_path)
    for i in range(10):
        try:
            p = Path(data_path, fileformatstring % i )
            p.mkdir(parents=True)
            return p
        except FileExistsError:
            print('already exists: ', i, p)
        #, exist_ok = True
    #Path(folder_name).mkdir(parents=True, exist_ok=True)

def getNextFile2(fileformatstring ="fscv%04i.h5"):
    data_path = Path(
        getConfig().get('DEFAULT', 'data_root_path', fallback='data'),  # data root path
        time.strftime("%Y-%m-%d", time.localtime())  # today's folder
    )

    data_path.mkdir(parents=True, exist_ok=True)
    print(data_path)

    i0 = len(os.listdir(data_path))
    for i in range(10):
        try:
            p = Path(data_path, fileformatstring % (i+i0-1) )
            p.mkdir(parents=True)
            return p
        except FileExistsError:
            print('already exists: ', i, p)
        #, exist_ok = True
    #Path(folder_name).mkdir(parents=True, exist_ok=True)


p = getNextFile()
print(p)