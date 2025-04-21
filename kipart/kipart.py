#!/usr/bin/env python3

"""
KiCad Symbol Library Generator

This script generates KiCad symbol libraries from CSV or Excel files using utility
functions from common.py. It supports creating formatted .kicad_sym files with
precise pin placement based on grid-based positioning.

Dependencies:
- common.py: Provides utility functions (open_input_file, read_symbol_rows, generate_symbol, indent_sexpr).
- pandas: For reading Excel files (requires openpyxl for .xlsx support).
- Standard library: argparse, os, sys.

Usage:
- Run: `python kipart.py input.csv --output output.kicad_sym`
"""

__all__ = ['generate_library']

import argparse
import os
import sys
from common import open_input_file, read_symbol_rows, generate_symbol, indent_sexpr

__version__ = "1.0"

def generate_library(input_file, sort_by='row', reverse=False, default_side='left', output_file=None, overwrite=False):
    """
    Generate a KiCad symbol library from a CSV or Excel file.

    Processes input rows into symbols, generates S-expressions, and writes a formatted
    .kicad_sym file using functions from common.py.

    Args:
        input_file (str): Path to the input CSV or Excel file.
        sort_by (str, optional): Sort pins by 'row', 'num', or 'name'. Defaults to 'row'.
        reverse (bool, optional): Reverse the sort order. Defaults to False.
        default_side (str, optional): Default pin side. Defaults to 'left'.
        output_file (str, optional): Output file path. Defaults to input file with .kicad_sym extension.
        overwrite (bool, optional): Allow overwriting existing output file. Defaults to False.

    Returns:
        str: Path to the generated .kicad_sym file.

    Raises:
        ValueError: If the input file is invalid, no symbols are found, or output file exists without overwrite.
    """
    # Read and group input rows using common utilities
    rows = open_input_file(input_file)
    symbol_data = read_symbol_rows(rows)
    
    # Construct library S-expression
    output = []
    output.append('(kicad_symbol_lib')
    output.append('(version 20241209)')
    output.append('(generator "kipart")')
    output.append('(generator_version "1.0")')
    
    # Generate symbols and add to library
    for symbol_rows in symbol_data:
        symbol_sexpr = generate_symbol(symbol_rows, sort_by=sort_by, reverse=reverse, default_side=default_side)
        output.extend(symbol_sexpr)
    
    output.append(')')
    
    # Determine output filename
    if output_file:
        final_output_file = output_file
    else:
        final_output_file = os.path.splitext(input_file)[0] + '.kicad_sym'
    
    # Check for existing file
    if os.path.exists(final_output_file) and not overwrite:
        raise ValueError(f"Output file {final_output_file} already exists. Use --overwrite to allow overwriting.")
    
    # Format and write output using common indent_sexpr
    indented_output = indent_sexpr(output)
    
    with open(final_output_file, 'w') as f:
        f.write('\n'.join(indented_output))
    
    return final_output_file

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
    
    # Process each input file
    for input_file in args.input_files:
        try:
            output_file = generate_library(
                input_file,
                sort_by=args.sort,
                reverse=args.reverse,
                default_side=args.side,
                output_file=args.output,
                overwrite=args.overwrite
            )
            print(f"Generated {output_file} successfully from {input_file}")
        except Exception as e:
            print(f"Error processing {input_file}: {str(e)}")
            continue

if __name__ == "__main__":
    main()