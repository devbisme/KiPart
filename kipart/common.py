"""
KiCad Symbol Library Common Utilities

This module provides utility functions for generating and parsing KiCad symbol
libraries. It supports creating symbol S-expressions from CSV/Excel data and
parsing S-expressions into CSV-compatible data. Used by `kipart.py` for library
generation and `kilib2csv.py` for library parsing.

Dependencies:
- simp_sexp: For parsing and manipulating S-expressions.
- pandas: For reading Excel files (requires openpyxl for .xlsx support).
- Standard library: csv, math, os, sys, re.
"""

__all__ = [
    'get_text_bounding_box',
    'parse_mixed_string',
    'extract_symbols_from_lib',
    'symbol_to_csv_rows',
    'open_input_file',
    'read_symbol_rows',
    'generate_symbol',
    'add_quotes',
]

import csv
import math
import pandas as pd
import os
import sys
import re
from simp_sexp import Sexp

# Constants for layout calculations
FONT_SIZE = 1.27  # Default font size for pin names and numbers
PIN_LENGTH = 5.08  # Standard pin length in KiCad
GRID_SPACING = 2.54  # Grid spacing for aligning pins and symbols
TEXT_CLEARANCE = 0.5  # Clearance between text and symbol boundaries

# ===== Basic Utility Functions =====

def get_text_bounding_box(text, font_size=FONT_SIZE):
    """
    Calculate the bounding box for a text string based on font size.

    Args:
        text (str): The text to measure.
        font_size (float, optional): Font size in mm. Defaults to FONT_SIZE (1.27).

    Returns:
        tuple: (width, height) of the text bounding box in mm.
    """
    # Approximate character width as 60% of font size for monospaced fonts
    char_width = font_size * 0.6
    char_height = font_size
    width = len(text) * char_width
    height = char_height
    return width, height

def parse_mixed_string(s):
    """
    Parse a string into a tuple for sorting, handling mixed alphanumeric content.

    Used for sorting pin numbers or names (e.g., 'A1', '10B') to ensure natural order.

    Args:
        s (str): String to parse (e.g., pin number or name).

    Returns:
        tuple: Parsed components (strings and integers) for sorting.
    """
    # Handle placeholder pin number "*". Return the largest possible tuple so it will always be sorted last.
    if s == '*':
        return (chr(0x10FFFF), float('inf'))

    # Split into alternating alphabetic and numeric parts
    parts = []
    current = ''
    is_numeric = False

    # Prepend chr(0) for strings starting with a digit to ensure consistent sorting
    if s and s[0].isdigit():
        parts.append(chr(0))

    for char in s:
        if char.isdigit() == is_numeric:
            current += char
        else:
            if current:
                parts.append(int(current) if is_numeric else current)
            current = char
            is_numeric = char.isdigit()

    if current:
        parts.append(int(current) if is_numeric else current)

    return tuple(parts) if parts else (s,)

def yntf_to_bool(value):
    """
    Convert a YES-NO-TRUE-FALSE string to a boolean value.

    Args:
        value (str): String to convert.

    Returns:
        bool: True if the string is 'yes', 'y', 'true', 't', '1', or 1 (numeric); False otherwise.
    """
    value = value.lower()
    if value in ['yes', 'y', 'true', 't', '1', 1]:
        return True
    if value in ['no', 'n', 'false', 'f', '0', 0]:
        return False
    raise ValueError(f"Invalid value for YES-NO-TRUE-FALSE string: {value}")

def str_to_type(value):
    """
    Convert a string to a standardized pin type.
    
    Maps various string representations of pin types to their canonical KiCad equivalents.
    
    Args:
        value (str): The string describing the pin type.
        
    Returns:
        str: Canonical KiCad pin type (input, output, bidirectional, etc.)
        
    Raises:
        ValueError: If the input string doesn't match any known pin type.
    """
    value = value.strip().lower()
    if value in ("input", "inp", "in", "clk"):
        return "input"
    if value in ("output", "out", "outp"):
        return "output"
    if value in ("bidirectional", "bidir", "bi", "inout", "io", "iop"):
        return "bidirectional"
    if value in ("tri-state", "tri", "tri_state", "tristate"):
        return "tri_state"
    if value in ("passive", "pass"):
        return "passive"
    if value in ("free",):
        return "free"
    if value in ("unspecified", "un", "analog"):
        return "unspecified"
    if value in ("power_in", "pwr_in", "pwrin", "power", "pwr", "ground", "gnd"):
        return "power_in"
    if value in ("power_out", "pwr_out", "pwrout", "pwr_o"):
        return "power_out"
    if value in ("open_collector", "opencollector", "open_coll", "opencoll", "oc"):
        return "open_collector"
    if value in ("open_emitter", "openemitter", "open_emit", "openemit", "oe"):
        return "open_collector"
    if value in ("no_connect", "noconnect", "no_conn", "noconn", "nc"):
        return "no_connect"
    raise ValueError(f"Invalid value for type: {value}")

def str_to_style(value):
    """
    Convert a string to a standardized pin style.
    
    Maps various string representations of pin styles to their canonical KiCad equivalents.
    
    Args:
        value (str): The string describing the pin style.
        
    Returns:
        str: Canonical KiCad pin style (line, inverted, clock, etc.)
        
    Raises:
        ValueError: If the input string doesn't match any known pin style.
    """
    value = value.strip().lower()
    if value in ("line", ""):
        return "line"
    if value in ("inverted", "inv", "~", "#"):
        return "inverted"
    if value in ("clock", "clk", "rising_clk"):
        return "clock"
    if value in ("inverted_clock", "inv_clk", "clk_b", "clk_n", "~clk", "#clk"):
        return "inverted_clock"
    if value in ("input_low", "inp_low", "in_lw", "in_b", "in_n", "~in", "#in"):
        return "input_low"
    if value in ("clock_low", "clk_low", "clk_lw", "clk_b", "clk_n", "~clk", "#clk"):
        return "inverted_clock"
    if value in ("output_low", "outp_low", "out_lw", "out_b", "out_n", "~out", "#out"):
        return "output_low"
    if value in ("edge_clock_high",):
        return "edge_clock_high"
    if value in ("non_logic", "nl", "analog"):
        return "non_logic"
    raise ValueError(f"Invalid value for style: {value}")

def add_quotes(sexp):
    """
    Add quotes to specific elements in an S-expression.
    
    This function adds quotes around the values of specific elements in the
    given S-expression object. The elements that get quoted are defined in
    the internal list 'quote_elements'.
    
    Args:
        sexp: An S-expression object that has an 'add_quotes' method.
        
    Returns:
        None. The S-expression is modified in-place.
    """

    # List of S-expression elements that require quoted values
    quote_elements = ["generator", "generator_version", "symbol", "extends", "property", "name", "number", "text"]
    # Apply quoting to each element type in the S-expression
    for elem in quote_elements:
        sexp.add_quotes(elem, ignore_case=True)

# ===== File Handling Functions =====

def open_input_file(input_file):
    """
    Read CSV or Excel file into a list of rows.

    Supports .csv, .xlsx, and .xls formats, using `pandas` for Excel files.

    Args:
        input_file (str): Path to the input file.

    Returns:
        list of list: Rows from the file, with each row as a list of strings.

    Raises:
        ValueError: If the file extension is unsupported.
    """
    _, ext = os.path.splitext(input_file)
    ext = ext.lower()

    # Use csv module for CSV files, pandas for Excel files
    if ext in ['.csv']:
        with open(input_file, newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
    elif ext in ['.xlsx', '.xls']:
        # Use header=None so the first row is treated as data.
        df = pd.read_excel(input_file, sheet_name=0, dtype=str, header=None)
        rows = df.fillna('').values.tolist()
    else:
        raise ValueError(f"Unsupported file extension: {ext}. Use .csv, .xlsx, or .xls")

    return rows

def read_symbol_rows(rows):
    """
    Group CSV rows into symbols based on part names and blank lines.

    Each symbol consists of a part name, optional properties, a header, and pin data.

    Args:
        rows (list of list): Raw CSV rows from the input file.

    Returns:
        list of list: List of symbol data, where each item is a list of rows for a symbol.

    Raises:
        ValueError: If no valid symbols are found.
    """
    symbols = []
    current_symbol_rows = None
    
    # Group rows by symbols, using blank lines as separators
    row_idx = 0
    while row_idx < len(rows):
        row = rows[row_idx]
        if not row or all(cell.strip() == '' for cell in row):
            if current_symbol_rows:
                symbols.append(current_symbol_rows)
                current_symbol_rows = None
            row_idx += 1
            continue
        
        if not current_symbol_rows:
            current_symbol_rows = [row]
            row_idx += 1
        else:
            current_symbol_rows.append(row)
            row_idx += 1
    
    if current_symbol_rows:
        symbols.append(current_symbol_rows)
    
    if not symbols:
        raise ValueError("No valid symbols found in input file")
    
    return symbols

# ===== Symbol Parsing Functions =====

def extract_symbols_from_lib(symbol_lib):
    """
    Extract individual symbol definitions from a KiCad symbol library S-expression.

    Uses `simp_sexp` to parse the library into a nested structure, avoiding manual
    parenthesis counting for robustness.

    Args:
        symbol_lib (str): S-expression string representing a KiCad symbol library.

    Returns:
        list of Sexp: List of Sexp symbols extracted from the S-expression.
    """

    # Parse the library, search for part symbols, and return a list Sexp objects, one for each part.
    return Sexp(symbol_lib).search("/kicad_symbol_lib/symbol")

def symbol_to_csv_rows(symbol):
    """
    Convert a Sexp object for a KiCad symbol into CSV rows.

    Parses a simp_sexp Sexp to extract symbol name, properties, and
    pin details, including a header row for pin data columns.

    Args:
        symbol (Sexp): Sexp object for a single symbol.

    Returns:
        list of list: CSV rows where each row is a list of strings:
            - [symbol_name, ""] for the symbol name.
            - [prop_name + ':', prop_value] for each property.
            - ["pin", "name", "type", "side", "unit", "style", "hidden"] for pin column labels.
            - [pin_number, pin_name, pin_type, pin_side, pin_unit, pin_style, pin_hidden] for each pin.
    """

    # Extract top-level symbol data
    symbol_name = symbol.search('/symbol', ignore_case=True)[0][1]
    properties = symbol.search('/symbol/property', ignore_case=True)
    units = symbol.search('/symbol/symbol', ignore_case=True)

    # Generate CSV rows starting with symbol name and properties
    rows = []
    rows.append([symbol_name, ""])
    for _, prop_name, prop_value in properties:
        rows.append([prop_name + ':', prop_value])

    # Add pin data column labels
    rows.append(["pin", "name", "type", "side", "unit", "style", "hidden"])

    # Process units and pins
    for unit_id, unit in enumerate(units, 1):
        unit_id = symbol_name + "_" + str(unit_id)
        pins = unit.search('/symbol/pin', ignore_case=True)
        for pin in pins:
            number = pin.search('/pin/number', ignore_case=True)[0][1]
            name = pin.search('/pin/name', ignore_case=True)[0][1]
            type_ = pin[1]
            style = pin[2]
            orientation = pin.search('/pin/at', ignore_case=True)[0][3]
            side = {0: 'left', 90: 'bottom', 180: 'right', 270: 'top'}[orientation]
            name_hidden = pin.search('/pin/name/effects/hidden', ignore_case=True)
            if name_hidden:
                name_hidden = yntf_to_bool(name_hidden[0][1])
            else:
                name_hidden = False
            num_hidden = pin.search('/pin/number/effects/hidden', ignore_case=True)
            if num_hidden:
                num_hidden = yntf_to_bool(num_hidden[0][1])
            else:
                num_hidden = False
            hidden = "yes" if name_hidden and num_hidden else "no"
            rows.append([
                number, name, type_, side, unit_id, style, hidden
            ])

    return rows

# ===== Symbol Generation Functions =====

def create_pin_sexp(pin, x, y, orientation, pin_length):
    """
    Create a pin S-expression for a KiCad symbol.
    
    Constructs an S-expression structure for a pin with proper name, number,
    position, and visual properties.
    
    Args:
        pin (dict): Dictionary containing pin properties:
                   'type', 'style', 'name', 'number', 'hidden', etc.
        x (float): X coordinate for the pin connection point.
        y (float): Y coordinate for the pin connection point.
        orientation (int): Pin orientation in degrees (0, 90, 180, or 270).
        pin_length (float): Length of the pin line in mm.
        
    Returns:
        Sexp: S-expression representing a complete pin definition.
    """
    pin_sexp = Sexp(['pin', pin['type'], pin['style']])
    pin_sexp.append(['at', x, y, orientation])
    pin_sexp.append(['length', pin_length])
    
    # Add name sub-expression
    name_sexp = Sexp(['name', pin['name']])
    effects_sexp = Sexp(['effects'])
    font_sexp = Sexp(['font'])
    font_sexp.append(['size', 1.27, 1.27])
    effects_sexp.append(font_sexp)
    if pin['hidden'].lower() in ['1', 'true', 'yes']:
        effects_sexp.append(['hide', 'yes'])
    name_sexp.append(effects_sexp)
    pin_sexp.append(name_sexp)
    
    # Add number sub-expression
    number_sexp = Sexp(['number', pin['number']])
    effects_sexp = Sexp(['effects'])
    font_sexp = Sexp(['font'])
    font_sexp.append(['size', 1.27, 1.27])
    effects_sexp.append(font_sexp)
    if pin['hidden'].lower() in ['1', 'true', 'yes']:
        effects_sexp.append(['hide', 'yes'])
    number_sexp.append(effects_sexp)
    pin_sexp.append(number_sexp)
    
    return pin_sexp

def generate_symbol(symbol_rows, sort_by='row', reverse=False, default_side='left'):
    """
    Generate a KiCad symbol S-expression from CSV rows.

    Constructs an Sexp object for the symbol with precise control over pin placement and
    symbol layout, using grid-based positioning.

    Args:
        symbol_rows (list of list): CSV rows for a single symbol, including part name,
                                   properties, header, and pin data.
        sort_by (str, optional): Sort pins by 'row' (input order), 'num' (pin number),
                                 or 'name' (pin name). Defaults to 'row'.
        reverse (bool, optional): Reverse the sort order. Defaults to False.
        default_side (str, optional): Default side for pins without a side specified.
                                     Defaults to 'left'.

    Returns:
        Sexp: KiCad symbol as an Sexp object.

    Raises:
        ValueError: If the part name is invalid, required columns are missing, or no valid pins are defined.
    """
    # Extract part name from the first row
    part_name = symbol_rows[0][0].strip()
    if not part_name:
        raise ValueError("Invalid part name in symbol rows")

    # Extract properties between part name and header
    additional_properties = []
    header_idx = 1
    while header_idx < len(symbol_rows):
        row = symbol_rows[header_idx]
        if len(row) >= 2 and row[0].strip().endswith(':'):
            label = row[0].strip()[:-1]  # Remove trailing ':'
            value = row[1].strip() if len(row) > 1 else ''
            additional_properties.append((label, value))
            header_idx += 1
        else:
            break

    # Process pin data starting after the header
    pins = []
    header = [col.strip().lower() for col in symbol_rows[header_idx]]
    column_map = {}
    required_columns = ['pin', 'name']
    optional_columns = ['unit', 'side', 'type', 'style', 'hidden']

    # Map column names to indices, ensuring required columns exist
    for col in required_columns:
        try:
            column_map[col] = header.index(col)
        except ValueError:
            raise ValueError(f"Required column '{col}' not found in header for part {part_name}")
    for col in optional_columns:
        try:
            column_map[col] = header.index(col)
        except ValueError:
            pass

    # Collect pin data with defaults for optional fields
    for idx, row in enumerate(symbol_rows[header_idx + 1:]):
        if not row or all(cell.strip() == '' for cell in row):
            break
        pin_number = row[column_map['pin']].strip()
        pin_data = {
            'number': pin_number,
            'name': row[column_map['name']].strip(),
            'unit': row[column_map['unit']].strip() if 'unit' in column_map and row[column_map['unit']].strip() else '1',
            'side': row[column_map['side']].strip().lower() if 'side' in column_map and row[column_map['side']].strip() else default_side,
            'type': str_to_type(row[column_map['type']]) if 'type' in column_map and row[column_map['type']].strip() else 'passive',
            'style': str_to_style(row[column_map['style']]) if 'style' in column_map and row[column_map['style']].strip() else 'line',
            'hidden': row[column_map['hidden']].strip() if 'hidden' in column_map and row[column_map['hidden']].strip() else '0',
            'row_index': idx  # Store original row index for row sorting
        }
        pins.append(pin_data)

    # Validate that at least one valid pin exists
    if not any(pin['number'] != '*' for pin in pins):
        raise ValueError(f"No valid pins defined for part {part_name} (all pins are placeholders)")

    # Group pins by unit and side for layout
    units = {}
    for pin in pins:
        unit = pin['unit']
        if unit not in units:
            units[unit] = {'left': [], 'right': [], 'top': [], 'bottom': []}
        if pin['side'] in units[unit]:
            units[unit][pin['side']].append(pin)
        else:
            raise ValueError(f"Invalid side '{pin['side']}' for pin {pin['number']} in part {part_name}")

    # Calculate symbol dimensions based on pin counts and text sizes
    max_left_count = 0
    max_right_count = 0
    max_top_count = 0
    max_bottom_count = 0
    max_left_text_width = 0
    max_right_text_width = 0
    max_top_text_height = 0
    max_bottom_text_height = 0

    for unit, sides in units.items():
        left_count = len(sides['left'])
        right_count = len(sides['right'])
        top_count = len(sides['top'])
        bottom_count = len(sides['bottom'])
        max_left_count = max(max_left_count, left_count)
        max_right_count = max(max_right_count, right_count)
        max_top_count = max(max_top_count, top_count)
        max_bottom_count = max(max_bottom_count, bottom_count)

        # Calculate text bounding boxes for pin names
        for pin in sides['left']:
            if pin['number'] != '*':
                w, _ = get_text_bounding_box(pin['name'])
                max_left_text_width = max(max_left_text_width, w)
        for pin in sides['right']:
            if pin['number'] != '*':
                w, _ = get_text_bounding_box(pin['name'])
                max_right_text_width = max(max_right_text_width, w)
        for pin in sides['top']:
            if pin['number'] != '*':
                _, h = get_text_bounding_box(pin['name'])
                max_top_text_height = max(max_top_text_height, h)
        for pin in sides['bottom']:
            if pin['number'] != '*':
                _, h = get_text_bounding_box(pin['name'])
                max_bottom_text_height = max(max_bottom_text_height, h)

    # Calculate symbol layout on a grid
    pin_grid_width = max(max_top_count, max_bottom_count, 4) * GRID_SPACING
    pin_grid_height = max(max_left_count, max_right_count, 3) * GRID_SPACING

    total_width = pin_grid_width + 2 * GRID_SPACING
    total_height = pin_grid_height + 2 * GRID_SPACING

    grid_width = math.ceil(total_width / GRID_SPACING) * GRID_SPACING
    grid_height = math.ceil(total_height / GRID_SPACING) * GRID_SPACING

    x_min = round((max_left_text_width + PIN_LENGTH + TEXT_CLEARANCE + GRID_SPACING) / GRID_SPACING) * GRID_SPACING
    x_max = x_min + pin_grid_width
    y_max = grid_height / 2
    y_min = -grid_height / 2

    # Begin constructing Sexp object
    symbol_sexp = Sexp(['symbol', part_name])

    # Add basic symbol attributes
    symbol_sexp.append(['exclude_from_sim', 'no'])
    symbol_sexp.append(['in_bom', 'yes'])
    symbol_sexp.append(['on_board', 'yes'])

    # Define default properties with calculated positions
    properties = [
        ('Reference', 'U', 3.81, y_max + 3.81, 'right', False),
        ('Value', part_name, 3.81, y_max + 1.27, 'right', False),
        ('Footprint', '', 3.81, y_max - 1.27, 'right', True),
        ('Datasheet', '', 3.81, y_max - 3.81, 'right', True),
        ('Description', '', 0, 0, '', True),
        ('ki_locked', '', 0, 0, '', True)
    ]

    # Add user-defined properties from input rows
    for label, value in additional_properties:
        properties.append((label, value, 0, 0, '', True))

    # Generate property Sexp objects
    for prop in properties:
        name, value, x, y, justify, hide = prop
        prop_sexp = Sexp(['property', name, value])

        at_sexp = Sexp(['at', x, y, 0])
        prop_sexp.append(at_sexp)

        effects_sexp = Sexp(['effects'])
        font_sexp = Sexp(['font'])
        font_sexp.append(['size', 1.27, 1.27])
        effects_sexp.append(font_sexp)

        if justify:
            effects_sexp.append(['justify', justify])
        if hide:
            effects_sexp.append(['hide', 'yes'])

        prop_sexp.append(effects_sexp)
        symbol_sexp.append(prop_sexp)

    # Generate unit and pin Sexp objects
    for unit, sides in sorted(units.items()):
        # Convert unit name to a number because that's what KiCad wants.
        unit_num = list(units.keys()).index(unit) + 1
        total_unit_name = f"{part_name}_{unit_num}_1"
        unit_sexp = Sexp(['symbol', total_unit_name])

        # Define unit rectangle
        rect_sexp = Sexp(['rectangle'])
        rect_sexp.append(['start', x_min, y_max])
        rect_sexp.append(['end', x_max, y_min])

        stroke_sexp = Sexp(['stroke'])
        stroke_sexp.append(['width', 0.254])
        stroke_sexp.append(['type', 'solid'])
        rect_sexp.append(stroke_sexp)

        fill_sexp = Sexp(['fill'])
        fill_sexp.append(['type', 'background'])
        rect_sexp.append(fill_sexp)

        unit_sexp.append(rect_sexp)

        # Process pins for each side
        for side, pin_list in sides.items():
            # Sort pins based on user-specified criteria
            if sort_by == 'num':
                pin_list.sort(key=lambda p: parse_mixed_string(p['number']), reverse=reverse)
            elif sort_by == 'name':
                pin_list.sort(key=lambda p: parse_mixed_string(p['name']) if p['number'] != '*' else (chr(0x10FFFF), float('inf')), reverse=reverse)
            elif sort_by == 'row':
                pin_list.sort(key=lambda p: p['row_index'], reverse=reverse)

            count = len([pin for pin in pin_list if pin['number'] != '*'])
            if count == 0:
                continue

            if side == 'left':
                total_height = (count - 1) * GRID_SPACING
                start_y = total_height / 2
                start_y = round(start_y / GRID_SPACING) * GRID_SPACING
                for idx, pin in enumerate(pin_list):
                    if pin['number'] == '*':
                        continue
                    y = start_y - idx * GRID_SPACING
                    y = round(y / GRID_SPACING) * GRID_SPACING
                    x = x_min - PIN_LENGTH
                    x = round(x / GRID_SPACING) * GRID_SPACING
                    orientation = 0
                    unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH))

            elif side == 'right':
                total_height = (count - 1) * GRID_SPACING
                start_y = -total_height / 2 if sort_by == 'num' else total_height / 2
                start_y = round(start_y / GRID_SPACING) * GRID_SPACING
                for idx, pin in enumerate(pin_list):
                    if pin['number'] == '*':
                        continue
                    y = start_y + idx * GRID_SPACING if sort_by == 'num' else start_y - idx * GRID_SPACING
                    y = round(y / GRID_SPACING) * GRID_SPACING
                    x = x_max + PIN_LENGTH
                    x = round(x / GRID_SPACING) * GRID_SPACING
                    orientation = 180
                    unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH))

            elif side == 'top':
                total_width = (count - 1) * GRID_SPACING
                start_x = x_max - total_width / 2 if sort_by == 'num' else x_min + total_width / 2
                start_x = round(start_x / GRID_SPACING) * GRID_SPACING
                for idx, pin in enumerate(pin_list):
                    if pin['number'] == '*':
                        continue
                    x = start_x - idx * GRID_SPACING if sort_by == 'num' else x_min + idx * GRID_SPACING
                    x = round(x / GRID_SPACING) * GRID_SPACING
                    y = y_max + PIN_LENGTH
                    y = round(y / GRID_SPACING) * GRID_SPACING
                    orientation = 270
                    unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH))

            elif side == 'bottom':
                total_width = (count - 1) * GRID_SPACING
                start_x = x_min + total_width / 2
                start_x = round(start_x / GRID_SPACING) * GRID_SPACING
                for idx, pin in enumerate(pin_list):
                    if pin['number'] == '*':
                        continue
                    x = start_x - idx * GRID_SPACING
                    x = round(x / GRID_SPACING) * GRID_SPACING
                    y = y_min - PIN_LENGTH
                    y = round(y / GRID_SPACING) * GRID_SPACING
                    orientation = 90
                    unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH))

        symbol_sexp.append(unit_sexp)

    symbol_sexp.append(['embedded_fonts', 'no'])

    return symbol_sexp
