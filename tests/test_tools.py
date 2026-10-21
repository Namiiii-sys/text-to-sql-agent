"""Zero-network tests for schema tools on Chinook SQLite database."""
import pathlib
import pytest
from app.executor.runner import open_ro
from app.agents.tools import list_tables, inspect_schema, sample_values

CHINOOK_PATH = pathlib.Path("data/chinook.sqlite")


@pytest.fixture
def con():
    c = open_ro(CHINOOK_PATH)
    yield c
    c.close()


def test_list_tables(con):
    out = list_tables(con)
    assert "Album" in out
    assert "Artist" in out
    assert "sqlite_" not in out


def test_inspect_schema(con):
    out = inspect_schema("Album", con)
    assert "Table: Album" in out
    assert "AlbumId (INTEGER, PK)" in out
    assert "ArtistId (INTEGER, FK -> Artist.ArtistId)" in out


def test_sample_values_caps_and_truncates(con):
    # Test capping at 5 even if n=10 requested
    out = eval(sample_values("Track", "Name", n=10, con=con))
    assert isinstance(out, list)
    assert len(out) <= 5

    # Test truncation of strings longer than 80 chars
    long_str = "x" * 120
    con.execute("CREATE TEMP TABLE t_long (s TEXT)")
    con.execute("INSERT INTO t_long VALUES (?)", (long_str,))
    out_long = eval(sample_values("t_long", "s", n=1, con=con))
    assert len(out_long[0]) == 80
