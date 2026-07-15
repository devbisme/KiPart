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
- `kipart/part.py` — **owns the neutral part structure** that `parse_spd_symbol`
  returns and JPD spells out. `symbol_to_part` is the one reader of a
  `.kicad_sym` symbol into it, and `load_parts` reads a part out of any of the
  three formats. Ask `symbol_to_part` for `geometry=True` and the part also
  carries what SPD and JPD can't say — pin positions, pin lengths, and the body
  shapes — which is what `kilib2spd` needs to work out spacers and what
  `compare_parts` needs to compare layouts.
- `kipart/spd2csv.py`, `kipart/kilib2spd.py`, `kipart/jpd.py` — converters that
  sit on top of `spd.py` and `part.py`: SPD→CSV, library→SPD, and SPD↔JPD
  (plus library→JPD).
- `kipart/compare_parts.py` — compares the parts of two or more libraries in any
  of the three formats, optionally disregarding geometry, and pairs up parts
  whose names don't agree. Owns the `cmpparts` command.
- `kipart/compare_symbols.py` — compares `.kicad_sym` symbols and libraries at
  the S-expression level, ignoring the order of properties, units, and pins. This
  is how you check a change to the *symbol writer* is safe; `compare_parts` is
  the one to reach for when the question is whether two libraries hold the same
  parts.

**The layering rule:** converters depend on `spd.py` and `part.py`, never on each
other. If you need something from a sibling converter, it belongs in one of those
two. Anything about how SPD is *spelled* goes in `spd.py` — the whole point of
that module is that adding a directive or a modifier is a one-place change — and
anything that reads a `.kicad_sym` symbol into a part goes in `part.py`, so that
there is one such reader and not several. `part.py` may depend on `kipart.py` and
`spd.py`; neither of those may depend on it.

## Verifying a change

Run the tests, but don't stop there — the tests can't tell you a symbol came out
subtly wrong:

    pytest tests            # 163 tests
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

`cmpparts` is the quick way to ask the same question of two libraries built any
which way: `cmpparts -g old.kicad_sym new.kicad_sym` exits 0 when they hold the
same parts, whatever the layout, and names what changed when they don't.

`tests/examples/cmp_a.spd` and `cmp_b.spd` are a pair holding one difference of
every category `cmpparts` reports, for trying it out by hand. Their comments say
what those differences are, and `TestExampleLibraries` holds them to it — so if
you edit the pair, that's where it will tell you.

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
- **A pin number is a name, not a quantity.** KiCad quotes them, so `simp_sexp`
  hands them back as strings — but an unquoted one comes back as an `int`, and
  then `"1" != 1` quietly makes every pin of a part look missing. `part.py` reads
  pin numbers, names, types, and styles through `str()` for that reason. Anything
  else that compares pin numbers across formats should do the same.
- **`extends` is resolved only in the kilib2* read paths**, not universally.
  `kipart.resolve_extends` copies a base part's units and pins into a part that
  extends it, and it's called in `symbol_lib_to_parts` (feeding kilib2spd and
  kilib2jpd) and `symbol_lib_file_to_csv_file` (kilib2csv) — *not* in
  `extract_symbols_from_lib`, which `merge_symbol_libs` and `compare_symbols` use
  and which must leave the `extends` relationship intact. It lives in `kipart.py`
  because it's a `.kicad_sym`-structure operation and `part.py` may import it from
  there; a copy in `part.py` would break the layering.
