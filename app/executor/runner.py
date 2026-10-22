"""Safe SQLite executor: read-only connection, timeout handler, and row caps."""
import pathlib, sqlite3, time


def open_ro(path: str | pathlib.Path, timeout_s: float = 5.0) -> sqlite3.Connection:
    """Open an SQLite database in strictly read-only mode with a CPU timeout."""
    p = pathlib.Path(path).resolve().as_posix()
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    deadline = time.time() + timeout_s
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 1000)
    return con


def execute_query(
    con: sqlite3.Connection, sql: str, max_rows: int = 200, timeout_s: float = 5.0
) -> tuple[list[str], list[tuple], bool]:
    """Execute SQL query, capping output at max_rows with truncated flag."""
    deadline = time.time() + timeout_s
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 1000)
    cur = con.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    fetched = cur.fetchmany(max_rows + 1)
    truncated = len(fetched) > max_rows
    return cols, fetched[:max_rows], truncated
