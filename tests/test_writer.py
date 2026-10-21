"""Zero-network unit tests for the Writer agent inner tool loop."""
import pathlib
import pytest
from app.executor.runner import open_ro
from app.llm.client import LLMResult
from app.agents.writer import writer

CHINOOK_PATH = pathlib.Path("data/chinook.sqlite")


def _make_mock_generate(responses: list[str]):
    idx = 0

    def mock_gen(messages, model=None, temperature=0, seed=None, json_mode=False):
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


def test_writer_executes_tool_then_returns_final():
    con = open_ro(CHINOOK_PATH)
    try:
        mock_gen = _make_mock_generate([
            '{"action": "inspect_schema", "table": "Album"}',
            '{"action": "final", "sql": "SELECT Title FROM Album", "reason": "Retrieved album titles"}',
        ])
        sql, trace, calls = writer("Show album titles", con=con, _generate_fn=mock_gen)
        assert sql == "SELECT Title FROM Album"
        assert calls == 2
        assert len(trace) == 2
        assert trace[0]["action"] == "inspect_schema"
        assert trace[1]["action"] == "final"
    finally:
        con.close()


def test_writer_incorporates_feedback():
    con = open_ro(CHINOOK_PATH)
    recorded_messages = []

    def mock_gen(messages, **kwargs):
        recorded_messages.extend(messages)
        return LLMResult(
            text='{"action": "final", "sql": "SELECT 1", "reason": "fixed"}',
            tokens_in=5,
            tokens_out=5,
            latency_ms=2,
            model="m",
            provider="p",
            cached=False,
        )

    try:
        sql, trace, calls = writer(
            "Show albums",
            feedback="Column X does not exist",
            con=con,
            _generate_fn=mock_gen,
        )
        assert sql == "SELECT 1"
        assert any("Column X does not exist" in m.get("content", "") for m in recorded_messages)
    finally:
        con.close()


def test_writer_caps_at_max_steps():
    con = open_ro(CHINOOK_PATH)
    try:
        # LLM that keeps asking for list_tables forever
        mock_gen = _make_mock_generate(['{"action": "list_tables"}'])
        sql, trace, calls = writer("Any question", con=con, max_steps=4, _generate_fn=mock_gen)
        assert calls == 4
        assert len(trace) == 4
        assert sql == ""
    finally:
        con.close()
