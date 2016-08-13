import unittest
import math
import stateair
import statistics

class AqiDataPatcher():
    def __init__(self, calibration):
        self.calibration = calibration

    @staticmethod
    def calibrate_on_data(aqi_data_set):
        my_range = aqi_data_set.data_in_range()

        deltas = []

        for x in range(0, len(my_range) - 2):
            delta_from_interp = (my_range[x].value + my_range[x + 2].value) / 2 - my_range[x + 1].value
            if not math.isnan(delta_from_interp):
                deltas.append(delta_from_interp)

        mean = statistics.mean(deltas)

        return {
            'fill-uncertainty':
                {'1': statistics.stdev(deltas, mean)}
        }

    def estimate_missing_data(self, aqi_data_set, max_distance=1):
        data_range = aqi_data_set.data_in_range()

        x = 0
        fill_count = 0
        while x < len(data_range) - 2:
            if math.isnan(data_range[x + 1].value) and not math.isnan(data_range[x].value + data_range[x + 2].value):
                data_range[x + 1].value = (data_range[x].value + data_range[x + 2].value) / 2
                data_range[x + 1].uncertainty = self.calibration['fill-uncertainty']['1']
                x += 2
                fill_count += 1
            else:
                x += 1

        return {'filled-items-count': fill_count}


class UnitTests(unittest.TestCase):

    def test_calibration(self):
        data = stateair.AqiDataSet("unittest\\test-data", "test2.csv")

        calibration = AqiDataPatcher.calibrate_on_data(data)

        self.assertAlmostEqual(33.543, calibration['fill-uncertainty']['1'], 3)
        # self.assertAlmostEqual(.4, calibration['fill-uncertainty']['2'], 3)
        # self.assertAlmostEqual(.4, calibration['fill-uncertainty']['3'], 3)


    def test_fill(self):
        data = stateair.AqiDataSet("unittest\\test-data", "test2.csv")

        calibration = AqiDataPatcher.calibrate_on_data(data)
        patcher = AqiDataPatcher(calibration)
        stats = patcher.estimate_missing_data(data, 1)
        self.assertEqual(1, stats['filled-items-count'])

        my_range = data.data_in_range()

        self.assertEqual(133, my_range[15].value)
        self.assertEqual(0, my_range[15].uncertainty)
        self.assertAlmostEqual(128.5, my_range[16].value)
        self.assertAlmostEqual(33.543, my_range[16].uncertainty, 3)
        # self.assertAlmostEqual(.4, calibration['fill-uncertainty']['2'], 3)
        # self.assertAlmostEqual(.4, calibration['fill-uncertainty']['3'], 3)


