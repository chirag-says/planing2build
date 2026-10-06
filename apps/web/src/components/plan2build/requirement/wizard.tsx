"use client";

// The requirement form (J06; REQUIREMENT_QUESTIONS_V1 section L), built entirely from the served
// question set: one step per section, then a review step. Each step is checked against the set's
// own rules, then saved as a draft with the requirement's version (optimistic locking); unanswered
// questions never cost the family what they did enter. Submission is confirmed, idempotent, and moves
// the project to SUBMITTED for operations review (B-01). The API validates everything again.
import type { FileView, Question, QuestionSet } from "@p2b/contracts";
import { ArrowLeftIcon, ArrowRightIcon, CircleCheckIcon, PencilIcon, SendIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { AnswerSummary } from "@/components/plan2build/answer-summary";
import { ConfirmationDialog } from "@/components/plan2build/confirmation-dialog";
import { FormActions } from "@/components/plan2build/form-actions";
import { LocationField } from "@/components/plan2build/requirement/location-field";
import type { MapTiles, Point } from "@/components/plan2build/requirement/plot-map";
import { QuestionField } from "@/components/plan2build/requirement/question-field";
import { RankingField } from "@/components/plan2build/requirement/ranking-field";
import { UploadsField } from "@/components/plan2build/requirement/uploads-field";
import { Notice } from "@/components/plan2build/states";
import { WizardProgress, type WizardLabels } from "@/components/plan2build/wizard-progress";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import {
  firstSectionWithError,
  isAnswered,
  isVisible,
  keptAnswers,
  onlyUnanswered,
  questionsByKey,
  validateSection,
  type Answers,
  type FieldErrors,
  type ValidationMessages,
} from "@/lib/questions";

const t = getTranslator("Requirement");
const common = getTranslator("Common");

const MESSAGES: ValidationMessages = {
  required: t("validation.required"),
  number: t("validation.number"),
  min: (min) => t("validation.min", { min }),
  max: (max) => t("validation.max", { max }),
  maxLength: (max) => t("validation.maxLength", { max }),
  allSides: t("validation.allSides"),
  rankAll: (count) => t("validation.rankAll", { count }),
};

const PROGRESS_LABELS: WizardLabels = {
  nav: t("stepsLabel"),
  step: (current, total) => t("step", { current, total }),
  done: (title) => t("stepDone", { title }),
  current: (title) => t("stepCurrent", { title }),
  todo: (title) => t("stepTodo", { title }),
};

interface Props {
  projectId: string;
  set: QuestionSet;
  initialAnswers: Answers;
  initialVersion: number;
  files: FileView[];
  tiles: MapTiles | null;
}

type Banner = { text: string; errors: FieldErrors } | null;

function errorFields(error: unknown): FieldErrors {
  const fields = (error as { error?: { details?: { fields?: FieldErrors } } })?.error?.details?.fields;
  return fields ?? {};
}

export function RequirementWizard({
  projectId,
  set,
  initialAnswers,
  initialVersion,
  files,
  tiles,
}: Props) {
  const router = useRouter();
  const byKey = questionsByKey(set);
  const reviewStep = set.sections.length;
  const stepTitles = [...set.sections.map((section) => section.title), t("review")];
  const [step, setStep] = useState(0);
  const [furthest, setFurthest] = useState(0);
  const [answers, setAnswers] = useState<Answers>(initialAnswers);
  const [version, setVersion] = useState(initialVersion);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<Banner>(null);
  const [busy, setBusy] = useState<"saving" | "submitting" | null>(null);
  const [dirty, setDirty] = useState(false);
  const [savedOnce, setSavedOnce] = useState(false);
  const [confirming, setConfirming] = useState(false);
  // The locality is filled from the pin unless the family has typed their own (R-3).
  const [suggestedLocality, setSuggestedLocality] = useState<string | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [localityMissing, setLocalityMissing] = useState(false);
  const submitKeys = useRef(new Map<number, string>());
  const heading = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    heading.current?.focus();
    window.scrollTo({ top: 0 });
  }, [step]);

  const setAnswer = useCallback((key: string, value: unknown) => {
    setAnswers((current) => {
      const next = { ...current };
      if (value === undefined) delete next[key];
      else next[key] = value;
      return next;
    });
    setErrors((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
    setDirty(true);
  }, []);

  function goTo(index: number) {
    setStep(index);
    setFurthest((current) => Math.max(current, index));
    setBanner(null);
  }

  async function pinMoved(point: Point) {
    setAnswer("location", point);
    setLookingUp(true);
    try {
      const { data } = await browserApi.GET("/api/v1/geo/locality", {
        params: { query: { lat: point.lat, lng: point.lng } },
      });
      const found = data?.locality ?? null;
      setLocalityMissing(!found);
      if (found) {
        setAnswers((current) => {
          const typed = current.locality;
          const replaceable = !isAnswered(typed) || typed === suggestedLocality;
          return replaceable ? { ...current, locality: found } : current;
        });
        setSuggestedLocality(found);
      }
    } finally {
      setLookingUp(false);
    }
  }

  function reportFailure(error: unknown, status: number) {
    const code = errorCode(error);
    if (code === "VALIDATION_ERROR") {
      const fields = errorFields(error);
      setErrors(fields);
      setBanner({ text: t("fixErrors"), errors: fields });
    } else if (code === "VERSION_CONFLICT") {
      setBanner({ text: t("conflict"), errors: {} });
    } else if (code === "STATE_CONFLICT") {
      router.push(`/projects/${projectId}`);
    } else if (code === "RATE_LIMITED" || status === 429) {
      setBanner({ text: t("errors.RATE_LIMITED"), errors: {} });
    } else {
      setBanner({ text: t("errors.default"), errors: {} });
    }
  }

  async function save(): Promise<boolean> {
    const { data, error, response } = await browserApi.PUT(
      "/api/v1/projects/{project_id}/requirement",
      {
        params: { path: { project_id: projectId } },
        body: { answers: keptAnswers(set, answers), version },
      },
    );
    if (data) {
      setVersion(data.version);
      setDirty(false);
      setSavedOnce(true);
      return true;
    }
    reportFailure(error, response.status);
    return false;
  }

  function showProblems(problems: FieldErrors) {
    setErrors(problems);
    setBanner({ text: t("fixErrors"), errors: problems });
  }

  async function saveAndContinue(event: FormEvent) {
    event.preventDefault();
    setBanner(null);
    const problems = validateSection(set, step, answers, MESSAGES);
    const blocked = Object.keys(problems).length > 0;
    setBusy("saving");
    try {
      // Keep whatever was entered when the only gap is an unanswered question.
      const saveable = !blocked || onlyUnanswered(problems, MESSAGES);
      if (saveable && (dirty || !blocked) && !(await save())) return;
      if (blocked) {
        showProblems(problems);
        return;
      }
      setErrors({});
      goTo(step + 1);
    } catch {
      setBanner({ text: t("errors.default"), errors: {} });
    } finally {
      setBusy(null);
    }
  }

  function requestSubmit() {
    const problems: FieldErrors = {};
    set.sections.forEach((_, index) =>
      Object.assign(problems, validateSection(set, index, answers, MESSAGES)),
    );
    if (Object.keys(problems).length > 0) {
      showProblems(problems);
      const section = firstSectionWithError(set, problems);
      if (section !== null) setStep(section);
      return;
    }
    setConfirming(true);
  }

  async function submit() {
    setConfirming(false);
    setBusy("submitting");
    setBanner(null);
    try {
      if (dirty && !(await save())) return;
      // One key per requirement version: a retry replays, a changed requirement is a new request.
      const key = submitKeys.current.get(version) ?? crypto.randomUUID();
      submitKeys.current.set(version, key);
      const { data, error, response } = await browserApi.POST(
        "/api/v1/projects/{project_id}/requirement/submit",
        {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": key } },
          body: { version },
        },
      );
      if (data) {
        setDirty(false);
        router.push(`/projects/${projectId}`);
        router.refresh();
        return;
      }
      reportFailure(error, response.status);
      const section = firstSectionWithError(set, errorFields(error));
      if (section !== null) setStep(section);
    } catch {
      setBanner({ text: t("errors.default"), errors: {} });
    } finally {
      setBusy(null);
    }
  }

  function renderQuestion(question: Question) {
    if (!isVisible(question, answers)) return null;
    const fieldErrors = errors[question.key];
    const value = answers[question.key];
    switch (question.type) {
      case "location":
        return (
          <LocationField
            key={question.key}
            question={question}
            value={(value as Point | undefined) ?? null}
            onChange={pinMoved}
            tiles={tiles}
            errors={fieldErrors}
          />
        );
      case "ranking":
        return (
          <RankingField
            key={question.key}
            question={question}
            value={(value as string[] | undefined) ?? []}
            onChange={(next) => setAnswer(question.key, next.length > 0 ? next : undefined)}
            errors={fieldErrors}
          />
        );
      case "files":
        return (
          <UploadsField
            key={question.key}
            question={question}
            projectId={projectId}
            initialFiles={files}
          />
        );
      default: {
        const description =
          question.key === "locality" && lookingUp
            ? t("locality.looking")
            : question.key === "locality" && localityMissing
              ? t("locality.none")
              : undefined;
        return (
          <QuestionField
            key={question.key}
            question={question}
            value={value}
            onChange={(next) => setAnswer(question.key, next)}
            errors={fieldErrors}
            description={description}
          />
        );
      }
    }
  }

  const bannerBlock = banner && (
    <Notice tone="error" live="assertive" title={banner.text}>
      {Object.keys(banner.errors).length > 0 && (
        <ul className="mt-1 list-disc pl-4">
          {Object.entries(banner.errors).map(([key, messages]) => (
            <li key={key}>
              <a href={`#q-${key}`}>{byKey.get(key)?.label ?? key}</a>: {messages.join(" ")}
            </li>
          ))}
        </ul>
      )}
    </Notice>
  );

  const saveState = (
    <span aria-live="polite" className="flex items-center gap-1.5">
      {dirty ? (
        t("unsaved")
      ) : savedOnce ? (
        <>
          <CircleCheckIcon aria-hidden="true" className="size-4 text-success" />
          {t("draftSaved")}
        </>
      ) : null}
    </span>
  );

  const stepHeading = (title: string) => (
    <h2
      id="step-heading"
      ref={heading}
      tabIndex={-1}
      className="font-heading text-xl font-semibold sm:text-2xl"
    >
      {title}
    </h2>
  );

  const back = step > 0 && (
    <Button type="button" variant="outline" size="lg" onClick={() => goTo(step - 1)}>
      <ArrowLeftIcon aria-hidden="true" data-icon="inline-start" />
      {common("back")}
    </Button>
  );

  return (
    <div className="flex flex-col gap-8">
      <WizardProgress
        steps={stepTitles}
        current={step}
        furthest={furthest}
        onSelect={goTo}
        labels={PROGRESS_LABELS}
      />

      {step === reviewStep ? (
        <section aria-labelledby="step-heading" className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            {stepHeading(t("review"))}
            <p className="text-base text-muted-foreground">{t("reviewIntro")}</p>
          </div>
          {bannerBlock}
          <AnswerSummary
            set={set}
            answers={answers}
            labels={{ yes: common("yes"), no: common("no"), notSure: common("notSure") }}
            notAnswered={t("notAnswered")}
            sectionAction={(index, title) => (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => goTo(index)}
                aria-label={`${t("edit")}: ${title}`}
              >
                <PencilIcon aria-hidden="true" />
                {t("edit")}
              </Button>
            )}
          />
          <FormActions sticky status={saveState}>
            {back}
            <Button type="button" size="lg" onClick={requestSubmit} disabled={busy !== null}>
              {busy === "submitting" ? <Spinner /> : <SendIcon aria-hidden="true" />}
              {busy === "submitting" ? t("submitting") : t("submit")}
            </Button>
          </FormActions>
          <ConfirmationDialog
            open={confirming}
            onOpenChange={setConfirming}
            title={t("submitConfirmTitle")}
            description={t("submitConfirmBody")}
            confirmLabel={t("submitConfirm")}
            cancelLabel={t("cancel")}
            onConfirm={submit}
          />
        </section>
      ) : (
        <form
          onSubmit={saveAndContinue}
          aria-labelledby="step-heading"
          className="flex flex-col gap-8"
          noValidate
        >
          {stepHeading(set.sections[step].title)}
          {bannerBlock}
          <div className="flex flex-col gap-10">
            {set.sections[step].questions.map((key) => {
              const question = byKey.get(key);
              return question ? renderQuestion(question) : null;
            })}
          </div>
          <FormActions sticky status={saveState}>
            {back}
            <Button type="submit" size="lg" disabled={busy !== null}>
              {busy === "saving" && <Spinner />}
              {busy === "saving" ? t("saving") : t("saveContinue")}
              {busy !== "saving" && <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />}
            </Button>
          </FormActions>
        </form>
      )}
    </div>
  );
}
