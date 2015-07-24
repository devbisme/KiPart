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
import re
import csv
from collections import defaultdict
from affine import Affine

__all__ = ['kipart']  # Only export this routine for use by the outside world.

THIS_MODULE = sys.modules[__name__]  # Ref to this module for making named calls.

DEFAULT_UNIT = 1
DEFAULT_PIN_TYPE = 'bidirectional'
DEFAULT_PIN_STYLE = 'line'
DEFAULT_PIN_SIDE = 'left'


# This is just a vanilla object class for device pins. 
# We'll add attributes to it as needed.
class Pin:
    pass


def generic_reader(csv_file, bundle):
    '''Extract pin data from a CSV file and return a dictionary of pin data.
       The CSV file should be formatted as follows:
           The first row should contain the part number.
           The second row should be empty.
           The third row should have columns labeled:
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
    '''

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
    part_num = re.search('([^,\s]+)', title).group(1)

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
        pin.name = row['Name']
        pin.num = row['Pin']
        try:
            pin.unit = row['Unit']
        except KeyError:
            pin.unit = DEFAULT_UNIT
        try:
            pin.side = row['Side']
        except KeyError:
            pin.side = DEFAULT_PIN_SIDE
        try:
            pin.style = row['Style']
        except KeyError:
            pin.style = DEFAULT_PIN_STYLE
        try:
            pin.type = row['Type']
        except KeyError:
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

    return part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.


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
            'VCC': 'power_in',
            'GND': 'power_in',
            'IO_': 'bidirectional',
            'DONE': 'output',
            'VREF[PN]_': 'input',
            'TCK': 'input',
            'TDI': 'input',
            'TDO': 'output',
            'TMS': 'input',
            'CCLK': 'input',
            'M0': 'input',
            'M1': 'input',
            'M2': 'input',
            'INIT_B': 'input',
            'PROG': 'input',
            'NC': 'no_connect',
            'VP_': 'input',
            'VN_': 'input',
            'DXP_': 'passive',
            'DXN_': 'passive',
            'CFGBVS_': 'input',
            'MGTZ?REFCLK[0-9]+[NP]_': 'input',
            'MGTZ_OBS_CLK_[PN]_': 'input',
            'MGT[ZPHX]TX[NP][0-9]+_': 'output',
            'MGT[ZPHX]RX[NP][0-9]+_': 'input',
            'MGTAVTTRCAL_': 'passive',
            'MGTRREF_': 'passive',
            'MGTVCCAUX_?': 'power_in',
            'MGTAVTT_?': 'power_in',
            'MGTZ_THERM_IN_': 'input',
            'MGTZ_THERM_OUT_': 'input',
            'MGTZ?A(VCC|GND)_?': 'power_in',
            'MGTZVCC[LH]_': 'power_in',
            'MGTZ_SENSE_(A?VCC|A?GND)[LH]?_': 'power_in',
            'RSVD(VCC[1-3]|GND)': 'power_in',
            'PS_CLK_': 'input',
            'PS_POR_B': 'input',
            'PS_SRST_B': 'input',
            'PS_DDR_CK[PN]_': 'output',
            'PS_DDR_CKE_': 'output',
            'PS_DDR_CS_B_': 'output',
            'PS_DDR_RAS_B_': 'output',
            'PS_DDR_CAS_B_': 'output',
            'PS_DDR_WE_B_': 'output',
            'PS_DDR_BA[0-9]+_': 'output',
            'PS_DDR_A[0-9]+_': 'output',
            'PS_DDR_ODT_': 'output',
            'PS_DDR_DRST_B_': 'output',
            'PS_DDR_DQ[0-9]+_': 'bidirectional',
            'PS_DDR_DM[0-9]+_': 'output',
            'PS_DDR_DQS_[PN][0-9]+_': 'bidirectional',
            'PS_DDR_VR[PN]_': 'power_out',
            'PS_DDR_VREF[0-9]+_': 'power_in',
            'PS_MIO_VREF_': 'power_in',
            'PS_MIO[0-9]+_': 'bidirectional',
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

    return part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.

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
PIN_ORIENTATIONS = {'left': 'R', 'right': 'L', 'bottom': 'U', 'top': 'D'}
ROTATION = {'left': 0, 'right': 180, 'bottom': 90, 'top': -90}

# Mapping from understandable pin type name to the type
# indicator used in the KiCad part library.
PIN_TYPES = {
    'input': 'I',
    'output': 'O',
    'bidirectional': 'B',
    'tristate': 'T',
    'passive': 'P',
    'unspecified': 'U',
    'power_in': 'W',
    'power_out': 'w',
    'open_collector': 'C',
    'open_emitter': 'E',
    'no_connect': 'N',
}

# Mapping from understandable pin drawing style to the style
# indicator used in the KiCad part library.
PIN_STYLES = {
    'line': '',
    'inverted': 'I',
    'clock': 'C',
    'inverted_clock': 'IC',
    'input_low': 'L',
    'clock_low': 'CL',
    'output_low': 'V',
    'falling_edge_clock': 'F',
    'non_logic': 'X'
}

# Mapping from understandable visibility indicator to the visibility
# indicator used in the KiCad part library.
VISIBILITY = {'visible': '', 'invisible': 'N'}

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
PIN = 'X {name} {num} {x} {y} {length} {orientation} {num_sz} {name_sz} {unit_num} 1 {pin_type} {visibility}{pin_style}\n'


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


def draw_pins(lib_file, unit_num, unit_pins, transform):
    '''Draw a column of pins rotated/translated by the transform matrix.'''

    # Start drawing pins from the origin.
    x = XO
    y = YO

    for name, pins in unit_pins:

        # Start off creating visible part pins. If there are multiple pins with
        # the same name, then the visibility will be turned off for any pins
        # after the first.
        visibility = VISIBILITY['visible']

        # Rotate/translate the current drawing point.
        (draw_x, draw_y) = transform * (x, y)

        # Create all the pins with a particular name. If there are more than one,
        # they are laid on top of each other and only the first is visible.
        for pin in pins:

            # Create a pin using the pin data.
            lib_file.write(PIN.format(name=pin.name,
                                      num=pin.num,
                                      x=int(draw_x),
                                      y=int(draw_y),
                                      length=PIN_LENGTH,
                                      orientation=PIN_ORIENTATIONS[pin.side],
                                      num_sz=PIN_NUM_SIZE,
                                      name_sz=PIN_NAME_SIZE,
                                      unit_num=unit_num,
                                      pin_type=PIN_TYPES[pin.type],
                                      visibility=visibility,
                                      pin_style=PIN_STYLES[PIN_STYLE]))

            # Turn off visibility after the first pin.
            visibility = VISIBILITY['invisible']

        # Move to the next pin placement location on this unit.
        y = y - PIN_SPACING


def row_key(pin):
    '''Generate a key from the order the pins were entered into the CSV file.'''
    return pin[1][0].index


def num_key(pin):
    '''Generate a key from a pin's number so they are sorted by position on the package.'''

    # Get the alphabetic prefix string of the pin number and then the numeric string.
    # Pad the numeric string with leading 0's and then concatenate the two strings.
    # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
    # appear before A10 in a list.
    try:
        m = re.search('(\D+)(\d+)', pin[1][0].num)
        prefix = m.group(1)
        num = m.group(2)
        num = '0' * (8 - len(num)) + num
        return prefix + num
    except:
        # The pin number is probably a straight number like '45', so just return it.
        try:
            return int(pin[1][0].num)
        except:
            return pin[1][0].num


def name_key(pin):
    '''Generate a key from a pin's name so they are sorted more logically.'''

    # Get the alphabetic prefix string of the pin name and the first numeric string.
    # Pad the numeric string with leading 0's and then concatenate the two strings.
    # Thus, 'adc10' and 'adc2' will become 'adc00010' and 'adc00002' and adc2 will
    # appear before adc10 in a list.
    try:
        m = re.search('(\D+)(\d+)', pin[0])
        prefix = m.group(1)
        num = m.group(2)
        num = '0' * (8 - len(num)) + num
        return prefix + num
    except:
        return pin[0]


def draw_symbol(lib_file, part_num, pin_data, sort_type):
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
            draw_pins(lib_file, unit_num, sorted_side_pins, transform[side])

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
           bundle=False,
           debug_level=0):
    '''Read part pin data from a CSV file and write or append it to a library file.'''

    # Get the part number and pin data from the CSV file.
    part_reader = getattr(THIS_MODULE, '{}_reader'.format(reader_type))
    part_num, pin_data = part_reader(csv_file, bundle)

    # Either write the part definition to a new KiCad library or append it to an existing library.
    if append_to_lib:
        lib_filemode = 'ab'
    else:
        lib_filemode = 'wb'
    with open(lib_filename, lib_filemode) as lib_file:

        # Write the library header if this is a new library.
        if not append_to_lib:
            lib_file.write(LIB_HEADER)

        # Draw the schematic symbol into the library.
        draw_symbol(lib_file=lib_file,
                    part_num=part_num,
                    pin_data=pin_data,
                    sort_type=sort_type)

        # Close the section that holds the part's units.
        lib_file.write(END_DRAW)

        # Close the part definition.
        lib_file.write(END_DEF)
