// Client-side reading of the served question set (REQUIREMENT_QUESTIONS_V1 section L). The API is the
// authority: it validates every save and submission. These helpers only decide what to show, mirror
// the API's rule that answers to hidden questions are dropped, and format answers for display.
import type { Question, QuestionSet } from "@p2b/contracts";

export type Answers = Record<string, unknown>;
export type FieldErrors = Record<string, string[]>;

export const NOT_SURE = "NOT_SURE";

export function isVisible(question: Question, answers: Answers): boolean {
  const rule = question.show_if;
  return !rule || answers[rule.key] === rule.equals;
}

/** Questions that hold an answer in `answers` (files are attached separately). */
export function answerable(question: Question): boolean {
  return question.type !== "files";
}

export function questionsByKey(set: QuestionSet): Map<string, Question> {
  return new Map(set.questions.map((question) => [question.key, question]));
}

/** The answers the API would keep: visible, answerable questions only. */
export function keptAnswers(set: QuestionSet, answers: Answers): Answers {
  const kept: Answers = {};
  for (const question of set.questions) {
    const value = answers[question.key];
    if (value !== undefined && answerable(question) && isVisible(question, answers)) {
      kept[question.key] = value;
    }
  }
  return kept;
}

export function isAnswered(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

export interface FormatLabels {
  yes: string;
  no: string;
  notSure: string;
}

/** A plain-text rendering of one answer, for the review step and the project page. */
export function formatAnswer(question: Question, value: unknown, labels: FormatLabels): string {
  if (!isAnswered(value)) return "";
  const optionLabel = (raw: unknown) =>
    question.options?.find((option) => option.value === raw)?.label ?? String(raw);
  const number = (raw: unknown) => (raw === NOT_SURE ? labels.notSure : String(raw));
  switch (question.type) {
    case "yes_no":
      return value === true ? labels.yes : labels.no;
    case "single_choice":
      return optionLabel(value);
    case "multi_choice":
      return (value as unknown[]).map(optionLabel).join(", ");
    case "ranking":
      return (value as unknown[]).map((raw, index) => `${index + 1}. ${optionLabel(raw)}`).join("; ");
    case "number_or_not_sure":
      return value === NOT_SURE ? (question.not_sure_label ?? labels.notSure) : String(value);
    case "setbacks": {
      const sides = value as Record<string, unknown>;
      return (question.sides ?? [])
        .map((side) => `${side.label}: ${number(sides[side.value])}`)
        .join(", ");
    }
    case "location": {
      const point = value as { lat: number; lng: number };
      return `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
    }
    default:
      return String(value);
  }
}

/** The section that holds the first question with an error, so the form can open it. */
export function firstSectionWithError(set: QuestionSet, errors: FieldErrors): number | null {
  const index = set.sections.findIndex((section) =>
    section.questions.some((key) => (errors[key] ?? []).length > 0),
  );
  return index === -1 ? null : index;
}

export interface ValidationMessages {
  required: string;
  number: string;
  min: (min: number) => string;
  max: (max: number) => string;
  maxLength: (max: number) => string;
  allSides: string;
  rankAll: (count: number) => string;
}

function numberProblem(question: Question, value: unknown, m: ValidationMessages): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return m.number;
  const min = question.min == null ? null : Number(question.min);
  const max = question.max == null ? null : Number(question.max);
  if (min !== null && value < min) return m.min(min);
  if (max !== null && value > max) return m.max(max);
  return null;
}

function problemsFor(question: Question, value: unknown, m: ValidationMessages): string[] {
  if (!isAnswered(value)) return question.required ? [m.required] : [];
  switch (question.type) {
    case "number": {
      const problem = numberProblem(question, value, m);
      return problem ? [problem] : [];
    }
    case "number_or_not_sure": {
      const problem = value === NOT_SURE ? null : numberProblem(question, value, m);
      return problem ? [problem] : [];
    }
    case "text":
      return question.max_length && String(value).length > question.max_length
        ? [m.maxLength(question.max_length)]
        : [];
    case "setbacks": {
      const sides = value as Record<string, unknown>;
      const problems = new Set<string>();
      for (const side of question.sides ?? []) {
        const raw = sides[side.value];
        if (raw === undefined) problems.add(m.allSides);
        else if (raw !== NOT_SURE) {
          const problem = numberProblem(question, raw, m);
          if (problem) problems.add(problem);
        }
      }
      return [...problems];
    }
    case "ranking": {
      const count = question.options?.length ?? 0;
      return (value as unknown[]).length === count ? [] : [m.rankAll(count)];
    }
    default:
      return [];
  }
}

/**
 * Immediate feedback for one step, generated from the question set's own rules (required, ranges,
 * lengths, every side, every rank). The API repeats every check and stays the authority.
 */
export function validateSection(
  set: QuestionSet,
  sectionIndex: number,
  answers: Answers,
  messages: ValidationMessages,
): FieldErrors {
  const byKey = questionsByKey(set);
  const errors: FieldErrors = {};
  for (const key of set.sections[sectionIndex]?.questions ?? []) {
    const question = byKey.get(key);
    if (!question || !answerable(question) || !isVisible(question, answers)) continue;
    const problems = problemsFor(question, answers[key], messages);
    if (problems.length > 0) errors[key] = problems;
  }
  return errors;
}

/**
 * True when every problem is an unanswered question: the draft can still be saved. The API rejects
 * partial setbacks, partial rankings and out-of-range values even in a draft.
 */
export function onlyUnanswered(errors: FieldErrors, messages: ValidationMessages): boolean {
  return Object.values(errors).every((problems) =>
    problems.every((problem) => problem === messages.required),
  );
}
