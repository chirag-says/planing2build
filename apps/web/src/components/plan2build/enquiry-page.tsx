import type { EnquiryKind } from "@p2b/contracts";

import { EnquiryForm } from "@/components/plan2build/enquiry-form";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Card, CardContent } from "@/components/ui/card";

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
  return (
    <PageContainer width="narrow">
      <PageHeader title={title} description={intro} />
      <Card>
        <CardContent>
          <EnquiryForm kind={kind} />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
