"""Static SQL guardrail validating SQLite queries via AST parsing with sqlglot."""
import sqlglot
from sqlglot import exp

BANNED_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.Create, exp.Pragma, exp.Command, exp.Attach,
)

BANNED_FUNCS = {"load_extension", "writefile", "readfile", "edit"}


def _extract_tables(tree: exp.Expression) -> set[str]:
    """Extract real table names, excluding CTE table aliases."""
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables = set()
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name and name not in cte_names:
            tables.add(name)
    return tables


def _has_cartesian_join(tree: exp.Expression) -> bool:
    """Return True if any JOIN lacks an explicit ON or USING condition."""
    for join in tree.find_all(exp.Join):
        on = join.args.get("on")
        using = join.args.get("using")
        if not using and (on is None or isinstance(on, exp.Boolean)):
            return True
    return False


def check_sql(
    sql: str, allowed_tables: set[str] | list[str]
) -> tuple[str, str, str]:
    """Inspect and sanitize SQL query. Returns (decision, reason, sql).

    decision is one of 'allow', 'modify', or 'block'.
    """
    try:
        trees = sqlglot.parse(sql, read="sqlite")
    except Exception as e:
        return "block", f"Parse error: {e}", sql

    if not trees or len(trees) != 1 or trees[0] is None:
        return "block", "Exactly one statement allowed", sql
    tree = trees[0]

    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return "block", f"Statement must be a SELECT, got {type(tree).__name__}", sql

    for node in tree.walk():
        if isinstance(node, BANNED_NODES):
            return "block", f"Forbidden statement type: {type(node).__name__}", sql
        if isinstance(node, exp.Anonymous) and node.name.lower() in BANNED_FUNCS:
            return "block", f"Forbidden function: {node.name}", sql

    allowed = {t.lower() for t in allowed_tables}
    tables = _extract_tables(tree)
    disallowed = [t for t in tables if t.startswith("sqlite_") or t not in allowed]
    if disallowed:
        return "block", f"Disallowed table(s): {', '.join(sorted(disallowed))}", sql

    cartesian = _has_cartesian_join(tree)
    reason = "Possible Cartesian join without ON or USING" if cartesian else "ok"

    if tree.args.get("limit") is None:
        tree = tree.limit(200)
        return "modify", f"{reason} (added LIMIT 200)", tree.sql(dialect="sqlite")

    return "allow", reason, tree.sql(dialect="sqlite")
