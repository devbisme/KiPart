===============================
KiPart
===============================

.. image:: https://img.shields.io/pypi/v/kipart.svg
        :target: https://pypi.python.org/pypi/kipart


Generate multi-unit schematic symbols for KiCad from a CSV file.

* Free software: MIT license
* Documentation: https://xesscorp.github.io/KiPart.

Features
--------

* Generates schematic part libraries for KiCad from CSV files.
* Converts lists of pins in a CSV file into a multi-unit schematic part symbol.
* Converts multiple CSV files stored in .zip archives.
* Each row of the CSV file lists the number, name, type, style, unit and side of a pin.
* Pins on a unit with the same name (e.g., GND) can be placed at the same location
  so they can all be tied to the same net with a single connection.
* Also includes ``kilib2csv`` for converting schematic part libraries into
  CSV files suitable for input to KiPart.
