#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
import argparse
import sys
import mdt
from mdt.models.cascade import DMRICascadeModelInterface
from mdt.shell_utils import BasicShellApplication

__author__ = 'Robbert Harms'
__date__ = "2015-08-18"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class PrintAbstractModelFunction(BasicShellApplication):

    def _get_arg_parser(self):
        description = "This script prints the abstract model function for any of the (non-cascade) models in MDT.\n\n" \
                      "For example, to print the abstract 'BallStick' model function run: \n" \
                      "\tmdt-print-abstract-model-function BallStick\n"
        description += mdt.shell_utils.get_citation_message()

        parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('model', metavar='model', choices=mdt.get_models_list(), help='the model to print')
        return parser

    def run(self, args):
        model_name = args.model
        model = mdt.get_model(model_name)

        if isinstance(model, DMRICascadeModelInterface):
            print('Printing an abstract model function is not supported for cascade models.')
            sys.exit(2)

        print(model.get_abstract_model_function())


if __name__ == '__main__':
    PrintAbstractModelFunction().start()