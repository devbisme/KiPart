# MIT license
#
# Copyright (C) 2019 by XESS Corp.
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


def gowin_reader(part_data_file, part_data_file_name="", part_data_file_type=".csv"):
    """Extract the pin data from a GOWIN CSV file and return a dictionary of pin data."""

    # If part data file is Excel, convert it to CSV.
    if part_data_file_type == ".xlsx":
        part_data_file = convert_xlsx_to_csv(part_data_file, "Pin List")
    csv_file = part_data_file

    # Create a dictionary that uses the unit numbers as keys. Each entry in this dictionary
    # contains another dictionary that uses the side of the symbol as a key. Each entry in
    # that dictionary uses the pin names in that unit and on that side as keys. Each entry
    # in that dictionary is a list of Pin objects with each Pin object having the same name
    # as the dictionary key. So the pins are separated into units at the top level, and then
    # the sides of the symbol, and then the pins with the same name that are on that side
    # of the unit.
    #
    # Since the GOWIN FPGA spreadsheets include several columns of pin numbers for each
    # package variant, an additional dictionary layer was added for the type of package used
    # by the part. So the layers are pin_data[pckg][pin.unit][pin.side][pin.name].
    pin_data = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    # Extract the base part number from the file name.
    part_num = re.search(
        r"GW[0-9]+\S*", part_data_file_name, flags=re.IGNORECASE
    ).group(0)

    # Scan the initial portion of the file for the column headers.
    while True:
        line = csv_file.readline()
        if re.match("^Pin Name,", line):
            # Found the header preceding the pin data.
            field_names = line.split(",")
            # There is one GOWIN pin data spreadsheet that has a column labelled "Functi-on"
            # instead of "Function", so I go through the column headers and remove all
            # punctuation just so I don't have to include this one special case.
            field_names = [re.sub(r"[^a-zA-Z0-9\s]", "", nm) for nm in field_names]
            # Strip all leading/trailing space and uppercase column headers.
            field_names = [nm.strip().rstrip().upper() for nm in field_names]
            # Determine where the package pin columns start.
            pckg_field_start_index = -1
            for col_hdr in ("LVDS", "DIFFERENTIAL PAIR", "X16"):
                try:
                    pckg_field_start_index = max(
                        pckg_field_start_index, field_names.index(col_hdr) + 1
                    )
                except ValueError:
                    pass
            assert pckg_field_start_index >= 0
            pckgs = list(
                set(field_names[pckg_field_start_index:])
            )  # FPGA package variants.
            try:
                pckgs.remove("")
            except ValueError:
                pass
            break

    # Create a reader object for the rows of the CSV file and read it row-by-row.
    csv_reader = csv.DictReader(csv_file, fieldnames=field_names, skipinitialspace=True)
    for index, row in enumerate(csv_reader):
        # A blank line signals the end of the pin data.
        if row["PIN NAME"] == "":
            break

        # Get the pin attributes from the cells of the row of data.
        pin = copy.copy(DEFAULT_PIN)
        pin.index = index
        pin.name = fix_pin_data(row["PIN NAME"], part_num)
        pin.unit = fix_pin_data(row["BANK"], part_num)
        pin.type = fix_pin_data(row["FUNCTION"], part_num)

        # Translate the GOWIN pin function to something KiPart understands.
        DEFAULT_PIN_TYPE = (
            "input"  # Assign this pin type if name inference can't be made.
        )
        PIN_TYPE_PREFIXES = [
            (r"Power$", "power_in"),
            (r"Ground$", "power_in"),
            (r"I/O$", "bidirectional"),
            (r"LVDS$", "bidirectional"),
            (r"N/A$", "no_connect"),
        ]
        for prefix, typ in PIN_TYPE_PREFIXES:
            if re.match(prefix, pin.type, re.IGNORECASE):
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

        for pckg in pckgs:
            if row[pckg] != "":
                # Add the pin from this row of the file to the pin dictionary for this package.
                # Place all the like-named pins into a list under their common name.
                # We'll unbundle them later, if necessary.
                pin.num = fix_pin_data(row[pckg], part_num)
                pin_data[pckg][pin.unit][pin.side][pin.name].append(copy.copy(pin))

    # Return the pin data for each package variant of this FPGA.
    for pckg in pckgs:
        if pin_data[pckg]:
            part_pckg_num = "_".join((part_num, pckg))
            yield part_pckg_num, "U", "", "", "", part_pckg_num, pin_data[
                pckg
            ]  # Return the dictionary of pins extracted from the CVS file.
