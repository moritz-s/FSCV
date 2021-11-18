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
        data_root_path = getConfig().get('DEFAULT', 'data_root_path', fallback='data'),
        today_path = time.strftime("%Y-%m-%d", time.localtime()))
    #i0 = len(os.listdir(data_path))
    for i in range(10):
        try:
            p = Path(data_path, fileformatstring % i )
            p.mkdir(parents=True)
            return p
        except FileExistsError:
            print(i)
        #, exist_ok = True
    #Path(folder_name).mkdir(parents=True, exist_ok=True)

p = getNextFile()
