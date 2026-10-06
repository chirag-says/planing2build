// A Build Plan version as read by the family, a professional or operations (Slice 3.5): the
// version's own snapshot, nothing computed here. Schedule dates are never shown: they are not
// calculated while the canonical build order (BP-07A) is deferred.
import type { components } from "@p2b/contracts";

import { StatusBadge } from "@/components/plan2build/status-badge";
import { getTranslator } from "@/lib/i18n";

type Snapshot = components["schemas"]["SnapshotOut"];

export function SnapshotView({ view, showRates = true }: { view: Snapshot; showRates?: boolean }) {
  const t = getTranslator("BuildPlan");
  const v = view.version;
  return (
    <div className="flex flex-col gap-6" data-version-state={v.state}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-heading text-lg font-medium">{t("version", { number: v.version_no })}</h2>
        <StatusBadge kind="buildPlan" status={v.state} withLabel />
      </div>
      <dl className="grid gap-1 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">{t("contentHash")}</dt>
        <dd className="break-all font-mono text-xs">{v.content_hash ?? "-"}</dd>
        {v.issued_at && (
          <>
            <dt className="text-muted-foreground">{t("issuedAt", { date: "" })}</dt>
            <dd>{v.issued_at}</dd>
          </>
        )}
      </dl>

      <section aria-labelledby="values" className="flex flex-col gap-2">
        <h3 id="values" className="font-medium">{t("values")}</h3>
        <div tabIndex={0} className="max-h-96 overflow-auto rounded-md border border-border">
          <table className="w-full text-left text-xs">
            <thead>
              <tr><th className="p-1">Code</th><th className="p-1">{t("criteria")}</th><th className="p-1">{t("projectValue")}</th></tr>
            </thead>
            <tbody>
              {view.values.map((value) => (
                <tr key={value.code} className="border-t border-border align-top">
                  <td className="p-1">{value.code} {value.item}</td>
                  <td className="p-1 text-muted-foreground">{value.criteria}</td>
                  <td className="p-1">
                    {value.applicability === "APPLICABLE"
                      ? value.value
                      : t("notApplicable", { reason: value.not_applicable_reason ?? "" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="boq" className="flex flex-col gap-2">
        <h3 id="boq" className="font-medium">{t("boq")}</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {view.boq.map((line) => (
            <li key={line.line_no}>
              {line.line_no}. {line.item_code} {line.description}: {line.quantity} {line.unit}
              {showRates ? ` x ${line.rate} = ${line.amount}` : ""}
            </li>
          ))}
        </ul>
        {showRates && <p className="text-sm font-medium">{t("total", { amount: view.boq_total })}</p>}
      </section>

      <section aria-labelledby="schedule" className="flex flex-col gap-2">
        <h3 id="schedule" className="font-medium">{t("schedule")}</h3>
        <p className="text-sm text-muted-foreground">{t("scheduleNote")}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {view.schedule.map((entry) => (
            <li key={entry.entry_key}>
              {entry.entry_key} {entry.stage_name}: {t("days", { days: entry.duration_days ?? 0 })}
              {entry.predecessors.length > 0 ? `; ${t("after", { keys: entry.predecessors.join(", ") })}` : ""}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="scope" className="grid gap-2 sm:grid-cols-3">
        <h3 id="scope" className="font-medium sm:col-span-3">{t("scope")}</h3>
        {(["inclusions", "exclusions", "assumptions"] as const).map((name) => (
          <div key={name}>
            <h4 className="text-sm font-medium">{t(name)}</h4>
            <ul className="list-disc pl-4 text-sm">
              {view.scope[name].map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        ))}
      </section>

      <section aria-labelledby="signoffs" className="flex flex-col gap-2">
        <h3 id="signoffs" className="font-medium">{t("signoffs")}</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {view.signoffs.filter((s) => s.state === "SIGNED").map((s) => (
            <li key={s.id}>
              {s.line_code}: {s.engineer_name} ({s.registration_number ?? "-"}), {s.mode}, {s.signed_at}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="history" className="flex flex-col gap-2">
        <h3 id="history" className="font-medium">{t("history")}</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {view.history.map((h) => (
            <li key={h.version_no}>
              {t("version", { number: h.version_no })}: {h.state} {h.close_reason ? `(${h.close_reason})` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
