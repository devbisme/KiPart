"""Tests for the neutral part structure and the comparison built on it.

The symbol libraries these need are built from tests/examples/grabbag.spd rather
than read from tests/examples/*.kicad_sym, which are gitignored build products.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kipart import compare_parts as cp
from kipart.compare_parts import (
    ABSENT,
    compare_libraries,
    compare_parts,
    flatten_part,
    format_html,
    format_report,
    format_rich,
    match_parts,
    report_differ,
    report_rows,
    show_html,
)
from kipart.jpd import kilib2jpd, symbol_lib_to_jpd
from kipart.kipart import row_file_to_symbol_lib_file
from kipart.part import flatten_unit, load_parts, unit_id
from kipart.spd2csv import spd_to_csv

EXAMPLES = Path(__file__).parent.parent / "examples"
GRABBAG = EXAMPLES / "grabbag.spd"
CMP_A = EXAMPLES / "cmp_a.spd"
CMP_B = EXAMPLES / "cmp_b.spd"

RT9818 = """\
device rt9818
Manf: Richtek
left
p       vcc     3
*
p       gnd     2
right
*2
i_      rst#    1
"""


def build_lib(spd_file, lib_file, **kwargs):
    """Build a symbol library from an SPD file, the way the CLIs do."""
    csv_file = lib_file.with_suffix(".csv")
    csv_file.write_text(spd_to_csv(Path(spd_file).read_text()))
    row_file_to_symbol_lib_file(str(csv_file), str(lib_file), overwrite=True, **kwargs)
    return lib_file


@pytest.fixture
def grabbag_lib(tmp_path):
    """The grabbag library, built from the SPD file that describes it."""
    return build_lib(GRABBAG, tmp_path / "grabbag.kicad_sym")


@pytest.fixture
def rt9818_spd(tmp_path):
    spd_file = tmp_path / "rt9818.spd"
    spd_file.write_text(RT9818)
    return spd_file


def parts_by_name(filename, **kwargs):
    return {part["name"]: part for part in load_parts(str(filename), **kwargs)}


class TestSymbolToPart:
    """Reading a KiCad symbol into the neutral part structure."""

    def test_part_has_the_shape_jpd_describes(self, grabbag_lib):
        rt9818 = parts_by_name(grabbag_lib, geometry=False)["rt9818"]

        # A one-unit part has a single unit that goes without a name.
        assert list(rt9818) == ["name", "units"]
        assert len(rt9818["units"]) == 1
        assert "name" not in rt9818["units"][0]

        left = rt9818["units"][0]["left"]
        assert [pin["name"] for pin in left] == ["vcc", "gnd"]
        assert left[0] == {
            "name": "vcc",
            "numbers": ["3"],
            "type": "power_in",
            "style": "line",
        }

    def test_pin_numbers_are_names_not_quantities(self, grabbag_lib):
        for part in load_parts(str(grabbag_lib)):
            for unit in part["units"]:
                pins, _layout = flatten_unit(unit)
                assert all(isinstance(number, str) for number in pins)

    def test_units_keep_their_names(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["74hc00"]
        assert [unit_id(unit) for unit in part["units"]] == ["LOGIC", "PWR"]

    def test_pins_of_a_side_come_out_in_the_order_they_are_placed(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["74hc00"]
        logic = part["units"][0]

        # The left pins run down the side, so each one sits below the last.
        ys = [pin["geometry"]["y"] for pin in logic["left"]]
        assert ys == sorted(ys, reverse=True)
        assert [pin["name"] for pin in logic["left"]] == [
            "a1", "b1", "a2", "b2", "a3", "b3",
        ]

    def test_geometry_is_only_kept_when_it_is_asked_for(self, grabbag_lib):
        with_geometry = parts_by_name(grabbag_lib, geometry=True)["rt9818"]
        without = parts_by_name(grabbag_lib, geometry=False)["rt9818"]

        unit = with_geometry["units"][0]
        assert unit["bbox"] and unit["graphics"]
        assert unit["left"][0]["geometry"]["orientation"] == 0

        assert "bbox" not in without["units"][0]
        assert "geometry" not in without["units"][0]["left"][0]

    def test_alternates_come_across(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["nonsense"]
        pins = {}
        for unit in part["units"]:
            pins.update(flatten_unit(unit)[0])

        # SPD gives pin 10 an alternate by naming the pin number a second time.
        assert pins["10"]["name"] == "enable"
        assert [alt[0] for alt in pins["10"]["alternates"]] == ["shutdown"]


class TestLoadParts:
    """Reading a part out of any of the three formats."""

    def test_the_three_formats_describe_the_same_pins(self, grabbag_lib, tmp_path):
        jpd_file = tmp_path / "grabbag.jpd"
        kilib2jpd(str(grabbag_lib), str(jpd_file), overwrite=True)

        def pinout(filename):
            out = {}
            for part in load_parts(str(filename)):
                for unit in part["units"]:
                    pins, _layout = flatten_unit(unit)
                    for number, pin in pins.items():
                        out[(part["name"], unit_id(unit), number)] = (
                            pin["name"], pin["type"], pin["style"], pin["hidden"]
                        )
            return out

        assert pinout(GRABBAG) == pinout(grabbag_lib) == pinout(jpd_file)

    def test_an_unreadable_format_is_refused(self, tmp_path):
        csv_file = tmp_path / "part.csv"
        csv_file.write_text("nothing to see here")
        with pytest.raises(ValueError, match="Don't know how to read"):
            load_parts(str(csv_file))

    def test_a_missing_file_is_refused(self):
        with pytest.raises(FileNotFoundError):
            load_parts("no_such_library.kicad_sym")


class TestComparePartsFindsRealDifferences:
    """Comparing two parts."""

    def test_a_part_matches_itself(self, grabbag_lib):
        for part in load_parts(str(grabbag_lib)):
            assert compare_parts(part, part) == []

    def test_the_library_says_what_the_spd_it_was_built_from_says(self, grabbag_lib):
        from_spd = parts_by_name(GRABBAG)
        from_lib = parts_by_name(grabbag_lib)

        for name, part in from_spd.items():
            assert compare_parts(part, from_lib[name]) == [], name

    def test_a_renamed_pin_is_reported(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["rt9818"]
        changed = json.loads(json.dumps(part))
        changed["units"][0]["left"][0]["name"] = "vdd"

        differences = compare_parts(part, changed)
        assert [d["category"] for d in differences] == ["pins"]
        assert differences[0]["pin"] == "3"
        assert "'vcc' != 'vdd'" in differences[0]["message"]

    def test_a_retyped_pin_is_reported(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["rt9818"]
        changed = json.loads(json.dumps(part))
        changed["units"][0]["left"][0]["type"] = "power_out"

        differences = compare_parts(part, changed)
        assert "type: 'power_in' != 'power_out'" in differences[0]["message"]

    def test_a_missing_pin_is_reported_from_both_sides(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["rt9818"]
        short = json.loads(json.dumps(part))
        del short["units"][0]["left"][0]

        assert "only in the first part" in compare_parts(part, short)[0]["message"]
        assert "only in the second part" in compare_parts(short, part)[0]["message"]

    def test_a_missing_unit_is_reported(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["74hc00"]
        short = json.loads(json.dumps(part))
        del short["units"][1]

        differences = compare_parts(part, short)
        assert differences[0]["category"] == "pins"
        assert "unit 'PWR' is only in the first part" in differences[0]["message"]

    def test_a_property_is_compared_by_its_value(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["74hc04"]
        changed = json.loads(json.dumps(part))
        changed["properties"]["manf"] = "Someone Else"

        differences = compare_parts(part, changed)
        assert differences[0]["category"] == "properties"
        assert "'Texas Instruments' != 'Someone Else'" in differences[0]["message"]

    def test_a_property_name_is_matched_without_regard_to_case(self, grabbag_lib):
        # grabbag.spd writes 'footprint', which kipart capitalizes on the way in.
        from_spd = parts_by_name(GRABBAG)["74hc00"]
        from_lib = parts_by_name(grabbag_lib)["74hc00"]

        assert "footprint" in from_spd["properties"]
        assert "Footprint" in from_lib["properties"]
        assert compare_parts(from_spd, from_lib) == []

    def test_a_unit_whose_name_changed_is_still_compared(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["74hc00"]
        renamed = json.loads(json.dumps(part))
        renamed["units"][0]["name"] = "GATES"
        renamed["units"][0]["left"][0]["name"] = "in1"

        differences = compare_parts(part, renamed)
        categories = [difference["category"] for difference in differences]

        # The unit is recognized by the pins it holds, so the renamed pin inside
        # it is found rather than the whole unit being reported as missing.
        assert "pins" in categories and "names" in categories
        assert any("'a1' != 'in1'" in d["message"] for d in differences)


class TestAlternateComparison:
    """Comparing a pin's alternate functions, the way its own name is compared."""

    # Pin 5 carries a main function plus two alternates. A re-used pin number is
    # how SPD writes an alternate.
    BASE = "device chip\nleft\n    b   PA0     5\n    o   TX      5\n    i   RX      5\n"

    def parts(self, tmp_path, text):
        a = tmp_path / "a.spd"
        b = tmp_path / "b.spd"
        a.write_text(self.BASE)
        b.write_text(text)
        return parts_by_name(a)["chip"], parts_by_name(b)["chip"]

    def test_matching_alternates_are_identical(self, tmp_path):
        part_a, part_b = self.parts(tmp_path, self.BASE)
        assert compare_parts(part_a, part_b) == []

    def test_an_alternate_only_one_pin_has_is_flagged_by_name(self, tmp_path):
        # b renames the RX alternate to SDA: RX is missing from b, SDA from a.
        part_a, part_b = self.parts(
            tmp_path, self.BASE.replace("i   RX      5", "i   SDA     5")
        )
        differences = compare_parts(part_a, part_b)

        by_message = {d["message"]: d for d in differences}
        assert any(
            "alternate 'RX' is only in the first part" in m for m in by_message
        )
        assert any(
            "alternate 'SDA' is only in the second part" in m for m in by_message
        )

        rx = next(d for d in differences if "'RX'" in d["message"])
        assert rx["field"] == "missing alternate"
        assert rx["pin"] == "5"
        assert rx["first"] == "RX" and rx["second"] == ABSENT

    def test_a_shared_alternate_has_its_type_compared(self, tmp_path):
        # TX keeps its name but changes type from output to tri_state.
        part_a, part_b = self.parts(
            tmp_path, self.BASE.replace("o   TX      5", "t   TX      5")
        )
        differences = compare_parts(part_a, part_b)

        assert len(differences) == 1
        diff = differences[0]
        assert diff["field"] == "alternate 'TX' type"
        assert (diff["first"], diff["second"]) == ("output", "tri_state")
        assert "alternate 'TX' type: 'output' != 'tri_state'" in diff["message"]

    def test_a_shared_alternate_has_its_style_compared(self, tmp_path):
        # TX keeps its name and type but gains an inverted style.
        part_a, part_b = self.parts(
            tmp_path, self.BASE.replace("o   TX      5", "o!  TX      5")
        )
        differences = compare_parts(part_a, part_b)

        assert [d["field"] for d in differences] == ["alternate 'TX' style"]
        assert (differences[0]["first"], differences[0]["second"]) == (
            "line",
            "inverted",
        )

    def test_alternates_are_matched_regardless_of_order(self, tmp_path):
        # b lists the same alternates in the other order; still identical.
        reordered = "device chip\nleft\n    b   PA0     5\n    i   RX      5\n    o   TX      5\n"
        part_a, part_b = self.parts(tmp_path, reordered)
        assert compare_parts(part_a, part_b) == []


class TestIgnoringGeometry:
    """The mode that compares what a part is, not how it's drawn."""

    def test_a_symbol_laid_out_differently_is_the_same_part(self, tmp_path):
        lib = build_lib(GRABBAG, tmp_path / "grabbag.kicad_sym")
        pushed = build_lib(GRABBAG, tmp_path / "pushed.kicad_sym", push=0.0)

        report = compare_libraries([str(lib), str(pushed)])
        assert report_differ(report)
        assert all(
            difference["category"] == "geometry"
            for part in report["comparisons"][0]["matched"]
            for difference in part["differences"]
        )

        ignored = compare_libraries([str(lib), str(pushed)], ignore=["geometry"])
        assert not report_differ(ignored)

    def test_a_moved_pin_is_a_geometry_difference(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["rt9818"]
        moved = json.loads(json.dumps(part))
        moved["units"][0]["left"][0]["geometry"]["y"] += 2.54

        differences = compare_parts(part, moved)
        assert [d["category"] for d in differences] == ["geometry"]
        assert "position" in differences[0]["message"]
        assert compare_parts(part, moved, ignore=["geometry"]) == []

    def test_a_pin_that_moved_to_another_side_is_a_geometry_difference(
        self, rt9818_spd, tmp_path
    ):
        moved_spd = tmp_path / "moved.spd"
        moved_spd.write_text(RT9818.replace("p       gnd     2", "").replace(
            "right", "right\np       gnd     2"
        ))

        part = parts_by_name(rt9818_spd)["rt9818"]
        moved = parts_by_name(moved_spd)["rt9818"]

        assert any(
            d["category"] == "geometry" and "side" in d["message"]
            for d in compare_parts(part, moved)
        )
        assert compare_parts(part, moved, ignore=["geometry"]) == []

    def test_reordered_pins_are_noticed_even_without_coordinates(self, rt9818_spd, tmp_path):
        # Two SPD files, neither of which knows where its pins sit, still know
        # what order they come in.
        swapped_spd = tmp_path / "swapped.spd"
        swapped_spd.write_text(
            RT9818.replace("p       vcc     3\n*\np       gnd     2",
                           "p       gnd     2\n*\np       vcc     3")
        )

        part = parts_by_name(rt9818_spd)["rt9818"]
        swapped = parts_by_name(swapped_spd)["rt9818"]

        differences = compare_parts(part, swapped)
        assert [d["category"] for d in differences] == ["geometry"]
        assert "different order" in differences[0]["message"]

    def test_an_unknown_category_cannot_be_ignored(self, grabbag_lib):
        part = parts_by_name(grabbag_lib)["rt9818"]
        with pytest.raises(ValueError, match="Can't ignore pins"):
            compare_parts(part, part, ignore=["pins"])


class TestIgnoringUnits:
    """The mode that compares the pins of a part however they've been split up."""

    SPLIT = """\
device 74hc00
    unit LOGIC
        left
            i       a1      1
            i       b1      2
        right
            o       y1      3
    unit PWR
        top
            p       vcc    14
        bottom
            p       gnd     7
"""

    FLAT = """\
device 74hc00
left
    i       a1      1
    i       b1      2
right
    o       y1      3
top
    p       vcc    14
bottom
    p       gnd     7
"""

    @pytest.fixture
    def parts(self, tmp_path):
        """The same pinout, drawn as two units and as one."""
        split = tmp_path / "split.spd"
        flat = tmp_path / "flat.spd"
        split.write_text(self.SPLIT)
        flat.write_text(self.FLAT)
        return parts_by_name(split)["74hc00"], parts_by_name(flat)["74hc00"]

    def test_the_same_pins_split_up_differently_are_the_same_part(self, parts):
        split, flat = parts

        # The unit split is a difference, until it's said not to be.
        assert compare_parts(split, flat, ignore=["geometry"])
        assert compare_parts(split, flat, ignore=["geometry", "units"]) == []

    def test_a_real_pin_difference_is_still_found(self, parts, tmp_path):
        split, _flat = parts

        changed = tmp_path / "changed.spd"
        changed.write_text(
            self.FLAT.replace("o       y1      3", "t       y1      3")
            .replace("p       gnd     7", "p       vss     7")
            .replace("    i       b1      2\n", "")
        )
        changed = parts_by_name(changed)["74hc00"]

        differences = compare_parts(split, changed, ignore=["geometry", "units"])

        assert [(d["pin"], d["field"]) for d in differences] == [
            ("2", "missing pin"),
            ("3", "type"),
            ("7", "name"),
        ]
        # The pins are no longer in a unit, so none is named.
        assert all(difference["unit"] is None for difference in differences)

    def test_nothing_about_the_units_themselves_is_reported(self, parts):
        split, flat = parts

        # Neither a unit only one part has, nor a unit under another name.
        for difference in compare_parts(split, flat, ignore=["units"]):
            assert difference["field"] not in ("missing unit", "unit name")

    def test_the_pins_of_a_part_are_gathered_from_all_its_units(self, parts):
        split, flat = parts

        pins, _layout = flatten_part(split)
        assert sorted(pins) == ["1", "14", "2", "3", "7"]
        assert flatten_part(flat)[0].keys() == pins.keys()

    def test_a_pin_number_in_two_units_names_a_second_function_of_the_one_pin(
        self, tmp_path
    ):
        # The rule a pin number re-used within a unit already follows.
        spd = tmp_path / "shared.spd"
        spd.write_text(
            "device p\n"
            "    unit A\n"
            "        left\n"
            "            b   PA0     5\n"
            "    unit B\n"
            "        left\n"
            "            i   TX      5\n"
        )

        pins, _layout = flatten_part(parts_by_name(spd)["p"])

        assert list(pins) == ["5"]
        assert pins["5"]["name"] == "PA0"
        assert [alt[0] for alt in pins["5"]["alternates"]] == ["TX"]


class TestMatchingParts:
    """Pairing parts up across libraries whose names don't agree."""

    @staticmethod
    def parts(*names):
        return [{"name": name, "units": []} for name in names]

    def test_exact_matching_pairs_identical_names_only(self):
        pairs, only_a, only_b = match_parts(
            self.parts("rt9818"), self.parts("RT9818"), mode="exact"
        )
        assert not pairs
        assert [part["name"] for part in only_a] == ["rt9818"]
        assert [part["name"] for part in only_b] == ["RT9818"]

    def test_normalized_matching_looks_past_case_and_punctuation(self):
        pairs, only_a, only_b = match_parts(
            self.parts("rt9818"), self.parts("RT-9818"), mode="normalized"
        )
        assert [(a["name"], b["name"]) for a, b, _score in pairs] == [
            ("rt9818", "RT-9818")
        ]
        assert not only_a and not only_b

    def test_fuzzy_matching_pairs_names_that_are_merely_alike(self):
        pairs, only_a, only_b = match_parts(
            self.parts("rt9818"), self.parts("RT9818_C_package"), mode="fuzzy"
        )
        assert [b["name"] for _a, b, _score in pairs] == ["RT9818_C_package"]
        assert not only_a and not only_b

    def test_fuzzy_matching_leaves_unalike_names_alone(self):
        pairs, only_a, only_b = match_parts(
            self.parts("rt9818"), self.parts("74hc00"), mode="fuzzy"
        )
        assert not pairs
        assert only_a and only_b

    def test_a_part_is_paired_with_its_closest_counterpart(self):
        pairs, _only_a, _only_b = match_parts(
            self.parts("opa2333"),
            self.parts("opa2333xdgk", "opa2277"),
            mode="fuzzy",
        )
        assert [b["name"] for _a, b, _score in pairs] == ["opa2333xdgk"]

    def test_pins_matching_recognizes_a_part_by_its_pinout(self, grabbag_lib):
        parts = load_parts(str(grabbag_lib))
        renamed = json.loads(json.dumps(parts))
        for part in renamed:
            part["name"] = f"XYZ-{parts.index(part)}"

        pairs, only_a, only_b = match_parts(parts, renamed, mode="pins")
        assert not only_a and not only_b
        assert all(score == 1.0 for _a, _b, score in pairs)

    def test_an_alias_pairs_parts_up_by_hand(self):
        pairs, only_a, only_b = match_parts(
            self.parts("rt9818"),
            self.parts("XYZ-9999"),
            mode="exact",
            aliases={"rt9818": "XYZ-9999"},
        )
        assert [b["name"] for _a, b, _score in pairs] == ["XYZ-9999"]
        assert not only_a and not only_b


class TestCompareLibraries:
    """Comparing whole libraries."""

    def test_the_formats_agree_with_each_other(self, grabbag_lib, tmp_path):
        jpd_file = tmp_path / "grabbag.jpd"
        kilib2jpd(str(grabbag_lib), str(jpd_file), overwrite=True)

        report = compare_libraries(
            [str(GRABBAG), str(grabbag_lib), str(jpd_file)], ignore=["geometry"]
        )
        assert not report_differ(report)
        assert len(report["comparisons"]) == 2
        assert len(report["comparisons"][0]["matched"]) == 8

    def test_a_part_only_one_library_has_is_reported(self, grabbag_lib, tmp_path):
        one_part = tmp_path / "one.spd"
        one_part.write_text(RT9818)

        report = compare_libraries([str(grabbag_lib), str(one_part)])
        comparison = report["comparisons"][0]

        assert comparison["only_in_library"] == []
        assert "74hc00" in comparison["only_in_reference"]
        assert [part["name"] for part in comparison["matched"]] == ["rt9818"]

    def test_fewer_than_two_libraries_is_refused(self, grabbag_lib):
        with pytest.raises(ValueError, match="at least two"):
            compare_libraries([str(grabbag_lib)])

    def test_the_report_names_the_parts_it_could_not_pair(self, grabbag_lib, tmp_path):
        one_part = tmp_path / "one.spd"
        one_part.write_text(RT9818)

        report = compare_libraries([str(grabbag_lib), str(one_part)])
        text = format_report(report, verbose=True)

        # The rt9818 of this SPD carries a property the library's hasn't got.
        assert "part 'rt9818':" in text
        assert "property 'Manf' ('Richtek') is only in the second part" in text
        assert f"part '74hc00' is only in {grabbag_lib}" in text
        assert "1 part matched, 0 identical, 1 differing" in text

    def test_an_identical_part_is_only_named_when_asked_about(self, grabbag_lib):
        report = compare_libraries([str(GRABBAG), str(grabbag_lib)])

        assert "part 'rt9818': identical" in format_report(report, verbose=True)
        assert "rt9818" not in format_report(report)


class TestKilib2Jpd:
    """Writing a JPD description straight out of a symbol library."""

    def test_the_jpd_identifies_itself(self, grabbag_lib):
        jpd = symbol_lib_to_jpd(Path(grabbag_lib).read_text())
        assert jpd["format"] == "jpd" and jpd["version"] == 1
        assert [part["name"] for part in jpd["parts"]] == [
            "74hc00", "74hc04", "dram", "mixed_types", "nonsense", "opa2277",
            "opa2333", "rt9818",
        ]

    def test_the_jpd_carries_no_geometry(self, grabbag_lib):
        jpd = symbol_lib_to_jpd(Path(grabbag_lib).read_text())
        text = json.dumps(jpd)
        assert "geometry" not in text and "bbox" not in text

    def test_the_jpd_rebuilds_the_library_it_came_from(self, grabbag_lib, tmp_path):
        from kipart.jpd import jpd_to_spd

        jpd_file = tmp_path / "grabbag.jpd"
        kilib2jpd(str(grabbag_lib), str(jpd_file), overwrite=True)

        rebuilt_spd = tmp_path / "rebuilt.spd"
        rebuilt_spd.write_text(jpd_to_spd(json.loads(jpd_file.read_text())))
        rebuilt = build_lib(rebuilt_spd, tmp_path / "rebuilt.kicad_sym")

        report = compare_libraries(
            [str(grabbag_lib), str(rebuilt)], ignore=["geometry"]
        )
        assert not report_differ(report)

    def test_a_library_is_the_only_thing_it_will_read(self, tmp_path, rt9818_spd):
        with pytest.raises(ValueError, match="must be a .kicad_sym file"):
            kilib2jpd(str(rt9818_spd), str(tmp_path / "out.jpd"))


class TestExampleLibraries:
    """The cmp_a / cmp_b pair in tests/examples, which cmpparts is tried out on.

    These check the pair still holds the differences its comments promise, since
    a fixture that has quietly drifted teaches the wrong thing.
    """

    @pytest.fixture
    def libs(self, tmp_path):
        """The pair, built into symbol libraries."""
        return (
            str(build_lib(CMP_A, tmp_path / "cmp_a.kicad_sym")),
            str(build_lib(CMP_B, tmp_path / "cmp_b.kicad_sym")),
        )

    def differences(self, libs, **kwargs):
        """The differences of each part, by the name cmp_a knows it by."""
        report = compare_libraries(list(libs), **kwargs)
        return {
            part["name"]: part["differences"]
            for part in report["comparisons"][0]["matched"]
        }

    def test_the_pair_says_the_same_thing_as_spd_as_it_does_as_a_library(self, libs):
        # cmpparts reads either format, and should say the same either way.
        def messages(files):
            report = compare_libraries(
                list(files), ignore=["geometry"], mode="fuzzy"
            )
            return sorted(
                difference["message"]
                for part in report["comparisons"][0]["matched"]
                for difference in part["differences"]
            )

        assert messages([str(CMP_A), str(CMP_B)]) == messages(libs)

    def test_lm1117_is_identical(self, libs):
        assert self.differences(libs)["lm1117"] == []

    def test_tl072_differs_only_in_geometry(self, libs):
        differences = self.differences(libs)["tl072"]

        assert differences
        assert {d["category"] for d in differences} == {"geometry"}
        assert any("different order" in d["message"] for d in differences)

        # ...so ignoring the geometry makes it identical.
        assert self.differences(libs, ignore=["geometry"])["tl072"] == []

    def test_74hc00_has_a_dropped_pin_and_a_retyped_pin(self, libs):
        differences = self.differences(libs, ignore=["geometry"])["74hc00"]

        assert [(d["pin"], d["field"]) for d in differences] == [
            ("5", "missing pin"),
            ("6", "type"),
        ]
        assert differences[0]["first"] == "b2" and differences[0]["second"] == ABSENT
        assert (differences[1]["first"], differences[1]["second"]) == (
            "output",
            "tri_state",
        )

    def test_rt9818_is_renamed_and_needs_fuzzy_matching_to_pair_up(self, libs):
        # The default match mode won't pair 'rt9818' with 'RT9818-33'...
        report = compare_libraries(list(libs), ignore=["geometry"])
        comparison = report["comparisons"][0]
        assert "rt9818" in comparison["only_in_reference"]
        assert "RT9818-33" in comparison["only_in_library"]

        # ...but fuzzy matching does, and then finds what changed inside it.
        differences = self.differences(libs, ignore=["geometry"], mode="fuzzy")
        fields = {d["field"] for d in differences["rt9818"]}
        assert fields == {"part name", "property 'Manf'", "name", "missing alternate"}
        assert {d["category"] for d in differences["rt9818"]} == {
            "names",
            "properties",
            "pins",
        }

    def test_each_library_has_a_part_the_other_hasnt(self, libs):
        report = compare_libraries(list(libs), ignore=["geometry"], mode="fuzzy")
        comparison = report["comparisons"][0]

        assert comparison["only_in_reference"] == ["dac8551"]
        assert comparison["only_in_library"] == ["lm358"]


class TestOpeningTheBrowser:
    """Which program the page is handed to.

    A file:// URL given to a Linux desktop's generic opener goes to whatever
    claims the text/html *file type*, which needn't be a browser: a mail client
    that registers itself for HTML swallows the page and shows nothing, while the
    opener reports success. So the default *web browser* is asked for by name.
    """

    @pytest.fixture
    def spies(self, monkeypatch):
        """Stand in for the machine's browser, and record what gets called."""
        calls = {"gio": [], "webbrowser": []}

        monkeypatch.setattr(cp.sys, "platform", "linux")
        monkeypatch.delenv("BROWSER", raising=False)
        monkeypatch.setattr(cp.shutil, "which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(
            cp,
            "_default_browser_entry",
            lambda: "/usr/share/applications/brave-browser.desktop",
        )
        monkeypatch.setattr(
            cp.webbrowser,
            "open",
            lambda url: calls["webbrowser"].append(url) or True,
        )

        def gio(command, **kwargs):
            calls["gio"].append(command)
            return subprocess.CompletedProcess(command, calls["returncode"])

        calls["returncode"] = 0
        monkeypatch.setattr(cp.subprocess, "run", gio)

        return calls

    def test_the_default_browser_is_asked_for_by_name(self, spies):
        assert cp._open_in_browser("file:///tmp/page.html")

        assert spies["gio"] == [
            [
                "gio",
                "launch",
                "/usr/share/applications/brave-browser.desktop",
                "file:///tmp/page.html",
            ]
        ]
        # The generic opener, which is the one that goes astray, is left alone.
        assert spies["webbrowser"] == []

    def test_the_generic_opener_is_the_fallback(self, spies):
        spies["returncode"] = 1  # The browser couldn't be launched by name.

        assert cp._open_in_browser("file:///tmp/page.html")
        assert spies["webbrowser"] == ["file:///tmp/page.html"]

    def test_a_browser_named_in_the_environment_wins(self, spies, monkeypatch):
        monkeypatch.setenv("BROWSER", "my-browser")

        assert cp._open_in_browser("file:///tmp/page.html")

        # webbrowser already honours BROWSER, so it's left to get on with it.
        assert spies["gio"] == []
        assert spies["webbrowser"] == ["file:///tmp/page.html"]

    def test_nothing_to_open_with_is_reported(self, spies, monkeypatch):
        monkeypatch.setattr(cp, "_default_browser_entry", lambda: None)
        monkeypatch.setattr(cp.webbrowser, "open", lambda url: False)

        assert not cp._open_in_browser("file:///tmp/page.html")

    def test_a_desktop_without_xdg_settings_is_survived(self, monkeypatch):
        def missing(command, **kwargs):
            raise FileNotFoundError(command[0])

        monkeypatch.setattr(cp.subprocess, "run", missing)
        assert cp._default_browser_entry() is None


class TestCmppartsCli:
    """The command line."""

    @staticmethod
    def run(*args, env=None):
        return subprocess.run(
            [sys.executable, "-m", "kipart.compare_parts", *args],
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )

    @staticmethod
    def no_browser_anywhere():
        """An environment with no browser for webbrowser to find.

        Setting BROWSER to something that isn't there isn't enough: webbrowser
        keeps its usual fallbacks behind it and would open one of those. It finds
        them on the PATH, and the graphical ones only when there's a display, so
        taking away both leaves it nothing to open.
        """
        return {"PATH": "", "BROWSER": "", "DISPLAY": "", "WAYLAND_DISPLAY": ""}

    def test_matching_libraries_exit_zero(self, grabbag_lib):
        result = self.run(str(GRABBAG), str(grabbag_lib))
        assert result.returncode == 0
        assert "8 parts matched, 8 identical" in result.stdout

    def test_differing_libraries_exit_one(self, grabbag_lib, rt9818_spd):
        result = self.run(str(grabbag_lib), str(rt9818_spd))
        assert result.returncode == 1
        assert "only in" in result.stdout

    def test_an_unreadable_library_exits_two(self, grabbag_lib):
        result = self.run(str(grabbag_lib), "no_such_library.kicad_sym")
        assert result.returncode == 2
        assert "does not exist" in result.stderr

    def test_one_library_is_refused(self, grabbag_lib):
        result = self.run(str(grabbag_lib))
        assert result.returncode == 2
        assert "at least two" in result.stderr

    def test_ignoring_geometry(self, tmp_path):
        lib = build_lib(GRABBAG, tmp_path / "grabbag.kicad_sym")
        pushed = build_lib(GRABBAG, tmp_path / "pushed.kicad_sym", push=0.0)

        assert self.run(str(lib), str(pushed)).returncode == 1
        assert self.run("-g", str(lib), str(pushed)).returncode == 0

    def test_a_filename_after_a_flag_is_still_a_filename(self, grabbag_lib):
        # An option that took a list of values would swallow the filenames here.
        result = self.run("-i", "geometry", str(GRABBAG), str(grabbag_lib))
        assert result.returncode == 0, result.stderr

    def test_an_alias_is_written_old_equals_new(self, grabbag_lib):
        result = self.run("-a", "rt9818", str(GRABBAG), str(grabbag_lib))
        assert result.returncode == 2
        assert "OLD=NEW" in result.stderr

    def test_the_json_report_carries_the_differences(self, grabbag_lib, rt9818_spd):
        result = self.run("-f", "json", "-g", str(rt9818_spd), str(grabbag_lib))
        report = json.loads(result.stdout)

        assert report["ignored"] == ["geometry"]
        comparison = report["comparisons"][0]
        assert [part["name"] for part in comparison["matched"]] == ["rt9818"]
        assert "74hc00" in comparison["only_in_library"]

    def test_the_rich_table_reaches_the_terminal(self, grabbag_lib, rt9818_spd):
        result = self.run("-f", "rich", "-g", str(rt9818_spd), str(grabbag_lib))

        assert result.returncode == 1
        assert "Difference" in result.stdout and "Part" in result.stdout
        assert "property 'Manf'" in result.stdout
        assert "1 part matched" in result.stdout

    def test_the_html_report_is_written_and_the_browser_left_alone(
        self, grabbag_lib, rt9818_spd, tmp_path
    ):
        page = tmp_path / "diff.html"
        result = self.run(
            "-f", "html", "-g", "--no-browser", "-o", str(page),
            str(rt9818_spd), str(grabbag_lib),
        )

        assert result.returncode == 1
        assert "opened it in the browser" not in result.stdout
        assert "<table>" in page.read_text()

    def test_an_unknown_format_is_refused(self, grabbag_lib, rt9818_spd):
        result = self.run("-f", "yaml", str(rt9818_spd), str(grabbag_lib))
        assert result.returncode == 2
        assert "invalid choice" in result.stderr

    def test_a_browser_that_will_not_open_is_owned_up_to(self, grabbag_lib, rt9818_spd):
        result = self.run(
            "-f", "html", str(rt9818_spd), str(grabbag_lib),
            env=self.no_browser_anywhere(),
        )

        assert "opened it in the browser" not in result.stdout
        assert "couldn't open a browser" in result.stderr

        # The page it wrote is named on stdout, and is there to be opened by hand.
        path = Path(result.stdout.split()[1])
        assert path.read_text().startswith("<!doctype html>")
        assert f"file://{path}" in result.stderr
        path.unlink()

    def test_the_browser_does_not_chatter_into_the_terminal(
        self, grabbag_lib, rt9818_spd, tmp_path, monkeypatch
    ):
        # A browser is spawned as a child of ours and would otherwise write its
        # startup grumbles (GTK modules, and the like) all over the user's shell.
        browser = tmp_path / "noisy-browser.sh"
        browser.write_text(
            '#!/bin/sh\n'
            'echo "Gtk-Message: Failed to load module" >&2\n'
            'echo "browser stdout noise"\n'
        )
        browser.chmod(0o755)
        monkeypatch.setenv("BROWSER", str(browser))

        result = self.run("-f", "html", str(rt9818_spd), str(grabbag_lib))

        assert "opened it in the browser" in result.stdout
        assert "noise" not in result.stdout
        assert "Gtk-Message" not in result.stderr and result.stderr == ""


class TestTabularFormats:
    """The report as a table, in the terminal and in the browser."""

    @pytest.fixture
    def report(self, grabbag_lib, rt9818_spd):
        return compare_libraries(
            [str(rt9818_spd), str(grabbag_lib)], ignore=["geometry"]
        )

    def test_a_row_says_what_each_library_has_to_say(self, report):
        rows = report_rows(report["comparisons"][0])
        by_field = {row["field"]: row for row in rows}

        # The SPD's rt9818 carries a property the library's hasn't got.
        assert by_field["property 'Manf'"]["first"] == "Richtek"
        assert by_field["property 'Manf'"]["second"] == ABSENT
        assert by_field["property 'Manf'"]["part"] == "rt9818"
        assert by_field["property 'Manf'"]["category"] == "properties"

    def test_a_part_only_one_library_has_gets_a_row(self, report):
        rows = report_rows(report["comparisons"][0])
        missing = [row for row in rows if row["part"] == "74hc00"]

        assert len(missing) == 1
        assert missing[0]["field"] == "missing part"
        assert missing[0]["first"] == ABSENT
        assert missing[0]["second"] == "74hc00"

    def test_identical_parts_get_a_row_only_when_asked_about(self, grabbag_lib):
        report = compare_libraries([str(GRABBAG), str(grabbag_lib)])
        comparison = report["comparisons"][0]

        assert report_rows(comparison) == []
        rows = report_rows(comparison, verbose=True)
        assert len(rows) == 8
        assert {row["field"] for row in rows} == {"identical"}

    def test_a_renamed_part_is_labelled_with_both_names(self, grabbag_lib, tmp_path):
        renamed = tmp_path / "renamed.spd"
        renamed.write_text(RT9818.replace("device rt9818", "device RT9818-33"))

        report = compare_libraries(
            [str(grabbag_lib), str(renamed)], ignore=["geometry"], mode="fuzzy"
        )
        rows = report_rows(report["comparisons"][0])

        assert any(row["part"] == "rt9818 ~ RT9818-33" for row in rows)

    def test_the_rich_table_holds_the_differences(self, report):
        text = self.rich_text(report, width=200)

        assert "rt9818" in text and "property 'Manf'" in text and "Richtek" in text
        assert "1 part matched, 0 identical, 1 differing" in text

    @staticmethod
    def rich_text(report, width=200, **kwargs):
        from io import StringIO

        from rich.console import Console

        output = StringIO()
        format_rich(report, console=Console(file=output, width=width), **kwargs)
        return output.getvalue()

    @staticmethod
    def table_width(text):
        """How wide the drawn table is, leaving aside what's printed around it."""
        rules = [line for line in text.splitlines() if line.startswith("┏")]
        return len(rules[0].rstrip())

    def test_the_table_is_no_wider_than_its_contents_need(self, report):
        # Left to itself the table fits its contents, well short of the terminal.
        assert self.table_width(self.rich_text(report, width=200)) < 100

        # --wide is what stretches it across the terminal.
        assert self.table_width(self.rich_text(report, width=200, expand=True)) == 200

    def test_a_library_column_is_headed_by_its_filename_not_its_path(self, report):
        lines = self.rich_text(report, width=200).splitlines()

        header = next(line for line in lines if "Difference" in line)
        assert "grabbag.kicad_sym" in header
        # A path in the heading would set the width of the whole table, so the
        # heading and the summary go without one...
        assert "/" not in header
        assert not any("/" in line for line in lines if "part matched" in line)

        # ...and the line above the table, which has the whole terminal to sit
        # on, says which libraries these are.
        assert any("/" in line and " vs " in line for line in lines)

    def test_the_html_page_stands_on_its_own(self, report):
        page = format_html(report)

        assert page.startswith("<!doctype html>")
        assert "<style>" in page
        # Nothing to fetch: no scripts, no stylesheets, no images.
        assert "http://" not in page and "https://" not in page
        assert "<script" not in page

    def test_the_html_page_holds_the_differences(self, report):
        page = format_html(report)

        assert "<th>Part</th>" in page
        assert "property &#x27;Manf&#x27;" in page or "property 'Manf'" in page
        assert "Richtek" in page
        assert "1 part matched, 0 identical, 1 differing" in page

    def test_a_value_that_looks_like_markup_is_escaped(self, grabbag_lib, tmp_path):
        # A property value is any string, and could hold anything at all.
        sneaky = tmp_path / "sneaky.spd"
        sneaky.write_text(RT9818.replace("Richtek", "<script>alert(1)</script>"))

        report = compare_libraries([str(grabbag_lib), str(sneaky)])
        page = format_html(report)

        assert "<script>" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page

    def test_showing_the_page_writes_it_where_it_is_told(self, report, tmp_path):
        page = tmp_path / "diff.html"
        path, opened = show_html(report, output=str(page), browser=False)

        assert path == str(page)
        assert not opened
        assert page.read_text().startswith("<!doctype html>")

    def test_showing_the_page_opens_the_browser(self, report, monkeypatch):
        urls = []
        monkeypatch.setattr(
            cp, "_open_in_browser", lambda url: urls.append(url) or True
        )

        path, opened = show_html(report)

        assert opened
        assert urls == [f"file://{path}"]
        assert Path(path).read_text().startswith("<!doctype html>")
        Path(path).unlink()

    def test_a_browser_that_will_not_open_is_owned_up_to(self, report, monkeypatch):
        # Nothing took the page, which is easy to throw away and claim success.
        monkeypatch.setattr(cp, "_open_in_browser", lambda url: False)

        path, opened = show_html(report)

        assert not opened
        # The page is still written, so it can be opened by hand.
        assert Path(path).read_text().startswith("<!doctype html>")
        Path(path).unlink()
