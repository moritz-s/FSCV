# -*- coding: utf-8 -*-
import os
import time
import configparser
import socket
from pathlib import Path

def getConfig():
    """Reads a hostname specific config section in the config.ini file.
    If the hostname section does not exist, the DEFAULT section is returned.
    If the config.ini file does not exist, a default config is returned """
    general_config = configparser.ConfigParser()
    general_config['DEFAULT']['datapath'] = 'data'
    general_config.read("config.ini")
    hostname = socket.gethostname()
    try:
        return general_config[hostname]
    except KeyError:
        return general_config['DEFAULT']

def getNextFile(config, fileformatstring ="fscv%04i.h5"):
    # get today's folder
    day_path = Path(config['datapath'], time.strftime("%Y-%m-%d", time.localtime()))
    day_path.mkdir(parents=True, exist_ok=True)

    i0 = len(os.listdir(day_path))
    print(i0)
    for i in range(10):
        try:
            p = Path(day_path, fileformatstring % (i+i0) )
            p.mkdir(parents=True)
            return p
        except FileExistsError:
            print('already exists: ', i, p)
    raise
        #, exist_ok = True
    #Path(folder_name).mkdir(parents=True, exist_ok=True)

# p = getNextFile()
# print(p)
