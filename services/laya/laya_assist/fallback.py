"""Fallback LLM client: forward requests to an OpenAI-compatible endpoint.

When Laya cannot decide with sufficient confidence (or for state queries), the
request is forwarded to the configured OpenAI-compatible endpoint (`/chat/completions`
and `/models`), such as Google Gemini (`https://generativelanguage.googleapis.com/v1beta/openai`)
or Ollama (`http://localhost:11434`).
"""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def base_url(url: str) -> str:
    """Normalize URL to its OpenAI base prefix; append `/v1` only when needed."""
    clean = (url or "").strip().rstrip("/")
    if not clean:
        return ""
    path = urlparse(clean).path.rstrip("/")
    if path.endswith("/v1") or path.endswith("/openai"):
        return clean
    return clean + "/v1"


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    head = {"Content-Type": "application/json"}
    if api_key:
        head["Authorization"] = "Bearer %s" % api_key
    return head


def _request(url: str, payload: Optional[dict], timeout: float,
             api_key: Optional[str]) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    for k, v in _headers(api_key).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError("Fallback LLM HTTP %d: %s"
                           % (e.code, e.read().decode()[:300]))
    except urllib.error.URLError as e:
        raise RuntimeError("Fallback LLM unreachable (%s): %s" % (url, e.reason))
    return json.loads(body) if body.strip() else None


def chat(url: str, model: str, body: Dict[str, Any], timeout: float = 120.0,
         api_key: Optional[str] = None) -> Dict[str, Any]:
    """Forward a chat completion request and return the OpenAI-format response."""
    payload = dict(body)
    payload["model"] = model
    payload["stream"] = False
    return _request(base_url(url) + "/chat/completions", payload, timeout, api_key)


def list_models(url: str, timeout: float = 10.0,
                api_key: Optional[str] = None) -> List[str]:
    """Return available models from the fallback endpoint."""
    try:
        data = _request(base_url(url) + "/models", None, timeout, api_key) or {}
        names = []
        for m in (data.get("data") or []):
            mid = m.get("id") or ""
            if mid.startswith("models/"):
                mid = mid[len("models/"):]
            if mid:
                names.append(mid)
        if names:
            return sorted(names)
    except RuntimeError as openai_err:
        try:
            data = _request((url or "").rstrip("/") + "/api/tags", None,
                            timeout, api_key) or {}
        except RuntimeError:
            raise openai_err
        return sorted(m.get("name") for m in (data.get("models") or []) if m.get("name"))
    return []
