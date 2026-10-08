// The handover and the Build Record as the homeowner sees them (Slice 3.7C): whether the owner
// acknowledged the handover or Plan2Build issued it without acknowledgement (EX-15, never shown
// as an acknowledgement), the documents and warranties, and the Build Record versions with their
// PDF and data file behind logged links (EX-17), and a link to read each version's contents.
// Household members read.
import type { components } from "@p2b/contracts";
import Link from "next/link";

import { SectionHeader } from "@/components/plan2build/page-header";
import { AcknowledgeHandover } from "@/components/plan2build/records";
import { DownloadLink } from "@/components/plan2build/rfq";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type HandoverView = components["schemas"]["HandoverViewOut"];
type Records = components["schemas"]["BuildRecordsOut"];

export function HandoverSection({ projectId, view }: { projectId: string; view: HandoverView }) {
  const t = getTranslator("Records");
  const h = view.handover;
  const base = `/api/v1/projects/${projectId}/handover`;
  return (
    <section aria-labelledby="handover" className="flex flex-col gap-3">
      <SectionHeader id="handover" title={t("handover")} description={t("handoverIntro")} />
      {!h && <p className="text-sm">{t("noHandover")}</p>}
      {h && (
        <div className="flex flex-col gap-2 text-sm">
          <p data-testid="handover-state">{t(`states.${h.state}`)}</p>
          {h.acknowledged_at && <p>{t("acknowledgedAt", { when: formatDate(h.acknowledged_at) })}</p>}
          {h.issued_without_acknowledgement && h.issued_at && (
            <p data-testid="issued-without">{t("issuedWithout", { when: formatDate(h.issued_at), reason: h.issue_reason ?? "" })}</p>
          )}
          <h3 className="font-medium">{t("documents")}</h3>
          {h.documents.length === 0 && <p>{t("noDocuments")}</p>}
          <span className="flex flex-wrap gap-2">
            {h.documents.map((d) => (
              <DownloadLink key={d.id} label={`${t(`kinds.${d.kind}`)}: ${d.title}`} url={`${base}/documents/${d.id}/url`} />
            ))}
          </span>
          {h.warranties.length > 0 && <h3 className="font-medium">{t("warranties")}</h3>}
          <ul className="flex flex-col gap-1">
            {h.warranties.map((w) => (
              <li key={w.id}>{t("warranty", { item: w.item, term: w.term, expiry: formatDate(w.expiry_date), installer: w.installer })}</li>
            ))}
          </ul>
          {view.is_owner && h.state === "READY" && <AcknowledgeHandover projectId={projectId} />}
          {!view.is_owner && h.state === "READY" && <p className="text-muted-foreground">{t("ownerAcknowledges")}</p>}
        </div>
      )}
    </section>
  );
}

export function BuildRecordSection({ projectId, records }: { projectId: string; records: Records }) {
  const t = getTranslator("Records");
  const base = `/api/v1/projects/${projectId}/build-record/versions`;
  return (
    <section aria-labelledby="build-record" className="flex flex-col gap-3">
      <SectionHeader id="build-record" title={t("buildRecord")} description={t("buildRecordIntro")} />
      {records.versions.length === 0 && <p className="text-sm">{t("noBuildRecord")}</p>}
      <ul className="flex flex-col gap-2">
        {records.versions.map((v) => (
          <li key={v.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="build-record-version">
            <span className="font-medium">{t("version", { version: v.version_no, state: t(`versionStates.${v.state}`) })}
              {v.issued_at ? ` · ${formatDate(v.issued_at)}` : ""}</span>
            {v.correction_reason && <span>{t("correction", { reason: v.correction_reason })}</span>}
            <span className="font-mono text-xs break-all">sha256 {v.snapshot_sha256}</span>
            <span className="flex flex-wrap items-center gap-2">
              <Link href={`/projects/${projectId}/construction/build-record/${v.version_no}`}
                className="text-sm font-medium underline underline-offset-4">
                {t("viewVersion", { version: v.version_no })}
              </Link>
              <DownloadLink label={t("pdf", { version: v.version_no })} url={`${base}/${v.version_no}/pdf/url`} />
              <DownloadLink label={t("json", { version: v.version_no })} url={`${base}/${v.version_no}/json/url`} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
