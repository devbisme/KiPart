.. :changelog:

History
-------

0.1.5 (2015-07-29)
---------------------
* Multiple parts can now be described in a single CSV file.
* Added function and option for reading Cypress PSoC5LP CSV files.
* Simplified key generators for sorting pins by name or number.
* Improved ordering of pins by name.
* Bumped version number.

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
