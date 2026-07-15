# SPD: Shorthand Part Description

SPD is a plain-text format for describing a schematic symbol as a list of pins.
`spd2csv` converts it to CSV for `kipart`, and `kilib2spd` converts a KiCad
symbol library back into it.

    spd2csv part.spd | kipart -o part.kicad_sym
    kilib2spd part.kicad_sym            # the reverse: writes part.spd

## Structure

A file holds one or more parts. Each part starts with a `device` line, followed
by optional properties, then pins grouped under `unit` and side directives:

    ; Comment
    device part_name
    property_name: property value

    unit unit_name
        left
            pin_type  pin_name  pin_number
        right
            pin_type  pin_name  pin_number
        top
            ...
        bottom
            ...

Whitespace is ignored, so parts can be indented freely. Blank lines are ignored
too — they do *not* leave gaps between pins (use `*` for that).

Comments run to the end of the line and start with `;` or `//`, either at the
start of a line or after whitespace. A `//` inside a value is left alone, so
`Datasheet: https://example.com/ds.pdf` survives intact.

## Properties

Any `name: value` line after `device` sets a part property. The name is whatever
sits before the colon — any one word, holding neither whitespace nor a colon of
its own — and the value is the rest of the line. KiCad calls some of its own
properties things like `Manf#`, so a name isn't held to letters, digits, and
underscores.

    device mypart
    Reference: U
    Footprint: SOP-8
    Manf#: PIC32MM0064GPM028
    Datasheet: https://example.com/ds.pdf?rev=D#page=3

Only the first colon separates the name from the value, so a value can hold
colons of its own. The colon of a property line follows its name directly, which
is what tells `Manf#: Microchip` (a property) from `b SDA:SCL 5` (a pin whose
name happens to carry a colon).

A property of a KiCad symbol whose name has a space in it is the one thing SPD
can't handle; `kilib2spd` warns and skips it.

    Description: A short description of the part
    keywords: opamp analog
    my_property_1: My very own property!

`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`, `keywords`, and
`fp_filters` map onto KiCad's standard fields. Anything else becomes a custom
property.

## Units

`unit <name>` assigns the pins that follow it to a functional unit of the
symbol, each of which becomes a separate section in the KiCad symbol. A part
with no `unit` directive is a single-unit symbol.

    device mypart
    unit A
        left
            i       a0      1 2 3
        right
            o       y0      4 5 6
    unit B
        left
            i       b0      7 8 9

## Sides

`left`, `right`, `top`, and `bottom` set the side of the symbol that the pins
that follow are placed on. Pins are laid out in the order they're listed: down
the left and right sides, and across the top and bottom ones.

## Pins

A pin line is a type, a name, and one or more pin numbers:

    i       clk     12

### Pin types

| Code             | KiCad type     |
|------------------|----------------|
| p, pi, pwr       | power_in       |
| po, pwr_out      | power_out      |
| i, in            | input          |
| o, out           | output         |
| b, bi, io        | bidirectional  |
| t, tri           | tri_state      |
| oc               | open_collector |
| oe               | open_emitter   |
| pass             | passive        |
| f                | free           |
| u, un, a, analog | unspecified    |
| x, nc            | no_connect     |

### Style modifiers

Modifier characters attach to the type code, before or after it, and set the
pin's graphical style and visibility:

| Modifier      | Effect   |
|---------------|----------|
| `*` `!` `~` `/` `#` | inverted |
| `>`           | clock    |
| `_`           | low      |
| `@`           | analog   |
| `-`           | hidden   |

Modifiers combine: `i!>` is an inverted clock input, `-i!>` hides it as well.
The `_` modifier depends on the pin type, giving `input_low` on an input and
`output_low` on an output.

### Several pins on one line

Listing more than one pin number creates a pin per number:

    i       a0      1 2 3 4 5 6 7 8

If the name ends in a number it is incremented for each pin (`a0` through `a7`
above), which is handy for buses. If it doesn't, every pin gets the same name,
which is handy for power pins:

    p       gnd     10 20 30

### Alternate pins

Re-using a pin number defines an alternate function for that pin, which can
have its own name, type, and style. Here pin 10 is a GPIO whose alternate
function is a serial output:

    io      GPIO1   10
    o       TX      10

### Spacers

A line containing only `*` leaves an empty pin position on the current side:

    left
        p       vcc     1
        *                       // gap between vcc and gnd
        p       gnd     3

To leave several positions empty, repeat the asterisk or give a count after it.
These two are the same:

    ***
    *3

A count and repeated asterisks can't be combined, so `**2` is an error.

## Errors

Every line has to be one of the above: a `device` line, a property, a `unit` or
side directive, a spacer, or a pin. Anything else is an error rather than
something quietly skipped, so a pin line missing its number (`i vcc`) or a
misspelled directive (`lefft`) is reported instead of silently dropping a pin.

## Example

    ;
    ; RT9818 reset (SOT-23)
    ;
    device rt9818
    Manf: Richtek

    left
        a       vcc     3
        *
        a       gnd     2

    right
        *
        *
        i_      rst#    1
