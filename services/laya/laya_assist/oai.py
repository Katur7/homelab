"""OpenAI-compatible layer: laya first, LLM as fallback."""
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import schema

ACTION_TOOLS: Dict[str, List[str]] = {
    "on":          ["HassTurnOn"],
    "off":         ["HassTurnOff"],
    "open":        ["HassTurnOn"],
    "close":       ["HassTurnOff"],
    "brightness":  ["HassLightSet", "HassTurnOn"],
    "temperature": ["HassClimateSetTemperature", "HassSetTemperature", "HassTurnOn"],
    "query":       ["HassGetState", "GetLiveContext"],
    "toggle":      [],
    # Legacy German keys in case old config is loaded
    "an":          ["HassTurnOn"],
    "aus":         ["HassTurnOff"],
    "hoch":        ["HassTurnOn"],
    "runter":      ["HassTurnOff"],
    "heller":      ["HassLightSet", "HassTurnOn"],
    "wärmer":      ["HassClimateSetTemperature", "HassSetTemperature", "HassTurnOn"],
    "frage":       ["HassGetState", "GetLiveContext"],
    "wechseln":    [],
}


def last_user_message(messages: List[Dict[str, Any]]) -> str:
    """Extract last user utterance from messages."""
    for m in reversed(messages or []):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c.strip()
        if isinstance(c, list):
            parts = [p.get("text", "") for p in c if isinstance(p, dict)]
            return " ".join(t for t in parts if t).strip()
    return ""


def ends_with_tool_result(messages: List[Dict[str, Any]]) -> bool:
    """Did the client return a tool result and now expects a text response?"""
    for m in reversed(messages or []):
        role = m.get("role")
        if role == "tool":
            return True
        if role in ("user", "system"):
            return False
    return False


CONTEXT_CHARS = 120


def history(messages: List[Dict[str, Any]], limit: int) -> List[Dict[str, str]]:
    """The last `limit` utterances BEFORE the current one, oldest first."""
    if limit <= 0:
        return []
    msgs = list(messages or [])
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "user":
            msgs = msgs[:i]
            break
    out: List[Dict[str, str]] = []
    for m in reversed(msgs):
        if len(out) >= limit:
            break
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(part.get("text", "") for part in content
                               if isinstance(part, dict))
        text = (content or "").strip()
        if not text:
            continue
        out.append({"role": "user" if role == "user" else "assistant",
                    "text": text[:CONTEXT_CHARS]})
    return list(reversed(out))


SWITCHING_TOOLS = {"HassTurnOn", "HassTurnOff", "HassLightSet",
                   "HassClimateSetTemperature", "HassSetTemperature"}


def answered_tools(messages: List[Dict[str, Any]]) -> List[str]:
    """Base names of tools whose result is at the end of the conversation."""
    for m in reversed(messages or []):
        calls = m.get("tool_calls")
        if m.get("role") == "assistant" and calls:
            return [(c.get("function") or {}).get("name", "").rsplit("__", 1)[-1]
                    for c in calls]
        if m.get("role") == "user":
            break
    return []


def result_needs_words(messages: List[Dict[str, Any]]) -> bool:
    """Does the tool result need to be phrased into a sentence, or is a short acknowledgment enough?"""
    names = answered_tools(messages)
    if not names:
        return True
    return any(n not in SWITCHING_TOOLS for n in names)


def declared_tools(body: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Name -> function definition from the `tools` field of the request."""
    out: Dict[str, Dict[str, Any]] = {}
    for t in body.get("tools") or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") if t.get("type") == "function" else t
        if isinstance(fn, dict) and fn.get("name"):
            out[fn["name"]] = fn
    return out


def resolve_tool(tools: Dict[str, Dict[str, Any]], base: str) -> Optional[str]:
    """Finds the actual tool name for a base intent name."""
    if base in tools:
        return base
    for name in tools:
        if name.rsplit("__", 1)[-1] == base:
            return name
    return None


def _coerce(value: Any, prop: Dict[str, Any]) -> Any:
    t = (prop or {}).get("type")
    if t == "array":
        return value if isinstance(value, list) else [value]
    if t == "integer" and isinstance(value, (int, float)):
        return int(round(value))
    if t == "number" and isinstance(value, (int, float)):
        return float(value)
    if t == "string" and not isinstance(value, str):
        return str(value)
    return value


def _schema_properties(fn: Dict[str, Any]) -> Tuple[set, set]:
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    required = set(params.get("required") or [])
    return set(props.keys()), required


def fit_arguments(fn: Dict[str, Any], candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed, required = _schema_properties(fn)
    props = (fn.get("parameters") or {}).get("properties") or {}
    if not allowed:
        args = {k: v for k, v in candidate.items() if v is not None}
    else:
        args = {k: _coerce(v, props.get(k))
                for k, v in candidate.items() if k in allowed and v is not None}
    if required - set(args):
        return None
    return args


def build_tool_call(answers: Dict[str, Any], toolcall: Dict[str, Any],
                    entities: Dict[str, Dict[str, str]], areas: Dict[str, str],
                    tools: Dict[str, Dict[str, Any]], threshold: float,
                    text: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
    """Builds an OpenAI tool call from laya answers."""
    if not tools:
        return None, "Client offered no tools"

    kind = toolcall.get("kind")
    if kind not in ("service_call", "query"):
        return None, "laya returned no executable call (%s)" % kind

    conf = toolcall.get("confidence")
    if conf is not None and conf < threshold:
        return None, "Confidence %.2f below threshold %.2f" % (conf, threshold)

    action = answers["action"]["choice"]
    names = ACTION_TOOLS.get(action) or []
    if not names:
        return None, "Action %r has no intent counterpart" % action

    device_key = answers["device"]["choice"]
    entity = entities.get(device_key)
    area_key = answers["area"]["choice"]
    area_conf = answers["area"]["confidence"]

    candidate: Dict[str, Any] = {}
    if entity is not None and _area_instead_of_device(entity, area_key, area_conf,
                                                      threshold, text, areas):
        candidate["area"] = _area_label(area_key, areas)
        candidate["domain"] = entity.get("domain")
    elif entity is not None:
        candidate["name"] = (entity.get("assist_name") or entity.get("name")
                             or entity["entity_id"])
        candidate["domain"] = entity.get("domain")
    elif area_key and area_key not in ("unknown", "unklar"):
        candidate["area"] = _area_label(area_key, areas)
    else:
        return None, "no device or area could be determined"

    data = toolcall.get("data") or {}
    if "brightness_pct" in data:
        candidate["brightness"] = data["brightness_pct"]
    if "temperature" in data:
        candidate["temperature"] = data["temperature"]

    for base in names:
        actual = resolve_tool(tools, base)
        if actual is None:
            continue
        args = fit_arguments(tools[actual], candidate)
        if args is None:
            continue
        return {
            "id": "call_" + uuid.uuid4().hex[:20],
            "type": "function",
            "function": {"name": actual,
                         "arguments": json.dumps(args, ensure_ascii=False)},
        }, "laya -> %s%s" % (actual, " (via area)" if "area" in args else "")

    return None, ("none of the tools %s were offered (available: %s)"
                  % (names, ", ".join(sorted(tools)[:6]) or "none"))


def _area_instead_of_device(entity: Dict[str, Any], area_key: str, area_conf: float,
                            threshold: float, text: str, areas: Dict[str, str]) -> bool:
    if not area_key or area_key in ("unknown", "unklar") or area_conf < threshold:
        return False
    if not schema.area_named(text, area_key, areas):
        return False
    own_area = entity.get("area") or ""
    return bool(own_area) and own_area != area_key


def _area_label(key: str, areas: Dict[str, str]) -> str:
    if not key:
        return ""
    label = areas.get(key)
    if label and "," not in label and not label.lower().startswith(("area ", "bereich ")):
        return label
    return key.replace("_", " ").title()


def completion(model: str, content: Optional[str] = None,
               tool_calls: Optional[List[Dict[str, Any]]] = None,
               extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    msg: Dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
        msg["content"] = content
    out = {
        "id": "chatcmpl-" + uuid.uuid4().hex[:24],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": msg,
                     "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    if extra:
        out["laya"] = extra
    return out


def to_sse(payload: Dict[str, Any]) -> bytes:
    choice = payload["choices"][0]
    msg = choice["message"]
    delta: Dict[str, Any] = {"role": "assistant"}
    if msg.get("content") is not None:
        delta["content"] = msg["content"]
    if msg.get("tool_calls"):
        delta["tool_calls"] = [
            {"index": i, **tc} for i, tc in enumerate(msg["tool_calls"])]
    head = {"id": payload["id"], "object": "chat.completion.chunk",
            "created": payload["created"], "model": payload["model"],
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
    tail = {"id": payload["id"], "object": "chat.completion.chunk",
            "created": payload["created"], "model": payload["model"],
            "choices": [{"index": 0, "delta": {},
                         "finish_reason": choice["finish_reason"]}]}
    lines = [b"data: " + json.dumps(head, ensure_ascii=False).encode(), b"\n\n",
             b"data: " + json.dumps(tail, ensure_ascii=False).encode(), b"\n\n",
             b"data: [DONE]\n\n"]
    return b"".join(lines)
