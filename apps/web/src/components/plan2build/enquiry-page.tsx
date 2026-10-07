import type { EnquiryKind } from "@p2b/contracts";

import { EnquiryForm } from "@/components/plan2build/enquiry-form";
import { HangingCard } from "@/components/plan2build/hanging-card";
import { getTranslator } from "@/lib/i18n";

/** Shared layout of the two capture pages (need help, other city). */
export function EnquiryPage({
  kind,
  title,
  intro,
}: {
  kind: EnquiryKind;
  title: string;
  intro: string;
}) {
  const t = getTranslator("Enquiry");
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={title}
      description={intro}
      label={t("card.label")}
      note={t("card.note")}
    >
      <EnquiryForm kind={kind} />
    </HangingCard>
  );
}
