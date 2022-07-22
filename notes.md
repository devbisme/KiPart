1. Make changes to source code.
2. Run `tox` to test changes.
3. Update `version` in `setup.py`.
4. Update `HISTORY.rst` with changes.\
5. Update `docs/usage.rst` for any user-visible changes.\
6. Run `tox -e docs` to update documentation.\
7. Run `tox -e publish_public` to send to PyPi and Github.\
