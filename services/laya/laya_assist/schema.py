"""Question schema for Home Assistant tool calls (English, Swedish, Icelandic).

Translates a voice command into an HA service call. Consists of two parts:
  * ENTITIES -- catalog of controllable items (key -> entity_id, area, domain)
  * build_questions() -- typed questions built from the catalog for laya
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------- Trilingual Vocabulary

# Common room translations for the demo catalog & automatic area enrichment
AREA_SYNONYMS: Dict[str, str] = {
    "living room": "living room, vardagsrum, vardagsrummet, stofa, stofan, stofunni",
    "kitchen": "kitchen, kök, köket, eldhús, eldhúsið, eldhúsinu",
    "bedroom": "bedroom, sovrum, sovrummet, svefnherbergi, svefnherbergið, svefnherberginu",
    "kids bedroom": "kids bedroom, barnrum, barnrummet, barnaherbergi, barnaherbergið, barnaherberginu",
    "bathroom": "bathroom, badrum, badrummet, baðherbergi, baðherbergið, baðherberginu",
    "office": "office, study, kontor, kontoret, arbetsrum, skrifstofa, skrifstofunni",
    "hallway": "hallway, corridor, hall, hallen, gangur, ganginum, forstofa, forstofunni",
    "garden": "garden, patio, balcony, trädgård, altan, balkong, garður, svalir, verönd, úti",
    "garage": "garage, garaget, bílskúr, bílskúrnum",
    "laundry": "laundry, tvättstuga, þvottahús, þvottahúsinu",
}

DOMAIN_SYNONYMS: Dict[str, str] = {
    "light": "light, lights, lamp, ljus, lampa, belysning, ljós, ljósin, lampi",
    "switch": "switch, plug, outlet, strömbrytare, uttag, rofi, innstunga, tengill",
    "climate": "heating, thermostat, temperature, värme, termostat, temperatur, hiti, hitastig, ofn",
    "cover": "blinds, cover, curtain, awning, jalusi, rullgardin, markis, gardínur, gluggatjöld, sólhlíf, markísa",
    "media_player": "speaker, tv, media, music, högtalare, tv, musik, hátalari, sjónvarp, tónlist",
    "lock": "lock, door, lås, dörr, lás, hurð, útidyrahurð",
    "vacuum": "vacuum, robot vacuum, dammsugare, ryksuga, róbótaryksuga",
    "fan": "fan, ventilation, fläkt, vifta",
    "scene": "scene, scen, sena",
    "script": "script, routine, skript, rútína",
}

# Domain keywords in utterances used to boost/filter candidate devices
DOMAIN_HINT_WORDS: Dict[str, Tuple[str, ...]] = {
    "light": ("light", "lights", "lamp", "lamps", "dim", "bright", "ljus", "ljuset", "lampan", "lampor", "belysning", "dimma", "ljós", "ljósin", "ljósið", "lampa", "lampann", "birtu"),
    "climate": ("heat", "heating", "thermostat", "temperature", "cold", "warm", "degrees", "värme", "värmen", "termostat", "kallt", "varmt", "grader", "hita", "hitann", "ofn", "kalt", "hlýtt", "gráður"),
    "cover": ("blind", "blinds", "curtain", "curtains", "shutter", "awning", "rullgardin", "gardin", "gardiner", "markis", "jalusi", "gardínur", "gluggatjöld", "sólhlíf", "markísu"),
    "media_player": ("tv", "television", "speaker", "music", "volume", "radio", "högtalare", "musik", "sjónvarp", "sjónvarpið", "hátalara", "tónlist"),
    "lock": ("lock", "unlock", "door", "lås", "låsa", "dörr", "dörren", "lás", "læsa", "aflæsa", "hurð"),
    "vacuum": ("vacuum", "roborock", "clean", "dammsuga", "dammsugare", "ryksuga", "ryksuguna"),
}

# ---------------------------------------------------------------- Default Demo Catalog

DEFAULT_AREAS = {
    "living_room": "Living room, vardagsrum, vardagsrummet, stofa, stofan, stofunni",
    "kitchen": "Kitchen, kök, köket, eldhús, eldhúsið, eldhúsinu",
    "bedroom": "Bedroom, sovrum, sovrummet, svefnherbergi, svefnherbergið, svefnherberginu",
    "bathroom": "Bathroom, badrum, badrummet, baðherbergi, baðherbergið, baðherberginu",
    "office": "Office, study, kontor, kontoret, skrifstofa, skrifstofunni",
    "hallway": "Hallway, entrance, hall, hallen, gangur, ganginum, forstofa",
    "garden": "Garden, patio, balcony, trädgård, altan, garður, verönd",
}

DEFAULT_ENTITIES: Dict[str, Dict[str, str]] = {
    "light_living_room": {
        "name": "Living Room Light",
        "entity_id": "light.living_room_ceiling", "area": "living_room", "domain": "light",
        "desc": "Living room light, vardagsrum ljus lampa, stofa stofunni ljós",
    },
    "light_kitchen": {
        "name": "Kitchen Light",
        "entity_id": "light.kitchen_ceiling", "area": "kitchen", "domain": "light",
        "desc": "Kitchen light, kök köket ljus lampa, eldhús eldhúsinu ljós",
    },
    "light_bedroom": {
        "name": "Bedroom Light",
        "entity_id": "light.bedroom_bedside", "area": "bedroom", "domain": "light",
        "desc": "Bedroom light, bedside lamp, sovrum sovrummet ljus lampa, svefnherbergi svefnherberginu ljós",
    },
    "light_office": {
        "name": "Office Desk Lamp",
        "entity_id": "light.office_desk", "area": "office", "domain": "light",
        "desc": "Office desk lamp, kontor arbetsrum ljus lampa, skrifstofa skrifstofunni ljós lampi",
    },
    "climate_living_room": {
        "name": "Living Room Heating",
        "entity_id": "climate.living_room", "area": "living_room", "domain": "climate",
        "desc": "Living room heating thermostat, vardagsrum värme termostat, stofa stofunni hiti ofn",
    },
    "climate_bedroom": {
        "name": "Bedroom Heating",
        "entity_id": "climate.bedroom", "area": "bedroom", "domain": "climate",
        "desc": "Bedroom heating thermostat, sovrum värme termostat, svefnherbergi svefnherberginu hiti ofn",
    },
    "cover_living_room": {
        "name": "Living Room Blinds",
        "entity_id": "cover.living_room_blinds", "area": "living_room", "domain": "cover",
        "desc": "Living room blinds curtain awning, vardagsrum rullgardin gardin markis, stofa gardínur gluggatjöld sólhlíf",
    },
    "tv_living_room": {
        "name": "Living Room TV",
        "entity_id": "media_player.living_room_tv", "area": "living_room", "domain": "media_player",
        "desc": "Living room TV television, vardagsrum tv, stofa sjónvarp sjónvarpið",
    },
    "speaker_kitchen": {
        "name": "Kitchen Speaker",
        "entity_id": "media_player.kitchen_speaker", "area": "kitchen", "domain": "media_player",
        "desc": "Kitchen speaker music radio, kök högtalare musik, eldhús hátalari tónlist",
    },
    "coffee_machine": {
        "name": "Coffee Machine",
        "entity_id": "switch.kitchen_coffee_machine", "area": "kitchen", "domain": "switch",
        "desc": "Coffee machine switch in kitchen, kaffebryggare kaffemaskin, kaffivél",
    },
    "vacuum": {
        "name": "Vacuum Cleaner",
        "entity_id": "vacuum.roborock", "area": "hallway", "domain": "vacuum",
        "desc": "Robot vacuum cleaner, dammsugare robotdammsugare, ryksuga róbótaryksuga",
    },
    "front_door": {
        "name": "Front Door Lock",
        "entity_id": "lock.front_door", "area": "hallway", "domain": "lock",
        "desc": "Front door lock, ytterdörr lås, útidyrahurð hurð lás",
    },
}

# ---------------------------------------------------------------- Actions

ACTIONS: Dict[str, Dict[str, Any]] = {
    "on": {
        "desc": "turn on, switch on, start, enable | tänd, slå på, sätt på, starta | kveiktu, kveikja, kveiktu á, settu í gang",
        "services": {"light": "turn_on", "switch": "turn_on", "media_player": "turn_on",
                     "climate": "turn_on", "vacuum": "start", "cover": "open_cover",
                     "lock": "unlock", "fan": "turn_on", "scene": "turn_on", "script": "turn_on"},
    },
    "off": {
        "desc": "turn off, switch off, stop, disable | släck, slå av, stäng av, stoppa | slökktu, slökkva, slökktu á, stöðva",
        "services": {"light": "turn_off", "switch": "turn_off", "media_player": "turn_off",
                     "climate": "turn_off", "vacuum": "return_to_base",
                     "cover": "close_cover", "lock": "lock", "fan": "turn_off", "script": "turn_off"},
    },
    "toggle": {
        "desc": "toggle, invert current state | växla | víxla",
        "services": {"light": "toggle", "switch": "toggle", "media_player": "toggle",
                     "cover": "toggle", "fan": "toggle"},
    },
    "brightness": {
        "desc": "dim, brighten, set brightness percentage | dimma, ljusstyrka, mörkare, ljusare | dimma, birta, dekkra, bjartara",
        "services": {"light": "turn_on"},
    },
    "temperature": {
        "desc": "set temperature, warmer, cooler, heating | temperatur, varmare, kallare, höj värmen | hitastig, hlýrra, kaldara, hækka hitann",
        "services": {"climate": "set_temperature"},
    },
    "open": {
        "desc": "open, raise, roll up, unlock | öppna, dra upp, lås upp | opna, opnaðu, dregðu frá, aflæsa",
        "services": {"cover": "open_cover", "lock": "unlock"},
    },
    "close": {
        "desc": "close, lower, roll down, lock | stäng, dra ner, lås | loka, lokaðu, dregðu fyrir, læsa",
        "services": {"cover": "close_cover", "lock": "lock"},
    },
    "query": {
        "desc": "ask for current status or state without changing anything | är, vad är, status | er, hvað er, staða",
        "services": {},
    },
}

BRIGHTNESS_LEVELS = [
    "off / 0% / släck / slökkt",
    "very dim / 25% / svagt / dauft",
    "medium / half / 50% / hälften / hálft",
    "bright / 75% / ljust / bjart",
    "maximum / full / 100% / max / fullt",
]
BRIGHTNESS_PCT = [0, 25, 50, 75, 100]

TEMP_LEVELS = [
    "very cold / 16 degrees / kallt / kalt",
    "cool / 18 degrees / svalt / svalt",
    "normal / 20 degrees / lagom / eðlilegt",
    "warm / 22 degrees / varmt / hlýtt",
    "very warm / 24 degrees / hett / mjög hlýtt",
]
TEMP_VALUES = [16, 18, 20, 22, 24]

# Explicit deterministic verb overrides for unambiguous Icelandic/Swedish/English action verbs
ACTION_VERB_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("on", ("turn on", "switch on", "kveiktu", "kveikja", "tänd", "slå på", "sätt på")),
    ("off", ("turn off", "switch off", "slökktu", "slökkva", "släck", "stäng av", "slå av")),
    ("open", ("open ", "opnaðu", "opna ", "öppna", "unlock", "lås upp", "aflæstu")),
    ("close", ("close ", "lokaðu", "loka ", "stäng ", "lock ", "læstu")),
    ("brightness", ("dim ", "dimma", "brighten", "dekkra", "bjartara", "mörkare", "ljusare")),
]

# ---------------------------------------------------------------- Questions

CONTEXT_QUESTIONS = ("device", "area")
MAX_CANDIDATE_DEVICES = 14


def _fold(text: str) -> str:
    """Lowercase and normalize Nordic/Germanic diacritics for token matching."""
    out = (text or "").lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("å", "a"), ("æ", "ae"),
                 ("ø", "o"), ("ð", "d"), ("þ", "th"), ("ß", "ss"),
                 ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ý", "y")):
        out = out.replace(a, b)
    return out


def detect_language(text: str) -> str:
    """Detect whether an utterance is Icelandic ('is'), Swedish ('sv'), or English ('en')."""
    low = (text or "").lower()
    # Icelandic-specific characters and common command words
    if any(c in low for c in ("ð", "þ", "æ", "ý", "í", "ú", "ó", "á", "é")):
        return "is"
    words = set(re.findall(r"\w+", low))
    if words & {"kveiktu", "kveikja", "slökktu", "slokkva", "ljosin", "ljos", "svefnherbergi", "svefnherberginu", "stofunni", "eldhusinu", "opnadu", "lokadu"}:
        return "is"
    if any(c in low for c in ("å", "ä")) or (words & {"tänd", "tand", "släck", "slack", "slå", "stäng", "öppna", "vardagsrummet", "sovrummet", "köket", "ljuset", "lampan"}):
        return "sv"
    return "en"


def detect_domains(text: str) -> Set[str]:
    """Identify if the utterance explicitly mentions a domain (e.g. light, climate, cover)."""
    low = (text or "").lower()
    folded = _fold(low)
    matched: Set[str] = set()
    for dom, words in DOMAIN_HINT_WORDS.items():
        for w in words:
            if w in low or _fold(w) in folded:
                matched.add(dom)
                break
    return matched


def _score_entity(key: str, ent: Dict[str, Any], areas: Dict[str, str],
                  text: str, hinted_domains: Set[str]) -> float:
    """Lexical + domain relevance score to prune large entity catalogs to top K candidates."""
    score = 0.0
    dom = ent.get("domain", "")
    if hinted_domains:
        if dom in hinted_domains:
            score += 10.0
        else:
            score -= 5.0

    area_key = ent.get("area") or ""
    if area_key and area_named(text, area_key, areas):
        score += 15.0

    hay = _fold(text)
    tokens = [t for t in re.findall(r"\w+", hay) if len(t) > 2]
    desc_fold = _fold("%s %s %s" % (ent.get("name", ""), ent.get("desc", ""), key))
    for tok in tokens:
        if tok in desc_fold:
            score += 4.0
        elif len(tok) >= 4 and tok[:4] in desc_fold:
            score += 2.0
    return score


def select_candidates(entities: Dict[str, Dict[str, str]], areas: Dict[str, str],
                      text: str, max_candidates: int = MAX_CANDIDATE_DEVICES
                      ) -> Dict[str, Dict[str, str]]:
    """Prune entity catalog to at most `max_candidates` most relevant entities for fast CPU inference."""
    if not text or len(entities) <= max_candidates:
        return entities
    hinted = detect_domains(text)
    scored = sorted(
        entities.items(),
        key=lambda kv: _score_entity(kv[0], kv[1], areas, text, hinted),
        reverse=True,
    )
    return dict(scored[:max_candidates])


def build_questions(entities: Optional[Dict[str, Dict[str, str]]] = None,
                    areas: Optional[Dict[str, str]] = None,
                    text: str = "") -> Dict[str, Any]:
    """Builds the typed-question schema from an entity catalog.

    Only includes brightness/temperature/confirmation questions when relevant to the
    utterance, reducing forward-pass batch size from 7 sequences to 3 for standard commands.
    """
    entities = entities or DEFAULT_ENTITIES
    areas = areas or DEFAULT_AREAS

    candidates = select_candidates(entities, areas, text)
    device_crit = {k: v.get("desc") or v["entity_id"] for k, v in candidates.items()}
    device_crit["unknown"] = "no specific device named or not in catalog"

    area_crit = dict(areas)
    area_crit["unknown"] = "no room or area named"

    questions: Dict[str, Any] = {
        "action": {
            "type": "choice",
            "instructions": "Which action does `command` request?",
            "criteria": {k: v["desc"] for k, v in ACTIONS.items()},
        },
        "device": {
            "type": "choice",
            "instructions": "Which device from the list does `command` refer to?",
            "criteria": device_crit,
        },
        "area": {
            "type": "choice",
            "instructions": "Which room or area does `command` mention?",
            "criteria": area_crit,
        },
        "is_query": {
            "type": "noul",
            "instructions": "Is `command` asking a status question rather than giving a command?",
        },
    }

    low = _fold(text)
    # Only evaluate brightness/temperature score questions if the utterance could involve them
    if not text or any(w in low for w in ("dim", "bright", "pct", "%", "half", "halft", "mork", "ljus", "dekk", "bjart", "birt")):
        questions["brightness"] = {
            "type": "score",
            "instructions": "What brightness level does `command` request, if it is about lights?",
            "criteria": BRIGHTNESS_LEVELS,
        }
    if not text or any(w in low for w in ("temp", "heat", "cold", "warm", "cool", "deg", "grad", "varm", "kall", "hlý", "hly", "kalt", "hit")) or any(c.isdigit() for c in low):
        questions["temperature"] = {
            "type": "score",
            "instructions": "What temperature does `command` request, if it is about heating/climate?",
            "criteria": TEMP_LEVELS,
        }

    return questions


# ---------------------------------------------------------------- Toolcall

DOMAIN_IMPLYING = {"temperature", "brightness"}


def _same_area_fallback(entities: Dict[str, Dict[str, str]], entity: Dict[str, str],
                        action: str, hinted_domains: Optional[Set[str]] = None) -> Optional[Dict[str, str]]:
    """Finds a device in the same area whose domain supports the requested action or domain hint."""
    area = entity.get("area")
    if not area:
        return None
    if hinted_domains and entity.get("domain") not in hinted_domains:
        for cand in entities.values():
            if cand.get("area") == area and cand.get("domain") in hinted_domains:
                return cand
    if action not in DOMAIN_IMPLYING:
        return None
    supported = ACTIONS[action]["services"]
    for cand in entities.values():
        if cand.get("area") == area and cand["domain"] in supported:
            return cand
    return None


def area_named(text: str, area_key: str, areas: Dict[str, str]) -> bool:
    """Does the room name (or any of its aliases/stems) appear in the command text?"""
    if not text:
        return False
    hay = _fold(text)
    label = areas.get(area_key, "") or area_key.replace("_", " ")
    # Also include built-in trilingual synonyms if the area slug matches a known room
    slug_words = area_key.replace("_", " ")
    extra = AREA_SYNONYMS.get(slug_words, "")
    all_words = re.findall(r"\w+", _fold(f"{label} {slug_words} {extra}"))
    for w in all_words:
        if len(w) <= 2:
            continue
        if w in hay:
            return True
        # Match inflected Nordic stems (e.g. "svefnherbergi" in "svefnherberginu", "sovrum" in "sovrummet")
        if len(w) >= 5 and w[:5] in hay:
            return True
    return False


def find_named_area(text: str, areas: Dict[str, str]) -> Optional[str]:
    """Return the area_key if an area from the catalog is explicitly named in `text`."""
    for area_key in areas:
        if area_key not in ("unknown", "unklar") and area_named(text, area_key, areas):
            return area_key
    return None


def area_id_of(entities: Dict[str, Dict[str, str]], area_key: str) -> str:
    """Resolve the true HA area_id for our slug from the catalog."""
    for ent in entities.values():
        if ent.get("area") == area_key and ent.get("area_id"):
            return ent["area_id"]
    return area_key


def _override_action_from_verbs(text: str, current_action: str, current_conf: float) -> Tuple[str, float]:
    """Apply deterministic verb matching for clear Icelandic/Swedish/English imperatives."""
    low = " " + (text or "").lower().strip() + " "
    for act, phrases in ACTION_VERB_RULES:
        for p in phrases:
            if p in low:
                return act, max(current_conf, 0.92)
    return current_action, current_conf


def build_toolcall(answers: Dict[str, Any],
                   entities: Optional[Dict[str, Dict[str, str]]] = None,
                   threshold: float = 0.6, text: str = "",
                   areas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Translates laya answers into a Home Assistant service call."""
    entities = entities or DEFAULT_ENTITIES
    areas = areas if areas is not None else DEFAULT_AREAS
    warnings: List[str] = []

    action = answers["action"]["choice"]
    action_conf = answers["action"]["confidence"]
    action, action_conf = _override_action_from_verbs(text, action, action_conf)
    answers["action"]["choice"] = action
    answers["action"]["confidence"] = round(action_conf, 4)

    device_key = answers["device"]["choice"]
    device_conf = answers["device"]["confidence"]
    area_key = answers["area"]["choice"]
    area_conf = answers["area"]["confidence"]

    # If the utterance explicitly names a room (including Icelandic/Swedish aliases/stems),
    # ensure area_key reflects it with high confidence.
    explicit_area = find_named_area(text, areas)
    if explicit_area and (area_key != explicit_area or area_conf < 0.85):
        area_key = explicit_area
        area_conf = max(area_conf, 0.92)
        answers["area"]["choice"] = area_key
        answers["area"]["confidence"] = round(area_conf, 4)

    hinted_domains = detect_domains(text)

    # If a room + domain (e.g. "svefnherberginu" + "ljósin") are both clearly stated in the text,
    # and there is a matching entity in that room, boost/select that entity if the model was uncertain.
    if explicit_area and hinted_domains:
        matching_in_area = [
            (k, e) for k, e in entities.items()
            if e.get("area") == explicit_area and e.get("domain") in hinted_domains
        ]
        if len(matching_in_area) == 1:
            mk, me = matching_in_area[0]
            if device_key != mk or device_conf < threshold:
                device_key = mk
                device_conf = max(device_conf, 0.88)
                answers["device"]["choice"] = device_key
                answers["device"]["confidence"] = round(device_conf, 4)

    is_query = answers.get("is_query", {}).get("noul", 0.0)

    if action_conf < threshold:
        warnings.append("Action uncertain (%.2f < %.2f)" % (action_conf, threshold))
    if device_conf < threshold:
        warnings.append("Device uncertain (%.2f < %.2f)" % (device_conf, threshold))

    if is_query > 0.5 or action in ("query", "frage"):
        target = entities.get(device_key)
        return {
            "kind": "query",
            "domain": None,
            "service": None,
            "target": {"entity_id": target["entity_id"]} if target else {},
            "data": {},
            "warnings": warnings,
            "confidence": round(min(action_conf, device_conf), 4),
        }

    entity = entities.get(device_key)
    if entity is None or device_conf < threshold:
        if area_key not in ("unknown", "unklar") and area_conf >= threshold and area_named(text, area_key, areas):
            dom = next(iter(hinted_domains), "homeassistant")
            service = ACTIONS.get(action, {}).get("services", {}).get(dom)
            if not service:
                service = "turn_on" if action in ("on", "open", "an", "hoch") else "turn_off"
            warnings.append("Targeting area %r (%s.%s)" % (area_key, dom, service))
            return {
                "kind": "service_call", "domain": dom, "service": service,
                "target": {"area_id": area_id_of(entities, area_key)}, "data": {},
                "warnings": warnings, "confidence": round(min(action_conf, area_conf), 4),
            }
        if entity is None:
            warnings.append("Could not match any device -- clarification needed")
            return {"kind": "unresolved", "domain": None, "service": None, "target": {},
                    "data": {}, "warnings": warnings,
                    "confidence": round(min(action_conf, device_conf), 4)}

    domain = entity["domain"]
    # If the utterance explicitly asked for a domain (e.g. "lights") and the chosen device is a different domain (e.g. "vacuum"), switch to same-area device of the hinted domain
    if hinted_domains and domain not in hinted_domains:
        alt_dom = _same_area_fallback(entities, entity, action, hinted_domains)
        if alt_dom is not None:
            entity = alt_dom
            domain = entity["domain"]

    service = ACTIONS[action]["services"].get(domain)

    if service is not None and explicit_area and entity.get("area") and entity.get("area") != explicit_area:
        warnings.append("Device %s is in %r, but %r was named -- targeting area instead"
                        % (entity["entity_id"], entity.get("area"), explicit_area))
        return {
            "kind": "service_call", "domain": domain, "service": service,
            "target": {"area_id": area_id_of(entities, explicit_area)}, "data": {},
            "warnings": warnings,
            "confidence": round(min(action_conf, area_conf), 4),
        }

    if service is None:
        alt = _same_area_fallback(entities, entity, action, hinted_domains)
        if alt is not None:
            warnings.append("Action %r does not apply to %s -- using %s in the same area"
                            % (action, entity["entity_id"], alt["entity_id"]))
            entity = alt
            domain = entity["domain"]
            service = ACTIONS[action]["services"].get(domain)

    if service is None:
        warnings.append("Action %r is not defined for domain %r" % (action, domain))
        return {"kind": "unsupported", "domain": domain, "service": None,
                "target": {"entity_id": entity["entity_id"]}, "data": {},
                "warnings": warnings, "confidence": round(action_conf, 4)}

    data: Dict[str, Any] = {}
    if action in ("brightness", "heller") and domain == "light":
        b_score = answers.get("brightness", {}).get("score", 2.0)
        idx = int(round(b_score))
        idx = max(0, min(len(BRIGHTNESS_PCT) - 1, idx))
        pct = BRIGHTNESS_PCT[idx]
        if pct == 0:
            service = "turn_off"
        else:
            data["brightness_pct"] = pct
    elif action in ("temperature", "wärmer") and domain == "climate":
        t_score = answers.get("temperature", {}).get("score", 2.0)
        idx = int(round(t_score))
        idx = max(0, min(len(TEMP_VALUES) - 1, idx))
        data["temperature"] = TEMP_VALUES[idx]

    if answers.get("needs_confirmation", {}).get("noul", 0.0) > 0.6:
        warnings.append("Model suggests confirmation (%.2f)"
                        % answers["needs_confirmation"]["noul"])

    return {
        "kind": "service_call",
        "domain": domain,
        "service": service,
        "target": {"entity_id": entity["entity_id"]},
        "data": data,
        "warnings": warnings,
        "confidence": round(min(action_conf, device_conf), 4),
    }
