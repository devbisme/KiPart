"""Tests for KiCad's 'extends' keyword.

A part written with '(extends "base")' borrows the base part's units and pins
and overrides only its properties. kilib2csv, kilib2spd, and kilib2jpd all copy
the base's units and pins into such a part so it isn't read as an empty one.
"""

import pytest
from simp_sexp import Sexp

from kipart.jpd import symbol_lib_to_jpd
from kipart.kipart import resolve_extends, symbol_lib_file_to_csv_file
from kipart.kilib2spd import symbol_lib_to_spd
from kipart.part import symbol_lib_to_parts


# The orientation of a pin sets the side it lands on: 0 left, 180 right.
_SIDE_X = {0: -7.62, 180: 7.62, 90: 0.0, 270: 0.0}


def a_symbol(name, extends=None, pins=(), unit_name=None, props=None):
    """Build one symbol S-expression, with pins on a single unit or none at all.

    Each pin is (number, type, name, orientation); the orientation sets the side
    it lands on. A symbol given no pins and an 'extends' is shaped like a real
    extending part: properties of its own, and no unit sub-symbols.
    """
    lines = [f'(symbol "{name}"', f'(property "Value" "{name}" (at 0 0 0))']
    for prop_name, prop_value in (props or {}).items():
        lines.append(f'(property "{prop_name}" "{prop_value}" (at 0 0 0))')
    if extends:
        lines.insert(1, f'(extends "{extends}")')
    if pins:
        unit = [f'(symbol "{name}_1_1"']
        if unit_name:
            unit.append(f"(unit_name {unit_name})")
        for number, ptype, pname, orientation in pins:
            unit.append(
                f'(pin {ptype} line (at {_SIDE_X[orientation]} 0 {orientation}) '
                f'(length 3.81) (name "{pname}") (number "{number}"))'
            )
        lines.append(" ".join(unit) + ")")
    return " ".join(lines) + ")"


def a_library(*symbols):
    """Build the text of a library from symbol text.

    Text rather than a parsed Sexp, so a property value with a space in it keeps
    its quotes the way it does in a real file; str(Sexp) doesn't re-quote it, and
    the readers all accept the text directly.
    """
    return (
        '(kicad_symbol_lib (version 20241209) (generator "test") '
        + " ".join(symbols)
        + ")"
    )


def pin_numbers(part):
    """Give every pin number of a part, across all its units and sides."""
    numbers = []
    for unit in part["units"]:
        for side in ("left", "right", "top", "bottom"):
            for pin in unit.get(side, []):
                numbers.extend(pin["numbers"])
    return sorted(numbers)


def parts_by_name(library):
    return {part["name"]: part for part in symbol_lib_to_parts(library)}


class TestResolveExtends:
    """Resolving the keyword at the S-expression level."""

    def test_an_extending_part_gets_the_base_pins(self):
        library = a_library(
            a_symbol("R", pins=[("1", "power_in", "1", 0), ("2", "power_in", "2", 180)]),
            a_symbol("R_Small", extends="R"),
        )
        parts = parts_by_name(library)

        assert pin_numbers(parts["R_Small"]) == ["1", "2"]

    def test_the_extending_part_keeps_its_own_properties(self):
        library = a_library(
            a_symbol("R", pins=[("1", "power_in", "1", 0)]),
            a_symbol("R_Small", extends="R", props={"Description": "small resistor"}),
        )
        parts = parts_by_name(library)

        # Its own property is kept; the base's pins are borrowed.
        assert parts["R_Small"]["name"] == "R_Small"
        assert parts["R_Small"]["properties"]["Description"] == "small resistor"
        assert pin_numbers(parts["R_Small"]) == ["1"]

    def test_the_base_is_left_untouched(self):
        library = a_library(
            a_symbol("R", pins=[("1", "power_in", "1", 0)]),
            a_symbol("R_Small", extends="R"),
        )
        symbols = resolve_extends(
            Sexp(library).search("/kicad_symbol_lib/symbol")
        )
        base = {s[1]: s for s in symbols}["R"]

        # The base still has its one unit, not two.
        assert len(base.search("/symbol/symbol")) == 1

    def test_a_base_defined_after_the_extender_is_found(self):
        library = a_library(
            a_symbol("Child", extends="Base"),
            a_symbol("Base", pins=[("7", "input", "a", 0)]),
        )
        parts = parts_by_name(library)

        assert pin_numbers(parts["Child"]) == ["7"]

    def test_extends_can_chain(self):
        library = a_library(
            a_symbol("C", extends="B"),
            a_symbol("B", extends="A"),
            a_symbol("A", pins=[("9", "input", "a", 0)]),
        )
        parts = parts_by_name(library)

        assert pin_numbers(parts["C"]) == ["9"]
        assert pin_numbers(parts["B"]) == ["9"]

    def test_a_multi_unit_base_keeps_its_units(self):
        multi = (
            '(symbol "M" (property "Value" "M" (at 0 0 0))'
            ' (symbol "M_1_1" (unit_name A)'
            '   (pin input line (at 0 0 0) (length 2) (name "a") (number "1")))'
            ' (symbol "M_2_1" (unit_name B)'
            '   (pin input line (at 0 0 0) (length 2) (name "b") (number "2"))))'
        )
        library = a_library(multi, a_symbol("MChild", extends="M"))
        child = parts_by_name(library)["MChild"]

        assert [unit.get("name") for unit in child["units"]] == ["A", "B"]
        assert pin_numbers(child) == ["1", "2"]

    def test_a_part_with_no_extends_is_untouched(self):
        library = a_library(a_symbol("R", pins=[("1", "power_in", "1", 0)]))
        part = parts_by_name(library)["R"]

        assert pin_numbers(part) == ["1"]

    def test_extending_a_missing_part_is_an_error(self):
        library = a_library(a_symbol("Orphan", extends="Missing"))

        with pytest.raises(ValueError, match="extends 'Missing', which isn't"):
            symbol_lib_to_parts(library)

    def test_a_cycle_of_extends_is_an_error(self):
        library = a_library(
            a_symbol("X", extends="Y"),
            a_symbol("Y", extends="X"),
        )

        with pytest.raises(ValueError, match="cycle"):
            symbol_lib_to_parts(library)


class TestExtendsThroughTheConverters:
    """The three commands that read a library all resolve the keyword."""

    @pytest.fixture
    def library(self, tmp_path):
        """A library with a base part and one that extends it, on disk."""
        text = a_library(
            a_symbol(
                "R",
                pins=[("1", "power_in", "1", 0), ("2", "power_in", "2", 180)],
            ),
            a_symbol(
                "R_Small", extends="R", props={"Description": "small resistor"}
            ),
        )
        path = tmp_path / "extends.kicad_sym"
        path.write_text(text)
        return path

    def test_kilib2spd_writes_the_borrowed_pins(self, library):
        spd = symbol_lib_to_spd(Sexp(library.read_text()))

        # The extending part's SPD has the base's two pins, not an empty body.
        r_small = spd.split("device R_Small")[1]
        assert "1           1" in r_small
        assert "2           2" in r_small

    def test_kilib2jpd_writes_the_borrowed_pins(self, library):
        jpd = symbol_lib_to_jpd(Sexp(library.read_text()))
        r_small = next(p for p in jpd["parts"] if p["name"] == "R_Small")

        assert pin_numbers(r_small) == ["1", "2"]
        assert r_small["properties"]["Description"] == "small resistor"

    def test_kilib2csv_writes_the_borrowed_pins(self, library, tmp_path):
        csv_file = tmp_path / "out.csv"
        symbol_lib_file_to_csv_file(str(library), str(csv_file), overwrite=True)
        text = csv_file.read_text()

        block = text.split("R_Small,")[1]
        # The two borrowed pins are among R_Small's rows.
        assert "1,1,power_in,left" in block
        assert "2,2,power_in,right" in block

    def test_an_extending_part_reads_the_same_as_a_flattened_copy(self, library):
        # What the extending part describes is exactly the base's pinout.
        parts = parts_by_name(Sexp(library.read_text()))
        assert pin_numbers(parts["R_Small"]) == pin_numbers(parts["R"])
