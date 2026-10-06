import { ArrowRightIcon, CalculatorIcon } from "lucide-react";
import Link from "next/link";

import { PageContainer } from "@/components/plan2build/page-header";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";

// Hero copy and the two calls to action are the client's own, from the S14 prototype
// (IHB_FLOW E1, E2). The rest of the public website waits for the client's content (W-01).
export default function IhbHome() {
  const t = getTranslator("Home");
  return (
    <PageContainer width="wide" className="justify-center sm:py-20">
      <section className="flex max-w-3xl flex-col gap-6">
        <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
          {t("title")}
        </h1>
        <p className="max-w-prose text-lg text-pretty text-muted-foreground">{t("lede")}</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href="/start">
              {t("start")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/estimate">
              <CalculatorIcon aria-hidden="true" data-icon="inline-start" />
              {t("estimate")}
            </Link>
          </Button>
        </div>
      </section>
    </PageContainer>
  );
}
