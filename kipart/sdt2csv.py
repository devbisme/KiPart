#!/usr/bin/env python3
"""Convert SDT symbol description format to CSV for kipart.

SDT (Schematic Design Tool) format is used by OrCAD/similar EDA tools.
"""

import argparse
import re
import sys
from pathlib import Path


# Map SDT pin types to kipart types
SDT_TYPE_MAP = {
    'a': 'power_in',
    's': 'power_out',
    'i': 'input',
    'o': 'output',
    'b': 'bidirectional',
    't': 'tri_state',
    'h': 'open_collector',
    'c': 'open_collector',
    'e': 'open_emitter',
    'p': 'passive',
    'u': 'unspecified',
    'x': 'no_connect',
}


def parse_sdt_file(filepath: Path) -> list[list[str]]:
    """Parse an SDT-format symbol description file.

    Returns a list of symbol row groups (each group is a list of CSV rows).
    """
    with open(filepath, 'r') as f:
        content = f.read()

    # Split into symbol definitions (separated by 'device' keyword)
    symbols = []
    current_symbol_lines = []
    empty_lines = []
    in_symbol = False

    for line in content.split('\n'):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            # Keep empty lines within a symbol definition (they indicate skipped pin positions)
            empty_lines.append('')
            continue

        # Skip pure comment lines
        if stripped.startswith(';'):
            continue

        # Start of a new symbol definition
        if stripped.startswith('device '):
            # Save previous symbol if exists
            if current_symbol_lines:
                symbols.append(current_symbol_lines)
            empty_lines = []
            current_symbol_lines = [stripped]
            in_symbol = True
        elif in_symbol:
            # Insert any preceding empty lines.
            current_symbol_lines.extend(empty_lines)
            empty_lines = []
            # Append the current, non-empty line to the current symbol definition
            current_symbol_lines.append(stripped)

    # Add the last symbol
    if current_symbol_lines:
        symbols.append(current_symbol_lines)

    return symbols


def convert_sdt_symbol(lines: list[str]) -> list[list[str]]:
    """Convert SDT symbol lines to CSV rows for kipart."""
    csv_rows = []

    # First line should be the device definition
    device_line = lines[0]
    match = re.match(r'device\s+(\S+)\s+(\d+)\s+(\d+)', device_line)
    if not match:
        raise ValueError(f"Invalid device line: {device_line}")

    part_name = match.group(1)

    # Part name row
    csv_rows.append([part_name, ''])

    # Parse remaining lines for pins to determine if units are used
    current_unit = None
    has_units = False

    # First pass: determine if any unit is specified
    for line in lines[1:]:
        stripped = line.strip().lower()
        if stripped.startswith('unit '):
            has_units = True
            break

    # Header row
    if has_units:
        csv_rows.append(['Pin', 'Type', 'Name', 'Side', 'Unit'])
    else:
        csv_rows.append(['Pin', 'Type', 'Name', 'Side'])

    # Second pass: process pins
    current_side = 'left'  # default
    current_unit = None

    for line in lines[1:]:
        stripped = line.strip()

        # Skip empty lines (they're used to skip pin positions in SDT)
        if not stripped:
            if has_units:
                csv_rows.append(["*", '', '', current_side, current_unit])  # Blank row for skipped pin with unit column
            else:
                csv_rows.append(["*", '', '', current_side])  # Blank row for skipped pin
            continue

        # Check if this is a side directive
        if stripped.lower() in ('left', 'right', 'top', 'bottom'):
            current_side = stripped.lower()
            continue

        # Check if this is a unit directive
        if stripped.lower().startswith('unit '):
            try:
                current_unit = stripped.split()[1]
            except IndexError:
                pass  # If no unit name is given, just keep whatever unit was active before
            continue

        # Skip comment blocks
        if stripped.startswith(';'):
            continue

        # Parse pin definition: <type> <name> <pin numbers...>
        # Example: "a   vcc   3" or "i   a0   k4 l8 l4 k3 l9 l3 m9 m3 n9 m4"
        parts = stripped.split()
        if len(parts) < 3:
            continue

        pin_type_code = parts[0]
        pin_name = parts[1]
        pin_numbers = parts[2:]

        # Convert SDT type code to kipart type
        pin_type = SDT_TYPE_MAP.get(pin_type_code, 'passive')

        # Create a row for each pin number (for repetitive pins)
        # If there is only one pin number, keep name as-is
        # If there are multiple pin numbers, we need to handle naming:
        #   - If pin name ends with a number (e.g., "a5"), then start incrementing
        #     from that number for each pin number (a5, a6, a7...).
        #   - If pin name does not end with a number, then start incrementing from 0.
        num_pin_numbers = len(pin_numbers)
        start_index_match = re.search(r'(\D+)(\d+)$', pin_name)

        if num_pin_numbers == 1:
            # Single pin number - use name as-is
            for pin_num in pin_numbers:
                if has_units:
                    csv_rows.append(
                        [pin_num, pin_type, pin_name, current_side, current_unit]
                    )
                else:
                    csv_rows.append([pin_num, pin_type, pin_name, current_side])
        else:
            # Multiple pin numbers - determine starting index for naming
            if start_index_match:
                pin_name_base = start_index_match.group(1)
                start_index = int(start_index_match.group(2))
            else:
                pin_name_base = pin_name
                start_index = 0  # default starting index if not given
            # Create a row for each pin number with incremented index
            for index, pin_num in enumerate(pin_numbers, start_index):
                if has_units:
                    csv_rows.append(
                        [pin_num, pin_type, f"{pin_name_base}{index}",
                         current_side, current_unit]
                    )
                else:
                    csv_rows.append(
                        [pin_num, pin_type, f"{pin_name_base}{index}", current_side]
                    )

    return csv_rows


def sdt_to_csv(sdt_content: str) -> str:
    """Convert SDT format content to CSV format string."""
    # Parse as file
    from io import StringIO

    # Write to temp file for parsing
    with open('/tmp/sdt_temp.txt', 'w') as f:
        f.write(sdt_content)

    symbols = parse_sdt_file(Path('/tmp/sdt_temp.txt'))

    all_csv_rows = []

    for i, symbol_lines in enumerate(symbols):
        csv_rows = convert_sdt_symbol(symbol_lines)
        all_csv_rows.extend(csv_rows)
        if i < len(symbols) - 1:
            all_csv_rows.append([])  # Blank row between symbols

    # Convert to CSV string
    output = StringIO()
    for row in all_csv_rows:
        if row:
            output.write(','.join(row) + '\n')
        else:
            output.write('\n')

    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(
        description='Convert SDT symbol description files to CSV format for kipart.'
    )
    parser.add_argument(
        'input_files',
        nargs='+',
        help='SDT format input files'
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

    for filepath in args.input_files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            continue

        try:
            symbols = parse_sdt_file(path)

            for i, symbol_lines in enumerate(symbols):
                csv_rows = convert_sdt_symbol(symbol_lines)
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