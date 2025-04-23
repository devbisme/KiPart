"""
KiCad Symbol Library Common Utilities

This module provides utility functions for generating and parsing KiCad symbol
libraries. It supports creating symbol S-expressions from CSV/Excel data and
parsing S-expressions into CSV-compatible data. Used by `kipart.py` for library
generation and `kilib2csv.py` for library parsing.

Dependencies:
- sexpdata: For parsing and manipulating S-expressions.
- pandas: For reading Excel files (requires openpyxl for .xlsx support).
- Standard library: csv, math, os, sys, re.
"""

__all__ = [
    'get_text_bounding_box',
    'indent_sexpr',
    'parse_mixed_string',
    'extract_parts_from_sexpr',
    'symbol_sexpr_to_csv_rows',
    'open_input_file',
    'read_symbol_rows',
    'generate_symbol'
]

import csv
import math
import pandas as pd
import os
import sys
import re
from sexpdata import loads, Symbol, dumps

# Constants for layout calculations
FONT_SIZE = 1.27  # Default font size for pin names and numbers
PIN_LENGTH = 5.08  # Standard pin length in KiCad
GRID_SPACING = 2.54  # Grid spacing for aligning pins and symbols
TEXT_CLEARANCE = 0.5  # Clearance between text and symbol boundaries

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

def indent_sexpr(lines, indent_char='\t', indent_level=0):
    """
    Indent S-expression lines based on parenthesis nesting for readability.

    Args:
        lines (list of str): List of S-expression lines to indent.
        indent_char (str, optional): Character to use for indentation. Defaults to '\t'.
        indent_level (int, optional): Initial indentation level. Defaults to 0.

    Returns:
        list of str: Indented S-expression lines.
    """
    result = []
    current_level = indent_level
    
    # Process each line to adjust indentation based on parenthesis
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
            
        # Calculate new indentation level before adding the line
        new_level = current_level
        for char in stripped_line:
            if char == '(':
                new_level += 1
            elif char == ')':
                new_level -= 1
        
        # Use reduced level for lines starting with closing parenthesis
        if stripped_line.startswith(')'):
            result.append(indent_char * (current_level - 1) + stripped_line)
        else:
            result.append(indent_char * current_level + stripped_line)
        
        # Update level for the next line
        current_level = new_level
    
    return result

def parse_mixed_string(s):
    """
    Parse a string into a tuple for sorting, handling mixed alphanumeric content.

    Used for sorting pin numbers or names (e.g., 'A1', '10B') to ensure natural order.

    Args:
        s (str): String to parse (e.g., pin number or name).

    Returns:
        tuple: Parsed components (strings and integers) for sorting.
    """
    # Handle placeholder pin number "*"
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

def extract_parts_from_sexpr(sexpr_lines):
    """
    Extract individual symbol definitions from a KiCad symbol library S-expression.

    Uses `sexpdata` to parse the library into a nested structure, avoiding manual
    parenthesis counting for robustness.

    Args:
        sexpr_lines (list of str): List of S-expression lines for the symbol library.

    Returns:
        dict: Dictionary mapping part names to their complete S-expression strings.
    """
    # Join lines into a single string for parsing
    sexpr_str = '\n'.join(sexpr_lines)

    # Parse S-expression using sexpdata for a structured representation
    parsed = loads(sexpr_str)

    parts = {}

    # Verify the root is a kicad_symbol_lib
    if not isinstance(parsed, list) or parsed[0] != Symbol('kicad_symbol_lib'):
        return parts

    # Extract symbol nodes from the library
    for node in parsed[1:]:
        if isinstance(node, list) and node[0] == Symbol('symbol') and isinstance(node[1], str):
            part_name = node[1]
            part_sexpr = dumps(node, str_as='string')
            parts[part_name] = part_sexpr

    return parts

def symbol_sexpr_to_csv_rows(sexpr):
    """
    Convert a KiCad symbol S-expression into CSV rows.

    Parses the S-expression using `sexpdata` to extract symbol name, properties, and
    pin details, including a header row for pin data columns.

    Args:
        sexpr (str or list of str): S-expression for a single symbol.

    Returns:
        list of list: CSV rows where each row is a list of strings:
            - [symbol_name, ""] for the symbol name.
            - [prop_name + ':', prop_value] for each property.
            - ["pin", "name", "type", "side", "unit", "style", "hidden"] for pin column labels.
            - [pin_number, pin_name, pin_type, pin_side, pin_unit, pin_style, pin_hidden] for each pin.
    """
    # Convert input to a single string if provided as a list
    if isinstance(sexpr, list):
        sexpr = '\n'.join(sexpr)
    
    # Parse S-expression using sexpdata
    parsed = loads(sexpr)
    
    rows = []
    symbol_name = None
    properties = []
    units = []
    
    # Regular expressions retained for potential future validation, though unused with sexpdata
    rect_start_pattern = re.compile(r'^\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*$')
    rect_end_pattern = re.compile(r'^\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)\s*$')
    at_pattern = re.compile(r'^\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)\)\s*$')
    name_pattern = re.compile(r'^\s*\(name\s+"([^"]*)"\s*$')
    number_pattern = re.compile(r'^\s*\(number\s+"([^"]*)"\s*$')
    hide_pattern = re.compile(r'^\s*\(hide\s+yes\)\s*$')
    
    def process_node(node):
        """
        Process a symbol node to extract name, properties, and units.

        Returns:
            tuple: (symbol_name, properties, units)
        """
        if not isinstance(node, list) or node[0] != Symbol('symbol') or not isinstance(node[1], str):
            return None, [], []
        
        name = node[1]
        props = []
        unit_list = []
        unit_id = 0
        
        # Extract properties and unit symbols from the node
        for subnode in node[2:]:
            if isinstance(subnode, list) and subnode[0] == Symbol('property'):
                if len(subnode) >= 3:
                    props.append((subnode[1], subnode[2]))
            elif isinstance(subnode, list) and subnode[0] == Symbol('symbol'):
                unit_id += 1
                unit_list.append({'id': str(unit_id), 'data': subnode})
        
        return name, props, unit_list
    
    # Extract top-level symbol data
    symbol_name, properties, units = process_node(parsed)
    
    # Process units and pins
    for unit in units:
        unit_data = {
            'id': unit['id'],
            'pins': [],
            'x_min': None,
            'x_max': None,
            'y_min': None,
            'y_max': None
        }
        unit_node = unit['data']
        
        # Extract rectangle coordinates and pin details
        for subnode in unit_node[2:]:
            if isinstance(subnode, list) and subnode[0] == Symbol('rectangle'):
                for item in subnode[1:]:
                    if isinstance(item, list) and item[0] == Symbol('start'):
                        unit_data['x_min'] = float(item[1])
                        unit_data['y_max'] = float(item[2])
                    elif isinstance(item, list) and item[0] == Symbol('end'):
                        unit_data['x_max'] = float(item[1])
                        unit_data['y_min'] = float(item[2])
            elif isinstance(subnode, list) and subnode[0] == Symbol('pin'):
                pin_data = {
                    'type': subnode[1].value() if isinstance(subnode[1], Symbol) else subnode[1],
                    'style': subnode[2].value() if isinstance(subnode[2], Symbol) else subnode[2],
                    'number': '',
                    'name': '',
                    'x': 0.0,
                    'y': 0.0,
                    'orientation': 0,
                    'hidden': '0'
                }
                for item in subnode[3:]:
                    if isinstance(item, list) and item[0] == Symbol('at'):
                        pin_data['x'] = float(item[1])
                        pin_data['y'] = float(item[2])
                        pin_data['orientation'] = int(item[3])
                    elif isinstance(item, list) and item[0] == Symbol('name'):
                        pin_data['name'] = item[1]
                    elif isinstance(item, list) and item[0] == Symbol('number'):
                        pin_data['number'] = item[1]
                    elif isinstance(item, list) and item[0] == Symbol('hide'):
                        pin_data['hidden'] = '1'
                
                # Only include valid pins (non-placeholder)
                if pin_data['number'] and pin_data['number'] != '*':
                    unit_data['pins'].append(pin_data)
        
        units[units.index(unit)] = unit_data
    
    # Generate CSV rows
    if symbol_name:
        rows.append([symbol_name, ""])
    
    for prop_name, prop_value in properties:
        rows.append([prop_name + ':', prop_value])
    
    # Add pin data column labels
    rows.append(["pin", "name", "type", "side", "unit", "style", "hidden"])
    
    for unit in units:
        for pin in unit['pins']:
            # Determine pin side based on position and orientation relative to rectangle
            side = 'unknown'
            if (unit['x_min'] is not None and unit['x_max'] is not None and
                unit['y_min'] is not None and unit['y_max'] is not None):
                if pin['orientation'] == 0 and pin['x'] < unit['x_min']:
                    side = 'left'
                elif pin['orientation'] == 180 and pin['x'] > unit['x_max']:
                    side = 'right'
                elif pin['orientation'] == 270 and pin['y'] > unit['y_max']:
                    side = 'top'
                elif pin['orientation'] == 90 and pin['y'] < unit['y_min']:
                    side = 'bottom'
            
            rows.append([
                pin['number'],
                pin['name'],
                pin['type'],
                side,
                unit['id'],
                pin['style'],
                pin['hidden']
            ])
    
    return rows

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

def generate_symbol(symbol_rows, sort_by='row', reverse=False, default_side='left'):
    """
    Generate a KiCad symbol S-expression from CSV rows.

    Constructs the S-expression manually for precise control over pin placement and
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
        list of str: Lines of the KiCad symbol S-expression.

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
            'type': row[column_map['type']].strip().lower() if 'type' in column_map and row[column_map['type']].strip() else 'passive',
            'style': row[column_map['style']].strip() if 'style' in column_map and row[column_map['style']].strip() else 'line',
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
    
    # Begin constructing S-expression
    output = []
    output.append(f'(symbol "{part_name}"')
    output.append('(exclude_from_sim no)')
    output.append('(in_bom yes)')
    output.append('(on_board yes)')
    
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
    
    # Generate property S-expressions
    for prop in properties:
        name, value, x, y, justify, hide = prop
        output.append(f'(property "{name}" "{value}"')
        output.append(f'(at {x} {y} 0)')
        output.append('(effects')
        output.append('(font')
        output.append('(size 1.27 1.27)')
        output.append(')')
        if justify:
            output.append(f'(justify {justify})')
        if hide:
            output.append('(hide yes)')
        output.append(')')
        output.append(')')
    
    # Generate unit and pin S-expressions
    for unit, sides in sorted(units.items()):
        output.append(f'(symbol "{part_name}_{unit}_1"')
        
        # Define unit rectangle
        output.append('(rectangle')
        output.append(f'(start {x_min:.2f} {y_max:.2f})')
        output.append(f'(end {x_max:.2f} {y_min:.2f})')
        output.append('(stroke')
        output.append('(width 0.254)')
        output.append('(type solid)')
        output.append(')')
        output.append('(fill')
        output.append('(type background)')
        output.append(')')
        output.append(')')
        
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
                    output.append(f'(pin {pin["type"]} {pin["style"]}')
                    output.append(f'(at {x:.2f} {y:.2f} {orientation})')
                    output.append(f'(length {PIN_LENGTH})')
                    output.append(f'(name "{pin["name"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(f'(number "{pin["number"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(')')
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
                    output.append(f'(pin {pin["type"]} {pin["style"]}')
                    output.append(f'(at {x:.2f} {y:.2f} {orientation})')
                    output.append(f'(length {PIN_LENGTH})')
                    output.append(f'(name "{pin["name"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(f'(number "{pin["number"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(')')
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
                    output.append(f'(pin {pin["type"]} {pin["style"]}')
                    output.append(f'(at {x:.2f} {y:.2f} {orientation})')
                    output.append(f'(length {PIN_LENGTH})')
                    output.append(f'(name "{pin["name"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(f'(number "{pin["number"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(')')
            elif side == 'bottom':
                total_width = (count - 1) * GRID_SPACING
                start_x = x_min + total_width / 2
                start_x = round(start_x / GRID_SPACING) * GRID_SPACING
                for idx, pin in enumerate(pin_list):
                    if pin['number'] == '*':
                        continue
                    x = start_x + idx * GRID_SPACING
                    x = round(x / GRID_SPACING) * GRID_SPACING
                    y = y_min - PIN_LENGTH
                    y = round(y / GRID_SPACING) * GRID_SPACING
                    orientation = 90
                    output.append(f'(pin {pin["type"]} {pin["style"]}')
                    output.append(f'(at {x:.2f} {y:.2f} {orientation})')
                    output.append(f'(length {PIN_LENGTH})')
                    output.append(f'(name "{pin["name"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(f'(number "{pin["number"]}"')
                    output.append('(effects')
                    output.append('(font')
                    output.append('(size 1.27 1.27)')
                    output.append(')')
                    if pin['hidden'].lower() in ['1', 'true', 'yes']:
                        output.append('(hide yes)')
                    output.append(')')
                    output.append(')')
                    output.append(')')
        
        output.append(')')
    
    output.append('(embedded_fonts no)')
    output.append(')')
    
    return output
