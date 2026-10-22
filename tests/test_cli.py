"""Zero-network tests for the CLI pipeline (Config A and B)."""
import pathlib
from app.llm.client import LLMResult
from app.cli import run_pipeline

CHINOOK_PATH = str(pathlib.Path("data/chinook.sqlite"))


def _make_mock_generate(responses: list[str]):
    idx = 0

    def mock_gen(messages, **kwargs):
        nonlocal idx
        resp_text = responses[min(idx, len(responses) - 1)]
        idx += 1
        return LLMResult(
            text=resp_text,
            tokens_in=10,
            tokens_out=10,
            latency_ms=5,
            model="test-model",
            provider="groq",
            cached=False,
        )

    return mock_gen


def test_config_b_retries_on_guardrail_block():
    # Attempt 1: blocked DROP TABLE, Attempt 2: valid SELECT
    mock_gen = _make_mock_generate([
        '{"action": "final", "sql": "DROP TABLE Album", "reason": "malicious"}',
        '{"action": "final", "sql": "SELECT Title FROM Album", "reason": "fixed"}',
    ])
    sql, rows, trace = run_pipeline(
        "Show albums",
        db_path=CHINOOK_PATH,
        use_checks=True,
        use_retry=True,
        max_retries=3,
        _generate_fn=mock_gen,
    )
    assert "SELECT Title FROM Album" in sql
    assert len(rows) > 0


def test_config_a_does_not_retry():
    # Attempt 1 fails, config A has use_retry=False so it stops immediately
    mock_gen = _make_mock_generate([
        '{"action": "final", "sql": "SELECT * FROM NonExistentTable", "reason": "bad"}',
        '{"action": "final", "sql": "SELECT * FROM Album", "reason": "would fix"}',
    ])
    sql, rows, trace = run_pipeline(
        "Show albums",
        db_path=CHINOOK_PATH,
        use_checks=False,
        use_retry=False,
        _generate_fn=mock_gen,
    )
    assert len(rows) == 0
