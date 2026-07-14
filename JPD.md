# JPD: JSON Part Description

JPD is a JSON encoding of everything the [SPD format](SPD.md) can describe: a
list of parts, their properties, units, and pins. SPD is meant to be typed by
hand; JPD is meant to be produced and consumed by programs, so it spells out
what SPD leaves implicit.

`spd2jpd` and `jpd2spd` convert between the two, and SPD is the way on to a
KiCad library:

    spd2jpd part.spd            # Generates part.jpd
    jpd2spd part.jpd            # Generates part.spd
    jpd2spd -o - part.jpd | spd2csv | kipart -o part.kicad_sym

## Top level

The top-level value is an object with a `parts` array. `format` and `version`
identify the file.

```json
{
  "format": "jpd",
  "version": 1,
  "parts": [ ... ]
}
```

## Part

| Key          | Type   | Required | Meaning |
|--------------|--------|----------|---------|
| `name`       | string | yes      | Part name, as in SPD's `device` line. |
| `properties` | object | no       | Property name → value. Names are single words; values are any string. |
| `units`      | array  | yes      | One or more units. A single-unit part has one unnamed unit. |

```json
{
  "name": "rt9818",
  "properties": {
    "Manf": "Richtek",
    "Datasheet": "https://example.com/ds.pdf"
  },
  "units": [ ... ]
}
```

## Unit

| Key     | Type   | Required | Meaning |
|---------|--------|----------|---------|
| `name`  | string | no       | Unit name, as in SPD's `unit` directive. Omitted for a single-unit part. |
| `left`, `right`, `top`, `bottom` | array | no | The pins on that side, in the order they're placed: down the left and right sides, across the top and bottom ones. |

```json
{
  "name": "LOGIC",
  "left":  [ ... ],
  "right": [ ... ]
}
```

## Pin

Each element of a side array is a pin or a spacer.

| Key          | Type            | Required | Default | Meaning |
|--------------|-----------------|----------|---------|---------|
| `name`       | string          | yes      |         | Pin name. |
| `numbers`    | array of string | yes      |         | One entry per pin. Several entries create several pins from one object (see below). |
| `type`       | string          | no       | `passive` | Electrical type (see below). |
| `style`      | string          | no       | `line`  | Graphical style (see below). |
| `hidden`     | boolean         | no       | `false` | Whether the pin is hidden. |
| `increment`  | boolean         | no       | `false` | Auto-increment the name across `numbers` (see below). |
| `alternates` | array           | no       |         | Alternate functions for the pin (see below). |

Pin numbers are always strings, since they can be alphanumeric (`"A1"`, `"k4"`).

```json
{ "name": "clk", "numbers": ["12"], "type": "input", "style": "clock" }
```

### Several pins from one object

Listing more than one number creates one pin per number, all sharing the same
name — the way power and ground pins are usually drawn:

```json
{ "name": "gnd", "numbers": ["10", "20", "30"], "type": "power_in" }
```

Set `increment` to `true` to number the names off the first one instead, which
is how buses are written. This creates `a0` through `a7`:

```json
{ "name": "a0", "numbers": ["1","2","3","4","5","6","7","8"],
  "type": "input", "increment": true }
```

This is the one place SPD is ambiguous — it decides between the two forms by
looking for a numeric suffix on the name — so JPD makes it an explicit flag.

### Alternates

An alternate is a second function for the same pin, with its own name and
optionally its own type and style. It corresponds to re-using a pin number in
SPD. Here pin 10 is a GPIO whose alternate function is a serial output:

```json
{
  "name": "GPIO1", "numbers": ["10"], "type": "bidirectional",
  "alternates": [
    { "name": "TX", "type": "output", "style": "line" }
  ]
}
```

### Spacers

A spacer leaves empty pin positions on a side. `count` defaults to 1.

```json
{ "spacer": 2 }
```

## Types and styles

`type` is a KiCad electrical type: `input`, `output`, `bidirectional`,
`tri_state`, `passive`, `free`, `unspecified`, `power_in`, `power_out`,
`open_collector`, `open_emitter`, or `no_connect`.

`style` is a KiCad graphical style: `line`, `inverted`, `clock`,
`inverted_clock`, `input_low`, `output_low`, `clock_low`, `edge_clock_high`, or
`non_logic`.

Unlike SPD, JPD names types and styles in full rather than encoding them as
codes and modifier characters, and it keeps visibility in its own `hidden`
field rather than folding it into the type. So SPD's `-i!>` is:

```json
{ "type": "input", "style": "inverted_clock", "hidden": true }
```

## Equivalence with SPD

| SPD                        | JPD |
|----------------------------|-----|
| `device rt9818`            | `"name": "rt9818"` |
| `Manf: Richtek`            | `"properties": {"Manf": "Richtek"}` |
| `unit LOGIC`               | a unit object with `"name": "LOGIC"` |
| `left`                     | the unit's `left` array |
| `i clk 12`                 | `{"name": "clk", "numbers": ["12"], "type": "input"}` |
| `i!> clk 12`               | ...plus `"style": "inverted_clock"` |
| `-i clk 12`                | ...plus `"hidden": true` |
| `p gnd 10 20 30`           | `"numbers": ["10","20","30"]` |
| `i a0 1 2 3`               | ...plus `"increment": true` |
| a repeated pin number      | an entry in `alternates` |
| `*`                        | `{"spacer": 1}` |
| `*3` (or `***`)            | `{"spacer": 3}` |
| `; comment`                | no equivalent — JSON has no comments |

Comments are the one thing SPD carries that JPD can't. Everything that affects
the generated symbol survives a trip in either direction.

## Example

The RT9818 from the SPD reference, plus a two-unit 74HC00:

```json
{
  "format": "jpd",
  "version": 1,
  "parts": [
    {
      "name": "rt9818",
      "properties": { "Manf": "Richtek" },
      "units": [
        {
          "left": [
            { "name": "vcc", "numbers": ["3"], "type": "unspecified" },
            { "spacer": 1 },
            { "name": "gnd", "numbers": ["2"], "type": "unspecified" }
          ],
          "right": [
            { "spacer": 2 },
            { "name": "rst#", "numbers": ["1"], "type": "input",
              "style": "input_low" }
          ]
        }
      ]
    },
    {
      "name": "74hc00",
      "properties": { "Footprint": "soic-14" },
      "units": [
        {
          "name": "LOGIC",
          "left": [
            { "name": "a1", "numbers": ["1"], "type": "input" },
            { "name": "b1", "numbers": ["2"], "type": "input" }
          ],
          "right": [
            { "name": "y1", "numbers": ["3"], "type": "output",
              "style": "inverted" }
          ]
        },
        {
          "name": "PWR",
          "top":    [ { "name": "vcc", "numbers": ["14"], "type": "power_in" } ],
          "bottom": [ { "name": "gnd", "numbers": ["7"],  "type": "power_in" } ]
        }
      ]
    }
  ]
}
```
