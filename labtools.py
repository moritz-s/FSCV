# -*- coding: utf-8 -*-
import os
import time
import configparser
from pathlib import Path

def getConfig(section='DEFAULT'):
    """Reads values from a config.ini file. The DEFAULT section is returned.
    If the config.ini file does not exist, it is created and a default config
    is returned. If section is None the complete config file is returned"""
    general_config = configparser.ConfigParser()
    general_config['DEFAULT']['datapath'] = 'data'
    general_config.read("config.ini")
    # Generate a config file if it doesnt exist
    if not Path('config.ini').is_file():
        with open('config.ini', 'w') as configfile:
            general_config.write(configfile)

    if section is None:
        return general_config
    else:
        return general_config[section]

def get_folder_of_the_day(config):
    """Returns todays folder, the folder is created if it does not exist"""
    day_path = Path(config['datapath'], time.strftime("%Y-%m-%d", time.localtime()))
    day_path.mkdir(parents=True, exist_ok=True)
    return day_path

def getNextFile(config, fileformatstring ="fscv%04i.h5"):
    day_path = get_folder_of_the_day(config)

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
