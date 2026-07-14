#!/usr/bin/env python3
"""Convert SPD symbol description format to CSV for kipart.

The SPD format itself lives in spd.py; this module only turns the parsed pieces
into the CSV rows that kipart reads.
"""

import argparse
import sys
from pathlib import Path

from .spd import (
    expand_pin_names,
    parse_spd,
    parse_spd_file,
    parse_spd_symbol,
    SIDE_ORDER,
)


def convert_spd_symbol(lines: list[str]) -> list[list[str]]:
    """Convert SPD symbol lines to CSV rows for kipart."""
    part = parse_spd_symbol(lines)

    csv_rows = [[part["name"], '']]

    # Pass any part property values through to the CSV.
    for prop_name, prop_value in part.get("properties", {}).items():
        csv_rows.append([f"{prop_name}:", prop_value, ''])

    # The Unit column only appears for a part that has unit directives.
    has_units = any("name" in unit for unit in part["units"])
    header = ['Pin', 'Type', 'Name', 'Side', 'Style', 'Hidden']
    if has_units:
        header.append('Unit')
    csv_rows.append(header)

    def add_row(row, unit_name):
        if has_units:
            row.append(unit_name)
        csv_rows.append(row)

    def pin_rows(pin, numbers, side, hidden, unit_name):
        """One row per pin number, with the name each of them ends up with."""
        names, _ = expand_pin_names(pin["name"], numbers)
        for name, number in zip(names, numbers):
            add_row(
                [number, pin["type"], name, side, pin["style"], hidden], unit_name
            )

    for unit in part["units"]:
        unit_name = unit.get("name", '')
        for side in (key for key in unit if key in SIDE_ORDER):
            for entry in unit[side]:
                if "spacer" in entry:
                    # Spacers skip a pin position on the side.
                    for _ in range(entry["spacer"]):
                        add_row(["*", '', '', side, '', ''], unit_name)
                    continue

                numbers = entry["numbers"]
                hidden = 'yes' if entry.get("hidden") else 'no'
                pin_rows(entry, numbers, side, hidden, unit_name)

                # An alternate re-uses the pin numbers of the pin it belongs to,
                # and kipart turns the duplicate rows into alternate pins.
                for alternate in entry.get("alternates", []):
                    pin_rows(alternate, numbers, side, hidden, unit_name)

    return csv_rows


def spd_to_csv(spd_content: str) -> str:
    """Convert SPD format content to CSV format string."""
    symbols = parse_spd(spd_content)

    all_csv_rows = []

    for i, symbol_lines in enumerate(symbols):
        csv_rows = convert_spd_symbol(symbol_lines)
        all_csv_rows.extend(csv_rows)
        if i < len(symbols) - 1:
            all_csv_rows.append([])  # Blank row between symbols

    # Convert to CSV string
    return ''.join(
        (','.join(row) + '\n') if row else '\n' for row in all_csv_rows
    )


def main():
    parser = argparse.ArgumentParser(
        description='Convert SPD symbol description files to CSV format for kipart.'
    )
    parser.add_argument(
        'input_files',
        nargs='*',
        help='SPD format input files (if none given, reads from stdin)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output CSV file (default: stdout)'
    )
    parser.add_argument(
        '-m', '--merge',
        action='store_true',
        help='Append to output file instead of overwriting'
    )

    args = parser.parse_args()

    all_csv_rows = []

    # If no input files given, read from stdin
    if len(args.input_files) == 0:
        stdin_content = sys.stdin.read()
        if not stdin_content.strip():
            print("Error: No input files specified and no data provided via stdin", file=sys.stderr)
            sys.exit(1)
        # Write stdin content to a temporary file and process it
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.spd', delete=False) as tmp:
            tmp.write(stdin_content)
            args.input_files = [tmp.name]

    for filepath in args.input_files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            continue

        try:
            symbols = parse_spd_file(path)

            for i, symbol_lines in enumerate(symbols):
                csv_rows = convert_spd_symbol(symbol_lines)
                all_csv_rows.extend(csv_rows)
                if i < len(symbols) - 1:
                    all_csv_rows.append([])  # Blank row between symbols

        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            continue

    # Write output
    output_content = '\n'.join(
        ','.join(row) if row else '' for row in all_csv_rows
    ) + '\n'

    if args.output:
        mode = 'a' if args.merge else 'w'
        with open(args.output, mode) as f:
            f.write(output_content)
    else:
        print(output_content, end='')


if __name__ == '__main__':
    main()
