"use client";

// Review decisions for operations (rulings 2.1, 2.6, 2.7): accept (records the package-eligibility
// checklist, F-05, and creates the workspace once), request information (message the family sees)
// and cancel (reason the family sees). Shown only to the reviewer holding the claim; a NEEDS_INFO
// project can still be cancelled. Each action keeps one idempotency key until it succeeds, so a
// retry replays instead of acting twice.
import type { components, ProjectStatus } from "@p2b/contracts";
import { CircleCheckIcon, MessageSquareTextIcon, XCircleIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Ops");

type Action = "accept" | "ask" | "cancel";
type Eligibility = components["schemas"]["EligibilityOut"];
type Check = components["schemas"]["EligibilityCheckIn"];

function useDecision(projectId: string) {
  const router = useRouter();
  const keys = useRef(new Map<Action, string>());
  const [busy, setBusy] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: Action, text?: string, checks?: Check[]): Promise<boolean> {
    const key = keys.current.get(action) ?? crypto.randomUUID();
    keys.current.set(action, key);
    setBusy(action);
    setError(null);
    try {
      const params = {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": key } },
      };
      const { data, error: failure } =
        action === "accept"
          ? await browserApi.POST("/api/v1/ops/projects/{project_id}/accept", {
              ...params,
              body: { checks: checks ?? [] },
            })
          : action === "ask"
            ? await browserApi.POST("/api/v1/ops/projects/{project_id}/request-information", {
                ...params,
                body: { message: text ?? "" },
              })
            : await browserApi.POST("/api/v1/ops/projects/{project_id}/cancel", {
                ...params,
                body: { reason: text ?? "" },
              });
      if (data) {
        keys.current.delete(action);
        router.refresh();
        return true;
      }
      setError(
        errorCode(failure) === "STATE_CONFLICT"
          ? t("decision.errors.STATE_CONFLICT")
          : t("decision.errors.default"),
      );
    } catch {
      setError(t("decision.errors.default"));
    } finally {
      setBusy(null);
    }
    return false;
  }

  return { busy, error, run };
}

function MessageDialog({
  open,
  onOpenChange,
  id,
  title,
  label,
  help,
  submitLabel,
  destructive,
  busy,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  id: string;
  title: string;
  label: string;
  help: string;
  submitLabel: string;
  destructive?: boolean;
  busy: boolean;
  onSubmit: (text: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [missing, setMissing] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) {
      setMissing(true);
      return;
    }
    if (await onSubmit(text.trim())) {
      setText("");
      onOpenChange(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{help}</DialogDescription>
          </DialogHeader>
          <FormField
            id={id}
            label={label}
            required
            errors={missing ? [t("decision.required")] : undefined}
          >
            {(control) => (
              <Textarea
                {...control}
                rows={4}
                maxLength={2000}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setMissing(false);
                }}
              />
            )}
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("decision.back")}
            </Button>
            <Button type="submit" variant={destructive ? "destructive" : "default"} disabled={busy}>
              {busy && <Spinner />}
              {busy ? t("decision.working") : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The F-05 checklist: each item passed or not, with a note; accepting needs every item passed. */
function AcceptDialog({
  open,
  onOpenChange,
  eligibility,
  busy,
  onAccept,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  eligibility: Eligibility;
  busy: boolean;
  onAccept: (checks: Check[]) => Promise<boolean>;
}) {
  const [outcomes, setOutcomes] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const allPassed = eligibility.items.every((item) => outcomes[item.id] === "PASSED");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!allPassed) return;
    const checks = eligibility.items.map((item) => ({
      item_id: item.id,
      outcome: "PASSED" as const,
      note: notes[item.id] ?? "",
    }));
    if (await onAccept(checks)) onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false} className="max-h-[90vh] overflow-y-auto">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{t("decision.acceptTitle")}</DialogTitle>
            <DialogDescription>{t("decision.acceptBody")}</DialogDescription>
          </DialogHeader>
          <p className="text-sm font-medium">
            {t("eligibility.intro", { version: eligibility.checklist_version ?? 0 })}
          </p>
          {eligibility.items.map((item) => (
            <div key={item.id} className="flex flex-col gap-2 rounded-md border border-border p-3">
              <FormFieldset id={`eligibility-${item.id}`} legend={item.label} required>
                {({ legendId }) => (
                  <ChoiceGroup
                    id={`eligibility-${item.id}`}
                    labelledBy={legendId}
                    value={outcomes[item.id]}
                    onValueChange={(value) => setOutcomes((all) => ({ ...all, [item.id]: value }))}
                    options={[
                      { value: "PASSED", label: t("eligibility.passed") },
                      { value: "FAILED", label: t("eligibility.failed") },
                    ]}
                  />
                )}
              </FormFieldset>
              {item.help && <p className="text-xs text-muted-foreground">{item.help}</p>}
              <FormField id={`eligibility-note-${item.id}`} label={t("eligibility.note")}>
                {(control) => (
                  <Input
                    {...control}
                    maxLength={1000}
                    value={notes[item.id] ?? ""}
                    onChange={(e) => setNotes((all) => ({ ...all, [item.id]: e.target.value }))}
                  />
                )}
              </FormField>
            </div>
          ))}
          {!allPassed && <p className="text-sm text-muted-foreground">{t("eligibility.allNeeded")}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t("decision.back")}
            </Button>
            <Button type="submit" disabled={busy || !allPassed}>
              {busy && <Spinner />}
              {busy ? t("decision.working") : t("decision.accept")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function DecisionPanel({
  projectId,
  status,
  claimedByMe,
  eligibility,
}: {
  projectId: string;
  status: ProjectStatus;
  claimedByMe: boolean;
  eligibility: Eligibility;
}) {
  const { busy, error, run } = useDecision(projectId);
  const [confirming, setConfirming] = useState(false);
  const [asking, setAsking] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const canDecide = status === "SUBMITTED" && claimedByMe;
  const canCancel = canDecide || status === "NEEDS_INFO";

  if (!canCancel) {
    return status === "SUBMITTED" ? (
      <p className="text-sm text-muted-foreground">{t("decision.claimFirst")}</p>
    ) : null;
  }

  return (
    <div className="flex flex-col gap-3">
      {error && (
        <Notice tone="error" live="assertive">
          {error}
        </Notice>
      )}
      {canDecide && (
        <>
          <Button type="button" onClick={() => setConfirming(true)} disabled={busy !== null}>
            {busy === "accept" ? <Spinner /> : <CircleCheckIcon aria-hidden="true" />}
            {busy === "accept" ? t("decision.working") : t("decision.accept")}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setAsking(true)}
            disabled={busy !== null}
          >
            <MessageSquareTextIcon aria-hidden="true" />
            {t("decision.ask")}
          </Button>
        </>
      )}
      <Button
        type="button"
        variant="destructive"
        onClick={() => setCancelling(true)}
        disabled={busy !== null}
      >
        <XCircleIcon aria-hidden="true" />
        {t("decision.cancel")}
      </Button>

      <AcceptDialog
        open={confirming}
        onOpenChange={setConfirming}
        eligibility={eligibility}
        busy={busy === "accept"}
        onAccept={(checks) => run("accept", undefined, checks)}
      />
      <MessageDialog
        open={asking}
        onOpenChange={setAsking}
        id="ask-message"
        title={t("decision.askTitle")}
        label={t("decision.askLabel")}
        help={t("decision.askHelp")}
        submitLabel={t("decision.askSend")}
        busy={busy === "ask"}
        onSubmit={(text) => run("ask", text)}
      />
      <MessageDialog
        open={cancelling}
        onOpenChange={setCancelling}
        id="cancel-reason"
        title={t("decision.cancelTitle")}
        label={t("decision.cancelLabel")}
        help={t("decision.cancelHelp")}
        submitLabel={t("decision.cancel")}
        destructive
        busy={busy === "cancel"}
        onSubmit={(text) => run("cancel", text)}
      />
    </div>
  );
}
