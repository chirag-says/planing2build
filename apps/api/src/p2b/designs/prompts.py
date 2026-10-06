"""From the submitted requirement to a provider prompt (Slice 3.1; F-08).

`sanitise` keeps only design facts whose values come from closed option sets or are numbers, so
free text (notes, "Tell us what you are building", locality), contact details, coordinates and
uploads can never reach a provider: anything not on the allowlist, or not a known option, is
dropped. A missing or "Not sure" answer is left out, never guessed. `render` turns the snapshot
into the prompt with a versioned template; the result is stored with the generation.
"""

import hashlib
import string
import uuid
from typing import Any

PROPERTY_TYPES = {
    "INDEPENDENT_HOUSE": "an independent house",
    "VILLA": "a villa",
    "MULTI_FLAT_OWN_PLOT": "a multi-flat residential building on its own plot",
}
FLOORS = {
    "G": "ground floor only",
    "G_PLUS_1": "ground plus one floor",
    "G_PLUS_2": "ground plus two floors",
    "G_PLUS_3": "ground plus three floors",
}
FACINGS = {
    "N": "North", "S": "South", "E": "East", "W": "West", "NE": "North-East", "NW": "North-West",
    "SE": "South-East", "SW": "South-West",
}  # fmt: skip
ROOM_COUNTS = {"1": "1", "2": "2", "3": "3", "4": "4", "5_PLUS": "5 or more"}
VASTU = {
    "MUST_FOLLOW": "designed to follow Vastu",
    "WHERE_POSSIBLE": "Vastu followed where possible",
}
TIERS = {"STANDARD": "standard", "PREMIUM": "premium", "LUXURY": "luxury"}
STYLES = {
    "MODERN": "modern", "CONTEMPORARY": "contemporary", "TRADITIONAL": "traditional",
    "MINIMALIST": "minimalist", "LUXURY": "luxury",
}  # fmt: skip
BUDGETS = {
    "UNDER_40L": "under 40 lakh rupees", "40L_60L": "40 to 60 lakh rupees",
    "60L_80L": "60 to 80 lakh rupees", "80L_1CR": "80 lakh to 1 crore rupees",
    "1CR_1_5CR": "1 to 1.5 crore rupees", "ABOVE_1_5CR": "above 1.5 crore rupees",
}  # fmt: skip
CHOICES: dict[str, dict[str, str]] = {
    "property_type": PROPERTY_TYPES, "floors": FLOORS, "facing": FACINGS,
    "bedrooms": ROOM_COUNTS, "bathrooms": ROOM_COUNTS, "vastu": VASTU, "quality_tier": TIERS,
    "style": STYLES, "budget_band": BUDGETS,
}  # fmt: skip
NUMBERS = ("plot_width_ft", "plot_depth_ft", "plot_area_sqft", "built_up_area_sqft")
FLAGS = ("plot_is_rectangular", "basement", "pooja_room", "car_parking")
# Setbacks shape the buildable envelope seen in an exterior view. Only sides answered with a
# number are kept; "Not sure" is left out, never guessed.
SETBACK_SIDES = {"FRONT": "front", "BACK": "back", "LEFT": "left", "RIGHT": "right"}
ALLOWED_KEYS = frozenset((*CHOICES, *NUMBERS, *FLAGS, "setbacks"))


def sanitise(answers: dict[str, Any]) -> dict[str, Any]:
    """The design facts the provider may see; everything else is dropped."""
    snapshot: dict[str, Any] = {}
    for key, options in CHOICES.items():
        value = answers.get(key)
        if isinstance(value, str) and value in options:
            snapshot[key] = value
    for key in NUMBERS:
        value = answers.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            snapshot[key] = value
    for key in FLAGS:
        value = answers.get(key)
        if isinstance(value, bool):
            snapshot[key] = value
    setbacks = answers.get("setbacks")
    if isinstance(setbacks, dict):
        given = {
            side: value
            for side, value in setbacks.items()
            if side in SETBACK_SIDES
            and isinstance(value, int | float)
            and not isinstance(value, bool)
            and value >= 0
        }
        if given:
            snapshot["setbacks"] = {side: given[side] for side in SETBACK_SIDES if side in given}
    if snapshot.get("plot_is_rectangular") is True:
        snapshot.pop("plot_area_sqft", None)
    elif snapshot.get("plot_is_rectangular") is False:
        snapshot.pop("plot_width_ft", None)
        snapshot.pop("plot_depth_ft", None)
    return snapshot


def _number(value: float) -> str:
    return f"{value:,.0f}"


def _feet(value: float) -> str:
    """Setbacks keep half feet (the form allows them): 3.5 stays 3.5."""
    return f"{value:g} ft"


def facts(snapshot: dict[str, Any]) -> str:
    """One plain sentence of facts. Only what the snapshot holds; nothing is filled in."""
    parts: list[str] = []
    building = PROPERTY_TYPES.get(snapshot.get("property_type", ""), "a house")
    tier = TIERS.get(snapshot.get("quality_tier", ""))
    parts.append(f"{tier}-finish {building.removeprefix('an ').removeprefix('a ')}" if tier
                 else building)  # fmt: skip
    if "floors" in snapshot:
        parts.append(FLOORS[snapshot["floors"]])
    if snapshot.get("basement") is True:
        parts.append("with a basement")
    if "plot_width_ft" in snapshot and "plot_depth_ft" in snapshot:
        parts.append(
            f"on a rectangular plot of about {_number(snapshot['plot_width_ft'])} by "
            f"{_number(snapshot['plot_depth_ft'])} feet"
        )
    elif "plot_area_sqft" in snapshot:
        parts.append(f"on an irregular plot of about {_number(snapshot['plot_area_sqft'])} sq ft")
    if "facing" in snapshot:
        parts.append(f"facing {FACINGS[snapshot['facing']]}")
    if "setbacks" in snapshot:
        sides = [
            f"{_feet(value)} {SETBACK_SIDES[side]}" for side, value in snapshot["setbacks"].items()
        ]
        parts.append("open setbacks of " + ", ".join(sides))
    if "built_up_area_sqft" in snapshot:
        parts.append(f"built-up area about {_number(snapshot['built_up_area_sqft'])} sq ft")
    rooms = [
        f"{ROOM_COUNTS[snapshot[key]]} {label}"
        for key, label in (("bedrooms", "bedrooms"), ("bathrooms", "bathrooms"))
        if key in snapshot
    ]
    if snapshot.get("pooja_room") is True:
        rooms.append("a pooja room")
    if snapshot.get("car_parking") is True:
        rooms.append("covered car parking")
    if rooms:
        parts.append(", ".join(rooms))
    if "vastu" in snapshot:
        parts.append(VASTU[snapshot["vastu"]])
    if "style" in snapshot:
        parts.append(f"{STYLES[snapshot['style']]} architectural style")
    if "budget_band" in snapshot:
        parts.append(f"construction budget {BUDGETS[snapshot['budget_band']]}")
    return "Project facts: " + "; ".join(parts) + "."


def render(body: str, snapshot: dict[str, Any]) -> str:
    """The template's `$facts` placeholder is the only substitution."""
    return string.Template(body).substitute(facts=facts(snapshot))


def seed_for(project_id: uuid.UUID, sequence: int) -> int:
    """A stable seed per generation, so the same request reproduces the same image."""
    digest = hashlib.sha256(f"{project_id}:{sequence}".encode()).digest()
    return int.from_bytes(digest[:4], "big")
