import pytest
import os
import csv
import subprocess
from kipart.kilib2csv import library_to_csv

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
    result = library_to_csv(kicad_sym_path, output_file=output_path)
    
    assert os.path.exists(result)
    expected_rows = [
        ["my_part", ""],
        ["Reference:", "U"],
        ["Value:", "my_part"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "P1", "input", "left", "1", "line", "0"],
        [],
        ["part2", ""],
        ["Reference:", "U"],
        ["Value:", "part2"],
        ["pin", "name", "type", "side", "unit", "style", "hidden"],
        ["1", "OUT", "output", "left", "1", "line", "0"]
    ]
    with open(output_path) as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert rows == expected_rows
    
    # Test invalid file
    with pytest.raises(FileNotFoundError):
        library_to_csv(tmp_path / "nonexistent.kicad_sym")
    
    # Test overwrite protection
    with pytest.raises(ValueError, match="Output file.*already exists"):
        library_to_csv(kicad_sym_path, output_file=output_path, overwrite=False)

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
        ["python", "../../kipart/kilib2csv.py", str(kicad_sym_path), "-o", str(output_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert f"Generated {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        ["python", "../../kipart/kilib2csv.py", str(tmp_path / "invalid.txt")],
        capture_output=True, text=True
    )
    assert result.returncode == 0  # Script continues after error
    assert "Error processing" in result.stdout