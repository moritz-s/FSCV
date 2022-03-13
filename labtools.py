# -*- coding: utf-8 -*-
import os
import time
import configparser
from pathlib import Path

def getConfig():
    """Reads a hostname specific config section in the config.ini file.
    If the hostname section does not exist, the DEFAULT section is returned.
    If the config.ini file does not exist, a default config is returned """
    general_config = configparser.ConfigParser()
    general_config['DEFAULT']['datapath'] = 'data'
    general_config.read("config.ini")
    # Generate a config file if it doesnt exist
    if not Path('config.ini').is_file():
        with open('config.ini', 'w') as configfile:
            general_config.write(configfile)

    return general_config['DEFAULT']

def getNextFile(config, fileformatstring ="fscv%04i.h5"):
    # get today's folder
    day_path = Path(config['datapath'], time.strftime("%Y-%m-%d", time.localtime()))
    day_path.mkdir(parents=True, exist_ok=True)

    # Find the next free filename (try 10 times)
    i0 = len(os.listdir(day_path))
    for i in range(10):
        try:
            p = Path(day_path, fileformatstring % (i+i0) )
            return p
        except FileExistsError:
            print('already exists: ', i, p)
    # Too much mess in the storage folder
    raise
