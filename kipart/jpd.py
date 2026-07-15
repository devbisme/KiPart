#!/usr/bin/env python3
"""Convert between the SPD and JPD part description formats.

SPD (Shorthand Part Description) is the terse text format meant to be typed by
hand. JPD (JSON Part Description) holds the same information as JSON, spelling
out what SPD encodes as type codes and modifier characters. See SPD.md and
JPD.md for the two formats.

A KiCad symbol library can be read straight into JPD as well, which is how a
part gets a description free of the geometry the library wraps it in.
"""

__all__ = [
    "spd_to_jpd",
    "jpd_to_spd",
    "symbol_lib_to_jpd",
    "spd2jpd",
    "jpd2spd",
    "kilib2jpd",
    "spd2jpd_cli",
    "jpd2spd_cli",
    "kilib2jpd_cli",
]

import argparse
import json
import os
import sys

from simp_sexp import Sexp

from .part import symbol_lib_to_parts
from .spd import (
    KICAD_STYLE_TO_SPD,
    KICAD_TYPE_TO_SPD,
    NUMBERED_NAME,
    SIDE_ORDER,
    format_pin_line,
    format_spacer_line,
    is_property_name,
    parse_spd,
    parse_spd_symbol,
    pin_to_spd_fields,
)

try:
    from .version import __version__
except ImportError:
    __version__ = "unknown"

# Identifies the format and revision of a JPD file.
JPD_FORMAT = "jpd"
JPD_VERSION = 1

# Defaults for the optional fields of a JPD pin.
DEFAULT_TYPE = "passive"
DEFAULT_STYLE = "line"

# ===== SPD to JPD =====


def spd_to_jpd(spd):
    """
    Convert SPD text into a JPD part description.

    Args:
        spd (str): The contents of an SPD file.

    Returns:
        dict: The equivalent JPD description.

    Raises:
        ValueError: If the SPD text is malformed.
    """
    return {
        "format": JPD_FORMAT,
        "version": JPD_VERSION,
        "parts": [parse_spd_symbol(lines) for lines in parse_spd(spd)],
    }


# ===== KiCad symbol library to JPD =====


def symbol_lib_to_jpd(symbol_lib):
    """
    Convert a KiCad symbol library into a JPD part description.

    What the library says about the part — its pins, their names, types, styles,
    and alternates, and the properties of the part — comes across; the geometry
    it's drawn with doesn't, since JPD has no way to say it and kipart lays a
    symbol out afresh from the description anyway.

    Args:
        symbol_lib (str or Sexp): KiCad symbol library S-expression.

    Returns:
        dict: The equivalent JPD description.

    Raises:
        ValueError: If the library contains no symbols.
    """
    return {
        "format": JPD_FORMAT,
        "version": JPD_VERSION,
        "parts": symbol_lib_to_parts(symbol_lib, geometry=False),
    }


# ===== JPD to SPD =====


def _spd_pin_lines(name, numbers, type_field, increment, indent):
    """
    Write the SPD lines for one JPD pin.

    SPD increments a name that ends in a number when its line carries several
    pin numbers, so a pin that doesn't want that gets a line per number.
    """
    if len(numbers) > 1 and NUMBERED_NAME.search(name) and not increment:
        return [format_pin_line(type_field, name, [n], indent) for n in numbers]

    if increment and not NUMBERED_NAME.search(name):
        raise ValueError(
            f"Pin '{name}' asks for incrementing names but its name doesn't end "
            "in a number"
        )

    return [format_pin_line(type_field, name, numbers, indent)]


def _type_field(pin, hidden):
    """Build the SPD type field of a JPD pin, checking its type and style."""
    pin_type = pin.get("type", DEFAULT_TYPE)
    pin_style = pin.get("style", DEFAULT_STYLE)

    if pin_type not in KICAD_TYPE_TO_SPD:
        raise ValueError(
            f"Pin '{pin.get('name')}' has unknown type '{pin_type}'. "
            f"Use one of: {', '.join(sorted(KICAD_TYPE_TO_SPD))}"
        )
    if pin_style not in KICAD_STYLE_TO_SPD:
        raise ValueError(
            f"Pin '{pin.get('name')}' has unknown style '{pin_style}'. "
            f"Use one of: {', '.join(sorted(KICAD_STYLE_TO_SPD))}"
        )

    return pin_to_spd_fields(pin_type, pin_style, hidden)


def _pin_to_spd(pin, indent):
    """Convert a JPD pin into its SPD lines, alternates included."""
    try:
        name = pin["name"]
        numbers = pin["numbers"]
    except KeyError as e:
        raise ValueError(f"Pin is missing the required key {e.args[0]!r}: {pin}")

    if not isinstance(numbers, list) or not numbers:
        raise ValueError(f"Pin '{name}' needs a non-empty list of pin numbers")

    hidden = pin.get("hidden", False)
    increment = pin.get("increment", False)
    lines = _spd_pin_lines(name, numbers, _type_field(pin, hidden), increment, indent)

    # An alternate re-uses the pin numbers of the pin it belongs to, and shares
    # its visibility, so only its name, type, and style are its own.
    for alternate in pin.get("alternates", []):
        lines.extend(
            _spd_pin_lines(
                alternate["name"],
                numbers,
                _type_field(alternate, hidden),
                alternate.get("increment", increment),
                indent,
            )
        )

    return lines


def jpd_to_spd(jpd):
    """
    Convert a JPD part description into SPD text.

    Args:
        jpd (dict): A JPD description, as read from a JPD file.

    Returns:
        str: The equivalent SPD text.

    Raises:
        ValueError: If the JPD description is malformed.
    """
    if not isinstance(jpd, dict) or not isinstance(jpd.get("parts"), list):
        raise ValueError("JPD description needs a 'parts' list")

    parts = []

    for part in jpd["parts"]:
        try:
            name = part["name"]
            units = part["units"]
        except KeyError as e:
            raise ValueError(f"Part is missing the required key {e.args[0]!r}")

        lines = [f"device {name}"]

        for prop_name, prop_value in part.get("properties", {}).items():
            if not is_property_name(prop_name):
                raise ValueError(
                    f"Property name '{prop_name}' of part '{name}' can't be written "
                    "in SPD: a name holds neither whitespace nor a colon"
                )
            lines.append(f"{prop_name}: {prop_value}")

        for unit in units:
            unit_name = unit.get("name")
            if unit_name:
                lines.append("")
                lines.append(f"unit {unit_name}")
                indent, side_indent = " " * 8, " " * 4
            else:
                indent, side_indent = " " * 4, ""

            # Sides come out in the order the JPD lists them.
            for side in (key for key in unit if key in SIDE_ORDER):
                if not unit[side]:
                    continue

                lines.append("")
                lines.append(f"{side_indent}{side}")

                for entry in unit[side]:
                    if "spacer" in entry:
                        lines.append(format_spacer_line(entry["spacer"], indent))
                    else:
                        lines.extend(_pin_to_spd(entry, indent))

        parts.append("\n".join(lines) + "\n")

    return "\n".join(parts)


# ===== File Conversion Functions =====


def _output_file(input_file, output_file, extension, overwrite):
    """Settle on the output path of a conversion and check it can be written."""
    if not output_file:
        output_file = os.path.splitext(input_file)[0] + extension

    if output_file != "-" and os.path.exists(output_file) and not overwrite:
        raise ValueError(
            f"Output file {output_file} already exists. Use --overwrite to allow overwriting."
        )

    return output_file


def _write(output_file, content):
    """Write the converted text to a file, or to stdout for '-'."""
    if output_file == "-":
        sys.stdout.write(content)
    else:
        with open(output_file, "w") as f:
            f.write(content)


def spd2jpd(spd_file, jpd_file=None, overwrite=False):
    """
    Convert an SPD file into a JPD file.

    Args:
        spd_file (str): Path to the input SPD file.
        jpd_file (str, optional): Path for the output JPD file. If None, uses the
                                 input filename with a .jpd extension. Use '-' to
                                 write to stdout.
        overwrite (bool, optional): Allow overwriting an existing output file.
                                   Defaults to False.

    Returns:
        str: Path to the generated JPD file, or '-' if written to stdout.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If the SPD file is malformed, or the output file exists and
                   overwrite is False.
    """
    if not os.path.exists(spd_file):
        raise FileNotFoundError(f"Input file {spd_file} does not exist")

    jpd_file = _output_file(spd_file, jpd_file, ".jpd", overwrite)

    with open(spd_file, "r") as f:
        jpd = spd_to_jpd(f.read())

    _write(jpd_file, json.dumps(jpd, indent=2) + "\n")

    return jpd_file


def jpd2spd(jpd_file, spd_file=None, overwrite=False):
    """
    Convert a JPD file into an SPD file.

    Args:
        jpd_file (str): Path to the input JPD file.
        spd_file (str, optional): Path for the output SPD file. If None, uses the
                                 input filename with an .spd extension. Use '-' to
                                 write to stdout.
        overwrite (bool, optional): Allow overwriting an existing output file.
                                   Defaults to False.

    Returns:
        str: Path to the generated SPD file, or '-' if written to stdout.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If the JPD file is malformed, or the output file exists and
                   overwrite is False.
    """
    if not os.path.exists(jpd_file):
        raise FileNotFoundError(f"Input file {jpd_file} does not exist")

    spd_file = _output_file(jpd_file, spd_file, ".spd", overwrite)

    with open(jpd_file, "r") as f:
        spd = jpd_to_spd(json.load(f))

    _write(spd_file, spd)

    return spd_file


def kilib2jpd(symbol_lib_file, jpd_file=None, overwrite=False):
    """
    Convert a KiCad symbol library file into a JPD file.

    Args:
        symbol_lib_file (str): Path to the input KiCad symbol library (.kicad_sym).
        jpd_file (str, optional): Path for the output JPD file. If None, uses the
                                 input filename with a .jpd extension. Use '-' to
                                 write to stdout.
        overwrite (bool, optional): Allow overwriting an existing output file.
                                   Defaults to False.

    Returns:
        str: Path to the generated JPD file, or '-' if written to stdout.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If the input isn't a .kicad_sym file, if it holds no symbols,
                   or if the output file exists and overwrite is False.
    """
    if not os.path.exists(symbol_lib_file):
        raise FileNotFoundError(f"Input file {symbol_lib_file} does not exist")

    if os.path.splitext(symbol_lib_file)[1].lower() != ".kicad_sym":
        raise ValueError(f"Input file must be a .kicad_sym file, got {symbol_lib_file}")

    jpd_file = _output_file(symbol_lib_file, jpd_file, ".jpd", overwrite)

    with open(symbol_lib_file, "r") as f:
        jpd = symbol_lib_to_jpd(Sexp(f.read()))

    _write(jpd_file, json.dumps(jpd, indent=2) + "\n")

    return jpd_file


# ===== Command-Line Interface Functions =====


def _convert_files(convert, description, extension):
    """Run one of the conversions over the files named on the command line."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input_files", nargs="+", help="Input files to convert")
    parser.add_argument(
        "-o", "--output", help=f"Output {extension} file path ('-' writes to stdout)"
    )
    parser.add_argument(
        "-w",
        "--overwrite",
        action="store_true",
        help="Allow overwriting of an existing output file",
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
            output_file = convert(
                input_file, args.output, overwrite=args.overwrite
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


def spd2jpd_cli():
    """
    Command-line interface for converting SPD files to JPD files.

    Usage:
        spd2jpd [-h] [-v] [-o OUTPUT] [-w] input_files [input_files ...]

    Examples:
        spd2jpd part.spd            # Generate part.jpd
        spd2jpd -o - part.spd       # Write the JPD to stdout
    """
    _convert_files(
        spd2jpd, "Convert SPD part description files into JPD (JSON) files", ".jpd"
    )


def jpd2spd_cli():
    """
    Command-line interface for converting JPD files to SPD files.

    Usage:
        jpd2spd [-h] [-v] [-o OUTPUT] [-w] input_files [input_files ...]

    Examples:
        jpd2spd part.jpd            # Generate part.spd
        jpd2spd -o - part.jpd       # Write the SPD to stdout
    """
    _convert_files(
        jpd2spd, "Convert JPD (JSON) part description files into SPD files", ".spd"
    )


def kilib2jpd_cli():
    """
    Command-line interface for converting KiCad symbol libraries to JPD files.

    Usage:
        kilib2jpd [-h] [-v] [-o OUTPUT] [-w] input_files [input_files ...]

    Examples:
        kilib2jpd lib.kicad_sym         # Generate lib.jpd
        kilib2jpd -o - lib.kicad_sym    # Write the JPD to stdout
    """
    _convert_files(
        kilib2jpd,
        "Convert KiCad symbol libraries into JPD (JSON) part description files, "
        "leaving behind the geometry the symbols are drawn with",
        ".jpd",
    )


if __name__ == "__main__":
    spd2jpd_cli()
