# MIT license
#
# Copyright (C) 2016-2021 by Dave Vandenbout.
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


"""
Parsers for netlist files of various formats (only KiCad, at present).
"""


from __future__ import absolute_import, division, print_function, unicode_literals

import re
import string
import sys
from builtins import open
from random import choice, randint

from future import standard_library

standard_library.install_aliases()


THIS_MODULE = locals()


def gen_random_part_csv():
    def random_name(len=20):
        chars = string.printable[:94]
        chars = re.sub('"', "", chars)
        chars = re.sub("'", "", chars)
        chars = re.sub(",", "", chars)
        chars = re.sub("\|", "", chars)
        return "".join(choice(chars) for _ in range(randint(1, len)))

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

    def pin_key(unit_pinnum_tuple):
        return zero_pad_nums(unit_pinnum_tuple[0]) + zero_pad_nums(unit_pinnum_tuple[1])

    part_name = random_name()
    ref_prefix = random_name(2)
    part_csv = "{part_name},{ref_prefix},,,,,".format(**locals())
    part_csv = "\n".join([part_csv, "Pin,Name,Type,Side,Unit,Style,Hidden"])

    num_units = randint(1, 10)
    pins = {}
    for unit in range(1, num_units + 1):
        unit_name = str(unit)
        for _ in range(randint(num_units, 256) // num_units):
            pin_num = (
                choice(string.ascii_uppercase + "           ") + str(randint(1, 256))
            ).strip()
            pin_name = random_name()
            pin_side = choice(["left", "right", "top", "bottom"])
            pin_type = choice(
                [
                    "in",
                    "out",
                    "bidir",
                    "tri",
                    "passive",
                    "pwr",
                    "pwr_out",
                    "open_collector",
                    "open_emitter",
                    "unspecified",
                    "NC",
                ]
            )
            pin_style = choice(
                [
                    "",
                    "inv",
                    "clk",
                    "inv_clk",
                    "input_low",
                    "clk_low",
                    "output_low",
                    "falling_clk",
                    "non_logic",
                ]
            )
            pin_hidden = choice(["Y", ""])
            pin_csv = "{pin_num},{pin_name},{pin_type},{pin_side},{unit_name},{pin_style},{pin_hidden}".format(
                **locals()
            )
            pins[(unit_name, pin_num)] = pin_csv
    for p in sorted(pins.keys(), key=pin_key):
        part_csv = "\n".join([part_csv, pins[p]])

    part_csv = "\n".join([part_csv, ",,,,,,"])
    return part_csv


def gen_random_lib_csv(num_lines=1000):
    lib_csv = gen_random_part_csv()
    while lib_csv.count("\n") < num_lines:
        lib_csv = "\n".join([lib_csv, gen_random_part_csv()])
    lib_csv += "\n"
    return lib_csv


if __name__ == "__main__":
    print(gen_random_lib_csv())
