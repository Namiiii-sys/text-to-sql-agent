import pytest
from app.guardrails.sql_static import check_sql

ALLOWED_TABLES = {"Album", "Artist", "Customer", "Invoice", "InvoiceLine", "Track"}


# ── Parametrized Bad Queries (~20 cases) ──────────────────────

BAD_QUERIES = [
    # 1. DROP TABLE
    ("DROP TABLE Album", "Statement must be a SELECT"),
    # 2. Semicolon chain with DROP
    ("SELECT * FROM Album; DROP TABLE Artist;", "Exactly one statement allowed"),
    # 3. Semicolon chain with two SELECTs
    ("SELECT * FROM Album; SELECT * FROM Artist;", "Exactly one statement allowed"),
    # 4. INSERT INTO
    ("INSERT INTO Artist (Name) VALUES ('Attacker')", "Statement must be a SELECT"),
    # 5. UPDATE
    ("UPDATE Customer SET Email = 'hacked@evil.com'", "Statement must be a SELECT"),
    # 6. DELETE
    ("DELETE FROM Customer WHERE CustomerId = 1", "Statement must be a SELECT"),
    # 7. CREATE TABLE
    ("CREATE TABLE Backdoor (id INT)", "Statement must be a SELECT"),
    # 8. ALTER TABLE
    ("ALTER TABLE Album ADD COLUMN evil TEXT", "Statement must be a SELECT"),
    # 9. PRAGMA
    ("PRAGMA table_info(Album)", "Statement must be a SELECT"),
    # 10. ATTACH DATABASE
    ("ATTACH DATABASE 'evil.db' AS evil", "Statement must be a SELECT"),
    # 11. Forbidden function: load_extension
    ("SELECT load_extension('evil.so') FROM Album", "Forbidden function: load_extension"),
    # 12. Forbidden function: readfile
    ("SELECT readfile('/etc/passwd') FROM Album", "Forbidden function: readfile"),
    # 13. Forbidden function: writefile
    ("SELECT writefile('backdoor.php', 'data') FROM Album", "Forbidden function: writefile"),
    # 14. Direct access to sqlite_master
    ("SELECT * FROM sqlite_master", "Disallowed table(s): sqlite_master"),
    # 15. UNION with sqlite_master
    ("SELECT Title FROM Album UNION SELECT name FROM sqlite_master", "Disallowed table(s): sqlite_master"),
    # 16. Subquery targeting sqlite_master
    ("SELECT * FROM Album WHERE Title IN (SELECT name FROM sqlite_master)", "Disallowed table(s): sqlite_master"),
    # 17. Disallowed table not in allowlist
    ("SELECT * FROM PasswordsTable", "Disallowed table(s): passwordstable"),
    # 18. Subquery referencing disallowed table
    ("SELECT * FROM Album WHERE AlbumId IN (SELECT id FROM SecretTable)", "Disallowed table(s): secrettable"),
    # 19. Empty string
    ("", "Exactly one statement allowed"),
    # 20. Comment-only string
    ("-- just a comment", "Exactly one statement allowed"),
    # 21. Comment trick attempting to hide second statement
    ("SELECT * FROM Album; /* comment */ DROP TABLE Artist;", "Exactly one statement allowed"),
    # 22. Syntax error
    ("SELECT FROM WHERE", "Parse error"),
]


@pytest.mark.parametrize("bad_sql,expected_snippet", BAD_QUERIES)
def test_check_sql_blocks_bad_queries(bad_sql, expected_snippet):
    decision, reason, _ = check_sql(bad_sql, ALLOWED_TABLES)
    assert decision == "block"
    assert expected_snippet.lower() in reason.lower()


# ── Parametrized Good Queries (~10 cases) ─────────────────────

GOOD_QUERIES = [
    # 1. Simple SELECT
    "SELECT Title FROM Album",
    # 2. SELECT with WHERE and ORDER BY
    "SELECT * FROM Customer WHERE Country = 'USA' ORDER BY LastName",
    # 3. Aggregation and GROUP BY
    "SELECT ArtistId, COUNT(*) FROM Album GROUP BY ArtistId HAVING COUNT(*) > 1",
    # 4. JOIN with ON
    "SELECT Album.Title, Artist.Name FROM Album JOIN Artist ON Album.ArtistId = Artist.ArtistId",
    # 5. JOIN with USING
    "SELECT * FROM Album JOIN Artist USING (ArtistId)",
    # 6. Multi-table JOIN with ON
    "SELECT Track.Name, Album.Title, Artist.Name FROM Track JOIN Album ON Track.AlbumId = Album.AlbumId JOIN Artist ON Album.ArtistId = Artist.ArtistId",
    # 7. Common Table Expression (CTE)
    "WITH TopAlbums AS (SELECT AlbumId, Title FROM Album WHERE AlbumId < 10) SELECT * FROM TopAlbums",
    # 8. Set operation (UNION of allowed tables)
    "SELECT Title FROM Album WHERE AlbumId = 1 UNION SELECT Title FROM Album WHERE AlbumId = 2",
    # 9. Query with existing LIMIT clause
    "SELECT * FROM Track LIMIT 10",
]


@pytest.mark.parametrize("good_sql", GOOD_QUERIES)
def test_check_sql_allows_or_modifies_good_queries(good_sql):
    decision, reason, mod_sql = check_sql(good_sql, ALLOWED_TABLES)
    assert decision in ("allow", "modify")
    assert "limit" in mod_sql.lower()


def test_missing_limit_is_added():
    sql = "SELECT Title FROM Album"
    decision, reason, mod_sql = check_sql(sql, ALLOWED_TABLES)
    assert decision == "modify"
    assert "added limit 200" in reason.lower()
    assert "LIMIT 200" in mod_sql


def test_existing_limit_is_preserved():
    sql = "SELECT Title FROM Album LIMIT 5"
    decision, reason, mod_sql = check_sql(sql, ALLOWED_TABLES)
    assert decision == "allow"
    assert "LIMIT 5" in mod_sql


def test_cartesian_join_is_flagged():
    sql = "SELECT * FROM Album JOIN Artist"
    decision, reason, _ = check_sql(sql, ALLOWED_TABLES)
    assert "cartesian" in reason.lower()
