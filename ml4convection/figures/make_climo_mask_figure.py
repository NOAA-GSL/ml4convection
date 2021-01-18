"""Makes figure with radar climatology and radar mask."""

import argparse
import numpy
import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.plotting import radar_plotting
from gewittergefahr.plotting import plotting_utils as gg_plotting_utils
from ml4convection.io import radar_io
from ml4convection.io import border_io
from ml4convection.utils import radar_utils
from ml4convection.plotting import plotting_utils

DUMMY_FIELD_NAME = 'reflectivity_column_max_dbz'
MASK_COLOUR_MAP_OBJECT = pyplot.get_cmap('winter')
MASK_COLOUR_NORM_OBJECT = pyplot.Normalize(vmin=0., vmax=1.)
BORDER_COLOUR_WITH_MASK = numpy.full(3, 0.)

INNER_DOMAIN_HALF_WIDTH_PX = 52
COMPLETE_DOMAIN_HALF_WIDTH_PX = 102

INNER_DOMAIN_COLOUR = numpy.array([117, 112, 179], dtype=float) / 255
COMPLETE_DOMAIN_COLOUR = numpy.array([217, 95, 2], dtype=float) / 255
DOMAIN_LINE_WIDTH = 3.

FIGURE_WIDTH_INCHES = 15
FIGURE_HEIGHT_INCHES = 15
FIGURE_RESOLUTION_DPI = 300
CONCAT_FIGURE_SIZE_PX = int(1e7)

CLIMO_FILE_ARG_NAME = 'input_climo_file_name'
MASK_FILE_ARG_NAME = 'input_mask_file_name'
OUTPUT_DIR_ARG_NAME = 'output_dir_name'

CLIMO_FILE_HELP_STRING = (
    'Path to climatology file.  Will be read by `climatology_io.read_file`.'
)
MASK_FILE_HELP_STRING = (
    'Path to mask file.  Will be read by `radar_io.read_mask_file`.'
)
OUTPUT_DIR_HELP_STRING = (
    'Name of output directory.  Figures will be saved here.'
)

INPUT_ARG_PARSER = argparse.ArgumentParser()
INPUT_ARG_PARSER.add_argument(
    '--' + CLIMO_FILE_ARG_NAME, type=str, required=True,
    help=CLIMO_FILE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + MASK_FILE_ARG_NAME, type=str, required=True,
    help=MASK_FILE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + OUTPUT_DIR_ARG_NAME, type=str, required=True,
    help=OUTPUT_DIR_HELP_STRING
)


def _plot_mask(mask_dict, border_latitudes_deg_n, border_longitudes_deg_e,
               letter_label, output_file_name):
    """Plots radar mask.

    P = number of points in border set

    :param mask_dict: Dictionary returned by `radar_io.read_mask_file`.
    :param border_latitudes_deg_n: length-P numpy array of latitudes (deg N).
    :param border_longitudes_deg_e: length-P numpy array of longitudes (deg E).
    :param letter_label: Letter label.
    :param output_file_name: Path to output file.  Figure will be saved here.
    """

    latitudes_deg_n = mask_dict[radar_io.LATITUDES_KEY]
    longitudes_deg_e = mask_dict[radar_io.LONGITUDES_KEY]

    figure_object, axes_object = pyplot.subplots(
        1, 1, figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES)
    )

    plotting_utils.plot_borders(
        border_latitudes_deg_n=border_latitudes_deg_n,
        border_longitudes_deg_e=border_longitudes_deg_e,
        axes_object=axes_object, line_colour=BORDER_COLOUR_WITH_MASK
    )

    mask_matrix = mask_dict[radar_io.MASK_MATRIX_KEY].astype(float)
    mask_matrix[mask_matrix < 0.5] = numpy.nan

    radar_plotting.plot_latlng_grid(
        field_matrix=mask_matrix, field_name=DUMMY_FIELD_NAME,
        axes_object=axes_object,
        min_grid_point_latitude_deg=numpy.min(latitudes_deg_n),
        min_grid_point_longitude_deg=numpy.min(longitudes_deg_e),
        latitude_spacing_deg=numpy.diff(latitudes_deg_n[:2])[0],
        longitude_spacing_deg=numpy.diff(longitudes_deg_e[:2])[0],
        colour_map_object=MASK_COLOUR_MAP_OBJECT,
        colour_norm_object=MASK_COLOUR_NORM_OBJECT
    )

    plotting_utils.plot_grid_lines(
        plot_latitudes_deg_n=latitudes_deg_n,
        plot_longitudes_deg_e=longitudes_deg_e, axes_object=axes_object,
        parallel_spacing_deg=2., meridian_spacing_deg=2.
    )

    this_index = numpy.argmin(radar_utils.RADAR_LATITUDES_DEG_N)
    radar_latitude_deg_n = radar_utils.RADAR_LATITUDES_DEG_N[this_index]
    radar_longitude_deg_e = radar_utils.RADAR_LONGITUDES_DEG_E[this_index]

    radar_row = numpy.argmin(numpy.absolute(
        radar_latitude_deg_n - latitudes_deg_n
    ))
    radar_column = numpy.argmin(numpy.absolute(
        radar_longitude_deg_e - longitudes_deg_e
    ))

    inner_polygon_rows = numpy.array([
        radar_row - INNER_DOMAIN_HALF_WIDTH_PX,
        radar_row - INNER_DOMAIN_HALF_WIDTH_PX,
        radar_row + INNER_DOMAIN_HALF_WIDTH_PX,
        radar_row + INNER_DOMAIN_HALF_WIDTH_PX,
        radar_row - INNER_DOMAIN_HALF_WIDTH_PX
    ], dtype=int)

    complete_polygon_rows = numpy.array([
        radar_row - COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_row - COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_row + COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_row + COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_row - COMPLETE_DOMAIN_HALF_WIDTH_PX
    ], dtype=int)

    inner_polygon_columns = numpy.array([
        radar_column - INNER_DOMAIN_HALF_WIDTH_PX,
        radar_column + INNER_DOMAIN_HALF_WIDTH_PX,
        radar_column + INNER_DOMAIN_HALF_WIDTH_PX,
        radar_column - INNER_DOMAIN_HALF_WIDTH_PX,
        radar_column - INNER_DOMAIN_HALF_WIDTH_PX
    ], dtype=int)

    complete_polygon_columns = numpy.array([
        radar_column - COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_column + COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_column + COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_column - COMPLETE_DOMAIN_HALF_WIDTH_PX,
        radar_column - COMPLETE_DOMAIN_HALF_WIDTH_PX
    ], dtype=int)

    axes_object.plot(
        longitudes_deg_e[inner_polygon_rows],
        latitudes_deg_n[inner_polygon_columns],
        color=INNER_DOMAIN_COLOUR, linestyle='solid',
        linewidth=DOMAIN_LINE_WIDTH
    )

    axes_object.plot(
        longitudes_deg_e[complete_polygon_rows],
        latitudes_deg_n[complete_polygon_columns],
        color=COMPLETE_DOMAIN_COLOUR, linestyle='solid',
        linewidth=DOMAIN_LINE_WIDTH
    )

    axes_object.set_title('Radar mask (100-km radius)')
    gg_plotting_utils.label_axes(
        axes_object=axes_object, label_string='({0:s})'.format(letter_label)
    )

    print('Saving figure to file: "{0:s}"...'.format(output_file_name))
    figure_object.savefig(
        output_file_name, dpi=FIGURE_RESOLUTION_DPI,
        pad_inches=0, bbox_inches='tight'
    )
    pyplot.close(figure_object)


def _run(climo_file_name, mask_file_name, output_dir_name):
    """Makes figure with radar climatology and radar mask.

    This is effectively the main method.

    :param climo_file_name: See documentation at top of file.
    :param mask_file_name: Same.
    :param output_dir_name: Same.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    border_latitudes_deg_n, border_longitudes_deg_e = border_io.read_file()

    print('Reading data from: "{0:s}"...'.format(mask_file_name))
    mask_dict = radar_io.read_mask_file(mask_file_name)

    mask_figure_file_name = '{0:s}/radar_mask.jpg'.format(output_dir_name)

    _plot_mask(
        mask_dict=mask_dict, border_latitudes_deg_n=border_latitudes_deg_n,
        border_longitudes_deg_e=border_longitudes_deg_e,
        letter_label='a', output_file_name=mask_figure_file_name
    )


if __name__ == '__main__':
    INPUT_ARG_OBJECT = INPUT_ARG_PARSER.parse_args()

    _run(
        climo_file_name=getattr(INPUT_ARG_OBJECT, CLIMO_FILE_ARG_NAME),
        mask_file_name=getattr(INPUT_ARG_OBJECT, MASK_FILE_ARG_NAME),
        output_dir_name=getattr(INPUT_ARG_OBJECT, OUTPUT_DIR_ARG_NAME)
    )