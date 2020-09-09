"""Methods for training and applying neural nets."""

import copy
import random
import os.path
import dill
import numpy
import keras
import tensorflow.keras as tf_keras
from gewittergefahr.gg_utils import time_conversion
from gewittergefahr.gg_utils import file_system_utils
from gewittergefahr.gg_utils import error_checking
from gewittergefahr.deep_learning import keras_metrics as custom_metrics
from ml4convection.io import satellite_io
from ml4convection.io import radar_io
from ml4convection.io import example_io
from ml4convection.utils import normalization
from ml4convection.utils import general_utils
from ml4convection.machine_learning import custom_losses

TOLERANCE = 1e-6

DAYS_TO_SECONDS = 86400
DATE_FORMAT = '%Y%m%d'

PLATEAU_PATIENCE_EPOCHS = 10
DEFAULT_LEARNING_RATE_MULTIPLIER = 0.5
PLATEAU_COOLDOWN_EPOCHS = 0
EARLY_STOPPING_PATIENCE_EPOCHS = 30
LOSS_PATIENCE = 0.

METRIC_FUNCTION_LIST = [
    custom_metrics.accuracy, custom_metrics.binary_accuracy,
    custom_metrics.binary_csi, custom_metrics.binary_frequency_bias,
    custom_metrics.binary_pod, custom_metrics.binary_pofd,
    custom_metrics.binary_peirce_score, custom_metrics.binary_success_ratio,
    custom_metrics.binary_focn
]

METRIC_FUNCTION_DICT = {
    'accuracy': custom_metrics.accuracy,
    'binary_accuracy': custom_metrics.binary_accuracy,
    'binary_csi': custom_metrics.binary_csi,
    'binary_frequency_bias': custom_metrics.binary_frequency_bias,
    'binary_pod': custom_metrics.binary_pod,
    'binary_pofd': custom_metrics.binary_pofd,
    'binary_peirce_score': custom_metrics.binary_peirce_score,
    'binary_success_ratio': custom_metrics.binary_success_ratio,
    'binary_focn': custom_metrics.binary_focn
}

SATELLITE_DIRECTORY_KEY = 'top_satellite_dir_name'
RADAR_DIRECTORY_KEY = 'top_radar_dir_name'
SPATIAL_DS_FACTOR_KEY = 'spatial_downsampling_factor'
BATCH_SIZE_KEY = 'num_examples_per_batch'
MAX_DAILY_EXAMPLES_KEY = 'max_examples_per_day_in_batch'
BAND_NUMBERS_KEY = 'band_numbers'
LEAD_TIME_KEY = 'lead_time_seconds'
REFL_THRESHOLD_KEY = 'reflectivity_threshold_dbz'
FIRST_VALID_DATE_KEY = 'first_valid_date_string'
LAST_VALID_DATE_KEY = 'last_valid_date_string'
NORMALIZATION_FILE_KEY = 'normalization_file_name'
UNIFORMIZE_FLAG_KEY = 'uniformize'
PREDICTOR_DIRECTORY_KEY = 'top_predictor_dir_name'
TARGET_DIRECTORY_KEY = 'top_target_dir_name'
NORMALIZE_FLAG_KEY = 'normalize'

DEFAULT_GENERATOR_OPTION_DICT = {
    SPATIAL_DS_FACTOR_KEY: 1,
    BATCH_SIZE_KEY: 256,
    MAX_DAILY_EXAMPLES_KEY: 64,
    BAND_NUMBERS_KEY: satellite_io.BAND_NUMBERS,
    REFL_THRESHOLD_KEY: 35.,
    NORMALIZE_FLAG_KEY: True,
    UNIFORMIZE_FLAG_KEY: True
}

VALID_DATE_KEY = 'valid_date_string'
NORMALIZATION_DICT_KEY = 'norm_dict_for_count'

NUM_EPOCHS_KEY = 'num_epochs'
NUM_TRAINING_BATCHES_KEY = 'num_training_batches_per_epoch'
TRAINING_OPTIONS_KEY = 'training_option_dict'
NUM_VALIDATION_BATCHES_KEY = 'num_validation_batches_per_epoch'
VALIDATION_OPTIONS_KEY = 'validation_option_dict'
EARLY_STOPPING_KEY = 'do_early_stopping'
PLATEAU_LR_MUTIPLIER_KEY = 'plateau_lr_multiplier'
CLASS_WEIGHTS_KEY = 'class_weights'

METADATA_KEYS = [
    NUM_EPOCHS_KEY, NUM_TRAINING_BATCHES_KEY, TRAINING_OPTIONS_KEY,
    NUM_VALIDATION_BATCHES_KEY, VALIDATION_OPTIONS_KEY,
    EARLY_STOPPING_KEY, PLATEAU_LR_MUTIPLIER_KEY, CLASS_WEIGHTS_KEY
]

PREDICTOR_MATRIX_KEY = 'predictor_matrix'
TARGET_MATRIX_KEY = 'target_matrix'
VALID_TIMES_KEY = 'valid_times_unix_sec'
LATITUDES_KEY = 'latitudes_deg_n'
LONGITUDES_KEY = 'longitudes_deg_e'


def _check_generator_args(option_dict):
    """Error-checks input arguments for generator.

    :param option_dict: See doc for `generator_from_raw_files`.
    :return: option_dict: Same as input, except defaults may have been added.
    """

    orig_option_dict = option_dict.copy()
    option_dict = DEFAULT_GENERATOR_OPTION_DICT.copy()
    option_dict.update(orig_option_dict)

    error_checking.assert_is_numpy_array(
        option_dict[BAND_NUMBERS_KEY], num_dimensions=1
    )
    error_checking.assert_is_integer_numpy_array(option_dict[BAND_NUMBERS_KEY])

    error_checking.assert_is_integer(option_dict[BATCH_SIZE_KEY])
    error_checking.assert_is_geq(option_dict[BATCH_SIZE_KEY], 2)
    error_checking.assert_is_integer(option_dict[SPATIAL_DS_FACTOR_KEY])
    error_checking.assert_is_geq(option_dict[SPATIAL_DS_FACTOR_KEY], 1)
    error_checking.assert_is_integer(option_dict[MAX_DAILY_EXAMPLES_KEY])
    error_checking.assert_is_geq(option_dict[MAX_DAILY_EXAMPLES_KEY], 2)
    error_checking.assert_is_integer(option_dict[LEAD_TIME_KEY])
    error_checking.assert_is_geq(option_dict[LEAD_TIME_KEY], 0)
    error_checking.assert_is_less_than(
        option_dict[LEAD_TIME_KEY], DAYS_TO_SECONDS
    )
    error_checking.assert_is_greater(option_dict[REFL_THRESHOLD_KEY], 0.)

    return option_dict


def _check_inference_args(predictor_matrix, num_examples_per_batch, verbose):
    """Error-checks input arguments for inference.

    :param predictor_matrix: See doc for `apply_model`.
    :param num_examples_per_batch: Batch size.
    :param verbose: Boolean flag.  If True, will print progress messages during
        inference.
    :return: num_examples_per_batch: Batch size (may be different than input).
    """

    error_checking.assert_is_numpy_array_without_nan(predictor_matrix)
    num_examples = predictor_matrix.shape[0]

    if num_examples_per_batch is None:
        num_examples_per_batch = num_examples + 0
    else:
        error_checking.assert_is_integer(num_examples_per_batch)
        # error_checking.assert_is_geq(num_examples_per_batch, 100)
        error_checking.assert_is_geq(num_examples_per_batch, 1)

    num_examples_per_batch = min([num_examples_per_batch, num_examples])
    error_checking.assert_is_boolean(verbose)

    return num_examples_per_batch


def _read_raw_inputs_one_day(
        valid_date_string, satellite_file_names, band_numbers,
        norm_dict_for_count, uniformize, radar_file_names, lead_time_seconds,
        reflectivity_threshold_dbz, spatial_downsampling_factor,
        num_examples_to_read, return_coords):
    """Reads raw inputs (satellite and radar files) for one day.

    E = number of examples
    M = number of rows in grid
    N = number of columns in grid

    :param valid_date_string: Valid date (format "yyyymmdd").
    :param satellite_file_names: 1-D list of paths to satellite files (readable
        by `satellite_io.read_file`).
    :param band_numbers: See doc for `generator_from_raw_files`.
    :param norm_dict_for_count: Dictionary returned by
        `normalization.read_file`.  Will use this to normalize satellite data.
        If None, will not normalize.
    :param uniformize: See doc for `generator_from_raw_files`.
    :param radar_file_names: 1-D list of paths to radar files (readable by
        `radar_io.read_2d_file`).
    :param lead_time_seconds: See doc for `generator_from_raw_files`.
    :param reflectivity_threshold_dbz: Same.
    :param spatial_downsampling_factor: Same.
    :param num_examples_to_read: Number of examples to read.
    :param return_coords: Boolean flag.  If True, will return latitudes and
        longitudes for grid points.

    :return: data_dict: Dictionary with the following keys.
    data_dict['predictor_matrix']: See doc for `generator_from_raw_files`.
    data_dict['target_matrix']: Same.
    data_dict['valid_times_unix_sec']: length-E numpy array of valid times.
    data_dict['latitudes_deg_n']: length-M numpy array of latitudes (deg N).
        If `return_coords == False`, this is None.
    data_dict['longitudes_deg_e']: length-N numpy array of longitudes (deg E).
        If `return_coords == False`, this is None.
    """

    radar_date_strings = [
        radar_io.file_name_to_date(f) for f in radar_file_names
    ]
    index = radar_date_strings.index(valid_date_string)
    desired_radar_file_name = radar_file_names[index]

    satellite_date_strings = [
        satellite_io.file_name_to_date(f) for f in satellite_file_names
    ]
    index = satellite_date_strings.index(valid_date_string)
    desired_satellite_file_names = [satellite_file_names[index]]

    if lead_time_seconds > 0:
        desired_satellite_file_names.insert(0, satellite_file_names[index - 1])

    print('Reading data from: "{0:s}"...'.format(desired_radar_file_name))
    radar_dict = radar_io.read_2d_file(desired_radar_file_name)

    satellite_dicts = []

    for this_file_name in desired_satellite_file_names:
        print('Reading data from: "{0:s}"...'.format(this_file_name))
        this_satellite_dict = satellite_io.read_file(
            netcdf_file_name=this_file_name, read_temperatures=False,
            read_counts=True
        )
        this_satellite_dict = satellite_io.subset_by_band(
            satellite_dict=this_satellite_dict, band_numbers=band_numbers
        )
        satellite_dicts.append(this_satellite_dict)

    satellite_dict = satellite_io.concat_data(satellite_dicts)

    assert numpy.allclose(
        radar_dict[radar_io.LATITUDES_KEY],
        satellite_dict[satellite_io.LATITUDES_KEY],
        atol=TOLERANCE
    )

    assert numpy.allclose(
        radar_dict[radar_io.LONGITUDES_KEY],
        satellite_dict[satellite_io.LONGITUDES_KEY],
        atol=TOLERANCE
    )

    valid_times_unix_sec = radar_dict[radar_io.VALID_TIMES_KEY]
    init_times_unix_sec = valid_times_unix_sec - lead_time_seconds

    good_flags = numpy.array([
        t in satellite_dict[satellite_io.VALID_TIMES_KEY]
        for t in init_times_unix_sec
    ], dtype=bool)

    if not numpy.any(good_flags):
        return None

    good_indices = numpy.where(good_flags)[0]
    valid_times_unix_sec = valid_times_unix_sec[good_indices]
    init_times_unix_sec = init_times_unix_sec[good_indices]

    radar_dict = radar_io.subset_by_time(
        radar_dict=radar_dict, desired_times_unix_sec=valid_times_unix_sec
    )[0]
    satellite_dict = satellite_io.subset_by_time(
        satellite_dict=satellite_dict,
        desired_times_unix_sec=init_times_unix_sec
    )[0]
    num_examples = len(good_indices)

    if num_examples >= num_examples_to_read:
        desired_indices = numpy.linspace(
            0, num_examples - 1, num=num_examples, dtype=int
        )
        desired_indices = numpy.random.choice(
            desired_indices, size=num_examples_to_read, replace=False
        )

        radar_dict = radar_io.subset_by_index(
            radar_dict=radar_dict, desired_indices=desired_indices
        )
        satellite_dict = satellite_io.subset_by_index(
            satellite_dict=satellite_dict, desired_indices=desired_indices
        )

    if spatial_downsampling_factor > 1:
        satellite_dict, radar_dict = example_io.downsample_data_in_space(
            satellite_dict=satellite_dict, radar_dict=radar_dict,
            downsampling_factor=spatial_downsampling_factor,
            change_coordinates=return_coords
        )

    if norm_dict_for_count is not None:
        satellite_dict = normalization.normalize_data(
            satellite_dict=satellite_dict, uniformize=uniformize,
            norm_dict_for_count=norm_dict_for_count
        )

    predictor_matrix = satellite_dict[satellite_io.BRIGHTNESS_COUNT_KEY]
    print('Mean reflectivity = {0:.2f} dBZ'.format(
        numpy.mean(radar_dict[radar_io.COMPOSITE_REFL_KEY])
    ))
    print('Threshold = {0:.2f} dBZ'.format(reflectivity_threshold_dbz))

    target_matrix = (
        radar_dict[radar_io.COMPOSITE_REFL_KEY] >= reflectivity_threshold_dbz
    ).astype(int)

    print('Number of target values in batch = {0:d} ... mean = {1:.3g}'.format(
        target_matrix.size, numpy.mean(target_matrix)
    ))

    data_dict = {
        PREDICTOR_MATRIX_KEY: predictor_matrix,
        TARGET_MATRIX_KEY: numpy.expand_dims(target_matrix, axis=-1),
        VALID_TIMES_KEY: valid_times_unix_sec,
        LATITUDES_KEY: None,
        LONGITUDES_KEY: None
    }

    if return_coords:
        data_dict[LATITUDES_KEY] = radar_dict[radar_io.LATITUDES_KEY]
        data_dict[LONGITUDES_KEY] = radar_dict[radar_io.LONGITUDES_KEY]

    return data_dict


def _read_preprocessed_inputs_one_day(
        valid_date_string, predictor_file_names, band_numbers,
        normalize, uniformize, target_file_names, lead_time_seconds,
        num_examples_to_read, return_coords):
    """Reads pre-processed inputs (predictor and target files) for one day.

    :param valid_date_string: Valid date (format "yyyymmdd").
    :param predictor_file_names: 1-D list of paths to predictor files (readable
        by `example_io.read_predictor_file`).
    :param band_numbers: See doc for `generator_from_preprocessed_files`.
    :param normalize: Same.
    :param uniformize: Same.
    :param target_file_names: 1-D list of paths to target files (readable by
        `example_io.read_target_file`).
    :param lead_time_seconds: See doc for `generator_from_preprocessed_files`.
    :param num_examples_to_read: Number of examples to read.
    :param return_coords: Boolean flag.  If True, will return latitudes and
        longitudes for grid points.
    :return: data_dict: See doc for `_read_raw_inputs_one_day`.
    """

    uniformize = uniformize and normalize

    target_date_strings = [
        example_io.target_file_name_to_date(f) for f in target_file_names
    ]
    index = target_date_strings.index(valid_date_string)
    desired_target_file_name = target_file_names[index]

    predictor_date_strings = [
        example_io.predictor_file_name_to_date(f) for f in predictor_file_names
    ]
    index = predictor_date_strings.index(valid_date_string)
    desired_predictor_file_names = [predictor_file_names[index]]

    if lead_time_seconds > 0:
        desired_predictor_file_names.insert(0, predictor_file_names[index - 1])

    print('Reading data from: "{0:s}"...'.format(desired_target_file_name))
    target_dict = example_io.read_target_file(
        netcdf_file_name=desired_target_file_name,
        read_targets=True, read_reflectivities=False
    )

    predictor_dicts = []

    for this_file_name in desired_predictor_file_names:
        print('Reading data from: "{0:s}"...'.format(this_file_name))
        this_predictor_dict = example_io.read_predictor_file(
            netcdf_file_name=this_file_name,
            read_unnormalized=not normalize,
            read_normalized=normalize and not uniformize,
            read_unif_normalized=normalize and uniformize
        )
        this_predictor_dict = example_io.subset_predictors_by_band(
            predictor_dict=this_predictor_dict, band_numbers=band_numbers
        )
        predictor_dicts.append(this_predictor_dict)

    predictor_dict = example_io.concat_predictor_data(predictor_dicts)

    assert numpy.allclose(
        target_dict[example_io.LATITUDES_KEY],
        predictor_dict[example_io.LATITUDES_KEY],
        atol=TOLERANCE
    )

    assert numpy.allclose(
        target_dict[example_io.LONGITUDES_KEY],
        predictor_dict[example_io.LONGITUDES_KEY],
        atol=TOLERANCE
    )

    valid_times_unix_sec = target_dict[example_io.VALID_TIMES_KEY]
    init_times_unix_sec = valid_times_unix_sec - lead_time_seconds

    good_flags = numpy.array([
        t in predictor_dict[example_io.VALID_TIMES_KEY]
        for t in init_times_unix_sec
    ], dtype=bool)

    if not numpy.any(good_flags):
        return None

    good_indices = numpy.where(good_flags)[0]
    valid_times_unix_sec = valid_times_unix_sec[good_indices]
    init_times_unix_sec = init_times_unix_sec[good_indices]

    predictor_dict = example_io.subset_by_time(
        predictor_dict=predictor_dict,
        desired_times_unix_sec=init_times_unix_sec
    )[0]
    target_dict = example_io.subset_by_time(
        target_dict=target_dict, desired_times_unix_sec=init_times_unix_sec
    )[1]
    num_examples = len(good_indices)

    if num_examples >= num_examples_to_read:
        desired_indices = numpy.linspace(
            0, num_examples - 1, num=num_examples, dtype=int
        )
        desired_indices = numpy.random.choice(
            desired_indices, size=num_examples_to_read, replace=False
        )
        predictor_dict, target_dict = example_io.subset_by_index(
            predictor_dict=predictor_dict, target_dict=target_dict,
            desired_indices=desired_indices
        )

    if normalize:
        if uniformize:
            predictor_matrix = (
                predictor_dict[example_io.PREDICTOR_MATRIX_UNIF_NORM_KEY]
            )
        else:
            predictor_matrix = (
                predictor_dict[example_io.PREDICTOR_MATRIX_NORM_KEY]
            )
    else:
        predictor_matrix = (
            predictor_dict[example_io.PREDICTOR_MATRIX_UNNORM_KEY]
        )

    target_matrix = target_dict[example_io.TARGET_MATRIX_KEY]

    print('Number of target values in batch = {0:d} ... mean = {1:.3g}'.format(
        target_matrix.size, numpy.mean(target_matrix)
    ))

    data_dict = {
        PREDICTOR_MATRIX_KEY: predictor_matrix,
        TARGET_MATRIX_KEY: numpy.expand_dims(target_matrix, axis=-1),
        VALID_TIMES_KEY: valid_times_unix_sec,
        LATITUDES_KEY: None,
        LONGITUDES_KEY: None
    }

    if return_coords:
        data_dict[LATITUDES_KEY] = predictor_dict[example_io.LATITUDES_KEY]
        data_dict[LONGITUDES_KEY] = predictor_dict[example_io.LONGITUDES_KEY]

    return data_dict


def _write_metafile(
        dill_file_name, num_epochs, num_training_batches_per_epoch,
        training_option_dict, num_validation_batches_per_epoch,
        validation_option_dict, do_early_stopping, plateau_lr_multiplier,
        class_weights):
    """Writes metadata to Dill file.

    :param dill_file_name: Path to output file.
    :param num_epochs: See doc for `train_model_from_raw_files`.
    :param num_training_batches_per_epoch: Same.
    :param training_option_dict: Same.
    :param num_validation_batches_per_epoch: Same.
    :param validation_option_dict: Same.
    :param do_early_stopping: Same.
    :param plateau_lr_multiplier: Same.
    :param class_weights: Same.
    """

    metadata_dict = {
        NUM_EPOCHS_KEY: num_epochs,
        NUM_TRAINING_BATCHES_KEY: num_training_batches_per_epoch,
        TRAINING_OPTIONS_KEY: training_option_dict,
        NUM_VALIDATION_BATCHES_KEY: num_validation_batches_per_epoch,
        VALIDATION_OPTIONS_KEY: validation_option_dict,
        EARLY_STOPPING_KEY: do_early_stopping,
        PLATEAU_LR_MUTIPLIER_KEY: plateau_lr_multiplier,
        CLASS_WEIGHTS_KEY: class_weights
    }

    file_system_utils.mkdir_recursive_if_necessary(file_name=dill_file_name)

    dill_file_handle = open(dill_file_name, 'wb')
    dill.dump(metadata_dict, dill_file_handle)
    dill_file_handle.close()


def _find_days_with_raw_inputs(
        satellite_file_names, radar_file_names, lead_time_seconds):
    """Finds days with raw inputs (both radar and satellite file).

    :param satellite_file_names: See doc for `_read_raw_inputs_one_day`.
    :param radar_file_names: Same.
    :param lead_time_seconds: Same.
    :return: valid_date_strings: List of valid dates (radar dates) for which
        both satellite and radar data exist, in format "yyyymmdd".
    """

    satellite_date_strings = [
        satellite_io.file_name_to_date(f) for f in satellite_file_names
    ]
    radar_date_strings = [
        radar_io.file_name_to_date(f) for f in radar_file_names
    ]
    valid_date_strings = []

    for this_radar_date_string in radar_date_strings:
        if this_radar_date_string not in satellite_date_strings:
            continue

        if lead_time_seconds > 0:
            if (
                    general_utils.get_previous_date(this_radar_date_string)
                    not in satellite_date_strings
            ):
                continue

        valid_date_strings.append(this_radar_date_string)

    return valid_date_strings


def _find_days_with_preprocessed_inputs(
        predictor_file_names, target_file_names, lead_time_seconds):
    """Finds days with pre-processed inputs (both predictor and target file).

    :param predictor_file_names: See doc for
        `_read_preprocessed_inputs_one_day`.
    :param target_file_names: Same.
    :param lead_time_seconds: Same.
    :return: valid_date_strings: List of valid dates (target dates) for which
        both predictors and targets exist, in format "yyyymmdd".
    """

    predictor_date_strings = [
        example_io.predictor_file_name_to_date(f) for f in predictor_file_names
    ]
    target_date_strings = [
        example_io.target_file_name_to_date(f) for f in target_file_names
    ]
    valid_date_strings = []

    for this_target_date_string in target_date_strings:
        if this_target_date_string not in predictor_date_strings:
            continue

        if lead_time_seconds > 0:
            if (
                    general_utils.get_previous_date(this_target_date_string)
                    not in predictor_date_strings
            ):
                continue

        valid_date_strings.append(this_target_date_string)

    return valid_date_strings


def check_class_weights(class_weights):
    """Error-checks class weights.

    :param class_weights: length-2 numpy with class weights for loss function.
        Elements will be interpreted as
        (negative_class_weight, positive_class_weight).
    """

    error_checking.assert_is_numpy_array(
        class_weights, exact_dimensions=numpy.array([2], dtype=int)
    )
    error_checking.assert_is_greater_numpy_array(class_weights, 0.)


def create_data_from_raw_files(option_dict, return_coords=False):
    """Creates input data from raw (satellite and radar) files.

    This method is the same as `generator_from_raw_files`, except that it
    returns all the data at once, rather than generating batches on the fly.

    :param option_dict: Dictionary with the following keys.
    option_dict['top_satellite_dir_name']: See doc for
        `generator_from_raw_files`.
    option_dict['top_radar_dir_name']: Same.
    option_dict['spatial_downsampling_factor']: Same.
    option_dict['band_numbers']: Same.
    option_dict['lead_time_seconds']: Same.
    option_dict['reflectivity_threshold_dbz']: Same.
    option_dict['valid_date_string']: Valid date (format "yyyymmdd").  Will
        create examples with radar data valid on this day.
    option_dict['norm_dict_for_count']: See doc for `_read_raw_inputs_one_day`.
    option_dict['uniformize']: See doc for `generator_from_raw_files`.

    :param return_coords: See doc for `_read_raw_inputs_one_day`.
    :return: data_dict: Same.
    """

    option_dict = _check_generator_args(option_dict)
    error_checking.assert_is_boolean(return_coords)

    top_satellite_dir_name = option_dict[SATELLITE_DIRECTORY_KEY]
    top_radar_dir_name = option_dict[RADAR_DIRECTORY_KEY]
    spatial_downsampling_factor = option_dict[SPATIAL_DS_FACTOR_KEY]
    band_numbers = option_dict[BAND_NUMBERS_KEY]
    lead_time_seconds = option_dict[LEAD_TIME_KEY]
    reflectivity_threshold_dbz = option_dict[REFL_THRESHOLD_KEY]
    valid_date_string = option_dict[VALID_DATE_KEY]
    norm_dict_for_count = option_dict[NORMALIZATION_DICT_KEY]
    uniformize = option_dict[UNIFORMIZE_FLAG_KEY]

    if lead_time_seconds == 0:
        first_init_date_string = copy.deepcopy(valid_date_string)
    else:
        valid_date_unix_sec = time_conversion.string_to_unix_sec(
            valid_date_string, DATE_FORMAT
        )
        first_init_date_string = time_conversion.unix_sec_to_string(
            valid_date_unix_sec - DAYS_TO_SECONDS, DATE_FORMAT
        )

    satellite_file_names = satellite_io.find_many_files(
        top_directory_name=top_satellite_dir_name,
        first_date_string=first_init_date_string,
        last_date_string=valid_date_string,
        raise_error_if_all_missing=False,
        raise_error_if_any_missing=False
    )

    radar_file_names = radar_io.find_many_files(
        top_directory_name=top_radar_dir_name,
        first_date_string=valid_date_string,
        last_date_string=valid_date_string, with_3d=False,
        raise_error_if_all_missing=False,
        raise_error_if_any_missing=False
    )

    valid_date_strings = _find_days_with_raw_inputs(
        satellite_file_names=satellite_file_names,
        radar_file_names=radar_file_names, lead_time_seconds=lead_time_seconds
    )

    if len(valid_date_strings) == 0:
        return None

    return _read_raw_inputs_one_day(
        valid_date_string=valid_date_string,
        satellite_file_names=satellite_file_names,
        band_numbers=band_numbers,
        norm_dict_for_count=norm_dict_for_count, uniformize=uniformize,
        radar_file_names=radar_file_names,
        lead_time_seconds=lead_time_seconds,
        reflectivity_threshold_dbz=reflectivity_threshold_dbz,
        spatial_downsampling_factor=spatial_downsampling_factor,
        num_examples_to_read=int(1e6), return_coords=return_coords
    )


def create_data_from_preprocessed_files(option_dict, return_coords=False):
    """Creates input data from pre-processed (predictor and target) files.

    This method is the same as `generator_from_preprocessed_files`, except that
    it returns all the data at once, rather than generating batches on the fly.

    :param option_dict: Dictionary with the following keys.
    option_dict['top_predictor_dir_name']: See doc for
        `generator_from_preprocessed_files`.
    option_dict['top_target_dir_name']: Same.
    option_dict['band_numbers']: Same.
    option_dict['lead_time_seconds']: Same.
    option_dict['valid_date_string']: Valid date (format "yyyymmdd").  Will
        create examples with targets valid on this day.
    option_dict['normalize']: See doc for `generator_from_preprocessed_files`.
    option_dict['uniformize']: Same.

    :param return_coords: See doc for `_read_preprocessed_inputs_one_day`.
    :return: data_dict: Same.
    """

    option_dict = _check_generator_args(option_dict)
    error_checking.assert_is_boolean(return_coords)

    top_predictor_dir_name = option_dict[PREDICTOR_DIRECTORY_KEY]
    top_target_dir_name = option_dict[TARGET_DIRECTORY_KEY]
    band_numbers = option_dict[BAND_NUMBERS_KEY]
    lead_time_seconds = option_dict[LEAD_TIME_KEY]
    valid_date_string = option_dict[VALID_DATE_KEY]
    normalize = option_dict[NORMALIZE_FLAG_KEY]
    uniformize = option_dict[UNIFORMIZE_FLAG_KEY]

    if lead_time_seconds == 0:
        first_init_date_string = copy.deepcopy(valid_date_string)
    else:
        valid_date_unix_sec = time_conversion.string_to_unix_sec(
            valid_date_string, DATE_FORMAT
        )
        first_init_date_string = time_conversion.unix_sec_to_string(
            valid_date_unix_sec - DAYS_TO_SECONDS, DATE_FORMAT
        )

    predictor_file_names = example_io.find_many_predictor_files(
        top_directory_name=top_predictor_dir_name,
        first_date_string=first_init_date_string,
        last_date_string=valid_date_string,
        raise_error_if_all_missing=False,
        raise_error_if_any_missing=False
    )

    target_file_names = example_io.find_many_target_files(
        top_directory_name=top_target_dir_name,
        first_date_string=valid_date_string,
        last_date_string=valid_date_string,
        raise_error_if_all_missing=False,
        raise_error_if_any_missing=False
    )

    valid_date_strings = _find_days_with_preprocessed_inputs(
        predictor_file_names=predictor_file_names,
        target_file_names=target_file_names, lead_time_seconds=lead_time_seconds
    )

    if len(valid_date_strings) == 0:
        return None

    return _read_preprocessed_inputs_one_day(
        valid_date_string=valid_date_string,
        predictor_file_names=predictor_file_names,
        band_numbers=band_numbers, normalize=normalize, uniformize=uniformize,
        target_file_names=target_file_names,
        lead_time_seconds=lead_time_seconds,
        num_examples_to_read=int(1e6), return_coords=return_coords
    )


def generator_from_raw_files(option_dict):
    """Generates training data from raw (satellite and radar) files.

    E = number of examples per batch
    M = number of rows in grid
    N = number of columns in grid
    C = number of channels (spectral bands)

    :param option_dict: Dictionary with the following keys.
    option_dict['top_satellite_dir_name']: Name of top-level directory with
        satellite data (predictors).  Files therein will be found by
        `satellite_io.find_file` and read by `satellite_io.read_file`.
    option_dict['top_radar_dir_name']: Name of top-level directory with radar
        data (targets).  Files therein will be found by `radar_io.find_file` and
        read by `radar_io.read_2d_file`.
    option_dict['spatial_downsampling_factor']: Downsampling factor (integer),
        used to coarsen spatial resolution.  If you do not want to coarsen
        spatial resolution, make this 1.
    option_dict['num_examples_per_batch']: Batch size.
    option_dict['max_examples_per_day_in_batch']: Max number of examples from
        the same day in one batch.
    option_dict['band_numbers']: 1-D numpy array of band numbers (integers) for
        satellite data.  Will use only these spectral bands as predictors.
    option_dict['lead_time_seconds']: Lead time for prediction.
    option_dict['reflectivity_threshold_dbz']: Reflectivity threshold for
       convection.  Only grid cells with composite (column-max) reflectivity >=
       threshold will be called convective.
    option_dict['first_valid_date_string']: First valid date (format
        "yyyymmdd").  Will not generate examples with radar data before this
        day.
    option_dict['last_valid_date_string']: Last valid date (format "yyyymmdd").
        Will not generate examples with radar data after this day.
    option_dict['normalization_file_name']: File with normalization parameters
        (will be read by `normalization.read_file`).  If you do not want to
        normalize, make this None.
    option_dict['uniformize']: Boolean flag.  If True, will convert satellite
        values to uniform distribution before normal distribution.  If False,
        will go directly to normal distribution.

    :return: predictor_matrix: E-by-M-by-N-by-C numpy array of predictor values,
        based on satellite data.
    :return: target_matrix: E-by-M-by-N-by-1 numpy array of target values
        (integers in 0...1, indicating whether or not convection occurs at
        the given lead time).
    :raises: ValueError: if no valid date can be found for which radar and
        satellite data are available.
    """

    # TODO(thunderhoser): Allow generator to read brightness temperatures
    # instead of counts.

    option_dict = _check_generator_args(option_dict)

    top_satellite_dir_name = option_dict[SATELLITE_DIRECTORY_KEY]
    top_radar_dir_name = option_dict[RADAR_DIRECTORY_KEY]
    spatial_downsampling_factor = option_dict[SPATIAL_DS_FACTOR_KEY]
    num_examples_per_batch = option_dict[BATCH_SIZE_KEY]
    max_examples_per_day_in_batch = option_dict[MAX_DAILY_EXAMPLES_KEY]
    band_numbers = option_dict[BAND_NUMBERS_KEY]
    lead_time_seconds = option_dict[LEAD_TIME_KEY]
    reflectivity_threshold_dbz = option_dict[REFL_THRESHOLD_KEY]
    first_valid_date_string = option_dict[FIRST_VALID_DATE_KEY]
    last_valid_date_string = option_dict[LAST_VALID_DATE_KEY]
    normalization_file_name = option_dict[NORMALIZATION_FILE_KEY]
    uniformize = option_dict[UNIFORMIZE_FLAG_KEY]

    if lead_time_seconds == 0:
        first_init_date_string = copy.deepcopy(first_valid_date_string)
    else:
        first_init_date_string = general_utils.get_previous_date(
            first_valid_date_string
        )

    if normalization_file_name is None:
        norm_dict_for_count = None
    else:
        print('Reading normalization parameters from: "{0:s}"...'.format(
            normalization_file_name
        ))
        norm_dict_for_count = (
            normalization.read_file(normalization_file_name)[1]
        )

    satellite_file_names = satellite_io.find_many_files(
        top_directory_name=top_satellite_dir_name,
        first_date_string=first_init_date_string,
        last_date_string=last_valid_date_string,
        raise_error_if_any_missing=False
    )

    radar_file_names = radar_io.find_many_files(
        top_directory_name=top_radar_dir_name,
        first_date_string=first_valid_date_string,
        last_date_string=last_valid_date_string,
        with_3d=False, raise_error_if_any_missing=False
    )

    valid_date_strings = _find_days_with_raw_inputs(
        satellite_file_names=satellite_file_names,
        radar_file_names=radar_file_names, lead_time_seconds=lead_time_seconds
    )

    if len(valid_date_strings) == 0:
        raise ValueError(
            'Cannot find any valid date for which both radar and satellite data'
            ' are available.'
        )

    random.shuffle(valid_date_strings)
    date_index = 0

    while True:
        predictor_matrix = None
        target_matrix = None
        num_examples_in_memory = 0

        while num_examples_in_memory < num_examples_per_batch:
            if date_index == len(valid_date_strings):
                date_index = 0

            num_examples_to_read = min([
                max_examples_per_day_in_batch,
                num_examples_per_batch - num_examples_in_memory
            ])

            this_data_dict = _read_raw_inputs_one_day(
                valid_date_string=valid_date_strings[date_index],
                satellite_file_names=satellite_file_names,
                band_numbers=band_numbers,
                norm_dict_for_count=norm_dict_for_count, uniformize=uniformize,
                radar_file_names=radar_file_names,
                lead_time_seconds=lead_time_seconds,
                reflectivity_threshold_dbz=reflectivity_threshold_dbz,
                spatial_downsampling_factor=spatial_downsampling_factor,
                num_examples_to_read=num_examples_to_read, return_coords=False
            )

            date_index += 1
            if this_data_dict is None:
                continue

            this_predictor_matrix = this_data_dict[PREDICTOR_MATRIX_KEY]
            this_target_matrix = this_data_dict[TARGET_MATRIX_KEY]

            if predictor_matrix is None:
                predictor_matrix = this_predictor_matrix + 0.
                target_matrix = this_target_matrix + 0
            else:
                predictor_matrix = numpy.concatenate(
                    (predictor_matrix, this_predictor_matrix), axis=0
                )
                target_matrix = numpy.concatenate(
                    (target_matrix, this_target_matrix), axis=0
                )

            num_examples_in_memory = predictor_matrix.shape[0]

        predictor_matrix = predictor_matrix.astype('float32')
        target_matrix = target_matrix.astype('float32')
        yield predictor_matrix, target_matrix


def generator_from_preprocessed_files(option_dict):
    """Generates training data from pre-processed (predictor and target) files.

    :param option_dict: Dictionary with the following keys.
    option_dict['top_predictor_dir_name']: Name of top-level directory with
        predictors.  Files therein will be found by
        `example_io.find_predictor_file` and read by
        `example_io.read_predictor_file`.
    option_dict['top_target_dir_name']: Name of top-level directory with
        targets.  Files therein will be found by `example_io.find_target_file`
        and read by `example_io.read_target_file`.
    option_dict['num_examples_per_batch']: See doc for
        `generator_from_raw_files`.
    option_dict['max_examples_per_day_in_batch']: Same.
    option_dict['band_numbers']: Same.
    option_dict['lead_time_seconds']: Same.
    option_dict['first_valid_date_string']: Same.
    option_dict['last_valid_date_string']: Same.
    option_dict['normalize']: Boolean flag.  If True (False), will use
        normalized (unnormalized) predictors.
    option_dict['uniformize']: [used only if `normalize == True`]
        Boolean flag.  If True, will use uniformized and normalized predictors.
        If False, will use only normalized predictors.

    :return: predictor_matrix: See doc for `generator_from_raw_files`.
    :return: target_matrix: See doc for `generator_from_raw_files`.
    :raises: ValueError: if no valid date can be found for which predictors and
        targets are available.
    """

    # TODO(thunderhoser): Allow generator to read brightness temperatures
    # instead of counts.

    option_dict = _check_generator_args(option_dict)

    top_predictor_dir_name = option_dict[PREDICTOR_DIRECTORY_KEY]
    top_target_dir_name = option_dict[TARGET_DIRECTORY_KEY]
    num_examples_per_batch = option_dict[BATCH_SIZE_KEY]
    max_examples_per_day_in_batch = option_dict[MAX_DAILY_EXAMPLES_KEY]
    band_numbers = option_dict[BAND_NUMBERS_KEY]
    lead_time_seconds = option_dict[LEAD_TIME_KEY]
    first_valid_date_string = option_dict[FIRST_VALID_DATE_KEY]
    last_valid_date_string = option_dict[LAST_VALID_DATE_KEY]
    normalize = option_dict[NORMALIZE_FLAG_KEY]
    uniformize = option_dict[UNIFORMIZE_FLAG_KEY]

    if lead_time_seconds == 0:
        first_init_date_string = copy.deepcopy(first_valid_date_string)
    else:
        first_init_date_string = general_utils.get_previous_date(
            first_valid_date_string
        )

    predictor_file_names = example_io.find_many_predictor_files(
        top_directory_name=top_predictor_dir_name,
        first_date_string=first_init_date_string,
        last_date_string=last_valid_date_string,
        raise_error_if_any_missing=False
    )

    target_file_names = example_io.find_many_target_files(
        top_directory_name=top_target_dir_name,
        first_date_string=first_init_date_string,
        last_date_string=last_valid_date_string,
        raise_error_if_any_missing=False
    )

    valid_date_strings = _find_days_with_preprocessed_inputs(
        predictor_file_names=predictor_file_names,
        target_file_names=target_file_names, lead_time_seconds=lead_time_seconds
    )

    if len(valid_date_strings) == 0:
        raise ValueError(
            'Cannot find any valid date for which both predictors and targets '
            ' are available.'
        )

    random.shuffle(valid_date_strings)
    date_index = 0

    while True:
        predictor_matrix = None
        target_matrix = None
        num_examples_in_memory = 0

        while num_examples_in_memory < num_examples_per_batch:
            if date_index == len(valid_date_strings):
                date_index = 0

            num_examples_to_read = min([
                max_examples_per_day_in_batch,
                num_examples_per_batch - num_examples_in_memory
            ])

            this_data_dict = _read_preprocessed_inputs_one_day(
                valid_date_string=valid_date_strings[date_index],
                predictor_file_names=predictor_file_names,
                band_numbers=band_numbers,
                normalize=normalize, uniformize=uniformize,
                target_file_names=target_file_names,
                lead_time_seconds=lead_time_seconds,
                num_examples_to_read=num_examples_to_read, return_coords=False
            )

            date_index += 1
            if this_data_dict is None:
                continue

            this_predictor_matrix = this_data_dict[PREDICTOR_MATRIX_KEY]
            this_target_matrix = this_data_dict[TARGET_MATRIX_KEY]

            if predictor_matrix is None:
                predictor_matrix = this_predictor_matrix + 0.
                target_matrix = this_target_matrix + 0
            else:
                predictor_matrix = numpy.concatenate(
                    (predictor_matrix, this_predictor_matrix), axis=0
                )
                target_matrix = numpy.concatenate(
                    (target_matrix, this_target_matrix), axis=0
                )

            num_examples_in_memory = predictor_matrix.shape[0]

        predictor_matrix = predictor_matrix.astype('float32')
        target_matrix = target_matrix.astype('float32')
        yield predictor_matrix, target_matrix


def train_model_from_raw_files(
        model_object, output_dir_name, num_epochs,
        num_training_batches_per_epoch, training_option_dict,
        num_validation_batches_per_epoch, validation_option_dict,
        do_early_stopping=True,
        plateau_lr_multiplier=DEFAULT_LEARNING_RATE_MULTIPLIER,
        class_weights=None):
    """Trains neural net from raw (satellite and radar) files.

    :param model_object: Untrained neural net (instance of `keras.models.Model`
        or `keras.models.Sequential`).
    :param output_dir_name: Path to output directory (model and training history
        will be saved here).
    :param num_epochs: Number of training epochs.
    :param num_training_batches_per_epoch: Number of training batches per epoch.
    :param training_option_dict: See doc for `generator_from_raw_files`.  This
        dictionary will be used to generate training data.
    :param num_validation_batches_per_epoch: Number of validation batches per
        epoch.
    :param validation_option_dict: See doc for `generator_from_raw_files`.  For
        validation only, the following values will replace corresponding values
        in `training_option_dict`:
    validation_option_dict['top_satellite_dir_name']
    validation_option_dict['top_radar_dir_name']
    validation_option_dict['first_valid_date_string']
    validation_option_dict['last_valid_date_string']

    :param do_early_stopping: Boolean flag.  If True, will stop training early
        if validation loss has not improved over last several epochs (see
        constants at top of file for what exactly this means).
    :param plateau_lr_multiplier: Multiplier for learning rate.  Learning
        rate will be multiplied by this factor upon plateau in validation
        performance.
    :param class_weights: See doc for `check_class_weights`.  If model uses
        unweighted loss function, leave this alone.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    error_checking.assert_is_integer(num_epochs)
    error_checking.assert_is_geq(num_epochs, 2)
    error_checking.assert_is_integer(num_training_batches_per_epoch)
    error_checking.assert_is_geq(num_training_batches_per_epoch, 10)
    error_checking.assert_is_integer(num_validation_batches_per_epoch)
    error_checking.assert_is_geq(num_validation_batches_per_epoch, 10)
    error_checking.assert_is_boolean(do_early_stopping)

    if do_early_stopping:
        error_checking.assert_is_greater(plateau_lr_multiplier, 0.)
        error_checking.assert_is_less_than(plateau_lr_multiplier, 1.)

    if class_weights is not None:
        check_class_weights(class_weights)

    training_option_dict = _check_generator_args(training_option_dict)

    validation_keys_to_keep = [
        SATELLITE_DIRECTORY_KEY, RADAR_DIRECTORY_KEY,
        FIRST_VALID_DATE_KEY, LAST_VALID_DATE_KEY
    ]

    for this_key in list(training_option_dict.keys()):
        if this_key in validation_keys_to_keep:
            continue

        validation_option_dict[this_key] = training_option_dict[this_key]

    validation_option_dict = _check_generator_args(validation_option_dict)

    # model_file_name = (
    #     output_dir_name + '/model_epoch={epoch:03d}_val-loss={val_loss:.6f}.h5'
    # )
    model_file_name = '{0:s}/model.h5'.format(output_dir_name)

    history_object = keras.callbacks.CSVLogger(
        filename='{0:s}/history.csv'.format(output_dir_name),
        separator=',', append=False
    )
    checkpoint_object = keras.callbacks.ModelCheckpoint(
        filepath=model_file_name, monitor='val_loss', verbose=1,
        save_best_only=do_early_stopping, save_weights_only=False, mode='min',
        period=1
    )
    list_of_callback_objects = [history_object, checkpoint_object]

    if do_early_stopping:
        early_stopping_object = keras.callbacks.EarlyStopping(
            monitor='val_loss', min_delta=LOSS_PATIENCE,
            patience=EARLY_STOPPING_PATIENCE_EPOCHS, verbose=1, mode='min'
        )
        list_of_callback_objects.append(early_stopping_object)

        plateau_object = keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=plateau_lr_multiplier,
            patience=PLATEAU_PATIENCE_EPOCHS, verbose=1, mode='min',
            min_delta=LOSS_PATIENCE, cooldown=PLATEAU_COOLDOWN_EPOCHS
        )
        list_of_callback_objects.append(plateau_object)

    metafile_name = find_metafile(
        model_file_name=model_file_name, raise_error_if_missing=False
    )
    print('Writing metadata to: "{0:s}"...'.format(metafile_name))

    _write_metafile(
        dill_file_name=metafile_name, num_epochs=num_epochs,
        num_training_batches_per_epoch=num_training_batches_per_epoch,
        training_option_dict=training_option_dict,
        num_validation_batches_per_epoch=num_validation_batches_per_epoch,
        validation_option_dict=validation_option_dict,
        do_early_stopping=do_early_stopping,
        plateau_lr_multiplier=plateau_lr_multiplier, class_weights=class_weights
    )

    training_generator = generator_from_raw_files(training_option_dict)
    validation_generator = generator_from_raw_files(validation_option_dict)

    model_object.fit_generator(
        generator=training_generator,
        steps_per_epoch=num_training_batches_per_epoch,
        epochs=num_epochs, verbose=1, callbacks=list_of_callback_objects,
        validation_data=validation_generator,
        validation_steps=num_validation_batches_per_epoch
    )


def train_model_from_preprocessed_files(
        model_object, output_dir_name, num_epochs,
        num_training_batches_per_epoch, training_option_dict,
        num_validation_batches_per_epoch, validation_option_dict,
        do_early_stopping=True,
        plateau_lr_multiplier=DEFAULT_LEARNING_RATE_MULTIPLIER,
        class_weights=None):
    """Trains neural net from pre-processed (predictor and target) files.

    :param model_object: See doc for `train_model_from_raw_files`.
    :param output_dir_name: Same.
    :param num_epochs: Same.
    :param num_training_batches_per_epoch: Same.
    :param training_option_dict: See doc for
        `generator_from_preprocessed_files`.  This dictionary will be used to
        generate training data.
    :param num_validation_batches_per_epoch: See doc for
        `train_model_from_raw_files`.
    :param validation_option_dict: See doc for
        `generator_from_preprocessed_files`.  For validation only, the following
        values will replace corresponding values in `training_option_dict`:
    validation_option_dict['top_predictor_dir_name']
    validation_option_dict['top_target_dir_name']
    validation_option_dict['first_valid_date_string']
    validation_option_dict['last_valid_date_string']

    :param do_early_stopping: See doc for `train_model_from_raw_files`.
    :param plateau_lr_multiplier: Same.
    :param class_weights: Same.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=output_dir_name
    )

    error_checking.assert_is_integer(num_epochs)
    error_checking.assert_is_geq(num_epochs, 2)
    error_checking.assert_is_integer(num_training_batches_per_epoch)
    error_checking.assert_is_geq(num_training_batches_per_epoch, 10)
    error_checking.assert_is_integer(num_validation_batches_per_epoch)
    error_checking.assert_is_geq(num_validation_batches_per_epoch, 10)
    error_checking.assert_is_boolean(do_early_stopping)

    if do_early_stopping:
        error_checking.assert_is_greater(plateau_lr_multiplier, 0.)
        error_checking.assert_is_less_than(plateau_lr_multiplier, 1.)

    if class_weights is not None:
        check_class_weights(class_weights)

    training_option_dict = _check_generator_args(training_option_dict)

    validation_keys_to_keep = [
        PREDICTOR_DIRECTORY_KEY, TARGET_DIRECTORY_KEY,
        FIRST_VALID_DATE_KEY, LAST_VALID_DATE_KEY
    ]

    for this_key in list(training_option_dict.keys()):
        if this_key in validation_keys_to_keep:
            continue

        validation_option_dict[this_key] = training_option_dict[this_key]

    validation_option_dict = _check_generator_args(validation_option_dict)
    model_file_name = '{0:s}/model.h5'.format(output_dir_name)

    history_object = keras.callbacks.CSVLogger(
        filename='{0:s}/history.csv'.format(output_dir_name),
        separator=',', append=False
    )
    checkpoint_object = keras.callbacks.ModelCheckpoint(
        filepath=model_file_name, monitor='val_loss', verbose=1,
        save_best_only=do_early_stopping, save_weights_only=False, mode='min',
        period=1
    )
    list_of_callback_objects = [history_object, checkpoint_object]

    if do_early_stopping:
        early_stopping_object = keras.callbacks.EarlyStopping(
            monitor='val_loss', min_delta=LOSS_PATIENCE,
            patience=EARLY_STOPPING_PATIENCE_EPOCHS, verbose=1, mode='min'
        )
        list_of_callback_objects.append(early_stopping_object)

        plateau_object = keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=plateau_lr_multiplier,
            patience=PLATEAU_PATIENCE_EPOCHS, verbose=1, mode='min',
            min_delta=LOSS_PATIENCE, cooldown=PLATEAU_COOLDOWN_EPOCHS
        )
        list_of_callback_objects.append(plateau_object)

    metafile_name = find_metafile(
        model_file_name=model_file_name, raise_error_if_missing=False
    )
    print('Writing metadata to: "{0:s}"...'.format(metafile_name))

    _write_metafile(
        dill_file_name=metafile_name, num_epochs=num_epochs,
        num_training_batches_per_epoch=num_training_batches_per_epoch,
        training_option_dict=training_option_dict,
        num_validation_batches_per_epoch=num_validation_batches_per_epoch,
        validation_option_dict=validation_option_dict,
        do_early_stopping=do_early_stopping,
        plateau_lr_multiplier=plateau_lr_multiplier, class_weights=class_weights
    )

    training_generator = generator_from_preprocessed_files(training_option_dict)
    validation_generator = generator_from_preprocessed_files(
        validation_option_dict
    )

    model_object.fit_generator(
        generator=training_generator,
        steps_per_epoch=num_training_batches_per_epoch,
        epochs=num_epochs, verbose=1, callbacks=list_of_callback_objects,
        validation_data=validation_generator,
        validation_steps=num_validation_batches_per_epoch
    )


def read_model(hdf5_file_name):
    """Reads model from HDF5 file.

    :param hdf5_file_name: Path to input file.
    :return: model_object: Instance of `keras.models.Model`.
    """

    error_checking.assert_file_exists(hdf5_file_name)

    try:
        return tf_keras.models.load_model(
            hdf5_file_name, custom_objects=METRIC_FUNCTION_DICT
        )
    except ValueError:
        pass

    metafile_name = find_metafile(
        model_file_name=hdf5_file_name, raise_error_if_missing=True
    )

    metadata_dict = read_metafile(metafile_name)
    class_weights = metadata_dict[CLASS_WEIGHTS_KEY]
    custom_object_dict = copy.deepcopy(METRIC_FUNCTION_DICT)

    if class_weights is not None:
        custom_object_dict['loss'] = custom_losses.weighted_xentropy(
            class_weights
        )

    return tf_keras.models.load_model(
        hdf5_file_name, custom_objects=custom_object_dict
    )


def find_metafile(model_file_name, raise_error_if_missing=True):
    """Finds metafile for neural net.

    :param model_file_name: Path to trained model.
    :param raise_error_if_missing: Boolean flag.  If file is missing and
        `raise_error_if_missing == True`, will throw error.  If file is missing
        and `raise_error_if_missing == False`, will return *expected* file path.
    :return: metafile_name: Path to metafile.
    """

    error_checking.assert_is_string(model_file_name)
    error_checking.assert_is_boolean(raise_error_if_missing)

    metafile_name = '{0:s}/model_metadata.dill'.format(
        os.path.split(model_file_name)[0]
    )

    if raise_error_if_missing and not os.path.isfile(metafile_name):
        error_string = 'Cannot find file.  Expected at: "{0:s}"'.format(
            metafile_name
        )
        raise ValueError(error_string)

    return metafile_name


def read_metafile(dill_file_name):
    """Reads metadata for neural net from Dill file.

    :param dill_file_name: Path to input file.
    :return: metadata_dict: Dictionary with the following keys.
    metadata_dict['num_epochs']: See doc for `train_model`.
    metadata_dict['num_training_batches_per_epoch']: Same.
    metadata_dict['training_option_dict']: Same.
    metadata_dict['num_validation_batches_per_epoch']: Same.
    metadata_dict['validation_option_dict']: Same.
    metadata_dict['do_early_stopping']: Same.
    metadata_dict['plateau_lr_multiplier']: Same.
    metadata_dict['class_weights']: Same.

    :raises: ValueError: if any expected key is not found in dictionary.
    """

    error_checking.assert_file_exists(dill_file_name)

    dill_file_handle = open(dill_file_name, 'rb')
    metadata_dict = dill.load(dill_file_handle)
    dill_file_handle.close()

    if CLASS_WEIGHTS_KEY not in metadata_dict:
        metadata_dict[CLASS_WEIGHTS_KEY] = None

    missing_keys = list(set(METADATA_KEYS) - set(metadata_dict.keys()))
    if len(missing_keys) == 0:
        return metadata_dict

    error_string = (
        '\n{0:s}\nKeys listed above were expected, but not found, in file '
        '"{1:s}".'
    ).format(str(missing_keys), dill_file_name)

    raise ValueError(error_string)


def apply_model(
        model_object, predictor_matrix, num_examples_per_batch, verbose=False):
    """Applies trained neural net to new data.

    E = number of examples
    M = number of rows in grid
    N = number of columns in grid

    :param model_object: Trained neural net (instance of `keras.models.Model` or
        `keras.models.Sequential`).
    :param predictor_matrix: See output doc for `generator_from_raw_files`.
    :param num_examples_per_batch: Batch size.
    :param verbose: Boolean flag.  If True, will print progress messages.
    :return: forecast_prob_matrix: E-by-M-by-N numpy array of forecast event
        probabilities.
    """

    num_examples_per_batch = _check_inference_args(
        predictor_matrix=predictor_matrix,
        num_examples_per_batch=num_examples_per_batch, verbose=verbose
    )

    forecast_prob_matrix = None
    num_examples = predictor_matrix.shape[0]

    for i in range(0, num_examples, num_examples_per_batch):
        this_first_index = i
        this_last_index = min(
            [i + num_examples_per_batch - 1, num_examples - 1]
        )

        these_indices = numpy.linspace(
            this_first_index, this_last_index,
            num=this_last_index - this_first_index + 1, dtype=int
        )

        if verbose:
            print((
                'Applying model to examples {0:d}-{1:d} of {2:d}...'
            ).format(
                this_first_index + 1, this_last_index + 1, num_examples
            ))

        this_prob_matrix = model_object.predict(
            predictor_matrix[these_indices, ...], batch_size=len(these_indices)
        )

        if forecast_prob_matrix is None:
            dimensions = (num_examples,) + this_prob_matrix.shape[1:3]
            forecast_prob_matrix = numpy.full(dimensions, numpy.nan)

        forecast_prob_matrix[these_indices, ...] = this_prob_matrix[..., 0]

    if verbose:
        print('Have applied model to all {0:d} examples!'.format(num_examples))

    return forecast_prob_matrix