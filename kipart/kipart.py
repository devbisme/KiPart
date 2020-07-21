# -*- coding: utf-8 -*-

# MIT license
#
# Copyright (C) 2015-2019 by XESS Corp.
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

from __future__ import absolute_import, division, print_function

import argparse as ap
import importlib
import io
import math
import os
import re
import sys
import zipfile
from builtins import str
from collections import OrderedDict
from copy import copy
from pprint import pprint

from affine import Affine
from past.utils import old_div

from .common import *
from .pckg_info import __version__
from .py_2_3 import *

__all__ = ["kipart"]  # Only export this routine for use by the outside world.

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
PIN_ORIENTATION = "left"
PIN_STYLE = "line"
SHOW_PIN_NUMBER = True  # Show pin numbers when True.
SHOW_PIN_NAME = True  # Show pin names when True.
SINGLE_PIN_SUFFIX = ""
MULTI_PIN_SUFFIX = "*"
PIN_SPACER_PREFIX = "*"

# Settings for box drawn around pins in a unit.
BOX_LINE_WIDTH = 12

# Part reference.
REF_SIZE = 60  # Font size.
REF_Y_OFFSET = 250

# Part number.
PART_NUM_SIZE = 60  # Font size.
PART_NUM_Y_OFFSET = 150

# Part footprint
PART_FOOTPRINT_SIZE = 60  # Font size.
PART_FOOTPRINT_Y_OFFSET = 50

# Part manufacturer number.
PART_MPN_SIZE = 60  # Font size.
PART_MPN_Y_OFFSET = -50

# Part datasheet.
PART_DATASHEET_SIZE = 60  # Font size.
PART_DATASHEET_Y_OFFSET = -150

# Part description.
PART_DESC_SIZE = 60  # Font size.
PART_DESC_Y_OFFSET = -250

# Mapping from understandable pin orientation name to the orientation
# indicator used in the KiCad part library. This mapping looks backward,
# but if pins are placed on the left side of the symbol, you actually
# want to use the pin symbol where the line points to the right.
# The same goes for the other sides.
PIN_ORIENTATIONS = {
    "": "R",
    "left": "R",
    "right": "L",
    "bottom": "U",
    "down": "U",
    "top": "D",
    "up": "D",
}
scrubber = re.compile("[^\w~#]+")
PIN_ORIENTATIONS = {
    scrubber.sub("", k).lower(): v for k, v in list(PIN_ORIENTATIONS.items())
}

ROTATION = {"left": 0, "right": 180, "bottom": 90, "top": -90}

# Mapping from understandable pin type name to the type
# indicator used in the KiCad part library.
PIN_TYPES = {
    "input": "I",
    "inp": "I",
    "in": "I",
    "clk": "I",
    "output": "O",
    "outp": "O",
    "out": "O",
    "bidirectional": "B",
    "bidir": "B",
    "bi": "B",
    "inout": "B",
    "io": "B",
    "iop": "B",
    "tristate": "T",
    "tri": "T",
    "passive": "P",
    "pass": "P",
    "unspecified": "U",
    "un": "U",
    "": "U",
    "analog": "U",
    "power_in": "W",
    "pwr_in": "W",
    "pwrin": "W",
    "power": "W",
    "pwr": "W",
    "ground": "W",
    "gnd": "W",
    "power_out": "w",
    "pwr_out": "w",
    "pwrout": "w",
    "pwr_o": "w",
    "open_collector": "C",
    "opencollector": "C",
    "open_coll": "C",
    "opencoll": "C",
    "oc": "C",
    "open_emitter": "E",
    "openemitter": "E",
    "open_emit": "E",
    "openemit": "E",
    "oe": "E",
    "no_connect": "N",
    "noconnect": "N",
    "no_conn": "N",
    "noconn": "N",
    "nc": "N",
}
PIN_TYPES = {scrubber.sub("", k).lower(): v for k, v in list(PIN_TYPES.items())}

# Mapping from understandable pin drawing style to the style
# indicator used in the KiCad part library.
PIN_STYLES = {
    "line": "",
    "": "",
    "inverted": "I",
    "inv": "I",
    "~": "I",
    "#": "I",
    "clock": "C",
    "clk": "C",
    "rising_clk": "C",
    "inverted_clock": "IC",
    "inv_clk": "IC",
    "clk_b": "IC",
    "clk_n": "IC",
    "~clk": "IC",
    "#clk": "IC",
    "input_low": "L",
    "inp_low": "L",
    "in_lw": "L",
    "in_b": "L",
    "in_n": "L",
    "~in": "L",
    "#in": "L",
    "clock_low": "CL",
    "clk_low": "CL",
    "clk_lw": "CL",
    "output_low": "V",
    "outp_low": "V",
    "out_lw": "V",
    "out_b": "V",
    "out_n": "V",
    "~out": "V",
    "#out": "V",
    "falling_edge_clock": "F",
    "falling_clk": "F",
    "fall_clk": "F",
    "non_logic": "X",
    "nl": "X",
    "analog": "X",
}
PIN_STYLES = {scrubber.sub("", k).lower(): v for k, v in list(PIN_STYLES.items())}

# Mapping from understandable box fill-type name to the fill-type
# indicator used in the KiCad part library.
FILLS = {"no_fill": "N", "fg_fill": "F", "bg_fill": "f"}

# Format strings for various items in a KiCad part library.
LIB_HEADER = "EESchema-LIBRARY Version 2.3\n"
START_DEF = "DEF {name} {ref} 0 {pin_name_offset} {show_pin_number} {show_pin_name} {num_units} L N\n"
END_DEF = "ENDDEF\n"
REF_FIELD = 'F0 "{ref_prefix}" {x} {y} {font_size} H V {text_justification} CNN\n'
PARTNUM_FIELD = 'F1 "{num}" {x} {y} {font_size} H V {text_justification} CNN\n'
FOOTPRINT_FIELD = 'F2 "{footprint}" {x} {y} {font_size} H I {text_justification} CNN\n'
DATASHEET_FIELD = 'F3 "{datasheet}" {x} {y} {font_size} H I {text_justification} CNN\n'
MPN_FIELD = 'F4 "{manf_num}" {x} {y} {font_size} H I {text_justification} CNN "manf#"\n'
DESC_FIELD = 'F5 "{desc}" {x} {y} {font_size} H I {text_justification} CNN "desc"\n'

START_DRAW = "DRAW\n"
END_DRAW = "ENDDRAW\n"
BOX = "S {x0} {y0} {x1} {y1} {unit_num} 1 {line_width} {fill}\n"
PIN = "X {name} {num} {x} {y} {length} {orientation} {num_sz} {name_sz} {unit_num} 1 {pin_type} {pin_style}\n"


def annotate_pins(unit_pins):
    """Annotate pin names to indicate special information."""
    for name, pins in unit_pins:
        # If there are multiple pins with the same name in a unit, then append a
        # distinctive suffix to the pin name to indicate multiple pins are placed
        # at a single location on the unit. (This is done so multiple pins that
        # should be on the same net (e.g. GND) can be connected using a single
        # net connection in the schematic.)
        name_suffix = SINGLE_PIN_SUFFIX
        if len(pins) > 1:
            # name_suffix = MULTI_PIN_SUFFIX
            name_suffix = "[{}]".format(len(pins))
        for pin in pins:
            pin.name += name_suffix


def get_pin_num_and_spacer(pin):
    pin_num = str(pin.num)
    pin_spacer = 0
    # spacer pins have pin numbers starting with a special prefix char.
    if pin_num.startswith(PIN_SPACER_PREFIX):
        pin_spacer = 1
        pin_num = pin_num[1:]  # Remove the spacer prefix.
    return pin_num, pin_spacer


def count_pin_slots(unit_pins):
    """Count the number of vertical pin slots needed for a column of pins."""

    # Compute the # of slots for the column of pins, taking spacers into account.
    num_slots = 0
    pin_num_len = 0
    for name, pins in unit_pins:
        pin_spacer = 0
        pin_num_len = 0
        for pin in pins:
            pin_num, pin_spacer = get_pin_num_and_spacer(pin)
            pin_num_len = max(pin_num_len, len(pin_num))
        num_slots += pin_spacer  # Add a slot if there was a spacer.
        # Add a slot if the pin number was more than just a spacer prefix.
        if pin_num_len > 0:
            num_slots += 1
    return num_slots


def pins_bbox(unit_pins):
    """Return the bounding box of a column of pins and their names."""

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

    # Compute the height of the column of pins.
    height = count_pin_slots(unit_pins) * PIN_SPACING

    return [[XO, YO + PIN_SPACING], [XO + width, YO - height]]


def balance_bboxes(bboxes):
    """Make the symbol more balanced by adjusting the bounding boxes of the pins on each side."""
    X = 0
    Y = 1

    def find_bbox_bbox(*bboxes):
        """Find the bounding box for a set of bounding boxes."""
        bb = [[0, 0], [0, 0]]
        for bbox in bboxes:
            bb[0][X] = min(bb[0][X], bbox[0][X])
            bb[1][X] = max(bb[1][X], bbox[1][X])
            bb[0][Y] = max(bb[0][Y], bbox[0][Y])
            bb[1][Y] = min(bb[1][Y], bbox[1][Y])
        return bb

    # Determine the number of sides of the symbol with pins.
    num_sides = len(bboxes)

    if num_sides == 4:
        # If the symbol has pins on all four sides, then check to see if there
        # are approximately the same number of pins on all four sides. If so,
        # then equalize the bounding box for each side. Otherwise, equalize
        # the left & right bounding boxes and the top & bottom bounding boxes.
        lr_bbox = find_bbox_bbox(bboxes["left"], bboxes["right"])
        lr_hgt = abs(lr_bbox[0][Y] - lr_bbox[1][Y])
        tb_bbox = find_bbox_bbox(bboxes["top"], bboxes["bottom"])
        tb_hgt = abs(tb_bbox[0][Y] - tb_bbox[1][Y])
        if 0.75 <= float(lr_hgt) / float(tb_hgt) <= 1 / 0.75:
            bal_bbox = find_bbox_bbox(*list(bboxes.values()))
            for side in bboxes:
                bboxes[side] = copy(bal_bbox)
        else:
            bboxes["left"] = copy(lr_bbox)
            bboxes["right"] = copy(lr_bbox)
            bboxes["top"] = copy(tb_bbox)
            bboxes["bottom"] = copy(tb_bbox)
    elif num_sides == 3:
        # If the symbol only has pins on threee sides, then equalize the
        # bounding boxes for the pins on opposite sides and leave the
        # bounding box on the other side unchanged.
        if "left" not in bboxes or "right" not in bboxes:
            # Top & bottom side pins, but the left or right side is empty.
            bal_bbox = find_bbox_bbox(bboxes["top"], bboxes["bottom"])
            bboxes["top"] = copy(bal_bbox)
            bboxes["bottom"] = copy(bal_bbox)
        elif "top" not in bboxes or "bottom" not in bboxes:
            # Left & right side pins, but the top or bottom side is empty.
            bal_bbox = find_bbox_bbox(bboxes["left"], bboxes["right"])
            bboxes["left"] = copy(bal_bbox)
            bboxes["right"] = copy(bal_bbox)
    elif num_sides == 2:
        # If the symbol only has pins on two opposing sides, then equalize the
        # height of the bounding boxes for each side. Leave the width unchanged.
        if "left" in bboxes and "right" in bboxes:
            bal_bbox = find_bbox_bbox(bboxes["left"], bboxes["right"])
            bboxes["left"][0][Y] = bal_bbox[0][Y]
            bboxes["left"][1][Y] = bal_bbox[1][Y]
            bboxes["right"][0][Y] = bal_bbox[0][Y]
            bboxes["right"][1][Y] = bal_bbox[1][Y]
        elif "top" in bboxes and "bottom" in bboxes:
            bal_bbox = find_bbox_bbox(bboxes["top"], bboxes["bottom"])
            bboxes["top"][0][Y] = bal_bbox[0][Y]
            bboxes["top"][1][Y] = bal_bbox[1][Y]
            bboxes["bottom"][0][Y] = bal_bbox[0][Y]
            bboxes["bottom"][1][Y] = bal_bbox[1][Y]


def draw_pins(unit_num, unit_pins, bbox, transform, fuzzy_match):
    """Draw a column of pins rotated/translated by the transform matrix."""

    # String to add pin definitions to.
    pin_defn = ""

    # Find the actual height of the column of pins and subtract it from the
    # bounding box (which should be at least as large). Half the difference
    # will be the offset needed to center the pins on the side of the symbol.
    Y = 1  # Index for Y coordinate.
    pins_bb = pins_bbox(unit_pins)
    height_offset = abs(bbox[0][Y] - bbox[1][Y]) - abs(pins_bb[0][Y] - pins_bb[1][Y])
    height_offset /= 2
    height_offset -= (
        height_offset % PIN_SPACING
    )  # Keep everything on the PIN_SPACING grid.

    # Start drawing pins from the origin.
    x = XO
    y = YO - height_offset

    for name, pins in unit_pins:

        # Detect pins with "spacer" pin numbers.
        pin_spacer = 0
        pin_num_len = 0
        for pin in pins:
            pin_num, pin_spacer = get_pin_num_and_spacer(pin)
            pin_num_len = max(pin_num_len, len(pin_num))
        y -= pin_spacer * PIN_SPACING  # Add space between pins if there was a spacer.
        if pin_num_len == 0:
            continue  # Omit pin if it only had a spacer prefix and no actual pin number.

        # Rotate/translate the current drawing point.
        (draw_x, draw_y) = transform * (x, y)

        # Use approximate matching to determine the pin's type, style and orientation.
        pin_type = find_closest_match(pins[0].type, PIN_TYPES, fuzzy_match)
        pin_style = find_closest_match(pins[0].style, PIN_STYLES, fuzzy_match)
        pin_side = find_closest_match(pins[0].side, PIN_ORIENTATIONS, fuzzy_match)

        if pins[0].hidden.lower().strip() in ["y", "yes", "t", "true", "1"]:
            pin_style = "N" + pin_style

        # Create all the pins with a particular name. If there are more than one,
        # they are laid on top of each other and only the first is visible.
        num_size = PIN_NUM_SIZE  # First pin will be visible.
        for pin in pins:

            pin_num = str(pin.num)

            # Remove any spacer prefix on the pin numbers.
            if pin_num.startswith(PIN_SPACER_PREFIX):
                pin_num = pin_num[1:]

            # Create a pin using the pin data.
            pin_defn += PIN.format(
                name=pin.name,
                num=pin_num,
                x=int(draw_x),
                y=int(draw_y),
                length=PIN_LENGTH,
                orientation=pin_side,
                num_sz=num_size,
                name_sz=PIN_NAME_SIZE,
                unit_num=unit_num,
                pin_type=pin_type,
                pin_style=pin_style,
            )

            # Turn off visibility after the first pin.
            num_size = 0

        # Move to the next pin placement location on this unit.
        y -= PIN_SPACING

    return pin_defn  # Return part symbol definition with pins added.


def zero_pad_nums(s):
    # Pad all numbers in the string with leading 0's.
    # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
    # appear before A10 in a list.
    try:
        return re.sub(
            r"\d+", lambda mtch: "0" * (8 - len(mtch.group(0))) + mtch.group(0), s
        )
    except TypeError:
        return s  # The input is probably not a string, so just return it unchanged.


def num_key(pin):
    """Generate a key from a pin's number so they are sorted by position on the package."""

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'A10' and 'A2' will become 'A00010' and 'A00002' and A2 will
    # appear before A10 in a list.
    return zero_pad_nums(pin[1][0].num)


def name_key(pin):
    """Generate a key from a pin's name so they are sorted more logically."""

    # Pad all numeric strings in the pin name with leading 0's.
    # Thus, 'adc10' and 'adc2' will become 'adc00010' and 'adc00002' and adc2 will
    # appear before adc10 in a list.
    return zero_pad_nums(pin[1][0].name)


def row_key(pin):
    """Generate a key from the order the pins were entered into the CSV file."""
    return pin[1][0].index


def draw_symbol(
    part_num,
    part_ref_prefix,
    part_footprint,
    part_manf_num,
    part_datasheet,
    part_desc,
    pin_data,
    sort_type,
    reverse,
    fuzzy_match,
    fill,
):
    """Add a symbol for a part to the library."""

    # Start the part definition with the header.
    part_defn = START_DEF.format(
        name=part_num,
        ref=part_ref_prefix,
        pin_name_offset=PIN_NAME_OFFSET,
        show_pin_number=SHOW_PIN_NUMBER and "Y" or "N",
        show_pin_name=SHOW_PIN_NAME and "Y" or "N",
        num_units=len(pin_data),
    )

    # Determine if there are pins across the top of the symbol.
    # If so, right-justify the reference, part number, etc. so they don't
    # run into the top pins. If not, stick with left-justification.
    text_justification = "L"
    horiz_offset = PIN_LENGTH
    for unit in list(pin_data.values()):
        if "top" in list(unit.keys()):
            text_justification = "R"
            horiz_offset = PIN_LENGTH - 50
            break

    # Create the field that stores the part reference.
    if not part_ref_prefix:
        part_ref_prefix = "U"
    part_defn += REF_FIELD.format(
        ref_prefix=part_ref_prefix,
        x=XO + horiz_offset,
        y=YO + REF_Y_OFFSET,
        text_justification=text_justification,
        font_size=REF_SIZE,
    )

    # Create the field that stores the part number.
    if not part_num:
        part_num = ""
    part_defn += PARTNUM_FIELD.format(
        num=part_num,
        x=XO + horiz_offset,
        y=YO + PART_NUM_Y_OFFSET,
        text_justification=text_justification,
        font_size=PART_NUM_SIZE,
    )

    # Create the field that stores the part footprint.
    if not part_footprint:
        part_footprint = ""
    part_defn += FOOTPRINT_FIELD.format(
        footprint=part_footprint,
        x=XO + horiz_offset,
        y=YO + PART_FOOTPRINT_Y_OFFSET,
        text_justification=text_justification,
        font_size=PART_FOOTPRINT_SIZE,
    )

    # Create the field that stores the datasheet link.
    if not part_datasheet:
        part_datasheet = ""
    part_defn += DATASHEET_FIELD.format(
        datasheet=part_datasheet,
        x=XO + horiz_offset,
        y=YO + PART_DATASHEET_Y_OFFSET,
        text_justification=text_justification,
        font_size=PART_DATASHEET_SIZE,
    )

    # Create the field that stores the manufacturer part number.
    if part_manf_num:
        part_defn += MPN_FIELD.format(
            manf_num=part_manf_num,
            x=XO + horiz_offset,
            y=YO + PART_MPN_Y_OFFSET,
            text_justification=text_justification,
            font_size=PART_MPN_SIZE,
        )

    # Create the field that stores the datasheet link.
    if part_desc:
        part_defn += DESC_FIELD.format(
            desc=part_desc,
            x=XO + horiz_offset,
            y=YO + PART_DESC_Y_OFFSET,
            text_justification=text_justification,
            font_size=PART_DESC_SIZE,
        )

    # Start the section of the part definition that holds the part's units.
    part_defn += START_DRAW

    # Get a reference to the sort-key generation function for pins.
    pin_key_func = getattr(THIS_MODULE, "{}_key".format(sort_type))

    # This is the sort-key generation function for unit names.
    unit_key_func = lambda x: zero_pad_nums(x[0])

    # Now create the units that make up the part. Unit numbers go from 1
    # up to the number of units in the part. The units are sorted by their
    # names before assigning unit numbers.
    for unit_num, unit in enumerate(
        [p[1] for p in sorted(pin_data.items(), key=unit_key_func)], 1
    ):

        # The indices of the X and Y coordinates in a list of point coords.
        X = 0
        Y = 1

        # Initialize data structures that store info for each side of a schematic symbol unit.
        all_sides = ["left", "right", "top", "bottom"]
        bbox = {side: [(XO, YO), (XO, YO)] for side in all_sides}
        box_pt = {side: [XO + PIN_LENGTH, YO + PIN_SPACING] for side in all_sides}
        anchor_pt = {side: [XO + PIN_LENGTH, YO + PIN_SPACING] for side in all_sides}
        transform = {}

        # Annotate the pins for each side of the symbol.
        for side_pins in list(unit.values()):
            annotate_pins(list(side_pins.items()))

        # Determine the actual bounding box for each side.
        bbox = {}
        for side, side_pins in list(unit.items()):
            bbox[side] = pins_bbox(list(side_pins.items()))

        # Adjust the sizes of the bboxes to make the unit look more symmetrical.
        balance_bboxes(bbox)

        # Determine some important points for each side of pins.
        for side in unit:
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
            anchor_pt[side] = [
                max(bbox[side][0][X], bbox[side][1][X]),
                max(bbox[side][0][Y], bbox[side][1][Y]),
            ]
            box_pt[side] = [
                min(bbox[side][0][X], bbox[side][1][X]) + PIN_LENGTH,
                max(bbox[side][0][Y], bbox[side][1][Y]),
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

        # Create zero-sized bounding boxes for any sides of the unit without pins.
        # This makes it simpler to do the width/height calculation that follows.
        for side in all_sides:
            if side not in bbox:
                bbox[side] = [(XO, YO), (XO, YO)]

        # This is the width and height of the box in the middle of the pins on each side.
        box_width = max(
            abs(bbox["top"][0][Y] - bbox["top"][1][Y]),
            abs(bbox["bottom"][0][Y] - bbox["bottom"][1][Y]),
        )
        box_height = max(
            abs(bbox["left"][0][Y] - bbox["left"][1][Y]),
            abs(bbox["right"][0][Y] - bbox["right"][1][Y]),
        )

        for side in all_sides:
            # Each side of pins starts off with the orientation of a left-hand side of pins.
            # Transformation matrix starts by rotating the side of pins.
            transform[side] = Affine.rotation(ROTATION[side])
            # Now rotate the anchor point to see where it goes.
            rot_anchor_pt = transform[side] * anchor_pt[side]
            # Translate the rotated anchor point to coincide with the AL anchor point.
            translate_x = anchor_pt["left"][X] - rot_anchor_pt[X]
            translate_y = anchor_pt["left"][Y] - rot_anchor_pt[Y]
            # Make additional translation to bring the AL point to the correct position.
            if side == "right":
                # Translate AL to AR.
                translate_x += box_width
                translate_y -= box_height
            elif side == "bottom":
                # Translate AL to AB
                translate_y -= box_height
            elif side == "top":
                # Translate AL to AT
                translate_x += box_width
            # Create the complete transformation matrix = rotation followed by translation.
            transform[side] = (
                Affine.translation(translate_x, translate_y) * transform[side]
            )
            # Also translate the point on each side that defines the box around the symbol.
            box_pt[side] = transform[side] * box_pt[side]

        # Draw the transformed pins for each side of the symbol.
        for side, side_pins in list(unit.items()):
            # If the pins are ordered by their row in the spreadsheet or by their name,
            # then reverse their order on the right and top sides so they go from top-to-bottom
            # on the right side and left-to-right on the top side instead of the opposite
            # as happens with counter-clockwise pin-number ordering.
            side_reverse = reverse
            if sort_type in ["name", "row"] and side in ["right", "top"]:
                side_reverse = not reverse
            # Sort the pins for the desired order: row-wise, numeric (pin #), alphabetical (pin name).
            sorted_side_pins = sorted(
                list(side_pins.items()), key=pin_key_func, reverse=side_reverse
            )
            # Draw the transformed pins for this side of the symbol.
            part_defn += draw_pins(
                unit_num, sorted_side_pins, bbox[side], transform[side], fuzzy_match
            )

            # Create the box around the unit's pins.
        part_defn += BOX.format(
            x0=int(box_pt["left"][X]),
            y0=int(box_pt["top"][Y]),
            x1=int(box_pt["right"][X]),
            y1=int(box_pt["bottom"][Y]),
            unit_num=unit_num,
            line_width=BOX_LINE_WIDTH,
            fill=FILLS[fill],
        )

    # Close the section that holds the part's units.
    part_defn += END_DRAW

    # Close the part definition.
    part_defn += END_DEF

    # Return complete part symbol definition.
    return part_defn


def is_pwr(pin, fuzzy_match):
    """Return true if this is a power input pin."""
    return (
        find_closest_match(name=pin.type, name_dict=PIN_TYPES, fuzzy_match=fuzzy_match)
        == "W"
    )


def do_bundling(pin_data, bundle, fuzzy_match):
    """Handle bundling for power pins. Unbundle everything else."""
    for unit in list(pin_data.values()):
        for side in list(unit.values()):
            for name, pins in list(side.items()):
                if len(pins) > 1:
                    for index, p in enumerate(pins):
                        if is_pwr(p, fuzzy_match) and bundle:
                            side[p.name + "_pwr"].append(p)
                        else:
                            side[p.name + "_" + str(index)].append(p)
                    del side[name]


def scan_for_readers():
    """Look for scripts for reading part description files."""

    trailer = "_reader.py"  # Reader file names always end with this.
    readers = {}
    for dir in [os.path.dirname(os.path.abspath(__file__)), "."]:
        for f in os.listdir(dir):
            if f.endswith(trailer):
                reader_name = f.replace(trailer, "")
                readers[reader_name] = dir
    return readers


def kipart(
    part_reader,
    part_data_file,
    part_data_file_name,
    part_data_file_type,
    parts_lib,
    fill,
    allow_overwrite=False,
    sort_type="name",
    reverse=False,
    fuzzy_match=False,
    bundle=False,
    debug_level=0,
):
    """Read part pin data from a CSV/text/Excel file and write or append it to a library file."""

    # Get the part number and pin data from the CSV file.
    for (
        part_num,
        part_ref_prefix,
        part_footprint,
        part_manf_num,
        part_datasheet,
        part_desc,
        pin_data,
    ) in part_reader(part_data_file, part_data_file_name, part_data_file_type):

        # Handle retaining/overwriting parts that are already in the library.
        if parts_lib.get(part_num):
            if allow_overwrite:
                print("Overwriting part {}!".format(part_num))
            else:
                print("Retaining previous definition of part {}.".format(part_num))
                continue

        do_bundling(pin_data, bundle, fuzzy_match)

        # Draw the schematic symbol into the library.
        parts_lib[part_num] = draw_symbol(
            part_num=part_num,
            part_ref_prefix=part_ref_prefix,
            part_footprint=part_footprint,
            part_manf_num=part_manf_num,
            part_datasheet=part_datasheet,
            part_desc=part_desc,
            pin_data=pin_data,
            sort_type=sort_type,
            reverse=reverse,
            fuzzy_match=fuzzy_match,
            fill=fill,
        )


def read_lib_file(lib_file):
    parts_lib = OrderedDict()
    with open(lib_file, "r") as lib:
        part_def = ""
        for line in lib:
            start = re.match("DEF (?P<part_name>\S+)", line)
            end = re.match("ENDDEF$", line)
            if start:
                part_def = line
                part_name = start.group("part_name")
            elif end:
                part_def += line
                parts_lib[part_name] = part_def
            else:
                part_def += line
    return parts_lib


def write_lib_file(parts_lib, lib_file):
    print("Writing", lib_file, len(parts_lib))
    LIB_HEADER = "EESchema-LIBRARY Version 2.3\n"
    with open(lib_file, "w") as lib_fp:
        lib_fp.write(LIB_HEADER)
        for part_def in parts_lib.values():
            lib_fp.write(part_def)


def call_kipart(args, part_reader, part_data_file, file_name, file_type, parts_lib):
    """Helper routine for calling kipart from main()."""
    return kipart(
        part_reader=part_reader,
        part_data_file=part_data_file,
        part_data_file_name=file_name,
        part_data_file_type=file_type,
        parts_lib=parts_lib,
        fill=args.fill,
        allow_overwrite=args.overwrite,
        sort_type=args.sort,
        reverse=args.reverse,
        fuzzy_match=args.fuzzy_match,
        bundle=args.bundle,
        debug_level=args.debug,
    )


def main():

    # Get Python routines for reading part description/CSV files.
    readers = scan_for_readers()

    parser = ap.ArgumentParser(
        description="Generate single & multi-unit schematic symbols for KiCad from a CSV file."
    )

    parser.add_argument(
        "-v", "--version", action="version", version="KiPart " + __version__
    )
    parser.add_argument(
        "input_files",
        nargs="+",
        type=str,
        metavar="file.[csv|txt|xlsx|zip]",
        help="Files for parts in CSV/text/Excel format or as such files in .zip archives.",
    )
    parser.add_argument(
        "-r",
        "--reader",
        nargs="?",
        type=lambda s: unicode(s).lower(),
        choices=readers.keys(),
        default="generic",
        help="Name of function for reading the CSV or part description files.",
    )
    parser.add_argument(
        "-s",
        "--sort",
        nargs="?",
        #        type=str.lower,
        type=lambda s: unicode(s).lower(),
        choices=["row", "num", "name"],
        default="row",
        help="Sort the part pins by their entry order in the CSV file, their pin number, or their pin name.",
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Sort pins in reverse order."
    )
    parser.add_argument(
        "--side",
        nargs="?",
        #        type=str.lower,
        type=lambda s: unicode(s).lower(),
        choices=["left", "right", "top", "bottom"],
        default="left",
        help="Which side to place the pins by default.",
    )
    parser.add_argument(
        "-o",
        "--output",
        nargs="?",
        type=str,
        metavar="file.lib",
        help="Generated KiCad symbol library for parts.",
    )
    parser.add_argument(
        "-f",
        "--fuzzy_match",
        action="store_true",
        help="Use approximate string matching when looking-up the pin type, style and orientation.",
    )
    parser.add_argument(
        "-b",
        "--bundle",
        action="store_true",
        help="Bundle multiple, identically-named power and ground pins each into a single schematic pin.",
    )
    parser.add_argument(
        "-a",
        "--append",
        "--add",
        action="store_true",
        help="Add parts to an existing part library. Overwrite existing parts only if used in conjunction with -w.",
    )
    parser.add_argument(
        "-w",
        "--overwrite",
        action="store_true",
        help="Allow overwriting of an existing part library.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        nargs="?",
        type=int,
        default=0,
        metavar="LEVEL",
        help="Print debugging info. (Larger LEVEL means more info.)",
    )
    parser.add_argument(
        "--fill",
        nargs="?",
        type=lambda s: unicode(s).lower(),
        choices=["no_fill", "fg_fill", "bg_fill"],
        default="no_fill",
        help="Select fill/no-fill for schematic symbol boxes.",
    )

    args = parser.parse_args()

    # kipart f1.csv f2.csv              # Create f1.lib, f2.lib
    # kipart f1.csv f2.csv -w           # Overwrite f1.lib, f2.lib
    # kipart f1.csv f2.csv -a           # Append to f1.lib, f2.lib
    # kipart f1.csv f2.csv -o f.lib     # Create f.lib
    # kipart f1.csv f2.csv -w -o f.lib  # Overwrite f.lib
    # kipart f1.csv f2.csv -a -o f.lib  # Append to f.lib

    # Load the function for reading the part description file.
    part_reader_name = args.reader + "_reader"  # Name of the reader module.
    reader_dir = readers[args.reader]
    sys.path.append(reader_dir)  # Import from dir where the reader is
    if reader_dir == ".":
        importlib.import_module(part_reader_name)  # Import module.
        reader_module = sys.modules[part_reader_name]  # Get imported module.
    else:
        importlib.import_module("kipart." + part_reader_name)  # Import module.
        reader_module = sys.modules[
            "kipart." + part_reader_name
        ]  # Get imported module.
    part_reader = getattr(reader_module, part_reader_name)  # Get reader function.

    DEFAULT_PIN.side = args.side

    check_file_exists = True  # Used to check for existence of a single output lib file.

    for input_file in args.input_files:

        # No explicit output lib file, so each individual input file will generate its own .lib file.
        if check_file_exists or not args.output:
            output_file = args.output or os.path.splitext(input_file)[0] + ".lib"
            if os.path.isfile(output_file):
                # The output lib file already exists.
                if args.overwrite:
                    # Overwriting an existing file, so ignore the existing parts.
                    parts_lib = OrderedDict()
                elif args.append:
                    # Appending to an existing file, so read in existing parts.
                    parts_lib = read_lib_file(output_file)
                else:
                    print(
                        "Output file {} already exists! Use the --overwrite option to replace it or the --append option to append to it.".format(
                            output_file
                        )
                    )
                    sys.exit(1)
            else:
                # Lib file doesn't exist, so create a new lib file starting with no parts.
                parts_lib = OrderedDict()

        # Don't setup the output lib file again if -o option was used to specify a single output lib.
        check_file_exists = not args.output

        file_ext = os.path.splitext(input_file)[-1].lower()  # Get input file extension.

        if file_ext == ".zip":
            # Process the individual files inside a ZIP archive.
            with zipfile.ZipFile(input_file, "r") as zip_file:
                for zipped_file in zip_file.infolist():
                    zip_file_ext = os.path.splitext(zipped_file.filename)[-1]
                    if zip_file_ext in [".csv", ".txt"]:
                        # Only process CSV, TXT, Excel files in the archive.
                        with zip_file.open(zipped_file, "r") as part_data_file:
                            part_data_file = io.TextIOWrapper(part_data_file)
                            call_kipart(
                                args,
                                part_reader,
                                part_data_file,
                                zipped_file.filename,
                                zip_file_ext,
                                parts_lib,
                            )
                    elif zip_file_ext in [".xlsx"]:
                        xlsx_data = zip_file.read(zipped_file)
                        part_data_file = io.BytesIO(xlsx_data)
                        call_kipart(
                            args,
                            part_reader,
                            part_data_file,
                            zipped_file.filename,
                            zip_file_ext,
                            parts_lib,
                        )
                    else:
                        # Skip unrecognized files.
                        continue

        elif file_ext in [".csv", ".txt"]:
            # Process CSV and TXT files.
            with open(input_file, "r") as part_data_file:
                call_kipart(
                    args, part_reader, part_data_file, input_file, file_ext, parts_lib
                )

        elif file_ext in [".xlsx"]:
            # Process Excel files.
            with open(input_file, "rb") as part_data_file:
                call_kipart(
                    args, part_reader, part_data_file, input_file, file_ext, parts_lib
                )

        else:
            # Skip unrecognized files.
            continue

        if not args.output:
            # No global output lib file, so output a lib file for each input file.
            write_lib_file(parts_lib, output_file)

    if args.output:
        # Only a single lib output file was given, so write library to it after all
        # the input files were processed.
        write_lib_file(parts_lib, output_file)


# main entrypoint.
if __name__ == "__main__":
    main()
