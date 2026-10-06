"""Requirement question sets as data (REQUIREMENT_QUESTIONS_V1, locked; IMPLEMENTATION_CONTRACT
section 3, rule 4). The definition lives in `requirement_question_sets`; this module only knows
the question *types*. A new question or option is a new set version, never a code change.

Answer formats by type:
- location: {"lat": number, "lng": number}
- text: string;  single_choice: option value;  multi_choice: list of distinct option values
- yes_no: boolean;  number: number
- number_or_not_sure: number, or the string "NOT_SURE"
- setbacks: {side: number or "NOT_SURE"} for every side
- ranking: every option value exactly once, most important first
- files: never an answer; files are attached to the project separately
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

NOT_SURE = "NOT_SURE"
QuestionType = Literal[
    "location", "text", "single_choice", "multi_choice", "yes_no", "number",
    "number_or_not_sure", "setbacks", "ranking", "files",
]  # fmt: skip


class Option(BaseModel):
    value: str
    label: str


class Condition(BaseModel):
    key: str
    equals: str | bool


class Question(BaseModel):
    key: str
    type: QuestionType
    label: str
    help: str | None = None
    required: bool
    options: list[Option] = Field(default_factory=list)
    sides: list[Option] = Field(default_factory=list)
    min: Decimal | None = None
    max: Decimal | None = None
    max_length: int | None = None
    multiline: bool = False
    not_sure_label: str | None = None
    max_files: int | None = None
    max_bytes: int | None = None
    accept: list[str] = Field(default_factory=list)
    show_if: Condition | None = None


class Section(BaseModel):
    key: str
    title: str
    questions: list[str]


class FlagRule(BaseModel):
    flag: str
    when: Condition


class QuestionSetDefinition(BaseModel):
    version: int
    locale: str
    sections: list[Section]
    questions: list[Question]
    review_flags: list[FlagRule]

    def by_key(self) -> dict[str, Question]:
        return {q.key: q for q in self.questions}


Errors = dict[str, list[str]]


def _visible(question: Question, answers: dict[str, Any]) -> bool:
    return question.show_if is None or answers.get(question.show_if.key) == question.show_if.equals


def _number_in_range(value: Any, question: Question) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return "Enter a number."
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return "Enter a number."
    if not number.is_finite():
        return "Enter a number."
    if question.min is not None and number < question.min:
        return f"Must be at least {question.min}."
    if question.max is not None and number > question.max:
        return f"Must be at most {question.max}."
    return None


def _check(question: Question, value: Any) -> str | None:
    """None if `value` is a well-formed answer to `question`, else a message."""
    allowed = {o.value for o in question.options}
    match question.type:
        case "location":
            if not isinstance(value, dict) or set(value) != {"lat", "lng"}:
                return "Mark the plot on the map."
            lat, lng = value["lat"], value["lng"]
            numeric = all(
                isinstance(v, int | float) and not isinstance(v, bool) for v in (lat, lng)
            )
            if not numeric or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                return "Mark the plot on the map."
            return None
        case "text":
            if not isinstance(value, str) or not value.strip():
                return "Enter a value."
            if question.max_length is not None and len(value) > question.max_length:
                return f"Use at most {question.max_length} characters."
            return None
        case "single_choice":
            return None if isinstance(value, str) and value in allowed else "Choose one option."
        case "multi_choice":
            valid = isinstance(value, list) and all(isinstance(v, str) for v in value)
            if not valid or len(set(value)) != len(value) or not set(value) <= allowed:
                return "Choose from the options."
            return None
        case "yes_no":
            return None if isinstance(value, bool) else "Choose yes or no."
        case "number":
            return _number_in_range(value, question)
        case "number_or_not_sure":
            return None if value == NOT_SURE else _number_in_range(value, question)
        case "setbacks":
            sides = {s.value for s in question.sides}
            if not isinstance(value, dict) or set(value) != sides:
                return "Give every side."
            for side_value in value.values():
                if side_value != NOT_SURE and _number_in_range(side_value, question):
                    return "Each side must be a number in feet, or Not sure."
            return None
        case "ranking":
            valid = isinstance(value, list) and all(isinstance(v, str) for v in value)
            if not valid or len(value) != len(allowed) or set(value) != allowed:
                return "Rank every item once."
            return None
        case "files":
            return "Files are uploaded separately."


def validate_answers(
    definition: QuestionSetDefinition, answers: dict[str, Any], *, complete: bool
) -> tuple[dict[str, Any], Errors]:
    """Check every given answer. With `complete`, also require every visible required question.
    Answers to questions hidden by a condition are dropped, so a stale "Other" text cannot
    survive a change of property type. Returns the cleaned answers and per-field errors."""
    questions = definition.by_key()
    errors: Errors = {}
    for key in answers:
        if key not in questions:
            errors.setdefault(key, []).append("Unknown question.")
    cleaned: dict[str, Any] = {}
    for key, question in questions.items():
        if key not in answers or answers[key] is None:
            continue
        if not _visible(question, answers):
            continue
        problem = _check(question, answers[key])
        if problem:
            errors.setdefault(key, []).append(problem)
        else:
            cleaned[key] = answers[key].strip() if question.type == "text" else answers[key]
    if complete:
        for key, question in questions.items():
            visible = _visible(question, cleaned)
            if question.required and visible and question.type != "files" and key not in cleaned:
                errors.setdefault(key, []).append("This answer is required.")
    return cleaned, errors


def review_flags(definition: QuestionSetDefinition, answers: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for rule in definition.review_flags:
        if answers.get(rule.when.key) == rule.when.equals and rule.flag not in flags:
            flags.append(rule.flag)
    return flags
