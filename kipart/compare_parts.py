#!/usr/bin/env python3
"""Compare the parts of two or more libraries and report what differs.

The libraries can be .kicad_sym, .spd, or .jpd files, in any mix: each one is
read into the neutral part structure (see part.py) and the parts are compared
there, so a symbol library can be checked against the SPD file it was built
from.

Two things make the comparison useful rather than merely exact:

- **Geometry can be left out.** Where a pin sits, how long it is, and how big
  the body is say nothing about what the part *is*, and only a .kicad_sym file
  records them at all. `--ignore geometry` compares the electrical description
  alone: the pins, their names, types, styles, and alternates.

- **Parts don't have to be named alike.** The same part is called `OPA2333` in
  one library and `opa2333xdgk` in another. Matching can be exact, or on names
  compared without case and punctuation, or fuzzy, or on the pins themselves for
  parts whose names have nothing in common.

- **Units can be set aside.** How a part is split into units is a drawing
  decision, not a fact about the part. `--ignore units` compares the pins of each
  part as one table, so a part drawn as a single unit and the same part split
  across several come out alike.

Differences fall into four categories, of which `names`, `properties`, and
`geometry` can be ignored:

    names       part and unit names
    properties  the properties of a part
    pins        pins, and their names, types, styles, and alternates
    geometry    which side a pin is on, where it sits, and the body of the symbol
"""

__all__ = [
    "CATEGORIES",
    "IGNORABLE",
    "FORMATS",
    "compare_parts",
    "match_parts",
    "flatten_part",
    "compare_libraries",
    "report_rows",
    "format_report",
    "format_rich",
    "format_html",
    "show_html",
    "cmpparts",
]

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from difflib import SequenceMatcher

from .part import flatten_unit, load_parts, unit_id
from .spd import SIDE_ORDER

try:
    from .version import __version__
except ImportError:
    __version__ = "unknown"

# The kinds of difference that can be reported.
CATEGORIES = ("names", "properties", "pins", "geometry")

# What can be left out of a comparison. The first three are categories of
# difference; 'units' isn't one, but a way of comparing — it sets the unit
# boundaries aside and compares the pins of a part as a single table.
IGNORABLE = ("names", "properties", "geometry", "units")

# How the parts of two libraries are paired up.
MATCH_MODES = ("exact", "normalized", "fuzzy", "pins")

# How alike two names have to be before a fuzzy match will pair them.
DEFAULT_THRESHOLD = 0.6

# The ways a report can be written out.
FORMATS = ("text", "rich", "html", "json")

# Stands in for a value one of the two libraries hasn't got.
ABSENT = "—"


def _difference(category, message, unit=None, pin=None, field=None, first=ABSENT,
                second=ABSENT):
    """
    Record one difference between two parts.

    A difference says what it's about ('field') and what each of the two
    libraries has to say about it ('first' and 'second'), as well as carrying the
    sentence that says the same thing in prose. The parts are for a table, the
    prose for a person reading down a report.
    """
    return {
        "category": category,
        "unit": unit,
        "pin": pin,
        "field": field,
        "first": _value(first),
        "second": _value(second),
        "message": message,
    }


def _value(value):
    """Write a value of a difference out for a table cell."""
    if value is None:
        return ABSENT
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value)


# ===== Matching parts across libraries =====


def _normalize(name):
    """Reduce a part name to the letters and digits of its lowercase form."""
    return re.sub(r"[^0-9a-z]", "", name.lower())


def name_similarity(name_a, name_b):
    """Give how alike two part names are, from 0 (nothing alike) to 1 (the same)."""
    return SequenceMatcher(None, _normalize(name_a), _normalize(name_b)).ratio()


def _signature(part):
    """Give the pins of a part as a set, for recognizing it by its pinout alone."""
    signature = set()
    for unit in part.get("units", []):
        pins, _layout = flatten_unit(unit)
        signature.update(
            (number, pin["name"].lower()) for number, pin in pins.items()
        )
    return signature


def pin_similarity(part_a, part_b):
    """Give how alike the pinouts of two parts are, from 0 to 1."""
    signature_a, signature_b = _signature(part_a), _signature(part_b)
    if not signature_a or not signature_b:
        return 0.0

    return len(signature_a & signature_b) / len(signature_a | signature_b)


def _similarity(part_a, part_b, mode):
    """Score how likely it is that two parts are the same part."""
    if mode == "pins":
        return pin_similarity(part_a, part_b)

    return name_similarity(part_a["name"], part_b["name"])


def match_parts(parts_a, parts_b, mode="normalized", threshold=DEFAULT_THRESHOLD,
                aliases=None):
    """
    Pair up the parts of two libraries.

    Parts are paired by name first, however the mode says to compare names, and
    the pairing is one-to-one: a part left over on one side has no counterpart on
    the other.

    Args:
        parts_a (list): The parts of the first library.
        parts_b (list): The parts of the second library.
        mode (str, optional): How to pair parts up:
            'exact' — names must be identical.
            'normalized' — names are compared without case or punctuation.
            'fuzzy' — names have to be alike, but not the same.
            'pins' — parts are recognized by their pinout, whatever they're called.
            Defaults to 'normalized'.
        threshold (float, optional): How alike two parts have to be before 'fuzzy'
                                    or 'pins' will pair them. Defaults to 0.6.
        aliases (dict, optional): Names in the first library mapped to the names
                                 they go by in the second, pairing those parts up
                                 whatever the mode. Defaults to None.

    Returns:
        tuple: The pairs as a list of (part_a, part_b, score), the parts of the
              first library that went unpaired, and those of the second.
    """
    aliases = aliases or {}

    remaining_a = list(parts_a)
    remaining_b = {part["name"]: part for part in parts_b}
    pairs = []

    def take(part_a, part_b, score):
        pairs.append((part_a, part_b, score))
        del remaining_b[part_b["name"]]

    # A name the caller has paired up by hand settles the matter.
    for part_a in list(remaining_a):
        alias = aliases.get(part_a["name"])
        if alias and alias in remaining_b:
            take(part_a, remaining_b[alias], 1.0)
            remaining_a.remove(part_a)

    # An identical name is a match under every mode.
    for part_a in list(remaining_a):
        if part_a["name"] in remaining_b:
            take(part_a, remaining_b[part_a["name"]], 1.0)
            remaining_a.remove(part_a)

    if mode == "exact":
        return pairs, remaining_a, list(remaining_b.values())

    # Then names that differ only in their case or punctuation.
    if mode in ("normalized", "fuzzy"):
        normalized_b = {}
        for name, part_b in remaining_b.items():
            normalized_b.setdefault(_normalize(name), []).append(part_b)

        for part_a in list(remaining_a):
            candidates = normalized_b.get(_normalize(part_a["name"]))
            if candidates:
                part_b = candidates.pop(0)
                take(part_a, part_b, 1.0)
                remaining_a.remove(part_a)

    if mode == "normalized":
        return pairs, remaining_a, list(remaining_b.values())

    # What's left is paired up by how alike the parts are, best pair first, so
    # that a part is only matched to its closest counterpart.
    scores = sorted(
        (
            (_similarity(part_a, part_b, mode), index_a, part_a, part_b)
            for index_a, part_a in enumerate(remaining_a)
            for part_b in remaining_b.values()
        ),
        key=lambda score: (-score[0], score[1]),
    )

    for score, _index_a, part_a, part_b in scores:
        if score < threshold:
            break
        if part_a not in remaining_a or part_b["name"] not in remaining_b:
            continue
        take(part_a, part_b, score)
        remaining_a.remove(part_a)

    return pairs, remaining_a, list(remaining_b.values())


def _match_units(part_a, part_b):
    """
    Pair up the units of two parts.

    Units pair up by name, and any left over pair up by the pins they share, so
    that a unit called 'A' in one library and '1' in another still gets compared.

    Returns:
        tuple: The pairs as a list of (unit_a, unit_b), then the leftover units
              of each part.
    """
    units_a = list(part_a.get("units", []))
    units_b = list(part_b.get("units", []))
    pairs = []

    for unit_a in list(units_a):
        for unit_b in units_b:
            if unit_id(unit_a) == unit_id(unit_b):
                pairs.append((unit_a, unit_b))
                units_a.remove(unit_a)
                units_b.remove(unit_b)
                break

    # A unit whose name has changed is recognized by the pins it holds.
    def numbers(unit):
        pins, _layout = flatten_unit(unit)
        return set(pins)

    overlaps = sorted(
        (
            (len(numbers(unit_a) & numbers(unit_b)), index_a, unit_a, unit_b)
            for index_a, unit_a in enumerate(units_a)
            for unit_b in units_b
        ),
        key=lambda overlap: (-overlap[0], overlap[1]),
    )

    for shared, _index_a, unit_a, unit_b in overlaps:
        if not shared:
            break
        if unit_a not in units_a or unit_b not in units_b:
            continue
        pairs.append((unit_a, unit_b))
        units_a.remove(unit_a)
        units_b.remove(unit_b)

    return pairs, units_a, units_b


# ===== Comparing two parts =====


def _has_geometry(part):
    """Say whether a part knows where its pins are."""
    return any(
        pin.get("geometry")
        for unit in part.get("units", [])
        for side in SIDE_ORDER
        for pin in unit.get(side, [])
    )


def _compare_properties(part_a, part_b):
    """Compare the properties of two parts.

    Properties are paired up by name without regard to case, since kipart
    capitalizes the names it knows — an SPD file's 'footprint' becomes the
    'Footprint' property of the symbol built from it, and the part hasn't
    changed. Their values are compared as they're written.
    """

    def by_name(part):
        return {
            name.lower(): (name, value)
            for name, value in part.get("properties", {}).items()
        }

    properties_a, properties_b = by_name(part_a), by_name(part_b)
    differences = []

    for name in sorted(set(properties_a) - set(properties_b)):
        spelling, value = properties_a[name]
        differences.append(
            _difference(
                "properties",
                f"property '{spelling}' ({value!r}) is only in the first part",
                field=f"property '{spelling}'",
                first=value,
            )
        )

    for name in sorted(set(properties_b) - set(properties_a)):
        spelling, value = properties_b[name]
        differences.append(
            _difference(
                "properties",
                f"property '{spelling}' ({value!r}) is only in the second part",
                field=f"property '{spelling}'",
                second=value,
            )
        )

    for name in sorted(set(properties_a) & set(properties_b)):
        spelling, value_a = properties_a[name]
        _spelling_b, value_b = properties_b[name]
        if value_a != value_b:
            differences.append(
                _difference(
                    "properties",
                    f"property '{spelling}': {value_a!r} != {value_b!r}",
                    field=f"property '{spelling}'",
                    first=value_a,
                    second=value_b,
                )
            )

    return differences


def _compare_alternates(pin_a, pin_b, unit, number):
    """
    Compare the alternate functions of two pins that share a pin number.

    An alternate is compared the way the pin's own name is: alternates are
    matched by name, an alternate that only one pin has is flagged, and one both
    pins share has its type and style compared. KiCad doesn't order a pin's
    alternates, so neither does this.
    """
    # Each alternate is (name, type, style); key them by name to pair them up.
    alternates_a = {alt[0]: alt for alt in pin_a["alternates"]}
    alternates_b = {alt[0]: alt for alt in pin_b["alternates"]}
    differences = []

    def report(field, message, first=ABSENT, second=ABSENT):
        differences.append(
            _difference(
                "pins", message, unit=unit, pin=number,
                field=field, first=first, second=second,
            )
        )

    for name in sorted(set(alternates_a) - set(alternates_b)):
        report(
            "missing alternate",
            f"pin {number} alternate {name!r} is only in the first part",
            first=name,
        )

    for name in sorted(set(alternates_b) - set(alternates_a)):
        report(
            "missing alternate",
            f"pin {number} alternate {name!r} is only in the second part",
            second=name,
        )

    for name in sorted(set(alternates_a) & set(alternates_b)):
        _name_a, type_a, style_a = alternates_a[name]
        _name_b, type_b, style_b = alternates_b[name]
        if type_a != type_b:
            report(
                f"alternate {name!r} type",
                f"pin {number} alternate {name!r} type: {type_a!r} != {type_b!r}",
                first=type_a,
                second=type_b,
            )
        if style_a != style_b:
            report(
                f"alternate {name!r} style",
                f"pin {number} alternate {name!r} style: {style_a!r} != {style_b!r}",
                first=style_a,
                second=style_b,
            )

    return differences


def _compare_pin(pin_a, pin_b, unit, positions):
    """Compare the two pins that share a pin number."""
    number = pin_a["number"]
    differences = []

    def report(category, field, value_a, value_b):
        differences.append(
            _difference(
                category,
                f"pin {number} {field}: {value_a!r} != {value_b!r}",
                unit=unit,
                pin=number,
                field=field,
                first=value_a,
                second=value_b,
            )
        )

    for field in ("name", "type", "style", "hidden"):
        if pin_a[field] != pin_b[field]:
            report("pins", field, pin_a[field], pin_b[field])

    differences.extend(_compare_alternates(pin_a, pin_b, unit, number))

    if pin_a["side"] != pin_b["side"]:
        report("geometry", "side", pin_a["side"], pin_b["side"])

    # Only a symbol library says where a pin actually sits.
    if positions and pin_a["geometry"] and pin_b["geometry"]:
        geometry_a, geometry_b = pin_a["geometry"], pin_b["geometry"]

        position_a = (geometry_a["x"], geometry_a["y"], geometry_a["orientation"])
        position_b = (geometry_b["x"], geometry_b["y"], geometry_b["orientation"])
        if position_a != position_b:
            report("geometry", "position", position_a, position_b)

        if geometry_a["length"] != geometry_b["length"]:
            report("geometry", "length", geometry_a["length"], geometry_b["length"])

    return differences


def _compare_pins(pins_a, pins_b, unit, positions):
    """Compare two tables of pins, matching them up by pin number."""
    differences = []

    for number in sorted(set(pins_a) - set(pins_b)):
        differences.append(
            _difference(
                "pins",
                f"pin {number} ({pins_a[number]['name']!r}) is only in the first part",
                unit=unit,
                pin=number,
                field="missing pin",
                first=pins_a[number]["name"],
            )
        )

    for number in sorted(set(pins_b) - set(pins_a)):
        differences.append(
            _difference(
                "pins",
                f"pin {number} ({pins_b[number]['name']!r}) is only in the second part",
                unit=unit,
                pin=number,
                field="missing pin",
                second=pins_b[number]["name"],
            )
        )

    for number in sorted(set(pins_a) & set(pins_b)):
        differences.extend(
            _compare_pin(pins_a[number], pins_b[number], unit, positions)
        )

    return differences


def flatten_part(part):
    """
    Spread the pins of a whole part out, one entry per pin number.

    The units are set aside: what comes back is every pin the part has, whatever
    unit it was drawn in. A pin number that turns up in two units names a second
    function of the one pin, the way a number re-used within a unit already does.

    Args:
        part (dict): The part (see part.py).

    Returns:
        tuple: A dict mapping each pin number to its pin, and a dict mapping each
              side to what's placed on it, both taken across all the units.
    """
    pins = {}
    layout = {}

    for unit in part.get("units", []):
        unit_pins, unit_layout = flatten_unit(unit)

        for number, pin in unit_pins.items():
            if number in pins:
                pins[number]["alternates"].extend(
                    [(pin["name"], pin["type"], pin["style"])] + pin["alternates"]
                )
                continue
            pins[number] = pin

        for side, placed in unit_layout.items():
            layout.setdefault(side, []).extend(placed)

    return pins, layout


def _compare_units(unit_a, unit_b, positions, strip_spacers):
    """Compare two units of a part, pin by pin."""
    unit = unit_id(unit_a)
    differences = []

    if unit_id(unit_a) != unit_id(unit_b):
        differences.append(
            _difference(
                "names",
                f"unit name: {unit_id(unit_a)!r} != {unit_id(unit_b)!r}",
                unit=unit,
                field="unit name",
                first=unit_id(unit_a),
                second=unit_id(unit_b),
            )
        )

    pins_a, layout_a = flatten_unit(unit_a)
    pins_b, layout_b = flatten_unit(unit_b)

    differences.extend(_compare_pins(pins_a, pins_b, unit, positions))
    differences.extend(
        _compare_layout(unit, unit_a, unit_b, layout_a, layout_b, strip_spacers)
    )

    return differences


def _compare_layout(unit, unit_a, unit_b, layout_a, layout_b, strip_spacers):
    """Compare where the pins of a unit are placed and how its body is drawn.

    Every format says which side a pin is on and what order the pins of a side
    come in, so that much can always be compared. Only an SPD or JPD file pads a
    side with spacers, though, and only a symbol library says where the pins
    actually landed — so a comparison that straddles the two leaves the padding
    out of it.
    """
    differences = []

    for side in SIDE_ORDER:
        side_a = layout_a.get(side, [])
        side_b = layout_b.get(side, [])

        if strip_spacers:
            side_a = [entry for entry in side_a if not entry.startswith("*")]
            side_b = [entry for entry in side_b if not entry.startswith("*")]

        # A side whose pins differ has already been reported, pin by pin; what's
        # left to notice is the same pins placed in a different order.
        if side_a != side_b and sorted(side_a) == sorted(side_b):
            differences.append(
                _difference(
                    "geometry",
                    f"{side} side is placed in a different order: "
                    f"{' '.join(side_a)} != {' '.join(side_b)}",
                    unit=unit,
                    field=f"{side} side order",
                    first=" ".join(side_a),
                    second=" ".join(side_b),
                )
            )

    if "bbox" in unit_a and "bbox" in unit_b:
        if unit_a["bbox"] != unit_b["bbox"]:
            differences.append(
                _difference(
                    "geometry",
                    f"bounding box: {unit_a['bbox']} != {unit_b['bbox']}",
                    unit=unit,
                    field="bounding box",
                    first=unit_a["bbox"],
                    second=unit_b["bbox"],
                )
            )

        graphics_a = set(unit_a.get("graphics", []))
        graphics_b = set(unit_b.get("graphics", []))
        if graphics_a != graphics_b:
            only_a = len(graphics_a - graphics_b)
            only_b = len(graphics_b - graphics_a)
            differences.append(
                _difference(
                    "geometry",
                    f"body shapes differ: {only_a} only in the first part, "
                    f"{only_b} only in the second",
                    unit=unit,
                    field="body shapes",
                    first=f"{only_a} not in the other",
                    second=f"{only_b} not in the other",
                )
            )

    return differences


def compare_parts(part_a, part_b, ignore=()):
    """
    Compare two parts and give the differences between them.

    Args:
        part_a (dict): The first part (see part.py).
        part_b (dict): The second part.
        ignore (iterable, optional): What to leave out of the report: any of
                                    'names', 'properties', 'geometry', and
                                    'units'. Defaults to reporting all of them.

                                    Ignoring 'units' sets the unit boundaries
                                    aside and compares the pins of each part as
                                    one table, so that a part drawn as one unit
                                    and the same part split across several come
                                    out alike. Whether the units line up is then
                                    no longer a question, and nothing about them
                                    is reported.

    Returns:
        list of dict: One entry per difference, each with a 'category', a
             'message', and the 'unit' and 'pin' it concerns, if any.
    """
    ignore = set(ignore)
    unknown = ignore - set(IGNORABLE)
    if unknown:
        raise ValueError(
            f"Can't ignore {', '.join(sorted(unknown))}. "
            f"Ignorable categories are: {', '.join(IGNORABLE)}"
        )

    # A part read from an SPD or JPD file doesn't know where its pins sit, so
    # there's nothing to compare them against in one that does.
    geometry_a, geometry_b = _has_geometry(part_a), _has_geometry(part_b)
    positions = geometry_a and geometry_b
    strip_spacers = geometry_a != geometry_b

    differences = []

    if part_a["name"] != part_b["name"]:
        differences.append(
            _difference(
                "names",
                f"part name: {part_a['name']!r} != {part_b['name']!r}",
                field="part name",
                first=part_a["name"],
                second=part_b["name"],
            )
        )

    differences.extend(_compare_properties(part_a, part_b))

    # With the units set aside, the part is one table of pins: how it's been
    # split up is exactly what's not being asked about, so a pin that moved from
    # one unit to another isn't a difference, and a unit that only one part has
    # can't be one either.
    if "units" in ignore:
        pins_a, _layout_a = flatten_part(part_a)
        pins_b, _layout_b = flatten_part(part_b)
        differences.extend(_compare_pins(pins_a, pins_b, None, positions))

        return [
            difference
            for difference in differences
            if difference["category"] not in ignore
        ]

    pairs, only_a, only_b = _match_units(part_a, part_b)

    for unit in only_a:
        differences.append(
            _difference(
                "pins",
                f"unit '{unit_id(unit)}' is only in the first part",
                unit=unit_id(unit),
                field="missing unit",
                first=unit_id(unit),
            )
        )

    for unit in only_b:
        differences.append(
            _difference(
                "pins",
                f"unit '{unit_id(unit)}' is only in the second part",
                unit=unit_id(unit),
                field="missing unit",
                second=unit_id(unit),
            )
        )

    for unit_a, unit_b in pairs:
        differences.extend(
            _compare_units(unit_a, unit_b, positions, strip_spacers)
        )

    return [
        difference
        for difference in differences
        if difference["category"] not in ignore
    ]


# ===== Comparing libraries =====


def compare_libraries(filenames, ignore=(), mode="normalized",
                      threshold=DEFAULT_THRESHOLD, aliases=None):
    """
    Compare the parts of two or more libraries.

    The first library is the one the others are compared against, so three
    libraries give two comparisons, not three.

    Args:
        filenames (list of str): The libraries to compare: .kicad_sym, .spd, or
                                .jpd files, in any mix.
        ignore (iterable, optional): The categories of difference to leave out.
        mode (str, optional): How to pair up the parts (see match_parts).
        threshold (float, optional): How alike two parts have to be to be paired.
        aliases (dict, optional): Part names paired up by hand.

    Returns:
        dict: The report, with the 'reference' library, and a 'comparisons' entry
             for each of the others holding its matched parts and the parts only
             one of the two libraries has.

    Raises:
        FileNotFoundError: If a library doesn't exist.
        ValueError: If a library can't be read, or fewer than two are given.
    """
    if len(filenames) < 2:
        raise ValueError("Give at least two libraries to compare")

    reference_name = filenames[0]
    reference = load_parts(reference_name, geometry="geometry" not in ignore)

    report = {
        "reference": reference_name,
        "ignored": sorted(ignore),
        "comparisons": [],
    }

    for filename in filenames[1:]:
        parts = load_parts(filename, geometry="geometry" not in ignore)

        pairs, only_a, only_b = match_parts(
            reference, parts, mode=mode, threshold=threshold, aliases=aliases
        )

        matched = []
        for part_a, part_b, score in pairs:
            differences = compare_parts(part_a, part_b, ignore=ignore)
            matched.append(
                {
                    "name": part_a["name"],
                    "other_name": part_b["name"],
                    "score": round(score, 3),
                    "differences": differences,
                }
            )

        report["comparisons"].append(
            {
                "library": filename,
                "matched": sorted(matched, key=lambda part: part["name"]),
                "only_in_reference": sorted(part["name"] for part in only_a),
                "only_in_library": sorted(part["name"] for part in only_b),
            }
        )

    return report


def report_differ(report):
    """Say whether a comparison found any difference at all."""
    return any(
        comparison["only_in_reference"]
        or comparison["only_in_library"]
        or any(part["differences"] for part in comparison["matched"])
        for comparison in report["comparisons"]
    )


def format_report(report, verbose=False):
    """
    Write a comparison out as text.

    Args:
        report (dict): The report from compare_libraries.
        verbose (bool, optional): Name the parts that came out identical, which
                                 are otherwise only counted. Defaults to False.

    Returns:
        str: The report as lines of text.
    """
    lines = []
    reference = report["reference"]

    if report["ignored"]:
        lines.append(f"Ignoring differences in: {', '.join(report['ignored'])}")
        lines.append("")

    for comparison in report["comparisons"]:
        lines.append(f"===== {reference} vs {comparison['library']} =====")

        identical = 0

        for part in comparison["matched"]:
            # A part matched to one of another name is worth pointing out, since
            # the reader gave no name to pair them up by.
            if part["name"] == part["other_name"]:
                heading = f"part '{part['name']}'"
            else:
                heading = (
                    f"part '{part['name']}' ~ '{part['other_name']}' "
                    f"(matched, {part['score']:.0%} alike)"
                )

            if not part["differences"]:
                identical += 1
                if verbose:
                    lines.append(f"{heading}: identical")
                continue

            lines.append(f"{heading}:")

            # Gather the differences under the unit they were found in.
            by_unit = {}
            for difference in part["differences"]:
                by_unit.setdefault(difference["unit"], []).append(difference)

            for message in by_unit.pop(None, []):
                lines.append(f"    {message['message']}")

            for unit, differences in by_unit.items():
                lines.append(f"    unit '{unit}':")
                for difference in differences:
                    lines.append(f"        {difference['message']}")

        for name in comparison["only_in_reference"]:
            lines.append(f"part '{name}' is only in {reference}")

        for name in comparison["only_in_library"]:
            lines.append(f"part '{name}' is only in {comparison['library']}")

        matched = len(comparison["matched"])
        differing = sum(1 for part in comparison["matched"] if part["differences"])
        lines.append("")
        lines.append(
            f"{matched} part{'' if matched == 1 else 's'} matched, "
            f"{identical} identical, {differing} differing; "
            f"{len(comparison['only_in_reference'])} only in {reference}, "
            f"{len(comparison['only_in_library'])} only in {comparison['library']}"
        )
        lines.append("")

    return "\n".join(lines)


# ===== The report as a table =====


def part_label(part):
    """Name a matched part, saying what the other library calls it if it differs."""
    if part["name"] == part["other_name"]:
        return part["name"]

    return f"{part['name']} ~ {part['other_name']}"


def report_rows(comparison, verbose=False):
    """
    Lay a comparison out as the rows of a table.

    Each row is one difference: the part, unit, and pin it concerns, what it's
    about, and what each of the two libraries has to say about it. A part that
    only one of the libraries has gets a row of its own, and one that came out
    identical gets a row only if it's asked about.

    Args:
        comparison (dict): One entry of the 'comparisons' of a report.
        verbose (bool, optional): Give a row to the parts that came out
                                 identical. Defaults to False.

    Returns:
        list of dict: The rows, each with 'part', 'unit', 'pin', 'field',
             'first', 'second', and 'category'.
    """
    rows = []

    for part in comparison["matched"]:
        if not part["differences"]:
            if verbose:
                rows.append(
                    {
                        "part": part_label(part),
                        "unit": "",
                        "pin": "",
                        "field": "identical",
                        "first": "",
                        "second": "",
                        "category": "identical",
                    }
                )
            continue

        for difference in part["differences"]:
            rows.append(
                {
                    "part": part_label(part),
                    "unit": difference["unit"] or "",
                    "pin": difference["pin"] or "",
                    "field": difference["field"] or difference["message"],
                    "first": difference["first"],
                    "second": difference["second"],
                    "category": difference["category"],
                }
            )

    for name in comparison["only_in_reference"]:
        rows.append(
            {
                "part": name,
                "unit": "",
                "pin": "",
                "field": "missing part",
                "first": name,
                "second": ABSENT,
                "category": "pins",
            }
        )

    for name in comparison["only_in_library"]:
        rows.append(
            {
                "part": name,
                "unit": "",
                "pin": "",
                "field": "missing part",
                "first": ABSENT,
                "second": name,
                "category": "pins",
            }
        )

    return rows


def _short(filename):
    """Name a library briefly, for a column heading a path would swamp."""
    return os.path.basename(filename) or filename


def _summary(comparison, reference, short=False):
    """
    Sum a comparison up in a sentence.

    Args:
        comparison (dict): One entry of the 'comparisons' of a report.
        reference (str): The library the others are compared against.
        short (bool, optional): Name the libraries by their filename alone, for
                               somewhere a path has no room to sit. Defaults to
                               naming them as they were given.
    """
    name = _short if short else (lambda filename: filename)

    matched = len(comparison["matched"])
    identical = sum(1 for part in comparison["matched"] if not part["differences"])

    return (
        f"{matched} part{'' if matched == 1 else 's'} matched, "
        f"{identical} identical, {matched - identical} differing; "
        f"{len(comparison['only_in_reference'])} only in {name(reference)}, "
        f"{len(comparison['only_in_library'])} only in {name(comparison['library'])}"
    )


def _import_rich():
    """Bring in the pieces of rich a table needs, saying how to get them if absent."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        raise ImportError(
            "The 'rich' package is needed to draw a rich table. Install it with "
            "'pip install rich', or ask for another format with --format."
        )

    return Console, Table, Text


# The colour each kind of difference is shown in.
CATEGORY_STYLES = {
    "pins": "red",
    "names": "cyan",
    "properties": "yellow",
    "geometry": "blue",
    "identical": "green",
}


def format_rich(report, verbose=False, console=None, expand=False):
    """
    Write a comparison out as a table on the terminal, using rich.

    Args:
        report (dict): The report from compare_libraries.
        verbose (bool, optional): Give a row to the parts that came out
                                 identical. Defaults to False.
        console (rich.console.Console, optional): Where to write. Defaults to a
                                                 console on stdout.
        expand (bool, optional): Stretch the table across the terminal. Defaults
                                to drawing it only as wide as its contents need,
                                which is easier to read down.

    Raises:
        ImportError: If rich isn't installed.
    """
    Console, Table, Text = _import_rich()

    console = console or Console()
    reference = report["reference"]

    if report["ignored"]:
        console.print(
            f"Ignoring differences in: {', '.join(report['ignored'])}", style="dim"
        )

    for comparison in report["comparisons"]:
        # The libraries are named in full on a line of their own, which has the
        # whole terminal to sit on. A title or a column heading is held to the
        # width of the table, and a path there would drag the table out to match.
        console.print(f"\n{reference} vs {comparison['library']}", style="bold")

        table = Table(header_style="bold", expand=expand)
        table.add_column("Part", style="magenta", no_wrap=True)
        table.add_column("Unit", no_wrap=True)
        table.add_column("Pin", no_wrap=True)
        table.add_column("Difference", no_wrap=True)
        table.add_column(_short(reference), overflow="fold")
        table.add_column(_short(comparison["library"]), overflow="fold")

        part = None
        for row in report_rows(comparison, verbose=verbose):
            # A part is named once, on the first of the rows that concern it.
            if row["part"] != part:
                part, first_of_part = row["part"], True
                if table.rows:
                    table.add_section()
            else:
                first_of_part = False

            style = CATEGORY_STYLES.get(row["category"], "")
            table.add_row(
                row["part"] if first_of_part else "",
                str(row["unit"]),
                str(row["pin"]),
                Text(row["field"], style=style),
                Text(row["first"], style="" if row["first"] == ABSENT else "dim"),
                Text(row["second"], style="" if row["second"] == ABSENT else "dim"),
            )

        if not table.rows:
            table.add_row("", "", "", Text("no differences", style="green"), "", "")

        console.print(table)
        console.print(_summary(comparison, reference, short=True), style="dim")


# The page a comparison is written into. The style is inlined so the file stands
# on its own, and it follows the browser's light or dark theme.
HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    color-scheme: light dark;
    --fg: #1a1a1a; --bg: #ffffff; --muted: #6a6a6a;
    --line: #e2e2e2; --head: #f6f6f6; --absent: #b4b4b4;
    --pins: #b3261e; --names: #0b6a75; --properties: #8a6100;
    --geometry: #2a4b8d; --identical: #1f7a3f;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --fg: #e8e8e8; --bg: #1c1c1e; --muted: #9a9a9a;
      --line: #37373a; --head: #262629; --absent: #5c5c60;
      --pins: #ff8a80; --names: #66d9e8; --properties: #ffd479;
      --geometry: #9db8ff; --identical: #7bdba1;
    }}
  }}
  body {{
    margin: 0; padding: 2rem 1.5rem; background: var(--bg); color: var(--fg);
    font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  h1 {{ font-size: 1.35rem; margin: 0 0 1.5rem; }}
  h2 {{
    font-size: 1rem; margin: 2rem 0 .6rem; font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  .ignored, .summary {{ color: var(--muted); font-size: .9rem; }}
  .summary {{ margin-top: .6rem; }}
  .scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
  th, td {{
    text-align: left; padding: .45rem .7rem; border-bottom: 1px solid var(--line);
    vertical-align: top;
  }}
  th {{
    background: var(--head); position: sticky; top: 0; font-weight: 600;
    white-space: nowrap;
  }}
  th.lib {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  tr.part-start td {{ border-top: 2px solid var(--line); }}
  td.part {{ font-weight: 600; white-space: nowrap; }}
  td.unit, td.pin, td.field {{ white-space: nowrap; }}
  td.value {{
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--muted);
  }}
  td.value.absent {{ color: var(--absent); }}
  .field {{ font-weight: 600; }}
  .pins {{ color: var(--pins); }}
  .names {{ color: var(--names); }}
  .properties {{ color: var(--properties); }}
  .geometry {{ color: var(--geometry); }}
  .identical {{ color: var(--identical); }}
  .none {{ color: var(--identical); padding: .6rem 0; }}
</style>
</head>
<body>
<h1>{heading}</h1>
{ignored}
{comparisons}
</body>
</html>
"""


def _escape(text):
    """Make a value safe to put in the page."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def format_html(report, verbose=False):
    """
    Write a comparison out as an HTML page.

    Args:
        report (dict): The report from compare_libraries.
        verbose (bool, optional): Give a row to the parts that came out
                                 identical. Defaults to False.

    Returns:
        str: The page, which stands on its own and needs nothing to view it.
    """
    reference = report["reference"]
    sections = []

    for comparison in report["comparisons"]:
        rows = []
        part = None

        for row in report_rows(comparison, verbose=verbose):
            new_part = row["part"] != part
            part = row["part"]

            cells = [
                f'<td class="part">{_escape(row["part"]) if new_part else ""}</td>',
                f'<td class="unit">{_escape(row["unit"])}</td>',
                f'<td class="pin">{_escape(row["pin"])}</td>',
                f'<td class="field"><span class="field {row["category"]}">'
                f'{_escape(row["field"])}</span></td>',
            ]
            for value in (row["first"], row["second"]):
                absent = " absent" if value == ABSENT else ""
                cells.append(f'<td class="value{absent}">{_escape(value)}</td>')

            rows.append(
                f'<tr class="{"part-start" if new_part else ""}">'
                + "".join(cells)
                + "</tr>"
            )

        if rows:
            # The libraries are named in full in the heading above the table, so
            # their columns carry the filename, with the path a hover away.
            body = (
                '<div class="scroll"><table>\n<thead><tr>'
                "<th>Part</th><th>Unit</th><th>Pin</th><th>Difference</th>"
                f'<th class="lib" title="{_escape(reference)}">'
                f"{_escape(_short(reference))}</th>"
                f'<th class="lib" title="{_escape(comparison["library"])}">'
                f'{_escape(_short(comparison["library"]))}</th>'
                "</tr></thead>\n<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table></div>"
            )
        else:
            body = '<p class="none">No differences.</p>'

        sections.append(
            f"<h2>{_escape(reference)} vs {_escape(comparison['library'])}</h2>\n"
            f"{body}\n"
            f'<p class="summary">{_escape(_summary(comparison, reference))}</p>'
        )

    ignored = ""
    if report["ignored"]:
        ignored = (
            f'<p class="ignored">Ignoring differences in: '
            f"{_escape(', '.join(report['ignored']))}</p>"
        )

    return HTML_PAGE.format(
        title=f"Part differences: {_escape(reference)}",
        heading=f"Part differences from {_escape(reference)}",
        ignored=ignored,
        comparisons="\n".join(sections),
    )


def _default_browser_entry():
    """Find the desktop entry of the default web browser, if there is one to find.

    This is the browser the user has actually chosen, which is not necessarily
    the program registered to open a file of type text/html.
    """
    try:
        name = subprocess.run(
            ["xdg-settings", "get", "default-web-browser"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None

    if not name:
        return None

    # Where a desktop entry may live, snap-installed browsers included.
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    directories = [
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/snapd/desktop/applications",
    ] + [os.path.join(d, "applications") for d in data_dirs.split(os.pathsep)]

    for directory in directories:
        entry = os.path.join(directory, name)
        if os.path.isfile(entry):
            return entry

    return None


def _open_in_browser(url):
    """
    Show a page in the user's browser, saying whether one took it.

    A file:// URL handed to a Linux desktop's generic opener goes to whatever
    program claims the text/html *file type* — and that needn't be a browser at
    all. A mail client that registers itself for HTML will happily swallow the
    page and show nothing, while the opener reports success. So the default *web
    browser* is asked for by name first, and the generic opener is only the
    fallback.

    Args:
        url (str): The page to show.

    Returns:
        bool: Whether a browser was started on it. A browser that starts can
             still fail to draw the page, which nothing here can see.
    """
    # A browser named outright in the environment is the user's own choice, and
    # webbrowser already honours it.
    if sys.platform.startswith("linux") and not os.environ.get("BROWSER"):
        entry = _default_browser_entry()
        if entry and shutil.which("gio"):
            try:
                launched = subprocess.run(["gio", "launch", entry, url], timeout=10)
                if launched.returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                pass  # Fall back to the generic opener below.

    return bool(webbrowser.open(url))


@contextlib.contextmanager
def _quiet():
    """Keep the chatter of a spawned browser off the terminal.

    A browser is started as a child of this process and inherits its output, so
    whatever it has to say on the way up — a Linux one is apt to grumble about
    GTK modules — lands in the middle of the user's shell prompt. A child takes
    the output it's given when it's spawned, so pointing that at nowhere for the
    moment it starts is enough to silence it for good.
    """
    sys.stdout.flush()
    sys.stderr.flush()

    with open(os.devnull, "w") as devnull:
        saved = os.dup(1), os.dup(2)
        try:
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def show_html(report, verbose=False, output=None, browser=True):
    """
    Write the comparison to an HTML file and show it in the browser.

    Args:
        report (dict): The report from compare_libraries.
        verbose (bool, optional): Give a row to the parts that came out identical.
        output (str, optional): Where to write the page. Defaults to a temporary
                               file that the browser is pointed at.
        browser (bool, optional): Open the page once it's written. Defaults to True.

    Returns:
        tuple: The path of the page that was written, and whether a browser was
              opened on it. A machine with no browser to open is not an error —
              the page is written either way — but the caller is told, so that it
              can say where the page went instead of leaving the user waiting for
              a window that isn't coming.
    """
    page = format_html(report, verbose=verbose)

    if output:
        path = os.path.abspath(output)
        with open(path, "w") as f:
            f.write(page)
    else:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", prefix="cmpparts-", delete=False
        ) as f:
            f.write(page)
            path = f.name

    if not browser:
        return path, False

    with _quiet():
        # This says a browser was started, not that it managed to draw the page.
        opened = _open_in_browser(f"file://{path}")

    return path, opened


# ===== Command-Line Interface Function =====


def cmpparts():
    """
    Command-line interface for comparing the parts of two or more libraries.

    Usage:
        cmpparts [-h] [-v] [-g] [-i CATEGORY] [-m MODE] [-t THRESHOLD]
                 [-a OLD=NEW] [-f FORMAT] [-o FILE] [--no-browser] [--verbose]
                 file file [file ...]

    Examples:
        cmpparts old.kicad_sym new.kicad_sym        # Everything, geometry included
        cmpparts -g old.kicad_sym new.kicad_sym     # Only what the part *is*
        cmpparts -g -i units old.kicad_sym new.kicad_sym  # ...never mind the units
        cmpparts parts.spd built.kicad_sym          # Did the symbols come out right?
        cmpparts -m fuzzy vendor.kicad_sym mine.kicad_sym   # Names needn't agree
        cmpparts -m pins -t 0.5 a.kicad_sym b.kicad_sym     # Match on the pinout
        cmpparts -f rich -g a.kicad_sym b.kicad_sym         # A table in the terminal
        cmpparts -f html -g a.kicad_sym b.kicad_sym         # A table in the browser

    Exits:
        0: The libraries hold the same parts.
        1: They differ.
        2: A library couldn't be read, or a format couldn't be written.
    """
    parser = argparse.ArgumentParser(
        description="Compare the parts of two or more libraries and report the "
        "differences. The first library is the one the others are compared "
        "against. Libraries can be .kicad_sym, .spd, or .jpd files, in any mix.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exits with 1 if the libraries differ, 0 if they don't.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="The libraries to compare (.kicad_sym, .spd, or .jpd)",
    )
    parser.add_argument(
        "-g",
        "--ignore-geometry",
        action="store_true",
        help="Ignore where the pins sit, how long they are, and how big the body "
        "is, comparing only what the part is. Short for '--ignore geometry'.",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        action="append",
        choices=IGNORABLE,
        default=[],
        metavar="CATEGORY",
        help=f"Something to leave out of the comparison, given once per entry: "
        f"{', '.join(IGNORABLE)}",
    )
    parser.add_argument(
        "-m",
        "--match",
        choices=MATCH_MODES,
        default="normalized",
        help="How to pair parts up across libraries: 'exact' by name, "
        "'normalized' ignoring case and punctuation (the default), 'fuzzy' by "
        "how alike the names are, or 'pins' by the pinout alone",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"How alike two parts must be for '--match fuzzy' or '--match pins' "
        f"to pair them, from 0 to 1 (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "-a",
        "--alias",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Pair up a part of the first library with a differently named part "
        "of the others, whatever the match mode says. Give it once per pair.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        default="text",
        help="How to write the report: 'text' (the default), 'rich' for a table "
        "in the terminal, 'html' for a table in the browser, or 'json' for "
        "another program to read",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Where to write the report. An HTML report goes to a temporary file "
        "and is opened in the browser unless this says otherwise; the other "
        "formats go to stdout.",
    )
    parser.add_argument(
        "--no-browser",
        dest="browser",
        action="store_false",
        help="Write the HTML report without opening it in the browser",
    )
    parser.add_argument(
        "--wide",
        action="store_true",
        help="Stretch the rich table across the terminal instead of drawing it "
        "only as wide as its contents need",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Name the parts that came out identical, not just the differing ones",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    if len(args.files) < 2:
        parser.error("give at least two libraries to compare")

    ignore = set(args.ignore)
    if args.ignore_geometry:
        ignore.add("geometry")

    aliases = {}
    for alias in args.alias:
        old, separator, new = alias.partition("=")
        if not separator or not old or not new:
            parser.error(f"an alias is written OLD=NEW, not {alias!r}")
        aliases[old] = new

    if not 0 <= args.threshold <= 1:
        parser.error("the threshold runs from 0 to 1")

    try:
        report = compare_libraries(
            args.files,
            ignore=ignore,
            mode=args.match,
            threshold=args.threshold,
            aliases=aliases,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        _write_report(report, args)
    except (ImportError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(1 if report_differ(report) else 0)


def _write_report(report, args):
    """Write the report out in the format the command line asked for."""
    if args.format == "html":
        path, opened = show_html(
            report, verbose=args.verbose, output=args.output, browser=args.browser
        )

        if opened:
            print(f"Wrote {path} and opened it in the browser")
        elif not args.browser:
            print(f"Wrote {path}")
        else:
            # The page is written and perfectly good; there was just nothing here
            # to show it in. Say where it is, so it can be opened by hand. The
            # flush keeps the warning behind the line it's about when the two
            # streams are being written somewhere other than a terminal.
            print(f"Wrote {path}", flush=True)
            print(
                "Warning: couldn't open a browser to show it. Open it yourself "
                f"with:\n    file://{path}",
                file=sys.stderr,
            )
        return

    if args.format == "rich":
        if not args.output:
            format_rich(report, verbose=args.verbose, expand=args.wide)
            return

        Console, _Table, _Text = _import_rich()

        with open(args.output, "w") as f:
            format_rich(
                report,
                verbose=args.verbose,
                console=Console(file=f),
                expand=args.wide,
            )
        print(f"Wrote {args.output}")
        return

    if args.format == "json":
        text = json.dumps(report, indent=2)
    else:
        text = format_report(report, verbose=args.verbose)

    if args.output:
        with open(args.output, "w") as f:
            f.write(text + "\n")
        print(f"Wrote {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    cmpparts()
