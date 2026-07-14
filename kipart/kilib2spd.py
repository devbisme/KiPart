#!/usr/bin/env python3
"""Convert KiCad symbol libraries into SPD (Shorthand Part Description) files.

This is the inverse of the spd2csv/kipart pipeline: it reads a .kicad_sym
library and writes the equivalent SPD text so an existing library can be
maintained in the compact SPD format.
"""

__all__ = [
    "pin_to_spd_fields",
    "symbol_to_spd",
    "symbol_lib_to_spd",
    "symbol_lib_file_to_spd_file",
    "kilib2spd",
]

import argparse
import os
import re
import sys

from simp_sexp import Sexp

from .kipart import (
    DEFAULT_UNIT_ID,
    PIN_SPACING,
    extract_symbols_from_lib,
    yntf_to_yesno,
)
from .spd import (
    NUMBERED_NAME,
    SIDE_ORDER,
    format_pin_line,
    format_spacer_line,
    pin_to_spd_fields,
    warn,
)

try:
    from .version import __version__
except ImportError:
    __version__ = "unknown"

# Map a pin orientation to the side of the symbol the pin is on.
ORIENTATION_TO_SIDE = {0: "left", 90: "bottom", 180: "right", 270: "top"}

# Property names/values that kipart supplies by default and which don't need
# to be written back out to the SPD file.
DEFAULT_PROPERTIES = {"Reference": "U"}


def _get_pins(unit):
    """Extract the pins of a unit as dicts of SPD-relevant pin data."""
    pins = []

    for pin in unit.search("/symbol/pin", ignore_case=True):
        at = pin.search("/pin/at", ignore_case=True)[0]
        orientation = int(at[3])
        try:
            side = ORIENTATION_TO_SIDE[orientation]
        except KeyError:
            warn(f"skipping pin with unsupported orientation {orientation}")
            continue

        hide = pin.search("/pin/hide", ignore_case=True)
        alternates = [
            {"name": alt[1], "type": alt[2], "style": alt[3]}
            for alt in pin.search("/pin/alternate", ignore_case=True)
        ]

        pins.append(
            {
                "number": pin.search("/pin/number", ignore_case=True)[0][1],
                "name": pin.search("/pin/name", ignore_case=True)[0][1],
                "type": pin[1],
                "style": pin[2],
                "hidden": bool(hide) and yntf_to_yesno(hide[0][1]) == "yes",
                "side": side,
                "x": float(at[1]),
                "y": float(at[2]),
                "alternates": alternates,
            }
        )

    return pins


def _order_side_pins(side, pins):
    """
    Sort the pins of one side into the order they're listed in an SPD file.

    Left/right pins are listed from top to bottom, top/bottom pins from left to
    right.
    """
    if side in ("left", "right"):
        # Pins run down the side, so later pins have smaller y coordinates.
        return sorted(pins, key=lambda p: (-p["y"], p["x"]))

    # Pins run across the side from left to right.
    return sorted(pins, key=lambda p: (p["x"], -p["y"]))


def _assign_spacers(side_pins):
    """
    Set the number of spacers preceding each pin of a unit.

    A gap between adjacent pins on a side becomes one spacer per empty position
    on the pin grid, so the groupings within a side survive the trip back
    through kipart. Where a side as a whole sits along its edge is not encoded:
    kipart re-derives that when it lays the symbol out again (see --push).

    Args:
        side_pins (dict): Maps each side name to its ordered list of pins. The
                         'spacers' key of each pin is set in place.
    """
    for side in SIDE_ORDER:
        for previous_pin, pin in zip([None] + side_pins[side][:-1], side_pins[side]):
            if previous_pin is None:
                pin["spacers"] = 0
                continue

            # Pins run down the left/right sides but across the top/bottom ones.
            if side in ("left", "right"):
                distance = previous_pin["y"] - pin["y"]
            else:
                distance = pin["x"] - previous_pin["x"]

            pin["spacers"] = max(round(distance / PIN_SPACING) - 1, 0)


def _mergeable(group, pin):
    """
    Test if a pin can be appended to a group of pins sharing one SPD line.

    Pins share a line when they're adjacent on a side and have the same type,
    style, and visibility. Their names must either all be identical (and free of
    a numeric suffix, which spd2csv would auto-increment) or form a run of names
    with consecutively incrementing numeric suffixes.
    """
    first, last = group[0], group[-1]

    if pin["spacers"] or pin["alternates"] or first["alternates"]:
        return False
    if (pin["type"], pin["style"], pin["hidden"]) != (
        first["type"],
        first["style"],
        first["hidden"],
    ):
        return False

    last_match = NUMBERED_NAME.search(last["name"])
    pin_match = NUMBERED_NAME.search(pin["name"])

    if not last_match and not pin_match:
        # Names without a numeric suffix have to match exactly since spd2csv
        # will replicate the single name across all the pin numbers.
        return pin["name"] == last["name"]

    if not last_match or not pin_match:
        return False

    # Names with a numeric suffix get incremented by spd2csv, so the group has
    # to be a run like a0, a1, a2 sharing the same base name.
    return pin_match.group(1) == last_match.group(1) and int(pin_match.group(2)) == int(
        last_match.group(2)
    ) + 1


def _group_side_pins(pins, compress=True):
    """Group the ordered pins of one side into the lines of an SPD file."""
    groups = []

    for pin in pins:
        if compress and groups and _mergeable(groups[-1], pin):
            groups[-1].append(pin)
        else:
            groups.append([pin])

    return groups


def symbol_to_spd(symbol, compress=True):
    """
    Convert a KiCad symbol into its SPD representation.

    Args:
        symbol (Sexp): Sexp object for a single symbol.
        compress (bool, optional): Combine adjacent pins that share a type,
                                  style, and name (or a run of incrementing
                                  names) onto a single SPD line. Defaults to True.

    Returns:
        str: The SPD text for the symbol, ending with a newline.
    """
    part_name = symbol.search("/symbol", ignore_case=True)[0][1]

    lines = [f"device {part_name}"]

    # Emit the properties that carry information beyond kipart's defaults.
    for _, prop_name, prop_value, *_discard in symbol.search(
        "/symbol/property", ignore_case=True
    ):
        if not prop_value:
            continue
        if DEFAULT_PROPERTIES.get(prop_name) == prop_value:
            continue
        if prop_name == "Value" and prop_value == part_name:
            continue
        if not re.fullmatch(r"\w+", prop_name):
            warn(
                f"property name '{prop_name}' of symbol '{part_name}' can't be "
                "represented in SPD; skipping it"
            )
            continue
        lines.append(f"{prop_name}: {prop_value}")

    units = symbol.search("/symbol/symbol", ignore_case=True)
    multi_unit = len(units) > 1

    for unit_index, unit in enumerate(units, 1):
        unit_name_search = unit.search("/symbol/unit_name", ignore_case=True)
        if unit_name_search:
            unit_id = unit_name_search[0][1]
        else:
            unit_id = str(unit_index)

        pins = _get_pins(unit)
        if not pins:
            continue

        if multi_unit or unit_id != DEFAULT_UNIT_ID:
            lines.append("")
            lines.append(f"unit {unit_id}")
            indent = " " * 8
            side_indent = " " * 4
        else:
            indent = " " * 4
            side_indent = ""

        side_pins = {
            side: _order_side_pins(side, [pin for pin in pins if pin["side"] == side])
            for side in SIDE_ORDER
        }
        _assign_spacers(side_pins)

        for side in SIDE_ORDER:
            if not side_pins[side]:
                continue

            lines.append("")
            lines.append(f"{side_indent}{side}")

            for group in _group_side_pins(side_pins[side], compress=compress):
                if group[0]["spacers"]:
                    lines.append(format_spacer_line(group[0]["spacers"], indent))

                pin = group[0]
                for field in ("name", "number"):
                    if any(char.isspace() for char in pin[field]):
                        warn(
                            f"pin {field} '{pin[field]}' of symbol '{part_name}' "
                            "contains whitespace, which SPD can't represent"
                        )
                lines.append(
                    format_pin_line(
                        pin_to_spd_fields(pin["type"], pin["style"], pin["hidden"]),
                        pin["name"],
                        [p["number"] for p in group],
                        indent,
                    )
                )

                # Alternate pin functions re-use the pin number on later lines.
                for alt in pin["alternates"]:
                    lines.append(
                        format_pin_line(
                            pin_to_spd_fields(alt["type"], alt["style"], pin["hidden"]),
                            alt["name"],
                            [pin["number"]],
                            indent,
                        )
                    )

    return "\n".join(lines) + "\n"


def symbol_lib_to_spd(symbol_lib, compress=True):
    """
    Convert a KiCad symbol library into its SPD representation.

    Args:
        symbol_lib (str or Sexp): KiCad symbol library S-expression.
        compress (bool, optional): Combine adjacent pins onto a single SPD line
                                  where possible. Defaults to True.

    Returns:
        str: The SPD text for every symbol in the library.

    Raises:
        ValueError: If the library contains no symbols.
    """
    symbols = extract_symbols_from_lib(symbol_lib)
    if not symbols:
        raise ValueError("No symbols found in the symbol library")

    return "\n".join(
        symbol_to_spd(symbol, compress=compress)
        for symbol in sorted(symbols, key=lambda s: s[1])
    )


def symbol_lib_file_to_spd_file(
    symbol_lib_file, spd_file=None, overwrite=False, compress=True
):
    """
    Convert a KiCad symbol library file into an SPD file.

    Args:
        symbol_lib_file (str): Path to the input KiCad symbol library (.kicad_sym).
        spd_file (str, optional): Path for the output SPD file. If None, uses the
                                 input filename with an .spd extension. Use '-' to
                                 write to stdout.
        overwrite (bool, optional): Allow overwriting an existing output file.
                                   Defaults to False.
        compress (bool, optional): Combine adjacent pins onto a single SPD line
                                  where possible. Defaults to True.

    Returns:
        str: Path to the generated SPD file, or '-' if written to stdout.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If the input isn't a .kicad_sym file, or the output file
                   exists and overwrite is False.
    """
    if not os.path.exists(symbol_lib_file):
        raise FileNotFoundError(f"Input file {symbol_lib_file} does not exist")

    if os.path.splitext(symbol_lib_file)[1].lower() != ".kicad_sym":
        raise ValueError(f"Input file must be a .kicad_sym file, got {symbol_lib_file}")

    if not spd_file:
        spd_file = os.path.splitext(symbol_lib_file)[0] + ".spd"

    if spd_file != "-" and os.path.exists(spd_file) and not overwrite:
        raise ValueError(
            f"Output file {spd_file} already exists. Use --overwrite to allow overwriting."
        )

    with open(symbol_lib_file, "r") as f:
        symbol_lib = Sexp(f.read())

    spd = symbol_lib_to_spd(symbol_lib, compress=compress)

    if spd_file == "-":
        sys.stdout.write(spd)
    else:
        with open(spd_file, "w") as f:
            f.write(spd)

    return spd_file


# ===== Command-Line Interface Function =====


def kilib2spd():
    """
    Command-line interface for converting KiCad symbol libraries to SPD files.

    Usage:
        kilib2spd [-h] [-v] [-o OUTPUT] [-w] [--no-compress] input_files [input_files ...]

    Examples:
        kilib2spd library.kicad_sym           # Generate library.spd
        kilib2spd -o out.spd lib.kicad_sym    # Generate out.spd from lib.kicad_sym
        kilib2spd -o - lib.kicad_sym          # Write the SPD to stdout
        kilib2spd -w *.kicad_sym              # Convert several libraries, overwriting existing SPDs

    Args:
        None (uses sys.argv via argparse).

    Returns:
        None

    Exits:
        0: On successful completion.
        1: If errors occur during processing.
    """
    parser = argparse.ArgumentParser(
        description="Convert KiCad symbol libraries into SPD (Shorthand Part Description) files"
    )
    parser.add_argument(
        "input_files", nargs="+", help="Input KiCad symbol library files (.kicad_sym)"
    )
    parser.add_argument(
        "-o", "--output", help="Output SPD file path ('-' writes to stdout)"
    )
    parser.add_argument(
        "-w",
        "--overwrite",
        action="store_true",
        help="Allow overwriting of an existing SPD file",
    )
    parser.add_argument(
        "--no-compress",
        dest="compress",
        action="store_false",
        help="Give each pin its own line instead of combining pins that share a type, style, and name",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    if args.output and args.output != "-" and len(args.input_files) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)

    error_flag = False
    for input_file in args.input_files:
        try:
            output_file = symbol_lib_file_to_spd_file(
                input_file,
                spd_file=args.output,
                overwrite=args.overwrite,
                compress=args.compress,
            )
            if output_file != "-":
                print(f"Generated {output_file} successfully from {input_file}")
        except Exception as e:
            print(f"Error processing file '{input_file}': {str(e)}")
            error_flag = True
            continue

    if error_flag:
        print("Errors occurred during processing. Please check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    kilib2spd()
