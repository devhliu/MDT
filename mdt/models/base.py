__author__ = 'Robbert Harms'
__date__ = "2015-10-27"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class DMRIOptimizable(object):
    """This is an interface for some base methods we expect in an MRI model.

    Since we have both single dMRI models and cascade models we must have an overarching interface to make
    sure that both type of models implement the same methods. This is that interface. The methods in this interface
    have little to do with modelling, but unify the required methods in the cascades and single models.
    """

    @property
    def double_precision(self):
        """If this model will calculate in double precision."""
        return 0

    @double_precision.setter
    def double_precision(self, double_precision):
        """Set if this model will calculate in double precision."""

    def is_protocol_sufficient(self, protocol=None):
        """Check if the protocol holds enough information for this model to work.

        Args:
            protocol (Protocol): The protocol object to check for sufficient information. If set the None, the
                current protocol in the problem data is used.

        Returns:
            boolean: True if there is enough information in the protocol, false otherwise
        """

    def get_protocol_problems(self, protocol=None):
        """Get all the problems with the protocol.

        Args:
            protocol (Protocol): The protocol object to check for problems. If set the None, the
                current protocol in the problem data is used.

        Returns:
            list of ModelProtocolProblem: A list of ModelProtocolProblem instances or subclasses of that baseclass.
                These objects indicate the problems with the protocol and this model.
        """

    def get_required_protocol_names(self):
        """Get a list with the constant data names that are needed for this model to work.

        For example, an implementing diffusion MRI model might require the presence of the protocol parameter
        'g' and 'b'. This function should then return ('g', 'b').

        Returns:
            A list of columns names that are to be taken from the protocol data.
        """