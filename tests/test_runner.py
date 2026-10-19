"""Unit tests for SQLite safe executor (open_ro, timeout, and row limits)."""
import pathlib, sqlite3, pytest
from app.executor.runner import open_ro, execute_query

CHINOOK_PATH = pathlib.Path("data/chinook.sqlite")


def test_readonly_blocks_inserts():
    """Verify physical read-only connection fails even when bypassing the checker."""
    con = open_ro(CHINOOK_PATH)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            con.execute("INSERT INTO Artist (Name) VALUES ('Malicious Artist')")
    finally:
        con.close()


def test_progress_handler_timeout():
    """Verify runaway long query is aborted by the progress handler timeout."""
    # Use a 0.05 second timeout with a heavy recursive query to trigger the handler
    con = open_ro(CHINOOK_PATH, timeout_s=0.05)
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("""
                WITH RECURSIVE cnt(x) AS (
                    SELECT 1
                    UNION ALL
                    SELECT x+1 FROM cnt WHERE x < 100000000
                )
                SELECT sum(x) FROM cnt;
            """)
    finally:
        con.close()


def test_execute_query_truncation_on_large_table():
    """Verify execute_query caps at 200 rows and flags truncated=True."""
    con = open_ro(CHINOOK_PATH)
    try:
        cols, rows, truncated = execute_query(con, "SELECT * FROM InvoiceLine")
        assert len(rows) == 200
        assert truncated is True
        assert len(cols) > 0
    finally:
        con.close()


def test_execute_query_small_result_not_truncated():
    """Verify small query results are not truncated."""
    con = open_ro(CHINOOK_PATH)
    try:
        cols, rows, truncated = execute_query(con, "SELECT * FROM Album LIMIT 5")
        assert len(rows) == 5
        assert truncated is False
        assert "Title" in cols
    finally:
        con.close()
