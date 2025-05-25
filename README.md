# KiPart

[![image](https://img.shields.io/pypi/v/kipart.svg)](https://pypi.python.org/pypi/kipart)

Generate multi-unit schematic symbols for KiCad from a CSV, text, or
Excel file.

-   Free software: MIT license
-   Documentation: <https://devbisme.github.io/KiPart>.

## Features

-   Generates schematic part libraries for KiCad from CSV/text/Excel
    files.
-   Converts lists of pins in a file into a multi-unit schematic part
    symbol.
-   Converts multiple files stored in .zip archives.
-   Each row of the file lists the number, name, type, style, unit and
    side of a pin.
-   Pins on a unit with the same name (e.g., GND) can be placed at the
    same location so they can all be tied to the same net with a single
    connection.
-   Also includes `kilib2csv` for converting schematic part libraries
    into CSV files suitable for input to KiPart.

## Example Use Case

From a user:

I had a very complex library for a microprocessor that I needed to
refactor--- I needed to reorder hundreds of pins in a sane human-usable
format. I thought I was going to have do it by hand in KiCAD\'s
graphical symbol editor. I tried that, got very frustrated with all the
clicking and dragging.

So I then:

-   searched and found this tool,
-   used `kilib2csv` to export my KiCAD lib to CSV,
-   imported the CSV in a spreadsheet program
-   edited the spreadsheet (mainly sorting the pins by function using
    the spreadsheet\'s `sort()` function),
-   exported the spreadsheet back to CSV,
-   used `kipart` to export back to KiCAD.

Boom! Usable part in minutes.

## Installation

Simple enough:

    pip install kipart

This will install two command-line utilities:

-   `kipart`: The main utility for generating schematic symbols from rows of pin data
        stored in CSV or Excel files.
-   `kilib2csv`: A utility for converting existing KiCad libraries into
        CSV files. This is useful for converting existing libraries into a format that
        can be used with KiPart.

## Usage

### KiPart

KiPart is mainly intended to be used as a script:

    usage: kipart [-h] [-v] [-r] [--side {left,right,top,bottom}] [-o OUTPUT] [-w] [-s {row,num,name}] [-a ALT_DELIMITER] [-b] [--scrunch] [--circulate] [-m]
                input_files [input_files ...]

    Convert CSV or Excel files to KiCad symbol libraries

    positional arguments:
    input_files           Input CSV or Excel files (.csv, .xlsx, .xls)

    options:
    -h, --help            show this help message and exit
    -v, --version         show program's version number and exit
    -r, --reverse         Sort pins in reverse order
    --side {left,right,top,bottom}
                            Which side to place the pins by default
    -o OUTPUT, --output OUTPUT
                            Generated KiCad symbol library (.kicad_sym)
    -w, --overwrite       Allow overwriting of an existing part library
    -s {row,num,name}, --sort {row,num,name}
                            Sort the part pins by their entry order in the CSV file (row), their pin number (num), or their pin name (name)
    -a ALT_DELIMITER, --alt-delimiter ALT_DELIMITER
                            Delimiter character for splitting pin names into alternatives
    -b, --bundle          Bundle identically-named power or ground pins into single schematic pins
    --scrunch             Compress pins of left/right columns underneath top/bottom rows
    --circulate           Reverse the direction and starting point of pins on the top and right sides
    -m, --merge           Merge with existing library rather than overwriting completely

The main input to `kipart` is one or more CSV or Excel files.
These contain the following items:

1.  The part name or number stands alone on row. The following five
    cells on the same row can contain: #. A reference prefix such as `R`
    (defaults to `U` if left blank), #. A footprint such as
    `Diodes_SMD:D_0603` (defaults to blank), #. A manufacturer\'s part
    number such as `MT48LC16M16A2F4-6A:GTR` (defaults to blank). #. A
    link to the part\'s datasheet. #. A description of the part.
2.  The next non-blank row contains the column headers. The required
    headers are \'Pin\' and \'Name\'. Optional columns are \'Unit\',
    \'Side\', \'Type\', \'Style\', and \'Hidden\'. These can be placed
    in any order and in any column.
3.  On each succeeding row, enter the pin number, name, unit identifier
    (if the schematic symbol will have multiple units), pin type and
    style. Each of these items should be entered in the column with the
    appropriate header.
    -   Pin numbers can be either numeric (e.g., \'69\') if the part is
        a DIP or QFP, or they can be alphanumeric (e.g., \'C10\') if a
        BGA or CSP is used. Using one or more [\*]{.title-ref}
        characters instead of a pin number creates non-existent \"gap\"
        pins that can be used to visually separate the pins into groups.
        (This only works when the `-s row` sorting option is selected.)

    -   Pin names can be any combination of letters, numbers and special
        characters (except a comma).

    -   The unit identifier can be blank or any combination of letters,
        numbers and special characters (except a comma). A separate unit
        will be generated in the schematic symbol for each distinct unit
        identifier.

    -   

        The side column specifies the side of the symbol the pin will be placed on. The allowable values are:

        :   -   left
            -   right
            -   top
            -   bottom

    -   

        The type column specifies the electrical type of the pin. The allowable values are:

        :   -   input, inp, in, clk
            -   output, outp, out
            -   bidirectional, bidir, bi, inout, io, iop
            -   tristate, tri
            -   passive, pass
            -   unspecified, un, analog
            -   power_in, pwr_in, pwrin, power, pwr, ground, gnd
            -   power_out, pwr_out, pwrout, pwr_o
            -   open_collector, opencollector, open_coll, opencoll, oc
            -   open_emitter, openemitter, open_emit, openemit, oe
            -   no_connect, noconnect, no_conn, noconn, nc

    -   

        The style column specifies the graphic representation of the pin. The allowable pin styles are:

        :   -   line, \<blank\>
            -   inverted, inv, \~, \#
            -   clock, clk, rising_clk
            -   inverted_clock, inv_clk, clk_b, clk_n, \~clk, #clk
            -   input_low, inp_low, in_lw, in_b, in_n, \~in, #in
            -   clock_low, clk_low, clk_lw, clk_b, clk_n, \~clk, #clk
            -   output_low, outp_low, out_lw, out_b, out_n, \~out, #out
            -   falling_edge_clock, falling_clk, fall_clk
            -   non_logic, nl, analog

    -   The hidden column specifies whether the pin is visible in
        Eeschema. This can be one of \'y\', \'yes\', \'t\', \'true\', or
        \'1\' to make it invisible, anything else makes it visible.
4.  A blank row ends the list of pins for the part.
5.  Multiple parts (each consisting of name, column header and pin rows)
    separated by blank lines are allowed in a single CSV file. Each part
    will become a separate symbol in the KiCad library.

When the option `-r xilinx7` is used, the individual pin files or entire
.zip archives for the [Xilinx 7-Series
FPGAs](http://www.xilinx.com/support/packagefiles/) can be processed.

When the option `-r stm32cube` is used, the input file should be the pin
layout file exported from the STM32CubeMx tool. To create this file,
create a project with STM32CubeMx and then from window menu select
\"Pinout -\> Generate CSV pinout text file\". If you select pin features
or define labels for pins these will be reflected in the generated
library symbol.

When the option `-r lattice` is used, the input file should come from
the Lattice website.

The `-s` option specifies the arrangement of the pins in the schematic
symbol:

-   `-s row` places the pins in the order they were entered into the
    file.
-   `-s name` places the pins in increasing order of their names.
-   `-s num` places the pins in increasing order of their pin numbers
    and arranged in a counter-clockwise fashion around the symbol
    starting from the upper-left corner.

The `--reverse` option reverses the sort order for the pins.

Using the `--side` option you can set the default side for the pins. The
option from the file will override the command line option. The default
choice is `left`.

Specifying the `-f` option enables *fuzzy matching* on the pin types,
styles and sides used in the CSV file. So, for example, `ck` would match
`clk` or `rgt` would match `right`.

Specifying the `-b` option will place multiple pins with the identical
names at the same location such that they can all attach to the same net
with a single connection. This is helpful for handling the multiple VCC,
GND, and NC pins found on many high pin-count devices.

The `--annotation` option determines the suffix added to bundled pin names:

:   -   `none`: No suffix is added.
    -   `count`: The number of bundled pins is added as `[n]`.
    -   `range`: The range of bundled pins is added as `[n:0]`.

The `-w` option is used to overwrite an existing library with any new
parts from the file. The old contents of the library are lost.

The `-a` option is used to add parts to an existing library. If a part
with the same name already exists, the new part will only overwrite it
if the `-w` flag is also used. Any existing parts in the library that
are not overwritten are retained.

Specifying the `--fill` option will determine how symbol boxes are
filled:

-   `no_fill`: Default. Schematic symbols are created with no filled
    boxes.
-   `fg_fill`: Symbol boxes will be foreground filled
-   `bg_fill`: Symbol boxes will be background filled. (This is the
    default.)

The `--box_line_width` option sets the linewidth of the schematic symbol
box in units of mils. The default setting is zero.

The `--push` option affects the positions of the pins on each side of
the schematic symbol box. A value of 0.0 pushes them to the upper-most
or left-most position on the left/right or top/bottom sides. A value of
1.0 pushes them to the bottom-most or right-most position on the
left-right or top-bottom sides. A value of 0.5 (the default) centers
them.

The `--scrunch` option will compress a three- or four-sided schematic
symbol by moving the left and right columns of pins closer together so
that their pin labels are shadowed by the pins on the top and bottom
rows.

By default, the first pin of a schematic symbol is placed at the origin.
The `-c` option causes the centroid of the symbol to be placed at the
origin.

#### Examples

KiPart can handle single or multiple input files. The simplest case is
generating a symbol library from a single CSV file. The following
command will process the `file.csv` file and place the symbols in
`file.lib`:

    kipart file.csv

This also works with multiple input files with a separate library
created for each CSV file:

    kipart file1.csv file2.csv  # Creates file1.lib and file2.lib.

Symbols from multiple CSV files can be placed into a single library
using the `-o` option:

    kipart file1.csv file2.csv -o total.lib

If `total.lib` already exists, the previous command will report that the
file cannot be overwritten. Use the `-w` option to force the overwrite:

    kipart file1.csv file2.csv -w -o total.lib

Symbol libraries can also be built incrementally by appending symbols
generated from CSV files:

    kipart file3.csv file4.csv -a -o total.lib

Assume the following data for a single-unit part is placed into the
[example.csv]{.title-ref} file:

    example_part

    Pin,    Type,           Name
    23,     input,          A5
    90,     output,         B1
    88,     bidirectional,  C3
    56,     tristate,       D22
    84,     tristate,       D3
    16,     power_in,       VCC
    5,      power_in,       GND
    29,     power_in,       VCC
    98,     power_in,       GND
    99,     power_in,       VCC
    59,     power_in,       GND

Then the command `kipart example.csv -o example1.lib` will create a
schematic symbol where the pins are arranged in the order of the rows in
the CSV file they are on:

![image](images/example1.png)

The command `kipart -s num example.csv -o example2.lib` will create a
schematic symbol where the pins are arranged by their pin numbers:

![image](images/example2.png)

The command `kipart -s name example.csv -o example3.lib` will create a
schematic symbol where the pins are arranged by their names:

![image](images/example3.png)

The command `kipart -b example.csv -o example4.lib` will bundle power
pins with identical names (like `GND` and `VCC`) into single pins like
so:

![image](images/example4.png)

Or you could divide the part into two units: one for I/O pins and the
other for power pins by adding a `Unit` column like this:

    example_part

    Pin,    Unit,   Type,           Name
    23,     IO,     input,          A5
    90,     IO,     output,         B1
    88,     IO,     bidirectional,  C3
    56,     IO,     tristate,       D22
    84,     IO,     tristate,       D3
    16,     PWR,    power_in,       VCC
    5,      PWR,    power_in,       GND
    29,     PWR,    power_in,       VCC
    98,     PWR,    power_in,       GND
    99,     PWR,    power_in,       VCC
    59,     PWR,    power_in,       GND

Then the command `kipart -b example.csv -o example5.lib` results in a
part symbol having two separate units:

![image](images/example5_1.png)

![image](images/example5_2.png)

As an alternative, you could go back to a single unit with all the
inputs on the left side, all the outputs on the right side, the `VCC`
pins on the top and the `GND` pins on the bottom:

    example_part

    Pin,    Unit,   Type,           Name,   Side
    23,     1,      input,          A5,     left
    90,     1,      output,         B1,     right
    88,     1,      bidirectional,  C3,     left
    56,     1,      tristate,       D22,    right
    84,     1,      tristate,       D3,     right
    16,     1,      power_in,       VCC,    top
    5,      1,      power_in,       GND,    bottom
    29,     1,      power_in,       VCC,    top
    98,     1,      power_in,       GND,    bottom
    99,     1,      power_in,       VCC,    top
    59,     1,      power_in,       GND,    bottom

Running the command `kipart -b example.csv -o example6.lib` generates a
part symbol with pins on all four sides:

![image](images/example6.png)

If the input file has a `Hidden` column, then some, none, or all pins
can be made invisible:

    a_part_with_secrets

    Pin,    Name,   Type,   Side,   Style,      Hidden
    1,      N.C.,   in,     left,   clk_low,    Y
    2,      GND,    pwr,    left,   ,           yes
    3,      SS_INH, in,     left,   ,           True
    4,      OSC,    in,     left,   ,
    5,      A1,     out,    right,  ,           False

In the Part Library Editor, hidden pins are grayed out:

![image](images/hidden_editor.png)

But in Eeschema, they won\'t be visible at all:

![image](images/hidden_eeschema.png)

### kilib2csv

Sometimes you have existing libraries that you want to manage with a
spreadsheet instead of the KiCad symbol editor. The kilib2csv utility
takes one or more library files and converts them into a CSV file. Then
the CSV file can be manipulated with a spreadsheet and used as input to
KiPart. **(Note that any stylized part symbol graphics will be lost in
the conversion. KiPart only supports boring, box-like part symbols.)**

    usage: kilib2csv [-h] [-v] [-o [file.csv]] [-a] [-w] file.lib [file.lib ...]

    Convert a KiCad schematic symbol library file into a CSV file for KiPart.

    positional arguments:
      file.lib              KiCad schematic symbol library.

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -o [file.csv], --output [file.csv]
                            CSV file created from schematic library file.
      -a, --append          Append to an existing CSV file.
      -w, --overwrite       Allow overwriting of an existing CSV file.

This utility handles single and multiple input files in the same manner
as KiPart and supports some of the same options for overwriting and
appending to the output CSV file:

    kilib2csv my_lib1.lib my_lib2.lib -o my_library.csv

Then you can generate a consistent library from the CSV file:

    kipart my_library.csv -o my_library_new.lib

