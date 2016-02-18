.. :changelog:

History
-------

0.1.15 (2016-02-17)
---------------------
* Added reader for Xilinx Ultrascale FPGAs.
* Fixed insertion of spaces between groups of pins when pin number starts with '*'.
* Replaced call to warnings.warn with issues() function.
* fix_pin_data() now strips leading/trailing spaces from pin information.

0.1.14 (2016-01-30)
---------------------
* Fixed incorrect y-offset of pins for symbols that only have pins along the right side.

0.1.13 (2015-09-09)
---------------------
* The number of pins in a bundle is now appended to the pin name instead of a *.

0.1.12 (2015-09-03)
---------------------
* Added capability to insert non-existent "gap" pins that divide groups of pins into sections.

0.1.11 (2015-09-02)
---------------------
* future module requirement added to setup.py.

0.1.10 (2015-08-26)
---------------------
* Now runs under both Python 2.7 and 3.4.

0.1.9 (2015-08-21)
---------------------
* The bundling option now only bundles pins where that operation makes sense:
  power input pins (e.g., VCC and GND) and no-connect pins.

0.1.8 (2015-08-17)
---------------------
* Input data from the CSV file is now scanned for errors and fixed before it can cause problems
  in the library file.

0.1.7 (2015-08-14)
---------------------
* Added reader functions for Xilinx Virtex-6 and Spartan-6.
* Broke-out reader functions into separate modules.
* TXT and CSV files are now acceptable as part data files, but the reader has to be built to handle it.

0.1.6 (2015-08-13)
---------------------
* Fuzzy string matching is now used for the column headers.
* Choice-type options are now case-insensitive.

0.1.5 (2015-07-29)
---------------------
* Multiple parts can now be described in a single CSV file.
* Added function and option for reading Cypress PSoC5LP CSV files.
* Simplified key generators for sorting pins by name or number.
* Improved ordering of pins by name.

0.1.4 (2015-07-27)
---------------------
* Added option for approximate (fuzzy) matching for pin types, styles and orientations (sides).

0.1.3 (2015-07-26)
---------------------
* Multiple pins with the same name are now hidden by reducing their pin number size to zero
  (rather than enabling the hidden flag which can cause problems with power-in pins).

0.1.2 (2015-07-24)
---------------------
* Symbols can now have pins on any combination of left, right, top and bottom sides.
* Added option to append parts to an existing library.
* Refactored kipart routine into subroutines.
* Added documentation.

0.1.1 (2015-07-21)
---------------------

* Fixed calculation of pin name widths.
* Made CSV row order the default for arranging pins on the schematic symbol.
* Fixed sorting key routine for numeric pin numbers.
* Spaces are now stripped between fields in a CSV file.

0.1.0 (2015-07-20)
---------------------

* First release on PyPI.
