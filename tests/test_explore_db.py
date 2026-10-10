import sqlite3
from explore_db import count_tables


def test_count_tables(tmp_path):
    db_file = tmp_path / "test.sqlite"
    con = sqlite3.connect(db_file)
    con.execute("CREATE TABLE t1 (id INT)")
    con.execute("CREATE TABLE t2 (id INT)")
    con.close()
    assert count_tables(db_file) == 2
