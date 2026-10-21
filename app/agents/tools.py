"""Database schema inspection and value sampling tools for the Writer agent."""
import sqlite3


def list_tables(con: sqlite3.Connection) -> str:
    """Return a sorted comma-separated list of user table names."""
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return ", ".join(r[0] for r in rows)


def inspect_schema(table: str, con: sqlite3.Connection) -> str:
    """Return compact column names, types, primary keys, and foreign keys for a table."""
    fks = {r[3]: f"{r[2]}.{r[4]}" for r in con.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()}
    cols = []
    for r in con.execute(f"PRAGMA table_info('{table}')").fetchall():
        cid, name, col_type, notnull, dflt, pk = r
        desc = f"{name} ({col_type or 'ANY'}"
        if pk:
            desc += ", PK"
        if name in fks:
            desc += f", FK -> {fks[name]}"
        desc += ")"
        cols.append(desc)
    return f"Table: {table}\nColumns: " + ", ".join(cols)


def sample_values(table: str, column: str, n: int = 5, con: sqlite3.Connection = None) -> str:
    """Return up to 5 distinct non-null sampled values with strings truncated to 80 chars."""
    limit = min(max(1, int(n)), 5)
    rows = con.execute(
        f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL LIMIT {limit}'
    ).fetchall()
    sampled = []
    for (val,) in rows:
        if isinstance(val, str) and len(val) > 80:
            val = val[:80]
        sampled.append(val)
    return str(sampled)
