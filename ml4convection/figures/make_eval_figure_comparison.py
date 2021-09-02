"""Makes figure with ungridded evaluation for several models."""

import os
import argparse
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.plotting import imagemagick_utils

CONVERT_EXE_NAME = '/usr/bin/convert'
PANEL_LETTER_FONT_SIZE = 200
MODEL_DESCRIPTION_FONT_SIZE = 350
TITLE_FONT_NAME = 'DejaVu-Sans-Bold'

PANEL_SIZE_PX = int(5e6)
CONCAT_FIGURE_SIZE_PX = int(2e7)

GRIDDED_EVAL_DIRS_ARG_NAME = 'input_gridded_eval_dir_names'
UNGRIDDED_EVAL_DIRS_ARG_NAME = 'input_ungridded_eval_dir_names'
MODEL_DESCRIPTIONS_ARG_NAME = 'model_description_strings'
OUTPUT_DIR_ARG_NAME = 'output_dir_name'

GRIDDED_EVAL_DIRS_HELP_STRING = (
    'Names of directories with figures to concatenate, created by '
    'plot_gridded_evaluation.py.  One directory per model.'
)
UNGRIDDED_EVAL_DIRS_HELP_STRING = (
    'Names of directories with other figures to concatenate, created by '
    'plot_evaluation.py.  One directory per model.'
)
MODEL_DESCRIPTIONS_HELP_STRING = (
    'Model descriptions.  This should be a space-separated list of strings, '
    'with one string per model.  Underscores within each string will be '
    'replaced by spaces.'
)
OUTPUT_DIR_HELP_STRING = (
    'Name of output directory.  New figures (most importantly, the paneled '
    'figure with all evaluation) will be saved here.'
)

INPUT_ARG_PARSER = argparse.ArgumentParser()
INPUT_ARG_PARSER.add_argument(
    '--' + GRIDDED_EVAL_DIRS_ARG_NAME, type=str, nargs='+', required=True,
    help=GRIDDED_EVAL_DIRS_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + UNGRIDDED_EVAL_DIRS_ARG_NAME, type=str, nargs='+', required=True,
    help=UNGRIDDED_EVAL_DIRS_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + MODEL_DESCRIPTIONS_ARG_NAME, type=str, nargs='+', required=True,
    help=MODEL_DESCRIPTIONS_HELP_STRING
)
INPUT_ARG_PARSER.add_argument(
    '--' + OUTPUT_DIR_ARG_NAME, type=str, required=True,
    help=OUTPUT_DIR_HELP_STRING
)


def _overlay_text(
        image_file_name, x_offset_from_left_px, y_offset_from_top_px,
        text_string, font_size, use_north_gravity):
    """Overlays text on image.

    :param image_file_name: Path to image file.
    :param x_offset_from_left_px: Left-relative x-coordinate (pixels).
    :param y_offset_from_top_px: Top-relative y-coordinate (pixels).
    :param text_string: String to overlay.
    :param font_size: Font size.
    :param use_north_gravity: Boolean flag.
    :raises: ValueError: if ImageMagick command (which is ultimately a Unix
        command) fails.
    """

    command_string = '"{0:s}" "{1:s}"'.format(CONVERT_EXE_NAME, image_file_name)
    if use_north_gravity:
        command_string += ' -gravity North'

    command_string += (
        ' -pointsize {0:d} -font "{1:s}" '
        '-fill "rgb(0, 0, 0)" -annotate {2:+d}{3:+d} "{4:s}" "{5:s}"'
    ).format(
        font_size, TITLE_FONT_NAME,
        x_offset_from_left_px, y_offset_from_top_px, text_string,
        image_file_name
    )

    exit_code = os.system(command_string)
    if exit_code == 0:
        return

    raise ValueError(imagemagick_utils.ERROR_STRING)


def _run(gridded_eval_dir_names, ungridded_eval_dir_names,
         model_description_strings, output_dir_name):
    """Makes figure with ungridded evaluation for several models.

    This is effectively the main method.

    :param gridded_eval_dir_names: See documentation at top of file.
    :param ungridded_eval_dir_names: Same.
    :param model_description_strings: Same.
    :param output_dir_name: Same.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    num_models = len(gridded_eval_dir_names)
    assert len(ungridded_eval_dir_names) == num_models
    assert len(model_description_strings) == num_models

    model_description_strings_dashed = [
        s.replace('_', '-') for s in model_description_strings
    ]
    # model_description_strings = [
    #     s.replace('_', ' ') for s in model_description_strings
    # ]

    pathless_panel_file_names = [
        'attributes_diagram.jpg', 'performance_diagram.jpg',
        'mean_forecast_prob.jpg'
    ]
    num_scores = len(pathless_panel_file_names)

    panel_file_names = []
    resized_panel_file_names = []

    for i in range(num_models):
        for j in range(num_scores):
            this_file_name = '{0:s}/{1:s}'.format(
                gridded_eval_dir_names[i] if j == num_scores - 1
                else ungridded_eval_dir_names[j],
                pathless_panel_file_names[j]
            )
            panel_file_names.append(this_file_name)

            this_file_name = '{0:s}/{1:s}_{2:s}.jpg'.format(
                output_dir_name, pathless_panel_file_names[j].split('.')[0],
                model_description_strings_dashed[i]
            )
            resized_panel_file_names.append(this_file_name)

    letter_label = None

    for k in range(len(panel_file_names)):
        print('Resizing panel and saving to: "{0:s}"...'.format(
            resized_panel_file_names[k]
        ))

        if letter_label is None:
            letter_label = 'a'
        else:
            letter_label = chr(ord(letter_label) + 1)

        imagemagick_utils.trim_whitespace(
            input_file_name=panel_file_names[k],
            output_file_name=resized_panel_file_names[k]
        )
        _overlay_text(
            image_file_name=resized_panel_file_names[k],
            x_offset_from_left_px=0, y_offset_from_top_px=225,
            text_string='({0:s})'.format(letter_label),
            font_size=PANEL_LETTER_FONT_SIZE, use_north_gravity=False
        )

        imagemagick_utils.trim_whitespace(
            input_file_name=resized_panel_file_names[k],
            output_file_name=resized_panel_file_names[k]
        )
        imagemagick_utils.resize_image(
            input_file_name=resized_panel_file_names[k],
            output_file_name=resized_panel_file_names[k],
            output_size_pixels=PANEL_SIZE_PX
        )

    concat_figure_file_name = '{0:s}/evaluation_comparison.jpg'.format(
        output_dir_name
    )
    print('Concatenating panels to: "{0:s}"...'.format(concat_figure_file_name))

    imagemagick_utils.concatenate_images(
        input_file_names=resized_panel_file_names,
        output_file_name=concat_figure_file_name,
        num_panel_rows=num_models, num_panel_columns=num_scores
    )
    imagemagick_utils.resize_image(
        input_file_name=concat_figure_file_name,
        output_file_name=concat_figure_file_name,
        output_size_pixels=CONCAT_FIGURE_SIZE_PX
    )
    imagemagick_utils.trim_whitespace(
        input_file_name=concat_figure_file_name,
        output_file_name=concat_figure_file_name
    )


if __name__ == '__main__':
    INPUT_ARG_OBJECT = INPUT_ARG_PARSER.parse_args()

    _run(
        gridded_eval_dir_names=getattr(
            INPUT_ARG_OBJECT, GRIDDED_EVAL_DIRS_ARG_NAME
        ),
        ungridded_eval_dir_names=getattr(
            INPUT_ARG_OBJECT, UNGRIDDED_EVAL_DIRS_ARG_NAME
        ),
        model_description_strings=getattr(
            INPUT_ARG_OBJECT, MODEL_DESCRIPTIONS_ARG_NAME
        ),
        output_dir_name=getattr(INPUT_ARG_OBJECT, OUTPUT_DIR_ARG_NAME)
    )
