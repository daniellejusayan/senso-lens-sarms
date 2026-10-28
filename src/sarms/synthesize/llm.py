"""The only place sarms talks to a language model: one chat completion per call, no tools, no agent.

Any OpenAI-compatible endpoint works, so the model is a configuration choice, not code:

  Ollama (local, free; default)   SARMS_LLM_BASE_URL=http://localhost:11434/v1  SARMS_LLM_MODEL=qwen2.5-coder:7b
  Gemini (free tier)              SARMS_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
                                  SARMS_LLM_MODEL=gemini-2.5-flash  SARMS_LLM_API_KEY=<key from AI Studio>
  OpenAI / OpenRouter / Groq      their base URL, model name and key
  fake (tests, demos offline)     SARMS_LLM_BASE_URL=fake:<file or directory of numbered replies>

Every call returns the text and a record (model, base URL host, prompt hash, seconds, usage)
that the draft step stores next to the prompt and the reply, so a draft can be reproduced
when the post-hoc audit asks. Temperature is 0 by default.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5-coder:7b"


class LLMError(RuntimeError):
    pass


def settings(model=None, base_url=None, api_key=None):
    return {"model": model or os.environ.get("SARMS_LLM_MODEL", DEFAULT_MODEL),
            "base_url": (base_url or os.environ.get("SARMS_LLM_BASE_URL", DEFAULT_BASE)).rstrip("/"),
            "api_key": api_key or os.environ.get("SARMS_LLM_API_KEY", "ollama")}


def prompt_hash(system, prompt):
    return hashlib.sha256((system or "").encode() + b"\0" + prompt.encode()).hexdigest()


def _fake(base_url, call_no):
    src = Path(base_url[len("fake:"):])
    if src.is_dir():
        files = sorted(src.glob("*.txt"))
        if not files:
            raise LLMError(f"fake model: no .txt replies in {src}")
        return files[min(call_no, len(files) - 1)].read_text()
    return src.read_text()


def complete(prompt, system=None, model=None, base_url=None, api_key=None, temperature=0.0, timeout=900, call_no=0):
    """-> (text, record). Raises LLMError when the endpoint cannot be reached or answers oddly."""
    cfg = settings(model, base_url, api_key)
    t0 = time.time()
    rec = {"model": cfg["model"], "endpoint": cfg["base_url"].split("//")[-1].split("/")[0],
           "prompt_hash": prompt_hash(system, prompt), "temperature": temperature}
    if cfg["base_url"].startswith("fake:"):
        text = _fake(cfg["base_url"], call_no)
        rec.update({"model": "fake", "seconds": 0.0})
        return text, rec
    body = {"model": cfg["model"], "temperature": temperature,
            "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(cfg["base_url"] + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"{cfg['base_url']} answered HTTP {e.code}: {e.read()[:300]!r}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"cannot reach {cfg['base_url']}: {e}. Is Ollama running (`ollama serve`), or is the key/URL right?") from e
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"unexpected reply shape: {json.dumps(data)[:300]}") from e
    rec.update({"seconds": round(time.time() - t0, 1), "usage": data.get("usage"), "served_model": data.get("model")})
    return text, rec
