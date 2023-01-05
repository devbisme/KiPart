.. :changelog:

History
-------

1.4.1 (2023-01-05)
__________________

* Swapped test on -a and -w flags so appending with overwrite doesn't erase all the existing parts.


1.4.0 (2022-11-23)
__________________

* Pin lengths are scaled to fit the size of the pin numbers.
* Part information is placed consistently regardless of part origin (either pin #1 or center).
* Fixed exceptions caused by malformed input pin data.


1.3.0 (2022-10-23)
__________________

* Multiple asterisks can be prepended to pin numbers to create more than one blank pin location.


1.2.0 (2022-08-25)
__________________

* Added ability to process KiCad V6 symbol libraries to kilib2csv.


1.1.0 (2022-07-21)
__________________

* No-connect pins were added to the types of pins that can be bundled.
* Option was added to select the suffix for bundled pins: none, count (`[n]`), or range (`[n:0]`).
* Option was added to center the symbol on the origin.
* Option was added to "scrunch" pin columns closer together between top/bottom pin rows.
* Changes made to conform to KiCad Library Conventions.


1.0.0 (2021-09-17)
__________________

* Decided this tool has matured to the point it could be called 1.0.0.


0.1.45 (2020-11-18)
______________________

* Added option to set thickness of schematic symbol box.
* Added option to push pins left/up or right/down on the sides of the schematic symbol box.
* Removed reference to Lattice Diamond tool since it's no longer supported.


0.1.44 (2020-07-21)
______________________

* Added "other" category to stm32cube_reader.py to remain compatible with new STM32cube software.
* KiPart will now use a <name>_reader.py file in the current directory to process part information.
* Cleaned up tests directory.


0.1.43 (2020-05-25)
______________________

* Fixed missing field label for description in F5.


0.1.42 (2020-04-30)
______________________

* Updated Lattice FPGA pinout reader.


0.1.41 (2020-04-07)
______________________

* Added option to select schematic symbol fill style.


0.1.40 (2020-02-26)
______________________

* Handled differing line terminations between Python 2/3 when converting XLSX to CSV file.


0.1.39 (2020-02-25)
______________________

* Fixed Python 2 str.lower() error requiring conversion of str to unicode.


0.1.38 (2020-02-24)
______________________

* Added missing parameter to stm32cube_reader().


0.1.37 (2020-01-28)
______________________

* Added requirement for openpyxl.


0.1.36 (2019-10-31)
______________________

* KiPart now accepts part data stored in Excel .xlsx files.
* Added reader for GOWIN FPGA pin tables.


0.1.35 (2019-09-19)
______________________

* Kipart now creates individual .lib files if given multiple .csv files with no global output .lib file specified using the -o option.
* kilib2csv now creates individual .csv files if given multiple .lib files with no global output .csv file specified using the -o option.


0.1.34 (2019-06-27)
______________________

* All symbols now include F2 (package) and F3 (datasheet) fields.
* Datasheet link and part description can be entered on the first line of a part description in the CSV file.


0.1.33 (2018-01-03)
______________________

* Fixed error in field syntax for part manufacturer number.
* No-connect pins can no longer be bundled because it is marked as an ERC error by EESCHEMA.


0.1.32 (2017-12-08)
______________________

* Pins sorted by name or row are now pplaced top-to-bottom on left/right sides and left-to-right on top/bottom sides.


0.1.31 (2017-10-10)
______________________

* Removed \*_ in statement that caused an error in Python2.
* Removed duplicated entries in pin-style table.
* ~ and # are now allowed in pin-style keys.
* Parts dictionary changed to OrderedDict so it retains the order parts were entered in. Important for passing random part generation tests.


0.1.30 (2017-10-05)
______________________

* Specifying ``-a`` option allows new parts to be written to an existing library but prevents overwriting existing parts.
  Using ``-w`` in conjunction with ``-a`` allows added parts to overwrite existing parts.
* Part name, reference prefix, footprint, and manf. part num. are now allowed on beginning row of part info in a CSV file.
* Expanded the lists of mnemonics for pin types and styles.


0.1.29 (2017-07-31)
______________________

* Fixed erroneous library generation when part number is omitted from first line of CSV file.
* Changed default output library to ``kipart.lib`` if no output library is specified.
* Changed default output CSV file of kilib2csv to ``kipart.csv`` if no output CSV file is specified.


0.1.28 (2017-07-27)
______________________

* Added reader for Lattice FPGA devices (except iCE40). (Thanks, Adrien Descamps!)


0.1.27 (2017-05-24)
______________________

* Fixed issue #11 (blank lines in CSV file were skipped and multiple parts ran together).


0.1.26 (2017-05-21)
______________________

* Fixed issue #18 (crash when symbol side for pin was left blank).


0.1.25 (2017-05-03)
______________________

* Fixed problem caused by pin side designators not being lower-case (e.g., "Left").


0.1.24 (2016-12-22)
______________________

* Fixed Xilinx reader function to parse leading comments in their FPGA pin files.


0.1.23 (2016-12-13)
______________________

* Added ability to create hidden pins.


0.1.22 (2016-11-29)
______________________

* Fixed readers for Xilinx, STM32, PSoC devices.
* Pins on multiple sides of a symbol are now distributed in a more attractive manner.


0.1.21 (2016-09-20)
______________________

* Extra stuff on starting line of library no longer kill kilib2csv.


0.1.20 (2016-09-16)
______________________

* Fixed bug where kilib2csv was choking on footprint lists in part definitions.


0.1.19 (2016-09-16)
______________________

* Added utility to test kilib2csv and kipart on randomly-generated CSV part files.


0.1.18 (2016-09-14)
______________________

* kilib2csv utility added to convert KiCad schematic symbol libraries into CSV files suitable for input to KiPart.


0.1.17 (2016-06-15)
______________________

* Use same type of sorting for unit names as for pin names so (for example) unit 'ADC_12' comes before unit 'ADC_2'.


0.1.16 (2016-06-12)
______________________

* Added reader for CSV-formatted pinout files exported from the STM32CubeMx tool. (Thanks, Hasan Yavuz OZDERYA!)


0.1.15 (2016-02-17)
______________________

* Added reader for Xilinx Ultrascale FPGAs.
* Fixed insertion of spaces between groups of pins when pin number starts with '*'.
* Replaced call to warnings.warn with issues() function.
* fix_pin_data() now strips leading/trailing spaces from pin information.


0.1.14 (2016-01-30)
______________________

* Fixed incorrect y-offset of pins for symbols that only have pins along the right side.


0.1.13 (2015-09-09)
______________________

* The number of pins in a bundle is now appended to the pin name instead of an '*'.


0.1.12 (2015-09-03)
______________________

* Added capability to insert non-existent "gap" pins that divide groups of pins into sections.


0.1.11 (2015-09-02)
______________________

* future module requirement added to setup.py.


0.1.10 (2015-08-26)
______________________

* Now runs under both Python 2.7 and 3.4.


0.1.9 (2015-08-21)
______________________

* The bundling option now only bundles pins where that operation makes sense:
  power input pins (e.g., VCC and GND) and no-connect pins.


0.1.8 (2015-08-17)
______________________

* Input data from the CSV file is now scanned for errors and fixed before it can cause problems
  in the library file.


0.1.7 (2015-08-14)
______________________

* Added reader functions for Xilinx Virtex-6 and Spartan-6.
* Broke-out reader functions into separate modules.
* TXT and CSV files are now acceptable as part data files, but the reader has to be built to handle it.


0.1.6 (2015-08-13)
______________________

* Fuzzy string matching is now used for the column headers.
* Choice-type options are now case-insensitive.


0.1.5 (2015-07-29)
______________________

* Multiple parts can now be described in a single CSV file.
* Added function and option for reading Cypress PSoC5LP CSV files.
* Simplified key generators for sorting pins by name or number.
* Improved ordering of pins by name.


0.1.4 (2015-07-27)
______________________

* Added option for approximate (fuzzy) matching for pin types, styles and orientations (sides).


0.1.3 (2015-07-26)
______________________

* Multiple pins with the same name are now hidden by reducing their pin number size to zero
  (rather than enabling the hidden flag which can cause problems with power-in pins).


0.1.2 (2015-07-24)
______________________

* Symbols can now have pins on any combination of left, right, top and bottom sides.
* Added option to append parts to an existing library.
* Refactored kipart routine into subroutines.
* Added documentation.


0.1.1 (2015-07-21)
______________________

* Fixed calculation of pin name widths.
* Made CSV row order the default for arranging pins on the schematic symbol.
* Fixed sorting key routine for numeric pin numbers.
* Spaces are now stripped between fields in a CSV file.


0.1.0 (2015-07-20)
______________________

* First release on PyPI.
