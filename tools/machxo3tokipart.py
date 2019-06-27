#! /usr/bin/python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Author:   Fabien Marteau <fabien.marteau@armadeus.com>
# Created:  24/06/2019
# -----------------------------------------------------------------------------
#  Copyright (2019)  Armadeus Systems
# -----------------------------------------------------------------------------
""" machxo3tokipart
"""

import getopt
import sys


def usages():
    print("Usage:")
    print("python3 machxo3tokipart.py [options]")
    print("-h, help                 This usage message")
    print("-c, csv=FILENAME         give the filename of lattice csv")
    print("-o, outputname=FILENAME  Output filename to write")
    print("-p, package=CABGA256     Package to use")
    print("-l, list                 list packages available")
    print("-n, partname=name        part name (filename in not present)")


class MachXO3toKipartError(Exception):
    pass


class MachXO3toKipart(object):
    """
    """

    def __init__(self, package=None, csvname=None, listpackage=False, partname=None):
        self._partname = partname
        self._package = package
        self._csvname = csvname
        self._listpackage = listpackage
        self._packages_available = []
        self._header = None

    def parse(self):

        with open(self._csvname, "r") as fcsv:
            for line in fcsv:
                if line[0] == "#" or line[0] == ",":
                    print(line)
                else:
                    self._header = line.split(",")
                    self._packages_available = self._header[8:]
                    self._packages_dict = {}
                    i = 8
                    for package in self._packages_available:
                        self._packages_dict[package.strip()] = i
                        i += 1
                    break
            # Parse header with package list
            if listpackage:
                return
            if self._package not in self._packages_available:
                raise MachXO3toKipartError(
                    "No package named {} in {}".format(
                        self._package, self._packages_available
                    )
                )
            # Parse pinout
            self._pinoutdict = {}
            power_index = 10000
            pindex = self._packages_dict[self._package]
            for line in fcsv:
                sline = line.split(",")
                index = int(sline[0])
                if sline[pindex] != "-":
                    if index != 0:
                        self._pinoutdict[index] = sline
                    else:
                        self._pinoutdict[power_index] = sline
                        power_index += 1
            self.count_bank()

    def count_bank(self):
        bank = {}
        for rawpin in self._pinoutdict.keys():
            pin = self._pinoutdict[rawpin]
            bank[pin[2]] = bank.get(pin[2], 0) + 1
        self._bankcount = bank

    def listpackage_output(self):
        print("Packages available are :")
        for package in self._packages_available:
            print(package)

    def output(self, filename=None):
        if filename is None:
            raise MachXO3toKipartError("can't write output on stdout")
        with open(filename, "w") as foutput:
            if self._partname is None:
                foutput.write(self._csvname.split(".")[0] + "\n")
            else:
                foutput.write("{}\n".format(self._partname))
            foutput.write("\n")
            foutput.write("Pin, Unit, Name, Side\n")
            bank = {}
            for rawpin in self._pinoutdict.keys():
                pin = self._pinoutdict[rawpin]
                bank[pin[2]] = bank.get(pin[2], 0) + 1
                pindex = self._packages_dict[self._package]
                if pin[pindex] != "-":
                    if bank[pin[2]] <= self._bankcount[pin[2]] / 2:
                        side = "left"
                    else:
                        side = "right"
                    foutput.write(
                        "{}, BANK{}, {}{}{}, {}\n".format(
                            pin[pindex],
                            pin[2],
                            pin[1] if pin[1] != "-" else "",
                            "_" + pin[2] if pin[2] != "-" else "",
                            "_" + pin[3] if pin[3] != "-" else "",
                            side,
                        )
                    )


if __name__ == "__main__":
    print("Convert a lattice csv pinout for Kipart\n")
    if sys.version_info[0] < 3:
        raise Exception("Must be using Python 3")
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "hp:lc:o:p:n:",
            ["help", "package=", "partname=" "list", "csv=", "outputname="],
        )
    except getopt.GetoptError as err:
        print(err)
        usages()
        sys.exit(2)

    package = None
    csvname = None
    listpackage = False
    outputname = None
    partname = None
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usages()
            sys.exit()
        elif opt in ("-p", "--package"):
            package = arg
        elif opt in ("-c", "--csv"):
            csvname = arg
        elif opt in ("-l", "--list"):
            listpackage = True
        elif opt in ("-o", "--outputname"):
            outputname = arg
        elif opt in ("-n", "--partname"):
            partname = arg

    l2k = MachXO3toKipart(package, csvname, listpackage, partname)

    l2k.parse()
    if listpackage:
        l2k.listpackage_output()
    else:
        l2k.output(outputname)
