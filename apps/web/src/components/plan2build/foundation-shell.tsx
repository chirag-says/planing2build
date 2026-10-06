import { AccountStatus } from "@/components/plan2build/account-status";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { getTranslator } from "@/lib/i18n";

type ShellNamespace = "Pro";

/**
 * Placeholder home for the professional and operations hosts until their first slices land. It
 * renders real data (the session state from the API), so it doubles as an end-to-end check of the
 * routing. Same design system as the homeowner host; each host keeps its own navigation later.
 */
export async function FoundationShell({ namespace }: { namespace: ShellNamespace }) {
  const t = getTranslator(namespace);
  return (
    <PageContainer>
      <PageHeader title={t("title")} description={t("foundationNote")} />
      <AccountStatus />
    </PageContainer>
  );
}
