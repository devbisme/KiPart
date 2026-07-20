# History

## 2.7.0 (2026-07-20)

-   `kilib2csv`, `kilib2spd`, and `kilib2jpd` now handle KiCad's `extends` keyword. A part written with `(extends "base")` borrows the base part's units and pins and overrides only its properties; the readers copy those units and pins into it so it comes out as a whole part rather than an empty one. `extends` may chain and the base may sit anywhere in the library. `kipart.resolve_extends` is the single place this is done, called once the symbols have been read from a library.
-   A property can be named `Manf#`, as KiCad names some of its own. An SPD property name is now whatever sits before the colon — any one word holding neither whitespace nor a colon — rather than being held to the letters, digits, and underscores of a word. A name with a space in it remains the one thing SPD can't say. `spd.is_property_name` is the single place that rule is spelled, so `kilib2spd` and `jpd2spd` no longer drop or refuse such a property either.

-   Added the `cmpparts` command-line utility (and the `compare_libraries`, `compare_parts`, and `match_parts` functions) for comparing the parts of two or more libraries and reporting what differs. The libraries can be `.kicad_sym`, `.spd`, or `.jpd` files, in any mix, so a symbol library can be checked against the part description it was built from. Exits with 1 if the libraries differ, so it can serve as a check in a build.
-   `cmpparts --ignore-geometry` compares what a part *is* — its pins, their names, types, styles, visibility, and alternates, and the properties of the part — leaving out where the pins sit, how long they are, and how big the body is. Two libraries built from the same pinout with different `--push` or `--bundle` settings compare equal under it.
-   `cmpparts --format` chooses how the report is written: `text` (the default), `rich` for a table in the terminal, `html` for a table opened in the browser, or `json` for another program to read. The tabular formats give a column to each library, so what changed reads across the row. `--output` says where the report goes, and `--no-browser` writes the HTML page without opening it.
-   `cmpparts -f html` opens the page in the default *web browser* rather than handing it to the desktop's generic file opener. On Linux the generic opener gives a `file://` page to whatever program claims the `text/html` file type, which needn't be a browser: a mail client registered for HTML (Thunderbird, as a snap, does) swallows the page and shows nothing while reporting success.
-   `cmpparts -f html` says so when there's no browser to be found, rather than claiming to have opened one. The page is written either way, and the warning names it so it can be opened by hand.
-   The browser opened by `cmpparts -f html` no longer chatters into the terminal. A browser is spawned as a child of the process and inherits its output, so its startup grumbles (GTK modules, and the like) used to land in the middle of the user's shell prompt.
-   The rich table is drawn only as wide as its contents need rather than stretched across the terminal, and `--wide` stretches it. The libraries are named in full above the table so their columns can go by filename alone, since a path in a column heading sets the width of the whole table.
-   `cmpparts -i units` sets the unit boundaries of a part aside and compares its pins as one table, so a part drawn as a single unit and the same part split across several come out alike. Nothing about the units themselves is then reported, but every difference in the pins still is.
-   `cmpparts` now compares a pin's alternate functions the way it compares the pin's own name: alternates are matched by name, an alternate that only one part has is flagged by name (`missing alternate`), and an alternate both parts share has its type and style compared (`alternate 'TX' type`). It used to report only that the set of alternate names differed, saying nothing about a changed type or style.
-   `cmpparts --match` pairs parts up across libraries whose names don't agree: `exact`, `normalized` (case and punctuation set aside, the default), `fuzzy` (names merely alike), or `pins` (recognizing a part by its pinout alone). `--alias OLD=NEW` pairs two parts up by hand.
-   Added the `kilib2jpd` command-line utility (and the `symbol_lib_to_jpd` and `kilib2jpd` functions) for reading a KiCad symbol library straight into a JPD description, which took `kilib2spd | spd2jpd` before.
-   Added `part.py`, which owns the neutral part structure the formats share. `symbol_to_part` is now the one reader of a `.kicad_sym` symbol into it, and `load_parts` reads a part out of any of the three formats. `kilib2spd` works from it rather than walking the S-expression itself.

## 2.6.0 (2026-07-14)

-   Added `kilib2spd` command-line utility (and `symbol_to_spd`, `symbol_lib_to_spd`, and `symbol_lib_file_to_spd_file` functions) for converting KiCad symbol libraries into SPD files, reversing the `spd2csv` + `kipart` pipeline.
-   Adjacent pins sharing a type, style, and name (or a run of incrementing names) are combined onto a single SPD line unless `--no-compress` is given.
-   Gaps between the pins on a side are written out as `*` spacers.
-   Fixed comment handling in SPD files: `;` and `//` now only start a comment at the beginning of a line or after whitespace, so values such as `Datasheet: https://example.com/ds.pdf` are no longer truncated.
-   Added the JPD (JSON Part Description) format, which holds the same information as an SPD file as JSON. See JPD.md.
-   Added `spd2jpd` and `jpd2spd` command-line utilities (and `spd_to_jpd`, `jpd_to_spd`, `spd2jpd`, and `jpd2spd` functions) for converting between the SPD and JPD formats.
-   Added SPD.md, a reference for the SPD format.
-   Moved the SPD format itself into `spd.py`, which owns its comment syntax, type codes, style modifiers, pin naming rules, and pin-line reading and writing. `spd2csv`, `kilib2spd`, and `jpd` are now converters built on top of it.
-   Added `spd.parse_spd_symbol`, the single reader of SPD's directives, which returns a structured part in the shape of the JPD format. `spd2csv` and `jpd` both work from it rather than each walking the lines of a symbol themselves.
-   `spd2csv` now writes pin styles under the names KiCad gives them, so the Style column holds `line` where it used to be left empty and `non_logic` where it used to say `analog`. Both produce the same symbols as before.
-   Only a line containing `*` creates a spacer. An empty line never did so in an SPD file, but could when symbol lines were passed to `convert_spd_symbol` directly.
-   Added spacer lines that leave several pin positions empty, written either as repeated asterisks (`***`) or as a count (`*3`). `kilib2spd` and `jpd2spd` write a run of spacers in the counted form.
-   SPD lines that are neither a directive, a spacer, nor a pin are now reported as errors. A pin line missing its pin number, or a misspelled side directive, used to be skipped without a word.

## 2.5.0 (2026-03-17)

-   Added alternate pin handling: when a pin number appears multiple times, the subsequent pins become alternates of the first pin.
-   Added Style and Hidden columns to spd2csv CSV output.
-   Added pin style modifiers in SPD files such as `!` = inverted, `>` = clock, `-` = hidden.
-   Combined modifiers supported: `!>` = inverted_clock.
-   Added support for `//` comments in addition to `;` comments in SPD files.
-   Added part properties support in SPD files using `property_name: property_value` format.
-   Added multi-pin bus support with automatic pin name incrementing.
-   Added spacer pin support (empty lines or lines containing just `*` create skipped pin positions).
-   Fixed pin naming: when pin name doesn't end with a number but has multiple pin numbers, the name is used as-is without appending incrementing index.
-   Added comprehensive unit tests for spd2csv.

## 2.4.0 (2026-03-14)

-   Added `spd2csv` command-line utility for converting SPD (Shorthand Part Description) symbol description format to CSV for use with kipart.
-   Added multi-unit symbol support in SPD files via the `unit <name>` directive.
-   Added ability for kipart to read CSV from stdin when no input files are given.

## 2.3.0 (2026-01-30)

-   Added `--justify` parameter for controlling text justification on symbols.
-   Added support for custom properties that are placed below the symbol body.
-   Added `--bundle-style` option for choosing a suffix for bundled pins.
-   Added `-1`/`--one-symbol` option for ignoring empty rows in CSV files.
-   Added ability to bundle NC (no-connect) pins when `-b` flag is specified twice.
-   Enable bundling of power_out pins.
-   Fixed bundled power_in pins becoming global nets.
-   Fixed truncation behavior: `-w` without `-m` now properly truncates the destination file.
-   Moved validation of overwrite and merge operations into the row_file_to_symbol_file function.
-   Improved spacing and breathing room on symbol properties.
-   Fixed gridify rounding to round from zero.
-   Updated tests to account for changes in overwrite/merge flag handling and output status messages.
-   Fixed unit tests for bundle_pins() changes.
-   Improved usage text formatting with code fencing.
-   Fixed handling of rows of symbol properties.

## 2.2.0 (2025-11-23)

-   Names in the unit column of the CSV are now displayed in the unit name drop-down of the Symbol Editor.
-   Added `hide-pin-num` to remove pin numbers on generated symbols.

## 2.1.0 (2025-05-26)

-   Symbol pin lengths are now sized to fit the longest pin number.
-   Symbol property names and values can now be placed on rows between the symbol name row and the pin rows.
-   Symbol properties are now placed so they don't overlap any symbol unit if the units have differing sizes.
-   Prepending asterisks to a pin number will insert blank pin spaces in the symbol. 
-   Multiple asterisks can be used to insert multiple blank pin spaces.
-   Bundled pins now have the number of pins in the bundle appended to the pin name within brackets.
-   Added `--alt-delimiter` option to split pin names using a given delimiter and assign them as alternate pin names.

## 2.0.0 (2025-05-25)

-   Complete rewrite to support modern KiCad symbol libraries based on S-expressions.

## 1.4.2 (2023-07-26)

-   Prevent bundling of spacer pins.

## 1.4.1 (2023-01-05)

-   Swapped test on -a and -w flags so appending with overwrite doesn't
    erase all the existing parts.

## 1.4.0 (2022-11-23)

-   Pin lengths are scaled to fit the size of the pin numbers.
-   Part information is placed consistently regardless of part origin
    (either pin #1 or center).
-   Fixed exceptions caused by malformed input pin data.

## 1.3.0 (2022-10-23)

-   Multiple asterisks can be prepended to pin numbers to create more
    than one blank pin location.

## 1.2.0 (2022-08-25)

-   Added ability to process KiCad V6 symbol libraries to kilib2csv.

## 1.1.0 (2022-07-21)

-   No-connect pins were added to the types of pins that can be bundled.
-   Option was added to select the suffix for bundled pins: none, count
    ([\[n\]]{.title-ref}), or range ([\[n:0\]]{.title-ref}).
-   Option was added to center the symbol on the origin.
-   Option was added to \"scrunch\" pin columns closer together between
    top/bottom pin rows.
-   Changes made to conform to KiCad Library Conventions.

## 1.0.0 (2021-09-17)

-   Decided this tool has matured to the point it could be called 1.0.0.

## 0.1.45 (2020-11-18)

-   Added option to set thickness of schematic symbol box.
-   Added option to push pins left/up or right/down on the sides of the
    schematic symbol box.
-   Removed reference to Lattice Diamond tool since it\'s no longer
    supported.

## 0.1.44 (2020-07-21)

-   Added \"other\" category to stm32cube_reader.py to remain compatible
    with new STM32cube software.
-   KiPart will now use a \<name\>\_reader.py file in the current
    directory to process part information.
-   Cleaned up tests directory.

## 0.1.43 (2020-05-25)

-   Fixed missing field label for description in F5.

## 0.1.42 (2020-04-30)

-   Updated Lattice FPGA pinout reader.

## 0.1.41 (2020-04-07)

-   Added option to select schematic symbol fill style.

## 0.1.40 (2020-02-26)

-   Handled differing line terminations between Python 2/3 when
    converting XLSX to CSV file.

## 0.1.39 (2020-02-25)

-   Fixed Python 2 str.lower() error requiring conversion of str to
    unicode.

## 0.1.38 (2020-02-24)

-   Added missing parameter to stm32cube_reader().

## 0.1.37 (2020-01-28)

-   Added requirement for openpyxl.

## 0.1.36 (2019-10-31)

-   KiPart now accepts part data stored in Excel .xlsx files.
-   Added reader for GOWIN FPGA pin tables.

## 0.1.35 (2019-09-19)

-   Kipart now creates individual .lib files if given multiple .csv
    files with no global output .lib file specified using the -o option.
-   kilib2csv now creates individual .csv files if given multiple .lib
    files with no global output .csv file specified using the -o option.

## 0.1.34 (2019-06-27)

-   All symbols now include F2 (package) and F3 (datasheet) fields.
-   Datasheet link and part description can be entered on the first line
    of a part description in the CSV file.

## 0.1.33 (2018-01-03)

-   Fixed error in field syntax for part manufacturer number.
-   No-connect pins can no longer be bundled because it is marked as an
    ERC error by EESCHEMA.

## 0.1.32 (2017-12-08)

-   Pins sorted by name or row are now pplaced top-to-bottom on
    left/right sides and left-to-right on top/bottom sides.

## 0.1.31 (2017-10-10)

-   Removed \*\_ in statement that caused an error in Python2.
-   Removed duplicated entries in pin-style table.
-   \~ and \# are now allowed in pin-style keys.
-   Parts dictionary changed to OrderedDict so it retains the order
    parts were entered in. Important for passing random part generation
    tests.

## 0.1.30 (2017-10-05)

-   Specifying `-a` option allows new parts to be written to an existing
    library but prevents overwriting existing parts. Using `-w` in
    conjunction with `-a` allows added parts to overwrite existing
    parts.
-   Part name, reference prefix, footprint, and manf. part num. are now
    allowed on beginning row of part info in a CSV file.
-   Expanded the lists of mnemonics for pin types and styles.

## 0.1.29 (2017-07-31)

-   Fixed erroneous library generation when part number is omitted from
    first line of CSV file.
-   Changed default output library to `kipart.lib` if no output library
    is specified.
-   Changed default output CSV file of kilib2csv to `kipart.csv` if no
    output CSV file is specified.

## 0.1.28 (2017-07-27)

-   Added reader for Lattice FPGA devices (except iCE40). (Thanks,
    Adrien Descamps!)

## 0.1.27 (2017-05-24)

-   Fixed issue #11 (blank lines in CSV file were skipped and multiple
    parts ran together).

## 0.1.26 (2017-05-21)

-   Fixed issue #18 (crash when symbol side for pin was left blank).

## 0.1.25 (2017-05-03)

-   Fixed problem caused by pin side designators not being lower-case
    (e.g., \"Left\").

## 0.1.24 (2016-12-22)

-   Fixed Xilinx reader function to parse leading comments in their FPGA
    pin files.

## 0.1.23 (2016-12-13)

-   Added ability to create hidden pins.

## 0.1.22 (2016-11-29)

-   Fixed readers for Xilinx, STM32, PSoC devices.
-   Pins on multiple sides of a symbol are now distributed in a more
    attractive manner.

## 0.1.21 (2016-09-20)

-   Extra stuff on starting line of library no longer kill kilib2csv.

## 0.1.20 (2016-09-16)

-   Fixed bug where kilib2csv was choking on footprint lists in part
    definitions.

## 0.1.19 (2016-09-16)

-   Added utility to test kilib2csv and kipart on randomly-generated CSV
    part files.

## 0.1.18 (2016-09-14)

-   kilib2csv utility added to convert KiCad schematic symbol libraries
    into CSV files suitable for input to KiPart.

## 0.1.17 (2016-06-15)

-   Use same type of sorting for unit names as for pin names so (for
    example) unit \'ADC_12\' comes before unit \'ADC_2\'.

## 0.1.16 (2016-06-12)

-   Added reader for CSV-formatted pinout files exported from the
    STM32CubeMx tool. (Thanks, Hasan Yavuz OZDERYA!)

## 0.1.15 (2016-02-17)

-   Added reader for Xilinx Ultrascale FPGAs.
-   Fixed insertion of spaces between groups of pins when pin number
    starts with \'\*\'.
-   Replaced call to warnings.warn with issues() function.
-   fix_pin_data() now strips leading/trailing spaces from pin
    information.

## 0.1.14 (2016-01-30)

-   Fixed incorrect y-offset of pins for symbols that only have pins
    along the right side.

## 0.1.13 (2015-09-09)

-   The number of pins in a bundle is now appended to the pin name
    instead of an \'\*\'.

## 0.1.12 (2015-09-03)

-   Added capability to insert non-existent \"gap\" pins that divide
    groups of pins into sections.

## 0.1.11 (2015-09-02)

-   future module requirement added to setup.py.

## 0.1.10 (2015-08-26)

-   Now runs under both Python 2.7 and 3.4.

## 0.1.9 (2015-08-21)

-   The bundling option now only bundles pins where that operation makes
    sense: power input pins (e.g., VCC and GND) and no-connect pins.

## 0.1.8 (2015-08-17)

-   Input data from the CSV file is now scanned for errors and fixed
    before it can cause problems in the library file.

## 0.1.7 (2015-08-14)

-   Added reader functions for Xilinx Virtex-6 and Spartan-6.
-   Broke-out reader functions into separate modules.
-   TXT and CSV files are now acceptable as part data files, but the
    reader has to be built to handle it.

## 0.1.6 (2015-08-13)

-   Fuzzy string matching is now used for the column headers.
-   Choice-type options are now case-insensitive.

## 0.1.5 (2015-07-29)

-   Multiple parts can now be described in a single CSV file.
-   Added function and option for reading Cypress PSoC5LP CSV files.
-   Simplified key generators for sorting pins by name or number.
-   Improved ordering of pins by name.

## 0.1.4 (2015-07-27)

-   Added option for approximate (fuzzy) matching for pin types, styles
    and orientations (sides).

## 0.1.3 (2015-07-26)

-   Multiple pins with the same name are now hidden by reducing their
    pin number size to zero (rather than enabling the hidden flag which
    can cause problems with power-in pins).

## 0.1.2 (2015-07-24)

-   Symbols can now have pins on any combination of left, right, top and
    bottom sides.
-   Added option to append parts to an existing library.
-   Refactored kipart routine into subroutines.
-   Added documentation.

## 0.1.1 (2015-07-21)

-   Fixed calculation of pin name widths.
-   Made CSV row order the default for arranging pins on the schematic
    symbol.
-   Fixed sorting key routine for numeric pin numbers.
-   Spaces are now stripped between fields in a CSV file.

## 0.1.0 (2015-07-20)

-   First release on PyPI.
