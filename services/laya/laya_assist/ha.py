"""Lightweight Home Assistant REST client: fetch catalog and execute service calls."""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import ha_ws
from . import schema

SUPPORTED_DOMAINS = {"light", "switch", "climate", "cover", "media_player",
                     "lock", "vacuum", "fan", "scene", "script"}


def _request(base_url: str, token: str, path: str, method: str = "GET",
             payload: Optional[dict] = None, timeout: float = 10.0) -> Any:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError("HA %s %s -> HTTP %d: %s"
                           % (method, path, e.code, e.read().decode()[:300]))
    except urllib.error.URLError as e:
        raise RuntimeError("HA unreachable (%s): %s" % (url, e.reason))
    return json.loads(body) if body.strip() else None


_UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "å": "a", "æ", "ae",
            "ø": "o", "ð": "d", "þ": "th", "á": "a", "é": "e", "í": "i",
            "ó": "o", "ú": "u", "ý": "y"}


def _slug(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch == "ä":
            out.append("ae")
        elif ch == "ö":
            out.append("oe")
        elif ch == "ü":
            out.append("ue")
        elif ch == "ß":
            out.append("ss")
        elif ch == "æ":
            out.append("ae")
        elif ch == "ø":
            out.append("o")
        elif ch == "å":
            out.append("a")
        elif ch == "ð":
            out.append("d")
        elif ch == "þ":
            out.append("th")
        elif ch in ("á", "é", "í", "ó", "ú", "ý"):
            out.append({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ý": "y"}[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in " -_/.":
            out.append("_")
    return "_".join(x for x in "".join(out).split("_") if x) or "entity"


def _head(ent: Dict[str, Any], areas: Dict[str, str]) -> str:
    """The distinguishing prefix: area (with its aliases) and trilingual device type."""
    dom = ent.get("domain", "")
    dom_words = schema.DOMAIN_SYNONYMS.get(dom, dom)
    area_desc = areas.get(ent.get("area") or "", "")
    return ("%s — %s" % (area_desc, dom_words)).strip(" —")


def describe_all(entities: Dict[str, Dict[str, Any]], areas: Dict[str, str]):
    """Sets `desc` -- the trilingual description laya matches against."""
    for key, ent in entities.items():
        head = _head(ent, areas)
        parts = [head] if head else []
        name = (ent.get("name") or "").strip()
        if name and name.lower() not in head.lower():
            parts.insert(0, name)
        for alias in ent.get("aliases") or []:
            if alias.lower() not in " ".join(parts).lower():
                parts.append(alias)
        ent["desc"] = " | ".join(parts) or name or ent["entity_id"]


CATALOG_TEMPLATE = """
{%- set ns = namespace(items=[]) -%}
{%- for s in states -%}
  {%- if s.domain in __DOMAINS__ -%}
    {%- set ns.items = ns.items + [{
      'entity_id': s.entity_id, 'name': s.name,
      'area': area_name(s.entity_id) or '', 'area_id': area_id(s.entity_id) or '',
      'domain': s.domain}] -%}
  {%- endif -%}
{%- endfor -%}
{{ ns.items | tojson }}
"""


def _format_area_desc(area_name: str, area_id: str, area_aliases: Optional[Dict[str, List[str]]]) -> str:
    """Combine HA area name, HA area aliases (Swedish/Icelandic), and built-in synonyms."""
    parts = [area_name]
    if area_aliases and area_id in area_aliases:
        for al in area_aliases[area_id]:
            if al.lower() not in [p.lower() for p in parts]:
                parts.append(al)
    builtin = schema.AREA_SYNONYMS.get(area_name.lower(), "")
    if builtin:
        for b in [x.strip() for x in builtin.split(",")]:
            if b and b.lower() not in [p.lower() for p in parts]:
                parts.append(b)
    return ", ".join(parts)


def fetch_catalog_via_template(base_url: str, token: str, limit: int = 200,
                               allow: Optional[Dict[str, Dict[str, Any]]] = None,
                               area_aliases: Optional[Dict[str, List[str]]] = None
                               ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    """Fetch catalog with real areas and area aliases rendered by Home Assistant."""
    tpl = CATALOG_TEMPLATE.replace("__DOMAINS__", json.dumps(sorted(SUPPORTED_DOMAINS)))
    raw = _request(base_url, token, "/api/template", method="POST",
                   payload={"template": tpl}, timeout=20.0)
    rows = raw if isinstance(raw, list) else json.loads(raw)
    if allow is not None:
        rows = [r for r in rows if r.get("entity_id") in allow]

    entities: Dict[str, Dict[str, str]] = {}
    areas: Dict[str, str] = {}
    for row in rows[:limit]:
        entry = (allow or {}).get(row["entity_id"]) or {}
        aliases = list(entry.get("aliases") or [])
        name = (entry.get("name") or row.get("name")
                or row["entity_id"].split(".", 1)[-1]).strip()
        key = _slug(name) or _slug(row["entity_id"])
        if key in entities:
            key = _slug("%s %s" % (name, row["entity_id"].split(".", 1)[-1]))
        area_name = (row.get("area") or "").strip()
        area_id = (row.get("area_id") or "").strip()
        area_key = _slug(area_name) if area_name else ""
        if area_key:
            areas[area_key] = _format_area_desc(area_name, area_id, area_aliases)
        entities[key] = {
            "name": name,
            "entity_id": row["entity_id"],
            "domain": row["domain"],
            "area": area_key,
            "area_id": area_id,
            "desc": "",
        }
        if aliases:
            entities[key]["aliases"] = aliases
    describe_all(entities, areas)
    return entities, areas


def fetch_catalog(base_url: str, token: str, limit: int = 200
                  ) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str], Dict[str, Any]]:
    """Fetch catalog from Home Assistant, filtered by Assist exposure and enriched with Area aliases."""
    info: Dict[str, Any] = {"assist_filter": False, "freigegeben": 0,
                            "mit_alias": 0, "nicht_ansprechbar": [],
                            "warnung": ""}
    allow: Optional[Dict[str, Dict[str, Any]]] = None
    area_aliases: Optional[Dict[str, List[str]]] = None
    try:
        allow, area_aliases = ha_ws.fetch_assist_entities(base_url, token)
        info["assist_filter"] = True
        info["freigegeben"] = len(allow)
    except Exception as e:
        info["warnung"] = ("Assist exposure list unavailable (%s) -- catalog "
                           "is unfiltered" % e)

    try:
        ents, areas = fetch_catalog_via_template(base_url, token, limit=limit,
                                                 allow=allow, area_aliases=area_aliases)
        if ents or (allow is not None and not allow):
            info["mit_alias"] = sum(1 for e in ents.values() if e.get("aliases"))
            info["nicht_ansprechbar"] = verify_names(base_url, token, ents)
            return ents, areas, info
    except Exception:
        pass

    states = _request(base_url, token, "/api/states")
    entities: Dict[str, Dict[str, str]] = {}
    area_hits: Dict[str, int] = {}

    for st in states:
        eid = st.get("entity_id", "")
        domain = eid.split(".")[0]
        if domain not in SUPPORTED_DOMAINS:
            continue
        if allow is not None and eid not in allow:
            continue
        entry = (allow or {}).get(eid) or {}
        aliases = list(entry.get("aliases") or [])
        attrs = st.get("attributes") or {}
        name = (entry.get("name") or attrs.get("friendly_name")
                or eid.split(".", 1)[-1].replace("_", " "))
        key = _slug(name)
        if key in entities:
            key = _slug("%s %s" % (name, eid.split(".", 1)[-1]))
        head = _slug(name.split()[0]) if name.split() else ""
        if head:
            area_hits[head] = area_hits.get(head, 0) + 1
        entities[key] = {
            "name": name,
            "entity_id": eid,
            "domain": domain,
            "area": head,
            "area_id": "",
            "desc": "",
        }
        if aliases:
            entities[key]["aliases"] = aliases
        if len(entities) >= limit:
            break

    areas = {a: "Area %s" % a for a, n in sorted(area_hits.items(),
                                                 key=lambda kv: -kv[1]) if n > 1}
    for ent in entities.values():
        if ent["area"] not in areas:
            ent["area"] = ""
    describe_all(entities, areas)
    info["mit_alias"] = sum(1 for e in entities.values() if e.get("aliases"))
    info["nicht_ansprechbar"] = verify_names(base_url, token, entities)
    return entities, areas, info


def _resolves(base_url: str, token: str, name: str, entity_id: str) -> bool:
    try:
        res = _request(base_url, token, "/api/intent/handle", method="POST",
                       payload={"name": "HassGetState", "data": {"name": name}},
                       timeout=10.0) or {}
    except RuntimeError:
        return False
    hits = ((res.get("data") or {}).get("success") or [])
    return any(h.get("id") == entity_id for h in hits)


def verify_names(base_url: str, token: str,
                 entities: Dict[str, Dict[str, Any]]) -> List[str]:
    unreachable: List[str] = []
    for key, ent in entities.items():
        eid = ent["entity_id"]
        for candidate in list(ent.get("aliases") or []) + [ent.get("name") or ""]:
            if candidate and _resolves(base_url, token, candidate, eid):
                ent["assist_name"] = candidate
                break
        else:
            unreachable.append(eid)
    return unreachable


def call_service(base_url: str, token: str, domain: str, service: str,
                 target: Dict[str, Any], data: Dict[str, Any]) -> Any:
    payload = dict(data or {})
    payload.update(target or {})
    return _request(base_url, token, "/api/services/%s/%s" % (domain, service),
                    method="POST", payload=payload)


def get_state(base_url: str, token: str, entity_id: str) -> Any:
    return _request(base_url, token, "/api/states/%s" % entity_id)


def ping(base_url: str, token: str) -> Any:
    return _request(base_url, token, "/api/")
