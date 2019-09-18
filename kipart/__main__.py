# MIT license
#
# Copyright (C) 2015 by XESS Corporation
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

from __future__ import absolute_import, print_function

import argparse as ap
import io
import os
import re
import sys
import zipfile
from collections import OrderedDict

from .__init__ import __version__
from .common import DEFAULT_PIN, issue
from .kipart import *


def main():
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
        metavar="file1.[csv|zip] file2.[csv|zip] ...",
        help="Files for parts in CSV format or as CSV files in .zip archives.",
    )
    parser.add_argument(
        "-r",
        "--reader",
        nargs="?",
        type=str.lower,
        choices=[
            "generic",
            "xilinxultra",
            "xilinx7",
            "xilinx6s",
            "xilinx6v",
            "psoc5lp",
            "stm32cube",
            "lattice",
        ],
        default="generic",
        help="Name of function for reading the CSV files.",
    )
    parser.add_argument(
        "-s",
        "--sort",
        nargs="?",
        type=str.lower,
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
        type=str.lower,
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

    args = parser.parse_args()

    # kipart f1.csv f2.csv              # Create f1.lib, f2.lib
    # kipart f1.csv f2.csv -w           # Overwrite f1.lib, f2.lib
    # kipart f1.csv f2.csv -a           # Append to f1.lib, f2.lib
    # kipart f1.csv f2.csv -o f.lib     # Create f.lib
    # kipart f1.csv f2.csv -w -o f.lib  # Overwrite f.lib
    # kipart f1.csv f2.csv -a -o f.lib  # Append to f.lib

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
        LIB_HEADER = "EESchema-LIBRARY Version 2.3\n"
        with open(lib_file, "w") as lib_fp:
            lib_fp.write(LIB_HEADER)
            for part_def in parts_lib.values():
                lib_fp.write(part_def)

    def call_kipart(part_data_file):
        """Helper routine for calling kipart."""
        return kipart(
            reader_type=args.reader,
            part_data_file=part_data_file,
            parts_lib=parts_lib,
            allow_overwrite=args.overwrite,
            sort_type=args.sort,
            reverse=args.reverse,
            fuzzy_match=args.fuzzy_match,
            bundle=args.bundle,
            debug_level=args.debug,
        )

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

        file_ext = os.path.splitext(input_file)[-1]  # Get input file extension.

        if file_ext == ".zip":
            # Process the individual files inside a ZIP archive.
            zip_file = zipfile.ZipFile(input_file, "r")
            zipped_files = zip_file.infolist()
            for zipped_file in zipped_files:
                if os.path.splitext(zipped_file.filename)[-1] in [".csv", ".txt"]:
                    # Only process CSV and TXT files in the archive.
                    with zip_file.open(zipped_file, "r") as part_data_file:
                        part_data_file = io.TextIOWrapper(part_data_file)
                        call_kipart(part_data_file)

        elif file_ext in [".csv", ".txt"]:
            # Process CSV and TXT files.
            with open(input_file, "r") as part_data_file:
                call_kipart(part_data_file)

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
