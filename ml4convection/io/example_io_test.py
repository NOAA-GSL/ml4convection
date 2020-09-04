"""Unit tests for example_io.py."""

import copy
import unittest
import numpy
from ml4convection.io import radar_io
from ml4convection.io import radar_io_test
from ml4convection.io import satellite_io
from ml4convection.io import satellite_io_test
from ml4convection.io import example_io

# The following constants are used to test _downsample_data_in_space.
TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS = numpy.array([
    [200, 210, 220, 230],
    [210, 220, 230, 240],
    [220, 230, 240, 250],
    [230, 240, 250, 260],
    [250, 260, 270, 280],
    [290, 300, 310, 320]
], dtype=float)

TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS = TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS - 10.
TEMP_MATRIX_EXAMPLE1_KELVINS = numpy.stack(
    (TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS, TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS),
    axis=-1
)
TEMPERATURE_MATRIX_KELVINS = numpy.stack((
    TEMP_MATRIX_EXAMPLE1_KELVINS, TEMP_MATRIX_EXAMPLE1_KELVINS + 2.5,
    TEMP_MATRIX_EXAMPLE1_KELVINS + 5, TEMP_MATRIX_EXAMPLE1_KELVINS + 7.5
))

LATITUDES_DEG_N = numpy.array([53, 53.2, 53.4, 53.6, 53.8, 54])
LONGITUDES_DEG_E = numpy.array([246, 246.5, 247, 247.5])
VALID_TIMES_UNIX_SEC = numpy.linspace(0, 3, num=4, dtype=int)
BAND_NUMBERS = numpy.array([8, 9], dtype=int)

SATELLITE_DICT = {
    satellite_io.BRIGHTNESS_TEMP_KEY: TEMPERATURE_MATRIX_KELVINS + 0.,
    satellite_io.BRIGHTNESS_COUNT_KEY: None,
    satellite_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    satellite_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.,
    satellite_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    satellite_io.BAND_NUMBERS_KEY: BAND_NUMBERS + 0
}

REFL_MATRIX_EXAMPLE1_DBZ = numpy.array([
    [10, 20, 30, 40],
    [20, 30, 40, 50],
    [30, 40, 50, 60],
    [40, 50, 60, 70],
    [50, 60, 70, 80],
    [60, 40, 20, 0]
], dtype=float)

COMPOSITE_REFL_MATRIX_DBZ = numpy.stack((
    REFL_MATRIX_EXAMPLE1_DBZ, REFL_MATRIX_EXAMPLE1_DBZ + 1,
    REFL_MATRIX_EXAMPLE1_DBZ + 2, REFL_MATRIX_EXAMPLE1_DBZ + 3
), axis=0)

RADAR_DICT = {
    radar_io.COMPOSITE_REFL_KEY: COMPOSITE_REFL_MATRIX_DBZ + 0.,
    radar_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    radar_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    radar_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.
}

TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS = numpy.array([
    [210, 230],
    [230, 250],
    [275, 295]
], dtype=float)

TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS = TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS - 10.
TEMP_MATRIX_EXAMPLE1_KELVINS = numpy.stack(
    (TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS, TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS),
    axis=-1
)
TEMPERATURE_MATRIX_KELVINS = numpy.stack((
    TEMP_MATRIX_EXAMPLE1_KELVINS, TEMP_MATRIX_EXAMPLE1_KELVINS + 2.5,
    TEMP_MATRIX_EXAMPLE1_KELVINS + 5, TEMP_MATRIX_EXAMPLE1_KELVINS + 7.5
))

LATITUDES_DEG_N = numpy.array([53.1, 53.5, 53.9])
LONGITUDES_DEG_E = numpy.array([246.25, 247.25])

SATELLITE_DICT_DOWNSAMPLED2 = {
    satellite_io.BRIGHTNESS_TEMP_KEY: TEMPERATURE_MATRIX_KELVINS + 0.,
    satellite_io.BRIGHTNESS_COUNT_KEY: None,
    satellite_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    satellite_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.,
    satellite_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    satellite_io.BAND_NUMBERS_KEY: BAND_NUMBERS + 0
}

REFL_MATRIX_EXAMPLE1_DBZ = numpy.array([
    [30, 50],
    [50, 70],
    [60, 80]
], dtype=float)

COMPOSITE_REFL_MATRIX_DBZ = numpy.stack((
    REFL_MATRIX_EXAMPLE1_DBZ, REFL_MATRIX_EXAMPLE1_DBZ + 1,
    REFL_MATRIX_EXAMPLE1_DBZ + 2, REFL_MATRIX_EXAMPLE1_DBZ + 3
), axis=0)

RADAR_DICT_DOWNSAMPLED2 = {
    radar_io.COMPOSITE_REFL_KEY: COMPOSITE_REFL_MATRIX_DBZ + 0.,
    radar_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    radar_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    radar_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.
}

TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS = numpy.array([[230]], dtype=float)
TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS = TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS - 10.
TEMP_MATRIX_EXAMPLE1_KELVINS = numpy.stack(
    (TEMP_MATRIX_BAND8_EXAMPLE1_KELVINS, TEMP_MATRIX_BAND9_EXAMPLE1_KELVINS),
    axis=-1
)
TEMPERATURE_MATRIX_KELVINS = numpy.stack((
    TEMP_MATRIX_EXAMPLE1_KELVINS, TEMP_MATRIX_EXAMPLE1_KELVINS + 2.5,
    TEMP_MATRIX_EXAMPLE1_KELVINS + 5, TEMP_MATRIX_EXAMPLE1_KELVINS + 7.5
))

LATITUDES_DEG_N = numpy.array([53.3])
LONGITUDES_DEG_E = numpy.array([246.75])

SATELLITE_DICT_DOWNSAMPLED4 = {
    satellite_io.BRIGHTNESS_TEMP_KEY: TEMPERATURE_MATRIX_KELVINS + 0.,
    satellite_io.BRIGHTNESS_COUNT_KEY: None,
    satellite_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    satellite_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.,
    satellite_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    satellite_io.BAND_NUMBERS_KEY: BAND_NUMBERS + 0
}

REFL_MATRIX_EXAMPLE1_DBZ = numpy.array([
    [70]
], dtype=float)

COMPOSITE_REFL_MATRIX_DBZ = numpy.stack((
    REFL_MATRIX_EXAMPLE1_DBZ, REFL_MATRIX_EXAMPLE1_DBZ + 1,
    REFL_MATRIX_EXAMPLE1_DBZ + 2, REFL_MATRIX_EXAMPLE1_DBZ + 3
), axis=0)

RADAR_DICT_DOWNSAMPLED4 = {
    radar_io.COMPOSITE_REFL_KEY: COMPOSITE_REFL_MATRIX_DBZ + 0.,
    radar_io.VALID_TIMES_KEY: VALID_TIMES_UNIX_SEC + 0,
    radar_io.LATITUDES_KEY: LATITUDES_DEG_N + 0.,
    radar_io.LONGITUDES_KEY: LONGITUDES_DEG_E + 0.
}

# The following constants are used to test find_predictor_file and
# find_target_file.
TOP_PREDICTOR_DIR_NAME = 'predictors'
PREDICTOR_DATE_STRING = '20200820'
PREDICTOR_FILE_NAME = 'predictors/2020/predictors_20200820.nc'

TOP_TARGET_DIR_NAME = 'targets'
TARGET_DATE_STRING = '40550405'
TARGET_FILE_NAME = 'targets/4055/targets_40550405.nc'


class ExampleIoTests(unittest.TestCase):
    """Each method is a unit test for example_io.py."""

    def test_downsample_data_in_space_factor2(self):
        """Ensures correct output from _downsample_data_in_space.

        In this case, downsampling factor is 2.
        """

        this_satellite_dict, this_radar_dict = (
            example_io.downsample_data_in_space(
                satellite_dict=copy.deepcopy(SATELLITE_DICT),
                radar_dict=copy.deepcopy(RADAR_DICT),
                downsampling_factor=2, change_coordinates=True
            )
        )

        self.assertTrue(satellite_io_test.compare_satellite_dicts(
            this_satellite_dict, SATELLITE_DICT_DOWNSAMPLED2
        ))
        self.assertTrue(radar_io_test.compare_radar_dicts(
            this_radar_dict, RADAR_DICT_DOWNSAMPLED2
        ))

    def test_downsample_data_in_space_factor4(self):
        """Ensures correct output from _downsample_data_in_space.

        In this case, downsampling factor is 4.
        """

        this_satellite_dict, this_radar_dict = (
            example_io.downsample_data_in_space(
                satellite_dict=copy.deepcopy(SATELLITE_DICT),
                radar_dict=copy.deepcopy(RADAR_DICT),
                downsampling_factor=4, change_coordinates=True
            )
        )

        self.assertTrue(satellite_io_test.compare_satellite_dicts(
            this_satellite_dict, SATELLITE_DICT_DOWNSAMPLED4
        ))
        self.assertTrue(radar_io_test.compare_radar_dicts(
            this_radar_dict, RADAR_DICT_DOWNSAMPLED4
        ))

    def test_find_predictor_file(self):
        """Ensures correct output from find_predictor_file."""

        this_file_name = example_io.find_predictor_file(
            top_directory_name=TOP_PREDICTOR_DIR_NAME,
            date_string=PREDICTOR_DATE_STRING, raise_error_if_missing=False
        )

        self.assertTrue(this_file_name == PREDICTOR_FILE_NAME)

    def test_find_target_file(self):
        """Ensures correct output from find_target_file."""

        this_file_name = example_io.find_target_file(
            top_directory_name=TOP_TARGET_DIR_NAME,
            date_string=TARGET_DATE_STRING, raise_error_if_missing=False
        )

        self.assertTrue(this_file_name == TARGET_FILE_NAME)


if __name__ == '__main__':
    unittest.main()
