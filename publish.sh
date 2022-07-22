#!/usr/bin/env bash
set -euo pipefail

rm -f dist/*.gz
python setup.py sdist
python -m twine check dist/*
python -m twine upload --repository pypi dist/*
git tag -f `kipart -v | cut -d' ' -f2`
git push
