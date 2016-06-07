import base
import sys
import os
import logging
import stateair
import csv

def _prepare_config(config):
    """
    Loads the program configuration from the given json file.
    """

    def expand_config_path(key): config[key] = os.path.expanduser(config[key])

    expand_config_path('aqi_files_path')

if __name__ == "__main__":

    config = base.Init(sys.argv)
    _prepare_config(config)

    logging.info("Reading AQI files from %s" % config['aqi_files_path'])

    aqiData = stateair.DataSet(config['aqi_files_path'])




