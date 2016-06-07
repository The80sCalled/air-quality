import logging
import os
import json
import codecs

def Init(argv):
    """
    Loads the program configuration from the given json file and sets up logging.  Returns the config dictionary.
    """

    def expand_config_path(key): config[key] = os.path.expanduser(config[key])

    if (len(argv) == 2):
        real_path = os.path.expanduser(argv[1])
        with codecs.open(real_path, "r", 'utf-8') as configFile:
            config = json.load(configFile)
            config['log_file'] = os.path.expanduser(config['log_file'])

            _init_logger(config['log_file'])

            logging.info("Loaded config file from %s", config['log_file'])

            return config

    raise "No config specified."


def _init_logger(logFilePath):
    import logging.handlers

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
