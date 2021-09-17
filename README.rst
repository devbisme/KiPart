===============================
KiPart
===============================

.. image:: https://img.shields.io/pypi/v/kipart.svg
        :target: https://pypi.python.org/pypi/kipart

Generate multi-unit schematic symbols for KiCad from a CSV, text, or Excel file.

* Free software: MIT license
* Documentation: https://devbisme.github.io/KiPart.

Features
--------

* Generates schematic part libraries for KiCad from CSV/text/Excel files.
* Converts lists of pins in a file into a multi-unit schematic part symbol.
* Converts multiple files stored in .zip archives.
* Each row of the file lists the number, name, type, style, unit and side of a pin.
* Pins on a unit with the same name (e.g., GND) can be placed at the same location
  so they can all be tied to the same net with a single connection.
* Also includes ``kilib2csv`` for converting schematic part libraries into
  CSV files suitable for input to KiPart.

Example Use Case
----------------

From a user:

I had a very complex library for a microprocessor that I needed to refactor—
I needed to reorder hundreds of pins in a sane human-usable format. I thought
I was going to have do it by hand in KiCAD's graphical symbol editor. I tried
that, got very frustrated with all the clicking and dragging. 

So I then:

* searched and found this tool,
* used ``kilib2csv`` to export my KiCAD lib to CSV, 
* imported the CSV in a spreadsheet program 
* edited the spreadsheet (mainly sorting the pins by function using the 
  spreadsheet's ``sort()`` function), 
* exported the spreadsheet back to CSV, 
* used ``kipart`` to export back to KiCAD. 
  
Boom! Usable part in minutes.


