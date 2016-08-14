import stateair
import datetime
import osutils
import csv
import os
import logging
import statistics

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
    """
    Returns the data for the month into which the date 'period' falls.
    :param aqi_data:
    :param period:
    :return:
    """
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


class MovingAverageReport(AqiReportBase):
    """
    Returns data that shows, for each set of samples from a moving window, what are the
    mean and +/- N standard deviations for AQI.
    """

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):
        import math
        all_data = aqi_data.data_in_range()

        year = 2013
        window_size = datetime.timedelta(days=15)

        # Ensure the filter window is symmetric about the center point.  Since it's reasonable to expect that a moing box
        # filter of size hours=1 should be a simple pass through, this means that there will always be an odd number
        # of samples.
        window_half_size_in_samples = int(window_size.total_seconds() // 3600 // 2)
        window_size_in_samples = window_half_size_in_samples * 2 + 1
        window_begin_offset = datetime.timedelta(hours=window_half_size_in_samples)
        window_end_offset = datetime.timedelta(hours=(window_half_size_in_samples + 1))
        exp_factor = 20 * 24  # In samples, aka hours

        # Simple moving average
        kernel_func = [1 / window_size_in_samples for i in range(0, window_size_in_samples)]

        date_begin = datetime.datetime(year, 1, 1)
        date_end = datetime.datetime(year + 1, 1, 1)
        domain_total_days = int((date_end - date_begin).total_seconds() // 86400)

        report = CsvReport(
            "Moving average and N stdev: {0}".format(year),
            ['day'] + [str(year), str(year) + '-dx', str(year) + '-raw'])

        for day in range(0, domain_total_days):
            new_row = { 'day': day }
            center_datetime = date_begin + datetime.timedelta(days=day, hours=12)

            window_data = aqi_data.data_in_range(center_datetime - window_begin_offset, center_datetime + window_end_offset)
            avg = sum([window_data[x].value * kernel_func[x] for x in range(0, window_size_in_samples)])
            # Standard uncertainty propagation
            dx = math.sqrt(sum([y * y for y in
                                [abs(kernel_func[x]) * window_data[x].uncertainty for x in range(0, window_size_in_samples)]]))

            new_row[str(year)] = avg
            new_row[str(year) + '-dx'] = dx
            new_row[str(year) + '-raw'] = window_data[window_half_size_in_samples].value

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


class SampleDistributionHistogramReport(AqiReportBase):
    """
    Puts all samples into buckets for histogramming, then transforms it to a dimensionless distribution
    for use with curve-fitting.
    """

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):
        all_data = aqi_data.data_in_range()
        MAX_VALUE = 500

        report = CsvReport(
            "Sample Histogram",
            ["U", "PU"]
        )

        samples = [x.value for x in all_data if x.isvalid() and 5 <= x.date.date().month <= 9]
        bucket_counts = [0 for i in range(0, MAX_VALUE)]

        for sample in samples:
            int_sample = int(sample)
            if int_sample < len(bucket_counts):
                bucket_counts[int_sample] += 1

        overall_mean = statistics.mean(samples)
        logging.info("Analyzed {0} samples. Mean = {1}, Stdev = {2}".format(len(samples), overall_mean, statistics.stdev(samples, overall_mean) / overall_mean))

        logging.warning("Discarded {0} points because they were outside the bucket range".format(len(all_data) - len(samples)))

        for i in range(0, len(bucket_counts)):
            report.append_data({'U': i / overall_mean, 'PU': bucket_counts[i] / len(samples) * overall_mean})

        return report

class HourlyMeanReport(AqiReportBase):

    @classmethod
    def process(cls, aqi_data: stateair.AqiDataSet):
        all_data = aqi_data.data_in_range()

        report = CsvReport(
            "Hourly Mean",
            ["Hour", "Count", "Mean"]
        )

        samples = [x for x in all_data if x.isvalid()]
        hour_dict = [{'sum': 0, 'count': 0} for x in range(24)]

        for sample in samples:
            hour_info = hour_dict[sample.date.time().hour]
            hour_info['sum'] += sample.value
            hour_info['count'] += 1

        for hour in range(0, 24):
            hour_info = hour_dict[hour]
            report.append_data({'Hour': hour, 'Count': hour_info['count'], 'Mean': hour_info['sum'] / hour_info['count']})

        return report

