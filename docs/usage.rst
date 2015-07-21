========
Usage
========

KiPart is mainly intended to be  used as a script::

    usage: kipart [-h] [-v] [-r [generic|xilinx7]] [-s [row|num|name]]
                  [-o [file.lib]] [-b] [-w] [-d [LEVEL]]
                  file1.[csv|zip] file2.[csv|zip] ... [file1.[csv|zip]
                  file2.[csv|zip] ... ...]

    Generate KiCad multi-unit schematic symbols from a CSV file.

    positional arguments:
      file1.[csv|zip] file2.[csv|zip] ...
                            Files for parts in CSV format or as CSV files in .zip
                            archives.

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -r [generic|xilinx7], --reader [generic|xilinx7]
                            Name of function for reading the CSV file.
      -s [row|num|name], --sort [row|num|name]
                            Sort the part pins by their entry order in the CSV
                            file, their pin number, or their pin name.
      -o [file.lib], --output [file.lib]
                            Generated KiCad library for part.
      -b, --bundle          Bundle multiple pins with the same name into a single
                            schematic pin.
      -w, --overwrite       Allow overwriting of an existing part library.
      -d [LEVEL], --debug [LEVEL]
                            Print debugging info. (Larger LEVEL means more info.)
                        
A generic part file is expected when the `-r generic` option is specified.
It contains the following items:

#. The part name or number is on the first line.
#. The second line is blank.
#. The third line contains the column headers. The required headers are 'Pin', 'Name', 'Unit', and 'Type'.
   These can be placed in any order and in any column.
#. On each row, enter the pin number, name, unit identifier (if the schematic symbol will have multiple units),
   and pin type. Each of these items should be entered in the column with the appropriate header.

   * Pin numbers can be either numeric (e.g., '69') if the part is a DIP or QFP, or they can be
     alphanumeric (e.g., 'C10') if a BGA or CSP is used.
   * Pin names can be any combination of letters, numbers and special characters (except a comma).
   * The unit identifier can be any combination of letters, numbers and special characters (except a comma).
     A separate unit will be generated in the schematic symbol for each distinct unit identifier.
   * The allowable pin types are:
        * input
        * output
        * bidirectional
        * tristate
        * passive
        * unspecified
        * power_in
        * power_out
        * open_collector
        * open_emitter
        * no_connect

When the option `-r xilinx7` is used, the individual CSV pin files or entire .zip archives
`for the Xilinx 7-Series FPGAs <http://www.xilinx.com/support/packagefiles/>`_ can be processed.

The `-s` option specifies the arrangement of the pins in the schematic symbol:

* `-s row` places the pins in the order they were entered into the CSV file.
* `-s num` places the pins such that their pin numbers are in increasing order.
* `-s name` places the pins in increasing order of their names.

Specifying the `-b` option will place multiple pins with the identical names at the same location
such that they can all attach to the same net with a single connection.
This is helpful for handling the multiple VCC and GND pins found on many high pin-count devices.


Examples
-----------

Assume the following data for a single-unit part is placed into the `example.csv` file::

    example_part

    Pin,    Unit,   Type,           Name
    23,     1,      input,          A5
    90,     1,      output,         B1
    88,     1,      bidirectional,  C3
    56,     1,      tristate,       D22
    84,     1,      tristate,       D3
    16,     1,      power_in,       VCC
    5,      1,      power_in,       GND
    29,     1,      power_in,       VCC
    98,     1,      power_in,       GND
    99,     1,      power_in,       VCC
    59,     1,      power_in,       GND

Then the command `kipart example.csv -o example1.lib` will create a schematic symbol
where the pins are arranged in the order of the rows in the CSV file they are on:

.. image:: example1.png

The command `kipart -s num example.csv -o example2.lib` will create a schematic symbol
where the pins are arranged by their pin numbers:

.. image:: example2.png

The command `kipart -s name example.csv -o example3.lib` will create a schematic symbol
where the pins are arranged by their names:

.. image:: example3.png

The command `kipart -b example.csv -o example4.lib` will bundle pins with identical names 
(like `GND` and `VCC`) into single pins like so:

.. image:: example4.png
