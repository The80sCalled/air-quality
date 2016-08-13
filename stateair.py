import logging
import os
import io
import datetime
import unittest
import collections
import bisect


class AqiDataSet:

    # This is useful when correlating data with real world system times, which we never do.  Can add it later.
    #TIME_ZONE = datetime.timezone(datetime.timedelta(hours = 8))

    @staticmethod
    def _files_matching(path, pattern):
        import fnmatch

        full_names = [os.path.join(path, f) for f in os.listdir(path)]
        return [f for f in full_names
                if os.path.isfile(f) and
                fnmatch.fnmatch(os.path.basename(f), pattern)]

    @staticmethod
    def _load_csv_skip_header(filename):
        """
        Loads a CSV file by skipping all lines before the list of fields in the CSV file.  Assumes
        there's at least two fields in the CSV file.
        :return:
        """
        import itertools
        import csv
        import math

        skip_lines = 0
        found_header = False

        def _is_valid_field_name(field):
            return len(field) > 0 and field == field.strip()

        with open(filename, "r") as file:
            for line in file.readlines():
                split_line = line.strip().split(',')
                valid_fields = [t for t in split_line if _is_valid_field_name(t)]

                if len(split_line) > 1 and len(split_line) == len(valid_fields):
                    found_header = True
                    break

                skip_lines += 1

            if (not found_header):
                logging.warning("Couldn't find CSV header in file '{0}'".format(filename))

            file.seek(0, io.SEEK_SET)

            file_without_header = itertools.islice(file, skip_lines, None)

            return list([r for r in [AqiDataSet._standardize_row_format(row) for row in csv.DictReader(file_without_header)]
                        if r is not None])

    @staticmethod
    def _standardize_row_format(row):
        import math
        row["Date"] = datetime.datetime(int(row["Year"]), int(row["Month"]), int(row["Day"]), int(row["Hour"]))

        if row["QC Name"] != "Valid" or float(row["Value"]) < 0:
            row["Value"] = math.nan
        else:
            row["Value"] = float(row["Value"])

        # Verify assumptions that are baked into all the code
        # mg^3 / g^3: data for 2008 contains a typo
        if row["Unit"] != "µg/mg³" and row["Unit"] != "µg/m³":
            logging.warning("Weird unit at {0}: '{1}'".format(row["Date"], row["Unit"]))
            return None

        if row["Duration"] != "1 Hr":
            logging.warning("Weird duration at {0}: '{1}'".format(row["Date"], row["Duration"]))
            return None

        # Remove all the fields we don't need anymore
        [row.pop(f) for f in ["Date (LST)", "Year", "Month", "Day", "Hour", "Unit", "Duration", "QC Name"]]

        return row

    @staticmethod
    def _fix_dst_duplicates(rows):
        """
        The software that calculates the recorded time exhibits a bug during the spring DST transition (this is strange
        because China doesn't have DST), so there are some duplicate entries.  These are fixed here.
        :param rows: Hourly data.  May contain gaps; assumed to be sorted.
        :return: Nothing.
        """
        row_dates = [row['Date'] for row in rows]

        # Find up to one duplicate at 3am in the month of March; any others will be flagged.
        for year in range(row_dates[0].date().year, row_dates[-1].date().year + 1):
            march_begin = datetime.datetime(year, 3, 1)
            march_end = datetime.datetime(year, 4, 1)

            # If we don't have data for March in a given year, then range(first_index, last_index - 1) will be empty.
            first_index = bisect.bisect_left(row_dates, march_begin)
            last_index = bisect.bisect_left(row_dates, march_end)

            for i in range(first_index, last_index - 1):
                if (row_dates[i] == row_dates[i + 1] and row_dates[i].time().hour == 3):
                    rows[i]['Date'] += datetime.timedelta(hours = -1)
                    logging.info("Fixed DST error at {0}".format(rows[i]['Date']))
                    break

    @classmethod
    def _sort_and_fill_gaps(cls, rows):
        """
        Adds entries with None if any are missing.
        :param rows:
        :return:
        """
        import math

        rows.sort(key=lambda row: row["Date"])
        AqiDataSet._fix_dst_duplicates(rows)

        new_rows = []

        previous_row = None

        for r in rows:
            if (previous_row is not None):
                # do a quick duplicate check
                if (previous_row['Date'] == r['Date']):
                    raise BaseException("Duplicate data for date {0}".format(r['Date']))

                date_to_add = previous_row['Date'] + datetime.timedelta(hours = 1)
                while date_to_add < r['Date']:
                    new_row = dict(r) # clone it
                    new_row["Value"] = math.nan
                    new_row["Date"] = date_to_add
                    new_rows.append(new_row)
                    date_to_add += datetime.timedelta(hours = 1)

            new_rows.append(r)
            previous_row = r

        if (len(new_rows) > len(rows)):
            logging.info("Added {0} empty elements where there were gaps".format(len(new_rows) - len(rows)))

        return new_rows

    @staticmethod
    def _read_rows_from_csv_files(csv_files):
        rows = []

        for f in csv_files:
            rows += AqiDataSet._load_csv_skip_header(f)

        # Filter out the stuff we don't want
        total_count = len(rows)
        rows = [row for row in rows if row["Site"] == "Beijing" and row["Parameter"] == "PM2.5"]
        post_filter_count = len(rows)
        if (post_filter_count < total_count):
            logging.warning("Removed {0} rows that weren't Beijing / PM2.5".format(total_count - post_filter_count))

        # Sort by date and fill in gaps with invalid entries
        return AqiDataSet._sort_and_fill_gaps(rows)

    def __init__(self, csvPath, pattern="*.csv"):
        csv_files = AqiDataSet._files_matching(csvPath, pattern)
        if len(csv_files) == 0:
            raise BaseException("Couldn't find any files in '{0}' matching '{1}'".format(csvPath, pattern))

        logging.info("Preparing to parse %d AQI files" % len(csv_files))

        self.rows = [AqiDataPoint(r['Date'], r['Value']) for r in AqiDataSet._read_rows_from_csv_files(csv_files)]
        self.row_dates = [r.date for r in self.rows]

        logging.info("Loaded stateair.net AQI data with {0} rows".format(len(self.rows)))
        logging.info("    Start: {0}".format(self.rows[0].date))
        logging.info("    End:   {0}".format(self.rows[len(self.rows) - 1].date))

        self.missing_count = len([r for r in self.rows if (not r.isvalid())])
        logging.info("    Missing: {0} ({1}%)".format(self.missing_count, 100 * self.missing_count / len(self.rows)))

    def data_in_range(self, date_begin=None, date_end=None):
        """
        Given a date range (exclusive), returns all elements with dates greater than or equal to date_begin
        and less than date_end.  This function does not copy data, so it executes in O(1) time.
        :param date_begin:
        :param date_end:
        :return:
        """
        if date_begin is None:
            date_begin = self.rows[0].date

        if date_end is None:
            date_end = self.rows[-1].date + datetime.timedelta(hours=1)

        if type(date_begin) is datetime.date:
            date_begin = datetime.datetime.combine(date_begin, datetime.time())

        if type(date_end) is datetime.date:
            date_end = datetime.datetime.combine(date_end, datetime.time())

        return AqiDataRange(self, date_begin, date_end)


# Strongly coupled to AqiDataSet class
class AqiDataRange(collections.Sequence):

    def __init__(self, aqi_data, date_begin: datetime.datetime, date_end: datetime.datetime):
        self.aqi_data = aqi_data
        self.date_begin = date_begin
        self.date_end = date_end

        self.offset_into_data = int((self.date_begin - self.aqi_data.row_dates[0]).total_seconds()) // 3600
        self._count = max(0, int((self.date_end - self.date_begin).total_seconds()) // 3600)

    def __len__(self):
        return self._count

    # Optimized for the case where either the same key is being requested, or
    # the next key is being requested
    def __getitem__(self, key):
        import math

        if key < 0:
            key += self._count

        if key >= self._count:
            raise IndexError()

        index = key + self.offset_into_data
        if index < 0 or index >= len(self.aqi_data.row_dates):
            my_date = self.date_begin + datetime.timedelta(hours=key)
            return AqiDataPoint(my_date, math.nan)

        return self.aqi_data.rows[index]

    def valid_data_point_count(self):
        return len([dp for dp in self if dp.isvalid()])


class AqiDataPoint:
    def __init__(self, date, value, uncertainty=0):
        self.date = date
        self.value = value
        self.uncertainty = uncertainty

    def isvalid(self):
        import math
        try:
            return not math.isnan(self.value)
        except TypeError as e:
            print(self.value)
            raise Exception("Nope nope nope")


class UnitTests(unittest.TestCase):

    def test_data_load(self):
        import math

        data = AqiDataSet("unittest\\test-data", "test.csv")

        self.assertEqual(len(data.rows), 16, "row count")
        self.assertEqual(data.missing_count, 6, "missing_count")
        self.assertEqual(data.rows[0].date, datetime.datetime(2014, 3, 9, 0), "data[0].date")
        self.assertEqual(data.rows[-1].date, datetime.datetime(2014, 3, 9, 15), "data[0].date")

        self.assertEqual(data.rows[2].date.time().hour, 2, "dst corrected entry's time, in hours")
        self.assertEqual(data.rows[2].value, 112, "dst corrected entry's PM2.5")
        self.assertTrue(math.isnan(data.rows[10].value), "should be missing due to incorrect city")
        self.assertTrue(math.isnan(data.rows[11].value), "should be missing due to incorrect Parameter")
        self.assertTrue(math.isnan(data.rows[12].value), "should be missing due to incorrect unit")
        self.assertTrue(math.isnan(data.rows[13].value), "should be missing due to incorrect duration")
        self.assertTrue(math.isnan(data.rows[14].value), "should be missing since QC Name = Missing")

        pass

    def test_data_in_range(self):
        data = AqiDataSet("unittest\\test-data", "test.csv")

        my_range = data.data_in_range(datetime.date(2014, 2, 1), datetime.date(2014, 2, 4))
        self.assertEqual(len(my_range), 72, "empty set")
        self.assertEqual(my_range.valid_data_point_count(), 0, "empty set")

        my_range = data.data_in_range(datetime.date(2014, 4, 1), datetime.date(2014, 2, 4))
        self.assertEqual(len(my_range), 0, "empty set")
        self.assertEqual(my_range.valid_data_point_count(), 0, "empty set")

        my_range = data.data_in_range(datetime.date(2014, 4, 1), datetime.date(2014, 4, 4))
        self.assertEqual(len(my_range), 72, "empty set")
        self.assertEqual(my_range.valid_data_point_count(), 0, "empty set")
        self.assertTrue(not my_range[0].isvalid(), "none should be valid")
        self.assertTrue(not my_range[71].isvalid(), "none should be valid")
        self.assertEqual(my_range[71].date, datetime.datetime(2014, 4, 3, 23), "last item's date")

        my_range = data.data_in_range(datetime.datetime(2014, 3, 8, 23), datetime.datetime(2014, 3, 9, 8))
        self.assertEqual(len(my_range), 9, "partially overlapping set")
        self.assertEqual(my_range.valid_data_point_count(), 7, "missing some valid data points")
        self.assertEqual(my_range[1].value, 131, "first valid item's value")

        # Check behavior where start/end dates are implied
        my_range = data.data_in_range()
        self.assertEqual(len(my_range), 16)
        self.assertEqual(my_range[0].date, datetime.datetime(2014, 3, 9, 0), 15)
        self.assertEqual(my_range[15].date, datetime.datetime(2014, 3, 9, 15), 15)


    def test_single_data_point(self):

        data = AqiDataSet("unittest\\test-data", "test.csv")

        my_range = data.data_in_range(datetime.datetime(2014, 3, 9, 0), datetime.datetime(2014, 3, 9, 1))
        self.assertEqual(len(my_range), 1)
        self.assertEqual(my_range[0].value, 131)
