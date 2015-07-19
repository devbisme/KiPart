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

import re
import csv
from collections import defaultdict

# Dimensions in mils (0.001")
BOX_LINE_WIDTH = 12
PIN_LENGTH = 200
PIN_Y_SPACING = 100
PIN_NUM_SIZE = 50
PIN_NAME_SIZE = 50
PIN_NAME_OFFSET = 40
SHOW_PIN_NUMBER = 'Y'
SHOW_PIN_NAME = 'Y'
PART_PREFIX = 'U'
REF_SIZE = 60

XO = 0
YO = 0
REF_X_OFFSET = PIN_LENGTH
REF_Y_OFFSET = 250
PART_NUM_X_OFFSET = PIN_LENGTH
PART_NUM_Y_OFFSET = 150

PIN_ORIENTATIONS = {'right': 'R', 'left': 'L', 'up': 'U', 'down': 'D'}
PIN_TYPES = {
    'input': 'I',
    'I': 'I',
    'output': 'O',
    'O': 'O',
    'bidirectional': 'B',
    'BI': 'B',
    'tristate': 'T',
    'TRI': 'T',
    'passive': 'P',
    'P': 'P',
    'unspecified': 'U',
    'U': 'U',
    'power_in': 'W',
    'PWR': 'W',
    'PWRIN': 'W',
    'power_out': 'w',
    'PWROUT': 'w',
    'open_collector': 'C',
    'OC': 'C',
    'open_emitter': 'E',
    'OE': 'E',
    'not_connected': 'N',
    'NC': 'N',
}
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
VISIBILITY = {'visible': '', 'invisible': 'N'}
FILLS = {'no_fill': 'N', 'fg_fill': 'F', 'bg_fill': 'f'}

LIB_HEADER = 'EESchema-LIBRARY Version 2.3\n'
START_DEF = 'DEF {name} {ref} 0 {pin_name_offset} {show_pin_number} {show_pin_name} {num_units} L N\n'
END_DEF = 'ENDDEF\n'
REF_FIELD = 'F0 "{part_prefix}" {x} {y} {ref_size} H V L CNN\n'
PART_FIELD = 'F1 "{part_num}" {x} {y} {ref_size} H V L CNN\n'
START_DRAW = 'DRAW\n'
END_DRAW = 'ENDDRAW\n'

BOX = 'S {x0} {y0} {x1} {y1} {unit_num} 1 {line_width} {fill}\n'
PIN = 'X {name} {num} {x} {y} {length} {orientation} {num_sz} {name_sz} {unit_num} 1 {pin_type} {visibility}{pin_style}\n'

DEFAULT_PIN_TYPE = 'input'
PIN_TYPE_PREFIXES = {
    'VCC': 'PWRIN',
    'GND': 'PWRIN',
    'IO_': 'BI',
    'DONE': 'input',
    'VREF': 'input',
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
}


class Pin:
    pass


def kipart(csv_filename, lib_filename=None, debug_level=0):

    # Create a dictionary that uses the bank numbers as keys. Each entry in this dictionary
    # contains another dictionary that uses the pin names in that bank as keys. Each entry
    # in that dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into banks at the top level, and then
    # pins with the same name within a bank are organized into lists on the second level.
    pins = defaultdict(lambda: defaultdict(list))

    # Read the CSV file.
    with open(csv_filename, 'rb') as csv_file:
        title = csv_file.readline()
        _, part_num, date, time, _ = re.split('\s+', title)
        _ = csv_file.readline()  # blank line between title and pin data rows.
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            if row['Pin'] == '':
                break
            pin = Pin()
            pin.name = row['Pin Name']
            pin.num = row['Pin']
            pin.bank = row['Bank']
            pin.type = DEFAULT_PIN_TYPE
            for prefix, typ in PIN_TYPE_PREFIXES.items():
                if re.match(prefix, pin.name, re.IGNORECASE):
                    pin.type = typ
                    break
            pins[pin.bank][pin.name].append(pin)

    with open(lib_filename, 'wb') as lib_file:
        # Make main part header.
        lib_file.write(LIB_HEADER)
        lib_file.write(START_DEF.format(name=part_num,
                                        ref=PART_PREFIX,
                                        pin_name_offset=PIN_NAME_OFFSET,
                                        show_pin_number=SHOW_PIN_NUMBER,
                                        show_pin_name=SHOW_PIN_NAME,
                                        num_units=len(pins)))
        lib_file.write(REF_FIELD.format(part_prefix=PART_PREFIX,
                                        x=XO + REF_X_OFFSET,
                                        y=YO + REF_Y_OFFSET,
                                        ref_size=REF_SIZE))
        lib_file.write(PART_FIELD.format(part_num=part_num,
                                         x=XO + PART_NUM_X_OFFSET,
                                         y=YO + PART_NUM_Y_OFFSET,
                                         ref_size=REF_SIZE))
        lib_file.write(START_DRAW)
        for unit_num, unit in enumerate(pins.values(), 1):
            y = YO
            max_name_width = 0
            for name, pins in sorted(unit.items()):
                name_suffix = ''
                if len(pins) > 1:
                    name_suffix = '*'
                visibility = VISIBILITY['visible']
                max_name_width = max(max_name_width, len(pin.name+name_suffix)*PIN_NAME_SIZE)
                for pin in pins:
                    lib_file.write(PIN.format(name=pin.name + name_suffix,
                                              num=pin.num,
                                              x=XO,
                                              y=y,
                                              length=PIN_LENGTH,
                                              orientation=PIN_ORIENTATIONS['right'],
                                              num_sz=PIN_NUM_SIZE,
                                              name_sz=PIN_NAME_SIZE,
                                              unit_num=unit_num,
                                              pin_type=PIN_TYPES[pin.type],
                                              visibility=visibility,
                                              pin_style=PIN_STYLES['line']))
                    name_suffix = ''
                    visibility = VISIBILITY['invisible']
                y = y - PIN_Y_SPACING
            lib_file.write(BOX.format(x0=XO + PIN_LENGTH,
                                      y0=PIN_Y_SPACING,
                                      x1=XO + PIN_LENGTH + PIN_NAME_OFFSET + max_name_width + PIN_NAME_OFFSET,
                                      y1=y,
                                      unit_num=unit_num,
                                      line_width=BOX_LINE_WIDTH,
                                      fill=FILLS['no_fill']))
        lib_file.write(END_DRAW)
        lib_file.write(END_DEF)

# Partition into banks.

#   foreach pin_name, pin_num, bank:
#      if bank in banks:
#          if pin_name in banks[bank].keys():
#             Place pin_name, pin_num at same location.
#          else:
#             Place pin_name, pin_num at next location.
#             Increment y coord.
#          banks[bank].width = max(banks[bank].width, len(pin_name))
#      else:
#          Make pin in banks[bank].pins
#   for bank in banks:
#       Make box from (x0,y0) to (banks[bank].width+x0, banks[bank].y)
#       foreach pin in banks[bank].pins:
#           Make pin
