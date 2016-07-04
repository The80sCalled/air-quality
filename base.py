import logging
import os
import json
import codecs

def InitTest():
    return _init_internal("test/config.json")

def Init(argv):
    if len(argv) == 1:
        config_path = "./config.json"
    elif len(argv) == 2:
        config_path = os.path.expanduser(argv[1])
    else:
        raise Exception("Wrong number of arguments.  Syntax: main.py [<config-json-path>]")

    return _init_internal(config_path)


def _init_internal(config_file):
    """
    Loads the program configuration from the given json file and sets up logging.  Returns the config dictionary.
    """

    def expand_config_path(key): config[key] = os.path.expanduser(config[key])

    with codecs.open(config_file, 'r', 'utf-8') as configFile:
        config = json.load(configFile)
        config['log_file'] = os.path.expanduser(config['log_file'])

        _init_logger(config['log_file'])

        logging.info("Loaded config file from %s", config['log_file'])

        return config


def _init_logger(logFilePath):
    import logging.handlers
    import sys

    formatter = logging.Formatter(
        fmt = "%(asctime)s: %(filename)s:%(lineno)d %(levelname)s:%(name)s: %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S")
    handlers = [
        logging.handlers.RotatingFileHandler(logFilePath, encoding = 'utf-8',
            maxBytes = 1000000, backupCount = 1),
        logging.StreamHandler()
    ]
    root_logger = logging.getLogger()
    root_logger.handlers = []   # Default root logger contains a FileHandler that writes with cp1252 codec. Screw that.

    root_logger.setLevel(logging.DEBUG)
    for h in handlers:
        h.setFormatter(formatter)
        h.setLevel(logging.DEBUG)

        root_logger.addHandler(h)

    logging.info("Started logging")
    sys.excepthook = _unhandled_exception

def _unhandled_exception(ex_cls, ex, tb):
    import traceback
    # See http://blog.tplus1.com/blog/2012/08/05/python-log-uncaught-exceptions-with-sys-excepthook/
    logging.critical(''.join(traceback.format_tb(tb)))
    logging.critical('{0}: {1}'.format(ex_cls, ex))
    logging.critical(ex.__dict__)
