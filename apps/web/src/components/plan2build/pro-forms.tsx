"use client";

// The professional's own forms (Slice 3.2): add a category, the profile, a category's evidence and
// submission, hiding and showing a listing, and the portfolio. The API decides everything (what is
// missing, what is locked, what may be submitted); these forms send and show what it says. Files go
// straight to storage on a presigned URL, then through the same checks as every upload.
import type { components } from "@p2b/contracts";
import { EyeIcon, EyeOffIcon, PlusIcon, SendIcon, Trash2Icon, UploadIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { FileRow } from "@/components/plan2build/file-row";
import type { MapTiles, Point } from "@/components/plan2build/requirement/plot-map";
import { LocationField } from "@/components/plan2build/requirement/location-field";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type Dashboard = components["schemas"]["OwnDashboardOut"];
type Category = components["schemas"]["OwnCategoryOut"];
type CategoryOption = components["schemas"]["CategoryOut"];
type Purpose = "VERIFICATION_EVIDENCE" | "PORTFOLIO";

const t = getTranslator("Pro");
const key = () => crypto.randomUUID();
const IN_PROGRESS = ["UPLOADED", "SCANNING"];
const POLL_MS = 2000;
const POLL_LIMIT = 60;

/** Re-read the page while any listed file is still being scanned, as the requirement uploads do. */
function useRefreshWhileScanning(states: (string | undefined)[]) {
  const router = useRouter();
  const [polls, setPolls] = useState(0);
  const scanning = states.some((state) => state !== undefined && IN_PROGRESS.includes(state));
  useEffect(() => {
    if (!scanning || polls >= POLL_LIMIT) return;
    const timer = setTimeout(() => {
      router.refresh();
      setPolls((count) => count + 1);
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [scanning, polls, router]);
}

function put(url: string, headers: Record<string, string>, file: File): Promise<boolean> {
  return fetch(url, { method: "PUT", headers, body: file }).then(
    (response) => response.ok,
    () => false,
  );
}

/** Upload one file for a purpose; the file id, or null when any step fails. */
async function uploadFile(file: File, purpose: Purpose): Promise<string | null> {
  const { data: ticket } = await browserApi.POST("/api/v1/pro/uploads", {
    body: { purpose, file_name: file.name.slice(0, 200), content_type: file.type, size_bytes: file.size },
    params: { header: { "Idempotency-Key": key() } },
  });
  if (!ticket || !(await put(ticket.upload_url, ticket.headers, file))) return null;
  const { data } = await browserApi.POST("/api/v1/pro/uploads/{file_id}/complete", {
    params: { path: { file_id: ticket.file.file_id } },
  });
  return data ? data.file_id : null;
}

export function AddCategoryForm({ options }: { options: CategoryOption[] }) {
  const router = useRouter();
  const [code, setCode] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  async function add(event: FormEvent) {
    event.preventDefault();
    if (!code) return;
    setBusy(true);
    setError(false);
    const { data } = await browserApi.POST("/api/v1/pro/categories", {
      body: { category: code, subtypes: [] },
      params: { header: { "Idempotency-Key": key() } },
    });
    setBusy(false);
    if (data) router.push(`/categories/${code}`);
    else setError(true);
  }
  return (
    <form onSubmit={add} className="flex flex-col gap-4">
      <FormFieldset id="new-category" legend={t("dashboard.addLabel")} legendSize="label" required>
        {({ legendId }) => (
          <ChoiceGroup
            id="new-category"
            labelledBy={legendId}
            value={code}
            onValueChange={setCode}
            options={options.map((o) => ({ value: o.code, label: o.name }))}
          />
        )}
      </FormFieldset>
      {error && <Notice tone="error" live="assertive">{t("category.error")}</Notice>}
      <Button type="submit" disabled={!code || busy} className="sm:self-start">
        {busy ? <Spinner /> : <PlusIcon aria-hidden="true" />}
        {busy ? t("dashboard.adding") : t("dashboard.addButton")}
      </Button>
    </form>
  );
}

export function ProfileForm({ data, tiles }: { data: Dashboard; tiles: MapTiles | null }) {
  const router = useRouter();
  const profile = data.profile;
  const [values, setValues] = useState({
    display_name: profile.display_name ?? "",
    firm_name: profile.firm_name ?? "",
    bio: profile.bio ?? "",
    years_experience: profile.years_experience?.toString() ?? "",
    team_size: profile.team_size?.toString() ?? "",
    base_locality: profile.base_locality ?? "",
    service_radius_km: profile.service_radius_km?.toString() ?? "",
  });
  const [point, setPoint] = useState<Point | null>(profile.base_point ?? null);
  const [state, setState] = useState<"idle" | "busy" | "saved" | "error">("idle");
  const set = (name: keyof typeof values) => (value: string) =>
    setValues((current) => ({ ...current, [name]: value }));
  const number = (value: string) => (value.trim() === "" ? null : Number(value));

  async function save(event: FormEvent) {
    event.preventDefault();
    setState("busy");
    const body: components["schemas"]["ProfileUpdateIn"] = {
      bio: values.bio,
      years_experience: number(values.years_experience),
      team_size: number(values.team_size),
      base_locality: values.base_locality,
      base_point: point,
      service_radius_km: number(values.service_radius_km),
    };
    if (!profile.names_locked) {
      body.display_name = values.display_name;
      body.firm_name = values.firm_name;
    }
    const { data: saved } = await browserApi.PATCH("/api/v1/pro/profile", { body });
    setState(saved ? "saved" : "error");
    if (!saved) return;
    // Onboarding ends with the last required field: on to the dashboard, where the rail
    // continues with the category. Otherwise stay, with the saved values.
    if (profile.missing.length > 0 && saved.profile.missing.length === 0) {
      router.push("/");
    }
    router.refresh();
  }

  const text = (name: keyof typeof values, label: string, required = false, disabled = false) => (
    <FormField id={name} label={label} required={required}
      description={disabled ? t("profile.namesLocked") : undefined}>
      {(control) => (
        <Input {...control} value={values[name]} disabled={disabled}
          onChange={(e) => set(name)(e.target.value)} />
      )}
    </FormField>
  );
  const numeric = (name: keyof typeof values, label: string, required = false) => (
    <FormField id={name} label={label} required={required}>
      {(control) => (
        <Input {...control} type="number" inputMode="numeric" min={0} value={values[name]}
          onChange={(e) => set(name)(e.target.value)} className="sm:max-w-40" />
      )}
    </FormField>
  );

  return (
    <form onSubmit={save} className="flex flex-col gap-6">
      {profile.missing.length > 0 && (
        <Notice tone="info">
          {t("profile.missing", {
            fields: profile.missing
              .map((f) => t(`profile.fields.${f as "display_name"}`))
              .join(", "),
          })}
        </Notice>
      )}
      {text("display_name", t("profile.displayName"), true, profile.names_locked)}
      {text("firm_name", t("profile.firmName"), false, profile.names_locked)}
      <FormField id="bio" label={t("profile.bio")} required>
        {(control) => (
          <Textarea {...control} rows={4} maxLength={2000} value={values.bio}
            onChange={(e) => set("bio")(e.target.value)} />
        )}
      </FormField>
      {numeric("years_experience", t("profile.years"), true)}
      {numeric("team_size", t("profile.teamSize"))}
      {text("base_locality", t("profile.locality"), true)}
      <LocationField
        question={{ key: "base_point", label: t("profile.base"), required: true }}
        value={point}
        onChange={setPoint}
        tiles={tiles}
      />
      <p className="-mt-4 text-base text-muted-foreground">{t("profile.baseHelp")}</p>
      {numeric("service_radius_km", t("profile.radius"), true)}
      <div aria-live="polite">
        {state === "saved" && <Notice tone="success">{t("profile.saved")}</Notice>}
        {state === "error" && <Notice tone="error">{t("profile.error")}</Notice>}
      </div>
      <Button type="submit" size="lg" disabled={state === "busy"} className="sm:self-start">
        {state === "busy" && <Spinner />}
        {state === "busy" ? t("profile.saving") : t("profile.save")}
      </Button>
    </form>
  );
}

function useAction() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run(name: string, call: () => Promise<{ data?: unknown; error?: unknown }>) {
    setBusy(name);
    setError(null);
    try {
      const { data, error: failure } = await call();
      if (data) router.refresh();
      else {
        const details = (failure as { error?: { message?: string } } | undefined)?.error;
        setError(details?.message ?? t("category.error"));
      }
    } catch {
      setError(t("category.error"));
    } finally {
      setBusy(null);
    }
  }
  return { busy, error, run };
}

export function CategoryWorkspace({ data, category }: { data: Dashboard; category: Category }) {
  const { busy, error, run } = useAction();
  const locked = data.categories.some((c) => c.listing_state === "PENDING_REVIEW");
  const subtypes = data.available_categories.filter((c) => c.parent_code === category.code);
  const [chosen, setChosen] = useState<string[]>(category.subtypes);
  const documents = data.documents.filter((d) => d.category_code === null || d.category_code === category.code);
  const references = data.references.filter((r) => r.category_code === category.code);
  const due = category.review_due_at ? new Date(category.review_due_at) <= new Date() : false;
  const canSubmit = ["DRAFT", "CHANGES_REQUESTED", "REJECTED"].includes(category.listing_state) ||
    (category.listing_state === "LISTED" && due);
  const submitLabel = category.listing_state === "LISTED"
    ? t("category.reverify")
    : category.listing_state === "DRAFT" ? t("category.submit") : t("category.resubmit");
  const missingLabels = category.requirements
    .filter((r) => category.missing_requirements.includes(r.id))
    .map((r) => r.label);
  const path = { params: { path: { code: category.code } } };

  return (
    <div className="flex flex-col gap-8">
      {category.message && (
        <Notice tone={category.listing_state === "LISTED" ? "info" : "warning"} title={t("category.message")}>
          <p className="whitespace-pre-line">{category.message}</p>
        </Notice>
      )}
      {category.listing_state === "REJECTED" && category.reapply_after && (
        <Notice tone="info">{t("category.reapplyAfter", { date: formatDate(category.reapply_after) })}</Notice>
      )}
      {category.hidden && <Notice tone="info">{t("category.hiddenNote")}</Notice>}
      {category.listing_state === "LISTED" && due && <Notice tone="warning">{t("category.dueNote")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}

      <section aria-labelledby="checklist" className="flex flex-col gap-3">
        <h2 id="checklist" className="font-heading text-xl font-semibold">{t("category.checklist")}</h2>
        <p className="text-base text-muted-foreground">{t("category.checklistIntro")}</p>
        <ul className="flex flex-col gap-2">
          {category.requirements.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-foreground/15 bg-card px-3 py-2.5 text-base">
              <span className="font-medium">{r.label}</span>
              <span className="flex flex-wrap items-center gap-2 text-muted-foreground">
                {r.level === "WHERE_APPLICABLE" && <Badge variant="neutral">{t("category.optional")}</Badge>}
                {r.accepts.length === 1 && r.accepts[0] === "SITE_VISIT"
                  ? t("category.visit")
                  : t("category.supplied", { provided: Math.min(r.provided, r.count), count: r.count })}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {subtypes.length > 0 && (
        <section aria-labelledby="subtypes" className="flex flex-col gap-3">
          <h2 id="subtypes" className="font-heading text-xl font-semibold">{t("category.subtypes")}</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {subtypes.map((s) => (
              <div key={s.code} className="flex items-center gap-3">
                <Checkbox id={`sub-${s.code}`} checked={chosen.includes(s.code)}
                  onCheckedChange={(on) => setChosen((c) => on ? [...c, s.code] : c.filter((x) => x !== s.code))} />
                <Label htmlFor={`sub-${s.code}`}>{s.name}</Label>
              </div>
            ))}
          </div>
          <Button type="button" variant="outline" className="sm:self-start" disabled={busy !== null}
            onClick={() => run("subtypes", () => browserApi.PUT("/api/v1/pro/categories/{code}/subtypes", { ...path, body: { subtypes: chosen } }))}>
            {t("category.saveSubtypes")}
          </Button>
        </section>
      )}

      <DocumentsSection documents={documents} categoryCode={category.code} locked={locked} />
      <ReferencesSection references={references} categoryCode={category.code} locked={locked} />
      <p className="text-base">
        <Link href="/portfolio" className="font-medium underline underline-offset-4">{t("category.portfolioLink")}</Link>
      </p>

      <div className="flex flex-col gap-3">
        {locked && category.listing_state === "PENDING_REVIEW" && (
          <Notice tone="info">{t("category.locked")}</Notice>
        )}
        {canSubmit && missingLabels.length > 0 && (
          <Notice tone="info">{t("category.missing", { items: missingLabels.join(", ") })}</Notice>
        )}
        <div className="flex flex-wrap gap-2">
          {canSubmit && (
            <Button type="button" size="lg" disabled={busy !== null}
              onClick={() => run("submit", () => browserApi.POST("/api/v1/pro/categories/{code}/submit", { params: { path: { code: category.code }, header: { "Idempotency-Key": key() } } }))}>
              {busy === "submit" ? <Spinner /> : <SendIcon aria-hidden="true" />}
              {busy === "submit" ? t("category.submitting") : submitLabel}
            </Button>
          )}
          {category.listing_state === "LISTED" && !category.hidden && (
            <Button type="button" variant="outline" disabled={busy !== null}
              onClick={() => run("hide", () => browserApi.POST("/api/v1/pro/categories/{code}/hide", path))}>
              <EyeOffIcon aria-hidden="true" />
              {t("category.hide")}
            </Button>
          )}
          {category.listing_state === "LISTED" && category.hidden && (
            <Button type="button" variant="outline" disabled={busy !== null}
              onClick={() => run("show", () => browserApi.POST("/api/v1/pro/categories/{code}/show", path))}>
              <EyeIcon aria-hidden="true" />
              {t("category.show")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentsSection({ documents, categoryCode, locked }: {
  documents: Dashboard["documents"]; categoryCode: string; locked: boolean;
}) {
  const { busy, error, run } = useAction();
  useRefreshWhileScanning(documents.map((d) => d.file?.state));
  const [kind, setKind] = useState<string | undefined>(undefined);
  const [issuer, setIssuer] = useState("");
  const [number, setNumber] = useState("");
  const [gstin, setGstin] = useState("");
  const input = useRef<HTMLInputElement>(null);

  async function add(event: FormEvent) {
    event.preventDefault();
    const file = input.current?.files?.[0];
    if (!kind || !file) return;
    await run("add", async () => {
      const fileId = await uploadFile(file, "VERIFICATION_EVIDENCE");
      if (!fileId) return { error: undefined };
      return browserApi.POST("/api/v1/pro/documents", {
        body: {
          kind: kind as "IDENTITY", file_id: fileId,
          category_code: kind === "IDENTITY" ? null : categoryCode, issuer, number, gstin,
        },
      });
    });
    if (input.current) input.current.value = "";
  }

  return (
    <section aria-labelledby="documents" className="flex flex-col gap-3">
      <h2 id="documents" className="font-heading text-xl font-semibold">{t("category.documents")}</h2>
      <p className="text-base text-muted-foreground">{t("category.documentsIntro")}</p>
      {documents.length === 0 ? (
        <p className="text-base text-muted-foreground">{t("category.noDocuments")}</p>
      ) : (
        <Card size="sm"><CardContent>
          <ul className="divide-y divide-border">
            {documents.map((d) => (
              <li key={d.document_id}>
                <FileRow
                  name={`${t(`category.kinds.${d.kind}`)}: ${d.file?.file_name ?? ""}`}
                  mime={d.file?.content_type ?? "application/octet-stream"}
                  size={d.file?.size_bytes ?? 0}
                  state={d.file?.state ?? "FAILED"}
                  actions={!locked && (
                    <Button type="button" variant="ghost" size="sm" disabled={busy !== null}
                      onClick={() => run("remove", () => browserApi.DELETE("/api/v1/pro/documents/{item_id}", { params: { path: { item_id: d.document_id } } }))}>
                      <Trash2Icon aria-hidden="true" />{t("category.remove")}
                    </Button>
                  )}
                />
              </li>
            ))}
          </ul>
        </CardContent></Card>
      )}
      {!locked && (
        <form onSubmit={add} className="flex flex-col gap-4 rounded-md border border-dashed border-border p-4">
          <FormFieldset id="doc-kind" legend={t("category.kind")} required>
            {({ legendId }) => (
              <ChoiceGroup id="doc-kind" labelledBy={legendId} value={kind} onValueChange={setKind} columns={1}
                options={(["IDENTITY", "BUSINESS", "REGISTRATION"] as const).map((k) => ({ value: k, label: t(`category.kinds.${k}`) }))} />
            )}
          </FormFieldset>
          {kind === "REGISTRATION" && (
            <>
              <FormField id="doc-issuer" label={t("category.issuer")}>
                {(control) => <Input {...control} value={issuer} onChange={(e) => setIssuer(e.target.value)} />}
              </FormField>
              <FormField id="doc-number" label={t("category.number")}>
                {(control) => <Input {...control} value={number} onChange={(e) => setNumber(e.target.value)} />}
              </FormField>
            </>
          )}
          {kind === "BUSINESS" && (
            <FormField id="doc-gstin" label={t("category.gstin")}>
              {(control) => <Input {...control} value={gstin} onChange={(e) => setGstin(e.target.value)} />}
            </FormField>
          )}
          <FormField id="doc-file" label={t("category.file")} required>
            {(control) => <Input {...control} ref={input} type="file" accept="image/jpeg,image/png,application/pdf" />}
          </FormField>
          {error && <Notice tone="error" live="assertive">{error}</Notice>}
          <Button type="submit" variant="outline" disabled={!kind || busy !== null} className="sm:self-start">
            {busy === "add" ? <Spinner /> : <UploadIcon aria-hidden="true" />}
            {busy === "add" ? t("category.uploading") : t("category.addDocument")}
          </Button>
        </form>
      )}
    </section>
  );
}

function ReferencesSection({ references, categoryCode, locked }: {
  references: Dashboard["references"]; categoryCode: string; locked: boolean;
}) {
  const { busy, error, run } = useAction();
  const [form, setForm] = useState({ name: "", phone: "", note: "" });
  async function add(event: FormEvent) {
    event.preventDefault();
    await run("add", () => browserApi.POST("/api/v1/pro/references", {
      body: { category_code: categoryCode, name: form.name, phone: form.phone, project_note: form.note },
    }));
    setForm({ name: "", phone: "", note: "" });
  }
  return (
    <section aria-labelledby="references" className="flex flex-col gap-3">
      <h2 id="references" className="font-heading text-xl font-semibold">{t("category.references")}</h2>
      <p className="text-base text-muted-foreground">{t("category.referencesIntro")}</p>
      {references.length === 0 ? (
        <p className="text-base text-muted-foreground">{t("category.noReferences")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {references.map((r) => (
            <li key={r.reference_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-foreground/15 bg-card px-3 py-2.5 text-base">
              <span><span className="font-medium">{r.name}</span> · {r.phone} · {r.project_note}</span>
              {!locked && (
                <Button type="button" variant="ghost" size="sm" disabled={busy !== null}
                  onClick={() => run("remove", () => browserApi.DELETE("/api/v1/pro/references/{item_id}", { params: { path: { item_id: r.reference_id } } }))}>
                  <Trash2Icon aria-hidden="true" />{t("category.remove")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!locked && (
        <form onSubmit={add} className="grid gap-4 rounded-md border border-dashed border-border p-4 sm:grid-cols-3">
          <FormField id="ref-name" label={t("category.refName")} required>
            {(c) => <Input {...c} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
          </FormField>
          <FormField id="ref-phone" label={t("category.refPhone")} required>
            {(c) => <Input {...c} type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />}
          </FormField>
          <FormField id="ref-note" label={t("category.refNote")} required>
            {(c) => <Input {...c} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />}
          </FormField>
          {error && <div className="sm:col-span-3"><Notice tone="error" live="assertive">{error}</Notice></div>}
          <Button type="submit" variant="outline" className="sm:col-span-3 sm:justify-self-start"
            disabled={busy !== null || !form.name || !form.phone || !form.note}>
            <PlusIcon aria-hidden="true" />{t("category.addReference")}
          </Button>
        </form>
      )}
    </section>
  );
}

export function PortfolioManager({ data }: { data: Dashboard }) {
  const { busy, error, run } = useAction();
  const [caption, setCaption] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const locked = data.categories.some((c) => c.listing_state === "PENDING_REVIEW");
  useRefreshWhileScanning(data.portfolio.map((p) => p.file?.state));
  async function add(event: FormEvent) {
    event.preventDefault();
    const file = input.current?.files?.[0];
    if (!file) return;
    await run("add", async () => {
      const fileId = await uploadFile(file, "PORTFOLIO");
      if (!fileId) return { error: undefined };
      return browserApi.POST("/api/v1/pro/portfolio", { body: { file_id: fileId, caption } });
    });
    setCaption("");
    if (input.current) input.current.value = "";
  }
  return (
    <div className="flex flex-col gap-6">
      {data.portfolio.length === 0 ? (
        <p className="text-base text-muted-foreground">{t("portfolio.none")}</p>
      ) : (
        <Card size="sm"><CardContent>
          <ul className="divide-y divide-border">
            {data.portfolio.map((p) => (
              <li key={p.item_id}>
                <FileRow
                  name={`${p.caption} (${t(`portfolio.review.${p.review_state}`)})`}
                  mime={p.file?.content_type ?? "image/jpeg"}
                  size={p.file?.size_bytes ?? 0}
                  state={p.file?.state ?? "FAILED"}
                  actions={!locked && (
                    <Button type="button" variant="ghost" size="sm" disabled={busy !== null}
                      onClick={() => run("remove", () => browserApi.DELETE("/api/v1/pro/portfolio/{item_id}", { params: { path: { item_id: p.item_id } } }))}>
                      <Trash2Icon aria-hidden="true" />{t("category.remove")}
                    </Button>
                  )}
                />
              </li>
            ))}
          </ul>
        </CardContent></Card>
      )}
      {locked ? (
        <Notice tone="info">{t("category.locked")}</Notice>
      ) : (
        <Card size="sm">
          <CardHeader><CardTitle className="text-base"><h2>{t("portfolio.add")}</h2></CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={add} className="flex flex-col gap-4">
              <FormField id="caption" label={t("portfolio.caption")} required>
                {(c) => <Input {...c} maxLength={200} value={caption} onChange={(e) => setCaption(e.target.value)} />}
              </FormField>
              <FormField id="photo" label={t("portfolio.file")} required>
                {(c) => <Input {...c} ref={input} type="file" accept="image/jpeg,image/png" />}
              </FormField>
              {error && <Notice tone="error" live="assertive">{error}</Notice>}
              <Button type="submit" disabled={!caption || busy !== null} className="sm:self-start">
                {busy === "add" ? <Spinner /> : <UploadIcon aria-hidden="true" />}
                {busy === "add" ? t("category.uploading") : t("portfolio.add")}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function CategoryHeaderBadge({ category }: { category: Category }) {
  return <StatusBadge kind="listing" status={category.listing_state} withLabel />;
}

