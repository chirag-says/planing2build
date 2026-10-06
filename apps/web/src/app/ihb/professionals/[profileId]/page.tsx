import { ArrowLeftIcon, CheckIcon, SendIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { cache } from "react";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ChampionsBadge, ProfessionalFacts } from "@/components/plan2build/professional-card";
import { Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const loadProfile = cache(async (profileId: string) => {
  if (!UUID.test(profileId)) notFound();
  const response = await (await serverApi()).GET("/api/v1/public/professionals/{profile_id}", {
    params: { path: { profile_id: profileId } },
  });
  if (response.response.status === 404) notFound();
  if (!response.data) throw new Error("the profile could not be loaded");
  return response.data;
});

export async function generateMetadata({ params }: { params: Promise<{ profileId: string }> }): Promise<Metadata> {
  const profile = await loadProfile((await params).profileId);
  return { title: profile.display_name ?? profile.firm_name ?? getTranslator("Directory")("profileTitle") };
}

// A listed professional's public profile (D-01): what they told us, what Plan2Build verified,
// and approved portfolio photos. No phone, email or website; connecting is a package service.
export default async function ProfessionalProfilePage({
  params,
  searchParams,
}: {
  params: Promise<{ profileId: string }>;
  searchParams: Promise<{ project?: string; category?: string }>;
}) {
  const { profileId } = await params;
  const profile = await loadProfile(profileId);
  const { project, category } = await searchParams;
  // From a project's service (Slice 3.4): offer the connection request for that category.
  const connect =
    project && UUID.test(project) && category && profile.categories.some((c) => c.code === category)
      ? `/projects/${project}/services/connect?category=${category}&profile=${profileId}`
      : null;
  const back = project && UUID.test(project) && category ? `/professionals?project=${project}&category=${category}` : "/professionals";
  const t = getTranslator("Directory");
  const checks = getTranslator("Checks");
  const name = profile.display_name ?? profile.firm_name ?? t("profileTitle");

  return (
    <PageContainer width="wide">
      <Button asChild variant="ghost" className="self-start">
        <Link href={back}>
          <ArrowLeftIcon aria-hidden="true" />
          {t("back")}
        </Link>
      </Button>
      <PageHeader
        title={name}
        description={profile.firm_name && profile.firm_name !== name ? profile.firm_name : undefined}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ChampionsBadge />
            {connect && (
              <Button asChild>
                <Link href={connect}>
                  <SendIcon aria-hidden="true" />
                  {getTranslator("Services")("request")}
                </Link>
              </Button>
            )}
          </div>
        }
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          {profile.bio && (
            <section aria-labelledby="about" className="flex flex-col gap-2">
              <h2 id="about" className="font-heading text-lg font-medium">{t("about")}</h2>
              <p className="whitespace-pre-line text-muted-foreground">{profile.bio}</p>
            </section>
          )}
          <section aria-labelledby="portfolio" className="flex flex-col gap-3">
            <h2 id="portfolio" className="font-heading text-lg font-medium">{t("portfolio")}</h2>
            {profile.portfolio.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("noPortfolio")}</p>
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2">
                {profile.portfolio.map((item, i) => (
                  <li key={`${item.caption}-${i}`}>
                    <figure className="flex flex-col gap-2">
                      {item.image_url && (
                        // Signed, short-lived links to approved photos; no image optimiser in between.
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={item.image_url} alt={item.caption} loading="lazy"
                          className="aspect-[4/3] w-full rounded-lg object-cover ring-1 ring-border" />
                      )}
                      <figcaption className="text-sm text-muted-foreground">{item.caption}</figcaption>
                    </figure>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <aside className="order-first flex flex-col gap-6 lg:order-none">
          <Card size="sm">
            <CardContent>
              <ProfessionalFacts card={profile} />
            </CardContent>
          </Card>
          {profile.categories.map((category) => (
            <Card size="sm" key={category.code}>
              <CardHeader>
                <CardTitle className="text-base"><h2>{category.name}</h2></CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {category.subtypes.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {category.subtypes.map((s) => <Badge key={s} variant="neutral">{s}</Badge>)}
                  </div>
                )}
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-medium">{t("verification")}</h3>
                  <ul className="flex flex-col gap-1 text-sm">
                    {category.verified.map((kind) => (
                      <li key={kind} className="flex items-center gap-2">
                        <CheckIcon aria-hidden="true" className="size-4 text-success" />
                        {checks(`verified.${kind}`)}
                      </li>
                    ))}
                    {category.registrations.map((r, i) => (
                      <li key={`${r.number}-${i}`} className="text-muted-foreground">
                        {t("registration", { issuer: r.issuer ?? "", number: r.number ?? "" })}
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          ))}
          {!connect && <Notice tone="info">{t("contact")}</Notice>}
        </aside>
      </div>
    </PageContainer>
  );
}
