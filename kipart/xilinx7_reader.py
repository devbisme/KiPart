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
import warnings
from collections import defaultdict

from .common import *
from .kipart import *

defaulted_names = set(list())


def xilinx7_reader(part_data_file, part_data_file_name, part_data_file_type=".csv"):
    """Extract the pin data from a Xilinx CSV file and return a dictionary of pin data."""

    # If part data file is Excel, convert it to CSV.
    if part_data_file_type == ".xlsx":
        part_data_file = convert_xlsx_to_csv(part_data_file)
    csv_file = part_data_file

    # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
    # contains another dictionary that uses the side of the symbol as a key. Each entry in
    # that dictionary uses the pin names in that unit and on that side as keys. Each entry
    # in that dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into units at the top level, and then
    # the sides of the symbol, and then the pins with the same name that are on that side
    # of the unit.
    pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # Scan the initial portion of the file for the part number.
    part_num = None
    try:
        while True:
            line = csv_file.readline()
            if re.match("^,*$", line):
                # Stop searching for part number as soon as a blank line is seen.
                break
            elif line.startswith('"#') or line.startswith("#"):
                # Look for the part number within a comment.
                device = re.search(r"#\s+Device\s*:\s*(\w+)", line)
                if device:
                    part_num = device.group(1)
            else:
                # Look for the part number on a line of the file.
                _, part_num, date, time, _ = re.split("\s+", line)
    except Exception:
        return  # No part was found.

    if part_num is None:
        return  # No part number was found, so abort.

    # Create a reader object for the rows of the CSV file and read it row-by-row.
    csv_reader = csv.DictReader(csv_file, skipinitialspace=True)
    for index, row in enumerate(csv_reader):
        # A blank line signals the end of the pin data.
        try:
            if row["Pin"] == "":
                break
        except KeyError:
            # Abort if a TXT file is being processed instead of a CSV file.
            return

        # Get the pin attributes from the cells of the row of data.
        pin = copy.copy(DEFAULT_PIN)
        pin.index = index
        pin.name = fix_pin_data(row["Pin Name"], part_num)
        pin.num = fix_pin_data(row["Pin"], part_num)
        pin.unit = fix_pin_data(row["Bank"], part_num)

        # The type of the pin isn't given in the CSV file, so we'll have to infer it
        # from the name of the pin. Pin names starting with the following prefixes
        # are assigned the given pin type.
        DEFAULT_PIN_TYPE = (
            "input"  # Assign this pin type if name inference can't be made.
        )
        PIN_TYPE_PREFIXES = [
            (r"VCC", "power_in"),
            (r"GND", "power_in"),
            (r"IO_", "bidirectional"),
            (r"DONE", "output"),
            (r"VREF[PN]_", "input"),
            (r"TCK", "input"),
            (r"TDI", "input"),
            (r"TDO", "output"),
            (r"TMS", "input"),
            (r"CCLK", "input"),
            (r"M0", "input"),
            (r"M1", "input"),
            (r"M2", "input"),
            (r"INIT_B", "input"),
            (r"PROG", "input"),
            (r"NC", "no_connect"),
            (r"VP_", "input"),
            (r"VN_", "input"),
            (r"DXP_", "passive"),
            (r"DXN_", "passive"),
            (r"CFGBVS_", "input"),
            (r"MGTZ?REFCLK[0-9]+[NP]_", "input"),
            (r"MGTZ_OBS_CLK_[PN]_", "input"),
            (r"MGT[ZPHX]TX[NP][0-9]+_", "output"),
            (r"MGT[ZPHX]RX[NP][0-9]+_", "input"),
            (r"MGTAVTTRCAL_", "passive"),
            (r"MGTRREF_", "passive"),
            (r"MGTVCCAUX_?", "power_in"),
            (r"MGTAVTT_?", "power_in"),
            (r"MGTZ_THERM_IN_", "input"),
            (r"MGTZ_THERM_OUT_", "input"),
            (r"MGTZ?A(VCC|GND)_?", "power_in"),
            (r"MGTZVCC[LH]_", "power_in"),
            (r"MGTZ_SENSE_(A?VCC|A?GND)[LH]?_", "power_in"),
            (r"RSVD(VCC[1-3]|GND)", "power_in"),
            (r"PS_CLK_", "input"),
            (r"PS_POR_B", "input"),
            (r"PS_SRST_B", "input"),
            (r"PS_DDR_CK[PN]_", "output"),
            (r"PS_DDR_CKE_", "output"),
            (r"PS_DDR_CS_B_", "output"),
            (r"PS_DDR_RAS_B_", "output"),
            (r"PS_DDR_CAS_B_", "output"),
            (r"PS_DDR_WE_B_", "output"),
            (r"PS_DDR_BA[0-9]+_", "output"),
            (r"PS_DDR_A[0-9]+_", "output"),
            (r"PS_DDR_ODT_", "output"),
            (r"PS_DDR_DRST_B_", "output"),
            (r"PS_DDR_DQ[0-9]+_", "bidirectional"),
            (r"PS_DDR_DM[0-9]+_", "output"),
            (r"PS_DDR_DQS_[PN][0-9]+_", "bidirectional"),
            (r"PS_DDR_VR[PN]_", "power_out"),
            (r"PS_DDR_VREF[0-9]+_", "power_in"),
            (r"PS_MIO_VREF_", "power_in"),
            (r"PS_MIO[0-9]+_", "bidirectional"),
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
        pin.type = fix_pin_data(pin.type, part_num)

        # Add the pin from this row of the CVS file to the pin dictionary.
        # Place all the like-named pins into a list under their common name.
        # We'll unbundle them later, if necessary.
        pin_data[pin.unit][pin.side][pin.name].append(pin)

    yield part_num, "U", "", "", "", part_num, pin_data  # Return the dictionary of pins extracted from the CVS file.
