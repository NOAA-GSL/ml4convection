"""Makes U-net templates for Experiment 2."""

import sys
import copy
import os.path
import numpy

THIS_DIRECTORY_NAME = os.path.dirname(os.path.realpath(
    os.path.join(os.getcwd(), os.path.expanduser(__file__))
))
sys.path.append(os.path.normpath(os.path.join(THIS_DIRECTORY_NAME, '..')))

import u_net_architecture
import file_system_utils
import neural_net
import custom_losses

SEPARATOR_STRING = '\n\n' + '*' * 50 + '\n\n'

HOME_DIR_NAME = '/scratch1/RDARCH/rda-ghpcs/Ryan.Lagerquist'
OUTPUT_DIR_NAME = '{0:s}/ml4convection_models/experiment02/templates'.format(
    HOME_DIR_NAME
)

POSITIVE_CLASS_WEIGHTS = numpy.array(
    [1, 10, 25, 50, 75, 100, 150, 200], dtype=int
)
CONV_LAYER_DROPOUT_RATES = numpy.array([0, 0.175, 0.35, 0.525, 0.7])
L2_WEIGHTS = numpy.logspace(-4, -2, num=5)

DEFAULT_OPTION_DICT = {
    u_net_architecture.INPUT_DIMENSIONS_KEY:
        numpy.array([220, 230, 7], dtype=int),
    u_net_architecture.NUM_LEVELS_KEY: 5,
    u_net_architecture.NUM_CONV_LAYERS_KEY: 2,
    u_net_architecture.CONV_LAYER_CHANNEL_COUNTS_KEY:
        numpy.array([16, 24, 32, 48, 64, 96], dtype=int),
    u_net_architecture.UPCONV_LAYER_DROPOUT_RATES_KEY: numpy.full(5, 0.),
    u_net_architecture.SKIP_LAYER_DROPOUT_RATES_KEY: numpy.full(5, 0.)
}


def _run():
    """Makes U-net templates for Experiment 2.

    This is effectively the main method.
    """

    file_system_utils.mkdir_recursive_if_necessary(
        directory_name=OUTPUT_DIR_NAME
    )

    num_pos_class_weights = len(POSITIVE_CLASS_WEIGHTS)
    num_dropout_rates = len(CONV_LAYER_DROPOUT_RATES)
    num_l2_weights = len(L2_WEIGHTS)
    num_levels = DEFAULT_OPTION_DICT[u_net_architecture.NUM_LEVELS_KEY]

    for i in range(num_pos_class_weights):
        these_class_weights = numpy.array(
            [1, POSITIVE_CLASS_WEIGHTS[i]], dtype=float
        )
        this_loss_function = custom_losses.weighted_xentropy(
            these_class_weights
        )

        for j in range(num_dropout_rates):
            these_dropout_rates = numpy.full(
                num_levels + 1, CONV_LAYER_DROPOUT_RATES[j]
            )

            for k in range(num_l2_weights):
                this_option_dict = copy.deepcopy(DEFAULT_OPTION_DICT)
                this_option_dict[u_net_architecture.L2_WEIGHT_KEY] = (
                    L2_WEIGHTS[k]
                )
                this_option_dict[
                    u_net_architecture.CONV_LAYER_DROPOUT_RATES_KEY
                ] = these_dropout_rates

                print(this_option_dict)
                print(SEPARATOR_STRING)

                this_model_object = u_net_architecture.create_model(
                    option_dict=this_option_dict,
                    loss_function=this_loss_function
                )

                this_model_file_name = (
                    '{0:s}/model_positive-class-weight={1:03d}_'
                    'conv-dropout={2:.3f}_l2-weight={3:.6f}.h5'
                ).format(
                    OUTPUT_DIR_NAME, POSITIVE_CLASS_WEIGHTS[i],
                    CONV_LAYER_DROPOUT_RATES[j], L2_WEIGHTS[k]
                )

                print('Writing model to: "{0:s}"...'.format(
                    this_model_file_name
                ))
                this_model_object.save(
                    filepath=this_model_file_name, overwrite=True,
                    include_optimizer=True
                )

                this_metafile_name = neural_net.find_metafile(
                    model_file_name=this_model_file_name,
                    raise_error_if_missing=False
                )
                dummy_option_dict = neural_net.DEFAULT_GENERATOR_OPTION_DICT

                print('Writing metadata to: "{0:s}"...'.format(
                    this_metafile_name
                ))
                neural_net._write_metafile(
                    dill_file_name=this_metafile_name, num_epochs=100,
                    num_training_batches_per_epoch=100,
                    training_option_dict=dummy_option_dict,
                    num_validation_batches_per_epoch=100,
                    validation_option_dict=dummy_option_dict,
                    do_early_stopping=True, plateau_lr_multiplier=0.6,
                    class_weights=these_class_weights,
                    fss_half_window_size_px=None
                )


if __name__ == '__main__':
    _run()