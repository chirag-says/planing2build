import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { isNotRecorded, readBuildRecord } from "@/lib/build-record";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string; versionNo: string }>;
}): Promise<Metadata> {
  const { projectId, versionNo } = await params;
  const area = getTranslator("Records")("snapshot.title", { version: versionNo });
  return { title: await projectTitle(projectId, area) };
}

const FLOORS = { "-1": "basement", "0": "ground", "1": "first", "2": "second", "3": "third" } as const;
const KNOWN = {
  versionStates: ["DRAFT", "ISSUED", "SUPERSEDED"],
  basis: ["ACKNOWLEDGED", "ISSUED_BY_OPERATIONS"],
  handoverStates: ["OPEN", "READY", "ACKNOWLEDGED", "ISSUED_BY_OPERATIONS"],
  documentKinds: ["WARRANTY", "MANUAL", "DRAWING", "CERTIFICATE", "PHOTO", "OTHER"],
  stageStates: ["NOT_STARTED", "IN_PROGRESS", "COMPLETION_REQUESTED", "COMPLETED", "BLOCKED", "ON_HOLD"],
  results: ["PASS", "OBSERVATION", "NON_CONFORMANCE", "NOT_APPLICABLE"],
  kinds: ["INITIAL", "REINSPECTION"],
  ncStates: ["OPEN", "RECTIFICATION_SUBMITTED", "REINSPECTION_SCHEDULED", "CLOSED"],
  severities: ["MINOR", "MAJOR", "CRITICAL"],
  engagementStates: ["ACTIVE", "ENDED"],
  classes: ["SITE_PLAN", "FLOOR_PLAN", "ELEVATION", "SECTION", "STRUCTURAL", "OTHER"],
} as const;

/** A backend state through its translated label; a value this screen does not know shows as sent. */
function known<K extends keyof typeof KNOWN>(set: K, value: string | null): value is (typeof KNOWN)[K][number] {
  return value !== null && (KNOWN[set] as readonly string[]).includes(value);
}

function Block({ id, title, children, empty }: { id: string; title: string; children: ReactNode; empty?: string | false }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-2">
      <SectionHeader id={id} level={3} title={title} />
      {empty ? <p className="text-sm text-muted-foreground">{empty}</p> : children}
    </section>
  );
}

// One issued Build Record version as recorded (Slice 3.7C, EX-17): the frozen snapshot the PDF and
// the data file were made from, read section by section. Nothing is computed or added here: no
// price or amount is in the record, and product, purchase and installation show "not recorded"
// (EX-16). Household members read; drafts are never shown (404).
export default async function BuildRecordVersionPage({
  params,
}: {
  params: Promise<{ projectId: string; versionNo: string }>;
}) {
  const { projectId, versionNo } = await params;
  if (!/^\d{1,6}$/.test(versionNo)) notFound();
  const { data, error, response } = await (await serverApi()).GET(
    "/api/v1/projects/{project_id}/build-record/versions/{version_no}",
    { params: { path: { project_id: projectId, version_no: Number(versionNo) } } },
  );
  if (response.status === 404) notFound();
  const t = getTranslator("Records");
  const x = getTranslator("Execution");
  const a = getTranslator("Assurance");
  const b = getTranslator("BuildPlan");
  const w = getTranslator("Workspace");
  const s = getTranslator("Status");
  const back = (
    <Link href={`/projects/${projectId}/construction#build-record`} className="self-start text-sm underline underline-offset-4">
      {t("snapshot.back")}
    </Link>
  );
  if (!data) {
    const problem = (error as { error?: { message?: string } } | undefined)?.error?.message;
    return (
      <section className="flex flex-col gap-4">
        {back}
        <Notice tone="error" title={t("snapshot.loadFailed")}>{problem}</Notice>
      </section>
    );
  }

  const record = readBuildRecord(data.snapshot);
  const floor = (f: number | null) => {
    const key = f === null ? undefined : FLOORS[String(f) as keyof typeof FLOORS];
    return key ? ` · ${w(`floors.${key}`)}` : f === null ? "" : ` · ${t("snapshot.floor", { floor: f })}`;
  };
  const date = (iso: string | null) => (iso ? formatDate(iso) : t("snapshot.none"));
  const notRecorded = (value: string | null) => (isNotRecorded(value) ? t("snapshot.notRecorded") : value);
  const mark = (m: { value: string | null; byOperations: boolean } | null) =>
    m ? `${m.value === "YES" ? x("yes") : m.value === "NO" ? x("no") : (m.value ?? "")}${m.byOperations ? ` (${x("byOps")})` : ""}` : x("notMarked");
  const base = `/api/v1/projects/${projectId}/build-record/versions/${data.version_no}`;
  const hd = record.handover;

  return (
    <article aria-labelledby="record-title" className="flex flex-col gap-6" data-testid="build-record-snapshot">
      {back}
      <SectionHeader
        id="record-title"
        title={t("snapshot.title", { version: data.version_no })}
        description={t("snapshot.intro")}
      />
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted-foreground">{t("snapshot.state")}</dt>
        <dd>{known("versionStates", data.state) ? t(`versionStates.${data.state}`) : data.state}</dd>
        <dt className="text-muted-foreground">{t("snapshot.issued")}</dt>
        <dd>{date(data.issued_at ?? null)}</dd>
        <dt className="text-muted-foreground">{t("snapshot.basisLabel")}</dt>
        <dd>{known("basis", data.basis) ? t(`snapshot.basis.${data.basis}`) : data.basis}</dd>
        <dt className="text-muted-foreground">{t("snapshot.project")}</dt>
        <dd>{record.identity.projectCode ?? t("snapshot.none")}{record.identity.locality ? ` · ${record.identity.locality}` : ""}</dd>
        {data.correction_reason && (
          <>
            <dt className="text-muted-foreground">{t("snapshot.correctionLabel")}</dt>
            <dd>{data.correction_reason}</dd>
          </>
        )}
        <dt className="text-muted-foreground">sha256</dt>
        <dd className="font-mono text-xs break-all">{data.snapshot_sha256 ?? t("snapshot.none")}</dd>
      </dl>
      <span className="flex flex-wrap gap-2">
        <DownloadLink label={t("pdf", { version: data.version_no })} url={`${base}/pdf/url`} />
        <DownloadLink label={t("json", { version: data.version_no })} url={`${base}/json/url`} />
      </span>
      <Notice tone="info">{t("snapshot.noPrices")}</Notice>

      <Block id="record-plan" title={t("snapshot.plan")}>
        <p className="text-sm">
          {record.plan.versionNo === null
            ? t("snapshot.noPlan")
            : t("snapshot.planLine", { version: record.plan.versionNo, accepted: date(record.plan.acceptedAt) })}
        </p>
        {record.plan.contentHash && <p className="font-mono text-xs break-all">sha256 {record.plan.contentHash}</p>}
      </Block>

      <Block id="record-drawings" title={t("snapshot.drawings")} empty={record.drawings.length === 0 && t("snapshot.noneRecorded")}>
        <ul className="flex flex-col gap-1 text-sm">
          {record.drawings.map((d, n) => (
            <li key={d.fileId ?? n} className="flex flex-col">
              <span>
                {d.sheetNo ? `${d.sheetNo} · ` : ""}
                {d.title ?? (known("classes", d.drawingClass) ? b(`classes.${d.drawingClass}`) : d.drawingClass)}
                {floor(d.floor)}
              </span>
              {d.sha256 && <span className="font-mono text-xs break-all text-muted-foreground">sha256 {d.sha256}</span>}
            </li>
          ))}
        </ul>
      </Block>

      <Block id="record-contractors" title={t("snapshot.contractors")} empty={record.contractors.length === 0 && t("snapshot.noneRecorded")}>
        <ul className="flex flex-col gap-1 text-sm">
          {record.contractors.map((c, n) => (
            <li key={n}>
              {c.name ?? t("snapshot.contractor")}
              {c.chosenByFamily ? ` (${t("snapshot.chosenByFamily")})` : ""}
              {" · "}
              {t("snapshot.period", { from: date(c.startedAt), to: c.endedAt ? formatDate(c.endedAt) : t("snapshot.now") })}
              {c.state && ` · ${known("engagementStates", c.state) ? s(`engagement.${c.state}`) : c.state}`}
            </li>
          ))}
        </ul>
      </Block>

      <Block id="record-execution" title={t("snapshot.execution")} empty={record.execution.length === 0 && t("snapshot.noneRecorded")}>
        <ul className="flex flex-col gap-1 text-sm">
          {record.execution.map((e, n) => (
            <li key={n}>
              <span className="font-medium">{e.stageNumber !== null ? `${e.stageNumber}. ` : ""}{e.name}{floor(e.floor)}</span>
              {" · "}
              {known("stageStates", e.state) ? x(`states.${e.state}`) : e.state}
              {" · "}
              {t("snapshot.stageDates", { start: date(e.actualStart), end: date(e.actualEnd) })}
              {" · "}
              {t("snapshot.updates", { count: e.updates })}
            </li>
          ))}
        </ul>
      </Block>

      <Block
        id="record-assurance"
        title={t("snapshot.assurance")}
        empty={record.inspections.length === 0 && record.findings.length === 0 && t("snapshot.noneRecorded")}
      >
        <ul className="flex flex-col gap-2 text-sm">
          {record.inspections.map((i, n) => (
            <li key={n} className="flex flex-col">
              <span className="font-medium">
                {t("snapshot.gate", { gate: i.gate ?? "" })} · {i.stage ?? ""}{floor(i.floor)}
                {i.kind && ` · ${known("kinds", i.kind) ? a(`kinds.${i.kind}`) : i.kind}`}
              </span>
              <span>{t("snapshot.approved", { when: date(i.approvedAt), auditor: i.auditorCode ?? t("snapshot.none") })}</span>
              {i.outcome && <span>{i.outcome}</span>}
              {i.reports.map((r, m) => (
                <span key={m} className="font-mono text-xs break-all text-muted-foreground">
                  {t("snapshot.report", { version: r.version ?? "" })} sha256 {r.sha256 ?? ""}
                </span>
              ))}
            </li>
          ))}
        </ul>
        {record.findings.length > 0 && (
          <>
            <h4 className="text-sm font-medium">{t("snapshot.findings")}</h4>
            <ul className="flex flex-col gap-1 text-sm">
              {record.findings.map((f, n) => (
                <li key={n}>
                  {known("severities", f.severity) ? t(`snapshot.severities.${f.severity}`) : f.severity}: {f.description}
                  {" · "}
                  {known("ncStates", f.state) ? a(`ncStates.${f.state}`) : f.state}
                  {f.closedAt && ` · ${formatDate(f.closedAt)}`}
                </li>
              ))}
            </ul>
          </>
        )}
      </Block>

      <Block id="record-marks" title={t("snapshot.marks")} empty={record.paymentMarks.length === 0 && t("snapshot.noneRecorded")}>
        <p className="text-sm text-muted-foreground">{t("snapshot.marksNote")}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {record.paymentMarks.map((m, n) => (
            <li key={n}>
              {t("snapshot.stage", { stage: m.stageNumber ?? "" })}{floor(m.floor)} · {x("paid", { value: mark(m.paid) })} · {x("received", { value: mark(m.received) })}
            </li>
          ))}
        </ul>
      </Block>

      <Block id="record-handover" title={t("handover")}>
        {hd.state && <p className="text-sm">{known("handoverStates", hd.state) ? t(`states.${hd.state}`) : hd.state}</p>}
        {hd.acknowledgement && (
          <div className="flex flex-col gap-1 text-sm">
            <p>{t("acknowledgedAt", { when: date(hd.acknowledgement.acknowledgedAt) })}</p>
            {hd.acknowledgement.statementText && (
              <blockquote className="border-l-2 border-border pl-3">{hd.acknowledgement.statementText}</blockquote>
            )}
          </div>
        )}
        {hd.issuedWithoutAcknowledgement && (
          <p className="text-sm">
            {t("issuedWithout", { when: date(hd.issuedWithoutAcknowledgement.issuedAt), reason: hd.issuedWithoutAcknowledgement.reason ?? "" })}
          </p>
        )}
        <h4 className="text-sm font-medium">{t("documents")}</h4>
        {hd.documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("noDocuments")}</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {hd.documents.map((d, n) => (
              <li key={n} className="flex flex-col">
                <span>{known("documentKinds", d.kind) ? t(`kinds.${d.kind}`) : d.kind}: {d.title}</span>
                {d.sha256 && <span className="font-mono text-xs break-all text-muted-foreground">sha256 {d.sha256}</span>}
              </li>
            ))}
          </ul>
        )}
        {hd.warranties.length > 0 && (
          <>
            <h4 className="text-sm font-medium">{t("warranties")}</h4>
            <ul className="flex flex-col gap-1 text-sm">
              {hd.warranties.map((wt, n) => (
                <li key={n}>{t("warranty", { item: wt.item, term: wt.term, expiry: date(wt.expiryDate), installer: wt.installer })}</li>
              ))}
            </ul>
          </>
        )}
      </Block>

      <Block id="record-specification" title={t("snapshot.specification")} empty={record.specification.length === 0 && t("snapshot.noneRecorded")}>
        <ul className="flex flex-col divide-y divide-border text-sm">
          {record.specification.map((line) => (
            <li key={line.code} className="flex flex-col gap-0.5 py-2">
              <span className="font-medium">{line.code} · {line.item}</span>
              <span>
                {t("snapshot.accepted")}:{" "}
                {line.applicability === "NOT_APPLICABLE" ? t("snapshot.notApplicable") : (line.acceptedValue ?? t("snapshot.none"))}
              </span>
              <span>
                {t("snapshot.verified")}:{" "}
                {line.verification.length === 0
                  ? t("snapshot.notInspected")
                  : line.verification
                      .map((v) => `${t("snapshot.gate", { gate: v.gate ?? "" })}${floor(v.floor)}: ${known("results", v.result) ? a(`results.${v.result}`) : (v.result ?? "")}`)
                      .join("; ")}
              </span>
              <span className="text-muted-foreground">
                {t("snapshot.product")}: {notRecorded(line.product)} · {t("snapshot.purchase")}: {notRecorded(line.purchase)} · {t("snapshot.installation")}: {notRecorded(line.installation)}
              </span>
            </li>
          ))}
        </ul>
      </Block>
    </article>
  );
}
