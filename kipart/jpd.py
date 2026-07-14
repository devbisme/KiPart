#!/usr/bin/env python3
"""Convert between the SPD and JPD part description formats.

SPD (Shorthand Part Description) is the terse text format meant to be typed by
hand. JPD (JSON Part Description) holds the same information as JSON, spelling
out what SPD encodes as type codes and modifier characters. See SPD.md and
JPD.md for the two formats.
"""

__all__ = [
    "spd_to_jpd",
    "jpd_to_spd",
    "spd2jpd",
    "jpd2spd",
    "spd2jpd_cli",
    "jpd2spd_cli",
]

import argparse
import json
import os
import re
import sys

from .kilib2spd import (
    KICAD_STYLE_TO_SPD,
    KICAD_TYPE_TO_SPD,
    NUMBERED_NAME,
    SIDE_ORDER,
    _format_pin_line,
    pin_to_spd_fields,
)
from .spd2csv import parse_pin_type_field, parse_spd

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

# JPD names pin styles the way KiCad does, but a couple of the styles that come
# back from parsing SPD go by another name.
SPD_STYLE_TO_KICAD = {
    "": "line",
    "analog": "non_logic",
}

# Matches an SPD 'device' line, a property line, and a 'unit' directive.
DEVICE_RE = re.compile(r"^device\s+(\S+)$")
PROPERTY_RE = re.compile(r"^(\w+)\s*:\s*(.*)$")
UNIT_RE = re.compile(r"^unit\s+(\S+)$", re.IGNORECASE)


# ===== SPD to JPD =====


def _pin_names(name, numbers):
    """
    Give the name of each pin created by one SPD pin line.

    A line carrying several pin numbers repeats the name across all of them,
    unless the name ends in a number, in which case it is incremented for each
    pin (a0, a1, a2...). The second return value says which rule was applied.
    """
    match = NUMBERED_NAME.search(name)

    if len(numbers) > 1 and match:
        base, start = match.group(1), int(match.group(2))
        return [f"{base}{start + i}" for i in range(len(numbers))], True

    return [name] * len(numbers), False


def _add_pin(unit, side, line, pins_by_number):
    """Add the pins of one SPD pin line to a unit of a JPD part."""
    type_field, name, *numbers = line.split()
    pin_type, pin_style, pin_hidden = parse_pin_type_field(type_field)

    # JPD names the type and style in full and keeps visibility to itself,
    # rather than packing all three into a type code and its modifiers.
    pin = {
        "type": pin_type,
        "style": SPD_STYLE_TO_KICAD.get(pin_style, pin_style),
    }
    if pin_hidden == "yes":
        pin["hidden"] = True

    names, increment = _pin_names(name, numbers)

    # A pin number used a second time defines an alternate for the pin that
    # already claimed it, rather than a pin of its own.
    new_names, new_numbers = [], []
    for pin_name, number in zip(names, numbers):
        if number in pins_by_number:
            alternate = dict(pin, name=pin_name)
            alternate.pop("hidden", None)  # Visibility belongs to the pin itself.
            pins_by_number[number].setdefault("alternates", []).append(alternate)
        else:
            new_names.append(pin_name)
            new_numbers.append(number)

    if not new_numbers:
        return

    pin["name"] = new_names[0]
    pin["numbers"] = new_numbers
    if increment and len(new_numbers) > 1:
        pin["increment"] = True

    # Reorder the keys so a pin reads name-first when written out as JSON.
    key_order = ["name", "numbers", "type", "style", "hidden", "increment"]
    pin = {key: pin[key] for key in key_order if key in pin}

    unit[side].append(pin)
    for number in new_numbers:
        pins_by_number[number] = pin


def _symbol_to_part(lines):
    """Convert the lines of one SPD symbol into a JPD part."""
    device = DEVICE_RE.match(lines[0])
    if not device:
        raise ValueError(f"Invalid device line: {lines[0]}")

    part = {"name": device.group(1)}
    properties = {}
    units = []
    units_by_name = {}
    pins_by_number = {}  # Maps a unit name to its pins, for spotting alternates.
    side = "left"  # The side that pins go on until a side directive says otherwise.

    def get_unit(name):
        """Fetch a unit by name, creating it if this is its first mention."""
        if name not in units_by_name:
            unit = {} if name is None else {"name": name}
            units_by_name[name] = unit
            pins_by_number[name] = {}
            units.append(unit)
        return units_by_name[name]

    # Pins that appear before any unit directive land in a single unnamed unit.
    unit_name = None

    for line in lines[1:]:
        property_ = PROPERTY_RE.match(line)
        if property_:
            properties[property_.group(1)] = property_.group(2)
            continue

        unit_directive = UNIT_RE.match(line)
        if unit_directive:
            unit_name = unit_directive.group(1)
            continue

        if line.lower() in SIDE_ORDER:
            side = line.lower()
            continue

        # A unit comes into being when the first pin or spacer lands in it, and
        # its sides appear in the order the SPD file first uses them.
        unit = get_unit(unit_name)
        unit.setdefault(side, [])

        if line == "*":
            # Merge a run of spacers into a single JPD spacer.
            if unit[side] and "spacer" in unit[side][-1]:
                unit[side][-1]["spacer"] += 1
            else:
                unit[side].append({"spacer": 1})
            continue

        # Anything else is a pin line: a type, a name, and pin numbers.
        if len(line.split()) >= 3:
            _add_pin(unit, side, line, pins_by_number[unit_name])

    if properties:
        part["properties"] = properties

    # Drop the sides that were named but ended up with no pins on them.
    part["units"] = [
        {key: value for key, value in unit.items() if key not in SIDE_ORDER or value}
        for unit in units
    ]

    return part


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
        "parts": [_symbol_to_part(lines) for lines in parse_spd(spd)],
    }


# ===== JPD to SPD =====


def _spd_pin_lines(name, numbers, type_field, increment, indent):
    """
    Write the SPD lines for one JPD pin.

    SPD increments a name that ends in a number when its line carries several
    pin numbers, so a pin that doesn't want that gets a line per number.
    """
    if len(numbers) > 1 and NUMBERED_NAME.search(name) and not increment:
        return [_format_pin_line(type_field, name, [n], indent) for n in numbers]

    if increment and not NUMBERED_NAME.search(name):
        raise ValueError(
            f"Pin '{name}' asks for incrementing names but its name doesn't end "
            "in a number"
        )

    return [_format_pin_line(type_field, name, numbers, indent)]


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
            if not re.fullmatch(r"\w+", prop_name):
                raise ValueError(
                    f"Property name '{prop_name}' of part '{name}' isn't a single word"
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
                        lines.extend(f"{indent}*" for _ in range(entry["spacer"]))
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


if __name__ == "__main__":
    spd2jpd_cli()
