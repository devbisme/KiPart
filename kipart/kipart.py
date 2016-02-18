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

from __future__ import division
from __future__ import absolute_import
from builtins import str
from past.utils import old_div
import sys
import math
import re
import importlib
from affine import Affine
from .common import *

__all__ = ['kipart']  # Only export this routine for use by the outside world.

THIS_MODULE = sys.modules[__name__]  # Ref to this module for making named calls.

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
PIN_SPACER_PREFIX = '*'

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
PIN_ORIENTATIONS = {
    '': 'R',
    'left': 'R',
    'right': 'L',
    'bottom': 'U',
    'down': 'U',
    'top': 'D',
    'up': 'D',
}
scrubber = re.compile('[\W.]+')
PIN_ORIENTATIONS = {
    scrubber.sub('', k).lower(): v
    for k, v in list(PIN_ORIENTATIONS.items())
}

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
PIN_TYPES = {scrubber.sub('', k).lower(): v for k, v in list(PIN_TYPES.items())}

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
PIN_STYLES = {scrubber.sub('', k).lower(): v for k, v in list(PIN_STYLES.items())}

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
            #name_suffix = MULTI_PIN_SUFFIX
            name_suffix = '[{}]'.format(len(pins))
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
    width = math.ceil(old_div(float(width), PIN_SPACING)) * PIN_SPACING

    # Compute the height of the column of pins, taking spacers into account.
    height = 0
    for name, pins in unit_pins:
        pin_spacer = 0
        pin_num_len = 0
        for pin in pins:
            pin_num = str(pin.num)
            # spacer pins have pin numbers starting with a special prefix char.
            if pin_num.startswith(PIN_SPACER_PREFIX):
                pin_spacer = 1
                pin_num = pin_num[1:] # Remove the spacer prefix.
            pin_num_len = max(pin_num_len, len(pin_num))
        height += pin_spacer * PIN_SPACING # Add more to height if there was a spacer.
        # Add height of pin to bbox if the pin number was more than just a spacer prefix.
        if pin_num_len > 0:
            height += PIN_SPACING 

    return [[XO, YO + PIN_SPACING], [XO + width, YO - height]]


def draw_pins(lib_file, unit_num, unit_pins, transform, fuzzy_match):
    '''Draw a column of pins rotated/translated by the transform matrix.'''

    # Start drawing pins from the origin.
    x = XO
    y = YO

    for name, pins in unit_pins:

        # Detect pins with "spacer" pin numbers.
        pin_spacer = 0
        pin_num_len = 0
        for pin in pins:
            pin_num = str(pin.num)
            # spacer pins have pin numbers starting with a special prefix char.
            if pin_num.startswith(PIN_SPACER_PREFIX):
                pin_spacer = 1
                pin_num = pin_num[1:] # Remove the spacer prefix.
            pin_num_len = max(pin_num_len, len(pin_num))
        y -= pin_spacer * PIN_SPACING # Add space between pins if there was a spacer.
        if pin_num_len == 0:
            continue # Omit pin if it only had a spacer prefix and no actual pin number.

        # Rotate/translate the current drawing point.
        (draw_x, draw_y) = transform * (x, y)

        # Use approximate matching to determine the pin's type, style and orientation.
        pin_type = find_closest_match(pins[0].type, PIN_TYPES, fuzzy_match)
        pin_style = find_closest_match(pins[0].style, PIN_STYLES, fuzzy_match)
        pin_side = find_closest_match(pins[0].side, PIN_ORIENTATIONS,
                                      fuzzy_match)

        # Create all the pins with a particular name. If there are more than one,
        # they are laid on top of each other and only the first is visible.
        num_size = PIN_NUM_SIZE  # First pin will be visible.
        for pin in pins:

            pin_num = str(pin.num)

            # Remove any spacer prefix on the pin numbers.
            if pin_num.startswith(PIN_SPACER_PREFIX):
                pin_num = pin_num[1:]

            # Create a pin using the pin data.
            lib_file.write(PIN.format(name=pin.name,
                                      num=pin_num,
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
        y -= PIN_SPACING


def row_key(pin):
    '''Generate a key from the order the pins were entered into the CSV file.'''
    return pin[1][0].index


def num_key(pin):
    '''Generate a key from a pin's number so they are sorted by position on the package.'''

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
    # appear before A10 in a list.
    return re.sub(r'\d+', lambda mtch: '0' *
                  (8 - len(mtch.group(0))) + mtch.group(0), pin[1][0].num)


def name_key(pin):
    '''Generate a key from a pin's name so they are sorted more logically.'''

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'adc10' and 'adc2' will become 'adc00010' and 'adc00002' and adc2 will
    # appear before adc10 in a list.
    return re.sub(r'\d+', lambda mtch: '0' *
                  (8 - len(mtch.group(0))) + mtch.group(0), pin[1][0].name)


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
    for unit in list(pin_data.values()):
        if 'top' in list(unit.keys()):
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
    # up to the number of units in the part. The units are sorted by their
    # names before assigning unit numbers.
    for unit_num, unit in enumerate([p[1] for p in sorted(pin_data.items())], 1):

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
        for side, side_pins in list(unit.items()):
            annotate_pins(list(side_pins.items()))
            bbox[side] = pins_bbox(list(side_pins.items()))
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
                         abs(bbox['right'][0][Y] - bbox['right'][1][Y]))

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
        for side, side_pins in list(unit.items()):
            # Sort the pins names for the desired order: row-wise, numeric, alphabetical.
            sorted_side_pins = sorted(list(side_pins.items()), key=key_func)
            # Draw the transformed pins for this side of the symbol.
            draw_pins(lib_file, unit_num, sorted_side_pins, transform[side],
                      fuzzy_match)

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
    

def is_pwr(pin, fuzzy_match):
    '''Return true if this is a power input pin.'''
    return find_closest_match(name=pin.type, name_dict=PIN_TYPES, fuzzy_match=fuzzy_match) == 'W'
    

def is_nc(pin, fuzzy_match):
    '''Return true if this is a no-connect pin.'''
    return find_closest_match(name=pin.type, name_dict=PIN_TYPES, fuzzy_match=fuzzy_match) == 'N'
    

def do_bundling(pin_data, bundle, fuzzy_match):
    '''Handle bundling for power and NC pins. Unbundle everything else.'''
    for unit in list(pin_data.values()):
        for side in list(unit.values()):
            for name, pins in list(side.items()):
                if len(pins) > 1:
                    for index, p in enumerate(pins):
                        if is_pwr(p, fuzzy_match) and bundle:
                            side[p.name + '_pwr'].append(p)
                        elif is_nc(p, fuzzy_match) and bundle:
                            side[p.name + '_nc'].append(p)
                        else:
                            side[p.name + '_' + str(index)].append(p)
                    del side[name]


def kipart(reader_type, part_data_file, lib_filename,
           append_to_lib=False,
           sort_type='name',
           fuzzy_match=False,
           bundle=False,
           debug_level=0):
    '''Read part pin data from a CSV file and write or append it to a library file.'''

    part_reader_module = '{}_reader'.format(reader_type)
    importlib.import_module('kipart.' + part_reader_module)
    READER_MODULE = sys.modules['kipart.' + part_reader_module]
    part_reader = getattr(READER_MODULE, part_reader_module)

    # Either write the part definition to a new KiCad library or append it to an existing library.
    if append_to_lib:
        lib_filemode = 'a'
    else:
        lib_filemode = 'w'

    with open(lib_filename, lib_filemode) as lib_file:

        # Get the part number and pin data from the CSV file.
        for part_num, pin_data in part_reader(part_data_file):
        
            do_bundling(pin_data, bundle, fuzzy_match)

            # Write the library header if this is a new library.
            if not append_to_lib:
                lib_file.write(LIB_HEADER)
                append_to_lib = True  # Any further iterations will append to the library.

            # Draw the schematic symbol into the library.
            draw_symbol(lib_file=lib_file,
                        part_num=part_num,
                        pin_data=pin_data,
                        sort_type=sort_type,
                        fuzzy_match=fuzzy_match)

    # This enables library-appending if it was already on upon entry to the routine
    # or if the routine just added a symbol to the library.
    return append_to_lib
