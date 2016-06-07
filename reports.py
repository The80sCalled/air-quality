import stateair
import datetime
import osutils
import csv
import os
import logging

class CsvReport:
    def __init__(self, description, fields):
        self.description = description
        self.fields = fields
        self.data = []

    def append_data(self, moredata):
        self.data.append(moredata)

    def write_to_file(self, report_path):
        osutils.ensure_dir(report_path)

        filename = os.path.join(report_path, osutils.make_valid_filename(self.description) + ".csv")
        logging.info("Writing report with {0} lines to '{1}'".format(len(self.data), filename))

        with open(filename, 'w', newline='\n') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fields)

            writer.writeheader()
            [writer.writerow(row) for row in self.data]




class AqiReportBase:
    @classmethod
    def process(cls, aqi_data):
        pass

def _month_data(aqi_data, period: datetime.date):
    month_begin = datetime.date(period.year, period.month, 1)

    month_end_index = period.month + 1
    year_end_index = period.year
    if month_end_index == 13:
        year_end_index += 1
        month_end_index = 1

    return aqi_data.data_in_range(month_begin, datetime.date(year_end_index, month_end_index, 1))


class DataAvailabilityReport(AqiReportBase):

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):

        all_data = aqi_data.data_in_range()

        year_begin = all_data[0].date.date().year
        year_end = all_data[-1].date.date().year

        report = CsvReport(
            "Data Availability: {0} to {1}".format(year_begin, year_end),
            ['year'] + [str(i) for i in range(1, 13)])

        for year in range(year_begin, year_end + 1):
            new_row = { 'year': year }

            for month in range(1, 13):
                month_data = _month_data(aqi_data, datetime.date(year, month, 1))
                new_row[str(month)] = month_data.valid_data_point_count() / len(month_data)

            report.append_data(new_row)

        return report


class MonthlyAverageReport(AqiReportBase):
    """
    Returns
    """

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):
        all_data = aqi_data.data_in_range()

        year_begin = all_data[0].date.date().year
        year_end = all_data[-1].date.date().year

        report = CsvReport(
            "Monthly Average: {0} to {1}".format(year_begin, year_end),
            ['year'] + [str(i) for i in range(1, 13)])

        for year in range(year_begin, year_end + 1):
            new_row = {'year': year}

            for month in range(1, 13):
                month_data = _month_data(aqi_data, datetime.date(year, month, 1))
                valid_count = month_data.valid_data_point_count()
                available_frac = valid_count / len(month_data)

                if available_frac < .8:
                    new_row[str(month)] = None
                else:
                    new_row[str(month)] = sum([p.value for p in month_data if p.isvalid()]) / valid_count

            report.append_data(new_row)

        return report

        pass

