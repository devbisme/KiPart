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
    'read_row_file',
    'read_symbol_rows',
    'generate_symbol',
    'generate_symbol_lib',
    'add_quotes',
]

import csv
import math
import pandas as pd
import os
from simp_sexp import Sexp

# Constants for layout calculations
FONT_SIZE = 1.27  # Default font size for pin names and numbers
GRID_SPACING = 2.54  # Grid spacing for aligning pins and symbols
PIN_LENGTH = 4 * GRID_SPACING  # Standard pin length in KiCad
STROKE_WIDTH = 0.254  # Stroke width for symbol outlines
SIDE_CLEARANCE = GRID_SPACING/2  # Clearance between the endpoint of a side and the closest pin
PIN_OFFSET = SIDE_CLEARANCE + GRID_SPACING/2

# ===== Basic Utility Functions =====

def gridify(value, grid_spacing=GRID_SPACING):
    """
    Round a value to the nearest grid spacing.

    Args:
        value (float): The value to round.
        grid_spacing (float, optional): The grid spacing to use for rounding. Defaults to GRID_SPACING.

    Returns:
        float: The rounded value.
    """
    return math.ceil(value / grid_spacing) * grid_spacing

def get_text_bounding_box(text, alt_pin_delim=None, font_size=FONT_SIZE):
    """
    Calculate the bounding box for a text string based on font size.

    The bounding box dimensions will be extended to the nearest grid spacing
    so its height and width will always be an integer number of GRID_SPACING units.

    Args:
        text (str): The text to measure.
        alt_pin_delim (str, optional): Delimiter character for splitting
            a complete pin name into alternatives. Defaults to None (no splitting).
        font_size (float, optional): Font size in mm. Defaults to FONT_SIZE (1.27).

    Returns:
        tuple: (width, height) of the text bounding box in mm.
    """
    # Approximate character width as 60% of font size for monospaced fonts
    char_width = font_size * 0.6
    char_height = font_size

    # If using alternate pin names, then the bounding box width
    # is the length of the longest alternate name.
    # Otherwise, the bounding box width is the length of the text.
    alternates = text.split(alt_pin_delim)
    if not alternates:
        text_len = 0
    else:
        text_len = max(len(alt) for alt in alternates)

    width = text_len * char_width
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

def yntf_to_yesno(value):
    """
    Convert a YES-NO-TRUE-FALSE string to a boolean value.

    Args:
        value (str): String to convert.

    Returns:
        bool: True if the string is 'yes', 'y', 'true', 't', '1', or 1 (numeric); False otherwise.
    """
    value = value.lower()
    if value in ['yes', 'y', 'true', 't', '1', 1]:
        return 'yes'
    if value in ['no', 'n', 'false', 'f', '0', 0]:
        return 'no'
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

def str_to_side(value):
    """
    Convert a string to a standardized pin side.
    
    Maps various string representations of pin sides to their canonical KiCad equivalents.
    
    Args:
        value (str): The string describing the side of the symbol the pin is on.
        
    Returns:
        str: Canonical KiCad pin side ('left', 'right', 'top', 'bottom')
        
    Raises:
        ValueError: If the input string doesn't match any known pin side.
    """
    value = value.strip().lower()
    if value in ("left", "l"):
        return "left"
    if value in ("right", "r"):
        return "right"
    if value in ("top", "t"):
        return "top"
    if value in ("bottom", "b"):
        return "bottom"
    raise ValueError(f"Invalid value for side: {value}")

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
    quote_elements = [
        ("kicad_symbol_lib/generator", 2),
        ("kicad_symbol_lib/generator_version", 2),
        ("symbol", 2),
        ("symbol/extends", 2),
        ("symbol/property", None),
        ("pin/name", 2),
        ("pin/number", 2),
        ("text", None),
        ("pin/alternate", 2)
        ]
    # Apply quoting to each element type in the S-expression
    for search_name, stop_idx in quote_elements:
        sexp.add_quotes(search_name, stop_idx=stop_idx, ignore_case=True)

# ===== File Handling Functions =====

def read_row_file(input_file):
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

    current_symbol_rows = []
    for row in rows:
        if not row or all(cell.strip() == '' for cell in row):
            if current_symbol_rows:
                symbols.append(current_symbol_rows)
            current_symbol_rows = []
        else:
            current_symbol_rows.append(row)
        
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
                name_hidden = yntf_to_yesno(name_hidden[0][1])
            else:
                name_hidden = False
            num_hidden = pin.search('/pin/number/effects/hidden', ignore_case=True)
            if num_hidden:
                num_hidden = yntf_to_yesno(num_hidden[0][1])
            else:
                num_hidden = False
            hidden = "yes" if name_hidden=='yes' and num_hidden=='yes' else "no"
            rows.append([
                number, name, type_, side, unit_id, style, hidden
            ])

    return rows

# ===== Symbol Generation Functions =====

def create_pin_sexp(pin, x, y, orientation, pin_length, alt_pin_delim=None):
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
        alt_pin_delim (str, optional): Delimiter for splitting pin names
            into alternatives. Defaults to None (no splitting).
        
    Returns:
        Sexp: S-expression representing a complete pin definition.
    """
    pin_sexp = Sexp(['pin', pin['type'], pin['style']])
    pin_sexp.append(['at', x, y, orientation])
    pin_sexp.append(['length', pin_length])

    # Add pin name   
    names = pin['name'].split(alt_pin_delim)
    name_sexp = Sexp(['name', names[0]])
    effects_sexp = Sexp(['effects'])
    font_sexp = Sexp(['font'])
    font_sexp.append(['size', 1.27, 1.27])
    effects_sexp.append(font_sexp)
    if pin['hidden'].lower() in ['1', 'true', 'yes']:
        effects_sexp.append(['hide', 'yes'])
    name_sexp.append(effects_sexp)
    pin_sexp.append(name_sexp)
    
    # Add pin number
    number_sexp = Sexp(['number', pin['number']])
    effects_sexp = Sexp(['effects'])
    font_sexp = Sexp(['font'])
    font_sexp.append(['size', 1.27, 1.27])
    effects_sexp.append(font_sexp)
    if pin['hidden'].lower() in ['1', 'true', 'yes']:
        effects_sexp.append(['hide', 'yes'])
    number_sexp.append(effects_sexp)
    pin_sexp.append(number_sexp)

    # Add alternate names
    for name in names[1:]:
        pin_sexp.append(['alternate', name, pin['type'], pin['style']])
    
    return pin_sexp

def generate_symbol(symbol_rows, sort_by='row', reverse=False, default_side='left', alt_pin_delim=None):
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
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                               alternatives. Defaults to '' (no splitting).

    Returns:
        Sexp: KiCad symbol as an Sexp object.

    Raises:
        ValueError: If the part name is invalid, required columns are missing, or no valid pins are defined.
    """

    # Define the origin for the symbol coordinates
    x0, y0 = 0, 0

    # Extract part name from the first row
    part_name = symbol_rows[0][0].strip()
    if not part_name:
        raise ValueError("Invalid part name in symbol rows")

    # Begin constructing Sexp object
    symbol_sexp = Sexp(['symbol', part_name])

    # Add basic symbol attributes
    symbol_sexp.append(['exclude_from_sim', 'no'])
    symbol_sexp.append(['in_bom', 'yes'])
    symbol_sexp.append(['on_board', 'yes'])

    # Enter default properties. User-specified property values will override these.
    # The entries in the property list are [value, y coord, text justification, hidden].
    properties = {
        'Reference':     ['U',       x0, -y0 + 1.27,  'right', 'no'],
        'Value':         [part_name, x0, -y0 - 1.27,  'right', 'no'],
        'Footprint':     ['',        x0, -y0 + 0,     'right', 'yes'],
        'Datasheet':     ['',        x0, -y0 + 0,     'right', 'yes'],
        'Description':   ['',        x0, -y0 + 0,     'left',  'yes'],
        'ki_keywords':   ['',        x0, -y0 + 0,     'left',  'yes'],
        'ki_locked':     ['',        x0, -y0 + 0,     'left',  'yes'],
        'ki_fp_filters': ['',        x0, -y0 + 0,     'left',  'yes'],
    }

    # Extract user-specified properties between part name and pin data column names
    row_idx = 1
    for row in symbol_rows[1:]:
        if len(row) == 2 and row[0].strip().endswith(':'):
            row_idx += 1
            label = row[0].strip()[:-1] # Remove trailing ':'
            value = row[1].strip()
            # Convert the user-specified property label to the canonical label used by KiCad.
            try:
                label = {
                    'ref': 'Reference',
                    'reference': 'Reference',
                    'value': 'Value',
                    'val': 'Value',
                    'footprint': 'Footprint',
                    'fp': 'Footprint',
                    'datasheet': 'Datasheet',
                    'description': 'Description',
                    'desc': 'Description',
                    'keywords': 'ki_keywords',
                    'locked': 'ki_locked',
                    'filters': 'ki_fp_filters',
                    'fp_filters': 'ki_fp_filters',
                }[label.lower()]
            except KeyError:
                raise KeyError(f"Invalid property label '{label}' in part {part_name}")
            properties[label][0] = value
        else:
            # End of property rows, break out of the loop
            break

    # Add completed set of properties to the symbol Sexp
    for name, [value, x, y, justify, hide] in properties.items():
        symbol_sexp.append(['property', name, value,
                         ['at', x, y, 0],
                         ['effects', 
                            ['font', ['size', 1.27, 1.27]],
                            ['justify', justify],
                            ['hide', hide]]])

    # Process pin data starting after the header
    pins = []
    header = [col.strip().lower() for col in symbol_rows[row_idx]]
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

    # Check to make sure there are no unmatched column names
    for col in header:
        if col not in column_map:
            raise ValueError(f"Unrecognized column '{col}' in header for part {part_name}")

    # Step past the row of column names to get to the pin data
    row_idx = row_idx + 1

    # Collect pin data with defaults for optional fields
    for idx, row in enumerate(symbol_rows[row_idx:]):
        pin_data = {
            'number': row[column_map['pin']].strip(),
            'name': row[column_map['name']].strip(),
            'unit': row[column_map['unit']].strip() if 'unit' in column_map and row[column_map['unit']].strip() else '1',
            'side': str_to_side(row[column_map['side']].strip().lower()) if 'side' in column_map and row[column_map['side']].strip() else default_side,
            'type': str_to_type(row[column_map['type']]) if 'type' in column_map and row[column_map['type']].strip() else 'passive',
            'style': str_to_style(row[column_map['style']]) if 'style' in column_map and row[column_map['style']].strip() else 'line',
            'hidden': yntf_to_yesno(row[column_map['hidden']].strip()) if 'hidden' in column_map and row[column_map['hidden']].strip() else 'no',
            'row_index': idx  # Store original row index for row sorting
        }
        pins.append(pin_data)

    # Validate that at least one valid pin exists
    if not any(pin['number'] != '*' for pin in pins):
        raise ValueError(f"No valid pins defined for part {part_name} (all pins are placeholders)")

    # Group pins by the unit and side of the unit they're in.
    units = {}
    for pin in pins:
        unit_id = pin['unit']
        if unit_id not in units:
            units[unit_id] = {'left': [], 'right': [], 'top': [], 'bottom': []}
        if pin['side'] in units[unit_id]:
            units[unit_id][pin['side']].append(pin)
        else:
            raise ValueError(f"Invalid side '{pin['side']}' for pin {pin['number']} in unit {unit_name} of part {part_name}")

    # Create the Sexp for each unit and add it to the symbol Sexp.
    for unit_id, unit in units.items():

        # Convert unit name to a number because that's what KiCad wants.
        unit_num = list(units.keys()).index(unit_id) + 1
        total_unit_name = f"{part_name}_{unit_num}_1"

        # Begin instantiating the Sexp for this unit of the symbol.
        unit_sexp = Sexp(['symbol', total_unit_name])

        # Calculate dimensions for each side of the symbol unit based on pin counts and text sizes.
        # At this point, we assume each side is oriented with horizontal pins
        # running from top to bottom of a vertical side. We'll account for the
        # top and bottom sides later.
        bbox = {}
        for side, pins in unit.items():
            bbox[side] = {'width': 0, 'height': 0}
            for pin in pins:
                if pin['number'] == '*':
                    w, h = get_text_bounding_box('')
                else:
                    w, h = get_text_bounding_box(pin['name'], alt_pin_delim=alt_pin_delim)
                bbox[side]['width'] = max(bbox[side]['width'], w)
                bbox[side]['height'] += h

            # Make the bounding box dimensions a multiple of the grid spacing.
            bbox[side]['width'] = gridify(bbox[side]['width'])
            bbox[side]['height'] = gridify(bbox[side]['height'])
            
            # Add clearance at the top and bottom of the of the side.
            bbox[side]['height'] += 2 * SIDE_CLEARANCE

        # Now account for the top and bottom sides by switching their width and height.
        for side in ['top', 'bottom']:
            bbx = bbox[side]
            bbx['width'], bbx['height'] = bbx['height'], bbx['width']

        # Compute the bounding box for the entire unit.

        unit_width = 2 * max(bbox['left']['width'], bbox['right']['width']) + max(bbox['top']['width'], bbox['bottom']['width'])    
        unit_height = 2 * max(bbox['top']['height'], bbox['bottom']['height']) + max(bbox['left']['height'], bbox['right']['height'])
        tb_offset = max(bbox['top']['height'], bbox['bottom']['height'])
        lr_offset = max(bbox['left']['width'], bbox['right']['width'])

        # Define the origin for the unit coordinates
        x1, y1 = x0 + unit_width, y0 + unit_height 

        # Define the rectanglular outline for the unit
        rect_sexp = Sexp(['rectangle',
                          ['start', x0, -y0],
                          ['end', x1, -y1],
                          ['stroke', ['width', STROKE_WIDTH], ['type', 'solid']],
                          ['fill', ['type', 'background']],
                          ])
        # rect_sexp = Sexp(['polyline',
        #                   ['pts', ['xy', x0, y0], ['xy', x0, y1], ['xy', x1, y1], ['xy', x1, y0], ['xy', x0, y0]],
        #                   ['stroke', ['width', STROKE_WIDTH], ['type', 'solid']],
        #                   ['fill', ['type', 'background']],
        #                   ])
        # Add the rectangle to the unit Sexp
        unit_sexp.append(rect_sexp)

        # Process pins for each side
        for side, pin_list in unit.items():

            # Sort pins based on user-specified criteria
            if sort_by == 'num':
                pin_list.sort(key=lambda p: parse_mixed_string(p['number']), reverse=reverse)
            elif sort_by == 'name':
                pin_list.sort(key=lambda p: parse_mixed_string(p['name']) if p['number'] != '*' else (chr(0x10FFFF), float('inf')), reverse=reverse)
            elif sort_by == 'row':
                pin_list.sort(key=lambda p: p['row_index'], reverse=reverse)

            # count = len([pin for pin in pin_list if pin['number'] != '*'])
            # if count == 0:
            #     continue

            if side == 'left':
                x = x0 - PIN_LENGTH
                y = -y0 - PIN_OFFSET - tb_offset
                orientation = 0
                for idx, pin in enumerate(pin_list):
                    if pin['number'] != '*':
                        unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                    y -= GRID_SPACING

            elif side == 'right':
                x = x1 + PIN_LENGTH
                y = -y0 - PIN_OFFSET - tb_offset
                orientation = 180
                for idx, pin in enumerate(pin_list):
                    if pin['number'] != '*':
                        unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                    y -= GRID_SPACING

            elif side == 'top':
                x = x0 + PIN_OFFSET + lr_offset
                y = -y0 + PIN_LENGTH
                orientation = 270
                for idx, pin in enumerate(pin_list):
                    if pin['number'] != '*':
                        unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                    x += GRID_SPACING

            elif side == 'bottom':
                x = x0 + PIN_OFFSET + lr_offset
                y = -y1 - PIN_LENGTH
                orientation = 90
                for idx, pin in enumerate(pin_list):
                    if pin['number'] != '*':
                        unit_sexp.append(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                    x += GRID_SPACING

        symbol_sexp.append(unit_sexp)

    symbol_sexp.append(['embedded_fonts', 'no'])

    return symbol_sexp

def generate_symbol_lib(rows, sort_by='row', reverse=False, default_side='left', alt_pin_delim=None):
    """
    Generate a complete KiCad symbol library S-expression from CSV or Excel data.
    
    This function processes rows of data to create multiple symbols and combines them 
    into a complete KiCad library with appropriate metadata.
    
    Args:
        rows (list of list): Raw CSV rows containing one or more symbols.
        sort_by (str, optional): Sort pins by 'row' (input order), 'num' (pin number),
                                or 'name' (pin name). Defaults to 'row'.
        reverse (bool, optional): Reverse the sort order. Defaults to False.
        default_side (str, optional): Default side for pins without a side specified.
                                     Defaults to 'left'.
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                      alternatives. Defaults to None (no splitting).
    
    Returns:
        Sexp: Complete KiCad symbol library as an Sexp object.
    
    Raises:
        ValueError: If no valid symbols are found in the input rows.
    """

    # Create the library S-expression container
    symbol_lib = Sexp(['kicad_symbol_lib',
                     ['version', '20241209'],
                     ['generator', 'kicad_symbol_editor'],
                     ['generator_version', '8.0']])

    # Group rows into individual symbols
    symbol_row_groups = read_symbol_rows(rows)
    
    # Process each symbol and add it to the library
    for symbol_rows in symbol_row_groups:
        try:
            symbol = generate_symbol(
                symbol_rows, 
                sort_by=sort_by, 
                reverse=reverse, 
                default_side=default_side,
                alt_pin_delim=alt_pin_delim
            )
            symbol_lib.append(symbol)
        except Exception as e:
            # Get the symbol name from the first row if available
            symbol_name = symbol_rows[0][0] if symbol_rows and symbol_rows[0] else "Unknown"
            print(f"Error processing symbol '{symbol_name}': {e}")
            # Continue with the next symbol
    
    # Add quotes to string values that need them
    add_quotes(symbol_lib)
    
    # Check if we generated any valid symbols
    if not extract_symbols_from_lib(symbol_lib):  # No symbols found
        raise ValueError("No valid symbols were generated from the input data")
    
    return symbol_lib
