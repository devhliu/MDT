import nibabel as nib
from contextlib import contextmanager
from mdt import __version__
import logging
import os
import shutil
import timeit
import time
import collections
from six import string_types
from mdt.IO import Nifti
from mdt.components_loader import get_model
from mdt.configuration import get_processing_strategy
from mdt.models.cascade import DMRICascadeModelInterface
from mdt.utils import create_roi, \
    model_output_exists, get_cl_devices, per_model_logging_context, load_samples, is_scalar, \
    get_temporary_results_dir, MetaSamplerBuilder
from mdt.processing_strategies import SimpleModelProcessingWorkerGenerator, SamplingProcessingWorker
from mdt.exceptions import InsufficientProtocolError
from mot.configuration import config_context
from mot.load_balance_strategies import EvenDistribution
from mot.configuration import RuntimeConfigurationAction

__author__ = 'Robbert Harms'
__date__ = "2015-05-01"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class ModelSampling(object):

    def __init__(self, model, problem_data, output_folder,
                 sampler=None, recalculate=False, cl_device_ind=None, double_precision=True,
                 initialize=True, initialize_using=None, store_samples=True, tmp_results_dir=True):
        """Sample a single model. This does not accept cascade models, only single models.

        Args:
            model: the model to sample
            problem_data (ProblemData): the problem data object which contains the dwi image, the dwi header, the
                brain_mask and the protocol to use.
            output_folder (string): The path to the folder where to place the output, we will make a subdir with the
                model name in it (for the optimization results) and then a subdir with the samples output.
            sampler (AbstractSampler): the sampler to use, if not set we will use MCMC
            recalculate (boolean): If we want to recalculate the results if they are already present.
            cl_device_ind (int): the index of the CL device to use. The index is from the list from the function
                utils.get_cl_devices().
            double_precision (boolean): if we would like to do the calculations in double precision
            initialize (boolean): If we want to initialize the sampler with optimization output.
                This assumes that the optimization results are in the folder:
                    <output_folder>/<model_name>/
            initialize_using (None, str, or dict): If None, and initialize is True we will initialize from the
                optimization maps from a model with the same name. If a string is given and initialize is True we will
                interpret the string as a folder with the maps to set_current_map. If a dict is given and initialize is
                True we will initialize from the dict directly.
            store_samples (boolean): if set to False we will store none of the samples. Use this
                if you are only interested in the volume maps and not in the entire sample chain.
            tmp_results_dir (str, True or None): The temporary dir for the calculations. Set to a string to use
                that path directly, set to True to use the config value, set to None to disable.

        Returns:
            the full chain of the optimization if store_samples is True
        """
        if isinstance(model, string_types):
            model = get_model(model)

        if isinstance(model, DMRICascadeModelInterface):
            raise ValueError('The function \'sample_model()\' does not accept cascade models.')

        model.double_precision = double_precision

        self._model = model
        self._problem_data = problem_data
        self._output_folder = output_folder
        self._sampler = sampler
        self._recalculate = recalculate
        self._logger = logging.getLogger(__name__)
        self._cl_device_indices = cl_device_ind
        self._initialize = initialize
        self._initialize_using = initialize_using
        self._store_samples = store_samples
        self._tmp_results_dir = get_temporary_results_dir(tmp_results_dir)

        if self._sampler is None:
            self._sampler = MetaSamplerBuilder().construct(self._model.name)

        if self._cl_device_indices is not None and not isinstance(self._cl_device_indices, collections.Iterable):
            self._cl_device_indices = [self._cl_device_indices]

        if not model.is_protocol_sufficient(self._problem_data.protocol):
            raise InsufficientProtocolError(
                'The given protocol is insufficient for this model. '
                'The reported errors where: {}'.format(self._model.get_protocol_problems(
                    self._problem_data.protocol)))

    def run(self):
        """Sample the given model.

        Returns:
            dict: with as keys the sampled maps and as values a memory mapped array
        """
        cl_envs = None
        load_balancer = None
        if self._cl_device_indices is not None:
            all_devices = get_cl_devices()
            cl_envs = [all_devices[ind] for ind in self._cl_device_indices]
            load_balancer = EvenDistribution()

        with config_context(RuntimeConfigurationAction(cl_environments=cl_envs, load_balancer=load_balancer)):
            with per_model_logging_context(os.path.join(self._output_folder, self._model.name)):
                self._logger.info('Using MDT version {}'.format(__version__))
                self._logger.info('Preparing for model {0}'.format(self._model.name))

                if self._cl_device_indices is not None:
                    all_devices = get_cl_devices()
                    self._sampler.cl_environments = [all_devices[ind] for ind in self._cl_device_indices]
                    self._sampler.load_balancer = EvenDistribution()

                processing_strategy = get_processing_strategy('sampling', model_names=self._model.name)
                processing_strategy.set_tmp_dir(self._tmp_results_dir)

                sampler = SampleSingleModel(self._model, self._problem_data, self._output_folder, self._sampler,
                                            processing_strategy,
                                            recalculate=self._recalculate, initialize=self._initialize,
                                            initialize_using=self._initialize_using,
                                            store_samples=self._store_samples)

                return sampler.run()


class SampleSingleModel(object):

    def __init__(self, model, problem_data, output_folder, sampler, processing_strategy,
                 recalculate=False, initialize=True, initialize_using=None, store_samples=True):
        """Sample a single model.

        Please note that this function does not accept cascade models.

        This will place the output in the folder: <output_folder>/<model_name>/samples/

        Args:
            model (AbstractModel): An implementation of an AbstractModel that contains the model we want to optimize.
            problem_data (DMRIProblemData): The problem data object with which the model is initialized before running
            output_folder (string): The full path to the folder where to place the output
            sampler (AbstractSampler): The sampling routine to use.
            processing_strategy (ModelProcessingStrategy): the processing strategy to use
            recalculate (boolean): If we want to recalculate the results if they are already present.
            initialize (boolean): If we want to initialize the sampler with optimization output.
                This assumes that the optimization results are in the folder:
                    <output_folder>/<model_name>/
            initialize_using (None, str, or dict): If None, and initialize is True we will initialize from the
                optimization maps from a model with the same name. If a string is given and initialize is True we will
                interpret the string as a folder with the maps to set_current_map. If a dict is given and initialize is True we
                will initialize from the dict directly.
            store_samples (boolean): if set to False we will store none of the samples. Use this
                if you are only interested in the volume maps and not in the entire sample chain.
        """
        self.recalculate = recalculate

        self._model = model
        self._problem_data = problem_data
        self._output_folder = output_folder
        self._output_path = os.path.join(output_folder, model.name, 'samples')
        self._sampler = sampler
        self._logger = logging.getLogger(__name__)
        self._processing_strategy = processing_strategy
        self._initialize = initialize
        self._initialize_using = initialize_using
        self._store_samples = store_samples

        if not model.is_protocol_sufficient(problem_data.protocol):
            raise InsufficientProtocolError(
                'The provided protocol is insufficient for this model. '
                'The reported errors where: {}'.format(model.get_protocol_problems(problem_data.protocol)))

    def run(self):
        with per_model_logging_context(self._output_folder):
            self._model.set_problem_data(self._problem_data)

            if self.recalculate:
                if os.path.exists(self._output_path):
                    shutil.rmtree(self._output_path)
            else:
                if model_output_exists(self._model, self._output_path + '/volume_maps/',
                                       append_model_name_to_path=False):
                    self._logger.info('Not recalculating {} model'.format(self._model.name))
                    return load_samples(self._output_path)

            if not os.path.isdir(self._output_path):
                os.makedirs(self._output_path)

            with self._logging():
                self._model.set_initial_parameters(self._get_initialization_params())

                worker_generator = SimpleModelProcessingWorkerGenerator(
                    lambda *args: SamplingProcessingWorker(self._sampler, self._store_samples, *args))

                return self._processing_strategy.run(self._model, self._problem_data,
                                                     self._output_path, self.recalculate, worker_generator)

    def _get_initialization_params(self):
        logger = logging.getLogger(__name__)

        if self._initialize:
            maps = None
            if self._initialize_using is None:
                folder = os.path.join(self._output_folder, self._model.name)
                logger.info("Initializing sampler using maps in {}".format(folder))
                maps = create_roi(Nifti.read_volume_maps(folder), self._problem_data.mask)

            elif isinstance(self._initialize_using, string_types):
                logger.info("Initializing sampler using maps in {}".format(self._initialize_using))
                maps = create_roi(Nifti.read_volume_maps(self._initialize_using), self._problem_data.mask)

            elif isinstance(self._initialize_using, dict):
                logger.info("Initializing sampler using given maps.")
                maps = {}
                for key, value in self._initialize_using.items():
                    if isinstance(value, string_types):
                        maps[key] = create_roi(nib.load(value).get_data(), self._problem_data.mask)
                    elif is_scalar(value):
                        maps[key] = value
                    else:
                        maps[key] = create_roi(value, self._problem_data.mask)

            if not maps:
                raise RuntimeError('No initialization maps found in the folder "{}"'.format(
                    os.path.join(self._output_folder, self._model.name)))

            return maps

        return {}

    @contextmanager
    def _logging(self):
        """Adds logging information around the processing."""
        minimize_start_time = timeit.default_timer()
        self._logger.info('Sampling {} model'.format(self._model.name))

        yield

        run_time = timeit.default_timer() - minimize_start_time
        run_time_str = time.strftime('%H:%M:%S', time.gmtime(run_time))
        self._logger.info('Sampled {0} model with runtime {1} (h:m:s).'.format(self._model.name, run_time_str))
