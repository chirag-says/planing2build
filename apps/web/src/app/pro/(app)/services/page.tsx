import type { Metadata } from "next";

import { PageContainer, PageHeader, RuledSection } from "@/components/plan2build/page-header";
import { ConstructionLine, ServicesList, Todos } from "@/components/plan2build/pro-console";
import { AddCategoryForm } from "@/components/plan2build/pro-forms";
import { getTranslator } from "@/lib/i18n";
import { loadConsole } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("servicesPage.title") };

// The services a professional offers (their categories, D-06: each checked and listed on its own),
// the way to a listing while none is listed, and adding a service.
export default async function ProServicesPage() {
  const c = await loadConsole("/services");
  const t = getTranslator("Console");
  const p = getTranslator("Pro");
  return (
    <PageContainer width="wide">
      <PageHeader size="compact" title={t("servicesPage.title")} description={t("servicesPage.intro")} />
      {c.ready < 5 && (
        <div className="flex flex-col gap-6">
          <ConstructionLine checkpoints={c.checkpoints} />
          <Todos todos={c.todos} />
        </div>
      )}
      <RuledSection id="services-title" title={t("listing.services")}>
        <ServicesList console={c} add={false} />
      </RuledSection>
      <section id="add" aria-labelledby="add-title" className="flex scroll-mt-24 flex-col gap-4 border-t-2 border-foreground pt-4">
        <h2 id="add-title" className="font-heading text-2xl leading-none">
          {t("listing.addService")}
        </h2>
        {c.addOptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">{p("dashboard.allAdded")}</p>
        ) : (
          <AddCategoryForm options={c.addOptions} />
        )}
      </section>
    </PageContainer>
  );
}
