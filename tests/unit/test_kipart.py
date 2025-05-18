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
    generate_symbol,
    add_quotes,
    row_file_to_symbol_lib_file,
    symbol_lib_file_to_csv_file,
    empty_symbol_lib,
    merge_symbol_libs,
)

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
    assert parse_mixed_string("*") == (chr(0x10FFFF), float('inf'))

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
    with open(file_path, 'w') as f:
        f.write(content)

    with open(file_path) as f:
        parts = extract_symbols_from_lib(f.read())

    assert len(parts) == 2
    assert parts[0][0] == "symbol" and parts[0][1] == "part1"
    assert parts[1][0] == "symbol" and parts[1][1] == "part2"
    # assert "part1" in parts
    # assert "part2" in parts
    # assert "(symbol \"part1\"" in parts["part1"]
    # assert "(symbol \"part2\"" in parts["part2"]

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
        ["1", "P1", "input", "left", "my_part_1", "line", "no"],
        ["2", "P2", "output", "right", "my_part_1", "line", "yes"]
    ]
    rows = symbol_to_csv_rows(Sexp(sexp))
    assert rows == expected_rows

def test_open_row_file(tmp_path):
    """Test reading CSV and Excel files."""
    # Test CSV
    csv_content = "my_part,\nReference:,U\npin,name\n1,P1"
    csv_path = tmp_path / "test.csv"
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    
    rows = read_row_file(csv_path)
    assert rows == [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]

    # Test Excel
    df = pd.DataFrame([["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]])
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
        ["2", "P2"]
    ]
    symbols = read_symbol_rows(rows)
    assert len(symbols) == 2
    assert symbols[0] == [["part1", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]
    assert symbols[1] == [["part2", ""], ["pin", "name"], ["2", "P2"]]

    # Test empty input
    with pytest.raises(ValueError, match="No valid symbols found"):
        read_symbol_rows([])

def test_generate_symbol():
    """Test generating a symbol S-expression from CSV rows."""
    symbol_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "P1", "input", "left"],
        ["2", "P2", "output", "right"]
    ]
    symbol = generate_symbol(symbol_rows, sort_by="num")
    add_quotes(symbol)
    sexp_str = str(symbol)
    assert '(symbol "my_part"' in sexp_str
    assert '(property "Reference" "U"' in sexp_str
    assert '(pin input line' in sexp_str
    assert '(pin output line' in sexp_str
    assert '(name "P1"' in sexp_str
    assert '(name "P2"' in sexp_str

    # Test invalid part name
    with pytest.raises(ValueError, match="Invalid part name"):
        generate_symbol([["", ""], ["pin", "name"], ["1", "P1"]])

def test_generate_symbol_library(tmp_path):
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
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    
    output_path = tmp_path / "output.kicad_sym"
    result = row_file_to_symbol_lib_file(csv_path, symbol_lib_file=output_path)
    
    assert os.path.exists(result)
    with open(result) as f:
        content = f.read()
        assert '(kicad_symbol_lib' in content
        assert '(symbol "my_part"' in content
        assert '(pin input line' in content
        assert '(pin output line' in content
    
    # Test overwrite protection
    with pytest.raises(ValueError, match="Output file.*already exists"):
        row_file_to_symbol_lib_file(csv_path, symbol_lib_file=output_path, overwrite=False)

def test_kipart_cli(tmp_path):
    """Test the kipart.py command-line interface."""
    # Create a sample CSV file
    csv_content = """my_part,
Reference:,U
pin,name,type,side
1,P1,input,left
"""
    csv_path = tmp_path / "test.csv"
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    
    output_path = tmp_path / "output.kicad_sym"
    
    # Test successful run
    result = subprocess.run(
        ["kipart", str(csv_path), "-o", str(output_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert f"Generated {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        ["kipart", str(tmp_path / "invalid.txt")],
        capture_output=True, text=True
    )
    assert "Error processing" in result.stdout
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
    with open(kicad_sym_path, 'w') as f:
        f.write(kicad_sym_content)
    
    output_path = tmp_path / "output.csv"
    result = symbol_lib_file_to_csv_file(kicad_sym_path, csv_file=output_path)
    
    assert os.path.exists(result)
    expected_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["Value:", "my_part"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "P1", "input", "left", "my_part_1", "line", "no"],
        [],
        ["part2", ""],
        ["Reference:", "U"],
        ["Value:", "part2"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "OUT", "output", "left", "part2_1", "line", "no"]
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
        symbol_lib_file_to_csv_file(kicad_sym_path, csv_file=output_path, overwrite=False)

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
    with open(kicad_sym_path, 'w') as f:
        f.write(kicad_sym_content)
    
    output_path = tmp_path / "output.csv"
    
    # Test successful run
    result = subprocess.run(
        ["kilib2csv", str(kicad_sym_path), "-o", str(output_path)],
        capture_output=True, text=True
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
    assert f"Generated {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        ["kilib2csv", str(tmp_path / "invalid.txt")],
        capture_output=True, text=True
    )
    assert result.returncode != 0  # Script continues after error
    assert "Error processing" in result.stdout

def test_empty_symbol_lib():
    """Test creation of an empty symbol library."""
    lib = empty_symbol_lib()
    
    # Check that it's a valid Sexp with the expected structure
    assert isinstance(lib, Sexp)
    assert lib[0] == 'kicad_symbol_lib'
    
    # Check that it has the required attributes
    has_version = False
    has_generator = False
    has_generator_version = False
    
    for item in lib:
        if isinstance(item, list):
            if item[0] == 'version':
                has_version = True
                assert item[1] == '20241209'
            elif item[0] == 'generator':
                has_generator = True
                assert item[1] == 'kicad_symbol_editor'
            elif item[0] == 'generator_version':
                has_generator_version = True
                assert item[1] == '8.0'
    
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
                if isinstance(item, list) and item[0] == 'property' and item[1] == 'Reference':
                    assert item[2] == 'X'  # Should be from lib2, not lib1

def test_scrunch_option():
    """Test the scrunch option for compressing pins under top/bottom rows."""
    symbol_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["pin", "name", "type", "side"],
        ["1", "P1", "input", "left"],
        ["2", "P2", "output", "right"],
        ["3", "P3", "input", "top"],
        ["4", "P4", "output", "bottom"]
    ]
    
    # Generate symbol with scrunch=False (default)
    normal_symbol = generate_symbol(symbol_rows, sort_by="num")
    
    # Generate symbol with scrunch=True
    scrunched_symbol = generate_symbol(symbol_rows, sort_by="num", scrunch=True)
    
    # Convert to strings for easier comparison
    normal_str = str(normal_symbol)
    scrunched_str = str(scrunched_symbol)
    
    # Both should have all pins
    assert normal_str.count('(pin ') == 4
    assert scrunched_str.count('(pin ') == 4
    
    # Extract the rectangle dimensions
    # In normal layout, left/right pins are side by side with top/bottom
    # In scrunched layout, left/right pins are underneath top/bottom
    
    # Helper function to extract rectangle coordinates from symbol string
    def get_rectangle_coords(symbol_str):
        import re
        rect_match = re.search(r'\(rectangle\s+\(start\s+([\-\d\.]+)\s+([\-\d\.]+)\)\s+\(end\s+([\-\d\.]+)\s+([\-\d\.]+)\)', symbol_str)
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
        ["5", "SIG", "input", "right"]  # Different type, should not be bundled
    ]
    
    # Generate symbol with bundle=False (default)
    normal_symbol = generate_symbol(symbol_rows, sort_by="num")
    
    # Generate symbol with bundle=True
    bundled_symbol = generate_symbol(symbol_rows, sort_by="num", bundle=True)
    
    # Convert to strings for easier comparison
    normal_str = str(normal_symbol)
    bundled_str = str(bundled_symbol)
    
    # Normal should have 5 pins
    assert normal_str.count('(pin ') == 5
    
    # Bundled should have fewer pins (3 pins - one each for GND, VCC, and SIG)
    # But we need to check carefully since the S-expression might have other 'pin' instances
    # Let's count visible pins (ones without hide)
    
    # Check that input pin doesn't get bundled
    assert bundled_str.count('(pin input ') == 1
    
    # Check that power pins get bundled
    power_pins_count = 0
    power_in_indexes = [i for i, char in enumerate(bundled_str) if bundled_str[i:i+11] == '(pin power_']
    for idx in power_in_indexes:
        if '(hide yes)' not in bundled_str[idx:idx+100]:  # If no hide within reasonable distance
            power_pins_count += 1
    
    # Should have just one visible power_in pin for each group (GND and VCC)
    assert power_pins_count == 2

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
    with open(csv_path, 'w') as f:
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
    with open(csv_path2, 'w') as f:
        f.write(csv_content2)
    
    # Update the library with overwrite=True to test merge
    row_file_to_symbol_lib_file(csv_path2, symbol_lib_file=output_path, overwrite=True)
    
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
                if isinstance(item, list) and item[0] == 'property' and item[1] == 'Reference':
                    assert item[2] == 'X'  # Should be updated to X