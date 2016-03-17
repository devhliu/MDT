import numbers
import os
import nibabel as nib
import numpy as np
import six

import mdt
from mot import runtime_configuration
from mot.base import SimpleProblemData
from mot.cl_routines.mapping.evaluate_model import EvaluateModelPerProtocol
from mot.cl_routines.optimizing.powell import Powell
from mot.runtime_configuration import runtime_config

__author__ = 'Robbert Harms'
__date__ = "2016-03-17"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


def permutate_parameters(var_params_ind, default_values, lower_bounds, upper_bounds, grid_size,
                         np_dtype=np.float32):
    """Generate the combination of parameters for a simulation.

    This generates for each of the parameters of interest a linearly indexed range of parameter values
    starting with the lower bounds and ending at the upper bound (both inclusive). The length of the list is determined
    by the grid size per parameter. Next we create a matrix with the cartesian product of each of these parameters
    of interest and with all the other parameters set to their default value.

    Args:
        var_params_ind (list of int): the list of indices into the parameters. This indices the parameters
            we want to vary.
        default_values (list of float): the default values for each of the parameters in the model
        lower_bounds (list of float): the lower bounds used for the generation of the grid
        upper_bounds (list of float): the upper bounds used for the generation of the grid
        grid_size (int or list of int): the size of the grid. If a single int is given we assume a grid
            equal in all dimensions. If a list is given it should match the number of variable parameter indices
            and should contain a grid size for each parameter.
        np_dtype (dtype): the data type of the result matrix

    Returns:
        ndarray: the matrix with all combinations of the parameters of interest and with all other parameters set to
            the given default value.
    """
    if isinstance(grid_size, numbers.Number):
        grid_size = [int(grid_size)] * len(var_params_ind)

    result = np.reshape(default_values, [len(lower_bounds), 1]).astype(np_dtype)

    repeat_mult = 1
    for linear_ind, params_ind in enumerate(var_params_ind):
        result = np.tile(result, grid_size[linear_ind])
        result[params_ind] = np.repeat(np.linspace(lower_bounds[params_ind],
                                                   upper_bounds[params_ind],
                                                   grid_size[linear_ind]), repeat_mult)
        repeat_mult *= grid_size[linear_ind]

    return np.transpose(result)


def get_permuted_indices(nmr_var_params, grid_size):
    """Get for every parameter of interest the locations per parameter value.

    Suppose you have three variable parameters and you generate all permutations using permutate_parameters(), then you
    might want to know for any given parameter and for any value of that parameter at which indices that parameter
    occurs. This function tells you where.

    Note, we could have taken the nmr_var_params from the grid size, but the grid size can be a single scalar for all
    params.

    Args:
        nmr_var_params (int): the number of variable parameters
        grid_size (int or list of int): the grid size for all or per parameter

    Returns:
        ndarray: per permutation the value index indexing the parameter value
    """
    indices = np.zeros((nmr_var_params, 1), dtype=np.int64)

    repeat_mult = 1
    for ind in range(nmr_var_params):
        indices = np.tile(indices, grid_size[ind])
        indices[ind, :] = np.repeat(np.arange(0, grid_size[ind]), repeat_mult)
        repeat_mult *= grid_size[ind]

    return np.transpose(indices)


def simulate_signals(model_name, protocol, parameters):
    """Generate the signal for the given model for each of the parameters.

    Args:
        model_name (str): the name of the model we want to generate the values for
        protocol (Protocol): the protocol object we use for generating the signals
        parameters (ndarray): the matrix with the parameters for every problem instance

    Returns:
        signal estimates
    """
    problem_data = SimpleProblemData(protocol, None)

    model = mdt.get_model(model_name)
    model.set_problem_data(problem_data)

    signal_evaluate = EvaluateModelPerProtocol(**runtime_configuration.runtime_config)
    return signal_evaluate.calculate(model, parameters)


def make_rician_distributed(signals, noise_level):
    """Make the given signal Rician distributed.

    To calculate the noise level divide the signal of the unweighted volumes by the SNR you want. For example,
    for a unweighted signal b0=1e4 and a desired SNR of 20, you need an noise level of 1000/20 = 50.

    Args:
        signals: the signals to make Rician distributed
        noise_level: the level of noise to add. The actual Rician stdev depends on the signal. See ricestat in
            the mathworks library.

    Returns:
        ndarray: Rician distributed signals.
    """
    x = noise_level * np.random.normal(size=signals.shape) + signals
    y = noise_level * np.random.normal(size=signals.shape)
    return np.sqrt(np.power(x, 2), np.power(y, 2)).astype(signals.dtype)


def list_2d_to_4d(item_list):
    """Convert a 2d signal/parameter list to a 4d volume.

    The only thing this does is to prepend to singleton volumes to the signal list to make it 4d.

    Args:
         item_list (2d ndarray): the list with on the first dimension every problem and on the second
            the signals per protocol line.

    Returns:
        ndarray: 4d ndarray of size (1, 1, n, p) where n is the number of problems and p the length of the protocol.
    """
    return np.reshape(item_list, (1, 1) + item_list.shape)


def volume4d_to_file(file_name, data):
    """Save the 4d volume to the given file.

    Args:
        file_name (str): the output file name. If the directory does not exist we create one.
        data (ndarray): the 4d array to save.
    """
    if not os.path.isdir(os.path.dirname(file_name)):
        os.makedirs(os.path.dirname(file_name))
    img = nib.Nifti1Image(data, np.eye(4))
    img.to_filename(file_name)


def save_list_as_4d_volume(file_name, data):
    """Save the given 2d list with values as a 4d volume.

    This is a convenience function that calls list_2d_to_4d and volume4d_to_file after each other.

    Args:
        file_name (str): the output file name. If the directory does not exist we create one.
        data (ndarray): the 2d array to save
    """
    volume4d_to_file(file_name, list_2d_to_4d(data))


def get_unweighted_volumes(signals, protocol):
    """Get the signals and protocol for only the unweighted signals.

    Args:
        signals (ndarray): the matrix with for every problem (first dimension) the volumes (second dimension)
        protocol (Protocol): the protocol object

    Returns:
        tuple: unweighted signals and the protocol for only the unweighted indices.
    """
    unweighted_indices = protocol.get_unweighted_indices()

    unweighted_signals = signals[:, unweighted_indices]
    unweighted_protocol = protocol.get_new_protocol_with_indices(unweighted_indices)

    return unweighted_signals, unweighted_protocol


def estimate_noise_std(simulated_noisy_signals, protocol):
    """Estimate the noise on the noisy simulated dataset.

    This routine tries to estimate the noise level of the added noise. It first fits an S0 model to the data with
    a noise std of 1. It then removes this estimated S0 from the given signal and tries to estimate the noise std
    on the result.

    Args:
        simulated_noisy_signals (ndarray): the list with per problem the noisy simulated signal
        protocol (Protocol): the protocol object

    Returns:
        float: the noise standard deviation
    """
    if isinstance(protocol, six.string_types):
        protocol = mdt.load_protocol(protocol)

    optimizer = Powell(cl_environments=runtime_config['cl_environments'],
                       load_balancer=runtime_config['load_balancer'],
                       patience=2)

    unweighted_signals, unweighted_protocol = get_unweighted_volumes(simulated_noisy_signals, protocol)
    problem_data = SimpleProblemData(unweighted_protocol, unweighted_signals)
    problem_data.protocol = unweighted_protocol

    s0_model = mdt.get_model('S0')
    s0_model.set_problem_data(problem_data)
    s0_model.evaluation_model.set_noise_level_std(1, fix=True)

    s0_estimate = optimizer.minimize(s0_model, full_output=False)['S0.s0']
    s0_estimate = np.reshape(s0_estimate, s0_estimate.shape + (1,))

    baseline_images = unweighted_signals - s0_estimate

    sum_of_squares = np.sum(np.power(baseline_images, 2), axis=1)
    mean_squares = sum_of_squares / baseline_images.shape[0]

    sigmas = np.sqrt(mean_squares / 2)
    return np.mean(sigmas)
