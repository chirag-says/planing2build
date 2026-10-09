"use client";

// Service needs, connection requests and engagements (Slice 3.4): the family's controls on the
// services page and the request screen, the professional's responses, and operations' actions.
// The API decides every rule (package, cap, listing, area, one active engagement); these controls
// send and show its answer, translating the `reason` of a refusal.
import type { components } from "@p2b/contracts";
import {
  CheckIcon,
  DownloadIcon,
  SendIcon,
  Share2Icon,
  UploadIcon,
  UserPlusIcon,
  XIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmationDialog } from "@/components/plan2build/confirmation-dialog";
import { CheckboxGroup, ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

type NeedState = components["schemas"]["NeedState"];
type DeclineReason = components["schemas"]["DeclineReason"];
type FileOut = components["schemas"]["FileOut"];

const t = getTranslator("Services");
const pro = getTranslator("Pro");
const ops = getTranslator("Ops");
const key = () => crypto.randomUUID();

const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";

type Failure = { error?: { code?: string; details?: { reason?: string } } } | undefined;

/** The `reason` of a 409, or the error code, as a key the screens translate. */
export function refusal(failure: unknown): string | null {
  const body = (failure as Failure)?.error;
  return body?.details?.reason ?? body?.code ?? null;
}

const FAMILY_ERRORS = new Set([
  "NOT_NEEDED", "ENGAGED", "DUPLICATE", "OPEN_LIMIT", "NOT_LISTED", "OUTSIDE_AREA", "NO_LOCATION",
  "SELF", "NOT_OWNER", "NOT_ELIGIBLE", "PACKAGE_REQUIRED", "IN_USE",
]);
const PRO_ERRORS = new Set(["EXPIRED", "ENGAGED", "PACKAGE_ENDED", "PROJECT_CLOSED", "NOT_LISTED"]);
const DECLINE_REASONS: DeclineReason[] = [
  "UNAVAILABLE", "OUTSIDE_SERVICE_AREA", "SCOPE_MISMATCH", "SCHEDULE_MISMATCH", "COMPLIANCE",
  "ALREADY_ENGAGED", "OTHER",
];

function familyError(failure: unknown): string {
  const code = refusal(failure);
  return code && FAMILY_ERRORS.has(code) ? t(`errors.${code as "ENGAGED"}`) : t("errors.default");
}

function proError(failure: unknown): string {
  const code = refusal(failure);
  return code && PRO_ERRORS.has(code)
    ? pro(`connections.errors.${code as "EXPIRED"}`)
    : pro("connections.errors.default");
}

/** Run one call; refresh the server-rendered page on success, keep the message on failure. */
function useAction(describe: (failure: unknown) => string) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(call: () => Promise<{ data?: unknown; error?: unknown }>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await call();
      if (data) {
        router.refresh();
        return true;
      }
      setError(describe(failure));
    } catch {
      setError(describe(undefined));
    } finally {
      setBusy(false);
    }
    return false;
  }
  return { busy, error, run, setError };
}

function ErrorNotice({ error }: { error: string | null }) {
  return error ? (
    <Notice tone="error" live="assertive">
      {error}
    </Notice>
  ) : null;
}

// --- the family: needs -----------------------------------------------------------------------

export function NeedControl({
  projectId,
  code,
  name,
  need,
  subtypes,
  chosen,
}: {
  projectId: string;
  code: string;
  name: string;
  need: NeedState;
  subtypes: Record<string, string>;
  chosen: string[];
}) {
  const action = useAction(familyError);
  const [state, setState] = useState<NeedState>(need);
  const [kinds, setKinds] = useState<string[]>(chosen);
  const [saved, setSaved] = useState(false);
  const changed = state !== need || kinds.join() !== chosen.join();

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaved(false);
    const ok = await action.run(() =>
      browserApi.PUT("/api/v1/projects/{project_id}/services/{code}/need", {
        params: { path: { project_id: projectId, code } },
        body: { state, subtypes: state === "NEEDED" ? kinds : [] },
      }),
    );
    setSaved(ok);
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-4" aria-label={`${t("need")} ${name}`}>
      <FormFieldset id={`need-${code}`} legend={t("need")} required>
        {({ legendId }) => (
          <ChoiceGroup
            id={`need-${code}`}
            labelledBy={legendId}
            columns={3}
            value={state}
            onValueChange={(value) => setState(value as NeedState)}
            options={(["NEEDED", "NOT_NEEDED", "UNDECIDED"] as const).map((value) => ({
              value,
              label: t(`needOptions.${value}`),
            }))}
          />
        )}
      </FormFieldset>
      {state === "NEEDED" && Object.keys(subtypes).length > 0 && (
        <FormFieldset id={`subtypes-${code}`} legend={t("subtypes")}>
          {() => (
            <CheckboxGroup
              id={`subtypes-${code}`}
              columns={3}
              value={kinds}
              onValueChange={setKinds}
              options={Object.entries(subtypes).map(([value, label]) => ({ value, label }))}
            />
          )}
        </FormFieldset>
      )}
      <ErrorNotice error={action.error} />
      {saved && !changed && (
        <Notice tone="success" live="polite">
          {t("saved")}
        </Notice>
      )}
      <Button type="submit" variant="outline" className="sm:self-start" disabled={!changed || action.busy}>
        {action.busy && <Spinner />}
        {t("saveNeed")}
      </Button>
    </form>
  );
}

// --- the family: requests --------------------------------------------------------------------

export function WithdrawButton({ projectId, connectionId, name }: { projectId: string; connectionId: string; name: string }) {
  const action = useAction(familyError);
  const [open, setOpen] = useState(false);
  const [requestKey] = useState(key);
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)} disabled={action.busy}
        aria-label={`${t("withdraw")}: ${name}`}>
        {action.busy ? <Spinner /> : <XIcon aria-hidden="true" />}
        {t("withdraw")}
      </Button>
      <ConfirmationDialog
        open={open}
        onOpenChange={setOpen}
        title={t("withdrawTitle")}
        description={t("withdrawBody")}
        confirmLabel={t("withdraw")}
        cancelLabel={t("keep")}
        onConfirm={() =>
          void action.run(() =>
            browserApi.POST("/api/v1/projects/{project_id}/connections/{connection_id}/withdraw", {
              params: {
                path: { project_id: projectId, connection_id: connectionId },
                header: { "Idempotency-Key": requestKey },
              },
            }),
          )
        }
      />
      <ErrorNotice error={action.error} />
    </div>
  );
}

export function ConnectionRequestForm({
  projectId,
  category,
  profileId,
  defaultName,
  hours,
}: {
  projectId: string;
  category: string;
  profileId: string;
  defaultName: string | null;
  hours: number;
}) {
  const router = useRouter();
  const [name, setName] = useState(defaultName ?? "");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [requestKey, setRequestKey] = useState(key);
  const complete = name.trim() && phone.trim();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!complete) return;
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      const { data, error: failure, response } = await browserApi.POST("/api/v1/projects/{project_id}/connections", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": requestKey } },
        body: {
          category,
          profile_id: profileId,
          contact_name: name.trim(),
          contact_phone: phone.trim(),
          site_address: address.trim() || null,
        },
      });
      if (data) {
        router.push(`/projects/${projectId}/services?sent=${category}#${category}`);
        return;
      }
      setRequestKey(key());
      if (response.status === 422) {
        const fields = (failure as { error?: { details?: { fields?: Record<string, string[]> } } })?.error?.details?.fields;
        setFieldErrors(fields ?? {});
      }
      setError(familyError(failure));
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <Notice tone="info">{t("connect.window", { hours })}</Notice>
      <FormField id="contact-name" label={t("connect.contactName")} required errors={fieldErrors.contact_name}>
        {(control) => (
          <Input {...control} autoComplete="name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
        )}
      </FormField>
      <FormField id="contact-phone" label={t("connect.contactPhone")} description={t("connect.phoneHelp")} required
        errors={fieldErrors.contact_phone}>
        {(control) => (
          <Input {...control} type="tel" autoComplete="tel" maxLength={24} value={phone}
            onChange={(e) => setPhone(e.target.value)} />
        )}
      </FormField>
      <FormField id="site-address" label={t("connect.siteAddress")} description={t("connect.siteAddressHelp")} errors={fieldErrors.site_address}>
        {(control) => (
          <Textarea {...control} rows={2} autoComplete="street-address" maxLength={300} value={address}
            onChange={(e) => setAddress(e.target.value)} />
        )}
      </FormField>
      <ErrorNotice error={error} />
      <Button type="submit" size="lg" className="sm:self-start" disabled={!complete || busy}>
        {busy ? <Spinner /> : <SendIcon aria-hidden="true" />}
        {t("connect.send")}
      </Button>
    </form>
  );
}

// --- the family: engagements -----------------------------------------------------------------

export function OutsideProfessionalDialog({ projectId, code, name }: { projectId: string; code: string; name: string }) {
  const action = useAction(familyError);
  const [open, setOpen] = useState(false);
  const [person, setPerson] = useState("");
  const [firm, setFirm] = useState("");
  const [contact, setContact] = useState("");
  const [requestKey, setRequestKey] = useState(key);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!person.trim()) return;
    const ok = await action.run(() =>
      browserApi.POST("/api/v1/projects/{project_id}/engagements", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": requestKey } },
        body: { category: code, name: person.trim(), firm: firm.trim() || null, contact: contact.trim() || null },
      }),
    );
    if (ok) setOpen(false);
    else setRequestKey(key());
  }

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)} aria-label={`${t("useOwn")}: ${name}`}>
        <UserPlusIcon aria-hidden="true" />
        {t("useOwn")}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>{t("outsideTitle")}</DialogTitle>
              <DialogDescription>{t("outsideHelp")}</DialogDescription>
            </DialogHeader>
            <FormField id={`outside-name-${code}`} label={t("outsideName")} required>
              {(c) => <Input {...c} maxLength={120} value={person} onChange={(e) => setPerson(e.target.value)} />}
            </FormField>
            <FormField id={`outside-firm-${code}`} label={t("outsideFirm")}>
              {(c) => <Input {...c} maxLength={160} value={firm} onChange={(e) => setFirm(e.target.value)} />}
            </FormField>
            <FormField id={`outside-contact-${code}`} label={t("outsideContact")}>
              {(c) => <Input {...c} maxLength={200} value={contact} onChange={(e) => setContact(e.target.value)} />}
            </FormField>
            <ErrorNotice error={action.error} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={!person.trim() || action.busy}>
                {action.busy && <Spinner />}
                {t("outsideSave")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Ending with a reason: the family, the professional or operations. */
function EndForm({
  id,
  label,
  reasonLabel,
  confirm,
  send,
  describe,
}: {
  id: string;
  label: string;
  reasonLabel: string;
  confirm: string;
  send: (reason: string, requestKey: string) => Promise<{ data?: unknown; error?: unknown }>;
  describe: (failure: unknown) => string;
}) {
  const action = useAction(describe);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [requestKey, setRequestKey] = useState(key);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return;
    const ok = await action.run(() => send(reason.trim(), requestKey));
    if (ok) setOpen(false);
    else setRequestKey(key());
  }

  if (!open) {
    return (
      <Button type="button" variant="outline" size="sm" className="self-start" onClick={() => setOpen(true)}>
        {label}
      </Button>
    );
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-md border border-border p-3">
      <FormField id={id} label={reasonLabel} required>
        {(c) => <Textarea {...c} rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      <ErrorNotice error={action.error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="destructive" disabled={!reason.trim() || action.busy}>
          {action.busy && <Spinner />}
          {confirm}
        </Button>
        <Button type="button" variant="outline" onClick={() => setOpen(false)}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

export function FamilyEndEngagement({ projectId, engagementId }: { projectId: string; engagementId: string }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">{t("endBody")}</p>
      <EndForm
        id={`end-${engagementId}`}
        label={t("end")}
        reasonLabel={t("endReason")}
        confirm={t("endConfirm")}
        describe={familyError}
        send={(reason, requestKey) =>
          browserApi.POST("/api/v1/projects/{project_id}/engagements/{engagement_id}/end", {
            params: { path: { project_id: projectId, engagement_id: engagementId }, header: { "Idempotency-Key": requestKey } },
            body: { reason },
          })
        }
      />
    </div>
  );
}

export function ShareFiles({
  projectId,
  engagementId,
  files,
  shared,
}: {
  projectId: string;
  engagementId: string;
  files: FileOut[];
  shared: string[];
}) {
  const action = useAction(familyError);
  const available = files.filter((f) => f.state === "AVAILABLE");
  const [chosen, setChosen] = useState<string[]>([]);
  const names = new Map(files.map((f) => [f.file_id, f.file_name]));
  const notShared = available.filter((f) => !shared.includes(f.file_id));

  async function share(event: FormEvent) {
    event.preventDefault();
    if (chosen.length === 0) return;
    const ok = await action.run(() =>
      browserApi.POST("/api/v1/projects/{project_id}/engagements/{engagement_id}/files", {
        params: { path: { project_id: projectId, engagement_id: engagementId } },
        body: { file_ids: chosen },
      }),
    );
    if (ok) setChosen([]);
  }

  return (
    <section aria-labelledby={`files-${engagementId}`} className="flex flex-col gap-3">
      <h4 id={`files-${engagementId}`} className="text-sm font-medium">{t("files")}</h4>
      <p className="text-sm text-muted-foreground">{t("filesHelp")}</p>
      {shared.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noFiles")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {shared.map((fileId) => (
            <li key={fileId} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="break-all">{names.get(fileId) ?? fileId}</span>
              <Button type="button" size="sm" variant="ghost" disabled={action.busy}
                aria-label={`${t("unshare")}: ${names.get(fileId) ?? ""}`}
                onClick={() =>
                  void action.run(() =>
                    browserApi.DELETE("/api/v1/projects/{project_id}/engagements/{engagement_id}/files/{file_id}", {
                      params: { path: { project_id: projectId, engagement_id: engagementId, file_id: fileId } },
                    }),
                  )
                }>
                {t("unshare")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {available.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noRequirementFiles")}</p>
      ) : (
        notShared.length > 0 && (
          <form onSubmit={share} className="flex flex-col gap-3">
            <FormFieldset id={`share-${engagementId}`} legend={t("share")}>
              {() => (
                <CheckboxGroup
                  id={`share-${engagementId}`}
                  columns={1}
                  value={chosen}
                  onValueChange={setChosen}
                  options={notShared.map((f) => ({ value: f.file_id, label: f.file_name }))}
                />
              )}
            </FormFieldset>
            <Button type="submit" variant="outline" size="sm" className="self-start" disabled={chosen.length === 0 || action.busy}>
              {action.busy ? <Spinner /> : <Share2Icon aria-hidden="true" />}
              {t("share")}
            </Button>
          </form>
        )
      )}
      <ErrorNotice error={action.error} />
    </section>
  );
}

// --- the family: quote-holder review intake --------------------------------------------------

type Uploaded = { fileId: string; name: string; state: string };
const SCANNING = ["PENDING_UPLOAD", "UPLOADED", "SCANNING"];

function put(url: string, headers: Record<string, string>, file: File): Promise<boolean> {
  return fetch(url, { method: "PUT", headers, body: file }).then(
    (response) => response.ok,
    () => false,
  );
}

export function QuoteReviewForm({
  projectId,
  categories,
}: {
  projectId: string;
  categories: { code: string; name: string }[];
}) {
  const router = useRouter();
  const [category, setCategory] = useState("");
  const [quotedBy, setQuotedBy] = useState("");
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<Uploaded[]>([]);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [requestKey, setRequestKey] = useState(key);
  const q = (name: "category" | "chooseCategory" | "quotedBy" | "note" | "files" | "filesHelp" | "uploading" | "checking" | "remove" | "send" | "sent" | "uploadFailed") =>
    t(`quote.${name}`);
  const ready = files.length > 0 && files.every((f) => f.state === "AVAILABLE");
  const complete = category && quotedBy.trim() && ready;

  // Each upload is scanned before use: poll its state until it is available or refused.
  useEffect(() => {
    const waiting = files.filter((f) => SCANNING.includes(f.state));
    if (waiting.length === 0) return;
    const timer = setTimeout(async () => {
      const next = await Promise.all(
        files.map(async (f) => {
          if (!SCANNING.includes(f.state)) return f;
          const { data } = await browserApi.GET("/api/v1/projects/{project_id}/quote-reviews/uploads/{file_id}", {
            params: { path: { project_id: projectId, file_id: f.fileId } },
          });
          return data ? { ...f, state: data.state } : f;
        }),
      );
      setFiles(next);
    }, 1500);
    return () => clearTimeout(timer);
  }, [files, projectId]);

  async function add(file: File) {
    setUploading(true);
    setError(null);
    try {
      const { data: ticket } = await browserApi.POST("/api/v1/projects/{project_id}/quote-reviews/uploads", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": key() } },
        body: { file_name: file.name.slice(0, 200), content_type: file.type, size_bytes: file.size },
      });
      if (!ticket || !(await put(ticket.upload_url, ticket.headers, file))) {
        setError(q("uploadFailed"));
        return;
      }
      const { data } = await browserApi.POST(
        "/api/v1/projects/{project_id}/quote-reviews/uploads/{file_id}/complete",
        { params: { path: { project_id: projectId, file_id: ticket.file.file_id } } },
      );
      if (!data) {
        setError(q("uploadFailed"));
        return;
      }
      setFiles([...files, { fileId: data.file_id, name: data.file_name, state: data.state }]);
    } finally {
      setUploading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!complete) return;
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/projects/{project_id}/quote-reviews", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": requestKey } },
        body: { category, quoted_by: quotedBy.trim(), note: note.trim() || null, file_ids: files.map((f) => f.fileId) },
      });
      if (data) {
        setSent(true);
        setFiles([]);
        setQuotedBy("");
        setNote("");
        setCategory("");
        setRequestKey(key());
        router.refresh();
        return;
      }
      setRequestKey(key());
      setError(familyError(failure));
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField id="quote-category" label={q("category")} required>
        {(c) => (
          <select {...c} className={SELECT} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{q("chooseCategory")}</option>
            {categories.map((option) => (
              <option key={option.code} value={option.code}>{option.name}</option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id="quote-by" label={q("quotedBy")} required>
        {(c) => <Input {...c} maxLength={120} value={quotedBy} onChange={(e) => setQuotedBy(e.target.value)} />}
      </FormField>
      <FormField id="quote-note" label={q("note")}>
        {(c) => <Textarea {...c} rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <FormField id="quote-file" label={q("files")} description={q("filesHelp")} required>
        {(c) => (
          <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" disabled={uploading || files.length >= 5}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void add(file);
            }} />
        )}
      </FormField>
      {uploading && (
        <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          {q("uploading")}
        </p>
      )}
      {files.length > 0 && (
        <ul className="flex flex-col gap-2 text-sm">
          {files.map((f) => (
            <li key={f.fileId} className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 break-all">
                {f.state === "AVAILABLE" ? (
                  <CheckIcon aria-hidden="true" className="size-4 text-success" />
                ) : SCANNING.includes(f.state) ? (
                  <Spinner />
                ) : (
                  <XIcon aria-hidden="true" className="size-4 text-destructive" />
                )}
                {f.name}
                {SCANNING.includes(f.state) && <span className="text-muted-foreground">({q("checking")})</span>}
                {!SCANNING.includes(f.state) && f.state !== "AVAILABLE" && (
                  <span className="text-destructive">({q("uploadFailed")})</span>
                )}
              </span>
              <Button type="button" size="sm" variant="ghost" aria-label={`${q("remove")}: ${f.name}`}
                onClick={() => setFiles(files.filter((x) => x.fileId !== f.fileId))}>
                {q("remove")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ErrorNotice error={error} />
      {sent && <Notice tone="success" live="polite">{q("sent")}</Notice>}
      <Button type="submit" className="sm:self-start" disabled={!complete || busy}>
        {busy ? <Spinner /> : <UploadIcon aria-hidden="true" />}
        {q("send")}
      </Button>
    </form>
  );
}

export function QuoteFileButton({ projectId, fileId, name }: { projectId: string; fileId: string; name: string }) {
  const [busy, setBusy] = useState(false);
  async function open() {
    setBusy(true);
    const { data } = await browserApi.GET("/api/v1/projects/{project_id}/quote-reviews/files/{file_id}/url", {
      params: { path: { project_id: projectId, file_id: fileId } },
    });
    setBusy(false);
    if (data) window.location.assign(data.url);
  }
  return (
    <Button type="button" size="sm" variant="ghost" onClick={() => void open()} disabled={busy} aria-label={`${pro("connections.download")}: ${name}`}>
      {busy ? <Spinner /> : <DownloadIcon aria-hidden="true" />}
      {name}
    </Button>
  );
}

// --- the professional ------------------------------------------------------------------------

export function ProRespond({ connectionId }: { connectionId: string }) {
  const accept = useAction(proError);
  const decline = useAction(proError);
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState<DeclineReason | "">("");
  const [note, setNote] = useState("");
  const [acceptKey, setAcceptKey] = useState(key);
  const [declineKey, setDeclineKey] = useState(key);
  const noteNeeded = reason === "OTHER";

  async function onAccept(event: FormEvent) {
    event.preventDefault();
    const ok = await accept.run(() =>
      browserApi.POST("/api/v1/pro/connections/{connection_id}/accept", {
        params: { path: { connection_id: connectionId }, header: { "Idempotency-Key": acceptKey } },
        body: { phone: phone.trim() || null },
      }),
    );
    if (!ok) setAcceptKey(key());
  }

  async function onDecline(event: FormEvent) {
    event.preventDefault();
    if (!reason || (noteNeeded && !note.trim())) return;
    const ok = await decline.run(() =>
      browserApi.POST("/api/v1/pro/connections/{connection_id}/decline", {
        params: { path: { connection_id: connectionId }, header: { "Idempotency-Key": declineKey } },
        body: { reason, note: note.trim() || null },
      }),
    );
    if (!ok) setDeclineKey(key());
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <form onSubmit={onAccept} className="flex flex-col gap-3" aria-labelledby="accept-heading">
        <h3 id="accept-heading" className="font-heading text-base font-medium">{pro("connections.accept")}</h3>
        <p className="text-sm text-muted-foreground">{pro("connections.acceptHelp")}</p>
        <FormField id="accept-phone" label={pro("connections.phone")}>
          {(c) => <Input {...c} type="tel" autoComplete="tel" maxLength={24} value={phone} onChange={(e) => setPhone(e.target.value)} />}
        </FormField>
        <ErrorNotice error={accept.error} />
        <Button type="submit" className="sm:self-start" disabled={accept.busy || decline.busy}>
          {accept.busy ? <Spinner /> : <CheckIcon aria-hidden="true" />}
          {pro("connections.accept")}
        </Button>
      </form>
      <form onSubmit={onDecline} className="flex flex-col gap-3" aria-labelledby="decline-heading">
        <h3 id="decline-heading" className="font-heading text-base font-medium">{pro("connections.decline")}</h3>
        <FormField id="decline-reason" label={pro("connections.declineReason")} required>
          {(c) => (
            <select {...c} className={SELECT} value={reason} onChange={(e) => setReason(e.target.value as DeclineReason)}>
              <option value="">{pro("connections.chooseReason")}</option>
              {DECLINE_REASONS.map((value) => (
                <option key={value} value={value}>{pro(`connections.reasons.${value}`)}</option>
              ))}
            </select>
          )}
        </FormField>
        <FormField id="decline-note" label={pro("connections.declineNote")} description={pro("connections.declineNoteHelp")}
          required={noteNeeded}>
          {(c) => <Textarea {...c} rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />}
        </FormField>
        <ErrorNotice error={decline.error} />
        <Button type="submit" variant="outline" className="sm:self-start"
          disabled={!reason || (noteNeeded && !note.trim()) || accept.busy || decline.busy}>
          {decline.busy ? <Spinner /> : <XIcon aria-hidden="true" />}
          {pro("connections.decline")}
        </Button>
      </form>
    </div>
  );
}

export function ProEndEngagement({ connectionId }: { connectionId: string }) {
  return (
    <EndForm
      id={`pro-end-${connectionId}`}
      label={pro("connections.end")}
      reasonLabel={pro("connections.endReason")}
      confirm={pro("connections.endConfirm")}
      describe={proError}
      send={(reason, requestKey) =>
        browserApi.POST("/api/v1/pro/connections/{connection_id}/end", {
          params: { path: { connection_id: connectionId }, header: { "Idempotency-Key": requestKey } },
          body: { reason },
        })
      }
    />
  );
}

/** The same control on the project workspace, through the engagement's own endpoint. */
export function ProEndEngagementById({ engagementId }: { engagementId: string }) {
  const e = getTranslator("Engagement");
  return (
    <EndForm
      id={`pro-end-${engagementId}`}
      label={e("end")}
      reasonLabel={e("endReason")}
      confirm={e("endConfirm")}
      describe={proError}
      send={(reason, requestKey) =>
        browserApi.POST("/api/v1/pro/engagements/{engagement_id}/end", {
          params: { path: { engagement_id: engagementId }, header: { "Idempotency-Key": requestKey } },
          body: { reason },
        })
      }
    />
  );
}

export function SharedFileButton({ connectionId, fileId, name }: { connectionId: string; fileId: string; name: string }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function open() {
    setBusy(true);
    setFailed(false);
    const { data } = await browserApi.GET("/api/v1/pro/connections/{connection_id}/files/{file_id}/url", {
      params: { path: { connection_id: connectionId, file_id: fileId } },
    });
    setBusy(false);
    if (data) window.location.assign(data.url);
    else setFailed(true);
  }
  return (
    <span className="flex flex-col items-end gap-1">
      <Button type="button" size="sm" variant="outline" onClick={() => void open()} disabled={busy}
        aria-label={`${pro("connections.download")}: ${name}`}>
        {busy ? <Spinner /> : <DownloadIcon aria-hidden="true" />}
        {pro("connections.download")}
      </Button>
      {failed && <span role="alert" className="text-xs text-destructive">{getTranslator("Common")("unavailable")}</span>}
    </span>
  );
}

// --- operations ------------------------------------------------------------------------------

function opsError(): string {
  return ops("engagements.error");
}

export function OpsWithdraw({ connectionId }: { connectionId: string }) {
  return (
    <EndForm
      id={`ops-withdraw-${connectionId}`}
      label={ops("engagements.withdraw")}
      reasonLabel={ops("engagements.reason")}
      confirm={ops("engagements.withdraw")}
      describe={opsError}
      send={(reason, requestKey) =>
        browserApi.POST("/api/v1/ops/connections/{connection_id}/withdraw", {
          params: { path: { connection_id: connectionId }, header: { "Idempotency-Key": requestKey } },
          body: { reason },
        })
      }
    />
  );
}

export function OpsEnd({ engagementId }: { engagementId: string }) {
  return (
    <EndForm
      id={`ops-end-${engagementId}`}
      label={ops("engagements.end")}
      reasonLabel={ops("engagements.reason")}
      confirm={ops("engagements.end")}
      describe={opsError}
      send={(reason, requestKey) =>
        browserApi.POST("/api/v1/ops/engagements/{engagement_id}/end", {
          params: { path: { engagement_id: engagementId }, header: { "Idempotency-Key": requestKey } },
          body: { reason },
        })
      }
    />
  );
}
