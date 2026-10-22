"""CLI for running Text-to-SQL pipeline with Config A and B toggles."""
import argparse, sqlite3
from app.executor.runner import open_ro, execute_query
from app.guardrails.sql_static import check_sql
from app.agents.writer import writer


def run_pipeline(
    question: str,
    db_path: str = "data/bird_L0.sqlite",
    use_checks: bool = True,
    use_retry: bool = True,
    max_retries: int = 3,
    _generate_fn=None,
) -> tuple[str, list, list[dict]]:
    """Coordinate Writer, SQL guardrail, and executor with retry handling."""
    con = open_ro(db_path)
    try:
        allowed = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        feedback, trace, target_sql = None, [], ""
        attempts = max_retries if use_retry else 1

        for attempt in range(1, attempts + 1):
            print(f"[Attempt {attempt}/{attempts}] Generating query...")
            sql, tool_trace, calls = writer(question, feedback=feedback, con=con, _generate_fn=_generate_fn)
            trace.extend(tool_trace)
            print(f"[Writer] SQL: {sql}")
            if not sql:
                feedback = "Writer produced empty SQL."
                continue

            target_sql = sql
            if use_checks:
                decision, reason, mod_sql = check_sql(sql, allowed)
                print(f"[Guardrail] {decision.upper()}: {reason}")
                if decision == "block":
                    feedback = f"Guardrail blocked query: {reason}"
                    continue
                target_sql = mod_sql

            try:
                cols, rows, truncated = execute_query(con, target_sql)
                print(f"[Executor] Success: {len(rows)} rows returned (truncated={truncated})")
                return target_sql, rows, trace
            except sqlite3.OperationalError as e:
                print(f"[Executor] SQLite execution error: {e}")
                feedback = f"SQLite execution error: {e}"
                continue

        return target_sql, [], trace
    finally:
        con.close()


def main():
    """Command-line entrypoint for Text-to-SQL agent."""
    parser = argparse.ArgumentParser(description="Text-to-SQL agent runner")
    parser.add_argument("question", help="Natural language question")
    parser.add_argument("--level", type=int, default=0, help="Messiness level (0-3)")
    parser.add_argument("--config", choices=["A", "B"], default="B", help="Config A (off) or B (on)")
    args = parser.parse_args()

    use_checks = args.config == "B"
    use_retry = args.config == "B"
    db_path = f"data/bird_L{args.level}.sqlite"

    print(f"Question: {args.question}")
    print(f"Config: {args.config} (checks={use_checks}, retry={use_retry}) | DB: {db_path}\n")
    sql, rows, _ = run_pipeline(args.question, db_path=db_path, use_checks=use_checks, use_retry=use_retry)
    print(f"\nFinal SQL: {sql}")
    print(f"Result Rows ({len(rows)}): {rows[:5]}")


if __name__ == "__main__":
    main()
