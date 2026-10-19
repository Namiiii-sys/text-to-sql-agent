"""Zero-network tests for app.llm.client."""
import sqlite3, time
import pytest
from pydantic import BaseModel
from app.llm.client import (
    generate, parse_json, QuotaExceeded, LLMResult,
    _init_cache_db, _cache_key,
)


class _FakeRateLimit(Exception):
    """Simulates a rate limit error."""
    def __str__(self):
        return "rate limit exceeded"


def _make_fake_fn(text="hello", tok_in=10, tok_out=5):
    """Returns a provider function that needs no network."""
    def fn(messages, model, temperature, seed, json_mode):
        return text, tok_in, tok_out
    return fn


def _make_failing_fn():
    """Returns a provider fn that always raises a rate-limit error."""
    def fn(messages, model, temperature, seed, json_mode):
        raise _FakeRateLimit()
    return fn


# ── generate: basic call and cache ────────────────────────────

def test_generate_returns_result_and_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER", "groq")
    monkeypatch.setenv("MODEL", "test-model")
    db_path = str(tmp_path / "test_cache.sqlite")
    con = _init_cache_db(db_path)
    msgs = [{"role": "user", "content": "hi"}]

    r1 = generate(msgs, _provider_fn=_make_fake_fn("world", 8, 3), _cache_con=con)
    assert isinstance(r1, LLMResult)
    assert r1.text == "world"
    assert r1.tokens_in == 8
    assert r1.tokens_out == 3
    assert r1.cached is False

    r2 = generate(msgs, _provider_fn=_make_fake_fn("other", 1, 1), _cache_con=con)
    assert r2.text == "world"
    assert r2.cached is True


# ── generate: backoff then QuotaExceeded ──────────────────────

def test_generate_raises_quota_exceeded(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER", "groq")
    monkeypatch.setenv("MODEL", "test-model")
    db_path = str(tmp_path / "test_cache.sqlite")
    con = _init_cache_db(db_path)
    msgs = [{"role": "user", "content": "boom"}]

    import app.llm.client as client_mod
    original_backoff = client_mod._BACKOFF
    client_mod._BACKOFF = [0, 0, 0]  # no real waiting in tests
    try:
        with pytest.raises(QuotaExceeded):
            generate(msgs, _provider_fn=_make_failing_fn(), _cache_con=con)
    finally:
        client_mod._BACKOFF = original_backoff


# ── parse_json ────────────────────────────────────────────────

class Action(BaseModel):
    action: str
    table: str

def test_parse_json_strips_surrounding_text():
    raw = 'Sure! Here is the JSON:\n{"action": "inspect_schema", "table": "users"}\nDone.'
    result, repaired = parse_json(raw, Action)
    assert result.action == "inspect_schema"
    assert result.table == "users"
    assert repaired is False

def test_parse_json_repair_on_invalid():
    bad = '{"action": "inspect_schema"}'  # missing 'table'
    def repair_fn(text):
        return '{"action": "inspect_schema", "table": "fixed"}'
    result, repaired = parse_json(bad, Action, _repair_fn=repair_fn)
    assert result.table == "fixed"
    assert repaired is True

def test_parse_json_raises_without_repair():
    bad = '{"action": "inspect_schema"}'
    with pytest.raises(Exception):
        parse_json(bad, Action)
