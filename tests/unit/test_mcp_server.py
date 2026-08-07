"""Tests for the MCP server that exposes kipart's commands.

The server is an optional extra, so everything here is skipped when FastMCP
isn't installed.

Most of these call the tool functions directly — FastMCP's decorator hands the
function back unchanged, so `kipart_tool(...)` is the same call the server makes
once it has validated the arguments. The last two drive a client instead, which
is the only way to catch what goes wrong between a client and a tool rather
than inside one.

The symbol libraries these need are built from tests/examples/grabbag.spd rather
than read from tests/examples/*.kicad_sym, which are gitignored build products.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp", reason="the MCP server needs FastMCP")

from kipart.mcp_server import (  # noqa: E402
    cmpparts_tool,
    jpd2spd_tool,
    kilib2csv_tool,
    kilib2jpd_tool,
    kilib2spd_tool,
    kipart_tool,
    server,
    spd2csv_tool,
    spd2jpd_tool,
)

EXAMPLES = Path(__file__).parent.parent / "examples"
GRABBAG = EXAMPLES / "grabbag.spd"
CMP_A = EXAMPLES / "cmp_a.spd"
CMP_B = EXAMPLES / "cmp_b.spd"

ONE_PART_CSV = "MYPART\nPin,Name,Type,Side\n1,A,input,left\n2,B,output,right\n"


@pytest.fixture
def grabbag_spd():
    return GRABBAG.read_text()


@pytest.fixture
def grabbag_lib(grabbag_spd):
    """The grabbag library, built the way the server would build it."""
    csv = spd2csv_tool(spd_text=grabbag_spd)["content"]
    return kipart_tool(csv_text=csv)["content"]


class TestConversions:
    """Each tool turns the format it's named for into the one it promises."""

    def test_spd_to_csv_to_symbol_lib(self, grabbag_spd):
        csv = spd2csv_tool(spd_text=grabbag_spd)["content"]
        assert "74hc00" in csv

        lib = kipart_tool(csv_text=csv)["content"]
        assert lib.startswith("(kicad_symbol_lib")
        assert '"74hc00"' in lib

    def test_symbol_lib_to_every_format(self, grabbag_lib):
        assert "device 74hc00" in kilib2spd_tool(kicad_sym_text=grabbag_lib)["content"]
        assert "74hc00" in kilib2csv_tool(kicad_sym_text=grabbag_lib)["content"]

        jpd = json.loads(kilib2jpd_tool(kicad_sym_text=grabbag_lib)["content"])
        assert [part["name"] for part in jpd["parts"]].count("74hc00") == 1

    def test_spd_to_jpd_to_spd_gives_the_same_csv(self, grabbag_spd):
        """The round trip CLAUDE.md asks for, driven through the tools."""
        jpd = spd2jpd_tool(spd_text=grabbag_spd)["content"]
        back = jpd2spd_tool(jpd=jpd)["content"]

        assert spd2csv_tool(spd_text=back)["content"] == (
            spd2csv_tool(spd_text=grabbag_spd)["content"]
        )

    def test_jpd_taken_as_text_or_as_an_object(self, grabbag_spd):
        """A client may hand a JSON-shaped argument over already parsed."""
        jpd = spd2jpd_tool(spd_text=grabbag_spd)["content"]

        assert jpd2spd_tool(jpd=jpd)["content"] == (
            jpd2spd_tool(jpd=json.loads(jpd))["content"]
        )


class TestInputAndOutput:
    """A tool reads text or a path, and writes only where it's told to."""

    def test_reads_from_a_path(self, grabbag_spd):
        assert spd2csv_tool(input_path=str(GRABBAG))["content"] == (
            spd2csv_tool(spd_text=grabbag_spd)["content"]
        )

    def test_returns_the_text_without_writing_anything(self, tmp_path):
        result = kipart_tool(csv_text=ONE_PART_CSV)

        assert result["output_path"] is None
        assert not list(tmp_path.iterdir())

    def test_writes_where_it_is_told(self, tmp_path):
        lib = tmp_path / "out.kicad_sym"
        result = kipart_tool(csv_text=ONE_PART_CSV, output_path=str(lib))

        assert result["output_path"] == str(lib)
        assert lib.read_text() == result["content"]

    def test_will_not_clobber_unless_allowed(self, tmp_path):
        lib = tmp_path / "out.kicad_sym"
        kipart_tool(csv_text=ONE_PART_CSV, output_path=str(lib))

        with pytest.raises(ValueError, match="already exists"):
            kipart_tool(csv_text=ONE_PART_CSV, output_path=str(lib))

        kipart_tool(csv_text=ONE_PART_CSV, output_path=str(lib), overwrite=True)

    def test_merging_adds_to_the_library_already_there(self, tmp_path, grabbag_spd):
        lib = tmp_path / "out.kicad_sym"
        csv = spd2csv_tool(spd_text=grabbag_spd)["content"]
        kipart_tool(csv_text=csv, output_path=str(lib))

        before = json.loads(kilib2jpd_tool(input_path=str(lib))["content"])
        kipart_tool(csv_text=ONE_PART_CSV, output_path=str(lib), merge=True)
        after = json.loads(kilib2jpd_tool(input_path=str(lib))["content"])

        names = {part["name"] for part in after["parts"]}
        assert names == {part["name"] for part in before["parts"]} | {"MYPART"}

    def test_needs_exactly_one_source(self):
        with pytest.raises(ValueError, match="exactly one"):
            spd2csv_tool()

        with pytest.raises(ValueError, match="exactly one"):
            spd2csv_tool(spd_text="device X\n", input_path=str(GRABBAG))

    def test_checks_the_extension_of_an_input_path(self):
        with pytest.raises(ValueError, match=r"must be a \.kicad_sym"):
            kilib2spd_tool(input_path=str(GRABBAG))

    def test_reports_a_missing_input_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            spd2csv_tool(input_path=str(tmp_path / "nothing.spd"))


class TestCmpparts:
    """Comparing libraries given as paths, as text, and in a mix of formats."""

    def test_a_library_matches_the_one_built_from_it(self, grabbag_spd, grabbag_lib):
        result = cmpparts_tool(
            libraries=[
                {"text": grabbag_spd, "format": "spd", "name": "grabbag"},
                {"text": grabbag_lib, "format": "kicad_sym", "name": "built"},
            ],
            ignore=["geometry", "names", "properties"],
        )

        assert result["differ"] is False

    def test_the_example_pair_differs(self):
        assert cmpparts_tool(libraries=[str(CMP_A), str(CMP_B)])["differ"] is True

    def test_reports_in_json(self):
        result = cmpparts_tool(libraries=[str(CMP_A), str(CMP_B)], format="json")
        report = json.loads(result["content"])

        assert report["comparisons"][0]["matched"]

    def test_needs_two_libraries(self):
        with pytest.raises(ValueError, match="at least two"):
            cmpparts_tool(libraries=[str(CMP_A)])

    def test_rejects_what_it_cannot_do(self):
        with pytest.raises(ValueError, match="Can't ignore"):
            cmpparts_tool(libraries=[str(CMP_A), str(CMP_B)], ignore=["nonsense"])

        with pytest.raises(ValueError, match="rich"):
            cmpparts_tool(libraries=[str(CMP_A), str(CMP_B)], format="rich")

        with pytest.raises(ValueError, match="format"):
            cmpparts_tool(libraries=[{"text": "device X\n"}, str(CMP_B)])


COMMANDS = {
    "kipart",
    "kilib2csv",
    "kilib2spd",
    "kilib2jpd",
    "spd2csv",
    "spd2jpd",
    "jpd2spd",
    "cmpparts",
}


class TestThroughAClient:
    """The server as a client actually meets it, in the same process."""

    @staticmethod
    def talk(work):
        """Run `work` against an in-memory client of the server."""
        from fastmcp import Client

        async def session():
            async with Client(server) as client:
                return await work(client)

        return asyncio.run(session())

    def test_it_offers_a_tool_per_command(self):
        tools = self.talk(lambda client: client.list_tools())

        assert {tool.name for tool in tools} == COMMANDS

    def test_it_offers_the_formats_as_resources(self):
        resources = self.talk(lambda client: client.list_resources())

        assert {str(one.uri) for one in resources} == {
            "kipart://docs/spd",
            "kipart://docs/jpd",
            "kipart://docs/readme",
            "kipart://examples/grabbag.spd",
        }

    def test_a_tool_call_comes_back_converted(self):
        result = self.talk(
            lambda client: client.call_tool(
                "spd2csv", {"spd_text": GRABBAG.read_text()}
            )
        )

        assert "74hc00" in result.data["content"]

    def test_a_resource_comes_back_read(self):
        contents = self.talk(lambda client: client.read_resource("kipart://docs/spd"))

        assert contents[0].text.startswith("# SPD")

    def test_a_failing_tool_comes_back_as_an_error(self):
        result = self.talk(
            lambda client: client.call_tool("spd2csv", {}, raise_on_error=False)
        )

        assert result.is_error
        assert "exactly one" in result.content[0].text

    def test_json_text_stays_text(self):
        """A JSON-shaped string argument must not arrive parsed into a dict."""
        jpd = spd2jpd_tool(spd_text=GRABBAG.read_text())["content"]
        result = self.talk(lambda client: client.call_tool("jpd2spd", {"jpd": jpd}))

        assert "device 74hc00" in result.data["content"]


class TestOverStdio:
    """The server as its own command, over the pipe a client would use."""

    def test_a_client_can_drive_the_installed_command(self):
        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        async def talk():
            transport = StdioTransport(
                command=sys.executable, args=["-m", "kipart.mcp_server"]
            )
            async with Client(transport) as client:
                tools = await client.list_tools()
                result = await client.call_tool(
                    "spd2csv", {"spd_text": GRABBAG.read_text()}
                )
                return {tool.name for tool in tools}, result

        names, result = asyncio.run(talk())

        # Getting this far at all says the protocol wasn't corrupted by
        # anything kipart printed on its way through stdout.
        assert names == COMMANDS
        assert "74hc00" in result.data["content"]
