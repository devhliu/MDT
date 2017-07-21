import numpy as np

from mdt.component_templates.composite_models import DMRICompositeModelTemplate

__author__ = 'Robbert Harms'
__date__ = '2017-07-19'
__maintainer__ = 'Robbert Harms'
__email__ = 'robbert.harms@maastrichtuniversity.nl'
__licence__ = 'LGPL v3'


class ActiveAx(DMRICompositeModelTemplate):

    description = '''
        The ActiveAx model for use in in-vivo measurements.

        This model has a CSF compartment and white matter intrinsic diffusivity is fixed at 1.7E-9 m^2/s and 
        CSF diffusivity at 3.0E-9 m^2/s. (In CAMINO this model is listed as "MMWMD_INVIVO").
    '''
    model_expression = '''
        S0 * ((Weight(w_ic) * CylinderGPD) +
              (Weight(w_ec) * Zeppelin) +
              (Weight(w_csf) * Ball))
    '''
    inits = {
        'w_csf.w': 0.01
    }
    fixes = {'CylinderGPD.d': 1.7e-9,
             'Zeppelin.d': 1.7e-9,
             'Ball.d': 3.0e-9,
             'Zeppelin.dperp0': 'Zeppelin.d * (w_ec.w / (w_ec.w + w_ic.w))',
             'Zeppelin.theta': 'CylinderGPD.theta',
             'Zeppelin.phi': 'CylinderGPD.phi'}
    post_optimization_modifiers = [
        ('AxonDensityIndex', lambda d: (4 * (d['w_ic.w'] / (d['w_ec.w'] + d['w_ic.w'])))
                                       / (np.pi * (2 * d['CylinderGPD.R']) ** 2)),
    ]


class ActiveAx_ExVivo(DMRICompositeModelTemplate):

    description = '''
        The ActiveAx model for use in ex-vivo measurements.

        This model has all the compartments as described in Alexander et al NIMG 2010. The white matter intrinsic
        diffusivity is fixed at 0.6e-9 m^2/s and CSF diffusivity is fixed at 2.0e-9 m^2/s. 
        (In CAMINO this model is listed as "MMWMD_Fixed").
    '''
    model_expression = '''
        S0 * ((Weight(w_ic) * CylinderGPD) +
              (Weight(w_ec) * Zeppelin) +
              (Weight(w_csf) * Ball) + 
              (Weight(w_stat) * Dot))
    '''
    inits = {
        'w_csf.w': 0.01,
        'w_stat.w': 0.01
    }
    fixes = {
        'CylinderGPD.d': 0.6e-9,
        'Zeppelin.d': 0.6e-9,
        'Ball.d': 2.0e-9,
        'Zeppelin.dperp0': 'Zeppelin.d * (w_ec.w / (w_ec.w + w_ic.w))',
        'Zeppelin.theta': 'CylinderGPD.theta',
        'Zeppelin.phi': 'CylinderGPD.phi'
    }
    post_optimization_modifiers = [
        ('AxonDensityIndex', lambda d: (4 * (d['w_ic.w'] / (d['w_ec.w'] + d['w_ic.w'])))
                                        / (np.pi * (2 * d['CylinderGPD.R'])**2)),
    ]
