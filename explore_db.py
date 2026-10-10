import pathlib
import sqlite3


def count_tables(db_path: pathlib.Path) -> int:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return cur.fetchone()[0]
    finally:
        con.close()


def find_and_count_databases(base_dir: pathlib.Path) -> list[tuple[int, str, str]]:
    results = []
    for f in base_dir.rglob("*.sqlite"):
        results.append((count_tables(f), f.name, str(f)))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


if __name__ == "__main__":
    for count, name, path in find_and_count_databases(pathlib.Path("data")):
        print(f"{count:3d} tables: {name} ({path})")
