#!/usr/bin/env python3
"""The neutral part structure, and the readers that produce it.

A part is the dict that `spd.parse_spd_symbol` returns and that JPD spells out
as JSON: a name, some properties, and units holding the pins of each side. This
module adds the missing reader — KiCad symbol to part — and a loader that will
read a part out of any of the three formats.

A part read from a .kicad_sym file can also carry the geometry that SPD and JPD
have no way to say: where each pin sits, how long it is, and the shapes of the
symbol body. Ask for it with `geometry=True`; the extra keys are ignored by
everything that only wants the electrical description of the part.

See JPD.md for the structure itself.
"""

__all__ = [
    "ORIENTATION_TO_SIDE",
    "DEFAULT_PROPERTIES",
    "symbol_to_part",
    "symbol_lib_to_parts",
    "load_parts",
    "flatten_unit",
    "unit_id",
]

import json
import os

from simp_sexp import Sexp

from .kipart import (
    DEFAULT_UNIT_ID,
    extract_symbols_from_lib,
    resolve_extends,
    yntf_to_yesno,
)
from .spd import (
    NUMBERED_NAME,
    SIDE_ORDER,
    is_property_name,
    parse_spd,
    parse_spd_symbol,
    warn,
)

# Map a pin orientation to the side of the symbol the pin is on.
ORIENTATION_TO_SIDE = {0: "left", 90: "bottom", 180: "right", 270: "top"}

# Property names/values that kipart supplies by default and which say nothing
# about the part itself.
DEFAULT_PROPERTIES = {"Reference": "U"}

# The children of a unit that aren't graphics.
NON_GRAPHIC_ITEMS = ("pin", "unit_name")

# The coordinates carried by the graphic items of a symbol.
POINT_ITEMS = ("at", "start", "end", "center", "mid", "xy")

# How closely two coordinates have to agree to count as the same place.
GEOMETRY_PRECISION = 4


def _round(value):
    """Round a coordinate, so that 0.0 and -0.0 are the same place."""
    return round(float(value), GEOMETRY_PRECISION) + 0.0


# ===== Reading a KiCad symbol =====


def _canonical(sexp):
    """Render an S-expression as one line, with its numbers rounded.

    Two graphic items that draw the same thing give the same string, whatever
    the file they came out of did with whitespace or trailing zeroes.
    """
    if isinstance(sexp, (Sexp, list)):
        return "(" + " ".join(_canonical(item) for item in sexp) + ")"

    text = str(sexp)
    try:
        return f"{_round(text):g}"
    except ValueError:
        return text


def _points(sexp):
    """Give every coordinate pair in a graphic item."""
    if not isinstance(sexp, (Sexp, list)) or not sexp:
        return

    if sexp[0] in POINT_ITEMS and len(sexp) >= 3:
        try:
            yield _round(sexp[1]), _round(sexp[2])
        except ValueError:
            pass  # An 'at' whose first field isn't a number belongs to something else.

    for item in sexp:
        yield from _points(item)


def _bounding_box(graphics):
    """Give the box that encloses the shapes of a symbol body, or None."""
    points = [point for graphic in graphics for point in _points(graphic)]
    if not points:
        return None

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _pin_to_part(pin, geometry):
    """Convert one pin of a KiCad symbol into a part's pin, or None to skip it.

    The pin comes back with the single number it has in the symbol; a part read
    from SPD or JPD may instead carry several numbers on one pin.
    """
    at = pin.search("/pin/at", ignore_case=True)[0]
    orientation = int(at[3])
    if orientation not in ORIENTATION_TO_SIDE:
        warn(f"skipping pin with unsupported orientation {orientation}")
        return None, None

    hide = pin.search("/pin/hide", ignore_case=True)
    length = pin.search("/pin/length", ignore_case=True)

    # A pin name or number that reads as a number comes back as one from an
    # unquoted S-expression, but a pin number is a name, not a quantity.
    part_pin = {
        "name": str(pin.search("/pin/name", ignore_case=True)[0][1]),
        "numbers": [str(pin.search("/pin/number", ignore_case=True)[0][1])],
        "type": str(pin[1]),
        "style": str(pin[2]),
    }

    if bool(hide) and yntf_to_yesno(hide[0][1]) == "yes":
        part_pin["hidden"] = True

    alternates = [
        {"name": str(alt[1]), "type": str(alt[2]), "style": str(alt[3])}
        for alt in pin.search("/pin/alternate", ignore_case=True)
    ]
    if alternates:
        part_pin["alternates"] = alternates

    if geometry:
        part_pin["geometry"] = {
            "x": _round(at[1]),
            "y": _round(at[2]),
            "orientation": orientation,
            "length": _round(length[0][1]) if length else None,
        }

    return ORIENTATION_TO_SIDE[orientation], part_pin


def _side_order(side, pins):
    """Sort the pins of one side into the order they're placed.

    Left and right pins run down their side, top and bottom pins across theirs.
    This is the order SPD and JPD list them in.
    """
    if side in ("left", "right"):
        return sorted(pins, key=lambda p: (-p["geometry"]["y"], p["geometry"]["x"]))

    return sorted(pins, key=lambda p: (p["geometry"]["x"], -p["geometry"]["y"]))


def _properties_to_part(symbol, part_name):
    """Collect the properties of a symbol that say something about the part."""
    properties = {}

    for _, prop_name, prop_value, *_discard in symbol.search(
        "/symbol/property", ignore_case=True
    ):
        if not prop_value:
            continue
        if DEFAULT_PROPERTIES.get(prop_name) == prop_value:
            continue
        if prop_name == "Value" and prop_value == part_name:
            continue
        if not is_property_name(prop_name):
            warn(
                f"property name '{prop_name}' of symbol '{part_name}' can't be "
                "represented in a part description; skipping it"
            )
            continue
        properties[prop_name] = prop_value

    return properties


def symbol_to_part(symbol, geometry=False):
    """
    Convert a KiCad symbol into a part.

    Args:
        symbol (Sexp): Sexp object for a single symbol.
        geometry (bool, optional): Keep the pin positions, pin lengths, and body
                                  shapes of the symbol, which the part
                                  description formats don't record. Defaults to
                                  False.

    Returns:
        dict: The part, shaped as described in JPD.md. Each pin carries the one
             pin number it has in the symbol, and the pins of a side are listed
             in the order they're placed. With geometry, each pin gains a
             'geometry' key and each unit a 'graphics' and 'bbox' key.
    """
    part_name = symbol.search("/symbol", ignore_case=True)[0][1]

    part = {"name": part_name}

    properties = _properties_to_part(symbol, part_name)
    if properties:
        part["properties"] = properties

    unit_symbols = symbol.search("/symbol/symbol", ignore_case=True)
    multi_unit = len(unit_symbols) > 1
    units = []

    for index, unit_symbol in enumerate(unit_symbols, 1):
        unit = {}

        # A unit is known by its name, or by its position if it hasn't got one.
        # The single unnamed unit of a one-unit part goes without either, the
        # way an SPD file with no unit directives describes it.
        name_search = unit_symbol.search("/symbol/unit_name", ignore_case=True)
        if name_search:
            unit["name"] = str(name_search[0][1])
        elif multi_unit or str(index) != DEFAULT_UNIT_ID:
            unit["name"] = str(index)

        side_pins = {side: [] for side in SIDE_ORDER}
        for pin in unit_symbol.search("/symbol/pin", ignore_case=True):
            # A pin needs its position to be placed on a side, even when the
            # caller has no use for the position itself.
            side, part_pin = _pin_to_part(pin, geometry=True)
            if side is None:
                continue
            side_pins[side].append(part_pin)

        for side in SIDE_ORDER:
            if not side_pins[side]:
                continue
            pins = _side_order(side, side_pins[side])
            if not geometry:
                for part_pin in pins:
                    del part_pin["geometry"]
            unit[side] = pins

        if geometry:
            graphics = [
                item
                for item in unit_symbol[2:]
                if isinstance(item, Sexp) and item[0] not in NON_GRAPHIC_ITEMS
            ]
            unit["graphics"] = sorted(_canonical(graphic) for graphic in graphics)
            unit["bbox"] = _bounding_box(graphics)

        units.append(unit)

    # A unit with no pins says nothing that a part description can record.
    if not geometry:
        units = [unit for unit in units if any(unit.get(side) for side in SIDE_ORDER)]

    part["units"] = units

    return part


def symbol_lib_to_parts(symbol_lib, geometry=False):
    """
    Convert a KiCad symbol library into a list of parts.

    Args:
        symbol_lib (str or Sexp): KiCad symbol library S-expression.
        geometry (bool, optional): Keep the geometry of each symbol. Defaults to
                                  False.

    Returns:
        list of dict: One part per symbol, in name order.

    Raises:
        ValueError: If the library contains no symbols.
    """
    symbols = extract_symbols_from_lib(symbol_lib)
    if not symbols:
        raise ValueError("No symbols found in the symbol library")

    # A part that extends another borrows its units and pins; give it a copy.
    symbols = resolve_extends(symbols)

    return [
        symbol_to_part(symbol, geometry=geometry)
        for symbol in sorted(symbols, key=lambda s: s[1])
    ]


# ===== Reading a part out of any of the formats =====


def load_parts(filename, geometry=True):
    """
    Read the parts of a .kicad_sym, .spd, or .jpd file.

    Args:
        filename (str): Path to the file. Its extension picks the format.
        geometry (bool, optional): Keep the geometry of a .kicad_sym file. The
                                  other formats have none to keep. Defaults to
                                  True.

    Returns:
        list of dict: The parts of the file.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the extension isn't one this can read, or the file is
                   malformed.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Input file {filename} does not exist")

    extension = os.path.splitext(filename)[1].lower()

    with open(filename, "r") as f:
        content = f.read()

    if extension == ".kicad_sym":
        return symbol_lib_to_parts(Sexp(content), geometry=geometry)

    if extension == ".spd":
        return [parse_spd_symbol(lines) for lines in parse_spd(content)]

    if extension == ".jpd":
        try:
            jpd = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"{filename} isn't valid JSON: {e}")
        if not isinstance(jpd, dict) or not isinstance(jpd.get("parts"), list):
            raise ValueError(f"{filename} has no 'parts' list")
        return jpd["parts"]

    raise ValueError(
        f"Don't know how to read {filename}. Give a .kicad_sym, .spd, or .jpd file."
    )


# ===== Working with a part =====


def unit_id(unit):
    """Give the name a unit goes by, which is '1' for the unit of a one-unit part."""
    return unit.get("name") or DEFAULT_UNIT_ID


def _expand_names(pin):
    """Give the name of each pin number carried by one pin of a part.

    A pin with several numbers usually repeats its name across all of them, the
    way a ground pin does. A pin that asks to increment numbers its names off
    the first one instead, which is how a bus is written.
    """
    name, numbers = pin["name"], pin["numbers"]

    if len(numbers) > 1 and pin.get("increment"):
        match = NUMBERED_NAME.search(name)
        if not match:
            raise ValueError(
                f"Pin '{name}' asks for incrementing names but its name doesn't "
                "end in a number"
            )
        base, start = match.group(1), int(match.group(2))
        return [f"{base}{start + i}" for i in range(len(numbers))]

    return [name] * len(numbers)


def flatten_unit(unit):
    """
    Spread the pins of a unit out, one entry per pin number.

    The formats describe several pins with one entry — a ground pin with a list
    of numbers, a bus with incrementing names — and a pin number used twice
    names an alternate of the pin that claimed it first. This undoes all of
    that, so a unit becomes the flat table of pins that KiCad would draw.

    Args:
        unit (dict): A unit of a part.

    Returns:
        tuple: A dict mapping each pin number to its pin, and a dict mapping
              each side to the sequence of things placed on it (pin numbers, and
              '*n' for a run of n empty positions).
    """
    pins = {}
    layout = {}

    for side in SIDE_ORDER:
        if side not in unit:
            continue

        sequence = []

        for entry in unit[side]:
            if "spacer" in entry:
                sequence.append(f"*{entry['spacer']}")
                continue

            alternates = [
                (alt["name"], alt.get("type", "passive"), alt.get("style", "line"))
                for alt in entry.get("alternates", [])
            ]

            for name, number in zip(_expand_names(entry), entry["numbers"]):
                # A pin number is a name, whatever the file wrote it as.
                number = str(number)

                # A pin number claimed a second time is an alternate function of
                # the pin that already has it.
                if number in pins:
                    pins[number]["alternates"].extend(
                        [(name, entry.get("type", "passive"), entry.get("style", "line"))]
                        + alternates
                    )
                    continue

                pins[number] = {
                    "number": number,
                    "name": name,
                    "type": entry.get("type", "passive"),
                    "style": entry.get("style", "line"),
                    "hidden": bool(entry.get("hidden", False)),
                    "side": side,
                    "alternates": list(alternates),
                    "geometry": entry.get("geometry"),
                }
                sequence.append(number)

        layout[side] = sequence

    return pins, layout
