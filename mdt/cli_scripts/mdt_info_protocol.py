#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
import argparse
import os
import mdt
from argcomplete.completers import FilesCompleter
import textwrap

from mdt.protocols import column_names_nice_ordering
from mdt.shell_utils import BasicShellApplication

__author__ = 'Robbert Harms'
__date__ = "2015-08-18"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class InfoProtocol(BasicShellApplication):

    def _get_arg_parser(self):
        description = textwrap.dedent("""
            Print some basic information about a protocol.
        """)
        description += self._get_citation_message()

        epilog = textwrap.dedent("""
            Examples of use:
                mdt-info-protocol my_protocol.prtcl
        """)

        parser = argparse.ArgumentParser(description=description, epilog=epilog,
                                         formatter_class=argparse.RawTextHelpFormatter)

        parser.add_argument('protocol',
                            action=mdt.shell_utils.get_argparse_extension_checker(['.prtcl']),
                            help='the protocol file').completer = FilesCompleter(['prtcl'], directories=False)

        return parser

    def run(self, args):
        protocol = mdt.load_protocol(os.path.realpath(args.protocol))
        self.print_info(protocol)

    def print_info(self, protocol):
        row_format = "{:<15}{}"

        print(row_format.format('nmr_rows', protocol.length))
        print(row_format.format('nmr_unweighted', len(protocol.get_unweighted_indices())))
        print(row_format.format('nmr_weighted', len(protocol.get_weighted_indices())))
        print(row_format.format('nmr_shells', len(protocol.get_b_values_shells())))
        print(row_format.format('shells', ', '.join(map(lambda s: '{:0=.3f}e9'.format(s/1e9),
                                                        protocol.get_b_values_shells()))))
        print(row_format.format('nmr_columns', protocol.number_of_columns))
        print(row_format.format('columns', ', '.join(column_names_nice_ordering(protocol.column_names))))


if __name__ == '__main__':
    InfoProtocol().start()