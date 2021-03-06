"""Plots radar images for the given days."""

import argparse
import numpy
import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot
from gewittergefahr.gg_utils import number_rounding
from gewittergefahr.gg_utils import time_conversion
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.gg_utils import error_checking
from gewittergefahr.plotting import plotting_utils as gg_plotting_utils
from gewittergefahr.plotting import radar_plotting
from ml4convection.io import radar_io
from ml4convection.io import border_io
from ml4convection.plotting import plotting_utils

SEPARATOR_STRING = '\n\n' + '*' * 50 + '\n\n'

DAYS_TO_SECONDS = 86400
DATE_FORMAT = '%Y%m%d'
TIME_FORMAT = '%Y-%m-%d-%H%M'
COMPOSITE_REFL_NAME = 'reflectivity_column_max_dbz'

MASK_OUTLINE_COLOUR = numpy.full(3, 152. / 255)
FIGURE_RESOLUTION_DPI = 300
FIGURE_WIDTH_INCHES = 15
FIGURE_HEIGHT_INCHES = 15

REFLECTIVITY_DIR_ARG_NAME = 'input_reflectivity_dir_name'
ECHO_CLASSIFN_DIR_ARG_NAME = 'input_echo_classifn_dir_name'
MASK_FILE_ARG_NAME = 'input_mask_file_name'
FIRST_DATE_ARG_NAME = 'first_date_string'
LAST_DATE_ARG_NAME = 'last_date_string'
PLOT_ALL_HEIGHTS_ARG_NAME = 'plot_all_heights'
DAILY_TIMES_ARG_NAME = 'daily_times_seconds'
SPATIAL_DS_FACTOR_ARG_NAME = 'spatial_downsampling_factor'
EXPAND_GRID_ARG_NAME = 'expand_to_satellite_grid'
OUTPUT_DIR_ARG_NAME = 'output_dir_name'

REFLECTIVITY_DIR_HELP_STRING = (
    'Name of directory with reflectivity data.  Files therein will be found by '
    '`radar_io.find_file` and read by `radar_io.read_reflectivity_file`.'
)
ECHO_CLASSIFN_DIR_HELP_STRING = (
    'Name of directory with echo-classification data (files therein will be '
    'found by `radar_io.find_file` and read by '
    '`radar_io.read_echo_classifn_file`).  If specified, will plot stippling '
    'over convective pixels.'
).format(REFLECTIVITY_DIR_ARG_NAME)

MASK_FILE_HELP_STRING = (
    'Name of mask file (will be read by `radar_io.read_mask_file`).  Unmasked '
    'area will be plotted with grey outline.  If you do not want to plot a '
    'mask, leave this alone.'
)
DATE_HELP_STRING = (
    'Date (format "yyyymmdd").  Will plot radar images for all days in the '
    'period `{0:s}`...`{1:s}`.'
).format(FIRST_DATE_ARG_NAME, LAST_DATE_ARG_NAME)

PLOT_ALL_HEIGHTS_HELP_STRING = (
    'Boolean flag.  If 1, will plot reflectivity at all heights, with one '
    'figure per height.  If 0, will plot composite reflectivity only.'
)
DAILY_TIMES_HELP_STRING = (
    'List of times to plot for each day.  All values should be in the range '
    '0...86399.'
)
SPATIAL_DS_FACTOR_HELP_STRING = (
    'Downsampling factor, used to coarsen spatial resolution.  If you do not '
    'want to coarsen spatial resolution, leave this alone.'
)
EXPAND_GRID_HELP_STRING = (
    'Boolean flag.  If 1 (0), will plot radar images on full satellite grid '
    '(original radar grid, which is smaller).'
)
OUTPUT_DIR_HELP_STRING = 'Name of output directory.  Images will be saved here.'

INPUT_ARG_PARSER = argparse.ArgumentParser()
INPUT_ARG_PARSER.add_argument(
    '--' + REFLECTIVITY_DIR_ARG_NAME, type=str, required=True,
    help=REFLECTIVITY_DIR_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + ECHO_CLASSIFN_DIR_ARG_NAME, type=str, required=False, default='',
    help=ECHO_CLASSIFN_DIR_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + MASK_FILE_ARG_NAME, type=str, required=False, default='',
    help=MASK_FILE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + FIRST_DATE_ARG_NAME, type=str, required=True, help=DATE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + LAST_DATE_ARG_NAME, type=str, required=True, help=DATE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + PLOT_ALL_HEIGHTS_ARG_NAME, type=int, required=False, default=0,
    help=PLOT_ALL_HEIGHTS_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + DAILY_TIMES_ARG_NAME, type=int, nargs='+', required=True,
    help=DAILY_TIMES_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + SPATIAL_DS_FACTOR_ARG_NAME, type=int, required=False, default=1,
    help=SPATIAL_DS_FACTOR_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + EXPAND_GRID_ARG_NAME, type=int, required=False, default=0,
    help=EXPAND_GRID_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + OUTPUT_DIR_ARG_NAME, type=str, required=True,
    help=OUTPUT_DIR_HELP_STRING
)


def _plot_radar_one_time(
        reflectivity_dict, echo_classifn_dict, mask_dict, example_index,
        border_latitudes_deg_n, border_longitudes_deg_e, plot_all_heights,
        output_dir_name):
    """Plots radar images for one time step.

    :param reflectivity_dict: See doc for `_plot_radar_one_day`.
    :param echo_classifn_dict: Same.
    :param mask_dict: Same.
    :param example_index: Will plot [i]th example, where i = `example_index`.
    :param border_latitudes_deg_n: See doc for `_plot_radar_one_day`.
    :param border_longitudes_deg_e: Same.
    :param plot_all_heights: Same.
    :param output_dir_name: Same.
    """

    latitudes_deg_n = reflectivity_dict[radar_io.LATITUDES_KEY]
    longitudes_deg_e = reflectivity_dict[radar_io.LONGITUDES_KEY]

    valid_time_unix_sec = (
        reflectivity_dict[radar_io.VALID_TIMES_KEY][example_index]
    )
    valid_time_string = time_conversion.unix_sec_to_string(
        valid_time_unix_sec, TIME_FORMAT
    )
    reflectivity_matrix_dbz = (
        reflectivity_dict[radar_io.REFLECTIVITY_KEY][example_index, ...]
    )
    colour_map_object, colour_norm_object = (
        radar_plotting.get_default_colour_scheme(COMPOSITE_REFL_NAME)
    )

    if plot_all_heights:
        heights_m_asl = reflectivity_dict[radar_io.HEIGHTS_KEY]
    else:
        heights_m_asl = numpy.array([numpy.nan])

    num_heights = len(heights_m_asl)

    for k in range(num_heights):
        figure_object, axes_object = pyplot.subplots(
            1, 1, figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES)
        )

        plotting_utils.plot_borders(
            border_latitudes_deg_n=border_latitudes_deg_n,
            border_longitudes_deg_e=border_longitudes_deg_e,
            axes_object=axes_object
        )

        if numpy.isnan(heights_m_asl[k]):
            matrix_to_plot = numpy.nanmax(reflectivity_matrix_dbz, axis=-1)
            title_string = 'Composite reflectivity at {0:s}'.format(
                valid_time_string
            )
        else:
            matrix_to_plot = reflectivity_matrix_dbz[..., k]
            title_string = 'Reflectivity at {0:d} m ASL at {1:s}'.format(
                int(numpy.round(heights_m_asl[k])), valid_time_string
            )

        radar_plotting.plot_latlng_grid(
            field_matrix=matrix_to_plot, field_name=COMPOSITE_REFL_NAME,
            axes_object=axes_object,
            min_grid_point_latitude_deg=numpy.min(latitudes_deg_n),
            min_grid_point_longitude_deg=numpy.min(longitudes_deg_e),
            latitude_spacing_deg=numpy.diff(latitudes_deg_n[:2])[0],
            longitude_spacing_deg=numpy.diff(longitudes_deg_e[:2])[0]
        )

        if mask_dict is not None:
            pyplot.contour(
                longitudes_deg_e, latitudes_deg_n,
                mask_dict[radar_io.MASK_MATRIX_KEY].astype(int),
                numpy.array([0.999]),
                colors=(MASK_OUTLINE_COLOUR,), linewidths=2, linestyles='solid',
                axes=axes_object
            )

        if echo_classifn_dict is not None:
            convective_flag_matrix = echo_classifn_dict[
                radar_io.CONVECTIVE_FLAGS_KEY
            ][example_index, ...]

            row_indices, column_indices = numpy.where(convective_flag_matrix)
            positive_latitudes_deg_n = latitudes_deg_n[row_indices]
            positive_longitudes_deg_e = longitudes_deg_e[column_indices]

            plotting_utils.plot_stippling(
                x_coords=positive_longitudes_deg_e,
                y_coords=positive_latitudes_deg_n,
                figure_object=figure_object, axes_object=axes_object,
                num_grid_columns=convective_flag_matrix.shape[1]
            )

        gg_plotting_utils.plot_colour_bar(
            axes_object_or_matrix=axes_object, data_matrix=matrix_to_plot,
            colour_map_object=colour_map_object,
            colour_norm_object=colour_norm_object,
            orientation_string='vertical', extend_min=False, extend_max=True
        )

        plotting_utils.plot_grid_lines(
            plot_latitudes_deg_n=latitudes_deg_n,
            plot_longitudes_deg_e=longitudes_deg_e, axes_object=axes_object,
            parallel_spacing_deg=2., meridian_spacing_deg=2.
        )

        axes_object.set_title(title_string)

        if numpy.isnan(heights_m_asl[k]):
            height_string = 'composite'
        else:
            height_string = '{0:05d}-metres-asl'.format(
                int(numpy.round(heights_m_asl[k]))
            )

        output_file_name = '{0:s}/reflectivity_{1:s}_{2:s}.jpg'.format(
            output_dir_name, valid_time_string, height_string
        )

        print('Saving figure to file: "{0:s}"...'.format(output_file_name))
        figure_object.savefig(
            output_file_name, dpi=FIGURE_RESOLUTION_DPI,
            pad_inches=0, bbox_inches='tight'
        )
        pyplot.close(figure_object)


def _plot_radar_one_day(
        reflectivity_dict, echo_classifn_dict, mask_dict,
        border_latitudes_deg_n, border_longitudes_deg_e, plot_all_heights,
        daily_times_seconds, spatial_downsampling_factor,
        expand_to_satellite_grid, top_output_dir_name):
    """Plots radar images for one day.

    P = number of points in border set

    :param reflectivity_dict: Dictionary in the format returned by
        `radar_io.read_reflectivity_file`.
    :param echo_classifn_dict: Dictionary in the format returned by
        `radar_io.read_echo_classifn_file`.  If specified, will plot convective
        pixels only.  If None, will plot all pixels.
    :param mask_dict: Dictionary in the format returned by
        `radar_io.read_mask_file`.  If specified, will plot grey outline around
        unmasked area.
    :param border_latitudes_deg_n: length-P numpy array of latitudes (deg N).
    :param border_longitudes_deg_e: length-P numpy array of longitudes (deg E).
    :param plot_all_heights: See documentation at top of file.
    :param daily_times_seconds: Same.
    :param spatial_downsampling_factor: Same.
    :param expand_to_satellite_grid: Same.
    :param top_output_dir_name: Same.
    """

    if echo_classifn_dict is not None:
        assert numpy.array_equal(
            reflectivity_dict[radar_io.VALID_TIMES_KEY],
            echo_classifn_dict[radar_io.VALID_TIMES_KEY]
        )

    if expand_to_satellite_grid:
        reflectivity_dict = radar_io.expand_to_satellite_grid(
            any_radar_dict=reflectivity_dict, fill_nans=True
        )

        if echo_classifn_dict is not None:
            echo_classifn_dict = radar_io.expand_to_satellite_grid(
                any_radar_dict=echo_classifn_dict, fill_nans=True
            )

    if spatial_downsampling_factor is not None:
        reflectivity_dict = radar_io.downsample_in_space(
            any_radar_dict=reflectivity_dict,
            downsampling_factor=spatial_downsampling_factor
        )

        if echo_classifn_dict is not None:
            echo_classifn_dict = radar_io.downsample_in_space(
                any_radar_dict=echo_classifn_dict,
                downsampling_factor=spatial_downsampling_factor
            )

    valid_times_unix_sec = reflectivity_dict[radar_io.VALID_TIMES_KEY]
    base_time_unix_sec = number_rounding.floor_to_nearest(
        valid_times_unix_sec[0], DAYS_TO_SECONDS
    )
    desired_times_unix_sec = numpy.round(
        base_time_unix_sec + daily_times_seconds
    ).astype(int)

    good_flags = numpy.array([
        t in valid_times_unix_sec for t in desired_times_unix_sec
    ], dtype=bool)

    if not numpy.any(good_flags):
        return

    desired_times_unix_sec = desired_times_unix_sec[good_flags]
    reflectivity_dict = radar_io.subset_by_time(
        refl_or_echo_classifn_dict=reflectivity_dict,
        desired_times_unix_sec=desired_times_unix_sec
    )[0]

    if echo_classifn_dict is not None:
        echo_classifn_dict = radar_io.subset_by_time(
            refl_or_echo_classifn_dict=echo_classifn_dict,
            desired_times_unix_sec=desired_times_unix_sec
        )[0]

    date_string = time_conversion.unix_sec_to_string(
        desired_times_unix_sec[0], DATE_FORMAT
    )
    output_dir_name = '{0:s}/{1:s}/{2:s}'.format(
        top_output_dir_name, date_string[:4], date_string
    )
    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    num_times = len(desired_times_unix_sec)

    for i in range(num_times):
        _plot_radar_one_time(
            reflectivity_dict=reflectivity_dict,
            echo_classifn_dict=echo_classifn_dict,
            mask_dict=mask_dict, example_index=i,
            border_latitudes_deg_n=border_latitudes_deg_n,
            border_longitudes_deg_e=border_longitudes_deg_e,
            plot_all_heights=plot_all_heights,
            output_dir_name=output_dir_name
        )


def _run(top_reflectivity_dir_name, top_echo_classifn_dir_name, mask_file_name,
         first_date_string, last_date_string, plot_all_heights,
         daily_times_seconds, spatial_downsampling_factor,
         expand_to_satellite_grid, top_output_dir_name):
    """Plots radar images for the given days.

    This is effectively the main method.

    :param top_reflectivity_dir_name: See documentation at top of file.
    :param top_echo_classifn_dir_name: Same.
    :param mask_file_name: Same.
    :param first_date_string: Same.
    :param last_date_string: Same.
    :param plot_all_heights: Same.
    :param daily_times_seconds: Same.
    :param spatial_downsampling_factor: Same.
    :param expand_to_satellite_grid: Same.
    :param top_output_dir_name: Same.
    """

    border_latitudes_deg_n, border_longitudes_deg_e = border_io.read_file()

    if spatial_downsampling_factor <= 1:
        spatial_downsampling_factor = None

    if top_echo_classifn_dir_name == '':
        top_echo_classifn_dir_name = None

    if mask_file_name == '':
        mask_dict = None
    else:
        print('Reading mask from: "{0:s}"...'.format(mask_file_name))
        mask_dict = radar_io.read_mask_file(mask_file_name)

        if expand_to_satellite_grid:
            mask_dict = radar_io.expand_to_satellite_grid(
                any_radar_dict=mask_dict
            )

        if spatial_downsampling_factor > 1:
            mask_dict = radar_io.downsample_in_space(
                any_radar_dict=mask_dict,
                downsampling_factor=spatial_downsampling_factor
            )

    error_checking.assert_is_geq_numpy_array(daily_times_seconds, 0)
    error_checking.assert_is_less_than_numpy_array(
        daily_times_seconds, DAYS_TO_SECONDS
    )

    input_file_names = radar_io.find_many_files(
        top_directory_name=top_reflectivity_dir_name,
        first_date_string=first_date_string,
        last_date_string=last_date_string,
        file_type_string=radar_io.REFL_TYPE_STRING,
        raise_error_if_any_missing=False
    )

    if top_echo_classifn_dir_name is None:
        echo_classifn_file_names = None
    else:
        echo_classifn_file_names = [
            radar_io.find_file(
                top_directory_name=top_echo_classifn_dir_name,
                valid_date_string=radar_io.file_name_to_date(f),
                file_type_string=radar_io.ECHO_CLASSIFN_TYPE_STRING,
                raise_error_if_missing=True
            )
            for f in input_file_names
        ]

    for i in range(len(input_file_names)):
        print('Reading data from: "{0:s}"...'.format(input_file_names[i]))
        reflectivity_dict = radar_io.read_reflectivity_file(
            netcdf_file_name=input_file_names[i], fill_nans=True
        )

        if top_echo_classifn_dir_name is None:
            echo_classifn_dict = None
        else:
            echo_classifn_dict = radar_io.read_echo_classifn_file(
                echo_classifn_file_names[i]
            )

        _plot_radar_one_day(
            reflectivity_dict=reflectivity_dict,
            echo_classifn_dict=echo_classifn_dict, mask_dict=mask_dict,
            plot_all_heights=plot_all_heights,
            daily_times_seconds=daily_times_seconds,
            border_latitudes_deg_n=border_latitudes_deg_n,
            border_longitudes_deg_e=border_longitudes_deg_e,
            spatial_downsampling_factor=spatial_downsampling_factor,
            expand_to_satellite_grid=expand_to_satellite_grid,
            top_output_dir_name=top_output_dir_name
        )

        if i != len(input_file_names) - 1:
            print(SEPARATOR_STRING)


if __name__ == '__main__':
    INPUT_ARG_OBJECT = INPUT_ARG_PARSER.parse_args()

    _run(
        top_reflectivity_dir_name=getattr(
            INPUT_ARG_OBJECT, REFLECTIVITY_DIR_ARG_NAME
        ),
        top_echo_classifn_dir_name=getattr(
            INPUT_ARG_OBJECT, ECHO_CLASSIFN_DIR_ARG_NAME
        ),
        mask_file_name=getattr(INPUT_ARG_OBJECT, MASK_FILE_ARG_NAME),
        first_date_string=getattr(INPUT_ARG_OBJECT, FIRST_DATE_ARG_NAME),
        last_date_string=getattr(INPUT_ARG_OBJECT, LAST_DATE_ARG_NAME),
        plot_all_heights=bool(
            getattr(INPUT_ARG_OBJECT, PLOT_ALL_HEIGHTS_ARG_NAME)
        ),
        daily_times_seconds=numpy.array(
            getattr(INPUT_ARG_OBJECT, DAILY_TIMES_ARG_NAME), dtype=int
        ),
        spatial_downsampling_factor=getattr(
            INPUT_ARG_OBJECT, SPATIAL_DS_FACTOR_ARG_NAME
        ),
        expand_to_satellite_grid=bool(
            getattr(INPUT_ARG_OBJECT, EXPAND_GRID_ARG_NAME)
        ),
        top_output_dir_name=getattr(INPUT_ARG_OBJECT, OUTPUT_DIR_ARG_NAME)
    )
