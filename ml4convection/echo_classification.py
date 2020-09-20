"""Classification of radar echoes (e.g., convective vs. stratiform).

--- NOTATION ---

The following letters will be used throughout this module.

M = number of rows (unique grid-point latitudes)
N = number of columns (unique grid-point longitudes)
H = number of depths (unique grid-point heights)
"""

import os
import sys
import numpy
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage.filters import median_filter, convolve

THIS_DIRECTORY_NAME = os.path.dirname(os.path.realpath(
    os.path.join(os.getcwd(), os.path.expanduser(__file__))
))
sys.path.append(os.path.normpath(os.path.join(THIS_DIRECTORY_NAME, '..')))

import grids
import time_conversion
import error_checking

TOLERANCE = 1e-6
TIME_FORMAT = '%Y-%m-%d-%H%M%S'
DEGREES_LAT_TO_METRES = 60 * 1852.

MIN_LATITUDE_KEY = 'min_grid_point_latitude_deg'
LATITUDE_SPACING_KEY = 'latitude_spacing_deg'
MIN_LONGITUDE_KEY = 'min_grid_point_longitude_deg'
LONGITUDE_SPACING_KEY = 'longitude_spacing_deg'
MIN_HEIGHT_KEY = 'min_grid_point_height_m_asl'
HEIGHT_SPACING_KEY = 'height_spacing_metres'

LATITUDES_KEY = 'grid_point_latitudes_deg'
LONGITUDES_KEY = 'grid_point_longitudes_deg'
HEIGHTS_KEY = 'grid_point_heights_m_asl'

MELT_LEVEL_INTERCEPT_BY_MONTH_M_ASL = numpy.array(
    [7072, 7896, 8558, 7988, 7464, 6728, 6080, 6270, 6786, 8670, 8892, 7936],
    dtype=float
)
MELT_LEVEL_SLOPE_BY_MONTH_M_DEG01 = numpy.array(
    [-124, -152, -160, -128, -100, -65, -39, -44, -67, -137, -160, -147],
    dtype=float
)

PEAKEDNESS_NEIGH_KEY = 'peakedness_neigh_metres'
MAX_PEAKEDNESS_HEIGHT_KEY = 'max_peakedness_height_m_asl'
HALVE_RESOLUTION_KEY = 'halve_resolution_for_peakedness'
MIN_ECHO_TOP_KEY = 'min_echo_top_m_asl'
ECHO_TOP_LEVEL_KEY = 'echo_top_level_dbz'
MIN_COMPOSITE_REFL_CRITERION1_KEY = 'min_composite_refl_criterion1_dbz'
MIN_COMPOSITE_REFL_CRITERION5_KEY = 'min_composite_refl_criterion5_dbz'
MIN_COMPOSITE_REFL_AML_KEY = 'min_composite_refl_aml_dbz'

DEFAULT_OPTION_DICT = {
    PEAKEDNESS_NEIGH_KEY: 12000.,
    MAX_PEAKEDNESS_HEIGHT_KEY: 9000.,
    HALVE_RESOLUTION_KEY: False,
    MIN_ECHO_TOP_KEY: 10000.,
    ECHO_TOP_LEVEL_KEY: 25.,
    MIN_COMPOSITE_REFL_CRITERION1_KEY: 25.,
    MIN_COMPOSITE_REFL_CRITERION5_KEY: 25.,
    MIN_COMPOSITE_REFL_AML_KEY: 45.
}

VALID_TIME_KEY = 'valid_time_unix_sec'

ROW_DIMENSION_KEY = 'grid_row'
COLUMN_DIMENSION_KEY = 'grid_column'
FLAG_MATRIX_KEY = 'convective_flag_matrix'


def _check_input_args(option_dict):
    """Error-checks input arguments.

    :param option_dict: See doc for `find_convective_pixels`.
    :return: option_dict: Same as input, except that defaults might have been
        added.
    """

    if option_dict is None:
        orig_option_dict = {}
    else:
        orig_option_dict = option_dict.copy()

    option_dict = DEFAULT_OPTION_DICT.copy()
    option_dict.update(orig_option_dict)

    option_dict[PEAKEDNESS_NEIGH_KEY] = float(option_dict[PEAKEDNESS_NEIGH_KEY])
    option_dict[MAX_PEAKEDNESS_HEIGHT_KEY] = float(
        option_dict[MAX_PEAKEDNESS_HEIGHT_KEY])
    option_dict[MIN_ECHO_TOP_KEY] = int(numpy.round(
        option_dict[MIN_ECHO_TOP_KEY]))
    option_dict[ECHO_TOP_LEVEL_KEY] = float(option_dict[ECHO_TOP_LEVEL_KEY])
    option_dict[MIN_COMPOSITE_REFL_CRITERION5_KEY] = float(
        option_dict[MIN_COMPOSITE_REFL_CRITERION5_KEY])
    option_dict[MIN_COMPOSITE_REFL_AML_KEY] = float(
        option_dict[MIN_COMPOSITE_REFL_AML_KEY])

    error_checking.assert_is_greater(option_dict[PEAKEDNESS_NEIGH_KEY], 0.)
    error_checking.assert_is_greater(option_dict[MAX_PEAKEDNESS_HEIGHT_KEY], 0.)
    error_checking.assert_is_boolean(option_dict[HALVE_RESOLUTION_KEY])
    error_checking.assert_is_greater(option_dict[MIN_ECHO_TOP_KEY], 0)
    error_checking.assert_is_greater(option_dict[ECHO_TOP_LEVEL_KEY], 0.)
    error_checking.assert_is_greater(
        option_dict[MIN_COMPOSITE_REFL_CRITERION5_KEY], 0.)
    error_checking.assert_is_greater(
        option_dict[MIN_COMPOSITE_REFL_AML_KEY], 0.)

    if option_dict[MIN_COMPOSITE_REFL_CRITERION1_KEY] is not None:
        option_dict[MIN_COMPOSITE_REFL_CRITERION1_KEY] = float(
            option_dict[MIN_COMPOSITE_REFL_CRITERION1_KEY])
        error_checking.assert_is_greater(
            option_dict[MIN_COMPOSITE_REFL_CRITERION1_KEY], 0.)

    return option_dict


def _estimate_melting_levels(latitudes_deg, valid_time_unix_sec):
    """Estimates melting level at each point.

    This estimate is based on linear regression with respect to latitude.  There
    is one set of regression coefficients for each month.

    :param latitudes_deg: numpy array of latitudes (deg N).
    :param valid_time_unix_sec: Valid time.
    :return: melting_levels_m_asl: numpy array of melting levels (metres above
        sea level), with same shape as `latitudes_deg`.
    """

    month_index = int(
        time_conversion.unix_sec_to_string(valid_time_unix_sec, '%m'))

    return (
        MELT_LEVEL_INTERCEPT_BY_MONTH_M_ASL[month_index - 1] +
        MELT_LEVEL_SLOPE_BY_MONTH_M_DEG01[month_index - 1] *
        numpy.absolute(latitudes_deg)
    )


def _neigh_metres_to_rowcol(neigh_radius_metres, grid_metadata_dict):
    """Converts neighbourhood radius from metres to num rows/columns.

    :param neigh_radius_metres: Neighbourhood radius.
    :param grid_metadata_dict: See doc for `_apply_convective_criterion1`.
    :return: num_rows: Number of rows in neighbourhood.
    :return: num_columns: Number of columns in neighbourhood.
    """

    y_spacing_metres = (
        grid_metadata_dict[LATITUDE_SPACING_KEY] * DEGREES_LAT_TO_METRES)
    num_rows = 1 + 2 * int(numpy.ceil(neigh_radius_metres / y_spacing_metres))

    mean_latitude_deg = (
        numpy.max(grid_metadata_dict[LATITUDES_KEY]) -
        numpy.min(grid_metadata_dict[LATITUDES_KEY])
    ) / 2
    mean_x_spacing_metres = (
        grid_metadata_dict[LONGITUDE_SPACING_KEY] *
        DEGREES_LAT_TO_METRES * numpy.cos(numpy.deg2rad(mean_latitude_deg))
    )
    num_columns = 1 + 2 * int(
        numpy.ceil(neigh_radius_metres / mean_x_spacing_metres)
    )

    return num_rows, num_columns


def _get_peakedness(
        reflectivity_matrix_dbz, num_rows_in_neigh, num_columns_in_neigh):
    """Computes peakedness at each voxel (3-D grid point).

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :param num_rows_in_neigh: Number of rows in neighbourhood for median filter.
    :param num_columns_in_neigh: Number of columns in neighbourhood for median
        filter.
    :return: peakedness_matrix_dbz: numpy array of peakedness values, with same
        shape as `reflectivity_matrix_dbz`.
    """

    num_heights = reflectivity_matrix_dbz.shape[-1]
    peakedness_matrix_dbz = numpy.full(reflectivity_matrix_dbz.shape, numpy.nan)

    for k in range(num_heights):
        print(k)
        this_filtered_matrix_dbz = median_filter(
            reflectivity_matrix_dbz[..., k],
            size=(num_rows_in_neigh, num_columns_in_neigh),
            mode='constant', cval=0.)

        peakedness_matrix_dbz[..., k] = (
            reflectivity_matrix_dbz[..., k] - this_filtered_matrix_dbz
        )

    return peakedness_matrix_dbz


def _get_peakedness_thresholds(reflectivity_matrix_dbz):
    """Computes peakedness threshold at each voxel (3-D grid point).

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :return: peakedness_threshold_matrix_dbz: numpy array of thresholds, with
        same shape as `reflectivity_matrix_dbz`.
    """

    this_matrix = 10. - (reflectivity_matrix_dbz ** 2) / 337.5
    this_matrix[this_matrix < 4.] = 4.
    return this_matrix


def _halve_refl_resolution(
        fine_reflectivity_matrix_dbz, fine_grid_point_latitudes_deg,
        fine_grid_point_longitudes_deg):
    """Halves horizontal resolution of reflectivity grid.

    M = number of rows in fine-scale grid
    N = number of columns in fine-scale grid
    m = number of rows in coarse grid
    n = number of rows in coarse grid

    :param fine_reflectivity_matrix_dbz: M-by-N-by-H numpy array of reflectivity
        values, with latitude increasing along the first axis and longitude
        increasing along the second axis.
    :param fine_grid_point_latitudes_deg: length-M numpy array of latitudes
        (deg N), in increasing order.
    :param fine_grid_point_longitudes_deg: length-N numpy array of longitudes
        (deg E), in increasing order.

    :return: coarse_reflectivity_matrix_dbz: Same as input, except dimensions
        are m x n x H.
    :return: coarse_grid_point_latitudes_deg: Same as input, except length is m.
    :return: coarse_grid_point_longitudes_deg: Same as input, except length is
        n.
    """

    coarse_grid_point_latitudes_deg = fine_grid_point_latitudes_deg[::2]
    coarse_grid_point_longitudes_deg = fine_grid_point_longitudes_deg[::2]

    num_coarse_latitudes = len(coarse_grid_point_latitudes_deg)
    num_coarse_longitudes = len(coarse_grid_point_longitudes_deg)
    num_heights = fine_reflectivity_matrix_dbz.shape[-1]
    coarse_reflectivity_matrix_dbz = numpy.full(
        (num_coarse_latitudes, num_coarse_longitudes, num_heights), numpy.nan)

    for k in range(num_heights):
        this_interp_object = RectBivariateSpline(
            fine_grid_point_latitudes_deg, fine_grid_point_longitudes_deg,
            fine_reflectivity_matrix_dbz[..., k], kx=1, ky=1, s=0)
        coarse_reflectivity_matrix_dbz[..., k] = this_interp_object(
            coarse_grid_point_latitudes_deg, coarse_grid_point_longitudes_deg,
            grid=True)

    return (coarse_reflectivity_matrix_dbz, coarse_grid_point_latitudes_deg,
            coarse_grid_point_longitudes_deg)


def _double_class_resolution(
        coarse_convective_flag_matrix, coarse_grid_point_latitudes_deg,
        coarse_grid_point_longitudes_deg, fine_grid_point_latitudes_deg,
        fine_grid_point_longitudes_deg):
    """Doubles resolution of 2-D echo-classification grid.

    M = number of rows in fine-scale grid
    N = number of columns in fine-scale grid
    m = number of rows in coarse grid
    n = number of rows in coarse grid

    :param coarse_convective_flag_matrix: m-by-n numpy array of Boolean flags
        (True if convective, False if not).
    :param coarse_grid_point_latitudes_deg: See doc for
        `_halve_refl_resolution`.
    :param coarse_grid_point_longitudes_deg: Same.
    :param fine_grid_point_latitudes_deg: Same.
    :param fine_grid_point_longitudes_deg: Same.
    :return: fine_convective_flag_matrix: Same as input, except dimensions are
        M x N.
    """

    interp_object = RectBivariateSpline(
        coarse_grid_point_latitudes_deg, coarse_grid_point_longitudes_deg,
        coarse_convective_flag_matrix.astype(float), kx=1, ky=1, s=0)

    fine_convective_flag_matrix = interp_object(
        fine_grid_point_latitudes_deg, fine_grid_point_longitudes_deg,
        grid=True)

    return numpy.round(fine_convective_flag_matrix).astype(bool)


def _apply_convective_criterion1(
        reflectivity_matrix_dbz, peakedness_neigh_metres,
        max_peakedness_height_m_asl, halve_resolution_for_peakedness,
        min_composite_refl_dbz, grid_metadata_dict):
    """Applies criterion 1 for convective classification.

    Criterion 1 states: the pixel is convective if >= 50% of values in the
    column exceed the peakedness threshold AND composite reflectivity >=
    threshold.

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :param peakedness_neigh_metres: Same.
    :param max_peakedness_height_m_asl: Same.
    :param halve_resolution_for_peakedness: Same.
    :param min_composite_refl_dbz: Same.  Keep in mind that this may be None.
    :param grid_metadata_dict: Dictionary with keys listed in doc for
        `find_convective_pixels`, plus the following extras.
    grid_metadata_dict['grid_point_latitudes_deg']: length-M numpy array of
        latitudes (deg N) at grid points.
    grid_metadata_dict['grid_point_longitudes_deg']: length-N numpy array of
        longitudes (deg E) at grid points.

    :return: convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    """

    aloft_indices = numpy.where(
        grid_metadata_dict[HEIGHTS_KEY] >= max_peakedness_height_m_asl
    )[0]

    if len(aloft_indices) == 0:
        max_height_index = len(grid_metadata_dict[HEIGHTS_KEY]) - 1
    else:
        max_height_index = aloft_indices[0]

    if halve_resolution_for_peakedness:
        (coarse_reflectivity_matrix_dbz, coarse_grid_point_latitudes_deg,
         coarse_grid_point_longitudes_deg
        ) = _halve_refl_resolution(
            fine_reflectivity_matrix_dbz=reflectivity_matrix_dbz,
            fine_grid_point_latitudes_deg=grid_metadata_dict[LATITUDES_KEY],
            fine_grid_point_longitudes_deg=grid_metadata_dict[LONGITUDES_KEY])

        coarse_grid_metadata_dict = {
            MIN_LATITUDE_KEY: numpy.min(coarse_grid_point_latitudes_deg),
            LATITUDE_SPACING_KEY: (coarse_grid_point_latitudes_deg[1] -
                                   coarse_grid_point_latitudes_deg[0]),
            LATITUDES_KEY: coarse_grid_point_latitudes_deg,
            MIN_LONGITUDE_KEY: numpy.min(coarse_grid_point_longitudes_deg),
            LONGITUDE_SPACING_KEY: (coarse_grid_point_longitudes_deg[1] -
                                    coarse_grid_point_longitudes_deg[0]),
            LONGITUDES_KEY: coarse_grid_point_longitudes_deg
        }

        this_reflectivity_matrix_dbz = coarse_reflectivity_matrix_dbz[
            ..., :(max_height_index + 1)]

        num_rows_in_neigh, num_columns_in_neigh = _neigh_metres_to_rowcol(
            neigh_radius_metres=peakedness_neigh_metres,
            grid_metadata_dict=coarse_grid_metadata_dict)
    else:
        this_reflectivity_matrix_dbz = reflectivity_matrix_dbz[
            ..., :(max_height_index + 1)]

        num_rows_in_neigh, num_columns_in_neigh = _neigh_metres_to_rowcol(
            neigh_radius_metres=peakedness_neigh_metres,
            grid_metadata_dict=grid_metadata_dict)

    peakedness_matrix_dbz = _get_peakedness(
        reflectivity_matrix_dbz=this_reflectivity_matrix_dbz,
        num_rows_in_neigh=num_rows_in_neigh,
        num_columns_in_neigh=num_columns_in_neigh)

    peakedness_threshold_matrix_dbz = _get_peakedness_thresholds(
        this_reflectivity_matrix_dbz)

    numerator = numpy.sum(
        (peakedness_matrix_dbz > peakedness_threshold_matrix_dbz).astype(int),
        axis=-1
    )
    denominator = numpy.sum(
        (this_reflectivity_matrix_dbz > 0).astype(int),
        axis=-1
    )

    fractional_exceedance_matrix = numerator.astype(float) / denominator
    convective_flag_matrix = (fractional_exceedance_matrix >= 0.5).astype(bool)

    if halve_resolution_for_peakedness:
        convective_flag_matrix = _double_class_resolution(
            coarse_convective_flag_matrix=convective_flag_matrix,
            coarse_grid_point_latitudes_deg=coarse_grid_point_latitudes_deg,
            coarse_grid_point_longitudes_deg=coarse_grid_point_longitudes_deg,
            fine_grid_point_latitudes_deg=grid_metadata_dict[LATITUDES_KEY],
            fine_grid_point_longitudes_deg=grid_metadata_dict[LONGITUDES_KEY]
        )

    if min_composite_refl_dbz is None:
        return convective_flag_matrix

    composite_refl_matrix_dbz = numpy.max(reflectivity_matrix_dbz, axis=-1)
    return numpy.logical_and(
        convective_flag_matrix,
        (composite_refl_matrix_dbz >= min_composite_refl_dbz).astype(bool)
    )


def _apply_convective_criterion2(
        reflectivity_matrix_dbz, convective_flag_matrix, grid_metadata_dict,
        valid_time_unix_sec, min_composite_refl_aml_dbz):
    """Applies criterion 2 for convective classification.

    Criterion 2 states: the pixel is convective if already marked convective OR
    composite reflectivity above melting level >= threshold.

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :param convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    :param grid_metadata_dict: See doc for `_apply_convective_criterion1`.
    :param valid_time_unix_sec: See doc for `find_convective_pixels`.
    :param min_composite_refl_aml_dbz: Same.
    :return: convective_flag_matrix: Updated version of input.
    """

    _, latitude_matrix_deg, height_matrix_m_asl = numpy.meshgrid(
        grid_metadata_dict[LONGITUDES_KEY], grid_metadata_dict[LATITUDES_KEY],
        grid_metadata_dict[HEIGHTS_KEY])

    melting_level_matrix_m_asl = _estimate_melting_levels(
        latitudes_deg=latitude_matrix_deg,
        valid_time_unix_sec=valid_time_unix_sec)

    composite_refl_matrix_aml_dbz = numpy.max(
        (height_matrix_m_asl >= melting_level_matrix_m_asl + 1000).astype(int) *
        reflectivity_matrix_dbz,
        axis=-1)

    return numpy.logical_or(
        convective_flag_matrix,
        (composite_refl_matrix_aml_dbz >= min_composite_refl_aml_dbz).astype(
            bool
        )
    )


def _apply_convective_criterion3(
        reflectivity_matrix_dbz, convective_flag_matrix, grid_metadata_dict,
        min_echo_top_m_asl, echo_top_level_dbz):
    """Applies criterion 3 for convective classification.

    Criterion 3 states: the pixel is convective if already marked convective OR
    echo top >= threshold.

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :param convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    :param grid_metadata_dict: See doc for `_apply_convective_criterion1`.
    :param min_echo_top_m_asl:  See doc for `find_convective_pixels`.
    :param echo_top_level_dbz: Same.
    :return: convective_flag_matrix: Updated version of input.
    """

    _, _, height_matrix_m_asl = numpy.meshgrid(
        grid_metadata_dict[LONGITUDES_KEY], grid_metadata_dict[LATITUDES_KEY],
        grid_metadata_dict[HEIGHTS_KEY])

    echo_top_matrix_m_asl = numpy.max(
        (reflectivity_matrix_dbz >= echo_top_level_dbz).astype(int) *
        height_matrix_m_asl,
        axis=-1)

    return numpy.logical_or(
        convective_flag_matrix,
        (echo_top_matrix_m_asl >= min_echo_top_m_asl).astype(bool)
    )


def _apply_convective_criterion4(convective_flag_matrix):
    """Applies criterion 4 for convective classification.

    Criterion 4 states: if pixel (i, j) is marked convective but none of its
    neighbours are marked convective, (i, j) is not actually convective.

    :param convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    :return: convective_flag_matrix: Updated version of input.
    """

    weight_matrix = numpy.full((3, 3), 1.)
    weight_matrix = weight_matrix / weight_matrix.size

    average_matrix = convolve(
        convective_flag_matrix.astype(float), weights=weight_matrix,
        mode='constant', cval=0.
    )

    return numpy.logical_and(
        convective_flag_matrix,
        (average_matrix > weight_matrix[0, 0] + TOLERANCE).astype(bool)
    )


def _apply_convective_criterion5(
        reflectivity_matrix_dbz, convective_flag_matrix,
        min_composite_refl_dbz):
    """Applies criterion 5 for convective classification.

    Criterion 5 states: if pixel (i, j) neighbours a pixel marked convective and
    has composite reflectivity >= threshold, pixel (i, j) is convective as well.

    :param reflectivity_matrix_dbz: See doc for `find_convective_pixels`.
    :param convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    :param min_composite_refl_dbz: See doc for `find_convective_pixels`.
    :return: convective_flag_matrix: Updated version of input.
    """

    weight_matrix = numpy.full((3, 3), 1.)
    weight_matrix = weight_matrix / weight_matrix.size

    average_matrix = convolve(
        convective_flag_matrix.astype(float), weights=weight_matrix,
        mode='constant', cval=0.
    )

    composite_refl_matrix_dbz = numpy.max(reflectivity_matrix_dbz, axis=-1)
    new_convective_flag_matrix = numpy.logical_and(
        (average_matrix > 0.).astype(bool),
        (composite_refl_matrix_dbz >= min_composite_refl_dbz).astype(bool)
    )

    return numpy.logical_or(convective_flag_matrix, new_convective_flag_matrix)


def find_convective_pixels(reflectivity_matrix_dbz, grid_metadata_dict,
                           valid_time_unix_sec, option_dict):
    """Classifies pixels (horiz grid points) as convective or non-convective.

    :param reflectivity_matrix_dbz: M-by-N-by-H numpy array of reflectivity
        values.  Latitude should increase along the first axis; longitude should
        increase along the second axis; height should increase along the third
        axis.  MAKE SURE NOT TO FLIP YOUR LATITUDES.

    :param grid_metadata_dict: Dictionary with the following keys.
    grid_metadata_dict['min_grid_point_latitude_deg']: Minimum latitude (deg N)
        over all grid points.
    grid_metadata_dict['latitude_spacing_deg']: Spacing (deg N) between grid
        points in adjacent rows.
    grid_metadata_dict['min_grid_point_longitude_deg']: Minimum longitude
        (deg E) over all grid points.
    grid_metadata_dict['longitude_spacing_deg']: Spacing (deg E) between grid
        points in adjacent columns.
    grid_metadata_dict['grid_point_heights_m_asl']: length-H numpy array of
        heights (metres above sea level) at grid points.

    :param valid_time_unix_sec: Valid time.

    :param option_dict: Dictionary with the following keys.
    option_dict['peakedness_neigh_metres'] Neighbourhood radius for peakedness
        calculations (metres), used for criterion 1.
    option_dict['max_peakedness_height_m_asl'] Max height (metres above sea
        level) for peakedness calculations, used in criterion 1.
    option_dict['halve_resolution_for_peakedness'] Boolean flag.  If True,
        horizontal grid resolution will be halved for peakedness calculations.
    option_dict['min_echo_top_m_asl'] Minimum echo top (metres above sea level),
        used for criterion 3.
    option_dict['echo_top_level_dbz'] Critical reflectivity (used to compute
        echo top for criterion 3).
    option_dict['min_composite_refl_criterion1_dbz'] Minimum composite
        (column-max) reflectivity for criterion 1.  This may be None.
    option_dict['min_composite_refl_criterion5_dbz'] Minimum composite
        reflectivity for criterion 5.
    option_dict['min_composite_refl_aml_dbz'] Minimum composite reflectivity
        above melting level, used for criterion 2.

    :return: convective_flag_matrix: M-by-N numpy array of Boolean flags (True
        if convective, False if not).
    :return: option_dict: Same as input, except some values may have been
        replaced by defaults.
    """

    # Error-checking.
    error_checking.assert_is_numpy_array(
        reflectivity_matrix_dbz, num_dimensions=3)

    option_dict = _check_input_args(option_dict)

    peakedness_neigh_metres = option_dict[PEAKEDNESS_NEIGH_KEY]
    max_peakedness_height_m_asl = option_dict[MAX_PEAKEDNESS_HEIGHT_KEY]
    halve_resolution_for_peakedness = option_dict[HALVE_RESOLUTION_KEY]
    min_echo_top_m_asl = option_dict[MIN_ECHO_TOP_KEY]
    echo_top_level_dbz = option_dict[ECHO_TOP_LEVEL_KEY]
    min_composite_refl_criterion1_dbz = option_dict[
        MIN_COMPOSITE_REFL_CRITERION1_KEY]
    min_composite_refl_criterion5_dbz = option_dict[
        MIN_COMPOSITE_REFL_CRITERION5_KEY]
    min_composite_refl_aml_dbz = option_dict[MIN_COMPOSITE_REFL_AML_KEY]

    grid_point_heights_m_asl = numpy.round(
        grid_metadata_dict[HEIGHTS_KEY]).astype(int)

    error_checking.assert_is_numpy_array(
        grid_point_heights_m_asl, num_dimensions=1)
    error_checking.assert_is_geq_numpy_array(grid_point_heights_m_asl, 0)
    error_checking.assert_is_greater_numpy_array(
        numpy.diff(grid_point_heights_m_asl), 0)  # Must be in ascending order.

    # Compute grid-point coordinates.
    num_rows = reflectivity_matrix_dbz.shape[0]
    num_columns = reflectivity_matrix_dbz.shape[1]

    grid_point_latitudes_deg, grid_point_longitudes_deg = (
        grids.get_latlng_grid_points(
            min_latitude_deg=grid_metadata_dict[MIN_LATITUDE_KEY],
            min_longitude_deg=grid_metadata_dict[MIN_LONGITUDE_KEY],
            lat_spacing_deg=grid_metadata_dict[LATITUDE_SPACING_KEY],
            lng_spacing_deg=grid_metadata_dict[LONGITUDE_SPACING_KEY],
            num_rows=num_rows, num_columns=num_columns)
    )

    grid_metadata_dict[LATITUDES_KEY] = grid_point_latitudes_deg
    grid_metadata_dict[LONGITUDES_KEY] = grid_point_longitudes_deg
    reflectivity_matrix_dbz[numpy.isnan(reflectivity_matrix_dbz)] = 0.

    print('Applying criterion 1 for convective classification...')
    convective_flag_matrix = _apply_convective_criterion1(
        reflectivity_matrix_dbz=reflectivity_matrix_dbz,
        peakedness_neigh_metres=peakedness_neigh_metres,
        max_peakedness_height_m_asl=max_peakedness_height_m_asl,
        halve_resolution_for_peakedness=halve_resolution_for_peakedness,
        min_composite_refl_dbz=min_composite_refl_criterion1_dbz,
        grid_metadata_dict=grid_metadata_dict)

    print(reflectivity_matrix_dbz)
    print(convective_flag_matrix)
    print('Number of convective pixels = {0:d}'.format(
        numpy.sum(convective_flag_matrix)
    ))

    print('Applying criterion 2 for convective classification...')
    convective_flag_matrix = _apply_convective_criterion2(
        reflectivity_matrix_dbz=reflectivity_matrix_dbz,
        convective_flag_matrix=convective_flag_matrix,
        grid_metadata_dict=grid_metadata_dict,
        valid_time_unix_sec=valid_time_unix_sec,
        min_composite_refl_aml_dbz=
        min_composite_refl_aml_dbz)

    print('Number of convective pixels = {0:d}'.format(
        numpy.sum(convective_flag_matrix)
    ))

    print('Applying criterion 3 for convective classification...')
    convective_flag_matrix = _apply_convective_criterion3(
        reflectivity_matrix_dbz=reflectivity_matrix_dbz,
        convective_flag_matrix=convective_flag_matrix,
        grid_metadata_dict=grid_metadata_dict,
        min_echo_top_m_asl=min_echo_top_m_asl,
        echo_top_level_dbz=echo_top_level_dbz)

    print('Number of convective pixels = {0:d}'.format(
        numpy.sum(convective_flag_matrix)
    ))

    print('Applying criterion 4 for convective classification...')
    convective_flag_matrix = _apply_convective_criterion4(
        convective_flag_matrix)

    print('Number of convective pixels = {0:d}'.format(
        numpy.sum(convective_flag_matrix)
    ))

    print('Applying criterion 5 for convective classification...')
    convective_flag_matrix = _apply_convective_criterion5(
        reflectivity_matrix_dbz=reflectivity_matrix_dbz,
        convective_flag_matrix=convective_flag_matrix,
        min_composite_refl_dbz=min_composite_refl_criterion5_dbz
    )

    return convective_flag_matrix, option_dict
