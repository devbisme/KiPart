# MIT license
# 
# Copyright (C) 2015 by XESS Corporation
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import argparse as ap
import os
import sys
import zipfile
from __init__ import __version__
from kipart import *

parser = ap.ArgumentParser(
    description='Generate KiCad multi-unit schematic symbols from a CSV file.')
parser.add_argument('-v', '--version',
                    action='version',
                    version='KiPart ' + __version__)
parser.add_argument('input_files',
                    nargs='+',
                    type=str,
                    metavar='file1.[csv|zip] file2.[csv|zip] ...',
                    help='Files for parts in CSV format.')
parser.add_argument('-r', '--reader',
                    nargs='?',
                    type=str,
                    metavar='CSV_READER',
                    default='generic',
                    help='Name of function for reading the CSV file.')
parser.add_argument('-s', '--sort',
                    nargs='?',
                    choices=['row', 'num', 'name'],
                    default='name',
                    metavar='row|num|name',
                    help='Sort the part pins by their entry order in the CSV file, their pin number, or their pin name.')
parser.add_argument('-o', '--output',
                    nargs='?',
                    type=str,
                    metavar='file.lib',
                    help='Generated KiCad library for part.')
parser.add_argument('-b', '--bundle',
                    action='store_true',
                    help='Bundle multiple pins with the same name into a single schematic pin.')
parser.add_argument('-w', '--overwrite',
                    action='store_true',
                    help='Allow overwriting of an existing part library.')
parser.add_argument(
    '-d', '--debug',
    nargs='?',
    type=int,
    default=0,
    metavar='LEVEL',
    help='Print debugging info. (Larger LEVEL means more info.)')

args = parser.parse_args()

if args.output == None:
    args.output = os.path.splitext(sys.argv[0])[0] + '.lib'
else:
    args.output = os.path.splitext(args.output)[0] + '.lib'

if os.path.isfile(args.output):
    if not args.overwrite:
        print 'Output file {} already exists! Use the --overwrite option to replace it.'.format(
            args.output)
        sys.exit(1)

append_to_lib = False
for input_file in args.input_files:
    file_ext = os.path.splitext(input_file)[1]
    if file_ext == '.zip':
        zip_file = zipfile.ZipFile(input_file, 'r')
        zipped_files = zip_file.infolist()
        for zipped_file in zipped_files:
            if os.path.splitext(zipped_file.filename)[1] == '.csv':
                with zip_file.open(zipped_file, 'r') as csv_file:
                    kipart(reader_type=args.reader,
                           csv_file=csv_file,
                           lib_filename=args.output,
                           append_to_lib=append_to_lib,
                           sort_type=args.sort,
                           bundle=args.bundle,
                           debug_level=args.debug)
                    append_to_lib = True
    elif file_ext == '.csv':
        with open(input_file, 'r') as csv_file:
            kipart(reader_type=args.reader,
                   csv_file=csv_file,
                   lib_filename=args.output,
                   append_to_lib=append_to_lib,
                   sort_type=args.sort,
                   bundle=args.bundle,
                   debug_level=args.debug)
            append_to_lib = True
    else:
        continue
