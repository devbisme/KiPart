#!/usr/bin/env python3

"""
KiCad Symbol Library to CSV Parser

This script parses KiCad symbol libraries (.kicad_sym) into CSV files using utility
functions from common.py. The output CSV contains each part's symbol name, properties,
and pin details, with a blank row between parts.

Dependencies:
- common.py: Provides utility functions (extract_parts_from_symbol_libr, symbol_sexp_to_csv_rows).
- Standard library: csv, argparse, os, sys.

Usage:
- Run: `python kilib2csv.py input.kicad_sym --output output.csv`
"""

__all__ = ['library_to_csv']

import csv
import argparse
import os
import sys
from common import extract_symbols_from_lib, symbol_to_csv_rows

from pckg_info import __version__

def library_to_csv(input_file, output_file=None, overwrite=False):
    """
    Convert a KiCad symbol library to a CSV file with part data.

    Reads a .kicad_sym file, extracts each part's CSV rows using functions from
    common.py, and writes them to a CSV file with a blank row between parts.

    Args:
        input_file (str): Path to the input .kicad_sym file.
        output_file (str, optional): Path to the output CSV file. Defaults to input file
                                    with .csv extension.
        overwrite (bool, optional): Allow overwriting existing output file. Defaults to False.

    Returns:
        str: Path to the generated CSV file.

    Raises:
        FileNotFoundError: If the input file does not exist.
        ValueError: If the output file exists and overwrite is False, or if the input file
                    is not a .kicad_sym file.
    """
    # Validate input file
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} does not exist")
    
    _, ext = os.path.splitext(input_file)
    if ext.lower() != '.kicad_sym':
        raise ValueError(f"Input file must be a .kicad_sym file, got {ext}")
    
    # Determine output filename
    if output_file:
        final_output_file = output_file
    else:
        final_output_file = os.path.splitext(input_file)[0] + '.csv'
    
    # Check for existing output file
    if os.path.exists(final_output_file) and not overwrite:
        raise ValueError(f"Output file {final_output_file} already exists. Use --overwrite to allow overwriting.")
    
    # Read the symbol library contents
    with open(input_file, 'r') as f:
        symbol_lib = f.read()
    
    # Extract parts from the symbol library using common utility
    parts = extract_symbols_from_lib(symbol_lib)

    # Sort parts by name for consistent output.
    parts = sorted(parts, key=lambda x: x[1])
    
    # Convert each part to CSV rows and combine with blank rows
    all_rows = []
    for part in parts:  # Sort for consistent output
        part_rows = symbol_to_csv_rows(part)
        all_rows.extend(part_rows)
        all_rows.append([])  # Add blank row between parts
    
    # Remove trailing blank row if present
    if all_rows and all_rows[-1] == []:
        all_rows.pop()
    
    # Write to CSV file
    with open(final_output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(all_rows)
    
    return final_output_file

def main():
    """
    Command-line interface for parsing KiCad symbol libraries to CSV files.

    Processes .kicad_sym files, extracts part data, and writes CSV files with blank
    rows between parts. Handles errors gracefully and provides user feedback.

    Args:
        None (uses sys.argv via argparse).

    Returns:
        None

    Exits:
        1: If invalid arguments are provided (e.g., multiple inputs with --output).
    """
    parser = argparse.ArgumentParser(description="Parse KiCad symbol libraries to CSV files")
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-o', '--output', help="Output CSV file path")
    parser.add_argument('-w', '--overwrite', action='store_true', help="Allow overwriting of an existing output file")
    parser.add_argument('input_files', nargs='+', help="Input KiCad symbol library files (.kicad_sym)")
    
    args = parser.parse_args()
    
    # Validate single input file with output option
    if args.output and len(args.input_files) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)
    
    # Process each input file
    for input_file in args.input_files:
        try:
            output_file = library_to_csv(
                input_file,
                output_file=args.output,
                overwrite=args.overwrite
            )
            print(f"Generated {output_file} successfully from {input_file}")
        except Exception as e:
            print(f"Error processing {input_file}: {str(e)}")
            continue

if __name__ == "__main__":
    main()