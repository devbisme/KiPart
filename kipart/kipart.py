"""
KiCad Symbol Library Generator and Parser

This module provides utilities for creating KiCad symbol libraries from tabular data
(CSV/Excel) and parsing existing libraries back into tabular format. It supports
bidirectional conversion between KiCad's .kicad_sym format and spreadsheet files.

Main features:
- Generate KiCad symbols from CSV or Excel files with pin definitions
- Parse KiCad symbol libraries into CSV format for editing
- Command-line interfaces for both conversion directions
- Flexible pin sorting, positioning and configuration options

Dependencies:
- simp_sexp: For parsing and manipulating S-expressions
- pandas: For reading Excel files (requires openpyxl for .xlsx support)
- Standard library: csv, math, os, sys, argparse
"""

__all__ = [
    # Basic utility functions
    'gridify',
    'text_width',
    'parse_mixed_string',
    'yntf_to_yesno',
    'str_to_type',
    'str_to_style',
    'str_to_side',
    'add_quotes',
    # File handling functions
    'read_row_file',
    'read_symbol_rows',
    # Symbol library functions
    'empty_symbol_lib',
    'merge_symbol_libs',
    'extract_symbols_from_lib',
    # Symbol parsing functions
    'symbol_to_csv_rows',
    # Symbol generation functions
    'create_rectangle_outline',
    'create_pin_name_outline',
    'create_pin_sexp',
    'generate_symbol',
    'generate_symbol_lib',
    # File conversion functions
    'row_file_to_symbol_lib_file',
    'symbol_lib_file_to_csv_file',
    # Command-line interfaces
    'kipart',
    'kilib2csv',
]

import csv
import math
import pandas as pd
import os
import sys
import argparse
from simp_sexp import Sexp

try:
    from .pckg_info import __version__
except ImportError:
    __version__ = "unknown"

# Constants for layout calculations
FONT_SIZE = 1.27  # Default font size for pin names and numbers
GRID_SPACING = 1.27  # Grid spacing for aligning pins and symbols
PIN_LENGTH = 4 * GRID_SPACING  # Standard pin length in KiCad
PIN_HEIGHT = 2 * GRID_SPACING  # Standard pin height in KiCad
PIN_SPACING = 2 * GRID_SPACING  # Standard pin spacing in KiCad
PIN_NAME_OFFSET = 0.85  # Offset from the end of the pin to the pin name
STROKE_WIDTH = 0.254  # Stroke width for symbol outlines
SIDE_CLEARANCE = GRID_SPACING  # Clearance between the endpoint of a side and the closest pin
PIN_OFFSET = SIDE_CLEARANCE + GRID_SPACING
LR_SEPARATION = 2 * GRID_SPACING  # Minimum separation between opposing pin names on left and right sides
TB_SEPARATION = 2 * GRID_SPACING  # Minimum separation between opposing pin names on top and bottom sides

# Enable/disable debugging diagnostics
debug = False

# ===== Basic Utility Functions =====

def gridify(value, grid_spacing=GRID_SPACING, policy='round'):
    """
    Round a value to the nearest grid spacing multiple.
    
    Ensures all coordinates and dimensions align with KiCad's grid system,
    producing cleaner symbols that are easier to connect to other components.

    Args:
        value (float): The value to round.
        grid_spacing (float, optional): The grid spacing to use for rounding. 
                                      Defaults to GRID_SPACING (1.27 mm).
        policy (str, optional): Rounding policy. One of: 'round', 'up', 'down'.
                              Defaults to 'round'.

    Returns:
        float: The rounded value according to the specified policy.
        
    Raises:
        ValueError: If an invalid rounding policy is specified.
    """
    if policy == 'up':
        return math.ceil(value / grid_spacing) * grid_spacing
    elif policy == 'down':
        return math.floor(value / grid_spacing) * grid_spacing
    elif policy == 'round':
        return round(value / grid_spacing) * grid_spacing
    else:
        raise ValueError(f"Invalid gridify policy '{policy}'. Use 'up', 'down', or 'round'.")

def text_width(text, alt_pin_delim=None, font_size=FONT_SIZE):
    """
    Calculate the width for a text string based on font size.

    Args:
        text (str): The text to measure.
        alt_pin_delim (str, optional): Delimiter character for splitting
            a complete pin name into alternatives. Defaults to None (no splitting).
        font_size (float, optional): Font size in mm. Defaults to FONT_SIZE (1.27).

    Returns:
        float: width of the text in mm.
    """
    # Approximate character width as 60% of font size for monospaced fonts
    char_width = font_size * 0.9

    # If using alternate pin names, then the bounding box width
    # is the length of the longest alternate name.
    # Otherwise, the bounding box width is the length of the text.
    alternates = text.split(alt_pin_delim)
    if not alternates:
        text_len = 0
    else:
        text_len = max(len(alt) for alt in alternates)

    width = text_len * char_width
    return width

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
    Convert a YES-NO-TRUE-FALSE string to KiCad's 'yes'/'no' format.
    
    KiCad uses 'yes' and 'no' strings for boolean values in its file format.
    This function standardizes various input formats to these values.

    Args:
        value (str or int): Value to convert. Can be string representations like
                          'yes', 'y', 'true', 't', 'no', 'n', 'false', 'f',
                          or numbers like '1', '0', 1, 0.

    Returns:
        str: 'yes' for truthy values or 'no' for falsy values.

    Raises:
        ValueError: If the input string doesn't match any known boolean representation.
    """
    value = str(value).lower() if not isinstance(value, str) else value.lower()
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
    Read a CSV or Excel file into a list of rows.

    Automatically detects the file format by extension and uses the appropriate
    parser (csv module for CSV, pandas for Excel).

    Args:
        input_file (str): Path to the input file (.csv, .xlsx, or .xls).

    Returns:
        list of list: Rows from the file, with each row as a list of strings.
        Empty cells are represented as empty strings.

    Raises:
        ValueError: If the file extension is unsupported.
        FileNotFoundError: If the specified file doesn't exist.
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
    Group CSV rows into separate symbols based on blank lines.

    In the input format, symbols are separated by blank lines. Each symbol consists 
    of a part name in the first row, optional properties in subsequent rows, followed 
    by a header row for pin data, and then the pin definitions.

    Args:
        rows (list of list): Raw CSV rows from the input file.

    Returns:
        list of list: List of symbol data, where each item is a list of rows for a symbol.

    Raises:
        ValueError: If no valid symbols are found in the input data.
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

# ===== Symbol Library Functions =====

def empty_symbol_lib():
    """
    Create an empty KiCad symbol library with standard header information.
    
    Creates a basic library structure with KiCad-compatible version and generator
    information. This serves as the foundation for building new symbol libraries.
    
    Returns:
        Sexp: An S-expression object representing an empty KiCad symbol library
              with version and generator information.
    """
    return Sexp(['kicad_symbol_lib',
                ['version', '20241209'],
                ['generator', 'kicad_symbol_editor'],
                ['generator_version', '8.0']])
    
def merge_symbol_libs(lib1, lib2, overwrite=False):
    """
    Merge two KiCad symbol libraries.
    
    Combines symbols from two libraries into a new library. The version and
    generator information is preserved from the first library. By default, if
    symbols with the same name exist in both libraries, an error is raised unless
    the overwrite parameter is set to True.
    
    Args:
        lib1 (Sexp): First symbol library (base library).
        lib2 (Sexp): Second symbol library to merge into the base.
        overwrite (bool, optional): Whether to allow overwriting of symbols in lib1 with 
                                  symbols of the same name from lib2. If False, the merge
                                  will raise an exception when duplicate names are found.
                                  Defaults to False.
    
    Returns:
        Sexp: Merged symbol library.
    
    Raises:
        ValueError: If overwrite=False and lib2 contains symbols with names that
                   already exist in lib1.
    """
    # Create a new library with the same version, generator, etc. as lib1
    merged_lib = empty_symbol_lib()
    
    # Copy attributes from lib1 (version, generator, etc.) if they differ from defaults
    lib1_version = None
    lib1_generator = None
    lib1_generator_version = None
    
    # Extract these values from lib1
    for item in lib1:
        if item[0] == 'version':
            lib1_version = item[1]
        elif item[0] == 'generator':
            lib1_generator = item[1]
        elif item[0] == 'generator_version':
            lib1_generator_version = item[1]
    
    # Replace default values in merged_lib if lib1 has different values
    for i, item in enumerate(merged_lib):
        if item[0] == 'version' and lib1_version:
            merged_lib[i] = ['version', lib1_version]
        elif item[0] == 'generator' and lib1_generator:
            merged_lib[i] = ['generator', lib1_generator]
        elif item[0] == 'generator_version' and lib1_generator_version:
            merged_lib[i] = ['generator_version', lib1_generator_version]
    
    # Extract all symbols from lib1 and create a name-to-symbol mapping
    lib1_symbols = extract_symbols_from_lib(lib1)
    lib1_symbols_map = {symbol[1]: symbol for symbol in lib1_symbols}
    
    # Extract all symbols from lib2
    lib2_symbols = extract_symbols_from_lib(lib2)
    lib2_symbols_map = {symbol[1]: symbol for symbol in lib2_symbols}
    
    # Check for duplicates when overwrite is not allowed
    if not overwrite:
        duplicates = set(lib1_symbols_map.keys()) & set(lib2_symbols_map.keys())
        if duplicates:
            raise ValueError(f"Cannot merge libraries: The following symbols exist in both libraries: {', '.join(duplicates)}. Use --overwrite to replace them.")
    
    # Add all symbols from lib1 that aren't being overwritten
    for name, symbol in lib1_symbols_map.items():
        if overwrite and name in lib2_symbols_map:
            continue  # Skip symbols that will be overwritten
        merged_lib.append(symbol)
    
    # Add all symbols from lib2
    for name, symbol in lib2_symbols_map.items():
        merged_lib.append(symbol)
    
    return merged_lib

def extract_symbols_from_lib(symbol_lib):
    """
    Extract individual symbol definitions from a KiCad symbol library S-expression.

    Parses the library S-expression string into a structured format and extracts 
    each symbol definition. This allows processing of individual symbols without
    having to manually parse the S-expression structure.

    Args:
        symbol_lib (str or Sexp): S-expression string or object representing a KiCad symbol library.

    Returns:
        list of Sexp: List of Sexp objects, one for each symbol in the library.

    Raises:
        ValueError: If the input is not a valid KiCad symbol library S-expression.
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
    for _, prop_name, prop_value, *discard in properties:
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

# ===== Symbol Drawing Functions =====

def create_rectangle_outline(x0, y0, x1, y1, alpha=0.0001):
    """
    Create a rectangular outline for debugging purposes.
    
    Args:
        x0 (float): X-coordinate of the first corner.
        y0 (float): Y-coordinate of the first corner.
        x1 (float): X-coordinate of the opposite corner.
        y1 (float): Y-coordinate of the opposite corner.
        alpha (float, optional): Transparency value for the fill color.
                               Default is 0.0001 (nearly invisible).
        
    Returns:
        Sexp: S-expression representing the rectangle outline.
    """
    
    return Sexp(['rectangle',
                          ['start', x0, y0],
                          ['end', x1, y1],
                          ['stroke', ['width', STROKE_WIDTH/2], ['type', 'solid']],
                          ['fill', ['type', 'color'], ['color', 0, 0, 0, alpha]],
                          ])

def create_pin_name_outline(pin, x, y, orientation, pin_length):
    """
    Create a rectangular outline that surrounds a pin's name for debugging purposes.
    
    Args:
        pin (dict): Dictionary containing pin properties including 'name'.
        x (float): X-coordinate of the pin connection point.
        y (float): Y-coordinate of the pin connection point.
        orientation (int): Orientation of the pin in degrees (0, 90, 180, or 270).
        pin_length (float): Length of the pin line in grid units.
        
    Returns:
        Sexp: S-expression representing the outline around the pin name.
        
    Raises:
        ValueError: If an invalid orientation is provided.
    """
    
    pin_name = pin['name']
    name_offset = PIN_NAME_OFFSET

    w = text_width(pin_name)
    h = FONT_SIZE
    
    # Adjust position based on orientation and pin length
    if orientation == 0:  # Left-side pin
        x0 = x + pin_length + name_offset
        x1 = x0 + w
        y0 = y + h/2
        y1 = y - h/2
    elif orientation == 180:  # Right-side pin
        x0 = x - pin_length - name_offset
        x1 = x0 - w
        y0 = y + h/2
        y1 = y - h/2
    elif orientation == 90:  # Bottom-side pin
        x0 = x - h/2
        x1 = x0 + h
        y0 = y + pin_length + name_offset
        y1 = y0 + w
    elif orientation == 270:  # Top-side pin
        x0 = x - h/2
        x1 = x0 + h
        y0 = y - pin_length - name_offset
        y1 = y0 - w
    else:
        raise ValueError(f"Invalid orientation: {orientation}.")
    
    return create_rectangle_outline(x0, y0, x1, y1)

def create_pin_sexp(pin, x, y, orientation, pin_length, alt_pin_delim=None):
    """
    Create an S-expression for a pin in a KiCad symbol.
    
    Constructs the complete S-expression structure for a pin with all required
    attributes including position, orientation, name, number, and visual properties.
    Also handles bundled pins.
    
    Args:
        pin (dict): Dictionary containing pin properties:
                   'type': Pin electrical type (e.g., 'input', 'output', 'bidirectional')
                   'style': Pin visual style (e.g., 'line', 'inverted', 'clock')
                   'name': Pin name (can include alternatives with delimiter)
                   'number': Pin number or identifier
                   'hidden': Whether the pin should be visually hidden
        x (float): X coordinate for the pin connection point (grid units)
        y (float): Y coordinate for the pin connection point (grid units)
        orientation (int): Pin orientation in degrees (0, 90, 180, or 270)
        pin_length (float): Length of the pin line in grid units
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                     alternatives. Defaults to None (no splitting).
        
    Returns:
        List(Sexp): List of one or more pin S-expression objects depending upon bundling.
    """

    # Handle bundled pins which have multiple pin numbers.
    pin_numbers = pin['number']
    if isinstance(pin['number'], str):
        # An unbundled pin has a list of one pin number.
        pin_numbers = [pin['number']]
    elif isinstance(pin['number'], list):
        # A bundled pin has a list of multiple pin numbers.
        pin_numbers = pin['number']
    else:
        raise ValueError(f"Invalid pin number format: {pin['number']}")

    pin_sexps = []

    # Iterate through the pins. Only the first pin of a bundle is visible (not hidden)
    for hide, pin_number in enumerate(pin_numbers, 0):
        pin_sexp = Sexp(['pin', pin['type'], pin['style']])
        pin_sexp.append(['at', x, y, orientation])
        pin_sexp.append(['length', pin_length])
        if hide or pin['hidden'].lower() in ['1', 'true', 'yes']:
            pin_sexp.append(['hide', 'yes'])

        # Add pin name   
        names = pin['name'].split(alt_pin_delim)
        name_sexp = Sexp(['name', names[0]])
        effects_sexp = Sexp(['effects'])
        font_sexp = Sexp(['font'])
        font_sexp.append(['size', 1.27, 1.27])
        effects_sexp.append(font_sexp)
        name_sexp.append(effects_sexp)
        pin_sexp.append(name_sexp)
        
        # Add pin number
        number_sexp = Sexp(['number', pin_number])
        effects_sexp = Sexp(['effects'])
        font_sexp = Sexp(['font'])
        font_sexp.append(['size', 1.27, 1.27])
        effects_sexp.append(font_sexp)
        number_sexp.append(effects_sexp)
        pin_sexp.append(number_sexp)

        # Add alternate names
        for name in names[1:]:
            pin_sexp.append(['alternate', name, pin['type'], pin['style']])

        pin_sexps.append(pin_sexp)
    
    return pin_sexps

# ===== Symbol Generation Functions =====

def generate_symbol(symbol_rows, sort_by='row', reverse=False, default_side='left', alt_pin_delim=None, push=0.5, bundle=False, scrunch=False):
    """
    Generate a KiCad symbol S-expression from CSV rows.

    Creates a complete symbol definition with rectangle outline and pins positioned
    according to the specified parameters. Pins are automatically arranged on the 
    appropriate sides with proper spacing and alignment.

    Args:
        symbol_rows (list of list): CSV rows for a single symbol, including:
                                   - First row: [symbol_name, ""]
                                   - Property rows: [prop_name + ":", prop_value]
                                   - Header row: ["pin", "name", "type", "side", ...]
                                   - Pin data rows: [pin_number, pin_name, pin_type, ...]
        sort_by (str, optional): Method to sort pins:
                               - 'row': Original order in the CSV (default)
                               - 'num': By pin number using natural sort
                               - 'name': By pin name using natural sort
        reverse (bool, optional): Reverse the pin sort order. Defaults to False.
        default_side (str, optional): Default side for pins without a side specified.
                                    Valid values: 'left', 'right', 'top', 'bottom'.
                                    Defaults to 'left'.
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                      alternatives. Defaults to None (no splitting).
        push (float, optional): When 0, pins start at the top/left-most position on a side.
                                When 1, pins start at the bottom/right-most position.
                                Defaults to 0.5 (pins are centered).
        bundle (bool, optional): Bundle identically-named power or ground pins. Defaults to False.
        scrunch (bool, optional): Compress pins of left/right columns underneath top/bottom rows.
                                 Defaults to False.

    Returns:
        Sexp: KiCad symbol as an Sexp object, ready to be included in a library.

    Raises:
        ValueError: If the part name is invalid, required columns are missing,
                  or no valid pins are defined.
        KeyError: If a property label doesn't match known KiCad properties.
    """

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
    # The entries in the property list are [value, x_offset, y_offset, text justification, hidden].
    properties = {
        'Reference':     ['U',       0,  1.5 * GRID_SPACING, 'right', 'no'],
        'Value':         [part_name, 0,  0.5 * GRID_SPACING, 'right', 'no'],
        'Footprint':     ['',        0,  0,                  'right', 'yes'],
        'Datasheet':     ['',        0,  0,                  'right', 'yes'],
        'Description':   ['',        0,  0,                  'left',  'yes'],
        'ki_keywords':   ['',        0,  0,                  'left',  'yes'],
        'ki_locked':     ['',        0,  0,                  'left',  'yes'],
        'ki_fp_filters': ['',        0,  0,                  'left',  'yes'],
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
    # The properties are added below after the outline for the unit is determined
    # so that the property text can be placed at the upper-left corner of the unit.

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

    # Bundle identical power or ground input pins if requested
    if bundle:
        # Group pins by name, unit, and type (only for power pins)
        bundled_pins = {}
        pins_to_keep = []
        
        for pin in pins:
            # Only bundle power pins (power_in or power_out)
            if pin['type'] in ['power_in']:
                key = (pin['name'], pin['unit'], pin['type'], pin['side'])
                if key not in bundled_pins:
                    bundled_pins[key] = []
                bundled_pins[key].append(pin)
            else:
                # Keep non-power pins as they are
                pins_to_keep.append(pin)
        
        # For each group of identical power pins, create a single pin with combined numbers
        for pin_group in bundled_pins.values():
            if len(pin_group) > 1:
                # Create a bundled pin using the first pin's data
                bundled_pin = pin_group[0].copy()
                # Store bundled pin numbers as a list.
                bundled_pin['number'] = [p['number'] for p in pin_group if p['number'] != '*']
                pins_to_keep.append(bundled_pin)
            else:
                # Single pins don't need bundling
                pins_to_keep.append(pin_group[0])
        
        pins = pins_to_keep

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

    # Collect the Sexp for each unit and then add them to the symbol Sexp
    # after the properties are added below.
    unit_sexps = []

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
                    w = text_width('')
                else:
                    w = text_width(pin['name'], alt_pin_delim=alt_pin_delim) + PIN_NAME_OFFSET
                # Update the bounding box based on width of the pin name...
                bbox[side]['width'] = max(bbox[side]['width'], w)
                # ... and the standard height of a pin.
                bbox[side]['height'] += PIN_HEIGHT

        # Now account for the top and bottom sides by switching their width and height.
        for side in ['top', 'bottom']:
            bbx = bbox[side]
            bbx['width'], bbx['height'] = bbx['height'], bbx['width']

        # Compute the bounding box for the entire unit.
        lr_height = max(bbox['left']['height'], bbox['right']['height'])
        lr_width = max(bbox['left']['width'], bbox['right']['width'], SIDE_CLEARANCE)
        tb_height = max(bbox['top']['height'], bbox['bottom']['height'], SIDE_CLEARANCE)
        tb_width = max(bbox['top']['width'], bbox['bottom']['width'])
        lr_height = gridify(lr_height, policy='up')
        lr_width = gridify(lr_width, policy='up')
        tb_height = gridify(tb_height, policy='up')
        tb_width = gridify(tb_width, policy='up')
        
        # If scrunch option is enabled, compress left/right columns under top/bottom rows
        if scrunch:
            # Make the symbol width just wide enough to accommodate top and bottom pins
            unit_width = max(tb_width + 2 * SIDE_CLEARANCE, LR_SEPARATION)
            # But ensure it's at least wide enough for any left/right pin names
            unit_width = max(unit_width, 2 * lr_width)
            # Height needs to be tall enough for both top/bottom and left/right pins
            unit_height = 2 * tb_height + lr_height + 2 * SIDE_CLEARANCE
            # unit_height = max(2 * tb_height, lr_height + 2 * SIDE_CLEARANCE)
        else:
            # Standard layout (left/right columns beside top/bottom rows)
            unit_width = 2 * max(lr_width, SIDE_CLEARANCE) + max(tb_width, LR_SEPARATION)  
            unit_height = 2 * max(tb_height, SIDE_CLEARANCE) + max(lr_height, TB_SEPARATION)

        # Define the rectangular outline for the unit
        xorg = 0
        yorg = 0
        x0 = gridify(xorg-unit_width/2)
        y0 = gridify(yorg-unit_height/2)
        x1 = gridify(xorg+unit_width/2)
        y1 = gridify(yorg+unit_height/2)
        rect_sexp = Sexp(['rectangle',
                          ['start', x0, y0], # lower-left corner
                          ['end', x1, y1],   # upper-right corner
                          ['stroke', ['width', STROKE_WIDTH], ['type', 'solid']],
                          ['fill', ['type', 'background']],
                          ])
        # Add the rectangle to the unit Sexp
        unit_sexp.append(rect_sexp)

        # For debugging, show the boxes that contain the pins on each side.
        if debug:
            lr_box = create_rectangle_outline(x0, y0+tb_height, x0+lr_width, y0+tb_height+lr_height, alpha=0.1)
            unit_sexp.append(lr_box)
            lr_box = create_rectangle_outline(x1, y0+tb_height, x1-lr_width, y0+tb_height+lr_height, alpha=0.1)
            unit_sexp.append(lr_box)
            tb_box = create_rectangle_outline(x0+lr_width, y0, x0+lr_width+tb_width, y0+tb_height, alpha=0.1)
            unit_sexp.append(tb_box)
            tb_box = create_rectangle_outline(x0+lr_width, y1-tb_height, x0+lr_width+tb_width, y1, alpha=0.1)
            unit_sexp.append(tb_box)
            # For debugging, indicate the bottom-left and top-right corners of the unit outline
            unit_sexp.append(create_rectangle_outline(x0, y0, x0+1, y0+1, alpha=0.3))
            unit_sexp.append(create_rectangle_outline(x1, y1, x1-1, y1-1, alpha=0.3))

        # Process pins for each side
        for side, pin_list in unit.items():

            # Sort pins based on user-specified criteria
            if sort_by == 'num':
                pin_list.sort(key=lambda p: parse_mixed_string(p['number']), reverse=reverse)
            elif sort_by == 'name':
                pin_list.sort(key=lambda p: parse_mixed_string(p['name']) if p['number'] != '*' else (chr(0x10FFFF), float('inf')), reverse=reverse)
            elif sort_by == 'row':
                pin_list.sort(key=lambda p: p['row_index'], reverse=reverse)

            pin_cnt = len(pin_list)

            if side == 'left':
                ctr_offset = gridify(push * (lr_height - pin_cnt*PIN_HEIGHT))
                x = x0 - PIN_LENGTH
                y = y0 + tb_height + lr_height - ctr_offset - PIN_HEIGHT/2
                x, y = gridify(x), gridify(y)
                orientation = 0
                for pin in pin_list:
                    if pin['number'] != '*':
                        unit_sexp.extend(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                        if debug:
                            unit_sexp.append(create_pin_name_outline(pin, x, y, orientation, PIN_LENGTH))
                    y -= PIN_SPACING

            elif side == 'right':
                ctr_offset = gridify(push * (lr_height - pin_cnt*PIN_HEIGHT))
                x = x1 + PIN_LENGTH
                y = y0 + tb_height + lr_height - ctr_offset - PIN_HEIGHT/2
                x, y = gridify(x), gridify(y)
                orientation = 180
                for pin in pin_list:
                    if pin['number'] != '*':
                        unit_sexp.extend(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                        if debug:
                            unit_sexp.append(create_pin_name_outline(pin, x, y, orientation, PIN_LENGTH))
                    y -= PIN_SPACING

            elif side == 'top':
                if scrunch:
                    ctr_offset = gridify(push * (unit_width - pin_cnt*PIN_HEIGHT))
                    x = x0 + ctr_offset + PIN_HEIGHT/2
                else:
                    ctr_offset = gridify(push * (tb_width - pin_cnt*PIN_HEIGHT))
                    x = x0 + lr_width + ctr_offset + PIN_HEIGHT/2
                y = y1 + PIN_LENGTH
                x, y = gridify(x), gridify(y)
                orientation = 270
                for pin in pin_list:
                    if pin['number'] != '*':
                        unit_sexp.extend(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                        if debug:
                            unit_sexp.append(create_pin_name_outline(pin, x, y, orientation, PIN_LENGTH))
                    x += PIN_SPACING

            elif side == 'bottom':
                if scrunch:
                    ctr_offset = gridify(push * (unit_width - pin_cnt*PIN_HEIGHT))
                    x = x0 + ctr_offset + PIN_HEIGHT/2
                else:
                    ctr_offset = gridify(push * (tb_width - pin_cnt*PIN_HEIGHT))
                    x = x0 + lr_width + ctr_offset + PIN_HEIGHT/2
                y = -y1 - PIN_LENGTH
                x, y = gridify(x), gridify(y)
                orientation = 90
                for pin in pin_list:
                    if pin['number'] != '*':
                        unit_sexp.extend(create_pin_sexp(pin, x, y, orientation, PIN_LENGTH, alt_pin_delim=alt_pin_delim))
                        if debug:
                            unit_sexp.append(create_pin_name_outline(pin, x, y, orientation, PIN_LENGTH))
                    x += PIN_SPACING

        unit_sexps.append(unit_sexp)

    # Add completed set of properties to the symbol Sexp
    for name, [value, x_offset, y_offset, justify, hide] in properties.items():
        symbol_sexp.append(['property', name, value,
                         ['at', x0 + x_offset, y1 + y_offset, 0],
                         ['effects', 
                            ['font', ['size', FONT_SIZE, FONT_SIZE]],
                            ['justify', justify],
                            ['hide', hide]]])
        
    # Now add the units to the symbol
    symbol_sexp.extend(unit_sexps)

    symbol_sexp.append(['embedded_fonts', 'no'])

    return symbol_sexp

def generate_symbol_lib(rows, sort_by='row', reverse=False, default_side='left', alt_pin_delim=None, bundle=False, scrunch=False):
    """
    Generate a complete KiCad symbol library from CSV or Excel data.
    
    Processes input rows to create a full symbol library file with multiple
    symbols and appropriate metadata. Handles errors for individual symbols
    gracefully, continuing with the next symbol if one fails.
    
    Args:
        rows (list of list): Raw CSV rows containing one or more symbols.
        sort_by (str, optional): Method to sort pins within each symbol:
                                - 'row': Original order in the CSV (default)
                                - 'num': By pin number using natural sort
                                - 'name': By pin name using natural sort
        reverse (bool, optional): Reverse the pin sort order. Defaults to False.
        default_side (str, optional): Default side for pins without a side specified.
                                     Valid values: 'left', 'right', 'top', 'bottom'.
                                     Defaults to 'left'.
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                      alternatives. Defaults to None (no splitting).
        bundle (bool, optional): Bundle identically-named power or ground pins into single pins.
                               Defaults to False.
        scrunch (bool, optional): Compress pins of left/right columns underneath top/bottom rows.
                                 Defaults to False.
    
    Returns:
        Sexp: Complete KiCad symbol library as an Sexp object, ready to write to file.
    
    Raises:
        ValueError: If no valid symbols could be generated from the input data.
    """

    # Create the library S-expression container
    symbol_lib = empty_symbol_lib()

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
                alt_pin_delim=alt_pin_delim,
                bundle=bundle,
                scrunch=scrunch
            )
            symbol_lib.append(symbol)
        except Exception as e:
            # Get the symbol name from the first row if available
            symbol_name = symbol_rows[0][0] if symbol_rows and symbol_rows[0] else "Unknown"
            print(f"Error processing symbol '{symbol_name}': {e}")
            # Continue with the next symbol
    
    # Check if we generated any valid symbols
    if not extract_symbols_from_lib(symbol_lib):  # No symbols found
        raise ValueError("No valid symbols were generated from the input data")
    
    return symbol_lib

# ===== File Conversion Functions =====

def row_file_to_symbol_lib_file(row_file, symbol_lib_file=None, sort_by='row', reverse=False, default_side='left', alt_pin_delim=None, overwrite=False, bundle=False, scrunch=False):
    """
    Convert a CSV or Excel file to a KiCad symbol library file.

    This is the main entry point for the CSV-to-KiCad conversion process.
    It handles file I/O and delegates the symbol generation to other functions.
    If the output file exists and overwrite is True, it will merge the new symbols
    with the existing library.

    Args:
        row_file (str): Path to the input CSV or Excel file with symbol data.
        symbol_lib_file (str, optional): Path for the output .kicad_sym file.
                                        If None, uses the input filename with .kicad_sym extension.
        sort_by (str, optional): Method to sort pins within each symbol:
                                - 'row': Original order in the CSV (default)
                                - 'num': By pin number using natural sort
                                - 'name': By pin name using natural sort
        reverse (bool, optional): Reverse the pin sort order. Defaults to False.
        default_side (str, optional): Default side for pins without a side specified.
                                     Valid values: 'left', 'right', 'top', 'bottom'.
                                     Defaults to 'left'.
        alt_pin_delim (str, optional): Delimiter for splitting pin names into
                                      alternatives. Defaults to None (no splitting).
        overwrite (bool, optional): Allow overwriting or merging with existing output file.
                                   Defaults to False.
        bundle (bool, optional): Bundle identically-named power or ground pins into single pins.
                               Defaults to False.
        scrunch (bool, optional): Compress pins of left/right columns underneath top/bottom rows.
                                 Defaults to False.

    Returns:
        str: Path to the generated .kicad_sym file.

    Raises:
        ValueError: If the input file is invalid, no symbols are found, or
                   output file exists without overwrite permission.
        FileNotFoundError: If the input file doesn't exist.
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
    symbol_lib = generate_symbol_lib(rows, sort_by=sort_by, reverse=reverse, 
                                    default_side=default_side, alt_pin_delim=alt_pin_delim, 
                                    bundle=bundle, scrunch=scrunch)

    # If the output file already exists and overwrite is True, we need to merge
    if os.path.exists(symbol_lib_file) and overwrite:
        try:
            # Read the existing library
            with open(symbol_lib_file, 'r') as f:
                existing_lib = Sexp(f.read())
            
            # Merge the existing library with the new one
            symbol_lib = merge_symbol_libs(existing_lib, symbol_lib, overwrite=True)
        except Exception as e:
            print(f"Warning: Could not merge with existing library: {str(e)}")
            print("Creating a new library instead.")
            # Continue with the original symbol_lib

    # Add quotes to string values that need them
    add_quotes(symbol_lib)
    
    # Store the symbol library as an S-expression in the output file.
    with open(symbol_lib_file, 'w') as f:
        f.write(str(symbol_lib))

    return symbol_lib_file

def symbol_lib_file_to_csv_file(symbol_lib_file, csv_file=None, overwrite=False):
    """
    Convert a KiCad symbol library to a CSV file.

    This is the main entry point for the KiCad-to-CSV conversion process.
    It extracts symbols from a .kicad_sym file and formats them for CSV output.

    Args:
        symbol_lib_file (str): Path to the input KiCad symbol library (.kicad_sym).
        csv_file (str, optional): Path for the output CSV file.
                                 If None, uses the input filename with .csv extension.
        overwrite (bool, optional): Allow overwriting existing output file. 
                                   Defaults to False.

    Returns:
        str: Path to the generated CSV file.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If the input file is not a .kicad_sym file, or if the output file
                   exists and overwrite is False.
    """
    # Validate input file
    if not os.path.exists(symbol_lib_file):
        raise FileNotFoundError(f"Input file {symbol_lib_file} does not exist")
    
    _, ext = os.path.splitext(symbol_lib_file)
    if ext.lower() != '.kicad_sym':
        raise ValueError(f"Input file must be a .kicad_sym file, got {ext}")
    
    # Determine output filename
    if not csv_file:
        csv_file = os.path.splitext(symbol_lib_file)[0] + '.csv'
    
    # Check for existing output file
    if os.path.exists(csv_file) and not overwrite:
        raise ValueError(f"Output file {csv_file} already exists. Use --overwrite to allow overwriting.")
    
    # Read the symbol library contents
    with open(symbol_lib_file, 'r') as f:
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
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(all_rows)
    
    return csv_file

# ===== Command-Line Interface Functions =====

def kipart():
    """
    Command-line interface for generating KiCad symbol libraries from CSV or Excel files.

    Usage:
        kipart [-h] [-v] [-r] [--side {left,right,top,bottom}] [-o OUTPUT]
               [-w] [-s {row,num,name}] [-a ALT_DELIMITER] [-b] [--scrunch] [-m] input_files [input_files ...]

    Examples:
        kipart input.csv                # Generate input.kicad_sym 
        kipart -o lib.kicad_sym in.xlsx # Generate lib.kicad_sym from in.xlsx
        kipart -s num -r *.csv          # Generate libraries with pins sorted by number (descending)
        kipart -b input.csv             # Bundle identical power/ground pins into single pins
        kipart --scrunch input.csv      # Compress pins of left/right columns under top/bottom rows
        kipart -m existing.csv          # Merge with existing library instead of overwriting

    Args:
        None (uses sys.argv via argparse).

    Returns:
        None

    Exits:
        0: On successful completion.
        1: If errors occur during processing.
    """
    parser = argparse.ArgumentParser(description="Convert CSV or Excel files to KiCad symbol libraries")
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-r', '--reverse', action='store_true', help="Sort pins in reverse order")
    parser.add_argument('--side', choices=['left', 'right', 'top', 'bottom'], default='left',
                        help="Which side to place the pins by default")
    parser.add_argument('-o', '--output', help="Generated KiCad symbol library (.kicad_sym)")
    parser.add_argument('-w', '--overwrite', action='store_true', help="Allow overwriting of an existing part library")
    parser.add_argument('-s', '--sort', choices=['row', 'num', 'name'], default='row',
                        help="Sort the part pins by their entry order in the CSV file (row), "
                             "their pin number (num), or their pin name (name)")
    parser.add_argument('-a', '--alt-delimiter', dest='alt_delimiter', default=None,
                        help="Delimiter character for splitting pin names into alternatives")
    parser.add_argument('-b', '--bundle', action='store_true',
                        help="Bundle identically-named power or ground pins into single schematic pins")
    parser.add_argument('--scrunch', action='store_true',
                        help="Compress pins of left/right columns underneath top/bottom rows")
    parser.add_argument('-m', '--merge', action='store_true',
                        help="Merge with existing library rather than overwriting completely")
    parser.add_argument('input_files', nargs='+',
                        help="Input CSV or Excel files (.csv, .xlsx, .xls)")
    
    args = parser.parse_args()
    
    # Validate single input file with output option
    if args.output and len(args.input_files) > 1:
        print("Error: --output can only be used with a single input file")
        sys.exit(1)
    
    # Process each input file containing rows of symbol pin data
    error_flag = False
    for row_file in args.input_files:
        try:
            # Determine if we should overwrite or merge
            effective_overwrite = args.overwrite
            if args.merge and os.path.exists(os.path.splitext(row_file)[0] + '.kicad_sym'):
                effective_overwrite = True  # Enable overwrite if merging
                
            symbol_lib_file = row_file_to_symbol_lib_file(
                row_file,
                symbol_lib_file=args.output,
                sort_by=args.sort,
                reverse=args.reverse,
                default_side=args.side,
                alt_pin_delim=args.alt_delimiter,
                overwrite=effective_overwrite,
                bundle=args.bundle,
                scrunch=args.scrunch
            )
            print(f"Generated {symbol_lib_file} successfully from {row_file}")
        except Exception as e:
            # raise
            print(f"Error processing file '{row_file}': {str(e)}")
            error_flag = True
            continue

    if error_flag:
        print("Errors occurred during processing. Please check the output above.")
        sys.exit(1)

def kilib2csv():
    """
    Command-line interface for converting KiCad symbol libraries to CSV files.

    Usage:
        kilib2csv [-h] [-v] [-o OUTPUT] [-w] input_files [input_files ...]

    Examples:
        kilib2csv library.kicad_sym             # Generate library.csv
        kilib2csv -o output.csv lib.kicad_sym   # Generate output.csv from lib.kicad_sym
        kilib2csv -w *.kicad_sym                # Convert multiple libraries, overwriting existing CSVs

    Args:
        None (uses sys.argv via argparse).

    Returns:
        None

    Exits:
        0: On successful completion.
        1: If errors occur during processing.
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
    error_flag = False
    for input_file in args.input_files:
        try:
            output_file = symbol_lib_file_to_csv_file(
                input_file,
                csv_file=args.output,
                overwrite=args.overwrite
            )
            print(f"Generated {output_file} successfully from {input_file}")
        except Exception as e:
            # raise
            print(f"Error processing file '{input_file}': {str(e)}")
            error_flag = True
            continue

    if error_flag:
        print("Errors occurred during processing. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    kipart()
