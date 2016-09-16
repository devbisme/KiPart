# MIT license
# 
# Copyright (C) 2016 by XESS Corporation.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


"""
Parsers for LiCad schematic symbol library files.
"""



from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import open
from future import standard_library
standard_library.install_aliases()

import argparse as ap
import os
import sys
import re
from pyparsing import *

from .py_2_3 import *

from .__init__ import __version__

THIS_MODULE = locals()

def _parse_lib_kicad(text):
    """
    Return a pyparsing object storing the contents of a KiCad symbol library.
    """

    # Basic parser elements.
    terminator_char = '|'
    terminator = Literal(terminator_char + '\n').suppress()
    fnum = Group(Word(nums) + Optional(Literal('.') + Optional(Word(nums))))
    string = Word(printables, excludeChars=terminator_char)
    qstring = dblQuotedString() ^ sglQuotedString()
    qstring.addParseAction(removeQuotes)
    anystring = qstring ^ string

    #------------------ Schematic symbol parser.--------------------

    # Field section parser. (Fields are ignored.)
    field_start = CaselessLiteral('F') + Word(nums)('field_num')
    field = field_start + restOfLine
    fields = ZeroOrMore(field).suppress()  # Just ignore all fields.

    # Part aliases. (Aliases are ignored.)
    aliases = ZeroOrMore(CaselessKeyword('ALIAS') + restOfLine()).suppress()

    # Footprint section. (Footprints are ignored.)
    foot_start = (CaselessKeyword('$FPLIST') + restOfLine).suppress()
    foot_end = (CaselessKeyword('$ENDFPLIST') + restOfLine).suppress()
    footprint = (anystring + restOfLine).suppress()
    footprints = Optional(foot_start + ZeroOrMore(footprint) + foot_end).suppress()

    # Draw section parser.
    draw_start = (CaselessKeyword('DRAW') + restOfLine).suppress()
    draw_end = (CaselessKeyword('ENDDRAW') + terminator).suppress()
    draw_pin = Group(Word('Xx', exact=1).suppress() + anystring('name') + anystring('num') + \
                (anystring * 3).suppress() + anystring('orientation') + \
                (anystring * 2).suppress() + anystring('unit') + anystring.suppress() + \
                anystring('type') + Optional(anystring)('style') + terminator)
    draw_other = (Word('AaCcPpSsTt', exact=1) + White() + restOfLine).suppress()
    draw_element = draw_pin ^ draw_other
    draw = Group(draw_start + ZeroOrMore(draw_element) + draw_end)('pins')

    # Complete schematic symbol definition parser.
    def_start = CaselessKeyword('DEF').suppress() + anystring('name') + anystring('ref_id') + restOfLine.suppress()
    def_end = (CaselessKeyword('ENDDEF') + terminator).suppress()
    defn = Group(def_start + (fields & aliases & footprints & draw) + def_end)

    # Parser for set of schematic symbol definitions.
    defs = ZeroOrMore(defn)

    # Parser for entire library.
    version = CaselessKeyword('EESchema-LIBRARY').suppress() + \
            CaselessKeyword('version').suppress() + fnum('version') + terminator
    end_of_file = Optional(White()) + stringEnd
    lib = version + defs('parts') + end_of_file

    #---------------------- End of parser -------------------------

    # Remove all comments from the text to be parsed but leave the lines blank.
    # (Don't delete the lines or else it becomes hard to find the line in the file
    # that made the parser fail.)
    text = re.sub('(^|\n)#.*?(?=\n)', '\n', text)

    # Terminate all lines with the terminator string.
    # (This makes it easier to handle each line without accidentally getting
    # stuff from the next line.)
    text = re.sub('\n', ' '+terminator_char + '\n', text)

    # Remove the terminator from all lines that just have the terminator character on them.
    # (Don't delete the lines or else it becomes hard to find the line in the file
    # that made the parser fail.)
    text = re.sub('\n *\\' + terminator_char + ' *(?=\n)', '\n', text)

    # Return the parsed text.
    return lib.parseString(text)


def _parse_lib(src, tool='kicad'):
    """
    Return a pyparsing object storing the contents of a schematic symbol library.

    Args:
        src: Either a text string, or a filename, or a file object that stores
            the netlist.

    Returns:
        A pyparsing object that stores the library contents.

    Exception:
        PyparsingException.
    """

    try:
        text = src.read()
    except Exception:
        try:
            text = open(src,'r').read()
        except Exception:
            text = src

    if not isinstance(text, basestring):
        raise Exception("What is this shit you're handing me? [{}]\n".format(src))

    try:
        # Use the tool name to find the function for loading the library.
        func_name = '_parse_lib_{}'.format(tool)
        parse_func = THIS_MODULE[func_name]
        return parse_func(text)
    except KeyError:
        # OK, that didn't work so well...
        logger.error('Unsupported ECAD tool library: {}'.format(tool))
        raise Exception

def _gen_csv(parsed_lib):
    '''Return multi-line CSV string for the parts in a parsed schematic library.'''

    type_tbl = {'I':'in', 'O':'out', 'B':'bidir', 'T':'tri', 'P':'passive', 'U':'unspecified', 'W':'pwr', 'w':'pwr_out', 'C':'open_collector', 'E':'open_emitter', 'N':'NC'}
    orientation_tbl = {'R':'left', 'L':'right', 'U':'bottom', 'D':'top'}
    style_tbl = {'':'', 'I':'inv', 'C':'clk', 'IC':'inv_clk', 'L':'input_low', 'CL':'clk_low', 'V':'output_low', 'F':'falling_clk', 'X':'non_logic'}

    csv = ''
    for part in parsed_lib.parts:
        csv += '{part.name},{part.ref_id},,,,\n'.format(**locals())
        csv += 'Pin,Name,Type,Side,Unit,Style\n'

        def zero_pad_nums(s):
            # Pad all numbers in the string with leading 0's.
            # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
            # appear before A10 in a list.
            try:
                return re.sub(r'\d+', lambda mtch: '0' * (8 - len(mtch.group(0))) + mtch.group(0), s)
            except TypeError:
                return s # The input is probably not a string, so just return it unchanged.

        def num_key(pin):
            '''Generate a key from a pin's number so they are sorted by position on the package.'''

            # Pad all numeric strings in the pin name with leading 0's.
            # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
            # appear before A10 in a list.
            return zero_pad_nums(pin.unit) + zero_pad_nums(pin.num)

        for p in sorted(part.pins, key=num_key):
            # Replace commas in pin numbers, names and units so it doesn't screw-up the CSV file.
            p.num = re.sub(',', ';', p.num)
            p.name = re.sub(',', ';', p.name)
            p.unit = re.sub(',', ';', p.unit)
            csv += ','.join([p.num, p.name, type_tbl[p.type], orientation_tbl[p.orientation], p.unit, style_tbl[p.style]]) + '\n'
        csv += ',,,,,\n'
    csv += '\n'
    return csv

def main():
    parser = ap.ArgumentParser(
        description=
        'Convert a KiCad schematic symbol library file into a CSV file for KiPart.')

    parser.add_argument('-v', '--version',
        action='version',
        version='kilib2csv ' + __version__)
    parser.add_argument(
        'input_files',
        nargs='+',
        type=str,
        metavar='file.lib',
        help='KiCad schematic symbol library.')
    parser.add_argument('-o', '--output',
        nargs='?',
        type=str,
        metavar='file.csv',
        help='CSV file created from schematic library file.')
    parser.add_argument('-a', '--append',
        action='store_true',
        help='Append to an existing CSV file.')
    parser.add_argument('-w', '--overwrite',
        action='store_true',
        help='Allow overwriting of an existing CSV file.')

    args = parser.parse_args()

    if args.output:
        args.output = os.path.splitext(args.output)[0] + '.csv'
    else:
        args.output = os.path.splitext(sys.argv[0])[0] + '.csv'

    if os.path.isfile(args.output):
        if not (args.overwrite or args.append):
            print('Output file {} already exists! Use the --overwrite option to replace it or the --append option to append to it.'.format(
                args.output))
            sys.exit(1)

    file_mode = 'a' if args.append else 'w'
    with open(args.output, file_mode) as out_file:
        for lib in args.input_files:
            parsed_lib = _parse_lib(lib)
            out_file.write(_gen_csv(parsed_lib)) 

# main entrypoint.
if __name__ == '__main__':
    main()

