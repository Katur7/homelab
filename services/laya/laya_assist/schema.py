"""Question schema for Home Assistant tool calls.

Translates a voice command into an HA service call. Consists of two parts:
  * ENTITIES -- catalog of controllable items (key -> entity_id, area, domain)
  * build_questions() -- typed questions built from the catalog for laya
"""
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- Catalog

DEFAULT_AREAS = {
    "living_room": "Living room, couch, TV area",
    "kitchen": "Kitchen, dining area, stove",
    "bedroom": "Bedroom, bed",
    "bathroom": "Bathroom, shower",
    "office": "Office, study, desk",
    "hallway": "Hallway, corridor, entrance",
    "garden": "Garden, patio, balcony, outside",
}

DEFAULT_ENTITIES: Dict[str, Dict[str, str]] = {
    "light_living_room": {
        "name": "Living Room Ceiling Light",
        "entity_id": "light.living_room_ceiling", "area": "living_room", "domain": "light",
        "desc": "Ceiling light in the living room, living room lamp",
    },
    "light_kitchen": {
        "name": "Kitchen Light",
        "entity_id": "light.kitchen_ceiling", "area": "kitchen", "domain": "light",
        "desc": "Light in the kitchen, kitchen lamp",
    },
    "light_bedroom": {
        "name": "Bedside Lamp",
        "entity_id": "light.bedroom_bedside", "area": "bedroom", "domain": "light",
        "desc": "Bedside lamp, light in the bedroom",
    },
    "light_office": {
        "name": "Desk Lamp",
        "entity_id": "light.office_desk", "area": "office", "domain": "light",
        "desc": "Desk lamp, light in the office",
    },
    "climate_living_room": {
        "name": "Living Room Heating",
        "entity_id": "climate.living_room", "area": "living_room", "domain": "climate",
        "desc": "Thermostat and heating in the living room",
    },
    "climate_bedroom": {
        "name": "Bedroom Heating",
        "entity_id": "climate.bedroom", "area": "bedroom", "domain": "climate",
        "desc": "Thermostat and heating in the bedroom",
    },
    "cover_living_room": {
        "name": "Living Room Blinds",
        "entity_id": "cover.living_room_blinds", "area": "living_room", "domain": "cover",
        "desc": "Blinds, shutter, awning, curtain in the living room",
    },
    "tv_living_room": {
        "name": "TV",
        "entity_id": "media_player.living_room_tv", "area": "living_room", "domain": "media_player",
        "desc": "Television, TV in the living room",
    },
    "speaker_kitchen": {
        "name": "Kitchen Speaker",
        "entity_id": "media_player.kitchen_speaker", "area": "kitchen", "domain": "media_player",
        "desc": "Speaker, radio, music in the kitchen",
    },
    "coffee_machine": {
        "name": "Coffee Machine",
        "entity_id": "switch.kitchen_coffee_machine", "area": "kitchen", "domain": "switch",
        "desc": "Coffee machine, smart plug in the kitchen",
    },
    "vacuum": {
        "name": "Vacuum",
        "entity_id": "vacuum.roborock", "area": "hallway", "domain": "vacuum",
        "desc": "Robot vacuum cleaner",
    },
    "front_door": {
        "name": "Front Door",
        "entity_id": "lock.front_door", "area": "hallway", "domain": "lock",
        "desc": "Front door lock",
    },
}

# ---------------------------------------------------------------- Actions

ACTIONS: Dict[str, Dict[str, Any]] = {
    "on": {
        "desc": "turn the device on, start it, switch it on",
        "services": {"light": "turn_on", "switch": "turn_on", "media_player": "turn_on",
                     "climate": "turn_on", "vacuum": "start", "cover": "open_cover",
                     "lock": "unlock", "fan": "turn_on", "scene": "turn_on", "script": "turn_on"},
    },
    "off": {
        "desc": "turn the device off, stop it, switch it off",
        "services": {"light": "turn_off", "switch": "turn_off", "media_player": "turn_off",
                     "climate": "turn_off", "vacuum": "return_to_base",
                     "cover": "close_cover", "lock": "lock", "fan": "turn_off", "script": "turn_off"},
    },
    "toggle": {
        "desc": "invert or toggle the current state",
        "services": {"light": "toggle", "switch": "toggle", "media_player": "toggle",
                     "cover": "toggle", "fan": "toggle"},
    },
    "brightness": {
        "desc": "set a specific brightness level, dim or brighten a light",
        "services": {"light": "turn_on"},
    },
    "temperature": {
        "desc": "set a specific temperature, adjust heating or thermostat",
        "services": {"climate": "set_temperature"},
    },
    "open": {
        "desc": "open, raise, roll up, unlock",
        "services": {"cover": "open_cover", "lock": "unlock"},
    },
    "close": {
        "desc": "close, lower, roll down, lock",
        "services": {"cover": "close_cover", "lock": "lock"},
    },
    "query": {
        "desc": "only asking for the current state or status, not changing anything",
        "services": {},
    },
}

BRIGHTNESS_LEVELS = ["off / 0%", "very dim / 25%", "medium / 50%",
                     "bright / 75%", "maximum / 100%"]
BRIGHTNESS_PCT = [0, 25, 50, 75, 100]

TEMP_LEVELS = ["very cold / 16 degrees", "cool / 18 degrees", "normal / 20 degrees",
               "warm / 22 degrees", "very warm / 24 degrees"]
TEMP_VALUES = [16, 18, 20, 22, 24]


# ---------------------------------------------------------------- Questions

CONTEXT_QUESTIONS = ("device", "area")


def build_questions(entities: Optional[Dict[str, Dict[str, str]]] = None,
                    areas: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Builds the typed-question schema from an entity catalog."""
    entities = entities or DEFAULT_ENTITIES
    areas = areas or DEFAULT_AREAS

    device_crit = {k: v.get("desc") or v["entity_id"] for k, v in entities.items()}
    device_crit["unknown"] = "no specific device named or not in catalog"

    area_crit = dict(areas)
    area_crit["unknown"] = "no room or area named"

    return {
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
        "brightness": {
            "type": "score",
            "instructions": "What brightness level does `command` request, if it is about lights?",
            "criteria": BRIGHTNESS_LEVELS,
        },
        "temperature": {
            "type": "score",
            "instructions": "What temperature does `command` request, if it is about heating/climate?",
            "criteria": TEMP_LEVELS,
        },
        "is_query": {
            "type": "noul",
            "instructions": "Is `command` a status question?",
        },
        "needs_confirmation": {
            "type": "noul",
            "instructions": "Does `command` affect a lock, door, or security device?",
        },
    }


# ---------------------------------------------------------------- Toolcall

DOMAIN_IMPLYING = {"temperature", "brightness"}


def _same_area_fallback(entities: Dict[str, Dict[str, str]], entity: Dict[str, str],
                        action: str) -> Optional[Dict[str, str]]:
    """Finds a device in the same area whose domain supports the requested action."""
    if action not in DOMAIN_IMPLYING:
        return None
    area = entity.get("area")
    if not area:
        return None
    supported = ACTIONS[action]["services"]
    for cand in entities.values():
        if cand.get("area") == area and cand["domain"] in supported:
            return cand
    return None


def _fold(text: str) -> str:
    """Lowercase and normalize diacritics for matching command against room name."""
    out = text.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("å", "a"), ("æ", "ae"),
                 ("ø", "o"), ("ð", "d"), ("þ", "th"), ("ß", "ss"),
                 ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ý", "y")):
        out = out.replace(a, b)
    return out


def area_named(text: str, area_key: str, areas: Dict[str, str]) -> bool:
    """Does the room name actually appear in the command text?"""
    if not text:
        return False
    hay = _fold(text)
    label = areas.get(area_key, "") or area_key.replace("_", " ")
    return any(len(w) > 2 and w in hay for w in _fold(label).split())


def area_id_of(entities: Dict[str, Dict[str, str]], area_key: str) -> str:
    """Resolve the true HA area_id for our slug from the catalog."""
    for ent in entities.values():
        if ent.get("area") == area_key and ent.get("area_id"):
            return ent["area_id"]
    return area_key


def _area_instead_of_device(entity: Optional[Dict[str, str]], area_key: str,
                            area_conf: float, threshold: float,
                            text: str, areas: Dict[str, str]) -> bool:
    """Does the selected device contradict the confidently recognized room?"""
    if entity is None or not area_key or area_key in ("unknown", "unklar"):
        return False
    if area_conf < threshold or not area_named(text, area_key, areas):
        return False
    own_area = entity.get("area") or ""
    return bool(own_area) and own_area != area_key


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
    device_key = answers["device"]["choice"]
    device_conf = answers["device"]["confidence"]
    area_key = answers["area"]["choice"]
    area_conf = answers["area"]["confidence"]
    is_query = answers["is_query"]["noul"]

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
    if entity is None:
        if area_key not in ("unknown", "unklar") and area_conf >= threshold:
            warnings.append("No specific device matched, falling back to area %r" % area_key)
            domain = "homeassistant"
            service = "turn_on" if action in ("on", "open", "an", "hoch") else "turn_off"
            return {
                "kind": "service_call", "domain": domain, "service": service,
                "target": {"area_id": area_key}, "data": {},
                "warnings": warnings, "confidence": round(area_conf, 4),
            }
        warnings.append("Could not match any device -- clarification needed")
        return {"kind": "unresolved", "domain": None, "service": None, "target": {},
                "data": {}, "warnings": warnings,
                "confidence": round(min(action_conf, device_conf), 4)}

    domain = entity["domain"]
    service = ACTIONS[action]["services"].get(domain)

    if service is not None and _area_instead_of_device(entity, area_key, area_conf,
                                                       threshold, text, areas):
        warnings.append("Device %s is in %r, but %r was named -- targeting area instead"
                        % (entity["entity_id"], entity.get("area"), area_key))
        return {
            "kind": "service_call", "domain": domain, "service": service,
            "target": {"area_id": area_id_of(entities, area_key)}, "data": {},
            "warnings": warnings,
            "confidence": round(min(action_conf, area_conf), 4),
        }

    if service is None:
        alt = _same_area_fallback(entities, entity, action)
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
        idx = int(round(answers["brightness"]["score"]))
        idx = max(0, min(len(BRIGHTNESS_PCT) - 1, idx))
        pct = BRIGHTNESS_PCT[idx]
        if pct == 0:
            service = "turn_off"
        else:
            data["brightness_pct"] = pct
    elif action in ("temperature", "wärmer") and domain == "climate":
        idx = int(round(answers["temperature"]["score"]))
        idx = max(0, min(len(TEMP_VALUES) - 1, idx))
        data["temperature"] = TEMP_VALUES[idx]

    if answers["needs_confirmation"]["noul"] > 0.6:
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
