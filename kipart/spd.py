#!/usr/bin/env python3
"""The SPD (Shorthand Part Description) format, in both directions.

This module owns everything that knows how SPD is spelled: its comment syntax,
its pin type codes and style modifiers, the way it names several pins from one
line, and how a pin line is read and written. The converters built on top of it
(spd2csv, kilib2spd, jpd) deal only in the parsed pieces.

See SPD.md for the format itself.
"""

__all__ = [
    # Format tables
    "COMMENT_DELIM",
    "SPD_TYPE_MAP",
    "SPD_STYLE_MAP",
    "STYLE_TO_KICAD",
    "SPD_STYLE_TO_KICAD",
    "KICAD_TYPE_TO_SPD",
    "KICAD_STYLE_TO_SPD",
    "SIDE_ORDER",
    # Reading SPD
    "parse_spd",
    "parse_spd_file",
    "parse_spd_symbol",
    "parse_pin_type_field",
    "expand_pin_names",
    # Writing SPD
    "pin_to_spd_fields",
    "format_pin_line",
    "format_spacer_line",
]

import re
import sys
from pathlib import Path

# The sides of a symbol, in the order they're written out.
SIDE_ORDER = ("left", "right", "top", "bottom")

# SPD comment delimiters (both full-line and in-line).
COMMENT_DELIM = (
    ";",
    "//",
)

# A comment only starts at the beginning of a line or after whitespace so that
# values such as "Datasheet: https://example.com/ds.pdf" stay intact.
COMMENT_RE = re.compile(
    r"(?:^|(?<=\s))(?:" + "|".join(re.escape(d) for d in COMMENT_DELIM) + r")"
)

# A pin name ending in digits is incremented when its line carries several pin
# numbers, so "a0" over four numbers gives a0, a1, a2, a3.
NUMBERED_NAME = re.compile(r"(\D+)(\d+)$")

# The lines that introduce a part, one of its properties, and one of its units.
DEVICE_RE = re.compile(r"^device\s+(\S+)$")
PROPERTY_RE = re.compile(r"^(\w+)\s*:\s*(.*)$")
UNIT_RE = re.compile(r"^unit\s+(\S+)$", re.IGNORECASE)

# A spacer line leaves empty pin positions on a side. Several of them are asked
# for by repeating the asterisk ("***") or by giving a count ("*3").
SPACER_RE = re.compile(r"^(\*+)\s*(\d*)$")

# Map SPD pin type codes to KiCad pin types.
SPD_TYPE_MAP = {
    'p': 'power_in',
    'pi': 'power_in',
    'pwr': 'power_in',
    'pwr_in': 'power_in',
    'po': 'power_out',
    'pwr_out': 'power_out',
    'i': 'input',
    'in': 'input',
    'o': 'output',
    'out': 'output',
    'b': 'bidirectional',
    'bi': 'bidirectional',
    'io': 'bidirectional',
    't': 'tri_state',
    'tri': 'tri_state',
    'oc': 'open_collector',
    'oe': 'open_emitter',
    'pass': 'passive',
    'f': 'free',
    'u': 'unspecified',
    'un': 'unspecified',
    'a': 'unspecified',
    'analog': 'unspecified',
    'x': 'no_connect',
    'nc': 'no_connect',
}

# Map SPD modifier characters to the pin attribute each one sets.
SPD_STYLE_MAP = {
    '*': 'inverted',
    '!': 'inverted',
    '~': 'inverted',
    '/': 'inverted',
    '#': 'inverted',
    '>': 'clock',
    '_': 'low',
    '@': 'analog',
    '-': 'hidden',
}

# Map a set of pin attributes to the pin style it adds up to. A 'low' pin style
# depends on the pin type, so the type joins the set before it's looked up.
STYLE_TO_KICAD = {
    frozenset({'inverted'}): 'inverted',
    frozenset({'clock'}): 'clock',
    frozenset({'inverted', 'clock'}): 'inverted_clock',
    frozenset({'low', 'input'}): 'input_low',
    frozenset({'low', 'output'}): 'output_low',
    frozenset({'low', 'input', 'clock'}): 'clock_low',
    frozenset({'low', 'output', 'clock'}): 'clock_low',
    frozenset({'analog'}): 'analog',
    frozenset({}): '',
}

# The two styles above that KiCad knows by another name.
SPD_STYLE_TO_KICAD = {
    "": "line",
    "analog": "non_logic",
}

# Map KiCad pin types to their SPD type codes (the inverse of SPD_TYPE_MAP).
KICAD_TYPE_TO_SPD = {
    "power_in": "p",
    "power_out": "po",
    "input": "i",
    "output": "o",
    "bidirectional": "b",
    "tri_state": "t",
    "open_collector": "oc",
    "open_emitter": "oe",
    "passive": "pass",
    "free": "f",
    "unspecified": "u",
    "no_connect": "x",
}

# Map KiCad pin styles to their SPD modifier characters.
KICAD_STYLE_TO_SPD = {
    "line": "",
    "inverted": "!",
    "clock": ">",
    "inverted_clock": "!>",
    "input_low": "_",
    "output_low": "_",
    "clock_low": ">_",
    "edge_clock_high": ">",
    "non_logic": "@",
}

# Styles whose SPD modifiers only mean something on an input or output pin.
LOW_STYLES = ("input_low", "output_low", "clock_low")


def warn(message):
    """Report something an SPD file can't express."""
    print(f"Warning: {message}", file=sys.stderr)


# ===== Reading SPD =====


def parse_spd(content: str) -> list[list[str]]:
    """Parse SPD-format text into a list of symbols, each a list of lines.

    Blank lines and comments are removed.
    """
    # Split into symbol definitions (separated by 'device' keyword)
    symbols = []
    current_symbol_lines = []
    in_symbol = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Remove full-line and in-line comments
        comment = COMMENT_RE.search(stripped)
        if comment:
            stripped = stripped[:comment.start()].strip()

        # Skip lines that were nothing but a comment
        if not stripped:
            continue

        # Start of a new symbol definition
        if stripped.startswith('device '):
            # Save previous symbol if exists
            if current_symbol_lines:
                symbols.append(current_symbol_lines)
            current_symbol_lines = [stripped]
            in_symbol = True
        elif in_symbol:
            # Append the current, non-empty line to the current symbol definition
            current_symbol_lines.append(stripped)
        else:
            # Lines outside of any symbol definition are illegal.
            raise ValueError(f"Text outside of device definition: {line}")

    # Add the last symbol
    if current_symbol_lines:
        symbols.append(current_symbol_lines)

    return symbols


def parse_spd_file(filepath: Path) -> list[list[str]]:
    """Parse an SPD-format symbol description file.

    Returns a list of symbols, each a list of lines.
    """
    with open(filepath, 'r') as f:
        return parse_spd(f.read())


def parse_pin_type_field(field: str) -> tuple[str, str, str]:
    """Parse the type field of an SPD pin line.

    The field is a pin type code with optional style modifiers attached before
    or after it, e.g. "i", "i*", "-i*>".

    Returns the pin type, the pin style, and 'yes'/'no' for the pin visibility.
    """
    # The type code is the alphabetic part of the field, the modifiers the rest.
    pin_type_code = ''.join(c for c in field if c.isalpha())
    style_mods = ''.join(c for c in field if not c.isalpha())

    pin_type = SPD_TYPE_MAP.get(pin_type_code, 'passive')

    try:
        style = {SPD_STYLE_MAP[mod] for mod in style_mods}
    except KeyError as e:
        raise ValueError(f"Unsupported pin modifier: {e.args[0]} in {field}")

    # Visibility is carried by a modifier but isn't a style.
    pin_hidden = 'no'
    if 'hidden' in style:
        pin_hidden = 'yes'
        style.discard('hidden')

    # A 'low' pin style depends on whether the pin is an input or an output.
    if 'low' in style:
        style.add(pin_type)

    try:
        pin_style = STYLE_TO_KICAD[frozenset(style)]
    except KeyError:
        raise ValueError(f"Unsupported combination of pin modifiers: {field}")

    return pin_type, pin_style, pin_hidden


def _spacer_count(spacer, line, part_name):
    """Give the number of empty pin positions a spacer line asks for.

    The count is either the number of asterisks ("***") or the number written
    after a single one ("*3"), but not a mix of the two.
    """
    stars, count = spacer.group(1), spacer.group(2)

    if not count:
        return len(stars)

    if len(stars) > 1:
        raise ValueError(
            f"Ambiguous spacer in part '{part_name}': {line!r}. Give a count "
            "after a single asterisk, or repeat the asterisk, but not both."
        )

    if int(count) < 1:
        raise ValueError(f"Spacer count in part '{part_name}' must be 1 or more: {line!r}")

    return int(count)


def _add_pin(unit, side, line, pins_by_number):
    """Add the pins of one SPD pin line to a unit of a parsed part."""
    type_field, name, *numbers = line.split()
    pin_type, pin_style, pin_hidden = parse_pin_type_field(type_field)

    # The parsed form names the type and style in full and keeps visibility to
    # itself, rather than packing all three into a type code and its modifiers.
    pin = {
        "type": pin_type,
        "style": SPD_STYLE_TO_KICAD.get(pin_style, pin_style),
    }
    if pin_hidden == "yes":
        pin["hidden"] = True

    names, increment = expand_pin_names(name, numbers)

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


def parse_spd_symbol(lines: list) -> dict:
    """Parse the lines of one SPD symbol into a structured part.

    This is the single reader of SPD's directives; the converters work from the
    part it returns rather than walking the lines themselves. The part is shaped
    like this, which is also the JPD format (see JPD.md):

        {
            "name": "rt9818",
            "properties": {"Manf": "Richtek"},
            "units": [
                {
                    "name": "A",                    # Absent if the part has no
                    "left": [                       #   unit directives.
                        {"name": "vcc", "numbers": ["3"], "type": "power_in",
                         "style": "line"},          # Plus "hidden", "increment",
                        {"spacer": 1},              #   and "alternates" as needed.
                    ],
                },
            ],
        }

    Pin types and styles are named the way KiCad names them, several pins from
    one line stay as one entry carrying all their numbers, a re-used pin number
    becomes an alternate of the pin that claimed it, and a run of spacers is one
    entry with a count.

    Raises:
        ValueError: If the symbol has no valid device line.
    """
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

        spacer = SPACER_RE.match(line)
        if spacer:
            # Merge a run of spacers into a single spacer entry.
            count = _spacer_count(spacer, line, part["name"])
            if unit[side] and "spacer" in unit[side][-1]:
                unit[side][-1]["spacer"] += count
            else:
                unit[side].append({"spacer": count})
            continue

        # Anything else has to be a pin line: a type, a name, and pin numbers.
        if len(line.split()) < 3:
            raise ValueError(
                f"Unrecognized line in part '{part['name']}': {line!r}. A pin "
                "line needs a type, a name, and at least one pin number."
            )

        _add_pin(unit, side, line, pins_by_number[unit_name])

    if properties:
        part["properties"] = properties

    # Drop the sides that were named but ended up with no pins on them.
    part["units"] = [
        {key: value for key, value in unit.items() if key not in SIDE_ORDER or value}
        for unit in units
    ]

    return part


def expand_pin_names(name: str, numbers: list) -> tuple[list, bool]:
    """Give the name of each pin created by one SPD pin line.

    A line carrying several pin numbers repeats the name across all of them,
    unless the name ends in a number, in which case it is incremented for each
    pin (a0, a1, a2...). The second return value says which rule was applied.
    """
    match = NUMBERED_NAME.search(name)

    if len(numbers) > 1 and match:
        base, start = match.group(1), int(match.group(2))
        return [f"{base}{start + i}" for i in range(len(numbers))], True

    return [name] * len(numbers), False


# ===== Writing SPD =====


def pin_to_spd_fields(pin_type, pin_style, hidden=False):
    """
    Build the SPD type field (type code plus style modifiers) for a pin.

    Args:
        pin_type (str): KiCad pin electrical type (e.g. 'input', 'power_in').
        pin_style (str): KiCad pin graphical style (e.g. 'line', 'inverted').
        hidden (bool, optional): Whether the pin is hidden. Defaults to False.

    Returns:
        str: The SPD type field, e.g. 'i', 'i!>', 'pass-'.
    """
    try:
        type_code = KICAD_TYPE_TO_SPD[pin_type]
    except KeyError:
        warn(f"unknown pin type '{pin_type}'; using 'pass'")
        type_code = "pass"

    try:
        mods = KICAD_STYLE_TO_SPD[pin_style]
    except KeyError:
        warn(f"unknown pin style '{pin_style}'; using 'line'")
        mods = ""

    # SPD derives input_low/output_low/clock_low from the '_' modifier combined
    # with the pin type, so '_' can't be represented on any other type.
    if pin_style in LOW_STYLES and pin_type not in ("input", "output"):
        warn(
            f"style '{pin_style}' can't be applied to a '{pin_type}' pin in SPD; "
            "dropping the 'low' modifier"
        )
        mods = mods.replace("_", "")

    if hidden:
        mods += "-"

    return type_code + mods


def format_pin_line(type_field, name, numbers, indent=""):
    """
    Format a single SPD pin line with the columns aligned.

    Fields wider than their column still get a separating space, since SPD
    splits a pin line on whitespace.
    """
    return f"{indent}{type_field:<7} {name:<11} {' '.join(numbers)}".rstrip()


def format_spacer_line(count, indent=""):
    """
    Format an SPD spacer line leaving the given number of pin positions empty.

    A single position is just an asterisk; several are written as a count.
    """
    return f"{indent}*" if count == 1 else f"{indent}*{count}"
