"use client";

// The project's concept floor plans, kept current while one is being laid out, and the owner's
// generate panel above them. A plan requested here joins the list at once as QUEUED; the list is
// read again (every 2.5 s, then every 10 s after a minute) until no plan is QUEUED or RUNNING.
// A VALID plan opens in the plan workspace; an INFEASIBLE one says why in plain words from the
// plan's own `infeasibility`; a FAILED one says what went wrong from its `failure_reason`.
import { MapIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GeneratePanel } from "@/components/plan2build/plan/plan-generate";
import { LoadingState } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { browserApi } from "@/lib/api/browser";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import {
  anyInFlight,
  failureText,
  generationLock,
  inFlight,
  infeasibilityView,
  mergePlans,
  pollDelay,
  type Infeasibility,
  type LockReason,
  type PlanSummary,
} from "@/lib/plan/generate";
import type { ProjectStatus } from "@/lib/project";

const t = getTranslator("Plan");
const status = getTranslator("Status");

export function FloorPlans({
  projectId,
  status: projectStatus,
  initial,
  isOwner: ownerFromApi,
  assistant,
}: {
  projectId: string;
  status: ProjectStatus;
  initial: PlanSummary[];
  isOwner: boolean | null;
  assistant: boolean | null;
}) {
  const [plans, setPlans] = useState<PlanSummary[]>(initial);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [reads, setReads] = useState(0);
  const [announcement, setAnnouncement] = useState("");
  // what the server said when asked, over what the page knew when it loaded
  const [isOwner, setIsOwner] = useState(ownerFromApi);
  const [currentStatus, setCurrentStatus] = useState<string>(projectStatus);
  const [rulesetBlocked, setRulesetBlocked] = useState(false);
  const current = useRef(plans);
  const pending = useRef<PlanSummary | null>(null);
  const since = useRef<number | null>(null);
  const [watched, setWatched] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    current.current = plans;
  }, [plans]);

  const reload = useCallback(async () => {
    const response = await browserApi
      .GET("/api/v1/projects/{project_id}/house-plans", { params: { path: { project_id: projectId } } })
      .catch(() => null);
    const data = response?.data;
    setReads((n) => n + 1);
    if (!data) {
      setRefreshFailed(true);
      return;
    }
    setRefreshFailed(false);
    const finished = data.items.find((plan) => {
      const was = current.current.find((p) => p.plan_id === plan.plan_id);
      return was && inFlight(was.state) && !inFlight(plan.state);
    });
    if (finished) {
      setAnnouncement(
        t("list.finished", { number: finished.sequence, state: status(`plan.${finished.state}`) }),
      );
    }
    if (pending.current && data.items.some((p) => p.plan_id === pending.current?.plan_id)) {
      pending.current = null;
    }
    setPlans(mergePlans(data.items, pending.current));
  }, [projectId]);

  // while a plan is QUEUED or RUNNING, read the list again after every read, failed or not
  const busy = anyInFlight(plans);
  useEffect(() => {
    if (!busy) {
      since.current = null;
      return;
    }
    since.current ??= Date.now();
    const timer = setTimeout(() => void reload(), pollDelay(Date.now() - since.current));
    return () => clearTimeout(timer);
  }, [busy, reads, reload]);

  const lock = generationLock({ isOwner, status: currentStatus, plans, rulesetBlocked });

  function onRequested(plan: PlanSummary) {
    pending.current = plan;
    setWatched((before) => new Set(before).add(plan.plan_id));
    setPlans((before) => mergePlans(before, plan));
  }

  function onLock(reason: LockReason, current?: string) {
    if (reason === "OWNER_ONLY") setIsOwner(false);
    else if (reason === "RULESET_NOT_PUBLISHED") setRulesetBlocked(true);
    else if (current) setCurrentStatus(current);
  }

  const newest = plans[0]?.plan_id;
  return (
    <div className="flex flex-col gap-4">
      <GeneratePanel
        projectId={projectId}
        lock={lock}
        assistant={assistant}
        onRequested={onRequested}
        onInProgress={() => void reload()}
        onLock={onLock}
      />
      <p role="status" className="sr-only">
        {announcement}
      </p>
      {refreshFailed && busy && <p className="text-sm text-muted-foreground">{t("list.refreshFailed")}</p>}
      {plans.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("list.empty")}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border" aria-label={t("list.title")}>
          {plans.map((plan) => (
            <PlanRow
              key={plan.plan_id}
              projectId={projectId}
              plan={plan}
              openWhy={plan.plan_id === newest || watched.has(plan.plan_id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

type Why =
  | { kind: "closed" }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "shown"; infeasibility: Infeasibility | null };

function PlanRow({ projectId, plan, openWhy }: { projectId: string; plan: PlanSummary; openWhy: boolean }) {
  const [why, setWhy] = useState<Why>({ kind: "closed" });
  const infeasible = plan.state === "INFEASIBLE";

  const load = useCallback(async () => {
    setWhy({ kind: "loading" });
    const response = await browserApi
      .GET("/api/v1/projects/{project_id}/house-plans/{plan_id}", {
        params: { path: { project_id: projectId, plan_id: plan.plan_id } },
      })
      .catch(() => null);
    const data = response?.data;
    setWhy(data ? { kind: "shown", infeasibility: data.infeasibility } : { kind: "error" });
  }, [projectId, plan.plan_id]);

  // the newest plan, or one requested here, says why at once; older ones on request
  const opened = useRef(false);
  useEffect(() => {
    if (!infeasible || !openWhy || opened.current) return;
    opened.current = true;
    void load();
  }, [infeasible, openWhy, load]);

  const view = why.kind === "shown" ? infeasibilityView(why.infeasibility) : null;
  const whyId = `why-${plan.plan_id}`;
  return (
    <li className="flex flex-col gap-3 p-3" data-state={plan.state}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{t("planNumber", { number: plan.sequence })}</span>
            <StatusBadge kind="plan" status={plan.state} />
          </div>
          <span className="text-sm text-muted-foreground">
            {t("list.requestedOn", { date: formatDate(plan.created_at) })}
          </span>
        </div>
        {plan.state === "VALID" && (
          <Button asChild variant="outline">
            <Link href={`/projects/${projectId}/designs/plans/${plan.plan_id}`}>
              <MapIcon aria-hidden="true" data-icon="inline-start" />
              {t("list.open")}
            </Link>
          </Button>
        )}
        {infeasible && (
          <Button
            type="button"
            variant="ghost"
            aria-expanded={why.kind !== "closed"}
            aria-controls={whyId}
            onClick={() => (why.kind === "closed" ? void load() : setWhy({ kind: "closed" }))}
          >
            {why.kind === "closed" ? t("list.why") : t("list.whyHide")}
          </Button>
        )}
      </div>
      {inFlight(plan.state) && <p className="text-sm text-muted-foreground">{t("list.working")}</p>}
      {plan.state === "FAILED" && (
        <p className="text-sm">
          {failureText(plan.failure_reason)} {t("list.failure.next")}
        </p>
      )}
      {infeasible && why.kind !== "closed" && (
        <div id={whyId} className="flex flex-col gap-2 rounded-md bg-muted p-3 text-sm">
          {why.kind === "loading" && <LoadingState label={t("list.whyLoading")} />}
          {why.kind === "error" && (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-destructive">{t("list.whyError")}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
                {t("list.why")}
              </Button>
            </div>
          )}
          {view && (
            <>
              <p className="font-medium">{view.headline}</p>
              {view.reasons.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-muted-foreground">{t("list.infeasible.reasonsTitle")}</p>
                  <ul className="list-disc pl-5">
                    {view.reasons.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
              {view.explanation && (
                <div className="flex flex-col gap-1">
                  <p className="text-muted-foreground">{t("list.infeasible.explanationTitle")}</p>
                  <p>{view.explanation}</p>
                </div>
              )}
              <p className="text-muted-foreground">{t("list.infeasible.next")}</p>
            </>
          )}
        </div>
      )}
    </li>
  );
}
