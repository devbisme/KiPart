"""
An MCP server exposing kipart's command-line tools, built on FastMCP.

Every command kipart installs has a tool here, named after the command, so
`kipart`, `spd2csv`, `cmpparts` and the rest mean on this server what they mean
in a shell. The difference is what they read and write: a tool takes the part
description as *text* or as a *file path*, and hands the result back as text
unless it was told where to write it. That lets an agent work a symbol through
SPD -> CSV -> .kicad_sym without leaving anything on disk, while still being
able to convert a library the user already has.

The formats themselves are served as resources — SPD.md, JPD.md, the README,
and the grabbag example — so a model can look up how to write a part
description before writing one.

Run it with the `kipart-mcp` command, or `python -m kipart.mcp_server`. It
speaks MCP over stdio.

The tools call kipart's Python API directly rather than shelling out, which
means anything the library prints would land on stdout — the same pipe MCP
speaks JSON-RPC over. Every tool body therefore runs under `_captured()`, which
holds stdout and stderr aside and returns what was printed as the result's
'messages'.
"""

import contextlib
import csv
import io
import json
import os
import tempfile
from pathlib import Path

try:
    from fastmcp import FastMCP
except ImportError:
    raise SystemExit(
        "The MCP server needs FastMCP, which kipart doesn't install by "
        "default. Install it with:\n\n    pip install 'kipart[mcp]'\n"
    )

from simp_sexp import Sexp

from .kipart import (
    add_quotes,
    create_empty_symbol_lib,
    merge_symbol_libs,
    read_row_file,
    rows_to_symbol_lib,
    symbol_lib_to_csv,
)
from .kilib2spd import symbol_lib_to_spd
from .jpd import jpd_to_spd, spd_to_jpd, symbol_lib_to_jpd
from .spd2csv import spd_to_csv
from .compare_parts import (
    FORMATS,
    IGNORABLE,
    MATCH_MODES,
    compare_libraries,
    format_html,
    format_report,
    report_differ,
)
from .version import __version__


server = FastMCP(
    name="kipart",
    version=__version__,
    instructions=(
        "Turns part descriptions into KiCad symbol libraries and back. A part "
        "can be written as SPD (a terse indented text format), JPD (the same "
        "thing as JSON), or CSV, and any of them becomes a .kicad_sym library. "
        "Read the kipart://docs/spd and kipart://docs/jpd resources before "
        "writing a part description by hand. Every tool takes its input as "
        "text or as a file path, and returns the result as text unless given "
        "an output path."
    ),
)


def tool(name, description):
    """
    Register one of kipart's commands as a tool.

    The tools run on the event loop's own thread rather than on a worker
    thread, which is what makes `_captured()` safe: redirecting stdout is a
    change to the whole process, so a tool that did it from a worker thread
    could swallow a JSON-RPC response the loop was writing at that moment.
    Holding the loop for the length of a conversion serializes the tool calls,
    which costs nothing worth having on a local server doing sub-second work.
    """
    return server.tool(name=name, description=description, run_in_thread=False)


# ===== Reading input and writing output =====

# Where a format's text is expected to live on disk, used to check a given
# input path and to name the temporary files cmpparts needs.
EXTENSIONS = {
    "spd": ".spd",
    "jpd": ".jpd",
    "kicad_sym": ".kicad_sym",
    "csv": ".csv",
}


@contextlib.contextmanager
def _captured():
    """
    Hold aside anything the library prints while a tool runs.

    kipart reports what it couldn't do by printing rather than raising, and on
    a stdio server a stray print corrupts the protocol. This keeps stdout clear
    and collects both streams so the tool can hand them back.
    """
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        yield captured


def _input_text(text, path, fmt):
    """
    Give the text a tool was asked to work on, from either the text or the path.

    Args:
        text (str or None): The content itself.
        path (str or None): Path to a file holding the content.
        fmt (str): The format's key in EXTENSIONS, for checking the path.

    Returns:
        str: The content.

    Raises:
        ValueError: If neither or both were given, or the path is wrong.
        FileNotFoundError: If the path doesn't exist.
    """
    if (text is None) == (path is None):
        raise ValueError(
            f"Give exactly one of the {fmt} text or an input path, not neither "
            "and not both."
        )

    if text is not None:
        return text

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file {path} does not exist")

    extension = os.path.splitext(path)[1].lower()
    if extension != EXTENSIONS[fmt]:
        raise ValueError(
            f"Input file must be a {EXTENSIONS[fmt]} file, got {extension or path}"
        )

    with open(path, "r") as f:
        return f.read()


def _write_output(path, content, overwrite):
    """Write a converted part out, refusing to clobber unless told it may."""
    if not path:
        return None

    if os.path.exists(path) and not overwrite:
        raise ValueError(
            f"Output file {path} already exists. Pass overwrite=true to allow "
            "overwriting it."
        )

    with open(path, "w", newline="") as f:
        f.write(content)

    return path


def _result(content, output_path, messages):
    """The shape every converting tool answers with."""
    return {
        "content": content,
        "output_path": output_path,
        "messages": messages.getvalue(),
    }


def _convert(content, output_path, overwrite, messages):
    """Write the result if asked to, and package it up."""
    written = _write_output(output_path, content, overwrite)
    return _result(content, written, messages)


# ===== CSV or Excel to a KiCad symbol library =====


@tool(
    name="kipart",
    description=(
        "Build a KiCad symbol library (.kicad_sym) from rows of pin data, the "
        "`kipart` command. The rows come as CSV text, or from a .csv, .xlsx, "
        "or .xls file. Returns the library as text, and writes it to "
        "output_path if one is given."
    ),
)
def kipart_tool(
    csv_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
    merge: bool = False,
    sort: str = "row",
    reverse: bool = False,
    side: str = "left",
    pin_type: str = "passive",
    pin_style: str = "line",
    push: float = 0.5,
    ccw: bool = False,
    scrunch: bool = False,
    bundle: bool = False,
    bundle_style: str = "count",
    alt_delimiter: str | None = None,
    hide_pin_num: bool = False,
    one_symbol: bool = False,
    justify: str = "right",
) -> dict:
    """
    Args:
        csv_text: The CSV rows themselves. Give this or input_path.
        input_path: A .csv, .xlsx, or .xls file to read the rows from. Excel
            can only be read from a file, not passed as text.
        output_path: Where to write the .kicad_sym library. Omit to just get
            the text back.
        overwrite: Allow writing over an existing output file (`-w`).
        merge: Merge the new symbols into the library already at output_path
            rather than replacing it (`-m`).
        sort: Order pins by their CSV row order ('row'), pin number ('num'), or
            pin name ('name') (`-s`).
        reverse: Sort the pins the other way round (`-r`).
        side: Which side a pin goes on when its row doesn't say (`--side`).
        pin_type: The electrical type a pin takes when its row doesn't say —
            input, output, bidirectional, passive, and so on (`--type`).
        pin_style: The graphic style a pin takes when its row doesn't say —
            line, inverted, clock, and so on (`--style`).
        push: Where each side's pins sit along it: 0.0 at the start, 0.5
            centered, 1.0 at the end (`--push`).
        ccw: Run the pins counter-clockwise around the symbol (`--ccw`).
        scrunch: Tuck the left and right pins under the top and bottom ones
            (`--scrunch`).
        bundle: Bundle identically-named power and ground pins into one
            schematic pin (`-b`).
        bundle_style: What a bundled pin's name gets appended to it — 'none',
            'count', or 'range' (`--bundle-style`).
        alt_delimiter: The character that splits a pin name into alternates
            (`-a`).
        hide_pin_num: Hide the pin numbers (`--hide-pin-num`).
        one_symbol: Treat blank rows as nothing rather than as a break between
            symbols (`-1`).
        justify: How visible properties are justified — left, center, or right
            (`-j`).
    """
    with _captured() as messages:
        if not 0.0 <= push <= 1.0:
            raise ValueError("push must be between 0.0 and 1.0 inclusive")

        if csv_text is not None and input_path is not None:
            raise ValueError("Give the CSV text or an input path, not both.")

        if input_path is not None:
            # read_row_file picks the reader from the extension, which is the
            # only way an Excel file can come in.
            rows = read_row_file(input_path)
        elif csv_text is not None:
            rows = list(csv.reader(io.StringIO(csv_text)))
        else:
            raise ValueError("Give either the CSV text or an input path.")

        symbol_lib = rows_to_symbol_lib(
            rows,
            sort_by=sort,
            reverse=reverse,
            default_side=side,
            default_type=pin_type,
            default_style=pin_style,
            alt_pin_delim=alt_delimiter,
            bundle=bundle,
            scrunch=scrunch,
            ccw=ccw,
            push=push,
            hide_pin_num=hide_pin_num,
            one_symbol=one_symbol,
            bundle_style=bundle_style,
            justify=justify,
        )

        if merge:
            if not output_path:
                raise ValueError("Merging needs an output_path to merge into.")
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    existing = Sexp(f.read())
                symbol_lib = merge_symbol_libs(existing, symbol_lib, overwrite=True)
            else:
                symbol_lib = merge_symbol_libs(
                    create_empty_symbol_lib(), symbol_lib, overwrite=True
                )

        add_quotes(symbol_lib)

        # Merging is the one case where writing over the output file is the
        # point, so it doesn't also need to be given permission.
        return _convert(str(symbol_lib), output_path, overwrite or merge, messages)


# ===== A KiCad symbol library to the other formats =====


@tool(
    name="kilib2csv",
    description=(
        "Turn a KiCad symbol library (.kicad_sym) into CSV rows of pin data, "
        "the `kilib2csv` command. Returns the CSV as text, and writes it to "
        "output_path if one is given."
    ),
)
def kilib2csv_tool(
    kicad_sym_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        kicad_sym_text: The symbol library itself. Give this or input_path.
        input_path: A .kicad_sym file to read the library from.
        output_path: Where to write the CSV. Omit to just get the text back.
        overwrite: Allow writing over an existing output file (`-w`).
    """
    with _captured() as messages:
        content = _input_text(kicad_sym_text, input_path, "kicad_sym")
        return _convert(symbol_lib_to_csv(content), output_path, overwrite, messages)


@tool(
    name="kilib2spd",
    description=(
        "Turn a KiCad symbol library (.kicad_sym) into an SPD part "
        "description, the `kilib2spd` command. Returns the SPD as text, and "
        "writes it to output_path if one is given."
    ),
)
def kilib2spd_tool(
    kicad_sym_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
    compress: bool = True,
) -> dict:
    """
    Args:
        kicad_sym_text: The symbol library itself. Give this or input_path.
        input_path: A .kicad_sym file to read the library from.
        output_path: Where to write the SPD. Omit to just get the text back.
        overwrite: Allow writing over an existing output file (`-w`).
        compress: Combine pins that share a type, style, and name onto one
            line. False gives each pin its own line (`--no-compress`).
    """
    with _captured() as messages:
        content = _input_text(kicad_sym_text, input_path, "kicad_sym")
        return _convert(
            symbol_lib_to_spd(Sexp(content), compress=compress),
            output_path,
            overwrite,
            messages,
        )


@tool(
    name="kilib2jpd",
    description=(
        "Turn a KiCad symbol library (.kicad_sym) into a JPD part description, "
        "the `kilib2jpd` command. The geometry the symbols are drawn with is "
        "left behind, since JPD has no way to say it. Returns the JPD as text, "
        "and writes it to output_path if one is given."
    ),
)
def kilib2jpd_tool(
    kicad_sym_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        kicad_sym_text: The symbol library itself. Give this or input_path.
        input_path: A .kicad_sym file to read the library from.
        output_path: Where to write the JPD. Omit to just get the text back.
        overwrite: Allow writing over an existing output file (`-w`).
    """
    with _captured() as messages:
        content = _input_text(kicad_sym_text, input_path, "kicad_sym")
        jpd = json.dumps(symbol_lib_to_jpd(Sexp(content)), indent=2) + "\n"
        return _convert(jpd, output_path, overwrite, messages)


# ===== SPD and JPD =====


@tool(
    name="spd2csv",
    description=(
        "Turn an SPD part description into CSV rows of pin data for kipart, "
        "the `spd2csv` command. Returns the CSV as text, and writes it to "
        "output_path if one is given."
    ),
)
def spd2csv_tool(
    spd_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        spd_text: The SPD part description itself. Give this or input_path.
        input_path: An .spd file to read the description from.
        output_path: Where to write the CSV. Omit to just get the text back.
        overwrite: Allow writing over an existing output file.
    """
    with _captured() as messages:
        content = _input_text(spd_text, input_path, "spd")
        return _convert(spd_to_csv(content), output_path, overwrite, messages)


@tool(
    name="spd2jpd",
    description=(
        "Turn an SPD part description into the equivalent JPD (JSON) one, the "
        "`spd2jpd` command. Returns the JPD as text, and writes it to "
        "output_path if one is given."
    ),
)
def spd2jpd_tool(
    spd_text: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        spd_text: The SPD part description itself. Give this or input_path.
        input_path: An .spd file to read the description from.
        output_path: Where to write the JPD. Omit to just get the text back.
        overwrite: Allow writing over an existing output file (`-w`).
    """
    with _captured() as messages:
        content = _input_text(spd_text, input_path, "spd")
        jpd = json.dumps(spd_to_jpd(content), indent=2) + "\n"
        return _convert(jpd, output_path, overwrite, messages)


@tool(
    name="jpd2spd",
    description=(
        "Turn a JPD (JSON) part description into the equivalent SPD one, the "
        "`jpd2spd` command. The JPD can be given as JSON text or as the JSON "
        "object itself. Returns the SPD as text, and writes it to output_path "
        "if one is given."
    ),
)
def jpd2spd_tool(
    jpd: str | dict | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        jpd: The JPD part description itself, either as JSON text or as the
            JSON object it parses to. Give this or input_path.
        input_path: A .jpd file to read the description from.
        output_path: Where to write the SPD. Omit to just get the text back.
        overwrite: Allow writing over an existing output file (`-w`).
    """
    with _captured() as messages:
        # A JPD is JSON, and a client that sees a JSON-shaped argument may hand
        # it over already parsed rather than as text, so take it either way.
        if isinstance(jpd, dict):
            if input_path is not None:
                raise ValueError("Give the JPD or an input path, not both.")
            description = jpd
        else:
            content = _input_text(jpd, input_path, "jpd")
            try:
                description = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"The JPD isn't valid JSON: {e}")

        return _convert(jpd_to_spd(description), output_path, overwrite, messages)


# ===== Comparing libraries =====


@contextlib.contextmanager
def _library_files(libraries):
    """
    Give a filename for each library to compare, materializing the inline ones.

    compare_libraries reads its libraries from files and picks the format from
    the extension, so a library handed over as text is written to a temporary
    file named for its format and cleaned up afterwards.
    """
    if not isinstance(libraries, list) or len(libraries) < 2:
        raise ValueError("Give at least two libraries to compare.")

    with tempfile.TemporaryDirectory() as workspace:
        filenames = []

        for index, library in enumerate(libraries):
            if isinstance(library, str):
                library = {"path": library}
            if not isinstance(library, dict):
                raise ValueError(
                    "A library is a path, or an object with 'text' and "
                    f"'format', not {library!r}"
                )

            path, text = library.get("path"), library.get("text")

            if (path is None) == (text is None):
                raise ValueError(
                    "Give each library either a 'path' or a 'text', not "
                    "neither and not both."
                )

            if path is not None:
                filenames.append(path)
                continue

            fmt = library.get("format")
            if fmt not in EXTENSIONS or fmt == "csv":
                raise ValueError(
                    "A library given as text needs a 'format' of 'spd', "
                    f"'jpd', or 'kicad_sym', not {fmt!r}"
                )

            # The stem shows up in the report, so use the caller's name for it.
            stem = library.get("name") or f"library_{index + 1}"
            filename = os.path.join(workspace, stem + EXTENSIONS[fmt])
            with open(filename, "w") as f:
                f.write(text)
            filenames.append(filename)

        yield filenames


@tool(
    name="cmpparts",
    description=(
        "Compare the parts of two or more libraries and report the "
        "differences, the `cmpparts` command. The first library is the one the "
        "others are compared against. A library is a .kicad_sym, .spd, or .jpd "
        "file, or the same text inline, in any mix. Use ignore=['geometry'] to "
        "compare only what the parts are, disregarding how they're drawn."
    ),
)
def cmpparts_tool(
    libraries: list,
    ignore: list | None = None,
    match: str = "normalized",
    threshold: float = 0.6,
    aliases: dict | None = None,
    format: str = "text",
    verbose: bool = False,
    output_path: str | None = None,
    overwrite: bool = False,
) -> dict:
    """
    Args:
        libraries: The libraries to compare, at least two, the first being the
            reference. Each is either a path, or an object holding 'text' and
            a 'format' of 'spd', 'jpd', or 'kicad_sym', plus an optional 'name'
            to call it by in the report.
        ignore: Categories of difference to leave out — 'geometry', 'names',
            'properties', and the like (`-i`). Ask for the categories by
            calling with a bad one; they're listed in the error.
        match: How to pair parts up across libraries: 'exact' by name,
            'normalized' ignoring case and punctuation, 'fuzzy' by how alike the
            names are, or 'pins' by the pinout alone (`-m`).
        threshold: How alike two parts must be for 'fuzzy' or 'pins' to pair
            them, from 0 to 1 (`-t`).
        aliases: Part names paired up by hand, as {old_name: new_name} (`-a`).
        format: How to write the report — 'text', 'json', or 'html' (`-f`).
            The terminal-only 'rich' format isn't offered here.
        verbose: Name the parts that came out identical, not just the
            differing ones (`--verbose`).
        output_path: Where to write the report. Omit to just get it back.
        overwrite: Allow writing over an existing output file.
    """
    with _captured() as messages:
        ignore = set(ignore or [])
        unknown = ignore - set(IGNORABLE)
        if unknown:
            raise ValueError(
                f"Can't ignore {', '.join(sorted(unknown))}. The categories "
                f"are: {', '.join(IGNORABLE)}"
            )

        if match not in MATCH_MODES:
            raise ValueError(f"match is one of {', '.join(MATCH_MODES)}, not {match!r}")

        if format not in FORMATS or format == "rich":
            raise ValueError(
                "format is 'text', 'json', or 'html' — 'rich' only means "
                f"something in a terminal. Got {format!r}"
            )

        if not 0 <= threshold <= 1:
            raise ValueError("threshold runs from 0 to 1")

        with _library_files(libraries) as filenames:
            report = compare_libraries(
                filenames,
                ignore=ignore,
                mode=match,
                threshold=threshold,
                aliases=aliases or {},
            )

        if format == "json":
            content = json.dumps(report, indent=2)
        elif format == "html":
            content = format_html(report, verbose=verbose)
        else:
            content = format_report(report, verbose=verbose) + "\n"

        result = _convert(content, output_path, overwrite, messages)
        result["differ"] = report_differ(report)
        return result


# ===== The formats, as resources =====

# The format documents live beside the package in a checkout. A wheel doesn't
# carry them, so a missing one is reported rather than raised.
DOCS = Path(__file__).resolve().parent.parent

DOC_URL = "https://github.com/devbisme/kipart/blob/master/"


def _doc(relative_path):
    """Give the text of one of the documents kipart ships beside the package."""
    path = DOCS / relative_path
    try:
        return path.read_text()
    except OSError:
        return (
            f"{relative_path} isn't installed alongside kipart — it ships in "
            "the repository rather than in the wheel. Read it at "
            f"{DOC_URL}{relative_path}"
        )


@server.resource(
    "kipart://docs/spd",
    name="SPD format",
    description=(
        "How to write an SPD (Shorthand Part Description): its directives, pin "
        "type codes, style modifiers, and pin naming rules. Read this before "
        "writing an SPD part description."
    ),
    mime_type="text/markdown",
)
def spd_doc() -> str:
    return _doc("SPD.md")


@server.resource(
    "kipart://docs/jpd",
    name="JPD format",
    description=(
        "How to write a JPD (JSON Part Description): the structure of a part, "
        "its units, sides, and pins. Read this before writing a JPD part "
        "description."
    ),
    mime_type="text/markdown",
)
def jpd_doc() -> str:
    return _doc("JPD.md")


@server.resource(
    "kipart://docs/readme",
    name="kipart README",
    description=(
        "What kipart does and what each of its commands is for, including the "
        "columns a CSV of pin data holds."
    ),
    mime_type="text/markdown",
)
def readme_doc() -> str:
    return _doc("README.md")


@server.resource(
    "kipart://examples/grabbag.spd",
    name="grabbag.spd example",
    description=(
        "A worked SPD example exercising the whole format — multi-unit parts, "
        "alternates, buses, spacers, and every pin type and modifier."
    ),
    mime_type="text/plain",
)
def grabbag_example() -> str:
    return _doc("tests/examples/grabbag.spd")


# ===== Running it =====


def main():
    """Run the MCP server over stdio."""
    # The banner is decoration on a pipe that carries JSON-RPC, so it stays off.
    server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
