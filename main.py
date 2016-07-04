import base
import sys
import os
import logging
import stateair
import reports

def _prepare_config(config):
    """
    Loads the program configuration from the given json file.
    """

    def expand_config_path(key): config[key] = os.path.expanduser(config[key])

    expand_config_path('aqi_files_path')
    expand_config_path('reports_path')


if __name__ == "__main__":

    config = base.Init(sys.argv)
    _prepare_config(config)

    logging.info("Reading AQI files from %s" % config['aqi_files_path'])

    aqi_data = stateair.AqiDataSet(config['aqi_files_path'])

    report = reports.DataAvailabilityReport.process(aqi_data)
    report.write_to_file(config['reports_path'])

    report = reports.MonthlyAverageReport.process(aqi_data)
    report.write_to_file(config['reports_path'])

    report = reports.SampleDistributionHistogramReport.process(aqi_data)
    report.write_to_file(config['reports_path'])

    report = reports.HourlyMeanReport.process(aqi_data)
    report.write_to_file(config['reports_path'])

