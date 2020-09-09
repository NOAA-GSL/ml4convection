"""Plot predictions (and targets) for the given days."""

import argparse
import numpy
import matplotlib
matplotlib.use('agg')
from matplotlib import pyplot
from gewittergefahr.gg_utils import time_conversion
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.gg_utils import error_checking
from ml4convection.io import prediction_io
from ml4convection.plotting import prediction_plotting

TIME_FORMAT = '%Y-%m-%d-%H%M'

NUM_PARALLELS = 8
NUM_MERIDIANS = 6
FIGURE_RESOLUTION_DPI = 300
FIGURE_WIDTH_INCHES = 15
FIGURE_HEIGHT_INCHES = 15

INPUT_DIR_ARG_NAME = 'input_prediction_dir_name'
FIRST_DATE_ARG_NAME = 'first_date_string'
LAST_DATE_ARG_NAME = 'last_date_string'
NUM_EXAMPLES_PER_DAY_ARG_NAME = 'num_examples_per_day'
PLOT_RANDOM_ARG_NAME = 'plot_random_examples'
PROB_THRESHOLD_ARG_NAME = 'probability_threshold'
OUTPUT_DIR_ARG_NAME = 'output_dir_name'

INPUT_DIR_HELP_STRING = (
    'Name of input directory.  Files therein will be found by '
    '`prediction_io.find_file` and read by `prediction_io.read_file`.'
)
DATE_HELP_STRING = (
    'Date (format "yyyymmdd").  Will plot predictions for all days in the '
    'period `{0:s}`...`{1:s}`.'
).format(FIRST_DATE_ARG_NAME, LAST_DATE_ARG_NAME)

NUM_EXAMPLES_PER_DAY_HELP_STRING = (
    'Number of examples (time steps) to plot for each day.'
)
PLOT_RANDOM_HELP_STRING = (
    'Boolean flag.  If 1, will randomly draw `{0:s}` examples from each day.  '
    'If 0, will draw the first `{0:s}` examples from each day.'
).format(NUM_EXAMPLES_PER_DAY_ARG_NAME)

PROB_THRESHOLD_HELP_STRING = (
    'Threshold used to convert probabilistic forecasts to deterministic.  All '
    'probabilities >= `{0:s}` will be considered "yes" forecasts, and all '
    'probabilities < `{0:s}` will be considered "no" forecasts.'
).format(PROB_THRESHOLD_ARG_NAME)

OUTPUT_DIR_HELP_STRING = (
    'Name of output directory.  Figures will be saved here.'
)

INPUT_ARG_PARSER = argparse.ArgumentParser()
INPUT_ARG_PARSER.add_argument(
    '--' + INPUT_DIR_ARG_NAME, type=str, required=True,
    help=INPUT_DIR_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + FIRST_DATE_ARG_NAME, type=str, required=True, help=DATE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + LAST_DATE_ARG_NAME, type=str, required=True, help=DATE_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + NUM_EXAMPLES_PER_DAY_ARG_NAME, type=int, required=False, default=5,
    help=NUM_EXAMPLES_PER_DAY_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + PLOT_RANDOM_ARG_NAME, type=int, required=False, default=1,
    help=PLOT_RANDOM_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + PROB_THRESHOLD_ARG_NAME, type=float, required=True,
    help=PROB_THRESHOLD_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + OUTPUT_DIR_ARG_NAME, type=str, required=True,
    help=OUTPUT_DIR_HELP_STRING
)


def _plot_predictions_one_example(
        prediction_dict, example_index, probability_threshold, output_dir_name):
    """Plots predictions (and targets) for one example (time step).

    :param prediction_dict: Dictionary in format returned by
        `prediction_io.read_file`.
    :param example_index: Will plot [i]th example, where i = `example_index`.
    :param probability_threshold: See documentation at top of file.
    :param output_dir_name: Same.
    """

    latitudes_deg_n = prediction_dict[prediction_io.LATITUDES_KEY]
    longitudes_deg_e = prediction_dict[prediction_io.LONGITUDES_KEY]

    # figure_object, axes_object, basemap_object = (
    #     plotting_utils.create_equidist_cylindrical_map(
    #         min_latitude_deg=numpy.min(latitudes_deg_n),
    #         max_latitude_deg=numpy.max(latitudes_deg_n),
    #         min_longitude_deg=numpy.min(longitudes_deg_e),
    #         max_longitude_deg=numpy.max(longitudes_deg_e),
    #         resolution_string='i'
    #     )
    # )
    #
    # plotting_utils.plot_coastlines(
    #     basemap_object=basemap_object, axes_object=axes_object,
    #     line_colour=plotting_utils.DEFAULT_COUNTRY_COLOUR
    # )
    # plotting_utils.plot_countries(
    #     basemap_object=basemap_object, axes_object=axes_object
    # )
    # plotting_utils.plot_states_and_provinces(
    #     basemap_object=basemap_object, axes_object=axes_object
    # )
    # plotting_utils.plot_parallels(
    #     basemap_object=basemap_object, axes_object=axes_object,
    #     num_parallels=NUM_PARALLELS
    # )
    # plotting_utils.plot_meridians(
    #     basemap_object=basemap_object, axes_object=axes_object,
    #     num_meridians=NUM_MERIDIANS
    # )

    figure_object, axes_object = pyplot.subplots(
        1, 1, figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES)
    )

    i = example_index
    valid_time_unix_sec = prediction_dict[prediction_io.VALID_TIMES_KEY][i]
    target_matrix = prediction_dict[prediction_io.TARGET_MATRIX_KEY][i, ...]
    prediction_matrix = (
        prediction_dict[prediction_io.PROBABILITY_MATRIX_KEY][i, ...]
        >= probability_threshold
    ).astype(int)

    prediction_plotting.plot_with_basemap(
        target_matrix=target_matrix, prediction_matrix=prediction_matrix,
        axes_object=axes_object,
        min_latitude_deg_n=latitudes_deg_n[0],
        min_longitude_deg_e=longitudes_deg_e[0],
        latitude_spacing_deg=numpy.diff(latitudes_deg_n[:2])[0],
        longitude_spacing_deg=numpy.diff(longitudes_deg_e[:2])[0]
    )

    valid_time_string = time_conversion.unix_sec_to_string(
        valid_time_unix_sec, TIME_FORMAT
    )
    title_string = (
        'Actual (pink) and predicted (grey) convection at {0:s}'
    ).format(valid_time_string)

    axes_object.set_title(title_string)
    axes_object.set_xlabel(r'Longitude ($^{\circ}$E)')
    axes_object.set_ylabel(r'Latitude ($^{\circ}$N)')

    output_file_name = '{0:s}/predictions_{1:s}.jpg'.format(
        output_dir_name, valid_time_string
    )

    print('Saving figure to file: "{0:s}"...'.format(output_file_name))
    figure_object.savefig(
        output_file_name, dpi=FIGURE_RESOLUTION_DPI,
        pad_inches=0, bbox_inches='tight'
    )
    pyplot.close(figure_object)


def _plot_predictions_one_day(
        prediction_file_name, num_examples, plot_random_examples,
        probability_threshold, output_dir_name):
    """Plots predictions (and targets) for one day.

    :param prediction_file_name: Path to prediction file.  Will be read by
        `prediction_io.read_file`.
    :param num_examples: Number of examples to plot.
    :param plot_random_examples: See documentation at top of file.
    :param probability_threshold: Same.
    :param output_dir_name: Same.
    """

    print('Reading data from: "{0:s}"...'.format(prediction_file_name))
    prediction_dict = prediction_io.read_file(prediction_file_name)

    num_examples_total = len(prediction_dict[prediction_io.VALID_TIMES_KEY])
    example_indices = numpy.linspace(
        0, num_examples_total - 1, num=num_examples_total, dtype=int
    )

    if num_examples < num_examples_total:
        if plot_random_examples:
            example_indices = numpy.random.choice(
                example_indices, size=num_examples, replace=False
            )
        else:
            example_indices = example_indices[:num_examples]

    prediction_dict = prediction_io.subset_by_index(
        prediction_dict=prediction_dict, desired_indices=example_indices
    )
    num_examples = len(prediction_dict[prediction_io.VALID_TIMES_KEY])

    for i in range(num_examples):
        _plot_predictions_one_example(
            prediction_dict=prediction_dict, example_index=i,
            probability_threshold=probability_threshold,
            output_dir_name=output_dir_name
        )


def _run(top_prediction_dir_name, first_date_string, last_date_string,
         num_examples_per_day, plot_random_examples, probability_threshold,
         output_dir_name):
    """Plot predictions (and targets) for the given days.

    This is effectively the main method.

    :param top_prediction_dir_name: See documentation at top of file.
    :param first_date_string: Same.
    :param last_date_string: Same.
    :param num_examples_per_day: Same.
    :param plot_random_examples: Same.
    :param probability_threshold: Same.
    :param output_dir_name: Same.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    error_checking.assert_is_greater(probability_threshold, 0.)
    error_checking.assert_is_less_than(probability_threshold, 1.)

    prediction_file_names = prediction_io.find_many_files(
        top_directory_name=top_prediction_dir_name,
        first_date_string=first_date_string,
        last_date_string=last_date_string,
        raise_error_if_any_missing=False
    )

    for this_file_name in prediction_file_names:
        _plot_predictions_one_day(
            prediction_file_name=this_file_name,
            num_examples=num_examples_per_day,
            plot_random_examples=plot_random_examples,
            probability_threshold=probability_threshold,
            output_dir_name=output_dir_name
        )


if __name__ == '__main__':
    INPUT_ARG_OBJECT = INPUT_ARG_PARSER.parse_args()

    _run(
        top_prediction_dir_name=getattr(INPUT_ARG_OBJECT, INPUT_DIR_ARG_NAME),
        first_date_string=getattr(INPUT_ARG_OBJECT, FIRST_DATE_ARG_NAME),
        last_date_string=getattr(INPUT_ARG_OBJECT, LAST_DATE_ARG_NAME),
        num_examples_per_day=getattr(
            INPUT_ARG_OBJECT, NUM_EXAMPLES_PER_DAY_ARG_NAME
        ),
        plot_random_examples=bool(getattr(
            INPUT_ARG_OBJECT, PLOT_RANDOM_ARG_NAME
        )),
        probability_threshold=getattr(
            INPUT_ARG_OBJECT, PROB_THRESHOLD_ARG_NAME
        ),
        output_dir_name=getattr(INPUT_ARG_OBJECT, OUTPUT_DIR_ARG_NAME)
    )