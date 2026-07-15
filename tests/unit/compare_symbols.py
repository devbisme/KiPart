from simp_sexp import Sexp

from kipart.kipart import extract_symbols_from_lib


def compare_symbol_pins(symbol1, symbol2):
    """
    Compare two symbols pin-by-pin for matching pin numbers.

    For each unit present in either symbol, pins are matched by pin number.
    The function reports mismatches for:
    - pin names
    - alternate pin names
    - pin types
    - pin numbers present in one symbol but missing in the other

    Args:
        symbol1 (Sexp): First symbol S-expression to compare
        symbol2 (Sexp): Second symbol S-expression to compare

    Returns:
        list[str]: A list of human-readable difference reports.
    """
    if not symbol1 or not symbol2 or symbol1[0] != "symbol" or symbol2[0] != "symbol":
        return []

    def get_pin_number(pin):
        number_nodes = pin.search("/pin/number", ignore_case=True)
        return number_nodes[0][1] if number_nodes else None

    def get_pin_name(pin):
        name_nodes = pin.search("/pin/name", ignore_case=True)
        return name_nodes[0][1] if name_nodes else None

    def get_pin_type(pin):
        return pin[1] if len(pin) > 1 else None

    def get_pin_alternates(pin):
        alternates = pin.search("/pin/alternate", ignore_case=True)
        return [alt[1] for alt in alternates if len(alt) > 1]

    def get_unit_pins(unit):
        return unit.search("/symbol/pin", ignore_case=True)

    def get_units(symbol):
        return symbol.search("/symbol/symbol", ignore_case=True)

    units1 = {unit[1]: unit for unit in get_units(symbol1) if len(unit) > 1}
    units2 = {unit[1]: unit for unit in get_units(symbol2) if len(unit) > 1}

    reports = []
    unit_names = sorted(set(units1.keys()) | set(units2.keys()))

    for unit_name in unit_names:
        unit1 = units1.get(unit_name)
        unit2 = units2.get(unit_name)

        if unit1 is None:
            reports.append(
                f"unit '{unit_name}' is present in the second symbol but missing from the first"
            )
            continue

        if unit2 is None:
            reports.append(
                f"unit '{unit_name}' is present in the first symbol but missing from the second"
            )
            continue

        pins1 = {}
        pins2 = {}

        for pin in get_unit_pins(unit1):
            pin_num = get_pin_number(pin)
            if pin_num is not None:
                pins1[pin_num] = pin

        for pin in get_unit_pins(unit2):
            pin_num = get_pin_number(pin)
            if pin_num is not None:
                pins2[pin_num] = pin

        for pin_num in sorted(set(pins1) - set(pins2)):
            reports.append(
                f"unit '{unit_name}': pin {pin_num} is present in the first symbol but missing in the second"
            )

        for pin_num in sorted(set(pins2) - set(pins1)):
            reports.append(
                f"unit '{unit_name}': pin {pin_num} is present in the second symbol but missing in the first"
            )

        for pin_num in sorted(set(pins1) & set(pins2)):
            pin1 = pins1[pin_num]
            pin2 = pins2[pin_num]

            name1 = get_pin_name(pin1)
            name2 = get_pin_name(pin2)
            if name1 != name2:
                reports.append(
                    f"unit '{unit_name}': pin {pin_num} name mismatch: {name1!r} != {name2!r}"
                )

            alternates1 = get_pin_alternates(pin1)
            alternates2 = get_pin_alternates(pin2)
            if alternates1 != alternates2:
                reports.append(
                    f"unit '{unit_name}': pin {pin_num} alternate names mismatch: {alternates1} != {alternates2}"
                )

            type1 = get_pin_type(pin1)
            type2 = get_pin_type(pin2)
            if type1 != type2:
                reports.append(
                    f"unit '{unit_name}': pin {pin_num} type mismatch: {type1!r} != {type2!r}"
                )

    return reports


def symbols_are_equal(symbol1, symbol2):
    """
    Test if two symbols are equal regardless of the order of their properties, units, or pins.

    This function compares two KiCad symbol S-expressions for equality by matching properties
    by name, units by name, and pins by pin number, ensuring the comparison is not affected by
    the order of the original S-expressions.

    Args:
        symbol1 (Sexp): First symbol S-expression to compare
        symbol2 (Sexp): Second symbol S-expression to compare

    Returns:
        bool: True if the symbols are equivalent, False otherwise
    """
    if not isinstance(symbol1, Sexp) or not isinstance(symbol2, Sexp):
        return False

    if symbol1[0] != "symbol" or symbol2[0] != "symbol":
        return False

    if symbol1[1] != symbol2[1]:
        return False

    def get_named_children(node, name):
        return [child for child in node if isinstance(child, Sexp) and child[0] == name]

    def get_simple_attributes(node):
        return {
            child[0]: child
            for child in node[2:]
            if isinstance(child, Sexp) and child[0] not in ("property", "symbol")
        }

    def compare_properties(prop1, prop2):
        if prop1[1] != prop2[1] or prop2[2] != prop1[2]:
            return False

        effects1 = prop1.search("/property/effects", ignore_case=True)
        effects2 = prop2.search("/property/effects", ignore_case=True)

        if not effects1 and not effects2:
            return True
        if not effects1 or not effects2:
            return False

        def effects_to_dict(effects):
            result = {}
            for item in effects[1:]:
                if not isinstance(item, Sexp):
                    continue
                if item[0] == "font":
                    result["font"] = tuple(item[1][1:]) if len(item) > 1 else tuple()
                elif item[0] == "justify":
                    result["justify"] = item[1]
                elif item[0] == "hide":
                    result["hide"] = item[1]
            return result

        return effects_to_dict(effects1[0]) == effects_to_dict(effects2[0])

    def compare_pins(pin1, pin2):
        if pin1[1] != pin2[1] or pin1[2] != pin2[2]:
            return False

        num1 = pin1.search("/pin/number", ignore_case=True)
        num2 = pin2.search("/pin/number", ignore_case=True)
        if not num1 or not num2 or num1[0][1] != num2[0][1]:
            return False

        name1 = pin1.search("/pin/name", ignore_case=True)
        name2 = pin2.search("/pin/name", ignore_case=True)
        if not name1 or not name2 or name1[0][1] != name2[0][1]:
            return False

        at1 = pin1.search("/pin/at", ignore_case=True)
        at2 = pin2.search("/pin/at", ignore_case=True)
        if not at1 or not at2:
            return False

        if at1[0][1] != at2[0][1] or at1[0][2] != at2[0][2]:
            return False

        if len(at1[0]) > 3 and len(at2[0]) > 3:
            if at1[0][3] != at2[0][3]:
                return False
        elif len(at1[0]) > 3 or len(at2[0]) > 3:
            return False

        length1 = pin1.search("/pin/length", ignore_case=True)
        length2 = pin2.search("/pin/length", ignore_case=True)
        if not length1 or not length2 or length1[0][1] != length2[0][1]:
            return False

        hide1 = pin1.search("/pin/hide", ignore_case=True)
        hide2 = pin2.search("/pin/hide", ignore_case=True)
        if bool(hide1) != bool(hide2):
            return False

        alternates1 = [alt[1] for alt in pin1.search("/pin/alternate", ignore_case=True)]
        alternates2 = [alt[1] for alt in pin2.search("/pin/alternate", ignore_case=True)]
        return sorted(alternates1) == sorted(alternates2)

    def compare_units(unit1, unit2):
        if unit1[1] != unit2[1]:
            return False

        geom1 = [
            child for child in unit1 if isinstance(child, Sexp) and child[0] not in ("pin", "text")
        ]
        geom2 = [
            child for child in unit2 if isinstance(child, Sexp) and child[0] not in ("pin", "text")
        ]
        if sorted(str(g) for g in geom1) != sorted(str(g) for g in geom2):
            return False

        pins1 = get_named_children(unit1, "pin")
        pins2 = get_named_children(unit2, "pin")

        if len(pins1) != len(pins2):
            return False

        pin_dict1 = {
            pin.search("/pin/number", ignore_case=True)[0][1]: pin
            for pin in pins1
            if pin.search("/pin/number", ignore_case=True)
        }
        pin_dict2 = {
            pin.search("/pin/number", ignore_case=True)[0][1]: pin
            for pin in pins2
            if pin.search("/pin/number", ignore_case=True)
        }

        if set(pin_dict1.keys()) != set(pin_dict2.keys()):
            return False

        for pin_num in pin_dict1:
            if not compare_pins(pin_dict1[pin_num], pin_dict2[pin_num]):
                return False

        return True

    attrs1 = get_simple_attributes(symbol1)
    attrs2 = get_simple_attributes(symbol2)
    if set(attrs1.keys()) != set(attrs2.keys()):
        return False

    for key in attrs1:
        if attrs1[key] != attrs2[key]:
            return False

    props1 = {prop[1]: prop for prop in get_named_children(symbol1, "property")}
    props2 = {prop[1]: prop for prop in get_named_children(symbol2, "property")}
    if set(props1.keys()) != set(props2.keys()):
        return False

    for prop_name in props1:
        if not compare_properties(props1[prop_name], props2[prop_name]):
            return False

    units1 = get_named_children(symbol1, "symbol")
    units2 = get_named_children(symbol2, "symbol")
    if len(units1) != len(units2):
        return False

    unit_dict1 = {unit[1]: unit for unit in units1}
    unit_dict2 = {unit[1]: unit for unit in units2}
    if set(unit_dict1.keys()) != set(unit_dict2.keys()):
        return False

    for unit_name in unit_dict1:
        if not compare_units(unit_dict1[unit_name], unit_dict2[unit_name]):
            return False

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
