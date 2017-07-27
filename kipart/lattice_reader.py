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

from __future__ import absolute_import
import csv
import copy
import os.path
from collections import defaultdict
from .common import *
from .kipart import *


def lattice_reader(csv_file):
    '''Extract the pin data from a Lattice CSV file and return a dictionary of pin data.
    Both csv files available on Lattice website and csv files exported from Diamond are supported.
    ICE40 family is NOT supported, since they use a completely different format.'''

    # Create a dictionary that uses the package name as key. Each entry in this dictionary
    # uses the unit numbers as keys. Each entry in this dictionary contains another 
    # dictionary that uses the side of the symbol as a key. Each entry in that dictionary 
    # uses the pin names in that unit and on that side as keys. Each entry in that 
    # dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into units at the top level, and then
    # the sides of the symbol, and then the pins with the same name that are on that side
    # of the unit.
    pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

    # Parse the first lines, until we find the column title row
    global_device_name=''
    global_package_name=''
    while True:
        pos=csv_file.tell()
        line = csv_file.readline()
        if line[0:8]=='#DEVICE=':
		global_device_name=line[9:].split(',')[0].strip().upper().replace('-', '_').replace(' ','_')
        if line[0:9]=='#PACKAGE=':
		global_package_name=line[10:].split(',')[0].strip().upper().replace('-', '_').replace(' ','_')
        test_field = line.split(',')[0].strip().upper()
        if test_field == 'INDEX' or test_field == 'PAD':
            break
    csv_file.seek(pos)

    # If no device name found in comments, get part number from file name
    if global_device_name:
        part_num = global_device_name
    else:
        part_num = os.path.splitext(os.path.basename(csv_file.name))[0]
    part_num = part_num.upper().split('PINOUT')[0].replace('-', '_').replace(' ','_')

    # Create a csv dict reader, from the column title row
    csv_reader = csv.DictReader(csv_file, skipinitialspace=True)

    # Some field name normalization : there is some variation in capitalization, 
    # 'Pin/Ball function' is sometimes 'Pin/Ball', and there may be references to comments after the field name (eg 'type(1)')
    csv_reader.fieldnames = [f.split('(')[0] for f in csv_reader.fieldnames]
    csv_reader.fieldnames = [f.strip().upper() for f in csv_reader.fieldnames]
    csv_reader.fieldnames = ['PIN/BALL FUNCTION' if f == 'PIN/BALL' else f for f in csv_reader.fieldnames]

    # If we have found a package name in comments, and a 'Pin Number' field is available,
    # we use this package name, and replace the 'Pin Number' name by its name
    # else we consider this is a multi-package csv file, and any column with an unknown field name is considered a package name
    # In the multi-package case, package names are normalized, and DQS variants are ignored
    if global_package_name and 'PIN NUMBER' in csv_reader.fieldnames:
        csv_reader.fieldnames = [global_package_name if f=='PIN NUMBER' else f for f in csv_reader.fieldnames]
        package = [global_package_name]
    else:
        known_fields = ['INDEX', 'TYPE', 'PAD', 'PIN/BALL FUNCTION', 'BANK', 'DUAL FUNCTION', 'DIFFERENTIAL', 'HIGH SPEED', 'DQS', 'I/O GROUPING', 'PIN NUMBER']
	csv_reader.fieldnames = [x if x in known_fields else x.upper().replace('-', '_').replace(' ','_') for x in csv_reader.fieldnames]
        package = [x for x in csv_reader.fieldnames if x and x not in known_fields and not x.endswith('_DQS')]

    if not package:
	print 'Warning : no package found, exiting'
        return

    #Process the pins line-by-line
    for index,row in enumerate(csv_reader):
        pin = copy.copy(DEFAULT_PIN)
        pin.index = index
        pin.name = row['PIN/BALL FUNCTION']
        if not row['BANK'] or row['BANK'] == '-' or row['BANK'] == ' ':
            pin.unit = 1
        else:
            pin.unit = int(row['BANK'])+2

        # The type of the pin isn't given in the text file, so we'll have to infer it
        # from the name of the pin. Pin names starting with the following prefixes 
        # are assigned the given pin type.
        DEFAULT_PIN_TYPE = 'io'  # Assign this pin type if name inference can't be made.
        PIN_TYPE_PREFIXES = [
            (r'VCC', 'power_in'),
            (r'GND', 'power_in'),
            (r'NC', 'no_connect'),
        ]
        for prefix, typ in PIN_TYPE_PREFIXES:
            if re.match(prefix, pin.name, re.IGNORECASE):
                pin.type = typ
                break
        else:
            pin.type = DEFAULT_PIN_TYPE

        # Same for pin side, in order to have VCC at the top and GND at the bottom
        PIN_SIDE_PREFIXES = [
            (r'VCC', 'top'),
            (r'GND', 'bottom'),
        ]
        for prefix, s in PIN_SIDE_PREFIXES:
            if re.match(prefix, pin.name, re.IGNORECASE):
                pin.side = s

        for p in package:
            if row[p] and row[p] != '-' and row[p] != ' ':
                pin.num = row[p]
                pin_data[p][pin.unit][pin.side][pin.name].append(copy.copy(pin))

        
    for p in package:
        yield part_num+'_'+p, 'U', pin_data[p]  # Return the dictionary of pins for the package p

