#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import setuptools

__version__ = "1.4.1"
__author__ = "Dave Vandenbout"
__email__ = "devb@xess.com"

if "sdist" in sys.argv[1:]:
    with open("kipart/pckg_info.py", "w") as f:
        for name in ["__version__", "__author__", "__email__"]:
            f.write('{} = "{}"\n'.format(name, locals()[name]))

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read().replace(".. :changelog:", "")

requirements = [
    "affine >= 1.2.0",
    "future >= 0.15.0",
    "pyparsing",
    "openpyxl",
    "sexpdata",
]

test_requirements = []  # TODO: put package test requirements here

setup(
    name="kipart",
    version=__version__,
    description="Part creator for KiCad.",
    long_description=readme + "\n\n" + history,
    author=__author__,
    author_email=__email__,
    url="https://github.com/devbisme/kipart",
    project_urls={
        "Documentation": "https://devbisme.github.io/KiPart",
        "Source": "https://github.com/devbisme/kipart",
        "Changelog": "https://github.com/devbisme/kipart/blob/master/HISTORY.rst",
        "Tracker": "https://github.com/devbisme/kipart/issues",
    },
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "kipart = kipart.kipart:main",
            "kilib2csv = kipart.kilib2csv:main",
        ]
    },
    package_dir={"kipart": "kipart"},
    include_package_data=True,
    package_data={"kipart": ["*.gif", "*.png"]},
    scripts=[],
    install_requires=requirements,
    license="MIT",
    zip_safe=False,
    keywords="kipart kicad electronic circuit schematics",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
    test_suite="tests",
    tests_require=test_requirements,
)
