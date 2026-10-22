"""Unified LLM adapter with response cache."""
import hashlib, json, os, re, sqlite3, time, dotenv
from dataclasses import dataclass, asdict
from pydantic import ValidationError
import groq, google.genai as genai

dotenv.load_dotenv()
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
_CACHE_PATH = os.getenv("LLM_CACHE_PATH", "cache.sqlite")

class QuotaExceeded(Exception):
    pass

@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str
    provider: str
    cached: bool

# Cache helpers

def _init_cache_db(path=None):
    p = path or _CACHE_PATH
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response_json TEXT)")
    con.commit()
    return con

def _cache_key(provider, model, prompt_version, messages, temperature):
    raw = json.dumps([provider, model, prompt_version, messages, temperature], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def _cache_get(con, key):
    row = con.execute("SELECT response_json FROM cache WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None

def _cache_put(con, key, result_dict):
    con.execute("INSERT OR REPLACE INTO cache (key, response_json) VALUES (?, ?)",
                (key, json.dumps(result_dict)))
    con.commit()


#  Provider adapters

def _call_groq(messages, model, temperature, seed, json_mode):
    client = groq.Groq()
    kwargs = {"model": model, "messages": messages, "temperature": temperature}
    if seed is not None:
        kwargs["seed"] = seed
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    c = resp.choices[0]
    return c.message.content, resp.usage.prompt_tokens, resp.usage.completion_tokens

def _call_gemini(messages, model, temperature, seed, json_mode):
    client = genai.Client()
    config = {"temperature": temperature}
    if seed is not None:
        config["seed"] = seed
    if json_mode:
        config["response_mime_type"] = "application/json"
    contents = [{"role": "model" if m["role"] == "assistant" else m["role"],
                 "parts": [{"text": m["content"]}]} for m in messages]
    resp = client.models.generate_content(model=model, contents=contents,
                                          config=config)
    return resp.text, resp.usage_metadata.prompt_token_count, resp.usage_metadata.candidates_token_count

# Main entry point 

_BACKOFF = [2, 4, 8]

def generate(messages, model=None, temperature=0, seed=None, json_mode=False,
             _provider_fn=None, _cache_con=None):
    provider = os.getenv("PROVIDER", "groq")
    model = model or os.getenv("MODEL", "llama-3.1-8b-instant")
    con = _cache_con or _init_cache_db()
    key = _cache_key(provider, model, PROMPT_VERSION, messages, temperature)
    hit = _cache_get(con, key)
    if hit:
        return LLMResult(**hit, cached=True)

    call_fn = _provider_fn or (_call_groq if provider == "groq" else _call_gemini)
    for i, wait in enumerate(_BACKOFF):
        try:
            t0 = time.time()
            text, tok_in, tok_out = call_fn(messages, model, temperature, seed, json_mode)
            latency = int((time.time() - t0) * 1000)
            result = LLMResult(text=text, tokens_in=tok_in, tokens_out=tok_out,
                               latency_ms=latency, model=model, provider=provider, cached=False)
            _cache_put(con, key, {k: v for k, v in asdict(result).items() if k != "cached"})
            return result
        except Exception as e:
            if not any(k in str(e).lower() for k in ("rate limit", "rate_limit", "429", "quota")):
                raise
            if i == len(_BACKOFF) - 1:
                raise QuotaExceeded(f"Rate-limited after {sum(_BACKOFF)}s backoff") from e
            time.sleep(wait)


#  JSON parsing helper

def parse_json(text, pydantic_model, _repair_fn=None):
    """Strip surrounding text, validate against pydantic_model, allow one repair."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    raw = match.group(0) if match else text
    try:
        return pydantic_model.model_validate_json(raw), False
    except ValidationError:
        if _repair_fn:
            repaired = _repair_fn(raw)
            match2 = re.search(r"\{.*\}", repaired, re.DOTALL)
            raw2 = match2.group(0) if match2 else repaired
            return pydantic_model.model_validate_json(raw2), True
        raise
