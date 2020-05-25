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

from __future__ import print_function

import csv
import difflib
import os.path
import re
from builtins import object

import openpyxl

from .py_2_3 import *

COLUMN_NAMES = {
    "pin": "num",
    "num": "num",
    "name": "name",
    "type": "type",
    "style": "style",
    "side": "side",
    "unit": "unit",
    "bank": "unit",
    "hidden": "hidden",
    "": "",  # Blank column names stay blank.
}


# This is just a vanilla object class for device pins.
# We'll add attributes to it as needed.
class Pin(object):
    pass


DEFAULT_PIN = Pin()
DEFAULT_PIN.num = None
DEFAULT_PIN.name = ""
DEFAULT_PIN.type = "io"
DEFAULT_PIN.style = "line"
DEFAULT_PIN.unit = 1
DEFAULT_PIN.side = "left"
DEFAULT_PIN.hidden = "no"


def num_row_elements(row):
    """Get number of elements in CSV row."""
    try:
        rowset = set(row)
        rowset.discard("")
        return len(rowset)
    except TypeError:
        return 0


def get_nonblank_row(csv_reader):
    """Return the first non-blank row encountered from the current point in a CSV file."""
    for row in csv_reader:
        if num_row_elements(row) > 0:
            return row
    return []


def get_part_info(csv_reader):
    """Get the part number, ref prefix, footprint, MPN, datasheet link, and description from a row of the CSV file."""

    # Read the first, nonblank row and pad it with None's to make sure it's long enough.
    (
        part_num,
        part_ref_prefix,
        part_footprint,
        part_manf_num,
        part_datasheet,
        part_desc,
    ) = list(get_nonblank_row(csv_reader) + [None] * 6)[:6]

    # Put in the default part reference identifier if it isn't present.
    if part_ref_prefix in (None, "", " "):
        part_ref_prefix = "U"

    # Check to see if the row with the part identifier is missing.
    if part_num and part_num.lower() in list(COLUMN_NAMES.keys()):
        issue("Row with part number is missing in CSV file.", "error")

    return (
        part_num,
        part_ref_prefix,
        part_footprint,
        part_manf_num,
        part_datasheet,
        part_desc,
    )


def find_closest_match(name, name_dict, fuzzy_match, threshold=0.0):
    """Approximate matching subroutine"""

    # Scrub non-alphanumerics from name and lowercase it.
    scrubber = re.compile("[\W.]+")
    name = scrubber.sub("", name).lower()

    # Return regular dictionary lookup if fuzzy matching is not enabled.
    if fuzzy_match == False:
        return name_dict[name]

    # Find the closest fuzzy match to the given name in the scrubbed list.
    # Set the matching threshold to 0 so it always gives some result.
    match = difflib.get_close_matches(name, list(name_dict.keys()), 1, threshold)[0]

    return name_dict[match]


def clean_headers(headers):
    """Return a list of the closest valid column headers for the headers found in the file."""
    return [find_closest_match(h, COLUMN_NAMES, True) for h in headers]


def issue(msg, level="warning"):
    if level == "warning":
        print("Warning: {}".format(msg))
    elif level == "error":
        print("ERROR: {}".format(msg))
        raise Exception("Unrecoverable error")
    else:
        print(msg)


def fix_pin_data(pin_data, part_num):
    """Fix common errors in pin data."""
    fixed_pin_data = pin_data.strip()  # Remove leading/trailing spaces.
    if re.search("\s", fixed_pin_data) is not None:
        fixed_pin_data = re.sub("\s", "_", fixed_pin_data)
        issue(
            "Replaced whitespace with '_' in pin '{pin_data}' of part {part_num}.".format(
                **locals()
            )
        )
    return fixed_pin_data


def is_xlsx(filename):
    return os.path.splitext(filename)[1] == ".xlsx"


def convert_xlsx_to_csv(xlsx_file, sheetname=None):
    """
    Convert sheet of an Excel workbook into a CSV file in the same directory
    and return the read handle of the CSV file.
    """
    wb = openpyxl.load_workbook(xlsx_file)
    if sheetname:
        sh = wb[sheetname]
    else:
        sh = wb.active

    if USING_PYTHON2:
        # Python 2 doesn't accept newline parameter when opening file.
        newline = {}
    else:
        # kipart fails on Python 3 unless file is opened with this newline.
        newline = {"newline": ""}

    csv_filename = "xlsx_to_csv_file.csv"
    with open(csv_filename, "w", **newline) as f:
        col = csv.writer(f)
        for row in sh.rows:
            try:
                col.writerow([cell.value for cell in row])
            except UnicodeEncodeError:
                for cell in row:
                    if cell.value:
                        cell.value = "".join([c for c in cell.value if ord(c) < 128])
                col.writerow([cell.value for cell in row])
    return open(csv_filename, "r")
