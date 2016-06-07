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


class DataAvailabilityReport(AqiReportBase):

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):

        data = aqi_data.data_in_range()

        year_begin = data[0].date.date().year
        year_end = data[-1].date.date().year

        report = CsvReport(
            "Data Availability: {0} to {1}".format(year_begin, year_end),
            ['year'] + [str(i) for i in range(1, 13)])

        for year in range(year_begin, year_end + 1):
            new_row = { 'year': year }

            for month in range(1, 13):
                month_begin = datetime.date(year, month, 1)

                month_end_index = month + 1
                year_end_index = year
                if month_end_index == 13:
                    year_end_index += 1
                    month_end_index = 1

                month_data = aqi_data.data_in_range(month_begin, datetime.date(year_end_index, month_end_index, 1))
                new_row[str(month)] = month_data.valid_data_point_count() / len(month_data)

            report.append_data(new_row)

        return report
