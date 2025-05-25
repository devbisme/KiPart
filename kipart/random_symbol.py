"""
Random Symbol Generator for KiCad

This module provides functions to generate random KiCad symbols for testing purposes.
It creates random CSV rows and feeds them through the rows_to_symbol function.
"""

import random
import string
from simp_sexp import Sexp
from kipart.kipart import rows_to_symbol, create_empty_symbol_lib

# Valid pin types and styles
PIN_TYPES = [
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "passive",
    "free",
    "unspecified",
    "power_in",
    "power_out",
    "open_collector",
    "no_connect",
]

PIN_STYLES = [
    "line",
    "inverted",
    "clock",
    "inverted_clock",
    "input_low",
    "output_low",
    "edge_clock_high",
    "non_logic",
]

PIN_SIDES = ["left", "right", "top", "bottom"]


# Helper functions
def random_string(
    min_length=5, max_length=20, chars=string.ascii_letters + string.digits + "_"
):
    """Generate a random string of specified length from the given character set."""
    length = random.randint(min_length, max_length)
    return "".join(random.choice(chars) for _ in range(length))


def random_reference():
    """Generate a random component reference."""
    prefix = random.choice(["U", "R", "C", "L", "Q", "D", "IC", "SW", "J"])
    number = random.randint(1, 999)
    return f"{prefix}{number}"


def random_choice(items):
    """Select a random item from a list."""
    return random.choice(items)


def create_random_symbol(max_pins=50):
    """
    Generate a random KiCad symbol as an Sexp object.

    Creates random CSV rows with a part name, reference property, and pin data,
    then feeds these rows through rows_to_symbol() to produce a random KiCad symbol.

    Args:
        max_pins (int): Maximum number of pins to generate for a symbol.

    Returns:
        Sexp: A KiCad symbol as an S-expression object.
    """
    # Generate a random part name
    part_name = random_string(5, 20, string.ascii_letters + string.digits + "_")

    # Generate reference row
    reference = random_reference()

    # Determine number of pins (between 20 and max_pins)
    num_pins = random.randint(20, max_pins)

    # Determine number of units (between 1 and 3)
    num_units = random.randint(1, 3)
    unit_names = [
        random_string(1, 10, string.ascii_letters + string.digits + "_")
        for _ in range(num_units)
    ]

    # Set up column headers for pin data
    pin_columns = ["pin", "name", "type", "style", "side", "unit", "hidden"]

    # Create a set to track used pin numbers
    used_pin_numbers = set()

    # Generate pin rows
    pin_rows = []
    for i in range(num_pins):
        # Generate a unique pin number
        while True:
            # Decide if we'll use a prefix (20% chance)
            if random.random() < 0.2:
                prefix = random.choice(string.ascii_uppercase) + random.choice(
                    string.ascii_uppercase
                )
                number = f"{prefix}{random.randint(1, 99)}"
            else:
                number = str(random.randint(1, 99))

            if number not in used_pin_numbers:
                used_pin_numbers.add(number)
                break

        # Generate a pin name
        name = random_string(5, 10, string.ascii_letters + string.digits + "_#~")

        # Select pin type, style, side, and unit
        pin_type = random_choice(PIN_TYPES)
        pin_style = random_choice(PIN_STYLES)
        pin_side = random_choice(PIN_SIDES)
        pin_unit = random_choice(unit_names)

        # Determine if pin is hidden (5% chance)
        hidden = "yes" if random.random() < 0.05 else "no"

        # Create pin row
        pin_row = [number, name, pin_type, pin_style, pin_side, pin_unit, hidden]
        pin_rows.append(pin_row)

    # Create the complete CSV rows
    csv_rows = [
        [part_name, ""],
        ["Reference:", reference],
        pin_columns,
    ]
    csv_rows.extend(pin_rows)

    # Generate the symbol using the CSV rows
    symbol = rows_to_symbol(csv_rows)

    return symbol


def create_random_symbol_lib(count=1, max_pins=50):
    """
    Generate a symbol library containing multiple random KiCad symbols.

    Args:
        count (int): Number of symbols to generate.
        max_pins (int): Maximum number of pins to generate for a symbol.

    Returns:
        Sexp: Symbol library containing random symbols.
    """
    symbol_lib = create_empty_symbol_lib()
    for _ in range(count):
        symbol = create_random_symbol(max_pins=max_pins)
        symbol_lib.append(symbol)
    return symbol_lib
