# MIT license
#
# Copyright (C) 2015-2021 by Dave Vandenbout.
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
import warnings
from collections import defaultdict

from .common import *
from .kipart import *


def xilinx6v_reader(part_data_file, part_data_file_name, part_data_file_type=".txt"):
    """Extract the pin data from a Xilinx Virtex-6 TXT file and return a dictionary of pin data."""

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
            pin.name = fields[2]

            # The type of the pin isn't given in the text file, so we'll have to infer it
            # from the name of the pin. Pin names starting with the following prefixes
            # are assigned the given pin type.
        DEFAULT_PIN_TYPE = (
            "input"  # Assign this pin type if name inference can't be made.
        )
        PIN_TYPE_PREFIXES = [
            (r"VCC", "power_in"),
            (r"GND", "power_in"),
            (r"IO_", "bidirectional"),
            (r"VREF[PN]_", "input"),
            (r"NC", "no_connect"),
            (r"VP_", "input"),
            (r"VN_", "input"),
            (r"DXP_", "passive"),
            (r"DXN_", "passive"),
            (r"CCLK", "input"),
            (r"CSI_B", "input"),
            (r"DIN", "input"),
            (r"DOUT_BUSY", "output"),
            (r"HSWAPEN", "input"),
            (r"RDWR_B", "input"),
            (r"M0", "input"),
            (r"M1", "input"),
            (r"M2", "input"),
            (r"INIT_B", "input"),
            (r"PROGRAM_B", "input"),
            (r"DONE", "output"),
            (r"TCK", "input"),
            (r"TDI", "input"),
            (r"TDO", "output"),
            (r"TMS", "input"),
            (r"VFS", "power_in"),
            (r"RSVD", "nc"),
            (r"VREF[NP]", "power_in"),
            (r"VBATT", "power_in"),
            (r"A(VDD|VSS)_", "power_in"),
            (r"MGTA(VCC|VTT)", "power_in"),
            (r"MGTHA(VCC|GND|VTT)", "power_in"),
            (r"MGTRBIAS_", "passive"),
            (r"MGTREFCLK[0-9]?[NP]_", "input"),
            (r"MGTRX[NP][0-9]+_", "input"),
            (r"MGTTX[NP][0-9]+_", "output"),
            (r"MGTRREF_", "passive"),
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
        
    part_custom_fields = None # just a placeholder in case wish to implement
    yield part_num, "U", "", "", "", part_num, pin_data, part_custom_fields # Return the dictionary of pins extracted from the TXT file.
