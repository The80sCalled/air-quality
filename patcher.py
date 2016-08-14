import unittest
import math
import stateair
import statistics

class AqiDataPatcher():
    # Sizes of gaps in data that should be predicted using linear interpolation
    LINEAR_INTERP_GAP_SIZES = list(range(1, 7))

    """
    This class can fill in missing AQI data by estimating what that data might be, together with the possible
    uncertainty in the estimated data.  For small bits of missing data, linear interpolation from the nearest
    existing data points is used.  For larger blocks, we use the bi-weekly and hourly means, together with
    the uncertainty in those means
    """
    def __init__(self, calibration):
        self.calibration = calibration

    @staticmethod
    def calibrate_on_data(aqi_data_set):
        my_range = aqi_data_set.data_in_range()

        deltas = [[], [], [], [], [], [], []]

        def _deltas_from_interp(values, x_start, x_end):
            steps = x_end - x_start
            return [values[x_start].value * (1 - i / steps) + values[x_end].value * (i / steps) - values[i + x_start].value for i in range(1, steps)]

        for x in range(0, len(my_range)):
            for gap_size in AqiDataPatcher.LINEAR_INTERP_GAP_SIZES:
                if x + gap_size + 1 < len(my_range):
                    my_deltas = _deltas_from_interp(my_range, x, x + gap_size + 1)
                    if not math.isnan(sum(my_deltas)):
                        deltas[gap_size - 1].append(my_deltas)

        calibration = {'fill-uncertainty': {}}

        for gap_size in AqiDataPatcher.LINEAR_INTERP_GAP_SIZES:
            my_deltas = deltas[gap_size - 1]
            means = [statistics.mean([delta_item[i] for delta_item in my_deltas]) for i in range(0, gap_size)]

            calibration['fill-uncertainty'][str(gap_size)] = list([
                statistics.stdev([delta_item[i] for delta_item in my_deltas], means[i]) for i in range(0, gap_size)
            ])

        return calibration


    def estimate_missing_data(self, aqi_data_set, max_distance=1):
        data_range = aqi_data_set.data_in_range()

        x = 0
        fill_count = 0
        # Advance to the first valid item
        while x < len(data_range) and not data_range[x].isvalid():
            x += 1

        while x < len(data_range):
            last_valid_x = x
            x += 1
            while x < len(data_range) and not data_range[x].isvalid():
                x += 1

            # Ran off the end of the array? Don't do any more filling
            if x == len(data_range):
                break

            gap_size = x - last_valid_x - 1
            if gap_size in AqiDataPatcher.LINEAR_INTERP_GAP_SIZES:
                uncertainties = self.calibration['fill-uncertainty'][str(gap_size)]
                for i in range(1, gap_size + 1):
                    data_range[last_valid_x + i].value = (
                        data_range[last_valid_x].value * (1 - i / (gap_size + 1)) + data_range[x].value * i / (gap_size + 1)
                    )
                    data_range[last_valid_x + i].uncertainty = uncertainties[i - 1]

            fill_count += gap_size

        return {'filled-items-count': fill_count}


class UnitTests(unittest.TestCase):

    def test_calibration(self):
        data = stateair.AqiDataSet("unittest\\test-data", "test2.csv")

        calibration = AqiDataPatcher.calibrate_on_data(data)

        self.assertAlmostEqual(33.543, calibration['fill-uncertainty']['1'][0], 3)

        self.assertAlmostEqual(39.888, calibration['fill-uncertainty']['2'][0], 3)
        self.assertAlmostEqual(38.411, calibration['fill-uncertainty']['2'][1], 3)

        self.assertAlmostEqual(39.084, calibration['fill-uncertainty']['3'][0], 3)
        self.assertAlmostEqual(41.120, calibration['fill-uncertainty']['3'][1], 3)
        self.assertAlmostEqual(36.160, calibration['fill-uncertainty']['3'][2], 3)



    def test_fill(self):
        data = stateair.AqiDataSet("unittest\\test-data", "test2.csv")

        calibration = AqiDataPatcher.calibrate_on_data(data)
        patcher = AqiDataPatcher(calibration)
        stats = patcher.estimate_missing_data(data, 1)
        self.assertEqual(6, stats['filled-items-count'])

        my_range = data.data_in_range()

        self.assertEqual(133, my_range[15].value)
        self.assertEqual(0, my_range[15].uncertainty)
        self.assertAlmostEqual(128.5, my_range[16].value)
        self.assertAlmostEqual(33.543, my_range[16].uncertainty, 3)

        self.assertAlmostEqual(115.333, my_range[18].value, 3)
        self.assertAlmostEqual(39.888, my_range[18].uncertainty, 3)
        self.assertAlmostEqual(106.667, my_range[19].value, 3)
        self.assertAlmostEqual(38.411, my_range[19].uncertainty, 3)

        self.assertAlmostEqual(83.5, my_range[21].value, 3)
        self.assertAlmostEqual(39.084, my_range[21].uncertainty, 3)
        self.assertAlmostEqual(69, my_range[22].value, 3)
        self.assertAlmostEqual(41.120, my_range[22].uncertainty, 3)
        self.assertAlmostEqual(54.5, my_range[23].value, 3)
        self.assertAlmostEqual(36.160, my_range[23].uncertainty, 3)
