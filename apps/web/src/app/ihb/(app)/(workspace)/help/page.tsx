import { MailIcon, PhoneIcon } from "lucide-react";
import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";
import { site } from "@/marketing/content/site";
import { telHref } from "@/marketing/lib/text";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Help")("title") };

// "Need help?" inside the product: how to reach the Plan2Build team. The public enquiry forms
// (renovation leads, other cities) are for families Plan2Build cannot serve yet, never for a
// signed-in family with a project (decided 2026-10-08).
export default async function HelpPage() {
  await requireSignedIn("/help");
  const t = getTranslator("Help");
  return (
    <PageContainer>
      <PageHeader title={t("title")} description={t("intro")} />
      <Card>
        <CardContent className="flex flex-col gap-4">
          <p className="text-base">{t("hours", { hours: site.hours })}</p>
          <div className="flex flex-wrap gap-3">
            {site.phone && (
              <Button asChild size="lg">
                <a href={telHref(site.phone)}>
                  <PhoneIcon aria-hidden="true" data-icon="inline-start" />
                  {t("call", { phone: site.phone })}
                </a>
              </Button>
            )}
            <Button asChild size="lg" variant={site.phone ? "outline" : "default"}>
              <a href={`mailto:${site.email}`}>
                <MailIcon aria-hidden="true" data-icon="inline-start" />
                {t("email", { email: site.email })}
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageContainer>
  );
}
