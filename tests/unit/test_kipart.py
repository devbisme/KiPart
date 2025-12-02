import pytest
import pandas as pd
import csv
import os
import subprocess
from simp_sexp import Sexp

from kipart.kipart import (
    text_width,
    parse_mixed_string,
    extract_symbols_from_lib,
    symbol_to_csv_rows,
    read_row_file,
    read_symbol_rows,
    rows_to_symbol,
    add_quotes,
    rmv_quotes,
    row_file_to_symbol_lib_file,
    symbol_lib_file_to_csv_file,
    create_empty_symbol_lib,
    merge_symbol_libs,
)
from kipart.random_symbol import create_random_symbol_lib
from kipart.compare_symbols import symbols_are_equal, symbol_libs_are_equal


def test_get_text_bounding_box():
    """Test text bounding box calculation."""
    # Test default font size (1.27 mm)
    width = text_width("TEST")
    assert width == pytest.approx(4 * 1.27 * 0.9)  # 4 chars * 0.9 * font_size

    # Test custom font size
    width = text_width("ABC", font_size=2.0)
    assert width == pytest.approx(3 * 2.0 * 0.9)


def test_parse_mixed_string():
    """Test mixed alphanumeric string parsing for sorting."""
    # Test numeric and alphanumeric strings
    assert parse_mixed_string("10") == (chr(0), 10)
    assert parse_mixed_string("A1") == ("A", 1)
    assert parse_mixed_string("PIN10B") == ("PIN", 10, "B")
    assert parse_mixed_string("*") == (chr(0x10FFFF), float("inf"))

    # Test sorting behavior
    strings = ["A1", "A10", "B2", "10"]
    sorted_strings = sorted(strings, key=parse_mixed_string)
    assert sorted_strings == ["10", "A1", "A10", "B2"]


def test_extract_symbols_from_lib(tmp_path):
    """Test extracting parts from a KiCad symbol library."""
    # Create a sample .kicad_sym file
    content = """
    (kicad_symbol_lib
      (version 20241209)
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" (rectangle))
      )
      (symbol "part2"
        (property "Reference" "U")
        (symbol "part2_1_1" (rectangle))
      )
    )
    """
    file_path = tmp_path / "test.kicad_sym"
    with open(file_path, "w") as f:
        f.write(content)

    with open(file_path) as f:
        parts = extract_symbols_from_lib(f.read())

    assert len(parts) == 2
    assert parts[0][0] == "symbol" and parts[0][1] == "part1"
    assert parts[1][0] == "symbol" and parts[1][1] == "part2"

    # Test invalid S-expression
    parts = extract_symbols_from_lib(["(invalid)"])
    assert parts == []


def test_symbol_to_csv_rows():
    """Test converting a symbol S-expression to CSV rows."""
    sexp = """
    (symbol "my_part"
      (property "Reference" "U")
      (property "Value" "my_part")
      (symbol "my_part_1_1"
        (rectangle
          (start 10.16 6.35)
          (end 20.32 -6.35)
        )
        (pin input line
          (at 5.08 0.00 0)
          (length 5.08)
          (name "P1")
          (number "1")
        )
        (pin output line
          (at 25.40 0.00 180)
          (length 5.08)
          (name "P2" (effects (hidden yes)))
          (number "2" (effects (hidden yes)))
        )
      )
    )
    """
    expected_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["Value:", "my_part"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "P1", "input", "left", "1", "line", "no"],
        ["2", "P2", "output", "right", "1", "line", "yes"],
    ]
    rows = symbol_to_csv_rows(Sexp(sexp))
    assert rows == expected_rows


def test_open_row_file(tmp_path):
    """Test reading CSV and Excel files."""
    # Test CSV
    csv_content = "my_part,\nReference:,U\npin,name\n1,P1"
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)

    rows = read_row_file(csv_path)
    assert rows == [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]

    # Test Excel
    df = pd.DataFrame(
        [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]
    )
    excel_path = tmp_path / "test.xlsx"
    df.to_excel(excel_path, index=False, header=False)

    rows = read_row_file(excel_path)
    assert rows == [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]

    # Test invalid extension
    with pytest.raises(ValueError, match="Unsupported file extension"):
        read_row_file(tmp_path / "test.txt")


def test_read_symbol_rows():
    """Test grouping CSV rows into symbols."""
    rows = [
        ["part1", ""],
        ["Reference:", "U"],
        ["pin", "name"],
        ["1", "P1"],
        [],
        ["part2", ""],
        ["pin", "name"],
        ["2", "P2"],
    ]
    symbols = read_symbol_rows(rows)
    assert len(symbols) == 2
    assert symbols[0] == [
        ["part1", ""],
        ["Reference:", "U"],
        ["pin", "name"],
        ["1", "P1"],
    ]
    assert symbols[1] == [["part2", ""], ["pin", "name"], ["2", "P2"]]

    # Test empty input
    with pytest.raises(ValueError, match="No valid symbols found"):
        read_symbol_rows([])


def test_rows_to_symbol():
    """Test generating a symbol S-expression from CSV rows."""
    symbol_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "P1", "input", "left"],
        ["2", "P2", "output", "right"],
    ]
    symbol = rows_to_symbol(symbol_rows, sort_by="num")
    add_quotes(symbol)
    sexp_str = str(symbol)
    assert '(symbol "my_part"' in sexp_str
    assert '(property "Reference" "U"' in sexp_str
    assert "(pin input line" in sexp_str
    assert "(pin output line" in sexp_str
    assert '(name "P1"' in sexp_str
    assert '(name "P2"' in sexp_str

    # Test invalid part name
    with pytest.raises(ValueError, match="Invalid part name"):
        rows_to_symbol([["", ""], ["pin", "name"], ["1", "P1"]])


def test_row_file_to_symbol_lib_file(tmp_path):
    """Test generating a KiCad symbol library from a CSV file."""
    # Create a sample CSV file
    csv_content = """my_part,
Reference:,U
Value:,my_part
pin,name,type,side
1,P1,input,left
2,P2,output,right
"""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)

    output_path = tmp_path / "output.kicad_sym"
    result = row_file_to_symbol_lib_file(csv_path, symbol_lib_file=output_path)

    assert os.path.exists(result)
    with open(result) as f:
        content = f.read()
        assert "(kicad_symbol_lib" in content
        assert '(symbol "my_part"' in content
        assert "(pin input line" in content
        assert "(pin output line" in content

    # Test overwrite protection
    with pytest.raises(ValueError, match="Output file.*already exists"):
        row_file_to_symbol_lib_file(
            csv_path, symbol_lib_file=output_path, overwrite=False
        )


def test_kipart_cli(tmp_path):
    """Test the kipart.py command-line interface."""
    # Create a sample CSV file
    csv_content = """my_part,
Reference:,U
pin,name,type,side
1,P1,input,left
"""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)

    output_path = tmp_path / "output.kicad_sym"

    # Test successful run
    result = subprocess.run(
        ["kipart", str(csv_path), "-o", str(output_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert f"Created symbol library {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        ["kipart", str(tmp_path / "invalid.txt")], capture_output=True, text=True
    )
    assert "Error: Failed while processing" in result.stdout
    assert result.returncode != 0  # Script continues after error


def test_library_to_csv(tmp_path):
    """Test converting a KiCad symbol library to CSV."""
    # Create a sample .kicad_sym file
    kicad_sym_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kipart")
      (symbol "my_part"
        (property "Reference" "U")
        (property "Value" "my_part")
        (symbol "my_part_1_1"
          (rectangle
            (start 10.16 6.35)
            (end 20.32 -6.35)
          )
          (pin input line
            (at 5.08 0.00 0)
            (length 5.08)
            (name "P1")
            (number "1")
          )
        )
      )
      (symbol "part2"
        (property "Reference" "U")
        (property "Value" "part2")
        (symbol "part2_1_1"
          (rectangle
            (start 10.16 6.35)
            (end 20.32 -6.35)
          )
          (pin output line
            (at 5.08 0.00 0)
            (length 5.08)
            (name "OUT")
            (number "1")
          )
        )
      )
    )
    """
    kicad_sym_path = tmp_path / "test.kicad_sym"
    with open(kicad_sym_path, "w") as f:
        f.write(kicad_sym_content)

    output_path = tmp_path / "output.csv"
    result = symbol_lib_file_to_csv_file(kicad_sym_path, csv_file=output_path)

    assert os.path.exists(result)
    expected_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["Value:", "my_part"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "P1", "input", "left", "1", "line", "no"],
        [],
        ["part2", ""],
        ["Reference:", "U"],
        ["Value:", "part2"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "OUT", "output", "left", "1", "line", "no"],
    ]
    with open(output_path) as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert rows == expected_rows

    # Test invalid file
    with pytest.raises(FileNotFoundError):
        symbol_lib_file_to_csv_file(tmp_path / "nonexistent.kicad_sym")

    # Test overwrite protection
    with pytest.raises(ValueError, match="Output file.*already exists"):
        symbol_lib_file_to_csv_file(
            kicad_sym_path, csv_file=output_path, overwrite=False
        )


def test_kilib2csv_cli(tmp_path):
    """Test the kilib2csv.py command-line interface."""
    # Create a sample .kicad_sym file
    kicad_sym_content = """
    (kicad_symbol_lib
      (version 20241209)
      (symbol "my_part"
        (property "Reference" "U")
        (symbol "my_part_1_1"
          (rectangle
            (start 10.16 6.35)
            (end 20.32 -6.35)
          )
          (pin input line
            (at 5.08 0.00 0)
            (length 5.08)
            (name "P1")
            (number "1")
          )
        )
      )
    )
    """
    kicad_sym_path = tmp_path / "test.kicad_sym"
    with open(kicad_sym_path, "w") as f:
        f.write(kicad_sym_content)

    output_path = tmp_path / "output.csv"

    # Test successful run
    result = subprocess.run(
        ["kilib2csv", str(kicad_sym_path), "-o", str(output_path)],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    assert f"Generated {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        ["kilib2csv", str(tmp_path / "invalid.txt")], capture_output=True, text=True
    )
    assert result.returncode != 0  # Script continues after error
    assert "Error processing" in result.stdout


def test_create_empty_symbol_lib():
    """Test creation of an empty symbol library."""
    lib = create_empty_symbol_lib()

    # Check that it's a valid Sexp with the expected structure
    assert isinstance(lib, Sexp)
    assert lib[0] == "kicad_symbol_lib"

    # Check that it has the required attributes
    has_version = False
    has_generator = False
    has_generator_version = False

    for item in lib:
        if isinstance(item, list):
            if item[0] == "version":
                has_version = True
                assert item[1] == "20241209"
            elif item[0] == "generator":
                has_generator = True
                assert item[1] == "kicad_symbol_editor"
            elif item[0] == "generator_version":
                has_generator_version = True
                assert item[1] == "8.0"

    assert has_version
    assert has_generator
    assert has_generator_version

    # Check that it has no symbols yet
    symbols = extract_symbols_from_lib(lib)
    assert len(symbols) == 0


def test_merge_symbol_libs(tmp_path):
    """Test merging two symbol libraries."""
    # Create two libraries with some symbols
    lib1_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (generator_version 8.0)
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" (rectangle))
      )
      (symbol "common_part"
        (property "Reference" "U")
        (symbol "common_part_1_1" (rectangle))
      )
    )
    """

    lib2_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (generator_version 8.0)
      (symbol "part2"
        (property "Reference" "U")
        (symbol "part2_1_1" (rectangle))
      )
      (symbol "common_part"
        (property "Reference" "X")
        (symbol "common_part_1_1" (rectangle))
      )
    )
    """

    lib1 = Sexp(lib1_content)
    lib2 = Sexp(lib2_content)

    # Test merge with overwrite=False (should fail due to duplicate)
    with pytest.raises(ValueError, match="Cannot merge libraries.*common_part"):
        merged = merge_symbol_libs(lib1, lib2, overwrite=False)

    # Test merge with overwrite=True
    merged = merge_symbol_libs(lib1, lib2, overwrite=True)

    # Check that merged library has all symbols
    symbols = extract_symbols_from_lib(merged)
    symbol_names = [s[1] for s in symbols]

    assert len(symbols) == 3
    assert "part1" in symbol_names
    assert "part2" in symbol_names
    assert "common_part" in symbol_names

    # Verify that common_part from lib2 was used
    for symbol in symbols:
        if symbol[1] == "common_part":
            # Find the Reference property value
            for item in symbol:
                if (
                    isinstance(item, list)
                    and item[0] == "property"
                    and item[1] == "Reference"
                ):
                    assert item[2] == "X"  # Should be from lib2, not lib1


def test_scrunch_option():
    """Test the scrunch option for compressing pins under top/bottom rows."""
    symbol_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "P1", "input", "left"],
        ["2", "P2", "output", "right"],
        ["3", "P3", "input", "top"],
        ["4", "P4", "output", "bottom"],
    ]

    # Generate symbol with scrunch=False (default)
    normal_symbol = rows_to_symbol(symbol_rows, sort_by="num")

    # Generate symbol with scrunch=True
    scrunched_symbol = rows_to_symbol(symbol_rows, sort_by="num", scrunch=True)

    # Convert to strings for easier comparison
    normal_str = str(normal_symbol)
    scrunched_str = str(scrunched_symbol)

    # Both should have all pins
    assert normal_str.count("(pin ") == 4
    assert scrunched_str.count("(pin ") == 4

    # Extract the rectangle dimensions
    # In normal layout, left/right pins are side by side with top/bottom
    # In scrunched layout, left/right pins are underneath top/bottom

    # Helper function to extract rectangle coordinates from symbol string
    def get_rectangle_coords(symbol_str):
        import re

        rect_match = re.search(
            r"\(rectangle\s+\(start\s+([\-\d\.]+)\s+([\-\d\.]+)\)\s+\(end\s+([\-\d\.]+)\s+([\-\d\.]+)\)",
            symbol_str,
        )
        if rect_match:
            return [float(rect_match.group(i)) for i in range(1, 5)]
        return None

    normal_coords = get_rectangle_coords(normal_str)
    scrunched_coords = get_rectangle_coords(scrunched_str)

    assert normal_coords is not None
    assert scrunched_coords is not None

    # Extract width and height
    normal_width = abs(normal_coords[2] - normal_coords[0])
    normal_height = abs(normal_coords[3] - normal_coords[1])

    scrunched_width = abs(scrunched_coords[2] - scrunched_coords[0])
    scrunched_height = abs(scrunched_coords[3] - scrunched_coords[1])

    # Scrunched should be narrower and taller
    assert scrunched_width <= normal_width
    assert scrunched_height >= normal_height


def test_bundle_option():
    """Test the bundle option for power pins."""
    symbol_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "GND", "power", "left"],
        ["2", "GND", "power", "left"],  # Same name, should be bundled
        ["3", "VCC", "power", "left"],
        ["4", "VCC", "power", "left"],  # Same name, should be bundled
        ["5", "SIG", "input", "left"],  # Different type, should not be bundled
        ["6", "SIG", "output", "right"],  # Different type, should not be bundled
        ["7", "SIG", "bidir", "right"],  # Different type, should not be bundled
        ["8", "GND", "power", "right"],
        ["9", "GND", "power", "right"],  # Same name, should be bundled
        ["10", "VCC", "power", "right"], # Only one, so no bundling
    ]

    # Generate symbol with bundle=False (default)
    normal_symbol = rows_to_symbol(symbol_rows, sort_by="num")

    # Generate symbol with bundle=True
    bundled_symbol = rows_to_symbol(symbol_rows, sort_by="num", bundle=True)

    # Convert to strings for easier comparison
    normal_str = str(normal_symbol)
    bundled_str = str(bundled_symbol)

    # Normal should have 10 pins
    assert normal_str.count("(pin ") == 10

    # Bundled should have fewer visible pins (7 pins - one for each GND, VCC on each side and 3 non-power pins)
    # But we need to check carefully since the S-expression might have other 'pin' instances
    # Let's count visible pins (ones without hide)

    # Check that non-power pins don't get bundled
    assert bundled_str.count("(pin input ") == 1
    assert bundled_str.count("(pin output ") == 1
    assert bundled_str.count("(pin bidirectional ") == 1

    # Check that power pins get bundled
    power_pins_count = 0
    power_in_indexes = [
        i
        for i, char in enumerate(bundled_str)
        if bundled_str[i : i + 11] == "(pin power_"
    ]
    for idx in power_in_indexes:
        if (
            "(hide yes)" not in bundled_str[idx : idx + 100]
        ):  # If no hide within reasonable distance
            power_pins_count += 1

    # Should have just one visible power_in pin for each group (GND and VCC) on each side
    assert power_pins_count == 4


def test_row_file_to_symbol_lib_file_with_merge(tmp_path):
    """Test merging behavior when overwriting existing library."""
    # Create a sample CSV file with two parts
    csv_content = """part1,
Reference:,U
pin,name,type,side
1,P1,input,left

part2,
Reference:,U
pin,name,type,side
1,P2,output,right
"""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, "w") as f:
        f.write(csv_content)

    # Create an initial library
    output_path = tmp_path / "output.kicad_sym"
    row_file_to_symbol_lib_file(csv_path, symbol_lib_file=output_path)

    # Create a CSV with a third part and an updated part1
    csv_content2 = """part1,
Reference:,X
pin,name,type,side
1,P1_MODIFIED,input,left

part3,
Reference:,U
pin,name,type,side
1,P3,input,top
"""
    csv_path2 = tmp_path / "test2.csv"
    with open(csv_path2, "w") as f:
        f.write(csv_content2)

    # Update the library with overwrite=True to test merge
    row_file_to_symbol_lib_file(csv_path2, symbol_lib_file=output_path, overwrite=True, merge=True)

    # Read the resulting library
    with open(output_path) as f:
        content = f.read()

    # All three parts should be in the library
    lib = Sexp(content)
    symbols = extract_symbols_from_lib(lib)
    symbol_names = [s[1] for s in symbols]

    assert len(symbols) == 3
    assert "part1" in symbol_names
    assert "part2" in symbol_names
    assert "part3" in symbol_names

    # part1 should have the updated reference (X instead of U)
    for symbol in symbols:
        if symbol[1] == "part1":
            for item in symbol:
                if (
                    isinstance(item, list)
                    and item[0] == "property"
                    and item[1] == "Reference"
                ):
                    assert item[2] == "X"  # Should be updated to X


def test_symbols_are_equal():
    """Test the symbols_are_equal function with various symbol configurations."""
    # Create test symbols with different property and pin orderings
    symbol1_str = """
    (symbol "test_part"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "U")
      (property "Value" "test_part")
      (symbol "test_part_1_1"
        (rectangle (start -10 -5) (end 10 5))
        (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        (pin output line (at 15 0 180) (length 5) (name "OUT") (number "2"))
      )
    )
    """

    # Same symbol with properties, pins, and units in different order
    symbol2_str = """
    (symbol "test_part"
      (property "Value" "test_part")
      (property "Reference" "U")
      (on_board yes)
      (in_bom yes)
      (symbol "test_part_1_1"
        (pin output line (at 15 0 180) (length 5) (name "OUT") (number "2"))
        (rectangle (start -10 -5) (end 10 5))
        (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
      )
    )
    """

    # Symbol with different property value (should not be equal)
    symbol3_str = """
    (symbol "test_part"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "R")  # Changed from U to R
      (property "Value" "test_part")
      (symbol "test_part_1_1"
        (rectangle (start -10 -5) (end 10 5))
        (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        (pin output line (at 15 0 180) (length 5) (name "OUT") (number "2"))
      )
    )
    """

    # Symbol with different pin properties (should not be equal)
    symbol4_str = """
    (symbol "test_part"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "U")
      (property "Value" "test_part")
      (symbol "test_part_1_1"
        (rectangle (start -10 -5) (end 10 5))
        (pin input line (at -15 0 0) (length 5) (name "INPUT") (number "1"))  # Changed name
        (pin output line (at 15 0 180) (length 5) (name "OUT") (number "2"))
      )
    )
    """

    # Symbol with different pin position (should not be equal)
    symbol5_str = """
    (symbol "test_part"
      (in_bom yes)
      (on_board yes)
      (property "Reference" "U")
      (property "Value" "test_part")
      (symbol "test_part_1_1"
        (rectangle (start -10 -5) (end 10 5))
        (pin input line (at -15 2 0) (length 5) (name "IN") (number "1"))  # Changed Y position
        (pin output line (at 15 0 180) (length 5) (name "OUT") (number "2"))
      )
    )
    """

    # Symbol with multiple units in different order (should be equal)
    symbol6_str = """
    (symbol "multi_unit"
      (property "Reference" "U")
      (property "Value" "multi_unit")
      (symbol "multi_unit_1_1"
        (rectangle (start -5 -5) (end 5 5))
        (pin input line (at -10 0 0) (length 5) (name "IN1") (number "1"))
      )
      (symbol "multi_unit_2_1"
        (rectangle (start -5 -5) (end 5 5))
        (pin output line (at 10 0 180) (length 5) (name "OUT1") (number "2"))
      )
    )
    """

    symbol7_str = """
    (symbol "multi_unit"
      (property "Reference" "U")
      (property "Value" "multi_unit")
      (symbol "multi_unit_2_1"
        (rectangle (start -5 -5) (end 5 5))
        (pin output line (at 10 0 180) (length 5) (name "OUT1") (number "2"))
      )
      (symbol "multi_unit_1_1"
        (rectangle (start -5 -5) (end 5 5))
        (pin input line (at -10 0 0) (length 5) (name "IN1") (number "1"))
      )
    )
    """

    # Parse all symbols
    symbol1 = Sexp(symbol1_str)
    symbol2 = Sexp(symbol2_str)
    symbol3 = Sexp(symbol3_str)
    symbol4 = Sexp(symbol4_str)
    symbol5 = Sexp(symbol5_str)
    symbol6 = Sexp(symbol6_str)
    symbol7 = Sexp(symbol7_str)

    # Test equality
    assert symbols_are_equal(symbol1, symbol2) == True
    assert symbols_are_equal(symbol1, symbol3) == False  # Different property value
    assert symbols_are_equal(symbol1, symbol4) == False  # Different pin name
    assert symbols_are_equal(symbol1, symbol5) == False  # Different pin position
    assert symbols_are_equal(symbol6, symbol7) == True  # Units in different order

    # Test with generated symbols
    symbol_rows = [
        ["test_gen", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "IN", "input", "left"],
        ["2", "OUT", "output", "right"],
    ]

    gen_symbol1 = rows_to_symbol(symbol_rows, sort_by="num")
    gen_symbol2 = rows_to_symbol(
        symbol_rows, sort_by="name"
    )  # Different sort but same content
    add_quotes(gen_symbol1)
    add_quotes(gen_symbol2)

    assert symbols_are_equal(gen_symbol1, gen_symbol2) == True


def test_symbol_libs_are_equal():
    """Test the symbol_libs_are_equal function with various library configurations."""
    # Create test libraries with the same symbols in different orders
    lib1_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" 
          (rectangle (start -10 -5) (end 10 5))
          (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        )
      )
      (symbol "part2"
        (property "Reference" "R")
        (symbol "part2_1_1" 
          (rectangle (start -5 -5) (end 5 5))
          (pin passive line (at -10 0 0) (length 5) (name "P1") (number "1"))
        )
      )
    )
    """

    # Same library with symbols in different order
    lib2_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (symbol "part2"
        (property "Reference" "R")
        (symbol "part2_1_1" 
          (rectangle (start -5 -5) (end 5 5))
          (pin passive line (at -10 0 0) (length 5) (name "P1") (number "1"))
        )
      )
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" 
          (rectangle (start -10 -5) (end 10 5))
          (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        )
      )
    )
    """

    # Library with different symbol properties (should not be equal)
    lib3_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" 
          (rectangle (start -10 -5) (end 10 5))
          (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        )
      )
      (symbol "part2"
        (property "Reference" "D")
        (symbol "part2_1_1" 
          (rectangle (start -5 -5) (end 5 5))
          (pin passive line (at -10 0 0) (length 5) (name "P1") (number "1"))
        )
      )
    )
    """

    # Library with a different symbol name (should not be equal)
    lib4_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" 
          (rectangle (start -10 -5) (end 10 5))
          (pin input line (at -15 0 0) (length 5) (name "IN") (number "1"))
        )
      )
      (symbol "part3"
        (property "Reference" "R")
        (symbol "part3_1_1" 
          (rectangle (start -5 -5) (end 5 5))
          (pin passive line (at -10 0 0) (length 5) (name "P1") (number "1"))
        )
      )
    )
    """

    # Library with different pin in a symbol (should not be equal)
    lib5_content = """
    (kicad_symbol_lib
      (version 20241209)
      (generator "kicad_symbol_editor")
      (symbol "part1"
        (property "Reference" "U")
        (symbol "part1_1_1" 
          (rectangle (start -10 -5) (end 10 5))
          (pin input line (at -15 0 0) (length 5) (name "INPUT") (number "1"))
        )
      )
      (symbol "part2"
        (property "Reference" "R")
        (symbol "part2_1_1" 
          (rectangle (start -5 -5) (end 5 5))
          (pin passive line (at -10 0 0) (length 5) (name "P1") (number "1"))
        )
      )
    )
    """

    # Parse the libraries
    lib1 = Sexp(lib1_content)
    lib2 = Sexp(lib2_content)
    lib3 = Sexp(lib3_content)
    lib4 = Sexp(lib4_content)
    lib5 = Sexp(lib5_content)

    # Test equality
    assert (
        symbol_libs_are_equal(lib1, lib1) == True
    )  # Same library should be equal to itself
    assert symbol_libs_are_equal(lib1, lib2) == True  # Same symbols in different order
    assert symbol_libs_are_equal(lib1, lib3) == False  # Different symbol property
    assert symbol_libs_are_equal(lib1, lib4) == False  # Different symbol name
    assert symbol_libs_are_equal(lib1, lib5) == False  # Different pin name

    # Test with generated symbols
    rows1 = [
        ["part1", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "IN1", "input", "left"],
        [],
        ["part2", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "IN2", "input", "left"],
    ]

    # Same symbols but in different order
    rows2 = [
        ["part2", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "IN2", "input", "left"],
        [],
        ["part1", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "IN1", "input", "left"],
    ]

    # Generate symbol libraries
    lib1_generated = create_empty_symbol_lib()
    lib2_generated = create_empty_symbol_lib()

    # Process each symbol for lib1
    symbol_row_groups1 = read_symbol_rows(rows1)
    for symbol_rows in symbol_row_groups1:
        symbol = rows_to_symbol(symbol_rows)
        lib1_generated.append(symbol)

    # Process each symbol for lib2
    symbol_row_groups2 = read_symbol_rows(rows2)
    for symbol_rows in symbol_row_groups2:
        symbol = rows_to_symbol(symbol_rows)
        lib2_generated.append(symbol)

    add_quotes(lib1_generated)
    add_quotes(lib2_generated)

    # Test if generated libraries are equal
    assert symbol_libs_are_equal(lib1_generated, lib2_generated) == True


def test_end_to_end_conversion(tmp_path):
    """
    Test end-to-end conversion from symbols to CSV and back to symbols.

    This test performs the following steps:
    1. Creates a library of 10 random symbols
    2. Saves the library to a .kicad_sym file
    3. Converts the .kicad_sym file to a CSV file
    4. Converts the CSV file back to a .kicad_sym file
    5. Loads the new .kicad_sym file
    6. Compares the original and new libraries for equality

    The test verifies that the conversion process is lossless and the resulting
    libraries contain the same symbols with the same properties.
    """

    # Step 1: Create a library with 10 random symbols
    random_symbols_1 = create_random_symbol_lib(10)

    # Step 2: Store the library to a file
    add_quotes(random_symbols_1)
    sym_file_1 = tmp_path / "random_symbols_1.kicad_sym"
    with open(sym_file_1, "w") as f:
        f.write(str(random_symbols_1))
    rmv_quotes(random_symbols_1)

    # Step 3: Convert to CSV
    csv_file = tmp_path / "random_symbols_2.csv"
    symbol_lib_file_to_csv_file(sym_file_1, csv_file=csv_file, overwrite=True)

    # Step 4: Convert CSV back to symbol library
    sym_file_2 = tmp_path / "random_symbols_2.kicad_sym"
    row_file_to_symbol_lib_file(csv_file, symbol_lib_file=sym_file_2, overwrite=True)

    # Step 5: Read back the converted symbol library
    with open(sym_file_2, "r") as f:
        random_symbols_2 = Sexp(f.read())

    # Step 6: Compare the libraries for equality
    assert symbol_libs_are_equal(
        random_symbols_1, random_symbols_2
    ), "Symbol libraries are not equivalent after round-trip conversion"

    # Additional verification: Check that all original symbols are in the new library
    symbols1 = extract_symbols_from_lib(random_symbols_1)
    symbols2 = extract_symbols_from_lib(random_symbols_2)
    assert len(symbols1) == len(
        symbols2
    ), f"Symbol count mismatch: {len(symbols1)} vs {len(symbols2)}"

    # Print some statistics about the test
    symbol_names = [s[1] for s in symbols1]
    print(f"Successfully performed round-trip conversion for {len(symbols1)} symbols:")
    for name in symbol_names:
        print(f"  - {name}")


def test_insert_spacers():
    """Test insertion of spacers for pins with leading asterisks."""
    from kipart.kipart import insert_spacers, DEFAULT_TYPE, DEFAULT_STYLE
    
    # Case 1: Test with pins containing leading asterisks
    pins = [
        {
            "number": "**1",  # Two spacers followed by pin 1
            "name": "TEST1",
            "unit": "1",
            "side": "left",
            "type": "input",
            "style": "line",
            "hidden": "no",
            "row_index": 0
        },
        {
            "number": "*2",   # One spacer followed by pin 2
            "name": "TEST2",
            "unit": "1",
            "side": "left",
            "type": "output",
            "style": "line",
            "hidden": "no",
            "row_index": 1
        },
        {
            "number": "3",    # No spacers
            "name": "TEST3",
            "unit": "1",
            "side": "left",
            "type": "bidirectional",
            "style": "line",
            "hidden": "no",
            "row_index": 2
        }
    ]
    
    expanded_pins = insert_spacers(pins)
    
    # Should have 6 pins now: 2 spacers + pin 1, 1 spacer + pin 2, and pin 3
    assert len(expanded_pins) == 6
    
    # Check that spacers are created correctly
    assert expanded_pins[0]["number"] == "*"
    assert expanded_pins[0]["name"] == ""
    assert expanded_pins[0]["unit"] == "1"  # Should inherit unit from first pin
    assert expanded_pins[0]["side"] == "left"  # Should inherit side from first pin
    
    assert expanded_pins[1]["number"] == "*"
    assert expanded_pins[1]["name"] == ""
    
    # Check that original pins have asterisks removed from numbers
    assert expanded_pins[2]["number"] == "1"
    assert expanded_pins[2]["name"] == "TEST1"
    
    assert expanded_pins[3]["number"] == "*"
    assert expanded_pins[3]["name"] == ""
    
    assert expanded_pins[4]["number"] == "2"
    assert expanded_pins[4]["name"] == "TEST2"
    
    assert expanded_pins[5]["number"] == "3"
    assert expanded_pins[5]["name"] == "TEST3"
    
    # Check that row_index values are sequential
    for i, pin in enumerate(expanded_pins):
        assert pin["row_index"] == i
    
    # Case 2: Test with a pin that is just asterisks (should be all spacers)
    pins = [
        {
            "number": "***",  # Three asterisks only
            "name": "SPACER",
            "unit": "1",
            "side": "left",
            "type": "input",
            "style": "line",
            "hidden": "no",
            "row_index": 0
        }
    ]
    
    expanded_pins = insert_spacers(pins)
    
    # Should have 3 spacer pins and no regular pins
    assert len(expanded_pins) == 3
    for pin in expanded_pins:
        assert pin["number"] == "*"
        assert pin["name"] == ""
    
    # Case 3: Test with empty input
    assert insert_spacers([]) == []


def test_bundle_pins():
    """Test bundling of power pins with the same name."""
    from kipart.kipart import bundle_pins
    
    # Case 1: Basic bundling of power pins
    pins = [
        {
            "number": "1",
            "name": "VCC",
            "unit": "1",
            "side": "left",
            "type": "power_in",
            "style": "line",
            "hidden": "no",
            "row_index": 0
        },
        {
            "number": "2",
            "name": "VCC",  # Same name as first pin
            "unit": "1",
            "side": "left",
            "type": "power_in",
            "style": "line",
            "hidden": "no",
            "row_index": 1
        },
        {
            "number": "3",
            "name": "GND",
            "unit": "1",
            "side": "left",
            "type": "power_in",
            "style": "line",
            "hidden": "no",
            "row_index": 2
        },
        {
            "number": "4",
            "name": "SIG",  # Not a power pin
            "unit": "1",
            "side": "right",
            "type": "input",
            "style": "line",
            "hidden": "no",
            "row_index": 3
        }
    ]
    
    bundled = bundle_pins(0, pins)
    
    # Should have 3 pins now: bundled VCC, GND, and SIG
    assert len(bundled) == 3
    
    # Find the bundled VCC pin
    vcc_pin = None
    for pin in bundled:
        if pin["name"] == "VCC[2]":  # Name should have count indicator
            vcc_pin = pin
            break
    
    assert vcc_pin is not None
    assert vcc_pin["type"] == "power_in"
    assert isinstance(vcc_pin["number"], list)
    assert len(vcc_pin["number"]) == 2
    assert "1" in vcc_pin["number"]
    assert "2" in vcc_pin["number"]
    
    # Check that GND pin is unchanged except for number becoming a list
    gnd_pin = None
    for pin in bundled:
        if pin["name"] == "GND":  # No count indicator (only one pin)
            gnd_pin = pin
            break
    
    assert gnd_pin is not None
    assert isinstance(gnd_pin["number"], list)
    assert len(gnd_pin["number"]) == 1
    assert gnd_pin["number"][0] == "3"
    
    # Check that non-power pin is unchanged
    sig_pin = None
    for pin in bundled:
        if pin["name"] == "SIG":
            sig_pin = pin
            break
    
    assert sig_pin is not None
    assert sig_pin["type"] == "input"
    assert sig_pin["number"] == "4"  # Not converted to a list
    
    # Case 2: Test with no power pins
    pins = [
        {
            "number": "1",
            "name": "SIG1",
            "unit": "1",
            "side": "left",
            "type": "input",
            "style": "line",
            "hidden": "no",
            "row_index": 0
        },
        {
            "number": "2",
            "name": "SIG2",
            "unit": "1",
            "side": "right",
            "type": "output",
            "style": "line",
            "hidden": "no",
            "row_index": 1
        }
    ]
    
    bundled = bundle_pins(0, pins)
    
    # Should have same number of pins, all unchanged
    assert len(bundled) == 2
    assert bundled[0]["name"] == "SIG1"
    assert bundled[0]["number"] == "1"
    assert bundled[1]["name"] == "SIG2"
    assert bundled[1]["number"] == "2"
    
    # Case 3: Test with empty input
    assert bundle_pins(0, []) == []
