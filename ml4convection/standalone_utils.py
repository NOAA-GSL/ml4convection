"""Stand-alone Keras operations."""

import os
import sys
import numpy
import tensorflow.python.keras.backend as K

THIS_DIRECTORY_NAME = os.path.dirname(os.path.realpath(
    os.path.join(os.getcwd(), os.path.expanduser(__file__))
))
sys.path.append(os.path.normpath(os.path.join(THIS_DIRECTORY_NAME, '..')))

import error_checking


def do_2d_pooling(feature_matrix, do_max_pooling, window_size_px=2):
    """Pools 2-D feature maps.

    E = number of examples
    M = number of rows before pooling
    N = number of columns before pooling
    C = number of channels
    m = number of rows after pooling
    n = number of columns after pooling

    :param feature_matrix: E-by-M-by-N-by-C numpy array of feature values.
    :param do_max_pooling: Boolean flag.  If True, will do max-pooling.  If
        False, will do average-pooling.
    :param window_size_px: Window size (pixels).  This will be the number of
        rows and columns in the pooling window.
    :return: feature_matrix: E-by-m-by-n-by-C numpy array of new feature values.
    """

    error_checking.assert_is_numpy_array_without_nan(feature_matrix)
    error_checking.assert_is_numpy_array(feature_matrix, num_dimensions=4)
    error_checking.assert_is_boolean(do_max_pooling)
    error_checking.assert_is_integer(window_size_px)
    error_checking.assert_is_geq(window_size_px, 2)

    feature_tensor = K.pool2d(
        x=K.variable(feature_matrix),
        pool_mode='max' if do_max_pooling else 'avg',
        pool_size=(window_size_px, window_size_px),
        strides=(window_size_px, window_size_px),
        padding='valid', data_format='channels_last'
    )

    return feature_tensor.numpy()


def do_1d_pooling(feature_matrix, do_max_pooling, window_size_px=2):
    """Pools 1-D feature maps.

    E = number of examples
    P = number of pixels before pooling
    C = number of channels
    p = number of pixels after pooling

    :param feature_matrix: E-by-P-by-C numpy array of feature values.
    :param do_max_pooling: See doc for `do_2d_pooling`.
    :param window_size_px: Same.
    :return: feature_matrix: E-by-p-by-C numpy array of new feature values.
    """

    error_checking.assert_is_numpy_array_without_nan(feature_matrix)
    error_checking.assert_is_numpy_array(feature_matrix, num_dimensions=3)
    error_checking.assert_is_integer(window_size_px)
    error_checking.assert_is_geq(window_size_px, 2)

    feature_matrix = numpy.expand_dims(feature_matrix, axis=-2)
    feature_matrix = numpy.repeat(
        feature_matrix, repeats=window_size_px, axis=-2
    )

    feature_matrix = do_2d_pooling(
        feature_matrix=feature_matrix, do_max_pooling=do_max_pooling,
        window_size_px=window_size_px
    )

    return feature_matrix[..., 0, :]