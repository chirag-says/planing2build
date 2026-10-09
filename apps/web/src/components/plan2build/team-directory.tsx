// Meet your team: every professional engaged on the project, one card each with their phone and
// email in plain sight and the ways to reach them, then Plan2Build and the independent auditor.
// Reads the ProjectOverview's team (lib/project-overview.ts): approved engagements only.
import { ArrowRightIcon, MailIcon, PhoneIcon, ShieldCheckIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ContactActions, Monogram, Standing, contactHref } from "@/components/plan2build/overview";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import type { ProjectOverview, TeamMember } from "@/lib/project-overview";

function Detail({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <p className="flex min-w-0 items-center gap-2 text-base">
      <span aria-hidden="true" className="text-muted-foreground [&>svg]:size-4">
        {icon}
      </span>
      <span className="min-w-0 truncate">{children}</span>
    </p>
  );
}

function MemberCard({ member, base }: { member: TeamMember; base: string }) {
  const o = getTranslator("Overview");
  const name = member.firm ?? member.name;
  const phone = contactHref(member.phone);
  const email = contactHref(member.email);
  return (
    <li className="flex flex-col gap-4 rounded-lg bg-card p-5 ring-1 ring-foreground/15">
      <div className="flex items-start gap-4">
        <Monogram name={name} large />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="flex flex-wrap items-center gap-2 font-mono text-xs tracking-widest uppercase">
            {member.primary && (
              <span className="rounded-sm bg-brand px-1.5 py-0.5 text-brand-foreground ring-1 ring-foreground">
                {o("team.primary")}
              </span>
            )}
            <span className="text-muted-foreground">{member.role}</span>
          </p>
          <h2 className="font-heading text-2xl leading-none text-balance">{name}</h2>
          {member.firm && member.name !== member.firm && <p className="text-base text-muted-foreground">{member.name}</p>}
          <Standing member={member} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5 border-t border-foreground/15 pt-3">
        <Detail icon={<PhoneIcon />}>
          {phone ? (
            <a href={phone.href} className="font-mono tracking-wider tabular-nums underline-offset-4 hover:underline">
              {member.phone}
            </a>
          ) : (
            <span className="text-muted-foreground">{o("team.noContact")}</span>
          )}
        </Detail>
        <Detail icon={<MailIcon />}>
          {email ? (
            <a href={email.href} className="underline-offset-4 hover:underline">
              {member.email}
            </a>
          ) : (
            <span className="text-muted-foreground">{o("teamPage.noEmail")}</span>
          )}
        </Detail>
        <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
          {o("teamPage.since", { date: formatDate(member.since) })}
        </p>
      </div>
      <ContactActions name={name} contact={member.phone ?? member.email} />
    </li>
  );
}

export function TeamDirectory({
  overview,
  base,
  plan2build,
}: {
  overview: ProjectOverview;
  base: string;
  plan2build: { phone: string };
}) {
  const o = getTranslator("Overview");
  const p2bPhone = contactHref(plan2build.phone);
  return (
    <div className="flex flex-col gap-8">
      {overview.team.length === 0 ? (
        <div className="p2b-blueprint flex flex-col gap-3 rounded-lg p-6 ring-1 ring-foreground/15">
          <p className="text-lg font-semibold">{o("teamPage.none")}</p>
          <p className="max-w-prose text-base text-muted-foreground">{o("teamPage.noneBody")}</p>
          <Button asChild variant="outline" className="self-start">
            <Link href={`/professionals?project=${overview.project.id}`}>
              {o("team.find")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </div>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {overview.team.map((member) => (
            <MemberCard key={member.id} member={member} base={base} />
          ))}
        </ul>
      )}

      <section aria-labelledby="also-title" className="flex flex-col gap-4">
        <h2 id="also-title" className="border-t-2 border-foreground pt-4 font-heading text-2xl leading-none">
          {o("team.plan2buildRole")}
        </h2>
        <ul className="grid gap-4 md:grid-cols-2">
          <li className="flex flex-col gap-4 rounded-lg bg-card p-5 ring-1 ring-foreground/15">
            <div className="flex items-start gap-4">
              <span aria-hidden="true" className="ov-monogram is-brand font-mono">
                P2B
              </span>
              <div className="flex min-w-0 flex-col gap-1">
                <h3 className="font-heading text-2xl leading-none">{o("team.plan2build")}</h3>
                <p className="text-base text-pretty text-muted-foreground">{o("team.plan2buildBody")}</p>
              </div>
            </div>
            <Detail icon={<PhoneIcon />}>
              {p2bPhone ? (
                <a href={p2bPhone.href} className="font-mono tracking-wider tabular-nums underline-offset-4 hover:underline">
                  {plan2build.phone}
                </a>
              ) : (
                plan2build.phone
              )}
            </Detail>
            <ContactActions
              name={o("team.plan2build")}
              contact={plan2build.phone}
            />
          </li>
          {overview.assurance && (
            <li className="flex flex-col gap-3 rounded-lg bg-card p-5 ring-1 ring-foreground/15">
              <div className="flex items-start gap-4">
                <span aria-hidden="true" className="ov-monogram">
                  <ShieldCheckIcon className="size-5" />
                </span>
                <div className="flex min-w-0 flex-col gap-1">
                  <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{o("team.assurance")}</p>
                  <h3 className="font-heading text-2xl leading-none">
                    {overview.assurance.auditorCode
                      ? o("team.auditor", { code: overview.assurance.auditorCode })
                      : o("team.auditorNone")}
                  </h3>
                  <p className="text-base text-pretty text-muted-foreground">
                    {overview.assurance.auditorCode ? o("team.auditorBody") : o("team.auditorBodyNone")}
                  </p>
                </div>
              </div>
            </li>
          )}
        </ul>
      </section>
    </div>
  );
}
