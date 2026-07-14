# Working on kipart

Notes for anyone (human or AI) changing this codebase. The formats themselves are
documented in [SPD.md](SPD.md) and [JPD.md](JPD.md); this file covers the things
the code doesn't say out loud.

## What the modules are

Symbols reach KiCad along one path — a part description becomes CSV rows, and
kipart turns those rows into a `.kicad_sym` library:

    SPD ─┐
         ├─> CSV ─> .kicad_sym
    JPD ─┘

- `kipart/kipart.py` — the core: CSV rows ↔ `.kicad_sym`, plus symbol layout.
  Owns the `kipart` and `kilib2csv` commands.
- `kipart/spd.py` — **owns the SPD format**, in both directions: its comment
  syntax, pin type codes, style modifiers, pin naming rules, and the reading and
  writing of pin lines. `parse_spd_symbol` is the one reader of SPD's directives,
  and it returns a structured part shaped exactly like JPD.
- `kipart/spd2csv.py`, `kipart/kilib2spd.py`, `kipart/jpd.py` — converters that
  sit on top of `spd.py`: SPD→CSV, library→SPD, and SPD↔JPD.
- `kipart/compare_symbols.py` — compares symbols and libraries ignoring the order
  of properties, units, and pins. This is how you check a change is safe.

**The layering rule:** converters depend on `spd.py`, never on each other. If you
need something from a sibling converter, it belongs in `spd.py`. Anything about
how SPD is *spelled* goes in `spd.py` too — the whole point of that module is that
adding a directive or a modifier is a one-place change.

## Verifying a change

Run the tests, but don't stop there — the tests can't tell you a symbol came out
subtly wrong:

    pytest tests            # 63 tests
    tox                     # py39-py313

The real check is a round trip against `tests/examples/grabbag.spd`, which is a
deliberate torture case (multi-unit parts, alternates, buses, spacers, every pin
type and modifier). Convert it and compare with `compare_symbols`:

- **SPD → JPD → SPD** should produce identical CSV, and the JPD should be
  idempotent across a second trip.
- **library → SPD → library** should give zero `compare_symbol_pins` differences.
  Six of grabbag's eight symbols also come back byte-identical via
  `symbols_are_equal`; the two that don't (`opa2333`, `rt9818`) differ only in
  where a side's pins sit along its edge, which SPD deliberately doesn't record —
  kipart re-derives that from `--push`. Symbols built with `--bundle` don't come
  back byte-identical either, because their bundled pins are stacked at one spot.

## Gotchas

- **`tests/examples/*.kicad_sym` are gitignored build products**, not fixtures.
  `test.mk` regenerates them from the `.csv` and `.spd` files. A test that reads
  one will pass locally and fail on a fresh clone — build from `grabbag.spd`
  instead.
- **`str_to_type` and `str_to_style` in `kipart.py` accept loose aliases** (`pwr`,
  `inv_clk`, …) and have twice mapped a value to the wrong result. New code should
  validate against KiCad's canonical names — `spd.KICAD_TYPE_TO_SPD` and
  `spd.KICAD_STYLE_TO_SPD` are keyed by them — rather than route through the
  alias functions.
- **CSV row order is not symbol order.** kipart groups pins by unit and side and
  sorts within a side, so re-ordering rows across sides changes the CSV without
  changing the symbol. Compare symbols, not CSV text.
- **A pin number repeated within a unit becomes an alternate** of the pin that
  claimed it first. That's true of CSV rows, SPD lines, and JPD alike.
