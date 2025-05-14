import pytest
import os
import subprocess
from kipart.kipart import generate_library

def test_generate_library(tmp_path):
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
    result = generate_library(csv_path, output_file=output_path)
    
    assert os.path.exists(result)
    with open(result) as f:
        content = f.read()
        assert '(kicad_symbol_lib' in content
        assert '(symbol "my_part"' in content
        assert '(pin input line' in content
        assert '(pin output line' in content
    
    # Test overwrite protection
    with pytest.raises(ValueError, match="Output file.*already exists"):
        generate_library(csv_path, output_file=output_path, overwrite=False)

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
        # ["python", "../../kipart/kipart.py", str(csv_path), "-o", str(output_path)],
        ["kipart", str(csv_path), "-o", str(output_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert f"Generated {output_path}" in result.stdout
    assert os.path.exists(output_path)

    # Test invalid input
    result = subprocess.run(
        # ["python", "../../kipart/kipart.py", str(tmp_path / "invalid.txt")],
        ["kipart", str(tmp_path / "invalid.txt")],
        capture_output=True, text=True
    )
    assert result.returncode != 0  # Script continues after error
    assert "Error processing" in result.stdout