import logging
import os
import io
import datetime
import unittest

class DataSet:

    # This is useful when correlating data with real world system times, which we never do.  Can add it later.
    #TIME_ZONE = datetime.timezone(datetime.timedelta(hours = 8))

    @staticmethod
    def _files_matching(path, pattern):
        import fnmatch

        full_names = [os.path.join(path, f) for f in os.listdir(path)]
        return [f for f in full_names
                if os.path.isfile(f) and
                fnmatch.fnmatch(f, pattern)]

    @staticmethod
    def _load_csv_skip_header(filename):
        """
        Loads a CSV file by skipping all lines before the list of fields in the CSV file.  Assumes
        there's at least two fields in the CSV file.
        :return:
        """
        import itertools
        import csv

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

            return list([r for r in [DataSet._standardize_row_format(row) for row in csv.DictReader(file_without_header)]
                        if r is not None])

    @staticmethod
    def _standardize_row_format(row):
        row["Date"] = datetime.datetime(int(row["Year"]), int(row["Month"]), int(row["Day"]), int(row["Hour"]))

        if row["QC Name"] != "Valid" or float(row["Value"]) < 0:
            row["Value"] = None
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
        import bisect

        row_dates = [row['Date'] for row in rows]

        # Find up to one duplicate at 3am in the month of March; any others will be flagged.
        for year in range(row_dates[0].date().year, row_dates[-1:][0].date().year + 1):
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
        rows.sort(key=lambda row: row["Date"])
        DataSet._fix_dst_duplicates(rows)

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
                    new_row["Value"] = None
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
            rows += DataSet._load_csv_skip_header(f)

        # Filter out the stuff we don't want
        total_count = len(rows)
        rows = [row for row in rows if row["Site"] == "Beijing" and row["Parameter"] == "PM2.5"]
        post_filter_count = len(rows)
        if (post_filter_count < total_count):
            logging.warning("Removed {0} rows that weren't Beijing / PM2.5".format(total_count - post_filter_count))

        # Sort by date and fill in gaps with None
        return DataSet._sort_and_fill_gaps(rows)

    def __init__(self, csvPath):
        csv_files = DataSet._files_matching(csvPath, "*.csv")
        if len(csv_files) == 0:
            raise BaseException("Couldn't find any .csv files in '{0}'".format(csvPath))

        logging.info("Preparing to parse %d AQI files" % len(csv_files))

        self.rows = DataSet._read_rows_from_csv_files(csv_files)

        logging.info("Loaded stateair.net AQI data with {0} rows".format(len(self.rows)))
        logging.info("    Start: {0}".format(self.rows[0]['Date']))
        logging.info("    End:   {0}".format(self.rows[len(self.rows) - 1]['Date']))

        self.missing_count = len([r for r in self.rows if r["Value"] is None])
        logging.info("    Missing: {0} ({1}%)".format(self.missing_count, 100 * self.missing_count / len(self.rows)))


class UnitTests(unittest.TestCase):

    def test_data_load(self):

        data = DataSet("unittest\\test-data")


        self.assertEqual(len(data.rows), 16, "row count")
        self.assertEqual(data.missing_count, 6, "missing_count")
        self.assertEqual(data.rows[0]['Date'], datetime.datetime(2014, 3, 9, 0), "data[0].date")
        self.assertEqual(data.rows[-1:][0]['Date'], datetime.datetime(2014, 3, 9, 15), "data[0].date")

        self.assertEqual(data.rows[2]['Date'].time().hour, 2, "dst corrected entry's time, in hours")
        self.assertEqual(data.rows[2]['Value'], 112, "dst corrected entry's PM2.5")
        self.assertEqual(data.rows[10]['Value'], None, "should be missing due to incorrect city")
        self.assertEqual(data.rows[11]['Value'], None, "should be missing due to incorrect Parameter")
        self.assertEqual(data.rows[12]['Value'], None, "should be missing due to incorrect unit")
        self.assertEqual(data.rows[13]['Value'], None, "should be missing due to incorrect duration")
        self.assertEqual(data.rows[14]['Value'], None, "should be missing since QC Name = Missing")

        pass
