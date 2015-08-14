# -*- coding: utf-8 -*-

# MIT license
# 
# Copyright (C) 2015 by XESS Corp.
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

import sys
import warnings
import math
import copy
import re
import csv
from collections import defaultdict
from affine import Affine
import difflib

__all__ = ['kipart']  # Only export this routine for use by the outside world.

THIS_MODULE = sys.modules[__name__]  # Ref to this module for making named calls.

# DEFAULT_UNIT = 1
# DEFAULT_PIN_TYPE = 'bidirectional'
# DEFAULT_PIN_STYLE = 'line'
# DEFAULT_PIN_SIDE = 'left'

COLUMN_NAMES = {'pin':'num', 'num':'num', 'name':'name', 'type':'type', 'style':'style', 'side':'side', 'unit':'unit', 'bank':'unit'}

# This is just a vanilla object class for device pins. 
# We'll add attributes to it as needed.
class Pin:
    pass
    
DEFAULT_PIN = Pin()
DEFAULT_PIN.num = None
DEFAULT_PIN.name = ''
DEFAULT_PIN.type = 'io'
DEFAULT_PIN.style = 'line'
DEFAULT_PIN.unit = 1
DEFAULT_PIN.side = 'left'

    
def num_row_elements(row):
    '''Get number of elements in CSV row.'''
    try:
        rowset = set(row)
        rowset.discard('')
        return len(rowset)
    except TypeError:
        return 0

        
def get_nonblank_row(csv_reader):
    '''Return the first non-blank row encountered from the current point in a CSV file.'''
    for row in csv_reader:
        if num_row_elements(row) > 0:
            return row
    return None

    
def get_part_num(csv_reader):
    '''Get the part number from a row of the CSV file.'''
    part_num = get_nonblank_row(csv_reader)
    try:
        part_num = set(part_num)
        part_num.discard('')
        return part_num.pop()
    except TypeError:
        return None

    
def find_closest_match(name, name_dict, fuzzy_match, threshold=0.0):
    '''Approximate matching subroutine'''
    # Scrub non-alphanumerics from name and lowercase it.
    scrubber = re.compile('[\W.]+')
    name = scrubber.sub('', name).lower()
    
    # Return regular dictionary lookup if fuzzy matching is not enabled.
    if fuzzy_match == False:
        return name_dict[name]

    # Find the closest fuzzy match to the given name in the scrubbed list.
    # Set the matching threshold to 0 so it always gives some result.
    match = difflib.get_close_matches(name, name_dict.keys(), 1, threshold)[0]

    return name_dict[match]
    
    
def clean_headers(headers):
    '''Return a list of the closest valid column headers for the headers found in the file.'''
    return [find_closest_match(h,COLUMN_NAMES,True) for h in headers]

    
def generic_reader(csv_file, bundle):
    '''Extract pin data from a CSV file and return a dictionary of pin data.
       The CSV file contains one or more groups of rows formatted as follows:
           A row with a single field containing the part number.
           Zero or more blank rows.
           A row containing the column headers:
               'Pin', 'Unit', 'Type', 'Style', 'Side', and 'Name'.
               (Only 'Pin' and 'Name' are required. The order of
               the columns is not important.)
           Each succeeding row should contain:
               The 'Pin' column should contain the pin number.
               The 'Unit' column specifies the bank or unit number for the pin.
               The 'Type' column specifies the pin type (input, output,...).
               The 'Style' column specifies the pin's schematic style.
               The 'Side' column specifies the side of the symbol the pin is on.
               The 'Name' column contains the pin name.
           A blank row terminates the pin data for the part and begins
           a new group of rows for another part.
    '''

    while True:
        # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
        # contains another dictionary that uses the side of the symbol as a key. Each entry in
        # that dictionary uses the pin names in that unit and on that side as keys. Each entry
        # in that dictionary is a list of Pin objects with each Pin object having the same name
        # as the dictionary key. So the pins are separated into units at the top level, and then
        # the sides of the symbol, and then the pins with the same name that are on that side
        # of the unit.
        pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        # Create a reader that starts from the current position in the CSV file.
        csv_reader = csv.reader(csv_file,  skipinitialspace=True)
        
        # Extract part number from the first non-blank line. Break out of the infinite
        # while loop and stop processing this file if no part number is found.
        part_num = get_part_num(csv_reader)
        if part_num is None:
            break

        # Get the column header row for the part's pin data.
        headers = clean_headers(get_nonblank_row(csv_reader))
        
        # Now create a DictReader for grabbing the pin data in each row.
        dict_reader = csv.DictReader(csv_file, headers, skipinitialspace=True)
        for index, row in enumerate(dict_reader):
        
            # A blank line signals the end of the pin data.
            if num_row_elements(row.values()) == 0:
                break

            # Get the pin attributes from the cells of the row of data.
            pin = copy.copy(DEFAULT_PIN)
            pin.index = index
            for c, a in COLUMN_NAMES.items():
                try:
                    setattr(pin, a, row[c])
                except KeyError:
                    pass
            if pin.num is None:
                raise Exception('ERROR: No pin number on row {index} of {part_num}'.format(index=index, part_num=part_num))
            # pin.name = row['name']
            # pin.num = row['pin']
            # try:
                # pin.unit = row['unit']
            # except KeyError:
                # try:
                    # pin.unit = row['bank']
                # except KeyError:
                    # pin.unit = DEFAULT_UNIT
            # try:
                # pin.side = row['side']
            # except KeyError:
                # pin.side = DEFAULT_PIN_SIDE
            # try:
                # pin.style = row['style']
            # except KeyError:
                # pin.style = DEFAULT_PIN_STYLE
            # try:
                # pin.type = row['type']
            # except KeyError:
                # pin.type = DEFAULT_PIN_TYPE

            # Add the pin from this row of the CVS file to the pin dictionary.
            if bundle:
                # If bundling like-named pins, place all the pins into a list under their common name.
                pin_data[pin.unit][pin.side][pin.name].append(pin)
            else:
                # If each like-named pin should be shown separately, place each pin into a 
                # single-element list under the pin name with the unique row index appended
                # to differentiate the pin names.
                pin_data[pin.unit][pin.side][pin.name + '_' + str(index)].append(
                    pin)

        yield part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.

        
def psoc5lp_pin_name_process(name):
#    leading_paren = re.compile(r'^\s*(?P<paren>\([^)]*\))\s*(?<pin_name>.+)$', re.IGNORECASE)
#    leading_paren = re.compile(r'^\s*(?P<paren>\([^)]*\))', re.IGNORECASE)
    leading_paren = re.compile(r'^\s*(?P<paren>\([^)]*\))\s*(?P<pin_name>.+)$', re.IGNORECASE)
    m = leading_paren.match(name)
    if m is not None:
        name = m.group('pin_name') + ' ' + m.group('paren')
    name = re.sub(r'^\s+','',name) # Remove leading spaces.
    name = re.sub(r'\s+$','',name) # Remove trailing spaces.
    name = re.sub(r'\s*([-@#$%^&*_=+|",.<>!;?]+)\s*',r'\1',name) # Remove spaces around punc.
    name = re.sub(r'([\[\{\(]+)\s*',r'\1',name) # Remove spaces around braces and such.
    name = re.sub(r'\s*([\]\}\)]+)',r'\1',name) # Remove spaces around braces and such.
    name = re.sub(r'\s+','_',name) # Replace spaces with underscores.
    return name

        
def psoc5lp_reader(csv_file, bundle):
    '''Extract pin data from a Cypress PSoC5LP CSV file and return a dictionary of pin data.
       The CSV file contains one or more groups of rows formatted as follows:
           A row with a single field containing the part number.
           Zero or more blank rows.
           A row containing the column headers:
               'Pin', 'Unit', 'Type', 'Style', 'Side', and 'Name'.
               (Only 'Pin' and 'Name' are required. The order of
               the columns is not important.)
           Each succeeding row should contain:
               The 'Pin' column should contain the pin number.
               The 'Unit' column specifies the bank or unit number for the pin.
               The 'Type' column specifies the pin type (input, output,...).
               The 'Style' column specifies the pin's schematic style.
               The 'Side' column specifies the side of the symbol the pin is on.
               The 'Name' column contains the pin name.
           A blank row terminates the pin data for the part and begins
           a new group of rows for another part.
    '''

    while True:
        # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
        # contains another dictionary that uses the side of the symbol as a key. Each entry in
        # that dictionary uses the pin names in that unit and on that side as keys. Each entry
        # in that dictionary is a list of Pin objects with each Pin object having the same name
        # as the dictionary key. So the pins are separated into units at the top level, and then
        # the sides of the symbol, and then the pins with the same name that are on that side
        # of the unit.
        pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        # Create a reader that starts from the current position in the CSV file.
        csv_reader = csv.reader(csv_file,  skipinitialspace=True)
        
        # Extract part number from the first non-blank line. Break out of the infinite
        # while loop and stop processing this file if no part number is found.
        part_num = get_part_num(csv_reader)
        if part_num is None:
            break

        # Get the column header row for the part's pin data.
        headers = clean_headers(get_nonblank_row(csv_reader))
        
        # Now create a DictReader for grabbing the pin data in each row.
        dict_reader = csv.DictReader(csv_file, headers, skipinitialspace=True)
        for index, row in enumerate(dict_reader):
        
            # A blank line signals the end of the pin data.
            if num_row_elements(row.values()) == 0:
                break

            # Get the pin attributes from the cells of the row of data.
            pin = copy.copy(DEFAULT_PIN)
            pin.index = index
            pin.type = ''
            for c, a in COLUMN_NAMES.items():
                try:
                    setattr(pin, a, row[c])
                except KeyError:
                    pass
            if pin.num is None:
                raise Exception('ERROR: No pin number on row {index} of {part_num}'.format(index=index, part_num=part_num))
            pin.name = psoc5lp_pin_name_process(pin.name)
            if pin.type == '':
                # No explicit pin type, so infer it from the pin name.
                DEFAULT_PIN_TYPE = 'input'  # Assign this pin type if name inference can't be made.
                PIN_TYPE_PREFIXES = {
                    r'P[0-9]+\[[0-9]+\]': 'bidirectional',
                    r'VCC': 'power_out',
                    r'VDD': 'power_in',
                    r'VSS': 'power_in',
                    r'IND': 'passive',
                    r'VBOOST': 'input',
                    r'VBAT': 'power_in',
                    r'XRES': 'input',
                    r'NC': 'no_connect',
                }
                for prefix, typ in PIN_TYPE_PREFIXES.items():
                    if re.match(prefix, pin.name, re.IGNORECASE):
                        pin.type = typ
                        break
                else:
                    warnings.warn('No match for {} on {}, assigning as {}'.format(
                        pin.name, part_num, DEFAULT_PIN_TYPE))
                    pin.type = DEFAULT_PIN_TYPE

            # pin = Pin()
            # pin.index = index
            # pin.name = psoc5lp_pin_name_process(row['name'])
            # pin.num = row['pin']
            # try:
                # pin.unit = row['unit']
            # except KeyError:
                # pin.unit = DEFAULT_UNIT
            # try:
                # pin.side = row['side']
            # except KeyError:
                # pin.side = DEFAULT_PIN_SIDE
            # try:
                # pin.style = row['style']
            # except KeyError:
                # pin.style = DEFAULT_PIN_STYLE
            # try:
                # pin.type = row['type']
                # if pin.type == '':
                    # raise KeyError
            # except KeyError:
                # # No explicit pin type, so infer it from the pin name.
                # DEFAULT_PIN_TYPE = 'input'  # Assign this pin type if name inference can't be made.
                # PIN_TYPE_PREFIXES = {
                    # r'P[0-9]+\[[0-9]+\]': 'bidirectional',
                    # r'VCC': 'power_out',
                    # r'VDD': 'power_in',
                    # r'VSS': 'power_in',
                    # r'IND': 'passive',
                    # r'VBOOST': 'input',
                    # r'VBAT': 'power_in',
                    # r'XRES': 'input',
                    # r'NC': 'no_connect',
                # }
                # for prefix, typ in PIN_TYPE_PREFIXES.items():
                    # if re.match(prefix, pin.name, re.IGNORECASE):
                        # pin.type = typ
                        # break
                # else:
                    # warnings.warn('No match for {} on {}, assigning as {}'.format(
                        # pin.name, part_num, DEFAULT_PIN_TYPE))
                    # pin.type = DEFAULT_PIN_TYPE

            # Add the pin from this row of the CVS file to the pin dictionary.
            if bundle:
                # If bundling like-named pins, place all the pins into a list under their common name.
                pin_data[pin.unit][pin.side][pin.name].append(pin)
            else:
                # If each like-named pin should be shown separately, place each pin into a 
                # single-element list under the pin name with the unique row index appended
                # to differentiate the pin names.
                pin_data[pin.unit][pin.side][pin.name + '_' + str(index)].append(
                    pin)

        yield part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.


def xilinx7_reader(csv_file, bundle):
    '''Extract the pin data from a Xilinx CSV file and return a dictionary of pin data.'''

    # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
    # contains another dictionary that uses the side of the symbol as a key. Each entry in
    # that dictionary uses the pin names in that unit and on that side as keys. Each entry
    # in that dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into units at the top level, and then
    # the sides of the symbol, and then the pins with the same name that are on that side
    # of the unit.
    pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # Read title line of the CSV file and extract the part number.
    title = csv_file.readline()
    _, part_num, date, time, _ = re.split('\s+', title)

    # Dump the blank line between the title and the part's pin data.
    _ = csv_file.readline()

    # Create a reader object for the rows of the CSV file and read it row-by-row.
    csv_reader = csv.DictReader(csv_file, skipinitialspace=True)
    for index, row in enumerate(csv_reader):
        # A blank line signals the end of the pin data.
        if row['Pin'] == '':
            break

        # Get the pin attributes from the cells of the row of data.
        pin = Pin()
        pin.index = index
        pin.name = row['Pin Name']
        pin.num = row['Pin']
        pin.unit = row['Bank']
        pin.side = DEFAULT_PIN_SIDE
        pin.style = DEFAULT_PIN_STYLE

        # The type of the pin isn't given in the CSV file, so we'll have to infer it
        # from the name of the pin. Pin names starting with the following prefixes 
        # are assigned the given pin type.
        DEFAULT_PIN_TYPE = 'input'  # Assign this pin type if name inference can't be made.
        PIN_TYPE_PREFIXES = {
            r'VCC': 'power_in',
            r'GND': 'power_in',
            r'IO_': 'bidirectional',
            r'DONE': 'output',
            r'VREF[PN]_': 'input',
            r'TCK': 'input',
            r'TDI': 'input',
            r'TDO': 'output',
            r'TMS': 'input',
            r'CCLK': 'input',
            r'M0': 'input',
            r'M1': 'input',
            r'M2': 'input',
            r'INIT_B': 'input',
            r'PROG': 'input',
            r'NC': 'no_connect',
            r'VP_': 'input',
            r'VN_': 'input',
            r'DXP_': 'passive',
            r'DXN_': 'passive',
            r'CFGBVS_': 'input',
            r'MGTZ?REFCLK[0-9]+[NP]_': 'input',
            r'MGTZ_OBS_CLK_[PN]_': 'input',
            r'MGT[ZPHX]TX[NP][0-9]+_': 'output',
            r'MGT[ZPHX]RX[NP][0-9]+_': 'input',
            r'MGTAVTTRCAL_': 'passive',
            r'MGTRREF_': 'passive',
            r'MGTVCCAUX_?': 'power_in',
            r'MGTAVTT_?': 'power_in',
            r'MGTZ_THERM_IN_': 'input',
            r'MGTZ_THERM_OUT_': 'input',
            r'MGTZ?A(VCC|GND)_?': 'power_in',
            r'MGTZVCC[LH]_': 'power_in',
            r'MGTZ_SENSE_(A?VCC|A?GND)[LH]?_': 'power_in',
            r'RSVD(VCC[1-3]|GND)': 'power_in',
            r'PS_CLK_': 'input',
            r'PS_POR_B': 'input',
            r'PS_SRST_B': 'input',
            r'PS_DDR_CK[PN]_': 'output',
            r'PS_DDR_CKE_': 'output',
            r'PS_DDR_CS_B_': 'output',
            r'PS_DDR_RAS_B_': 'output',
            r'PS_DDR_CAS_B_': 'output',
            r'PS_DDR_WE_B_': 'output',
            r'PS_DDR_BA[0-9]+_': 'output',
            r'PS_DDR_A[0-9]+_': 'output',
            r'PS_DDR_ODT_': 'output',
            r'PS_DDR_DRST_B_': 'output',
            r'PS_DDR_DQ[0-9]+_': 'bidirectional',
            r'PS_DDR_DM[0-9]+_': 'output',
            r'PS_DDR_DQS_[PN][0-9]+_': 'bidirectional',
            r'PS_DDR_VR[PN]_': 'power_out',
            r'PS_DDR_VREF[0-9]+_': 'power_in',
            r'PS_MIO_VREF_': 'power_in',
            r'PS_MIO[0-9]+_': 'bidirectional',
        }
        for prefix, typ in PIN_TYPE_PREFIXES.items():
            if re.match(prefix, pin.name, re.IGNORECASE):
                pin.type = typ
                break
        else:
            warnings.warn('No match for {} on {}, assigning as {}'.format(
                pin.name, part_num[:4], DEFAULT_PIN_TYPE))
            pin.type = DEFAULT_PIN_TYPE

        # Add the pin from this row of the CVS file to the pin dictionary.
        if bundle:
            # If bundling like-named pins, place all the pins into a list under their common name.
            pin_data[pin.unit][pin.side][pin.name].append(pin)
        else:
            # If each like-named pin should be shown separately, place each pin into a 
            # single-element list under the pin name with the unique row index appended
            # to differentiate the pin names.
            pin_data[pin.unit][pin.side][pin.name + '_' + str(index)].append(
                pin)

    yield part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.

###########################################################################################
# Settings for creating the KiCad schematic part symbol.
# Dimensions are given in mils (0.001").

# Origin point.
XO = 0
YO = 0

# Pin settings.
PIN_LENGTH = 200
PIN_SPACING = 100
PIN_NUM_SIZE = 50  # Font size for pin numbers.
PIN_NAME_SIZE = 50  # Font size for pin names.
PIN_NAME_OFFSET = 40  # Separation between pin and pin name.
PIN_ORIENTATION = 'left'
PIN_STYLE = 'line'
SHOW_PIN_NUMBER = True  # Show pin numbers when True.
SHOW_PIN_NAME = True  # Show pin names when True.
SINGLE_PIN_SUFFIX = ''
MULTI_PIN_SUFFIX = '*'

# Settings for box drawn around pins in a unit.
BOX_LINE_WIDTH = 12
FILL = 'no_fill'

# Part reference.
REF_PREFIX = 'U'
REF_SIZE = 60  # Font size.
REF_Y_OFFSET = 250

# Part number.
PART_NUM_SIZE = 60  # Font size.
PART_NUM_Y_OFFSET = 150

# Mapping from understandable pin orientation name to the orientation
# indicator used in the KiCad part library. This mapping looks backward,
# but if pins are placed on the left side of the symbol, you actually
# want to use the pin symbol where the line points to the right. 
# The same goes for the other sides.
PIN_ORIENTATIONS = {'':'R', 'left': 'R', 'right': 'L', 'bottom': 'U', 'down':'U', 'top': 'D', 'up':'D',}
scrubber = re.compile('[\W.]+')
PIN_ORIENTATIONS = {scrubber.sub('', k).lower():v for k,v in PIN_ORIENTATIONS.items()}

ROTATION = {'left': 0, 'right': 180, 'bottom': 90, 'top': -90}

# Mapping from understandable pin type name to the type
# indicator used in the KiCad part library.
PIN_TYPES = {
    'input': 'I',
    'inp': 'I',
    'in': 'I',
    'clk': 'I',
    'output': 'O',
    'outp': 'O',
    'out': 'O',
    'bidirectional': 'B',
    'bidir': 'B',
    'bi': 'B',
    'inout': 'B',
    'io': 'B',
    'tristate': 'T',
    'tri': 'T',
    'passive': 'P',
    'pass': 'P',
    'unspecified': 'U',
    'un': 'U',
    '': 'U',
    'analog': 'U',
    'power_in': 'W',
    'pwr_in': 'W',
    'power': 'W',
    'pwr': 'W',
    'ground': 'W',
    'gnd': 'W',
    'power_out': 'w',
    'pwr_out': 'w',
    'pwr_o': 'w',
    'open_collector': 'C',
    'open_coll': 'C',
    'oc': 'C',
    'open_emitter': 'E',
    'open_emit': 'E',
    'oe': 'E',
    'no_connect': 'N',
    'no_conn': 'N',
    'nc': 'N',
}
PIN_TYPES = {scrubber.sub('', k).lower():v for k,v in PIN_TYPES.items()}

# Mapping from understandable pin drawing style to the style
# indicator used in the KiCad part library.
PIN_STYLES = {
    'line': '',
    '': '',
    'inverted': 'I',
    'inv': 'I',
    'clock': 'C',
    'clk': 'C',
    'rising_clk': 'C',
    'inverted_clock': 'IC',
    'inv_clk': 'IC',
    'input_low': 'L',
    'inp_low': 'L',
    'in_lw': 'L',
    'in_b': 'L',
    'clock_low': 'CL',
    'clk_low': 'CL',
    'clk_lw': 'CL',
    'clk_b': 'CL',
    'output_low': 'V',
    'outp_low': 'V',
    'out_lw': 'V',
    'out_b': 'V',
    'falling_edge_clock': 'F',
    'falling_clk': 'F',
    'non_logic': 'X',
    'nl': 'X',
    'analog': 'X',
}
PIN_STYLES = {scrubber.sub('', k).lower():v for k,v in PIN_STYLES.items()}

# Mapping from understandable box fill-type name to the fill-type
# indicator used in the KiCad part library.
FILLS = {'no_fill': 'N', 'fg_fill': 'F', 'bg_fill': 'f'}

# Format strings for various items in a KiCad part library.
LIB_HEADER = 'EESchema-LIBRARY Version 2.3\n'
START_DEF = 'DEF {name} {ref} 0 {pin_name_offset} {show_pin_number} {show_pin_name} {num_units} L N\n'
END_DEF = 'ENDDEF\n'
REF_FIELD = 'F0 "{ref_prefix}" {x} {y} {ref_size} H V {horiz_just} CNN\n'
PART_FIELD = 'F1 "{part_num}" {x} {y} {ref_size} H V {horiz_just} CNN\n'
START_DRAW = 'DRAW\n'
END_DRAW = 'ENDDRAW\n'
BOX = 'S {x0} {y0} {x1} {y1} {unit_num} 1 {line_width} {fill}\n'
PIN = 'X {name} {num} {x} {y} {length} {orientation} {num_sz} {name_sz} {unit_num} 1 {pin_type} {pin_style}\n'


def annotate_pins(unit_pins):
    '''Annotate pin names to indicate special information.'''
    for name, pins in unit_pins:
        # If there are multiple pins with the same name in a unit, then append a
        # distinctive suffix to the pin name to indicate multiple pins are placed
        # at a single location on the unit. (This is done so multiple pins that
        # should be on the same net (e.g. GND) can be connected using a single
        # net connection in the schematic.)
        name_suffix = SINGLE_PIN_SUFFIX
        if len(pins) > 1:
            name_suffix = MULTI_PIN_SUFFIX
        for pin in pins:
            pin.name += name_suffix


def pins_bbox(unit_pins):
    '''Return the bounding box of a column of pins and their names.'''

    if len(unit_pins) == 0:
        return [[XO, YO], [XO, YO]]  # No pins, so no bounding box.

    width = 0
    for name, pins in unit_pins:

        # Update the maximum observed width of a pin name. This is used later to
        # size the width of the box surrounding the pin names for this unit.
        width = max(width, len(pins[0].name) * PIN_NAME_SIZE)

    # Add the separation space before and after the pin name.
    width += PIN_LENGTH + 2 * PIN_NAME_OFFSET
    # Make bounding box an integer number of pin spaces so pin connections are always on the grid.
    width = math.ceil(float(width) / PIN_SPACING) * PIN_SPACING
    height = len(unit_pins) * PIN_SPACING

    return [[XO, YO + PIN_SPACING], [XO + width, YO - height]]


def draw_pins(lib_file, unit_num, unit_pins, transform, fuzzy_match):
    '''Draw a column of pins rotated/translated by the transform matrix.'''

    # Start drawing pins from the origin.
    x = XO
    y = YO

    for name, pins in unit_pins:

        # Start off creating visible pin numbers. If there are multiple pins with
        # the same name, then the 'visibility' will be turned off for any pins
        # after the first by reducing their pin number size to zero.
        num_size = PIN_NUM_SIZE

        # Rotate/translate the current drawing point.
        (draw_x, draw_y) = transform * (x, y)
        
        # Use approximate matching to determine the pin's type, style and orientation.
        pin_type = find_closest_match(pins[0].type, PIN_TYPES, fuzzy_match)
        pin_style = find_closest_match(pins[0].style, PIN_STYLES, fuzzy_match)
        pin_side = find_closest_match(pins[0].side, PIN_ORIENTATIONS, fuzzy_match)

        # Create all the pins with a particular name. If there are more than one,
        # they are laid on top of each other and only the first is visible.
        for pin in pins:

            # Create a pin using the pin data.
            lib_file.write(PIN.format(name=pin.name,
                                      num=pin.num,
                                      x=int(draw_x),
                                      y=int(draw_y),
                                      length=PIN_LENGTH,
                                      orientation=pin_side,
                                      num_sz=num_size,
                                      name_sz=PIN_NAME_SIZE,
                                      unit_num=unit_num,
                                      pin_type=pin_type,
                                      pin_style=pin_style))

            # Turn off visibility after the first pin.
            num_size = 0

        # Move to the next pin placement location on this unit.
        y = y - PIN_SPACING


def row_key(pin):
    '''Generate a key from the order the pins were entered into the CSV file.'''
    return pin[1][0].index


def num_key(pin):
    '''Generate a key from a pin's number so they are sorted by position on the package.'''

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
    # appear before A10 in a list.
    return re.sub(r'\d+', lambda mtch: '0'*(8-len(mtch.group(0))) + mtch.group(0), pin[1][0].num)


def name_key(pin):
    '''Generate a key from a pin's name so they are sorted more logically.'''

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'adc10' and 'adc2' will become 'adc00010' and 'adc00002' and adc2 will
    # appear before adc10 in a list.
    return re.sub(r'\d+', lambda mtch: '0'*(8-len(mtch.group(0))) + mtch.group(0), pin[1][0].name)


def draw_symbol(lib_file, part_num, pin_data, sort_type, fuzzy_match):
    '''Add a symbol for a part to the library.'''
    
    # Start the part definition with the header.
    lib_file.write(
        START_DEF.format(name=part_num,
                         ref=REF_PREFIX,
                         pin_name_offset=PIN_NAME_OFFSET,
                         show_pin_number=SHOW_PIN_NUMBER and 'Y' or 'N',
                         show_pin_name=SHOW_PIN_NAME and 'Y' or 'N',
                         num_units=len(pin_data)))

    # Determine if there are pins across the top of the symbol.
    # If so, right-justify the reference and part number so they don't
    # run into the top pins. If not, stick with left-justification.
    horiz_just = 'L'
    horiz_offset = PIN_LENGTH
    for unit in pin_data.values():
        if 'top' in unit.keys():
            horiz_just = 'R'
            horiz_offset = PIN_LENGTH - 50
            break

            # Create the field that stores the part reference.
    lib_file.write(REF_FIELD.format(ref_prefix=REF_PREFIX,
                                    x=XO + horiz_offset,
                                    y=YO + REF_Y_OFFSET,
                                    horiz_just=horiz_just,
                                    ref_size=REF_SIZE))

    # Create the field that stores the part number.
    lib_file.write(PART_FIELD.format(part_num=part_num,
                                     x=XO + horiz_offset,
                                     y=YO + PART_NUM_Y_OFFSET,
                                     horiz_just=horiz_just,
                                     ref_size=PART_NUM_SIZE))

    # Start the section of the part definition that holds the part's units.
    lib_file.write(START_DRAW)

    # Get a reference to the sort-key generation routine.
    key_func = getattr(THIS_MODULE, '{}_key'.format(sort_type))

    # Now create the units that make up the part. Unit numbers go from 1
    # up to the number of units in the part.
    for unit_num, unit in enumerate(pin_data.values(), 1):

        # The indices of the X and Y coordinates in a list of point coords.
        X = 0
        Y = 1

        # Initialize data structures that store info for each side of a schematic symbol unit.
        all_sides = ['left', 'right', 'top', 'bottom']
        bbox = {side: [(XO, YO), (XO, YO)] for side in all_sides}
        box_pt = {
            side: [XO + PIN_LENGTH, YO + PIN_SPACING]
            for side in all_sides
        }
        anchor_pt = {
            side: [XO + PIN_LENGTH, YO + PIN_SPACING]
            for side in all_sides
        }
        transform = {}

        # Annotate the pins for each side of the symbol and determine the bounding box
        # and various points for each side.
        for side, side_pins in unit.items():
            annotate_pins(side_pins.items())
            bbox[side] = pins_bbox(side_pins.items())
            #
            #     C     B-------A
            #           |       |
            #     ------| name1 |
            #           |       |
            #     ------| name2 |
            #
            # A = anchor point = upper-right corner of bounding box.
            # B = box point = upper-left corner of bounding box + pin length.
            # C = upper-left corner of bounding box.
            anchor_pt[side] = [max(bbox[side][0][X], bbox[side][1][X]),
                               max(bbox[side][0][Y], bbox[side][1][Y])]
            box_pt[side] = [
                min(bbox[side][0][X], bbox[side][1][X]) + PIN_LENGTH,
                max(bbox[side][0][Y], bbox[side][1][Y])
            ]

        # AL = left-side anchor point.
        # AB = bottom-side anchor point.
        # AR = right-side anchor point.
        # AT = top-side anchor-point.
        #        +-------------+          
        #        |             |          
        #        |     TOP     |          
        #        |             |          
        # +------AL------------AT         
        # |      |                        
        # |      |             +---------+
        # |      |             |         |
        # |  L   |             |         |
        # |  E   |             |    R    |
        # |  F   |             |    I    |
        # |  T   |             |    G    |
        # |      |             |    H    |
        # |      |             |    T    |
        # |      |             |         |
        # +------AB-------+    AR--------+
        #        | BOTTOM |               
        #        +--------+               
        #
        # This is the width and height of the box in the middle of the pins on each side.
        box_width = max(abs(bbox['top'][0][Y] - bbox['top'][1][Y]),
                        abs(bbox['bottom'][0][Y] - bbox['bottom'][1][Y]))
        box_height = max(abs(bbox['left'][0][Y] - bbox['left'][1][Y]),
                         abs(bbox['left'][0][Y] - bbox['right'][1][Y]))

        for side in all_sides:
            # Each side of pins starts off with the orientation of a left-hand side of pins.
            # Transformation matrix starts by rotating the side of pins.
            transform[side] = Affine.rotation(ROTATION[side])
            # Now rotate the anchor point to see where it goes.
            rot_anchor_pt = transform[side] * anchor_pt[side]
            # Translate the rotated anchor point to coincide with the AL anchor point.
            translate_x = anchor_pt['left'][X] - rot_anchor_pt[X]
            translate_y = anchor_pt['left'][Y] - rot_anchor_pt[Y]
            # Make additional translation to bring the AL point to the correct position.
            if side == 'right':
                # Translate AL to AR.
                translate_x += box_width
                translate_y -= box_height
            elif side == 'bottom':
                # Translate AL to AB
                translate_y -= box_height
            elif side == 'top':
                # Translate AL to AT
                translate_x += box_width
            # Create the complete transformation matrix = rotation followed by translation.
            transform[side] = Affine.translation(translate_x,
                                                 translate_y) * transform[side]
            # Also translate the point on each side that defines the box around the symbol.
            box_pt[side] = transform[side] * box_pt[side]

        # Draw the transformed pins for each side of the symbol.
        for side, side_pins in unit.items():
            # Sort the pins names for the desired order: row-wise, numeric, alphabetical.
            sorted_side_pins = sorted(side_pins.items(), key=key_func)
            # Draw the transformed pins for this side of the symbol.
            draw_pins(lib_file, unit_num, sorted_side_pins, transform[side], fuzzy_match)

            # Create the box around the unit's pins.
        lib_file.write(BOX.format(x0=int(box_pt['left'][X]),
                                  y0=int(box_pt['top'][Y]),
                                  x1=int(box_pt['right'][X]),
                                  y1=int(box_pt['bottom'][Y]),
                                  unit_num=unit_num,
                                  line_width=BOX_LINE_WIDTH,
                                  fill=FILLS[FILL]))

    # Close the section that holds the part's units.
    lib_file.write(END_DRAW)

    # Close the part definition.
    lib_file.write(END_DEF)


def kipart(reader_type, csv_file, lib_filename,
           append_to_lib=False,
           sort_type='name',
           fuzzy_match=False,
           bundle=False,
           debug_level=0):
    '''Read part pin data from a CSV file and write or append it to a library file.'''

    part_reader = getattr(THIS_MODULE, '{}_reader'.format(reader_type))

    # Either write the part definition to a new KiCad library or append it to an existing library.
    if append_to_lib:
        lib_filemode = 'ab'
    else:
        lib_filemode = 'wb'
        
    with open(lib_filename, lib_filemode) as lib_file:

        # Get the part number and pin data from the CSV file.
        for part_num, pin_data in part_reader(csv_file, bundle):

            # Write the library header if this is a new library.
            if not append_to_lib:
                lib_file.write(LIB_HEADER)
                append_to_lib = True # Any further iterations will append to the library.

            # Draw the schematic symbol into the library.
            draw_symbol(lib_file=lib_file,
                        part_num=part_num,
                        pin_data=pin_data,
                        sort_type=sort_type,
                        fuzzy_match=fuzzy_match)
