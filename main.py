import base
import sys
import os
import logging
import stateair
import reports
import patcher

def _prepare_config(config):
    """
    Loads the program configuration from the given json file.
    """

    def expand_config_path(key): config[key] = os.path.expanduser(config[key])

    expand_config_path('aqi_files_path')
    expand_config_path('reports_path')


def _json_fload(filename):
    import codecs
    import json
    with codecs.open(filename, 'r', 'utf-8') as file:
        return json.loads(file.read())

def _json_fsave(filename, obj):
    import codecs
    import json
    with codecs.open(filename, 'w', 'utf-8') as file:
        file.write(json.dumps(obj))


_PATCHER_CABLIRATION_FILE = "patcher-calibration.json"

def _do_calibrate(config):
    logging.info("Reading AQI files from %s" % config['aqi_files_path'])
    aqi_data = stateair.AqiDataSet(config['aqi_files_path'])

    calibration = patcher.AqiDataPatcher.calibrate_on_data(aqi_data)
    _json_fsave(_PATCHER_CABLIRATION_FILE, calibration)
    logging.info("Saved patcher calibration to '%s'" % _PATCHER_CABLIRATION_FILE)

    pass

def _do_reports(config):
    logging.info("Reading AQI files from %s" % config['aqi_files_path'])
    aqi_data = stateair.AqiDataSet(config['aqi_files_path'])

    if not os.path.exists(_PATCHER_CABLIRATION_FILE):
        raise Exception("Calibration file {0} not found; please run --calibrate first".format(_PATCHER_CABLIRATION_FILE))

    calibration = _json_fload("patcher-calibration.json")
    logging.info("Loaded patcher calibration from '%s'" % _PATCHER_CABLIRATION_FILE)
    patch = patcher.AqiDataPatcher(calibration)
    patch_stats = patch.estimate_missing_data(aqi_data)

    logging.info("Patcher filled %d missing items" % patch_stats['filled-items-count'])

    report = reports.DataAvailabilityReport.process(aqi_data)
    report.write_to_file(config['reports_path'])

    # report = reports.MonthlyAverageReport.process(aqi_data)
    # report.write_to_file(config['reports_path'])
    #
    # report = reports.SampleDistributionHistogramReport.process(aqi_data)
    # report.write_to_file(config['reports_path'])
    #
    # report = reports.HourlyMeanReport.process(aqi_data)
    # report.write_to_file(config['reports_path'])

    report = reports.MovingAverageReport.process(aqi_data)
    report.write_to_file(config['reports_path'])
    pass


if __name__ == "__main__":

    config = base.Init(sys.argv)
    _prepare_config(config)

    mode = 'reports'
    if '--calibrate' in sys.argv:
        mode = 'calibrate'

    if mode == 'calibrate':
        _do_calibrate(config)

    elif mode == 'reports':
        _do_reports(config)