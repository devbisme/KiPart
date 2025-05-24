from kipart.kipart import extract_symbols_from_lib


def symbols_are_equal(symbol1, symbol2):
    """
    Test if two symbols are equal regardless of the order of their properties, units, or pins.

    This function compares two KiCad symbol S-expressions for equality by matching properties
    by name, units by name, and pins by pin number, ensuring the comparison is not affected by
    the order of these elements in the original S-expressions.

    Args:
        symbol1 (Sexp): First symbol S-expression to compare
        symbol2 (Sexp): Second symbol S-expression to compare

    Returns:
        bool: True if the symbols are equivalent, False otherwise
    """
    # Check if both are valid symbol S-expressions
    if symbol1[0] != "symbol" or symbol2[0] != "symbol":
        return False

    # Compare symbol names
    if symbol1[1] != symbol2[1]:
        return False

    # Helper function to match subelements across S-expressions
    def match_by_key(elements1, elements2, key_pos, compare_func=None):
        """Match elements from two lists using a specified position as key"""
        if len(elements1) != len(elements2):
            return False

        # Create dictionaries to look up elements by key
        dict1 = {elem[key_pos]: elem for elem in elements1}
        dict2 = {elem[key_pos]: elem for elem in elements2}

        # Check that all keys match
        if set(dict1.keys()) != set(dict2.keys()):
            return False

        # Compare each matched pair
        for key in dict1:
            elem1 = dict1[key]
            elem2 = dict2[key]

            if compare_func:
                if not compare_func(elem1, elem2):
                    return False
            elif elem1 != elem2:
                return False

        return True

    # Compare simple attributes (exclude properties, units, and pins for now)
    symbol1_attrs = {}
    symbol2_attrs = {}

    # Extract simple attributes (non-property, non-unit elements)
    for i in range(2, len(symbol1)):
        if symbol1[i][0] not in ("property", "symbol"):
            symbol1_attrs[symbol1[i][0]] = symbol1[i]

    for i in range(2, len(symbol2)):
        if symbol2[i][0] not in ("property", "symbol"):
            symbol2_attrs[symbol2[i][0]] = symbol2[i]

    # Compare attributes
    if set(symbol1_attrs.keys()) != set(symbol2_attrs.keys()):
        return False

    for key in symbol1_attrs:
        if symbol1_attrs[key] != symbol2_attrs[key]:
            return False

    # Extract and compare properties by name
    props1 = [
        item for item in symbol1 if isinstance(item, list) and item[0] == "property"
    ]
    props2 = [
        item for item in symbol2 if isinstance(item, list) and item[0] == "property"
    ]

    # Function to compare properties (name, value, position, effects)
    def compare_properties(prop1, prop2):
        # Compare property name and value
        if prop1[1] != prop2[1] or prop1[2] != prop2[2]:
            return False

        # Compare effects, ignoring order
        effects1 = next(
            (x for x in prop1 if isinstance(x, list) and x[0] == "effects"), None
        )
        effects2 = next(
            (x for x in prop2 if isinstance(x, list) and x[0] == "effects"), None
        )

        if not effects1 and not effects2:
            return True
        if not effects1 or not effects2:
            return False

        # Convert effects to dictionaries for easy comparison
        def effects_to_dict(effects):
            result = {}
            for item in effects[1:]:
                if item[0] == "font":
                    result["font"] = tuple(item[1][1:]) if len(item) > 1 else tuple()
                elif item[0] == "justify":
                    result["justify"] = item[1]
                elif item[0] == "hide":
                    result["hide"] = item[1]
            return result

        effects_dict1 = effects_to_dict(effects1)
        effects_dict2 = effects_to_dict(effects2)

        return effects_dict1 == effects_dict2

    if not match_by_key(props1, props2, 1, compare_properties):
        return False

    # Extract and compare units
    units1 = [
        item for item in symbol1 if isinstance(item, list) and item[0] == "symbol"
    ]
    units2 = [
        item for item in symbol2 if isinstance(item, list) and item[0] == "symbol"
    ]

    if len(units1) != len(units2):
        return False

    # Function to compare units and their pins
    def compare_units(unit1, unit2):
        # Compare unit names
        if unit1[1] != unit2[1]:
            return False

        # Extract geometry elements (rectangles, polylines, etc.)
        geom1 = [
            item
            for item in unit1
            if isinstance(item, list) and item[0] not in ("pin", "text")
        ]
        geom2 = [
            item
            for item in unit2
            if isinstance(item, list) and item[0] not in ("pin", "text")
        ]

        # Compare geometry (must match exactly regardless of order)
        if sorted(str(g) for g in geom1) != sorted(str(g) for g in geom2):
            return False

        # Extract and compare pins by number
        pins1 = [item for item in unit1 if isinstance(item, list) and item[0] == "pin"]
        pins2 = [item for item in unit2 if isinstance(item, list) and item[0] == "pin"]

        def compare_pins(pin1, pin2):
            # Type and style must match
            if pin1[1] != pin2[1] or pin1[2] != pin2[2]:
                return False

            # Extract pin number and name, which must match
            num1 = next(
                (x[1] for x in pin1 if isinstance(x, list) and x[0] == "number"), None
            )
            num2 = next(
                (x[1] for x in pin2 if isinstance(x, list) and x[0] == "number"), None
            )
            if num1 != num2:
                return False

            name1 = next(
                (x[1] for x in pin1 if isinstance(x, list) and x[0] == "name"), None
            )
            name2 = next(
                (x[1] for x in pin2 if isinstance(x, list) and x[0] == "name"), None
            )
            if name1 != name2:
                return False

            # Check pin position and orientation
            at1 = next((x for x in pin1 if isinstance(x, list) and x[0] == "at"), None)
            at2 = next((x for x in pin2 if isinstance(x, list) and x[0] == "at"), None)
            if not at1 or not at2:
                return False

            # Compare x, y coordinates
            if at1[1] != at2[1] or at1[2] != at2[2]:
                return False

            # Compare orientation (either both have it or neither does)
            if len(at1) > 3 and len(at2) > 3:
                if at1[3] != at2[3]:
                    return False
            elif len(at1) > 3 or len(at2) > 3:
                return False

            # Compare pin length
            len1 = next(
                (x[1] for x in pin1 if isinstance(x, list) and x[0] == "length"), None
            )
            len2 = next(
                (x[1] for x in pin2 if isinstance(x, list) and x[0] == "length"), None
            )
            if len1 != len2:
                return False

            # Compare hide attribute if present
            hide1 = next(
                (x for x in pin1 if isinstance(x, list) and x[0] == "hide"), None
            )
            hide2 = next(
                (x for x in pin2 if isinstance(x, list) and x[0] == "hide"), None
            )
            if bool(hide1) != bool(hide2):
                return False

            # Compare alternates if present
            alt1 = [x for x in pin1 if isinstance(x, list) and x[0] == "alternate"]
            alt2 = [x for x in pin2 if isinstance(x, list) and x[0] == "alternate"]

            # Convert to sets for order-independent comparison
            alt_set1 = {tuple(x[1:]) for x in alt1}
            alt_set2 = {tuple(x[1:]) for x in alt2}

            return alt_set1 == alt_set2

        # Extract pin numbers for lookup
        pin_nums1 = []
        pin_nums2 = []

        for pin in pins1:
            num = next(
                (x[1] for x in pin if isinstance(x, list) and x[0] == "number"), None
            )
            if num:
                pin_nums1.append(num)

        for pin in pins2:
            num = next(
                (x[1] for x in pin if isinstance(x, list) and x[0] == "number"), None
            )
            if num:
                pin_nums2.append(num)

        # Make sure the same pin numbers exist in both units
        if set(pin_nums1) != set(pin_nums2):
            return False

        # Create pin lookup dictionaries
        pin_dict1 = {}
        pin_dict2 = {}

        for pin in pins1:
            num = next(
                (x[1] for x in pin if isinstance(x, list) and x[0] == "number"), None
            )
            if num:
                pin_dict1[num] = pin

        for pin in pins2:
            num = next(
                (x[1] for x in pin if isinstance(x, list) and x[0] == "number"), None
            )
            if num:
                pin_dict2[num] = pin

        # Compare each pin
        for num in pin_dict1:
            if not compare_pins(pin_dict1[num], pin_dict2[num]):
                return False

        return True

    # Match units by name
    unit_dict1 = {u[1]: u for u in units1}
    unit_dict2 = {u[1]: u for u in units2}

    # Ensure same unit names exist in both symbols
    if set(unit_dict1.keys()) != set(unit_dict2.keys()):
        return False

    # Compare matched units
    for name in unit_dict1:
        if not compare_units(unit_dict1[name], unit_dict2[name]):
            return False

    # If we've made it this far, the symbols match
    return True


def symbol_libs_are_equal(lib1, lib2):
    """
    Test if two symbol libraries are equal regardless of the order of symbols.

    This function compares two KiCad symbol library S-expressions for equality by
    matching symbols by name and comparing their contents using symbols_are_equal.

    Args:
        lib1 (Sexp): First symbol library S-expression to compare
        lib2 (Sexp): Second symbol library S-expression to compare

    Returns:
        bool: True if the libraries contain the same symbols, False otherwise
    """

    # Check basic library attributes (version, generator)
    lib1_version = lib1.search("/kicad_symbol_lib/version", ignore_case=True)
    lib2_version = lib2.search("/kicad_symbol_lib/version", ignore_case=True)
    if int(lib1_version[0][1]) != int(lib2_version[0][1]):
        return False

    # Extract all symbols from each library
    symbols1 = extract_symbols_from_lib(lib1)
    symbols2 = extract_symbols_from_lib(lib2)

    # Check if the number of symbols is the same
    if len(symbols1) != len(symbols2):
        return False

    # Create dictionaries to lookup symbols by name
    symbols1_dict = {symbol[1]: symbol for symbol in symbols1}
    symbols2_dict = {symbol[1]: symbol for symbol in symbols2}

    # Check if the same symbol names exist in both libraries
    if set(symbols1_dict.keys()) != set(symbols2_dict.keys()):
        return False

    # Compare each symbol
    for name, symbol1 in symbols1_dict.items():
        symbol2 = symbols2_dict[name]
        if not symbols_are_equal(symbol1, symbol2):
            return False

    # All checks passed
    return True
