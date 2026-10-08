import type { Metadata } from "next";

import { ActionButton, ConfirmAction, JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { canRetireCard } from "@/lib/ops-admin";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.buildPlan") };

// Build Plan reference data (Slice 3.5, functional): item rate cards (operations prepare, ADMIN
// publishes, BP-06), drawing checkers (BP-01) and sign-off statements (BP-04).
export default async function OpsBuildPlanSetupPage() {
  const staff = await requireVerifiedStaff("/build-plan");
  const admin = staff.roles.includes("ADMIN");
  const api = await serverApi();
  const [cards, checkers, statements, acceptance] = await Promise.all([
    api.GET("/api/v1/ops/item-rate-cards"),
    api.GET("/api/v1/ops/drawing-checkers"),
    api.GET("/api/v1/ops/signoff-statements"),
    api.GET("/api/v1/ops/acceptance-statements"),
  ]);
  const t = getTranslator("BuildPlan");
  const newCard = JSON.stringify(
    { geography: "Raipur", effective_from: new Date().toISOString().slice(0, 10), source_reference: "", is_demo: false },
    null,
    2,
  );
  return (
    <PageContainer width="wide">
      <PageHeader title={getTranslator("Ops")("nav.buildPlan")} />
      <section aria-labelledby="cards" className="flex flex-col gap-4">
        <SectionHeader id="cards" title={t("ops.rateCards")} />
        {(cards.data ?? []).map((card) => (
          <article key={card.id} className="flex flex-col gap-2 rounded-md border border-border p-3" data-card-status={card.status}>
            <h3 className="font-medium">
              {card.geography} v{card.version} · {card.status}{card.is_demo ? " · DEMO" : ""}
            </h3>
            <p className="text-sm text-muted-foreground">{card.source_reference}</p>
            <ul className="text-sm">
              {card.lines.map((line) => (
                <li key={line.item_code}>{line.item_code} {line.description} ({line.unit}): {line.rate}</li>
              ))}
            </ul>
            {card.status === "DRAFT" && (
              <>
                <JsonForm id={`lines-${card.id}`} label={t("ops.lines")} method="PUT" wrap="lines"
                  url={`/api/v1/ops/item-rate-cards/${card.id}/lines`} submitLabel={t("ops.saveLines")}
                  initial={JSON.stringify(card.lines.length ? card.lines : [{ item_code: "", description: "", unit: "", rate: "0.00" }], null, 2)} />
                {admin && <ActionButton label={t("ops.publish")} url={`/api/v1/admin/item-rate-cards/${card.id}/publish`} />}
              </>
            )}
            {canRetireCard(card.status, admin) && (
              <ConfirmAction id={`retire-${card.id}`} label={t("ops.retire")} url={`/api/v1/admin/item-rate-cards/${card.id}/retire`}
                title={t("ops.retireTitle", { geography: card.geography, version: card.version })}
                description={t("ops.retireBody")} done={t("ops.retired")} />
            )}
          </article>
        ))}
        <JsonForm id="new-card" label={t("ops.newCard")} method="POST" url="/api/v1/ops/item-rate-cards"
          initial={newCard} submitLabel={t("ops.create")} once />
      </section>
      <section aria-labelledby="checkers" className="flex flex-col gap-3">
        <SectionHeader id="checkers" title={t("ops.checkers")} />
        <ul className="flex flex-col gap-2 text-sm">
          {(checkers.data ?? []).map((c) => (
            <li key={c.id} className="flex flex-col gap-1">
              <span>{c.name}: {c.qualification}{c.user_id ? " (account)" : ""}</span>
              {admin && (
                <ConfirmAction id={`end-${c.id}`} label={t("ops.endChecker")} url={`/api/v1/admin/drawing-checkers/${c.id}/end`}
                  once={false} title={t("ops.endCheckerTitle", { name: c.name })} description={t("ops.endCheckerBody")} />
              )}
            </li>
          ))}
        </ul>
        {(checkers.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("ops.noCheckers")}</p>}
        {admin && (
          <JsonForm id="new-checker" label={t("ops.appoint")} method="POST" url="/api/v1/admin/drawing-checkers"
            initial={JSON.stringify({ name: "", qualification: "", registration_reference: null, user_id: null }, null, 2)}
            submitLabel={t("ops.appoint")} once />
        )}
      </section>
      <section aria-labelledby="statements" className="flex flex-col gap-3">
        <SectionHeader id="statements" title={t("ops.statements")} />
        <ul className="flex flex-col gap-2 text-sm">
          {(statements.data ?? []).map((s) => (
            <li key={s.id} className="flex flex-col gap-1">
              <span className="font-medium">v{s.version} · {s.status}</span>
              <p>{s.text}</p>
              <p className="text-muted-foreground">{s.note}</p>
              {admin && s.status === "DRAFT" && (
                <ActionButton label={t("ops.activate")} url={`/api/v1/admin/signoff-statements/${s.id}/activate`} once={false} />
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <JsonForm id="new-statements" label={t("ops.newStatement")} method="POST" url="/api/v1/admin/signoff-statements"
            initial={JSON.stringify({ text: "", note: "" }, null, 2)} submitLabel={t("ops.create")} once />
        )}
      </section>
      <section aria-labelledby="acceptance" className="flex flex-col gap-3">
        <SectionHeader id="acceptance" title={t("ops.acceptanceStatements")} />
        <ul className="flex flex-col gap-2 text-sm">
          {(acceptance.data ?? []).map((s) => (
            <li key={s.id} className="flex flex-col gap-1">
              <span className="font-medium">v{s.version} · {s.status}</span>
              <p>{s.text}</p>
              <p className="text-muted-foreground">{s.note}</p>
              {admin && s.status === "DRAFT" && (
                <ActionButton label={t("ops.activate")} url={`/api/v1/admin/acceptance-statements/${s.id}/activate`} once={false} />
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <JsonForm id="new-acceptance" label={t("ops.newStatement")} method="POST" url="/api/v1/admin/acceptance-statements"
            initial={JSON.stringify({ text: "", note: "" }, null, 2)} submitLabel={t("ops.create")} once />
        )}
      </section>
    </PageContainer>
  );
}
