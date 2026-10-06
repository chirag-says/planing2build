// A listed professional in the public directory (D-01: public fields only). The "Champions Club"
// label is the name for every approved, listed professional (PD-18), never a tier.
import type { components } from "@p2b/contracts";
import { ArrowRightIcon, SendIcon, ShieldCheckIcon, UserRoundIcon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";

type Card = components["schemas"]["DirectoryCardOut"];

export function ChampionsBadge() {
  return (
    <Badge variant="success">
      <ShieldCheckIcon aria-hidden="true" />
      {getTranslator("Directory")("champions")}
    </Badge>
  );
}

export function ProfessionalFacts({ card }: { card: Card }) {
  const t = getTranslator("Directory");
  return (
    <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
      {card.base_locality && card.service_radius_km && (
        <li>{t("serves", { radius: card.service_radius_km, locality: card.base_locality })}</li>
      )}
      {card.years_experience !== null && card.years_experience !== undefined && (
        <li>{t("experience", { years: card.years_experience })}</li>
      )}
      {card.team_size ? <li>{t("team", { size: card.team_size })}</li> : null}
    </ul>
  );
}

/** `connect`: the family came from a project's service (Slice 3.4), so the card offers the request. */
export function ProfessionalCard({
  card,
  connect,
}: {
  card: Card;
  connect?: { projectId: string; category: string };
}) {
  const t = getTranslator("Directory");
  const name = card.display_name ?? card.firm_name ?? "";
  const query = connect ? `?project=${connect.projectId}&category=${connect.category}` : "";
  return (
    <Card size="sm" className="h-full">
      {card.cover_image_url ? (
        // Signed, short-lived links to approved portfolio photos; no image optimiser in between.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={card.cover_image_url} alt="" className="aspect-[4/3] w-full object-cover" loading="lazy" />
      ) : (
        <div className="-mt-(--card-spacing) flex aspect-[4/3] w-full items-center justify-center bg-muted text-muted-foreground">
          <UserRoundIcon aria-hidden="true" className="size-10" />
        </div>
      )}
      <CardHeader>
        <CardTitle className="text-base">
          <h2>{name}</h2>
        </CardTitle>
        {card.firm_name && card.firm_name !== name && (
          <p className="text-sm text-muted-foreground">{card.firm_name}</p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1">
          <ChampionsBadge />
          {card.categories.map((c) => (
            <Badge key={c.code} variant="neutral">{c.name}</Badge>
          ))}
        </div>
        <ProfessionalFacts card={card} />
      </CardContent>
      <CardFooter className="mt-auto flex flex-wrap gap-2">
        <Button asChild variant="outline">
          <Link href={`/professionals/${card.profile_id}${query}`} aria-label={`${t("view")}: ${name}`}>
            {t("view")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
        {connect && (
          <Button asChild>
            <Link
              href={`/projects/${connect.projectId}/services/connect?category=${connect.category}&profile=${card.profile_id}`}
              aria-label={`${getTranslator("Services")("request")}: ${name}`}
            >
              <SendIcon aria-hidden="true" />
              {getTranslator("Services")("request")}
            </Link>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
