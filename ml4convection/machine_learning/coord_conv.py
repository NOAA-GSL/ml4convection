"""Implements CoordConv solution from Liu et al. (2018).

https://arxiv.org/abs/1807.03247
"""

import numpy
from keras import backend as K
from gewittergefahr.gg_utils import error_checking


def add_spatial_coords_2d(
        input_layer_object, test_mode=False, input_dimensions=None):
    """Adds spatial coords to layer with two spatial dimensions.

    :param input_layer_object: Input layer (instance of `keras.layers.Layer`).
    :param test_mode: Leave this alone.
    :param input_dimensions: Leave this alone.
    :return: output_layer_object: Same but with two extra output channels, one
        for each spatial coordinate.
    """

    error_checking.assert_is_boolean(test_mode)

    if test_mode:
        error_checking.assert_is_numpy_array(input_dimensions, num_dimensions=1)
        error_checking.assert_is_integer_numpy_array(input_dimensions)
        error_checking.assert_is_greater_numpy_array(input_dimensions, 0)

        error_checking.assert_is_geq(len(input_dimensions), 4)
        error_checking.assert_is_leq(len(input_dimensions), 4)
    else:
        input_dimensions = K.shape(input_layer_object)
        input_dimensions = [input_dimensions[i] for i in range(4)]

    num_examples = input_dimensions[0]
    num_grid_rows = input_dimensions[1]
    num_grid_columns = input_dimensions[2]

    one_matrix_for_y = K.ones(
        K.stack([num_examples, num_grid_columns]),
        dtype='int64' if test_mode else 'int32'
    )
    one_matrix_for_y = K.expand_dims(one_matrix_for_y, axis=-1)

    y_coord_matrix = K.expand_dims(K.arange(0, num_grid_rows), axis=0)
    y_coord_matrix = K.tile(
        x=y_coord_matrix, n=K.stack([num_examples, 1])
    )
    y_coord_matrix = K.expand_dims(y_coord_matrix, axis=1)
    y_coord_matrix = K.batch_dot(one_matrix_for_y, y_coord_matrix, axes=[2, 1])
    y_coord_matrix = K.expand_dims(y_coord_matrix, axis=-1)
    y_coord_matrix = K.permute_dimensions(y_coord_matrix, [0, 2, 1, 3])

    y_coord_matrix = K.cast(y_coord_matrix, K.floatx())
    y_coord_matrix = y_coord_matrix / K.cast(num_grid_rows - 1, K.floatx())
    y_coord_matrix = (y_coord_matrix * 2) - 1.

    one_matrix_for_x = K.ones(
        K.stack([num_examples, num_grid_rows]),
        dtype='int64' if test_mode else 'int32'
    )
    one_matrix_for_x = K.expand_dims(one_matrix_for_x, axis=1)

    x_coord_matrix = K.expand_dims(K.arange(0, num_grid_columns), axis=0)
    x_coord_matrix = K.tile(
        x=x_coord_matrix, n=K.stack([num_examples, 1])
    )
    x_coord_matrix = K.expand_dims(x_coord_matrix, axis=-1)

    x_coord_matrix = K.batch_dot(x_coord_matrix, one_matrix_for_x, axes=[2, 1])
    x_coord_matrix = K.expand_dims(x_coord_matrix, axis=-1)
    x_coord_matrix = K.permute_dimensions(x_coord_matrix, [0, 2, 1, 3])

    x_coord_matrix = K.cast(x_coord_matrix, K.floatx())
    x_coord_matrix = x_coord_matrix / K.cast(num_grid_columns - 1, K.floatx())
    x_coord_matrix = (x_coord_matrix * 2) - 1.

    if test_mode:
        return numpy.concatenate((x_coord_matrix, y_coord_matrix), axis=-1)

    return K.concatenate(
        [input_layer_object, x_coord_matrix, y_coord_matrix], axis=-1
    )


def add_spatial_coords_2d_with_time(
        input_layer_object, num_times, test_mode=False, input_dimensions=None):
    """Adds spatial coords to layer with two spatial dim and time dim.

    :param input_layer_object: Input layer (instance of `keras.layers.Layer`).
    :param num_times: Number of times.
    :param test_mode: Leave this alone.
    :param input_dimensions: Leave this alone.
    :return: output_layer_object: Same but with two extra output channels, one
        for each spatial coordinate.
    """

    error_checking.assert_is_boolean(test_mode)

    if test_mode:
        error_checking.assert_is_numpy_array(input_dimensions, num_dimensions=1)
        error_checking.assert_is_integer_numpy_array(input_dimensions)
        error_checking.assert_is_greater_numpy_array(input_dimensions, 0)

        error_checking.assert_is_geq(len(input_dimensions), 5)
        error_checking.assert_is_leq(len(input_dimensions), 5)

        num_times = input_dimensions[-2]
    else:
        input_dimensions = K.shape(input_layer_object)
        input_dimensions = [input_dimensions[i] for i in range(5)]

    error_checking.assert_is_integer(num_times)
    error_checking.assert_is_geq(num_times, 1)

    num_examples = input_dimensions[0]
    num_grid_rows = input_dimensions[1]
    num_grid_columns = input_dimensions[2]

    one_matrix_for_y = K.ones(
        K.stack([num_examples, num_grid_columns]),
        dtype='int64' if test_mode else 'int32'
    )
    one_matrix_for_y = K.expand_dims(one_matrix_for_y, axis=-1)

    y_coord_matrix = K.expand_dims(K.arange(0, num_grid_rows), axis=0)
    y_coord_matrix = K.tile(
        x=y_coord_matrix, n=K.stack([num_examples, 1])
    )
    y_coord_matrix = K.expand_dims(y_coord_matrix, axis=1)
    y_coord_matrix = K.batch_dot(one_matrix_for_y, y_coord_matrix, axes=[2, 1])
    y_coord_matrix = K.expand_dims(y_coord_matrix, axis=-1)
    y_coord_matrix = K.permute_dimensions(y_coord_matrix, [0, 2, 1, 3])

    y_coord_matrix = K.expand_dims(y_coord_matrix, axis=-2)
    y_coord_matrix = K.repeat_elements(y_coord_matrix, rep=num_times, axis=-2)

    y_coord_matrix = K.cast(y_coord_matrix, K.floatx())
    y_coord_matrix = y_coord_matrix / K.cast(num_grid_rows - 1, K.floatx())
    y_coord_matrix = (y_coord_matrix * 2) - 1.

    one_matrix_for_x = K.ones(
        K.stack([num_examples, num_grid_rows]),
        dtype='int64' if test_mode else 'int32'
    )
    one_matrix_for_x = K.expand_dims(one_matrix_for_x, axis=1)

    x_coord_matrix = K.expand_dims(K.arange(0, num_grid_columns), axis=0)
    x_coord_matrix = K.tile(
        x=x_coord_matrix, n=K.stack([num_examples, 1])
    )
    x_coord_matrix = K.expand_dims(x_coord_matrix, axis=-1)

    x_coord_matrix = K.batch_dot(x_coord_matrix, one_matrix_for_x, axes=[2, 1])
    x_coord_matrix = K.expand_dims(x_coord_matrix, axis=-1)
    x_coord_matrix = K.permute_dimensions(x_coord_matrix, [0, 2, 1, 3])

    x_coord_matrix = K.expand_dims(x_coord_matrix, axis=-2)
    x_coord_matrix = K.repeat_elements(x_coord_matrix, rep=num_times, axis=-2)

    x_coord_matrix = K.cast(x_coord_matrix, K.floatx())
    x_coord_matrix = x_coord_matrix / K.cast(num_grid_columns - 1, K.floatx())
    x_coord_matrix = (x_coord_matrix * 2) - 1.

    if test_mode:
        return numpy.concatenate((x_coord_matrix, y_coord_matrix), axis=-1)

    return K.concatenate(
        [input_layer_object, x_coord_matrix, y_coord_matrix], axis=-1
    )
