"""Runs all unit tests in ml4convection library."""

import os
import sys
import glob

SEPARATOR_STRING = '\n\n' + '*' * 50 + '\n\n'


def _run():
    """Runs all unit tests in ml4rt library.

    This is effectively the main method.
    """

    script_dir_name = os.getcwd()
    top_library_dir_name = '/'.join(script_dir_name.split('/')[:-1])

    test_file_pattern = '{0:s}/*/*_test.py'.format(top_library_dir_name)
    test_file_names = glob.glob(test_file_pattern)

    for this_file_name in test_file_names:
        print('Running file: "{0:s}"...'.format(this_file_name))

        command_string = '"{0:s}" "{1:s}"'.format(
            sys.executable, this_file_name
        )

        os.system(command_string)
        print(SEPARATOR_STRING)


if __name__ == '__main__':
    _run()
