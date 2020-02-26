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

import copy
import csv
from collections import defaultdict

from .common import *
from .kipart import *


def xilinx6s_reader(part_data_file, part_data_file_name, part_data_file_type=".txt"):
    """Extract the pin data from a Xilinx Spartan-6 TXT file and return a dictionary of pin data."""

    # If part data file is Excel, convert it to CSV.
    if part_data_file_type == ".xlsx":
        part_data_file = convert_xlsx_to_csv(part_data_file)
    txt_file = part_data_file

    # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
    # contains another dictionary that uses the side of the symbol as a key. Each entry in
    # that dictionary uses the pin names in that unit and on that side as keys. Each entry
    # in that dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into units at the top level, and then
    # the sides of the symbol, and then the pins with the same name that are on that side
    # of the unit.
    pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # Read title line of the TXT file and extract the part number.
    part_num = txt_file.readline().split()[1]

    # Dump the lines between the title and the part's pin data.
    _ = txt_file.readline()
    _ = txt_file.readline()
    _ = txt_file.readline()

    # Read all the pin data.
    pin_list = txt_file.readlines()

    # Process the pin data line-by-line.
    for index, line in enumerate(pin_list, 4):
        pin = copy.copy(DEFAULT_PIN)
        pin.index = index
        # Get the pin attributes from a line of pin data.
        fields = line.split()
        # Fix common errors in pin data.
        fields = [fix_pin_data(d, part_num) for d in fields]
        if len(fields) == 0:
            break  # A blank line signals the end of pin data.
        pin.num = fields[0]
        if fields[1].upper() == "NOPAD/UNCONNECTED":
            pin.unit = "NA"
            pin.name = "NC"
        else:
            pin.unit = fields[1]
            pin.name = fields[3]

            # The type of the pin isn't given in the text file, so we'll have to infer it
            # from the name of the pin. Pin names starting with the following prefixes
            # are assigned the given pin type.
        DEFAULT_PIN_TYPE = (
            "input"  # Assign this pin type if name inference can't be made.
        )
        PIN_TYPE_PREFIXES = [
            (r"CMPCS_B", "input"),
            (r"DONE", "output"),
            (r"VCC", "power_in"),
            (r"GND", "power_in"),
            (r"IO_", "bidirectional"),
            (r"MGTAVCC", "power_in"),
            (r"MGTAVTTRCAL_", "passive"),
            (r"MGTREFCLK[0-9]?[NP]_", "input"),
            (r"MGTRX[NP][0-9]+_", "input"),
            (r"MGTRREF_", "passive"),
            (r"MGTAVTT[RT]_?", "power_in"),
            (r"MGTTX[NP][0-9]+_", "output"),
            (r"NC", "no_connect"),
            (r"PROGRAM_B", "input"),
            (r"RFUSE", "input"),
            (r"SUSPEND", "input"),
            (r"TCK", "input"),
            (r"TDI", "input"),
            (r"TDO", "output"),
            (r"TMS", "input"),
            (r"VFS", "power_in"),
            (r"VBATT", "power_in"),
        ]
        for prefix, typ in PIN_TYPE_PREFIXES:
            if re.match(prefix, pin.name, re.IGNORECASE):
                pin.type = typ
                break
        else:
            issue(
                "No match for {} on {}, assigning as {}".format(
                    pin.name, part_num[:4], DEFAULT_PIN_TYPE
                )
            )
            pin.type = DEFAULT_PIN_TYPE

        # Add the pin from this row of the CVS file to the pin dictionary.
        # Place all the like-named pins into a list under their common name.
        # We'll unbundle them later, if necessary.
        pin_data[pin.unit][pin.side][pin.name].append(pin)

    yield part_num, "U", "", "", "", part_num, pin_data  # Return the dictionary of pins extracted from the TXT file.
