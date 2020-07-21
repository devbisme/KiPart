# MIT license
#
# Copyright (C) 2016 Hasan Yavuz Ozderya
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

import copy
import csv
import os
import re
from collections import defaultdict
from operator import itemgetter

from .common import *
from .kipart import *

# Pin type mappings of STM32Cube output to kipart accepted values.
type_mappings = {
    "Power": "power_in",
    "Input": "input",
    "Output": "output",
    "I/O": "inout",
    "Reset": "input",
    "Boot": "input",
}


def parse_csv_file(csv_file):
    """Parses the CSV file and returns a list of pins in the form of (number, 'name', 'type')"""

    pins = []
    reader = csv.reader(csv_file, delimiter=",", quotechar='"')
    next(reader, None)  # skip header
    for row in reader:
        number, name, ptype, signal, label = row

        if label:
            name += "/" + label
        elif signal:
            name += "/" + signal

        name = name.replace(" ", "_")
        pin_type = type_mappings.get(ptype, "inout")

        pins.append((number, name, pin_type))

    return pins


def parse_portpin(name):
    """Finds the port name and number of a pin in a string. If found
    returns a tuple in the form of ('port_name', port_number).
    Otherwise returns `None`.
    """
    m = re.search("P([A-Z])(\d+)", name)
    if m:
        port_name, port_number = m.groups()
        return (port_name, int(port_number))


def group_pins(pins):
    """Groups pins together per their port name and functions. Returns a
    dictionary of {'port': [pin]}."""
    ports = defaultdict(list)

    power_names = ["VDD", "VSS", "VCAP", "VBAT", "VREF", "V12PHYHS"]
    config_names = ["RCC_OSC", "NRST", "PDR", "SWCLK", "SWDIO", "BOOT"]

    for pin in pins:
        number, name, ptype = pin
        if any(pn in name for pn in power_names):
            ports["power"].append(pin)

        elif any(pn in name for pn in config_names):
            ports["config"].append(pin)

        else:
            m = parse_portpin(name)
            if m:
                port_name, port_number = m
                ports[port_name].append(pin)
            else:
                ports["other"].append(pin)

    # sort pins
    for port in ports:
        # config and power gates are sorted according to their function name
        if port in ["config", "power", "other"]:
            ports[port] = sorted(ports[port], key=itemgetter(1))
        # IO ports are sorted according to port number
        else:
            ports[port] = sorted(ports[port], key=lambda p: parse_portpin(p[1])[1])

    return ports


def stm32cube_reader(part_data_file, part_data_file_name, part_data_file_type=".csv"):
    """Reader for STM32CubeMx pin list output.

    STM32CubeMx is a tool for creating firmware projects for STM32
    MCUs. It also includes a pin layout designer which can export the
    list of pins in the form of a CSV file. This will read the csv
    file and return a dictionary of pin data.

    An example output of the STM32CubeMx tool can be seen below:

    "Position","Name","Type","Signal","Label"
    "1","VBAT","Power","",""
    "2","PC13-ANTI_TAMP","I/O","",""
    "3","PC14-OSC32_IN","I/O","RCC_OSC32_IN",""
    "4","PC15-OSC32_OUT","I/O","RCC_OSC32_OUT",""
    ...

    Pin names for the symbols will be constructed as "Name/Signal". If
    user defined label is specified it will be used instead of
    "Signal" column.

    All IO pins will be grouped to units per their ports.
    Configuration related pins such as boot, clock etc will be grouped
    as a separate unit. Power pins will be a separate unit as well.
    """

    # If part data file is Excel, convert it to CSV.
    if part_data_file_type == ".xlsx":
        part_data_file = convert_xlsx_to_csv(part_data_file)
    csv_file = part_data_file

    pins = parse_csv_file(csv_file)

    ports = group_pins(pins)

    # create pin data
    pin_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    index = 0

    for port_name in ports:
        for p in ports[port_name]:
            # Get the pin attributes from the cells of the row of data.
            pin = copy.copy(DEFAULT_PIN)  # Start off with default values for the pin.
            pin.index = index = index + 1
            pin.num = p[0]
            pin.name = p[1]
            pin.type = p[2]
            pin.unit = port_name

            pin_data[pin.unit][pin.side][pin.name].append(pin)

    # use file name as the part name
    part_name = os.path.splitext(os.path.split(csv_file.name)[1])[0]

    # what should be the part_num?
    yield part_name, "U", "", "", "", "", pin_data
