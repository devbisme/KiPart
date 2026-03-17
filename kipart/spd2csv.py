#!/usr/bin/env python3
"""Convert SPD symbol description format to CSV for kipart.

SPD (Shorthand Part Description) format.
"""

import argparse
import re
import sys
from pathlib import Path


# SDT comment delimiters (both full-line and in-line)
COMMENT_DELIM = (
    ";",
    "//",
)

# Map SDT pin types to kipart types
SPD_TYPE_MAP = {
    'p': 'power_in',
    'pi': 'power_in',
    'pwr': 'power_in',
    'pwr_in': 'power_in',
    'po': 'power_out',
    'pwr_out': 'power_out',
    'i': 'input',
    'in': 'input',
    'o': 'output',
    'out': 'output',
    'b': 'bidirectional',
    'bi': 'bidirectional',
    'io': 'bidirectional',
    't': 'tri_state',
    'tri': 'tri_state',
    'oc': 'open_collector',
    'oe': 'open_emitter',
    'pass': 'passive',
    'f': 'free',
    'u': 'unspecified',
    'un': 'unspecified',
    'a': 'unspecified',
    'analog': 'unspecified',
    'x': 'no_connect',
    'nc': 'no_connect',
}

SPD_STYLE_MAP = {
    '*': 'inverted',
    '!': 'inverted',
    '~': 'inverted',
    '/': 'inverted',
    '#': 'inverted',
    '>': 'clock',
    '_': 'low',
    '@': 'analog',
    '-': 'hidden',
}

STYLE_TO_KICAD = {
    frozenset({'inverted'}): 'inverted',
    frozenset({'clock'}): 'clock',
    frozenset({'inverted', 'clock'}): 'inverted_clock',
    frozenset({'low', 'input'}): 'input_low',
    frozenset({'low', 'output'}): 'output_low',
    frozenset({'low', 'input', 'clock'}): 'clock_low',
    frozenset({'low', 'output', 'clock'}): 'clock_low',
    frozenset({'analog'}): 'analog',
    frozenset({}): '',       
}


def parse_spd_file(filepath: Path) -> list[list[str]]:
    """Parse an SPD-format symbol description file.

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
        if stripped.startswith(COMMENT_DELIM):
            continue

        # Remove in-line comments
        for comment_start in COMMENT_DELIM:
            comment_index = stripped.find(comment_start)
            if comment_index != -1:
                stripped = stripped[:comment_index].strip()

        # Start of a new symbol definition
        if stripped.startswith('device '):
            # Save previous symbol if exists
            if current_symbol_lines:
                symbols.append(current_symbol_lines)
            empty_lines = []
            current_symbol_lines = [stripped]
            in_symbol = True
        elif in_symbol:
            if stripped.lower().split()[0] in ('left', 'right', 'top', 'bottom', 'unit'):
                empty_lines = []  # Clear empty lines before side/unit directives
            # Insert any preceding empty lines between pins.
            current_symbol_lines.extend(empty_lines)
            empty_lines = []
            # Append the current, non-empty line to the current symbol definition
            current_symbol_lines.append(stripped)

    # Add the last symbol
    if current_symbol_lines:
        symbols.append(current_symbol_lines)

    return symbols


def convert_spd_symbol(lines: list[str]) -> list[list[str]]:
    """Convert SPD symbol lines to CSV rows for kipart."""
    csv_rows = []

    # First line should be the device definition
    device_line = lines[0]
    match = re.match(r'^device\s+(\S+)$', device_line)
    if not match:
        raise ValueError(f"Invalid device line: {device_line}")

    part_name = match.group(1)

    # Part name row
    csv_rows.append([part_name, ''])

    # Pass any part property values through to the CSV.
    non_property_lines = []
    for line in lines[1:]:
        # Property lines are in the format "property_name: property_value"
        match = re.match(r"^(\w+)\s*:\s*(.*)$", line)
        if match:
            prop_name = match.group(1)
            prop_value = match.group(2)
            csv_rows.append([f"{prop_name}:", prop_value, ''])
        else:
            non_property_lines.append(line)
    lines = non_property_lines  # Only keep non-property lines for further processing

    # Parse remaining lines for pins to determine if units are used
    current_unit = None
    has_units = False

    # First pass: determine if any unit is specified
    for line in lines:
        if line.strip().lower().startswith('unit '):
             has_units = True
             break

    # Header row (always include Style and Hidden columns)
    if has_units:
        csv_rows.append(['Pin', 'Type', 'Name', 'Side', 'Style', 'Hidden', 'Unit'])
    else:
        csv_rows.append(['Pin', 'Type', 'Name', 'Side', 'Style', 'Hidden'])

    # Second pass: process pins
    current_side = 'left'  # default
    current_unit = None

    for line in lines:
        stripped = line.strip()

        # Skip empty lines or lines with just an asterisk (they're used to skip pin positions in SPD)
        if not stripped or stripped=='*':
            if has_units:
                csv_rows.append(["*", '', '', current_side, '', '', current_unit])  # Blank row for skipped pin with unit column
            else:
                csv_rows.append(["*", '', '', current_side, '', ''])  # Blank row for skipped pin
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

        # Parse pin definition: <type> <name> <pin numbers...>
        # Example: "a   vcc   3" or "i   a0   k4 l8 l4 k3 l9 l3 m9 m3 n9 m4"
        # Type can have modifiers: "*"=inverted, "-"=hidden, ">"=clock
        parts = stripped.split()
        if len(parts) < 3:
            continue

        # Extract pin type and modifiers from first part
        # e.g., "i*" -> pin_type_code="i", style_mods="*"
        #       "i*->" -> pin_type_code="i", style_mods="*->"
        pin_type_with_mods = parts[0]
        # Extract pin_type_code as all the alpha chars from the start
        pin_type_code = ''.join(c for c in pin_type_with_mods if c.isalpha())
        # Extract style_mods as the remaining characters
        style_mods = ''.join(c for c in pin_type_with_mods if not c.isalpha())

        # Convert SPD type code to kipart type
        pin_type = SPD_TYPE_MAP.get(pin_type_code, 'passive')

        # Parse modifiers
        # Build up style based on modifiers (* = inverted, > = clock)
        try:
            style = {SPD_STYLE_MAP[mod] for mod in style_mods}
        except KeyError as e:
            raise ValueError(f"Unsupported pin modifier: {e.args[0]} in {pin_type_with_mods}")
        pin_hidden = 'no'
        if 'hidden' in style:
            pin_hidden = 'yes'
            style.discard('hidden')  # Hidden is not a style, it's a separate column
        if 'low' in style:
            style.add(pin_type)
        try:
            pin_style = STYLE_TO_KICAD[frozenset(style)]
        except KeyError:
            raise ValueError(f"Unsupported combination of pin modifiers: {pin_type_with_mods}")

        pin_name = parts[1]
        pin_numbers = parts[2:]

        # Create a row for each pin number (for repetitive pins)
        # If there is only one pin number, keep name as-is
        # If there are multiple pin numbers, we need to handle naming:
        #   - If pin name ends with a number (e.g., "a5"), then start incrementing
        #     from that number for each pin number (a5, a6, a7...).
        #   - If pin name does not end with a number, use name as-is for all pins.
        num_pin_numbers = len(pin_numbers)
        start_index_match = re.search(r'(\D+)(\d+)$', pin_name)

        if num_pin_numbers == 1:
            # Single pin number - use name as-is
            for pin_num in pin_numbers:
                if has_units:
                    csv_rows.append(
                        [pin_num, pin_type, pin_name, current_side,
                         pin_style, pin_hidden, current_unit]
                    )
                else:
                    csv_rows.append(
                        [pin_num, pin_type, pin_name, current_side,
                         pin_style, pin_hidden]
                    )
        else:
            # Multiple pin numbers - determine starting index for naming
            if start_index_match:
                pin_name_base = start_index_match.group(1)
                start_index = int(start_index_match.group(2))
                # Create a row for each pin number with incremented index
                for index, pin_num in enumerate(pin_numbers, start_index):
                    if has_units:
                        csv_rows.append(
                            [pin_num, pin_type, f"{pin_name_base}{index}",
                             current_side, pin_style, pin_hidden, current_unit]
                        )
                    else:
                        csv_rows.append(
                            [pin_num, pin_type, f"{pin_name_base}{index}",
                             current_side, pin_style, pin_hidden]
                        )
            else:
                # No numeric suffix - use name as-is for all pins
                for pin_num in pin_numbers:
                    if has_units:
                        csv_rows.append(
                            [pin_num, pin_type, pin_name, current_side,
                             pin_style, pin_hidden, current_unit]
                        )
                    else:
                        csv_rows.append(
                            [pin_num, pin_type, pin_name, current_side,
                             pin_style, pin_hidden]
                        )

    return csv_rows


def spd_to_csv(spd_content: str) -> str:
    """Convert SPD format content to CSV format string."""
    # Parse as file
    from io import StringIO

    # Write to temp file for parsing
    with open('/tmp/spd_temp.txt', 'w') as f:
        f.write(spd_content)

    symbols = parse_spd_file(Path('/tmp/spd_temp.txt'))

    all_csv_rows = []

    for i, symbol_lines in enumerate(symbols):
        csv_rows = convert_spd_symbol(symbol_lines)
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
        description='Convert SPD symbol description files to CSV format for kipart.'
    )
    parser.add_argument(
        'input_files',
        nargs='+',
        help='SPD format input files'
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
