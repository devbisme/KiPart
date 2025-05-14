import pytest
import pandas as pd
import os
from simp_sexp import Sexp
from kipart.common import (
    get_text_bounding_box,
    parse_mixed_string,
    extract_symbols_from_lib,
    symbol_to_csv_rows,
    open_input_file,
    read_symbol_rows,
    generate_symbol,
    add_quotes,
)

def test_get_text_bounding_box():
    """Test text bounding box calculation."""
    # Test default font size (1.27 mm)
    width, height = get_text_bounding_box("TEST")
    assert width == pytest.approx(4 * 1.27 * 0.6)  # 4 chars * 0.6 * font_size
    assert height == pytest.approx(1.27)

    # Test custom font size
    width, height = get_text_bounding_box("ABC", font_size=2.0)
    assert width == pytest.approx(3 * 2.0 * 0.6)
    assert height == pytest.approx(2.0)

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
          (name "P2")
          (number "2")
        )
      )
    )
    """
    expected_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["Value:", "my_part"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "P1", "input", "left", "my_part_1", "line", "0"],
        ["2", "P2", "output", "right", "my_part_1", "line", "0"]
    ]
    rows = symbol_to_csv_rows(Sexp(sexp))
    assert rows == expected_rows

def test_open_input_file(tmp_path):
    """Test reading CSV and Excel files."""
    # Test CSV
    csv_content = "my_part,\nReference:,U\npin,name\n1,P1"
    csv_path = tmp_path / "test.csv"
    with open(csv_path, 'w') as f:
        f.write(csv_content)
    
    rows = open_input_file(csv_path)
    assert rows == [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]

    # Test Excel
    df = pd.DataFrame([["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]])
    excel_path = tmp_path / "test.xlsx"
    df.to_excel(excel_path, index=False, header=False)
    
    rows = open_input_file(excel_path)
    assert rows == [["my_part", ""], ["Reference:", "U"], ["pin", "name"], ["1", "P1"]]

    # Test invalid extension
    with pytest.raises(ValueError, match="Unsupported file extension"):
        open_input_file(tmp_path / "test.txt")

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
