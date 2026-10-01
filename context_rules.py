import copy
import json
import re
from typing import Any


CAVE_CUES = (
    "gufa", "guha", "cave", "holy cave", "natural cave", "sacred cave",
    "garbhjoon", "garbh joon", "ardhkuwari cave", "adha kuwari cave",
)
TREK_CUES = (
    "trek", "trekking", "walking route", "on foot", "foot journey", "yatra route",
    "ban ganga", "charan paduka", "ardhkuwari", "sanjichhat", "bhairon",
)
SPECIAL_ACCESS_CUES = (
    "vip darshan", "special darshan", "sheeghra darshan", "garbh grah darshan",
    "sanctum access", "entry window", "darshan window", "special access",
)


def _resolve_ref(node: Any, root_schema: dict) -> Any:
    seen = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = node.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            break
        seen.add(ref)
        cur = root_schema
        try:
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                cur = cur[part]
            node = cur
        except Exception:
            break
    return node


def schema_has_path(schema: dict, path_parts: list[str]) -> bool:
    node: Any = schema
    for part in path_parts:
        node = _resolve_ref(node, schema)
        props = node.get("properties", {}) if isinstance(node, dict) else {}
        if part not in props:
            return False
        node = props[part]
    return True


def _schema_node(schema: dict, path_parts: list[str]) -> Any:
    node: Any = schema
    for part in path_parts:
        node = _resolve_ref(node, schema)
        props = node.get("properties", {}) if isinstance(node, dict) else {}
        if part not in props:
            return None
        node = props[part]
    return _resolve_ref(node, schema)


def _flatten_evidence_text(evidence) -> str:
    rows = []
    for page in evidence or []:
        for fact in page.get("facts", []) or []:
            rows.extend([
                str(fact.get("claim") or ""),
                str(fact.get("evidenceSnippet") or ""),
            ])
    return " ".join(rows).lower()


def _context_text(data: dict, evidence=None) -> str:
    gi = data.get("generalInfo") or {}
    rows = [
        gi.get("templeName"), gi.get("templeDescription"), gi.get("location"), gi.get("deity"),
        data.get("prerequisites"), data.get("transportation"), data.get("nearbyPlaces"),
        data.get("specialServices"), data.get("visitorRules"),
        _flatten_evidence_text(evidence),
    ]
    return json.dumps(rows, ensure_ascii=False, default=str).lower()


def has_literal_cave_context(data: dict, evidence=None) -> bool:
    text = _context_text(data, evidence)
    return any(cue in text for cue in CAVE_CUES)


def has_trek_context(data: dict, evidence=None) -> bool:
    text = _context_text(data, evidence)
    return any(cue in text for cue in TREK_CUES)


def has_special_access_context(data: dict, evidence=None) -> bool:
    text = _context_text(data, evidence)
    return any(cue in text for cue in SPECIAL_ACCESS_CUES)


def _looks_like_aarti(name: str) -> bool:
    return bool(re.search(r"\b(aarti|arti|arati)\b|आरती", (name or "").lower()))


def _looks_like_access_window(name: str) -> bool:
    low = (name or "").lower()
    return any(x in low for x in ("darshan", "entry", "access", "garbh", "sanctum", "window", "slot"))


def _is_restriction_facility(item: dict) -> bool:
    text = f"{item.get('name') or ''} {item.get('description') or ''} {item.get('extraInfo') or ''}".lower()
    restriction = any(x in text for x in (
        "prohibited", "not allowed", "restriction", "restricted", "ban", "photography",
        "mobile phone", "camera", "footwear", "dress code", "must not", "cannot carry",
    ))
    amenity = any(x in text for x in (
        "toilet", "water", "medical", "hospital", "cloak", "locker", "parking", "wheelchair",
        "food", "bhojanalaya", "restaurant", "counter", "help desk", "rest room", "restroom",
    ))
    return restriction and not amenity


def _is_historical_prerequisite(value: str) -> bool:
    low = (value or "").lower()
    history = any(x in low for x in (
        "believed", "legend", "mythology", "century", "reconstruction", "renovation", "architecture",
        "dynasty", "king ", "queen ", "maratha", "chalukya", "swayambhu", "idol of", "lingam",
    ))
    visitor_action = any(x in low for x in (
        "carry", "register", "registration", "book", "booking", "wear", "bring", "permit", "id proof",
        "reach", "report", "must", "required", "mandatory", "prepare", "avoid", "follow",
    ))
    return history and not visitor_action


def apply_context_awareness(data: dict, schema: dict, evidence=None) -> dict:
    """Deterministic semantic cleanup after model reconciliation.

    The function intentionally removes obviously inapplicable/mis-mapped content rather than
    inventing replacement facts. It is safe to run after every reconciliation pass.
    """
    out = copy.deepcopy(data)

    # 1) gufaTimings only applies to a literal cave/gufa with separate visitor timings.
    if schema_has_path(schema, ["templeTimings", "gufaTimings"]):
        tt = out.setdefault("templeTimings", {})
        gufa = tt.get("gufaTimings")
        if not has_literal_cave_context(out, evidence):
            node = _schema_node(schema, ["templeTimings", "gufaTimings"]) or {}
            types = node.get("type")
            allows_null = types == "null" or (isinstance(types, list) and "null" in types)
            props = node.get("properties", {}) if isinstance(node, dict) else {}
            if allows_null:
                tt["gufaTimings"] = None
            elif "applicable" in props or isinstance(gufa, dict):
                tt["gufaTimings"] = {
                    "applicable": False,
                    "reason": "No separate literal cave/gufa with visitor timings was identified in the available evidence.",
                    "morningOpen": None,
                    "morningClose": None,
                    "eveningOpen": None,
                    "eveningClose": None,
                }

    # 2) Keep only actual Aarti/Arti rituals inside aartis. Move access windows where supported.
    tt = out.get("templeTimings") or {}
    aartis = tt.get("aartis")
    if isinstance(aartis, list) and schema_has_path(schema, ["templeTimings", "specialAccessTimings"]):
        kept, moved = [], []
        for item in aartis:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            name = str(item.get("name") or "")
            if name and not _looks_like_aarti(name) and _looks_like_access_window(name):
                moved.append({
                    "name": item.get("name"),
                    "time": item.get("time"),
                    "appliesTo": item.get("name"),
                    "extraInfo": item.get("extraInfo"),
                })
            else:
                kept.append(item)
        if moved:
            tt["aartis"] = kept
            existing = tt.get("specialAccessTimings") or []
            seen = {(str(x.get("name")), str(x.get("time"))) for x in existing if isinstance(x, dict)}
            for item in moved:
                key = (str(item.get("name")), str(item.get("time")))
                if key not in seen:
                    existing.append(item)
                    seen.add(key)
            tt["specialAccessTimings"] = existing

    # 3) Restrictions are visitor rules, not facilities.
    if schema_has_path(schema, ["visitorRules"]) and isinstance(out.get("facilities"), list):
        kept, rules = [], list(out.get("visitorRules") or [])
        seen_rules = {(str(x.get("name")), str(x.get("description"))) for x in rules if isinstance(x, dict)}
        for item in out.get("facilities") or []:
            if isinstance(item, dict) and _is_restriction_facility(item):
                rule = {
                    "name": item.get("name"),
                    "description": item.get("description") or item.get("extraInfo"),
                    "appliesTo": item.get("location") or "Temple visit",
                    "mandatory": True,
                }
                key = (str(rule.get("name")), str(rule.get("description")))
                if key not in seen_rules:
                    rules.append(rule)
                    seen_rules.add(key)
            else:
                kept.append(item)
        out["facilities"] = kept
        out["visitorRules"] = rules

    # 4) Historical/mythological facts do not belong in prerequisites.
    if isinstance(out.get("prerequisites"), list):
        out["prerequisites"] = [
            x for x in out["prerequisites"]
            if not (isinstance(x, str) and _is_historical_prerequisite(x))
        ]

    # 5) Booking for an optional ritual/service is not mandatory entry registration.
    for item in out.get("registrationProcess") or []:
        if not isinstance(item, dict):
            continue
        text = f"{item.get('name') or ''} {item.get('description') or ''} {item.get('method') or ''}".lower()
        optional_service = any(x in text for x in (
            "vip", "bhasma aarti", "sandhya aarti", "shayan aarti", "puja", "pooja", "abhishek",
            "special darshan", "sheeghra",
        ))
        entry_registration = any(x in text for x in ("yatra registration", "rfid", "entry registration", "yatra access card"))
        if optional_service and not entry_registration:
            if "isMandatory" in item:
                item["isMandatory"] = False
            if "bookingRequired" in item and any(x in text for x in ("book", "booking", "reservation", "online")):
                item["bookingRequired"] = True

    return out


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    return False


def _path_is_contextually_relevant(path: str, root_data: dict, evidence=None) -> bool:
    clean = re.sub(r"\[\d+\]", "", path)
    if clean.startswith("templeTimings.gufaTimings") and not has_literal_cave_context(root_data, evidence):
        return False
    if clean == "generalInfo.trekPoints" and not has_trek_context(root_data, evidence):
        return False
    if clean == "templeTimings.specialAccessTimings" and not has_special_access_context(root_data, evidence):
        return False

    # A single continuous opening interval is represented by morningOpen -> eveningClose.
    # In that case the unused split points are intentionally null, not missing research targets.
    if clean in {"templeTimings.mandirTimings.morningClose", "templeTimings.mandirTimings.eveningOpen"}:
        mt = ((root_data.get("templeTimings") or {}).get("mandirTimings") or {})
        if mt.get("morningOpen") and mt.get("eveningClose") and not mt.get("morningClose") and not mt.get("eveningOpen"):
            return False
    return True


def find_missing_contextual(data: Any, path: str = "", root_data: dict | None = None, evidence=None) -> list[str]:
    """Find missing values while excluding contextually inapplicable fields."""
    if root_data is None:
        root_data = data if isinstance(data, dict) else {}
    missing: list[str] = []

    if data is None:
        if path and path != "slNo" and _path_is_contextually_relevant(path, root_data, evidence):
            missing.append(path)
        return missing

    if isinstance(data, str):
        if not data.strip() and path and path != "slNo" and _path_is_contextually_relevant(path, root_data, evidence):
            missing.append(path)
        return missing

    if isinstance(data, dict):
        if data.get("applicable") is False:
            if data.get("reason") is None and path:
                missing.append(path + ".reason")
            return missing
        if not data:
            if path and _path_is_contextually_relevant(path, root_data, evidence):
                missing.append(path)
            return missing
        for k, v in data.items():
            p = f"{path}.{k}" if path else k
            missing.extend(find_missing_contextual(v, p, root_data, evidence))
        return missing

    if isinstance(data, list):
        if not data:
            if path and path != "slNo" and _path_is_contextually_relevant(path, root_data, evidence):
                missing.append(path)
        else:
            for i, v in enumerate(data):
                missing.extend(find_missing_contextual(v, f"{path}[{i}]", root_data, evidence))
        return missing

    return missing


def parse_path(path: str) -> list[Any]:
    tokens: list[Any] = []
    for name, idx in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path):
        tokens.append(name if name else int(idx))
    return tokens


def get_path_value(data: Any, path: str) -> Any:
    cur = data
    for token in parse_path(path):
        try:
            cur = cur[token]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def set_path_if_missing(data: Any, path: str, value: Any) -> bool:
    tokens = parse_path(path)
    if not tokens:
        return False
    cur = data
    for token in tokens[:-1]:
        try:
            cur = cur[token]
        except (KeyError, IndexError, TypeError):
            return False
    last = tokens[-1]
    try:
        current = cur[last]
    except (KeyError, IndexError, TypeError):
        return False
    if not _is_empty(current) or _is_empty(value):
        return False
    cur[last] = value
    return True


def apply_internet_updates(data: dict, results: list[dict], allowed_paths: list[str]) -> tuple[dict, list[dict], list[dict]]:
    """Apply web-researched values only to paths that were explicitly missing before search."""
    out = copy.deepcopy(data)
    allowed = set(allowed_paths)
    applied, rejected = [], []
    for result in results or []:
        path = result.get("path")
        if path not in allowed:
            rejected.append({**result, "reason": "path was not requested"})
            continue
        try:
            value = json.loads(result.get("valueJson") or "null")
        except Exception:
            rejected.append({**result, "reason": "valueJson was not valid JSON"})
            continue
        if set_path_if_missing(out, path, value):
            applied.append(result)
        else:
            rejected.append({**result, "reason": "target was no longer missing or path was invalid"})
    return out, applied, rejected
