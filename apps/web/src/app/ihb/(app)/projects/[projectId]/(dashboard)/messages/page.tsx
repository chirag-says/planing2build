import { cn } from "cn";
import { MailIcon, PhoneIcon, UsersIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { contactHref } from "@/components/plan2build/overview";
import { SectionHeader } from "@/components/plan2build/page-header";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";
import { loadProject, projectTitle } from "@/lib/project";
import { getProjectOverview } from "@/lib/project-overview";
import { site } from "@/marketing/content/site";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return {
    title: await projectTitle((await params).projectId, getTranslator("Inbox")("messages.title")),
  };
}

interface Contact {
  id: string;
  name: string;
  firm: string | null;
  role: string;
  phone: string | null;
  email: string | null;
}

function ContactCard({ contact, current }: { contact: Contact; current: boolean }) {
  const t = getTranslator("Inbox");
  // An outside professional's one contact line may be a phone or an email: contactHref tells which.
  const links = [contact.phone, contact.email]
    .flatMap((value) => {
      const link = value ? contactHref(value) : null;
      return link && value ? [{ ...link, value }] : [];
    })
    .filter((link, index, all) => all.findIndex((other) => other.href === link.href) === index);
  return (
    <li
      id={`contact-${contact.id}`}
      aria-current={current ? "true" : undefined}
      className={cn(
        "flex scroll-mt-24 flex-col gap-3 rounded-lg bg-card p-4",
        current ? "ring-2 ring-foreground" : "ring-1 ring-foreground/15",
      )}
      data-testid="contact"
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <h4 className="text-lg font-semibold">{contact.name}</h4>
        {contact.firm && contact.firm !== contact.name && <p className="text-sm text-muted-foreground">{contact.firm}</p>}
        <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{contact.role}</p>
      </div>
      {links.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("messages.noContact")}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {links.map((link) => {
            const Icon = link.kind === "phone" ? PhoneIcon : MailIcon;
            const label = link.kind === "phone" ? "messages.callName" : "messages.emailName";
            return (
              <Button key={link.href} asChild variant="outline" size="sm">
                <a href={link.href} aria-label={t(label, { name: contact.name })}>
                  <Icon aria-hidden="true" data-icon="inline-start" />
                  <span className="break-all">{link.value}</span>
                </a>
              </Button>
            );
          })}
        </div>
      )}
    </li>
  );
}

// "Message" on the overview leads here (decided 2026-10-08: no sample data). The API has no
// messaging yet (OQ-025), so this is an honest contact page: the people engaged on the project
// with the phone and email the API shares (ProjectOverview.team), and Plan2Build's own contact.
// `?to=` marks the person the overview's button was for.
export default async function MessagesPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ to?: string | string[] }>;
}) {
  const [{ projectId }, { to }] = await Promise.all([params, searchParams]);
  const [detail, overview] = await Promise.all([loadProject(projectId), getProjectOverview(projectId)]);
  const t = getTranslator("Inbox");
  const o = getTranslator("Overview");
  const target = typeof to === "string" ? to : undefined;
  const team: Contact[] = overview.team.map((member) => ({
    id: member.id,
    name: member.name,
    firm: member.firm,
    role: member.outside ? `${member.role} · ${o("team.outside")}` : member.role,
    phone: member.phone,
    email: member.email,
  }));
  const plan2build: Contact = {
    id: "plan2build",
    name: site.name,
    firm: null,
    role: o("team.plan2buildRole"),
    phone: site.phone,
    email: site.email,
  };

  return (
    <section aria-labelledby="messages-title" className="flex flex-col gap-6">
      <SectionHeader
        id="messages-title"
        title={t("messages.title")}
        description={t("messages.intro", { code: detail.project.code })}
      />
      <Notice tone="info">
        <p>{t("messages.notAvailable")}</p>
      </Notice>
      <section aria-labelledby="team-contacts" className="flex flex-col gap-3">
        <SectionHeader id="team-contacts" level={3} title={t("messages.team")} />
        {team.length === 0 ? (
          <EmptyState
            icon={UsersIcon}
            title={t("messages.empty")}
            description={t("messages.emptyDetail")}
            action={
              <Button asChild variant="outline">
                <Link href={`/projects/${projectId}/services`}>{o("team.find")}</Link>
              </Button>
            }
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {team.map((contact) => (
              <ContactCard key={contact.id} contact={contact} current={contact.id === target} />
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="plan2build-contact" className="flex flex-col gap-3">
        <SectionHeader
          id="plan2build-contact"
          level={3}
          title={o("team.plan2build")}
          description={o("team.plan2buildBody")}
        />
        <ul className="grid gap-3 sm:grid-cols-2">
          <ContactCard contact={plan2build} current={target === "plan2build"} />
        </ul>
      </section>
    </section>
  );
}
