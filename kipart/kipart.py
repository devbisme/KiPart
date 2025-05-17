#!/usr/bin/env python3

"""
KiCad Symbol Library Generator

This script generates KiCad symbol libraries from CSV or Excel files using utility
functions from common.py. It supports creating formatted .kicad_sym files with
precise pin placement based on grid-based positioning.

Dependencies:
- common.py: Provides utility functions (open_row_file, read_symbol_rows, generate_symbol).
- pandas: For reading Excel files (requires openpyxl for .xlsx support).
- Standard library: argparse, os, sys.

Usage:
- Run: `python kipart.py input.csv --output output.kicad_sym`
"""

__all__ = ['row_file_to_symbol_lib_file']

import argparse
import os
import sys
from .common import read_row_file, generate_symbol_lib

from .pckg_info import __version__

def row_file_to_symbol_lib_file(row_file, symbol_lib_file=None, sort_by='row', reverse=False, default_side='left', overwrite=False):
    """
    Generate a KiCad symbol library from a CSV or Excel file.

    Processes input rows into symbols, generates S-expressions, and writes a formatted
    .kicad_sym file using functions from common.py.

    Args:
        row_file (str): Path to the input CSV or Excel file with rows of symbol pin data.
        symbol_lib_file (str, optional): Output file path. Defaults to input file with .kicad_sym extension.
        sort_by (str, optional): Sort pins by 'row', 'num', or 'name'. Defaults to 'row'.
        reverse (bool, optional): Reverse the sort order. Defaults to False.
        default_side (str, optional): Default pin side. Defaults to 'left'.
        overwrite (bool, optional): Allow overwriting existing output file. Defaults to False.

    Returns:
        str: Path to the generated .kicad_sym file.

    Raises:
        ValueError: If the input file is invalid, no symbols are found, or output file exists without overwrite.
    """

    # Determine output filename for the symbol library
    if not symbol_lib_file:
        symbol_lib_file = os.path.splitext(row_file)[0] + '.kicad_sym'

    # Check for an existing file
    if os.path.exists(symbol_lib_file) and not overwrite:
        raise ValueError(f"Output file {symbol_lib_file} already exists. Use --overwrite to allow overwriting.")
    
    # Read rows of symbol pin data from CSV or Excel file.
    rows = read_row_file(row_file)

    # Generate the symbol library from the rows.
    symbol_lib = generate_symbol_lib(rows, sort_by=sort_by, reverse=reverse, default_side=default_side, alt_pin_delim=None)

    # Store the symbol library as an S-expression in the output file.
    with open(symbol_lib_file, 'w') as f:
        f.write(str(symbol_lib))

    return symbol_lib_file

def main():
    """
    Command-line interface for generating KiCad symbol libraries from CSV or Excel files.

    Parses arguments and processes input files, handling errors gracefully.

    Args:
        None (uses sys.argv via argparse).

    Returns:
        None

    Exits:
        1: If invalid arguments are provided (e.g., multiple inputs with --output).
    """
    parser = argparse.ArgumentParser(description="Convert CSV or Excel files to KiCad symbol libraries")
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--reverse', action='store_true', help="Sort pins in reverse order")
    parser.add_argument('--side', choices=['left', 'right', 'top', 'bottom'], default='left',
                        help="Which side to place the pins by default")
    parser.add_argument('-o', '--output', help="Generated KiCad symbol library (.kicad_sym)")
    parser.add_argument('-w', '--overwrite', action='store_true', help="Allow overwriting of an existing part library")
    parser.add_argument('-s', '--sort', choices=['row', 'num', 'name'], default='row',
                        help="Sort the part pins by their entry order in the CSV file (row), "
                             "their pin number (num), or their pin name (name)")
    parser.add_argument('input_files', nargs='+',
                        help="Input CSV or Excel files (.csv, .xlsx, .xls)")
    
    args = parser.parse_args()
    
    # Validate single input file with output option
    if args.output and len(args.input_files) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)
    
    # Process each input file containing rows of symbol pin data
    for row_file in args.input_files:
        try:
            symbol_lib_file = row_file_to_symbol_lib_file(
                row_file,
                symbol_lib_file=args.output,
                sort_by=args.sort,
                reverse=args.reverse,
                default_side=args.side,
                overwrite=args.overwrite
            )
            print(f"Generated {symbol_lib_file} successfully from {row_file}")
        except Exception as e:
            print(f"Error processing {row_file}: {str(e)}")
            raise e
            continue

if __name__ == "__main__":
    main()
