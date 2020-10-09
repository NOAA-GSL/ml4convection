"""Plots scores on hyperparameter grid for Experiment 5."""

import sys
import os.path
import argparse
import numpy
import matplotlib
matplotlib.use('agg')
import matplotlib.colors
from matplotlib import pyplot

THIS_DIRECTORY_NAME = os.path.dirname(os.path.realpath(
    os.path.join(os.getcwd(), os.path.expanduser(__file__))
))
sys.path.append(os.path.normpath(os.path.join(THIS_DIRECTORY_NAME, '..')))

import evaluation
import gg_model_evaluation as gg_model_eval
import gg_plotting_utils
import file_system_utils

SEPARATOR_STRING = '\n\n' + '*' * 50 + '\n\n'

LAG_TIME_STRINGS = [
    '0', '0-600-1200', '0-600-1200-1800-2400', '0-600-1200-1800-2400-3000-3600',
    '0-1200', '0-1200-2400', '0-1200-2400-3600'
]
CONV_LAYER_DROPOUT_RATES = numpy.array([0, 0.05, 0.1, 0.15, 0.2])
L2_WEIGHTS = numpy.logspace(-6, -4, num=5)

FONT_SIZE = 20
pyplot.rc('font', size=FONT_SIZE)
pyplot.rc('axes', titlesize=FONT_SIZE)
pyplot.rc('axes', labelsize=FONT_SIZE)
pyplot.rc('xtick', labelsize=FONT_SIZE)
pyplot.rc('ytick', labelsize=FONT_SIZE)
pyplot.rc('legend', fontsize=FONT_SIZE)
pyplot.rc('figure', titlesize=FONT_SIZE)

DEFAULT_COLOUR_MAP_OBJECT = pyplot.get_cmap('plasma')
BSS_COLOUR_MAP_OBJECT = pyplot.get_cmap('seismic')

FIGURE_WIDTH_INCHES = 15
FIGURE_HEIGHT_INCHES = 15
FIGURE_RESOLUTION_DPI = 300

EXPERIMENT_DIR_ARG_NAME = 'experiment_dir_name'
EXPERIMENT_DIR_HELP_STRING = 'Name of top-level directory with models.'

INPUT_ARG_PARSER = argparse.ArgumentParser()
INPUT_ARG_PARSER.add_argument(
    '--' + EXPERIMENT_DIR_ARG_NAME, type=str, required=True,
    help=EXPERIMENT_DIR_HELP_STRING
)


def _plot_scores_2d(
        score_matrix, min_colour_value, max_colour_value, x_tick_labels,
        y_tick_labels, colour_map_object):
    """Plots scores on 2-D grid.

    M = number of rows in grid
    N = number of columns in grid

    :param score_matrix: M-by-N numpy array of scores.
    :param min_colour_value: Minimum value in colour scheme.
    :param max_colour_value: Max value in colour scheme.
    :param x_tick_labels: length-N list of tick labels.
    :param y_tick_labels: length-M list of tick labels.
    :param colour_map_object: Colour scheme (instance of `matplotlib.pyplot.cm`
        or similar).
    :return: figure_object: Figure handle (instance of
        `matplotlib.figure.Figure`).
    :return: axes_object: Axes handle (instance of
        `matplotlib.axes._subplots.AxesSubplot`).
    """

    figure_object, axes_object = pyplot.subplots(
        1, 1, figsize=(FIGURE_WIDTH_INCHES, FIGURE_HEIGHT_INCHES)
    )

    axes_object.imshow(
        score_matrix, cmap=colour_map_object, origin='lower',
        vmin=min_colour_value, vmax=max_colour_value
    )

    x_tick_values = numpy.linspace(
        0, score_matrix.shape[1] - 1, num=score_matrix.shape[1], dtype=float
    )
    y_tick_values = numpy.linspace(
        0, score_matrix.shape[0] - 1, num=score_matrix.shape[0], dtype=float
    )

    pyplot.xticks(x_tick_values, x_tick_labels)
    pyplot.yticks(y_tick_values, y_tick_labels)

    colour_norm_object = matplotlib.colors.Normalize(
        vmin=min_colour_value, vmax=max_colour_value, clip=False
    )

    colour_bar_object = gg_plotting_utils.plot_colour_bar(
        axes_object_or_matrix=axes_object,
        data_matrix=score_matrix[numpy.invert(numpy.isnan(score_matrix))],
        colour_map_object=colour_map_object,
        colour_norm_object=colour_norm_object,
        orientation_string='horizontal', extend_min=False, extend_max=False,
        fraction_of_axis_length=0.8, font_size=FONT_SIZE
    )

    tick_values = colour_bar_object.get_ticks()
    tick_strings = ['{0:.2g}'.format(v) for v in tick_values]
    colour_bar_object.set_ticks(tick_values)
    colour_bar_object.set_ticklabels(tick_strings)

    return figure_object, axes_object


def _print_ranking_one_score(score_matrix, score_name):
    """Prints ranking for one score.

    L = number of lag-time sets for predictors
    C = number of conv-layer dropout rates
    W = number of L_2 weights

    :param score_matrix: L-by-C-by-W numpy array of scores.
    :param score_name: Name of score.
    """

    scores_1d = numpy.ravel(score_matrix)
    scores_1d[numpy.isnan(scores_1d)] = -numpy.inf
    sort_indices_1d = numpy.argsort(-scores_1d)
    i_sort_indices, j_sort_indices, k_sort_indices = numpy.unravel_index(
        sort_indices_1d, score_matrix.shape
    )

    for m in range(len(i_sort_indices)):
        i = i_sort_indices[m]
        j = j_sort_indices[m]
        k = k_sort_indices[m]

        print((
            '{0:d}th-highest {1:s} = {2:.4g} ... lag times (seconds) = {3:s} '
            '... conv-layer dropout rate = {4:.3f} ... L_2 weight = 10^{5:.1f}'
        ).format(
            m + 1, score_name, score_matrix[i, j, k],
            LAG_TIME_STRINGS[i], CONV_LAYER_DROPOUT_RATES[j],
            numpy.log10(L2_WEIGHTS[k])
        ))


def _run(experiment_dir_name):
    """Plots scores on hyperparameter grid for Experiment 5.

    This is effectively the main method.

    :param experiment_dir_name: See documentation at top of file.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=experiment_dir_name
    )

    num_lag_time_sets = len(LAG_TIME_STRINGS)
    num_dropout_rates = len(CONV_LAYER_DROPOUT_RATES)
    num_l2_weights = len(L2_WEIGHTS)
    dimensions = (num_lag_time_sets, num_dropout_rates, num_l2_weights)

    aupd_matrix = numpy.full(dimensions, numpy.nan)
    max_csi_matrix = numpy.full(dimensions, numpy.nan)
    fss_matrix = numpy.full(dimensions, numpy.nan)
    bss_matrix = numpy.full(dimensions, numpy.nan)

    y_tick_labels = [
        '{0:.3f}'.format(d).replace('-1', '0')
        for d in CONV_LAYER_DROPOUT_RATES
    ]
    x_tick_labels = [
        r'10${0:.1f}$'.format(numpy.log10(w)) for w in L2_WEIGHTS
    ]
    y_axis_label = 'Conv-layer dropout rate'
    x_axis_label = r'L$_{2}$ weight'

    for i in range(num_lag_time_sets):
        for j in range(num_dropout_rates):
            for k in range(num_l2_weights):
                this_score_file_name = (
                    '{0:s}/lag-times-sec={1:2}_conv-dropout={2:.3f}_'
                    'l2-weight={3:.10f}/validation/evaluation/'
                    'advanced_scores_gridded=0.p'
                ).format(
                    experiment_dir_name, LAG_TIME_STRINGS[i],
                    CONV_LAYER_DROPOUT_RATES[j], L2_WEIGHTS[k]
                )

                print('Reading data from: "{0:s}"...'.format(
                    this_score_file_name
                ))
                t = evaluation.read_advanced_score_file(this_score_file_name)

                aupd_matrix[i, j, k] = (
                    gg_model_eval.get_area_under_perf_diagram(
                        pod_by_threshold=t[evaluation.POD_KEY].values,
                        success_ratio_by_threshold=
                        t[evaluation.SUCCESS_RATIO_KEY].values
                    )
                )

                max_csi_matrix[i, j, k] = numpy.nanmax(
                    t[evaluation.CSI_KEY].values
                )
                fss_matrix[i, j, k] = t[evaluation.FSS_KEY].values[0]
                bss_matrix[i, j, k] = (
                    t[evaluation.BRIER_SKILL_SCORE_KEY].values[0]
                )

    print(SEPARATOR_STRING)

    _print_ranking_one_score(score_matrix=aupd_matrix, score_name='AUPD')
    print(SEPARATOR_STRING)

    _print_ranking_one_score(score_matrix=max_csi_matrix, score_name='Max CSI')
    print(SEPARATOR_STRING)

    _print_ranking_one_score(score_matrix=fss_matrix, score_name='FSS')
    print(SEPARATOR_STRING)

    _print_ranking_one_score(score_matrix=bss_matrix, score_name='BSS')
    print(SEPARATOR_STRING)

    for i in range(num_lag_time_sets):

        # Plot AUPD for [i]th set of lag times.
        figure_object, axes_object = _plot_scores_2d(
            score_matrix=aupd_matrix[i, ...],
            min_colour_value=numpy.nanpercentile(aupd_matrix, 1),
            max_colour_value=numpy.nanpercentile(aupd_matrix, 99),
            x_tick_labels=x_tick_labels, y_tick_labels=y_tick_labels,
            colour_map_object=DEFAULT_COLOUR_MAP_OBJECT
        )
        axes_object.set_xlabel(x_axis_label)
        axes_object.set_ylabel(y_axis_label)

        title_string = 'AUPD with lag times of {0:s} s'.format(
            LAG_TIME_STRINGS[i].replace('-', ', ')
        )
        axes_object.set_title(title_string)

        figure_file_name = '{0:s}/lag-times-sec={1:s}_aupd_grid.jpg'.format(
            experiment_dir_name, LAG_TIME_STRINGS[i]
        )
        print('Saving figure to: "{0:s}"...'.format(figure_file_name))
        figure_object.savefig(
            figure_file_name, dpi=FIGURE_RESOLUTION_DPI,
            pad_inches=0, bbox_inches='tight'
        )
        pyplot.close(figure_object)

        # Plot max CSI for [i]th set of lag times.
        figure_object, axes_object = _plot_scores_2d(
            score_matrix=max_csi_matrix[i, ...],
            min_colour_value=numpy.nanpercentile(max_csi_matrix, 1),
            max_colour_value=numpy.nanpercentile(max_csi_matrix, 99),
            x_tick_labels=x_tick_labels, y_tick_labels=y_tick_labels,
            colour_map_object=DEFAULT_COLOUR_MAP_OBJECT
        )
        axes_object.set_xlabel(x_axis_label)
        axes_object.set_ylabel(y_axis_label)

        title_string = 'Max CSI with lag times of {0:s} s'.format(
            LAG_TIME_STRINGS[i].replace('-', ', ')
        )
        axes_object.set_title(title_string)

        figure_file_name = '{0:s}/lag-times-sec={1:s}_csi_grid.jpg'.format(
            experiment_dir_name, LAG_TIME_STRINGS[i]
        )
        print('Saving figure to: "{0:s}"...'.format(figure_file_name))
        figure_object.savefig(
            figure_file_name, dpi=FIGURE_RESOLUTION_DPI,
            pad_inches=0, bbox_inches='tight'
        )
        pyplot.close(figure_object)

        # Plot FSS for [i]th set of lag times.
        figure_object, axes_object = _plot_scores_2d(
            score_matrix=fss_matrix[i, ...],
            min_colour_value=numpy.nanpercentile(fss_matrix, 1),
            max_colour_value=numpy.nanpercentile(fss_matrix, 99),
            x_tick_labels=x_tick_labels, y_tick_labels=y_tick_labels,
            colour_map_object=DEFAULT_COLOUR_MAP_OBJECT
        )
        axes_object.set_xlabel(x_axis_label)
        axes_object.set_ylabel(y_axis_label)

        title_string = 'FSS with lag times of {0:s} s'.format(
            LAG_TIME_STRINGS[i].replace('-', ', ')
        )
        axes_object.set_title(title_string)

        figure_file_name = '{0:s}/lag-times-sec={1:s}_fss_grid.jpg'.format(
            experiment_dir_name, LAG_TIME_STRINGS[i]
        )
        print('Saving figure to: "{0:s}"...'.format(figure_file_name))
        figure_object.savefig(
            figure_file_name, dpi=FIGURE_RESOLUTION_DPI,
            pad_inches=0, bbox_inches='tight'
        )
        pyplot.close(figure_object)

        # Plot BSS for [i]th set of lag times.
        this_max_value = numpy.nanpercentile(numpy.absolute(bss_matrix), 99.)
        this_max_value = min([this_max_value, 1.])
        this_min_value = -1 * this_max_value

        figure_object, axes_object = _plot_scores_2d(
            score_matrix=bss_matrix[i, ...],
            min_colour_value=this_min_value, max_colour_value=this_max_value,
            x_tick_labels=x_tick_labels, y_tick_labels=y_tick_labels,
            colour_map_object=BSS_COLOUR_MAP_OBJECT
        )
        axes_object.set_xlabel(x_axis_label)
        axes_object.set_ylabel(y_axis_label)

        title_string = 'BSS with lag times of {0:s} s'.format(
            LAG_TIME_STRINGS[i].replace('-', ', ')
        )
        axes_object.set_title(title_string)

        figure_file_name = '{0:s}/lag-times-sec={1:s}_bss_grid.jpg'.format(
            experiment_dir_name, LAG_TIME_STRINGS[i]
        )
        file_system_utils.mkdir_recursive_if_necessary(
            file_name=figure_file_name
        )

        print('Saving figure to: "{0:s}"...'.format(figure_file_name))
        figure_object.savefig(
            figure_file_name, dpi=FIGURE_RESOLUTION_DPI,
            pad_inches=0, bbox_inches='tight'
        )
        pyplot.close(figure_object)


if __name__ == '__main__':
    INPUT_ARG_OBJECT = INPUT_ARG_PARSER.parse_args()

    _run(
        experiment_dir_name=getattr(INPUT_ARG_OBJECT, EXPERIMENT_DIR_ARG_NAME)
    )
