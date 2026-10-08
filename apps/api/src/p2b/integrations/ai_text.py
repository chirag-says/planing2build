"""Structured-output language model adapters (Checkpoint 4; `core.ai_text.TextProvider`).

- `gemini`: the Gemini API over HTTPS (`generateContent`) with a JSON response schema, so the
  model must answer in the schema's shape. Server-side only, with an API key from configuration;
  the model name is configuration too (models are retired often: the adapter is the stable
  part, as for images). Bounded timeout and attempts; transient failures retried, others not.
- `mock`: a deterministic interpreter of plain English for local development, tests, CI and the
  offline benchmark. It reads only the request text and the plan summary the caller sends, and
  answers in the same schema. Never allowed in production (settings guard).
- `none`: no provider: the assistant is unavailable.

No adapter logs the prompt, the answer or any credential."""

import asyncio
import json
import re
import time
from typing import Any

import httpx

from p2b.core.ai_text import TextProvider, TextProviderError, TextRequest, TextResult, TextUsage
from p2b.core.config import Settings

# ---------- Gemini ----------


def _inline(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema as a self-contained JSON Schema in the forms Gemini's structured output
    enforces: every `$ref` replaced by its definition; `oneOf` as `anyOf`; `const` as a one-value
    `enum`; pydantic's `discriminator`, `default` and `title` removed; and a one-value enum field
    (a union's tag, such as `action`) made required. Live validation (2026-10-08) showed the
    model ignoring the tag otherwise and inventing actions. Our own models still validate every
    answer exactly as strictly: this only tells the model the shape more plainly."""
    defs = schema.get("$defs", {})
    dropped = ("$defs", "title", "discriminator", "default")

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(v) for v in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in dropped:
                continue
            if key == "const":
                out["enum"] = [value]
            elif key == "oneOf":
                out["anyOf"] = walk(value)
            else:
                out[key] = walk(value)
        # a map keyed by an enum (setbacks by side): explicit properties, which the model
        # follows; `propertyNames` alone let it write "front" and "rear" (live, 2026-10-08)
        names = out.get("propertyNames")
        if (
            isinstance(names, dict)
            and names.get("enum")
            and isinstance(out.get("additionalProperties"), dict)
        ):
            out["properties"] = {n: out["additionalProperties"] for n in names["enum"]}
            out["additionalProperties"] = False
            del out["propertyNames"]
        properties = out.get("properties")
        if isinstance(properties, dict):
            tags = [
                k
                for k, v in properties.items()
                if isinstance(v, dict) and len(v.get("enum", ())) == 1
            ]
            if tags:
                out["required"] = list(dict.fromkeys([*out.get("required", []), *tags]))
        return out

    return walk(schema)  # type: ignore[no-any-return]


class GeminiTextProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.model = model
        self._key = api_key
        self._url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        self._timeout = httpx.Timeout(timeout_seconds, connect=10)
        self._attempts = attempts
        self._transport = transport

    @property
    def configured(self) -> bool:
        return True

    async def structured(self, request: TextRequest) -> TextResult:
        body = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": [{"text": request.user}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": _inline(request.schema),
            },
        }
        headers = {"x-goog-api-key": self._key, "x-request-id": request.request_id}
        started = time.monotonic()
        last: TextProviderError | None = None
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            for attempt in range(1, self._attempts + 1):
                try:
                    response = await client.post(self._url, json=body, headers=headers)
                except httpx.TimeoutException:
                    last = TextProviderError("the model timed out", kind="TIMEOUT", retryable=True)
                except httpx.HTTPError:
                    last = TextProviderError(
                        "the model is unreachable", kind="UNAVAILABLE", retryable=True
                    )
                else:
                    if response.status_code == 200:
                        return self._parse(response.json(), started, attempt)
                    retryable = response.status_code == 429 or response.status_code >= 500
                    last = TextProviderError(
                        f"the model answered {response.status_code}",
                        kind="UNAVAILABLE" if retryable else "REJECTED",
                        retryable=retryable,
                    )
                if not last.retryable or attempt == self._attempts:
                    break
                await asyncio.sleep(min(2.0, 0.5 * attempt))
        raise last or TextProviderError("the model gave no answer", kind="ERROR", retryable=False)

    def _parse(self, payload: dict[str, Any], started: float, attempt: int) -> TextResult:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            data = json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError):
            raise TextProviderError(
                "the model's answer is not JSON", kind="MALFORMED", retryable=False
            ) from None
        usage = payload.get("usageMetadata") or {}
        return TextResult(
            data=data,
            usage=TextUsage(usage.get("promptTokenCount"), usage.get("candidatesTokenCount")),
            duration_ms=int((time.monotonic() - started) * 1000),
            attempts=attempt,
        )


# ---------- deterministic mock ----------

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "single": 1, "a": 1, "an": 1}
_FACING = {
    "north-east": "NE", "north east": "NE", "northeast": "NE",
    "north-west": "NW", "north west": "NW", "northwest": "NW",
    "south-east": "SE", "south east": "SE", "southeast": "SE",
    "south-west": "SW", "south west": "SW", "southwest": "SW",
    "north": "N", "east": "E", "south": "S", "west": "W",
}  # fmt: skip
_TYPES = {
    "living": "LIVING", "hall": "LIVING", "dining": "DINING", "kitchen": "KITCHEN",
    "bedroom": "BEDROOM", "bed room": "BEDROOM", "toilet": "WC", "wc": "WC",
    "bathroom": "BATH_COMMON", "bath": "BATH_COMMON", "pooja": "PUJA", "puja": "PUJA",
    "prayer": "PUJA", "utility": "UTILITY", "store": "STORE", "passage": "PASSAGE",
}  # fmt: skip
_UNSUPPORTED = (
    (r"\b(floor|storey|story|g\+1|duplex|upstairs|first floor)\b", "ADD_FLOOR"),
    (r"\b(vastu)\b", "VASTU_CERTIFICATION"),
    (r"\b(beam|column|structural|load|foundation)\b", "STRUCTURAL_ENGINEERING"),
    (r"\b(permit|approval|sanction|legal|compliance)\b", "PERMIT_COMPLIANCE"),
    (r"\b(curved|circular|round|diagonal|angled|free ?form)\b", "FREE_SHAPE"),
    (r"\b(render|image|photo|3d|picture)\b", "IMAGES_OR_3D"),
    (r"\b(privacy|private)\b", "PRIVACY_REDESIGN"),
)


def _number(token: str) -> int | None:
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBERS.get(token)


def _requirement(text: str) -> dict[str, Any]:
    t = text.lower().replace(chr(0xD7), "x")  # the multiplication sign, as in 30x50
    out: dict[str, Any] = {"plot": {}, "unsupported": [], "clarifications": []}
    plot = re.search(r"(\d{2,3})\s*(?:ft|feet|')?\s*(?:by|x|\*)\s*(\d{2,3})", t)
    if plot:
        out["plot"]["width_ft"] = int(plot.group(1))
        out["plot"]["depth_ft"] = int(plot.group(2))
    for words, code in _FACING.items():
        if re.search(rf"\b{words}[- ]?facing\b|\bfacing {words}\b", t):
            out["plot"]["facing"] = code
            break
    setback = re.search(r"setbacks? (?:of )?(\d+(?:\.\d+)?)\s*(?:ft|feet)? all round", t)
    if setback:
        v = float(setback.group(1))
        out["plot"]["setbacks_ft"] = {"FRONT": v, "BACK": v, "LEFT": v, "RIGHT": v}
    bhk = re.search(r"(\d)\s*bhk", t)
    beds = re.search(r"(\w+)\s+bed(?:room)?s?\b", t)
    if bhk:
        out["bedrooms"] = int(bhk.group(1))
    elif beds and _number(beds.group(1)) is not None:
        out["bedrooms"] = _number(beds.group(1))
    baths = re.search(r"(\w+)\s+(?:bathrooms?|baths?|toilets?)\b", t)
    if baths and _number(baths.group(1)) is not None:
        out["bathrooms"] = _number(baths.group(1))
    attached = re.search(r"(\w+)\s+attached", t)
    if attached and _number(attached.group(1)) is not None:
        out["attached_bathrooms"] = _number(attached.group(1))
    elif "attached" in t and out.get("bedrooms"):
        out["attached_bathrooms"] = 1
    elif "bathrooms" in out or "bedrooms" in out:
        out["attached_bathrooms"] = 0
    if re.search(r"\b(pooja|puja|prayer)\b", t):
        out["pooja_room"] = True
    if "utility" in t:
        out["utility"] = True
    if re.search(r"open kitchen|kitchen open", t):
        out["kitchen"] = "OPEN"
    elif "kitchen" in t:
        out["kitchen"] = "CLOSED"
    if re.search(r"dining (?:in|with|inside) (?:the )?living|living[- ]dining", t):
        out["dining"] = "IN_LIVING"
    elif "dining" in t:
        out["dining"] = "SEPARATE"
    parking = re.search(r"(\w+)\s+cars?\b(?: parking)?", t)
    if re.search(r"no parking|without parking", t):
        out["parking"] = {"kind": "NONE", "spaces": 0}
    elif re.search(r"two[- ]wheeler|bike|scooter", t):
        out["parking"] = {"kind": "TWO_WHEELER", "spaces": 1}
    elif parking and _number(parking.group(1)) is not None:
        out["parking"] = {"kind": "CAR", "spaces": min(4, _number(parking.group(1)) or 1)}
    elif re.search(r"\bcar\b|parking", t):
        out["parking"] = {"kind": "CAR", "spaces": 1}
    if re.search(r"(large|big|spacious) living", t):
        out["living_size"] = "LARGE"
    if re.search(r"kitchen (?:close|near|next|adjacent) to (?:the )?dining", t):
        out["adjacencies"] = [{"a": "KITCHEN", "b": "DINING", "strength": "PREFERRED"}]
    if re.search(r"master bedroom.*private|private master", t):
        out["private_rooms"] = ["MASTER_BEDROOM"]
    if "vastu" in t:
        out["vastu"] = "WHERE_POSSIBLE"
    for pattern, topic in _UNSUPPORTED[:1]:
        if re.search(pattern, t):
            out["floors"] = 2
            out["unsupported"].append(topic)
    if re.search(r"vastu (?:certif|compliant|approved)", t):
        out["unsupported"].append("VASTU_CERTIFICATION")
    if "plot" not in t and not plot:
        out["clarifications"].append("What are the plot's width and depth?")
    return out


def _room_ref(t: str, rooms: list[dict[str, Any]], skip: str | None = None) -> str | None:
    """The plan room the words name: by its name first ("bedroom 3"), then by type."""
    candidates = sorted(rooms, key=lambda r: -len(r["name"]))
    for r in candidates:
        if r["id"] != skip and r["name"].lower() in t:
            return str(r["id"])
    if "master" in t:
        beds = [r for r in rooms if r["type"] == "BEDROOM" and r["id"] != skip]
        if beds:
            return str(max(beds, key=lambda r: r["area_m2"])["id"])
    for word, room_type in _TYPES.items():
        if re.search(rf"\b{word}", t):
            for r in rooms:
                if r["type"] == room_type and r["id"] != skip:
                    return str(r["id"])
    return None


def _edit(text: str, plan: dict[str, Any], failure: str | None) -> dict[str, Any]:
    t = text.lower()
    rooms = plan.get("rooms", [])
    for pattern, topic in _UNSUPPORTED:
        if re.search(pattern, t):
            return {"intent": {"action": "UNSUPPORTED", "topic": topic}}
    room = _room_ref(t, rooms)
    add = re.search(r"\badd (?:a |an |one )?([a-z ]+?)(?: room)?(?: in| to| at|$)", t)
    if add:
        word = add.group(1).strip()
        room_type = next((v for k, v in _TYPES.items() if k in word), None)
        if room_type is None:
            return {"intent": {"action": "UNSUPPORTED", "topic": "UNSUPPORTED_ROOM_TYPE"}}
        area = next(
            (
                code
                for words, code in (
                    ("forecourt", "FORECOURT"),
                    ("front", "FORECOURT"),
                    ("side yard", "SIDE_YARD"),
                    ("rear", "REAR_YARD"),
                    ("back", "REAR_YARD"),
                    ("court", "COURT"),
                )
                if words in t
            ),
            "ANY",
        )
        return {"intent": {"action": "ADD_ROOM", "room_type": room_type, "area": area}}
    if room is None:
        return {"intent": {"action": "CLARIFY", "question": "Which room do you mean?"}}
    change = re.search(r"(?:change|convert|turn|make) .+? (?:into|to|as) (?:a |an )?([a-z ]+)$", t)
    if change and not re.search(r"bigger|larger|smaller|wider|narrower", t):
        word = change.group(1).strip()
        room_type = next((v for k, v in _TYPES.items() if k in word), None)
        if room_type is None:
            return {"intent": {"action": "UNSUPPORTED", "topic": "UNSUPPORTED_ROOM_TYPE"}}
        return {"intent": {"action": "CHANGE_ROOM_TYPE", "room": room, "room_type": room_type}}
    rename = re.search(r"(?:rename|call) .+? (?:to|as) ['\"]?([a-z0-9' ]{1,60})['\"]?$", t)
    if rename:
        return {
            "intent": {
                "action": "RENAME_ROOM",
                "room": room,
                "name": rename.group(1).strip().title(),
            }
        }
    if re.search(r"\b(remove|delete|get rid of|drop)\b", t):
        return {"intent": {"action": "REMOVE_ROOM", "room": room}}
    opening = "DOOR" if "door" in t else "WINDOW" if "window" in t else None
    if opening and re.search(r"wider|bigger|larger|narrower|smaller", t):
        change_word = "WIDER" if re.search(r"wider|bigger|larger", t) else "NARROWER"
        return {
            "intent": {
                "action": "RESIZE_OPENING",
                "room": room,
                "opening": opening,
                "change": change_word,
            }
        }
    if opening and "move" in t:
        return {
            "intent": {
                "action": "MOVE_OPENING",
                "room": room,
                "opening": opening,
                "direction": "EITHER",
            }
        }
    toward = re.search(r"(?:closer|nearer|next) to (?:the )?(.+)$", t)
    if toward:
        target = _room_ref(toward.group(1), rooms, skip=room)
        if target is None:
            return {
                "intent": {"action": "CLARIFY", "question": "Which room should it move towards?"}
            }
        return {"intent": {"action": "MOVE_ROOM_TOWARD", "room": room, "target": target}}
    if re.search(r"bigger|larger|more space|increase|enlarge|expand", t):
        amount = "LOTS" if re.search(r"much|a lot|lot", t) else "MODERATE"
        if failure:  # the last interpretation could not be applied: ask for less
            amount = "SLIGHT"
        return {
            "intent": {"action": "RESIZE_ROOM", "room": room, "change": "LARGER", "amount": amount}
        }
    if re.search(r"smaller|reduce|shrink|decrease", t):
        amount = "SLIGHT" if failure else "MODERATE"
        return {
            "intent": {"action": "RESIZE_ROOM", "room": room, "change": "SMALLER", "amount": amount}
        }
    return {"intent": {"action": "CLARIFY", "question": "What would you like to change about it?"}}


class MockTextProvider:
    """Deterministic: the same request gives the same answer. `script` makes it answer with
    given raw values in turn (tests of malformed answers and repair)."""

    name = "mock"
    model = "mock-rules-v1"

    def __init__(self, script: list[Any] | None = None):
        self._script = list(script or [])
        self.calls: list[TextRequest] = []

    @property
    def configured(self) -> bool:
        return True

    async def structured(self, request: TextRequest) -> TextResult:
        self.calls.append(request)
        if self._script:
            item = self._script.pop(0)
            if isinstance(item, TextProviderError):
                raise item
            return TextResult(data=item, usage=TextUsage(0, 0), duration_ms=0, attempts=1)
        payload = json.loads(request.user)
        text = str(payload.get("request", ""))
        if request.task == "requirement":
            data = _requirement(text)
        else:
            data = _edit(text, payload.get("plan", {}), payload.get("previous_failure"))
        return TextResult(data=data, usage=TextUsage(0, 0), duration_ms=0, attempts=1)


class UnconfiguredTextProvider:
    name = "none"
    model = "none"

    @property
    def configured(self) -> bool:
        return False

    async def structured(self, request: TextRequest) -> TextResult:
        raise TextProviderError("no text model is configured", kind="UNAVAILABLE", retryable=False)


def build_text_provider(settings: Settings) -> TextProvider:
    if settings.ai_text_provider == "mock":
        return MockTextProvider()
    if (
        settings.ai_text_provider == "gemini"
        and settings.gemini_api_key is not None
        and settings.ai_text_model
    ):
        return GeminiTextProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.ai_text_model,
            base_url=settings.gemini_api_base,
            timeout_seconds=settings.ai_text_timeout_seconds,
            attempts=settings.ai_text_attempts,
        )
    return UnconfiguredTextProvider()
