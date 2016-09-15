#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools
import kipart

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read().replace('.. :changelog:', '')

requirements = ['affine >= 1.2.0', 'future >= 0.15.0', 'pyparsing']

test_requirements = [  # TODO: put package test requirements here
]

setup(name='kipart',
      version=kipart.__version__,
      description="Part creator for KiCad.",
      long_description=readme + '\n\n' + history,
      author=kipart.__author__,
      author_email=kipart.__email__,
      url='https://github.com/xesscorp/kipart',
      packages=setuptools.find_packages(),
      entry_points={'console_scripts': 
            ['kipart = kipart.__main__:main', 
             'kilib2csv = kipart.kilib2csv:main']},
      package_dir={'kipart': 'kipart'},
      include_package_data=True,
      package_data={'kipart': ['*.gif', '*.png']},
      scripts=[],
      install_requires=requirements,
      license="MIT",
      zip_safe=False,
      keywords='kipart',
      classifiers=['Development Status :: 2 - Pre-Alpha',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: MIT License',
                   'Natural Language :: English',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3.4', ],
      test_suite='tests',
      tests_require=test_requirements)
