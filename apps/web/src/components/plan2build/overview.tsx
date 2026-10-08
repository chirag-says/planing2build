// The project overview as a command center (homeowner brief v3, 2026-10-08): which home this is and
// where it stands, the one next step, how far it has come, who is building it and how to reach
// them, what changed. Everything else has its own page. Every section reads the ProjectOverview
// model (lib/project-overview.ts), never raw API responses. Facts only: counts, never percentages
// or forecasts (EX-02, EX-04), and no money (EX-05). One motion per section, each played once:
// the blueprint draws over the house, the stage marker switches on, the marks fill, the timeline
// steps in.
import { cn } from "cn";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  CheckCheckIcon,
  ClipboardCheckIcon,
  DraftingCompassIcon,
  FileCheck2Icon,
  HandshakeIcon,
  HardHatIcon,
  MailIcon,
  MessageSquareTextIcon,
  PhoneIcon,
  ScaleIcon,
  SendIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserPlusIcon,
  type LucideIcon,
} from "lucide-react";
import Image, { type StaticImageData } from "next/image";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { BuildProgress } from "@/components/plan2build/build-progress";
import { IllustrativeBadge } from "@/components/plan2build/design-gallery";
import { Eyebrow } from "@/components/plan2build/page-header";
import { RevealOnView } from "@/components/plan2build/reveal-on-view";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dayGroup } from "@/lib/inbox";
import { PHASES, type NextAction, type Phase, type PhaseState } from "@/lib/journey";
import type { ActivityItem, ActivityKind, ProjectOverview, TeamMember } from "@/lib/project-overview";
import { initialsOf } from "@/lib/session";
import "./overview.css";

const order = (index: number) => ({ "--i": index }) as CSSProperties;

/** A phone number or an email as a link target; null when there is nothing to call or write to. */
export function contactHref(value: string | null): { href: string; kind: "phone" | "email" } | null {
  if (!value) return null;
  if (value.includes("@")) return { href: `mailto:${value.trim()}`, kind: "email" };
  const digits = value.replace(/[^\d+]/g, "");
  return digits.length >= 6 ? { href: `tel:${digits}`, kind: "phone" } : null;
}

/* 1. The greeting ------------------------------------------------------------------------- */

export function OverviewGreeting({ name }: { name: string | null }) {
  const o = getTranslator("Overview");
  return (
    <header className="flex flex-col gap-2">
      <h1 className="p2b-rise-clip font-heading text-4xl leading-none sm:text-5xl">
        <span className="p2b-rise-in">{name ? o("greeting.named", { name }) : o("greeting.plain")}</span>
      </h1>
      <p className="text-lg text-pretty text-muted-foreground">{o("sub")}</p>
    </header>
  );
}

/* 2. The home ----------------------------------------------------------------------------- */

/** The surveyor's lines drawn over the concept image: frame, thirds and the two dimension lines. */
function BlueprintOverlay() {
  return (
    <svg className="ov-blueprint" viewBox="0 0 400 300" preserveAspectRatio="none" aria-hidden="true">
      <g className="ov-bp-lines">
        <path pathLength={1} d="M16 16H384V284H16Z" />
        <path pathLength={1} d="M16 106H384M16 196H384M138 16V284M262 16V284" className="ov-bp-thin" />
        <path pathLength={1} d="M16 7H384M16 3V11M384 3V11" />
        <path pathLength={1} d="M393 16V284M389 16H397M389 284H397" />
      </g>
      <g className="ov-bp-marks">
        <rect x="12" y="12" width="8" height="8" />
        <rect x="380" y="280" width="8" height="8" />
      </g>
    </svg>
  );
}

const HOME_FACTS = ["bedrooms", "built_up_area_sqft", "floors", "quality_tier"] as const;

export function HomeVisual({ overview, base }: { overview: ProjectOverview; base: string }) {
  const o = getTranslator("Overview");
  const designs = getTranslator("Designs");
  const hero = overview.heroDesign;
  const place = overview.project.locality;
  const facts = HOME_FACTS.flatMap((key) => overview.facts.filter((fact) => fact.key === key));
  const quota = overview.designQuota;
  // When the next step is the first design, the board offers it; the frame only counts what is left.
  const designFirst = overview.actions.find((action) => action.kind === "act")?.key === "generateDesign";
  return (
    <section aria-labelledby="home-title" className="flex min-w-0 flex-col gap-4">
      <div className={cn("ov-home", hero ? "is-photo" : "is-drawing")}>
        {hero ? (
          <>
            <div className="ov-home-photo p2b-unmask">
              {/* Signed, short-lived links to private storage: no image optimiser in between. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={hero.image_url!}
                alt={designs("imageAlt", {
                  view: designs(`viewShort.${hero.view}`),
                  number: hero.sequence,
                })}
                className="p2b-unmask-img"
              />
            </div>
            <BlueprintOverlay />
            <span className="ov-home-badge">
              <IllustrativeBadge />
            </span>
          </>
        ) : (
          <div className="ov-home-drawing">
            <BuildProgress
              stages={overview.stages}
              floorsAbove={overview.floorsAbove}
              label={(s) => `${s.stage_number}. ${s.name}`}
            />
          </div>
        )}
        <p className="ov-home-tag font-mono" aria-hidden="true">
          <span className="ov-home-marker" />
          {o("home.label")}
        </p>
        {facts.length > 0 && (
          <dl className="ov-home-facts" aria-label={o("facts.title")}>
            {facts.map((fact) => (
              <div key={fact.key}>
                <dt className="font-mono">{o(`facts.${fact.key}`)}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <h2 id="home-title" className="font-heading text-2xl leading-none">
            {place ? o("home.place", { place }) : o("home.label")}
          </h2>
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            {hero ? o("home.illustrativeNote") : overview.stages.length ? o("home.drawingBuild") : o("home.drawing")}
          </p>
        </div>
        {quota && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
              {o("home.free", {
                remaining: quota.freeRemaining,
                total: quota.freeTotal,
              })}
            </p>
            {quota.canGenerate ? (
              !designFirst && (
              <Button asChild variant="outline" size="sm">
                <Link href={`${base}/designs`}>
                  <SparklesIcon aria-hidden="true" data-icon="inline-start" />
                  {designs("generate")}
                </Link>
              </Button>
              )
            ) : (
              quota.count > 0 && (
                <Link href={`${base}/designs`} className="ov-link">
                  {designs("seeAll")}
                  <ArrowRightIcon aria-hidden="true" />
                </Link>
              )
            )}
          </div>
        )}
      </div>
    </section>
  );
}

/* 3. Where the project is ---------------------------------------------------------------- */

const RAIL: Record<PhaseState, string> = {
  done: "is-done",
  current: "is-current",
  alongside: "is-alongside",
  next: "is-next",
};

function phaseNote(overview: ProjectOverview, phase: Phase): string {
  const o = getTranslator("Overview");
  const fact = overview.phaseNotes[phase];
  if (fact) return o(`notes.${fact.key}`, fact.values);
  return phase === "plan" ? o("notes.planFree") : o(`notes.${phase}`);
}

export function StagePanel({ overview, base }: { overview: ProjectOverview; base: string }) {
  const o = getTranslator("Overview");
  const phase = overview.phase;
  const n = phase ? PHASES.indexOf(phase) + 1 : null;
  return (
    <section aria-labelledby="stage-title" className="ov-stage flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Eyebrow>{o("stage.label")}</Eyebrow>
        <StatusBadge kind="project" status={overview.project.status} withLabel />
      </div>
      <div className="flex items-end gap-4">
        {n && (
          <p className="ov-stage-num" aria-hidden="true">
            <span className="p2b-rise-clip">
              <span className="p2b-rise-in font-heading">{String(n).padStart(2, "0")}</span>
            </span>
            <span className="font-mono">/ 07</span>
          </p>
        )}
        <h2 id="stage-title" className="font-heading text-5xl leading-[0.85] sm:text-6xl">
          {phase && n && <span className="sr-only">{o("stage.aria", { n, phase: o(`phases.${phase}`) })}</span>}
          <span aria-hidden={phase ? true : undefined}>{phase ? o(`phases.${phase}`) : o("stage.paused")}</span>
        </h2>
      </div>
      <ol className="ov-rail" aria-label={o("stage.railLabel")}>
        {PHASES.map((key, index) => (
          <li key={key} className={RAIL[overview.phases[key]]} style={order(index)}>
            <span className="ov-rail-bar" aria-hidden="true" />
            <span className="ov-rail-name font-mono" aria-hidden="true">
              {o(`phases.${key}`)}
            </span>
            <span className="sr-only">
              {o(`phases.${key}`)}: {o(`journey.states.${overview.phases[key]}`)}
            </span>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <p className="text-base text-pretty text-muted-foreground">
          {phase ? phaseNote(overview, phase) : o("stage.pausedNote")}
        </p>
        <Link href={`${base}/journey`} className="ov-link">
          {o("stage.viewJourney")}
          <ArrowRightIcon aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}

export function actionCopy(action: NextAction) {
  const o = getTranslator("Overview");
  const projects = getTranslator("Projects");
  const key = action.key;
  const cta =
    key === "finishRequirement"
      ? projects("continue")
      : key === "answerQuestions"
        ? projects("update")
        : o(`actions.${key}.cta`);
  return {
    title: o(`actions.${key}.title`, action.values),
    body: o(`actions.${key}.body`, action.values),
    cta,
  };
}

/**
 * The one next step: the dark board with the brass button, and at most two more things waiting on
 * the family under it. With nothing to do, it says who is acting.
 */
export function NextStep({
  overview,
  base,
  waiting,
  children,
}: {
  overview: ProjectOverview;
  base: string;
  waiting: { title: string; body: string } | null;
  children?: ReactNode;
}) {
  const o = getTranslator("Overview");
  const [primary, ...rest] = overview.actions.filter((action) => action.kind === "act");
  if (!primary && !waiting) return null;
  const lead = primary ? actionCopy(primary) : { ...waiting!, cta: null };
  const more = [...rest, ...overview.actions.filter((action) => action.kind === "watch")].slice(0, 2);
  return (
    <section
      aria-labelledby="next-title"
      className="surface-dark ov-next overflow-hidden rounded-lg bg-background text-foreground ring-1 ring-foreground"
    >
      <div className="flex flex-col gap-3 p-5 sm:p-6">
        <Eyebrow>{o("next.eyebrow")}</Eyebrow>
        <span aria-hidden="true" className="p2b-beam" />
        <h2 id="next-title" className="font-heading text-3xl leading-none text-balance">
          {lead.title}
        </h2>
        <p className="max-w-prose text-base text-pretty text-muted-foreground">{lead.body}</p>
        {children}
        {primary && lead.cta && (
          <Button asChild size="lg" className="mt-1 bg-brand text-brand-foreground sm:self-start">
            <Link href={`${base}${primary.path}`}>
              {lead.cta}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        )}
      </div>
      {more.length > 0 && (
        <div className="border-t border-foreground/15 px-5 pt-3 pb-2 sm:px-6">
          <h3 className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{o("next.also")}</h3>
          <ul className="flex flex-col">
            {more.map((action, index) => (
              <li key={`${action.key}-${index}`} className="border-b border-foreground/15 last:border-b-0">
                <Link
                  href={`${base}${action.path}`}
                  className="group flex min-h-11 items-center justify-between gap-3 rounded-md py-2 text-base font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {actionCopy(action).title}
                  <ArrowRightIcon
                    aria-hidden="true"
                    className="size-4 shrink-0 text-brand transition-transform group-hover:translate-x-1"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/* 4. How far it has come ----------------------------------------------------------------- */

type GaugeKey = "planning" | "construction" | "verification" | "decisions" | "payments";

function Marks({ done, total, label }: { done: number; total: number; label: string }) {
  return (
    <span className="ov-marks" role="img" aria-label={label}>
      {Array.from({ length: total }, (_, index) => (
        <span key={index} className={index < done ? "is-on" : undefined} style={order(index)} />
      ))}
    </span>
  );
}

export function StandingPanel({ overview }: { overview: ProjectOverview }) {
  const o = getTranslator("Overview");
  const { progress } = overview;
  const planningDone = progress.planning.filter((step) => step.done).length;
  const nextStep = progress.planning.find((step) => !step.done);
  const gauges: Array<{
    key: GaugeKey;
    value: { done: number; total: number } | null;
    caption: string;
  }> = [
    {
      key: "planning",
      value: { done: planningDone, total: progress.planning.length },
      caption: nextStep
        ? o("standing.next", { step: o(`standing.steps.${nextStep.key}`) })
        : o("standing.planningDone"),
    },
    {
      key: "construction",
      value: progress.construction,
      caption: o("standing.unit.construction"),
    },
    {
      key: "verification",
      value: progress.verification,
      caption: o("standing.unit.verification"),
    },
    {
      key: "decisions",
      value: progress.decisions,
      caption: o("standing.unit.decisions"),
    },
    {
      key: "payments",
      value: progress.payments,
      caption: o("standing.unit.payments"),
    },
  ];
  return (
    <section aria-labelledby="standing-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-1 border-t-2 border-foreground pt-4">
        <h2 id="standing-title" className="font-heading text-2xl leading-none">
          {o("standing.title")}
        </h2>
        <p className="text-sm text-muted-foreground">{o("standing.intro")}</p>
      </div>
      <RevealOnView as="ul" className="ov-gauges">
        {gauges.map((gauge, index) => (
          <li key={gauge.key} className={cn("ov-gauge", !gauge.value && "is-empty")} style={order(index)}>
            <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
              {o(`standing.${gauge.key}`)}
            </p>
            {gauge.value ? (
              <>
                <p className="ov-gauge-value font-heading" aria-hidden="true">
                  {gauge.value.done}
                  <span className="font-mono"> / {gauge.value.total}</span>
                </p>
                <Marks
                  done={gauge.value.done}
                  total={gauge.value.total}
                  label={o("standing.aria", {
                    label: o(`standing.${gauge.key}`),
                    done: gauge.value.done,
                    total: gauge.value.total,
                    unit: o(`standing.unit.${gauge.key}`),
                  })}
                />
                <p className="text-sm text-muted-foreground">{gauge.caption}</p>
              </>
            ) : (
              <>
                <p className="ov-gauge-value font-heading text-muted-foreground" aria-hidden="true">
                  0
                </p>
                <span className="ov-marks is-none" aria-hidden="true" />
                <p className="text-sm text-muted-foreground">
                  {o(`standing.notYet.${gauge.key as Exclude<GaugeKey, "planning">}`)}
                </p>
              </>
            )}
          </li>
        ))}
      </RevealOnView>
    </section>
  );
}

/* 5. The team ------------------------------------------------------------------------------ */

function ContactActions({
  name,
  contact,
  messageHref,
  compact = false,
}: {
  name: string;
  contact: string | null;
  messageHref: string;
  compact?: boolean;
}) {
  const o = getTranslator("Overview");
  const link = contactHref(contact);
  const Icon = link?.kind === "email" ? MailIcon : PhoneIcon;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {!link && (
        <Button
          type="button"
          disabled
          size={compact ? "sm" : "default"}
          variant="outline"
          aria-label={o("team.noPhoneName", { name })}
          title={o("team.noContact")}
        >
          <PhoneIcon aria-hidden="true" data-icon="inline-start" />
          <span className={cn(compact && "max-sm:sr-only")}>{o("team.call")}</span>
        </Button>
      )}
      {link && (
        <Button
          asChild
          size={compact ? "sm" : "default"}
          variant={compact ? "outline" : "default"}
          className={cn(!compact && "bg-brand text-brand-foreground")}
        >
          <a
            href={link.href}
            aria-label={link.kind === "phone" ? o("team.callName", { name }) : o("team.email", { name })}
          >
            <Icon aria-hidden="true" data-icon="inline-start" />
            <span className={cn(compact && "max-sm:sr-only")}>
              {link.kind === "phone" ? o("team.call") : o("team.emailShort")}
            </span>
          </a>
        </Button>
      )}
      <Button asChild size={compact ? "sm" : "default"} variant="outline">
        <Link href={messageHref} aria-label={o("team.messageName", { name })}>
          <MessageSquareTextIcon aria-hidden="true" data-icon="inline-start" />
          <span className={cn(compact && "max-sm:sr-only")}>{o("team.message")}</span>
        </Link>
      </Button>
    </div>
  );
}

function Monogram({ name, large }: { name: string; large?: boolean }) {
  return (
    <span aria-hidden="true" className={cn("ov-monogram font-mono", large && "is-large")}>
      {initialsOf(name) ?? "P"}
    </span>
  );
}

function Standing({ member }: { member: TeamMember }) {
  const o = getTranslator("Overview");
  return member.outside ? (
    <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">{o("team.own")}</span>
  ) : (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs tracking-wider text-foreground uppercase">
      <ShieldCheckIcon aria-hidden="true" className="size-3.5 text-success" />
      {o("team.approved")}
    </span>
  );
}

function PrimaryContact({ member, base }: { member: TeamMember; base: string }) {
  const o = getTranslator("Overview");
  const name = member.firm ?? member.name;
  return (
    <article className="ov-person is-primary">
      <p className="flex flex-wrap items-center gap-2 font-mono text-xs tracking-widest uppercase">
        <span className="rounded-sm bg-brand px-1.5 py-0.5 text-brand-foreground ring-1 ring-foreground">
          {o("team.primary")}
        </span>
        <span className="text-muted-foreground">{member.role}</span>
      </p>
      <div className="flex items-center gap-4">
        <Monogram name={name} large />
        <div className="flex min-w-0 flex-col gap-1.5">
          <h3 className="font-heading text-3xl leading-none text-balance">{name}</h3>
          {member.firm && member.name !== member.firm && (
            <p className="text-base text-muted-foreground">{member.name}</p>
          )}
          <Standing member={member} />
        </div>
      </div>
      {member.phone ? (
        <p className="flex items-center gap-2 font-mono text-sm tracking-wider tabular-nums">
          <PhoneIcon aria-hidden="true" className="size-4 text-muted-foreground" />
          {member.phone}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">{o("team.noContact")}</p>
      )}
      <ContactActions
        name={name}
        contact={member.phone ?? member.email}
        messageHref={`${base}/messages?to=${member.id}`}
      />
    </article>
  );
}

function TeamRow({
  name,
  role,
  detail,
  monogram,
  actions,
}: {
  name: string;
  role: string;
  detail: ReactNode;
  monogram: ReactNode;
  actions: ReactNode;
}) {
  return (
    <li className="ov-person-row">
      {monogram}
      <div className="flex min-w-0 flex-col gap-1">
        <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{role}</p>
        <h3 className="text-lg leading-tight font-semibold text-balance">{name}</h3>
        {detail}
      </div>
      {actions && <div className="ov-person-actions">{actions}</div>}
    </li>
  );
}

export function TeamSection({
  overview,
  base,
  plan2build,
}: {
  overview: ProjectOverview;
  base: string;
  plan2build: { phone: string };
}) {
  const o = getTranslator("Overview");
  const [primary, ...others] = overview.team;
  return (
    <section aria-labelledby="team-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3 border-t-2 border-foreground pt-4">
        <h2 id="team-title" className="font-heading text-2xl leading-none">
          {o("team.title")}
        </h2>
        <Link href={`${base}/services`} className="ov-link">
          {o("team.viewTeam")}
          <ArrowRightIcon aria-hidden="true" />
        </Link>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {primary ? (
          <PrimaryContact member={primary} base={base} />
        ) : (
          <div className="ov-person is-empty p2b-blueprint">
            <p className="text-lg font-semibold">{o("team.empty")}</p>
            <p className="text-base text-muted-foreground">{o("team.emptyBody")}</p>
            <Button asChild variant="outline" className="self-start">
              <Link href={`/professionals?project=${overview.project.id}`}>
                {o("team.find")}
                <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
              </Link>
            </Button>
          </div>
        )}
        <ul className="ov-team-list">
          {others.map((member) => {
            const name = member.firm ?? member.name;
            return (
              <TeamRow
                key={member.id}
                name={name}
                role={member.role}
                monogram={<Monogram name={name} />}
                detail={<Standing member={member} />}
                actions={
                  <ContactActions
                    name={name}
                    contact={member.phone ?? member.email}
                    messageHref={`${base}/messages?to=${member.id}`}
                    compact
                  />
                }
              />
            );
          })}
          {overview.assurance && (
            <TeamRow
              name={
                overview.assurance.auditorCode
                  ? o("team.auditor", { code: overview.assurance.auditorCode })
                  : o("team.auditorNone")
              }
              role={o("team.assurance")}
              monogram={
                <span aria-hidden="true" className="ov-monogram">
                  <ShieldCheckIcon className="size-5" />
                </span>
              }
              detail={
                <p className="text-sm text-pretty text-muted-foreground">
                  {overview.assurance.auditorCode ? o("team.auditorBody") : o("team.auditorBodyNone")}
                </p>
              }
              actions={null}
            />
          )}
          <TeamRow
            name={o("team.plan2build")}
            role={o("team.plan2buildRole")}
            monogram={
              <span aria-hidden="true" className="ov-monogram is-brand font-mono">
                P2B
              </span>
            }
            detail={<p className="text-sm text-pretty text-muted-foreground">{o("team.plan2buildBody")}</p>}
            actions={
              <ContactActions
                name={o("team.plan2build")}
                contact={plan2build.phone}
                messageHref={`${base}/messages?to=plan2build`}
                compact
              />
            }
          />
        </ul>
      </div>
    </section>
  );
}

/* 6. What changed -------------------------------------------------------------------------- */

const ACTIVITY_ICON: Record<ActivityKind, LucideIcon> = {
  submitted: ClipboardCheckIcon,
  design: SparklesIcon,
  planIssued: DraftingCompassIcon,
  planAccepted: FileCheck2Icon,
  quotesRequested: SendIcon,
  quotesCompared: ScaleIcon,
  contractorChosen: HandshakeIcon,
  teamJoined: UserPlusIcon,
  stageStarted: HardHatIcon,
  stageDone: CheckCheckIcon,
  inspectionPassed: ShieldCheckIcon,
  findingClosed: ClipboardCheckIcon,
};

export function activityText(item: ActivityItem): string {
  return getTranslator("Overview")(`activity.items.${item.kind}`, item.values);
}

export function whenText(at: string, now: string): string {
  const o = getTranslator("Overview");
  const group = dayGroup(at, now);
  return group === "earlier" ? formatDate(at) : o(`activity.when.${group}`);
}

export function ActivityIcon({ kind, className }: { kind: ActivityKind; className?: string }) {
  const Icon = ACTIVITY_ICON[kind];
  return <Icon aria-hidden="true" className={className} />;
}

export function ActivityTimeline({ overview, base, now }: { overview: ProjectOverview; base: string; now: string }) {
  const o = getTranslator("Overview");
  const items = overview.activity.slice(0, 5);
  return (
    <section aria-labelledby="activity-title" className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3 border-t-2 border-foreground pt-4">
        <h2 id="activity-title" className="font-heading text-2xl leading-none">
          {o("activity.title")}
        </h2>
        {overview.activity.length > 0 && (
          <Link href={`${base}/notifications`} className="ov-link">
            {o("activity.all")}
            <ArrowRightIcon aria-hidden="true" />
          </Link>
        )}
      </div>
      {items.length === 0 ? (
        <p className="text-base text-muted-foreground">{o("activity.empty")}</p>
      ) : (
        <RevealOnView as="ol" className="ov-timeline">
          {items.map((item, index) => (
            <li key={item.id} className="ov-tl-item" style={order(index)}>
              <span className="ov-tl-node">
                <ActivityIcon kind={item.kind} className="size-4" />
              </span>
              <div className="flex min-w-0 flex-col gap-0.5 pt-1.5">
                <p className="text-base font-medium text-pretty">{activityText(item)}</p>
                <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
                  <time dateTime={item.at}>{whenText(item.at, now)}</time>
                </p>
              </div>
            </li>
          ))}
        </RevealOnView>
      )}
    </section>
  );
}

/* 7. The rest, one line each -------------------------------------------------------------- */

export function ProjectSnapshot({ overview, base }: { overview: ProjectOverview; base: string }) {
  const o = getTranslator("Overview");
  const t = getTranslator("Dashboard");
  const { pkg } = overview;
  const open = overview.estimate !== null;
  const draft = overview.project.status === "DRAFT" || overview.project.status === "NEEDS_INFO";
  const links = [
    {
      href: draft ? `${base}/requirement` : `${base}/answers`,
      label: o("snapshot.requirement"),
    },
    ...(open ? [{ href: `${base}/estimate`, label: o("snapshot.estimate") }] : []),
  ];
  return (
    <section aria-labelledby="snapshot-title" className="ov-snapshot">
      <h2 id="snapshot-title" className="font-heading text-xl leading-none">
        {o("snapshot.title")}
      </h2>
      <dl className="flex flex-col">
        <div className="ov-snap-row">
          <dt className="font-mono">{o("snapshot.code")}</dt>
          <dd className="font-mono tabular-nums">{overview.project.code}</dd>
        </div>
        {open && (
          <div className="ov-snap-row">
            <dt className="font-mono">{o("snapshot.package")}</dt>
            <dd className="flex flex-col items-end gap-1 text-right">
              <span className="font-semibold">
                {o(
                  `snapshot.packageState.${pkg.state === "ACTIVE" ? "ACTIVE" : pkg.state === "NOT_ACTIVE" ? "NOT_ACTIVE" : "ENDED"}`,
                )}
              </span>
              {pkg.state === "NOT_ACTIVE" && (
                <span className="text-sm text-muted-foreground">
                  {o(`snapshot.packageWhy.${pkg.availability === "ELIGIBLE" ? "ELIGIBLE" : "OTHER"}`)}
                </span>
              )}
            </dd>
          </div>
        )}
      </dl>
      <ul className="flex flex-col">
        {(pkg.purchasable || (open && pkg.state !== "NOT_ACTIVE")) && (
          <li>
            <Link href={`${base}/package`} className="ov-snap-link">
              {t("packageView")}
              <ArrowUpRightIcon aria-hidden="true" />
            </Link>
          </li>
        )}
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="ov-snap-link">
              {link.label}
              <ArrowUpRightIcon aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* The journey page ------------------------------------------------------------------------- */

const STATE_CHIP: Record<PhaseState, string> = {
  done: "text-foreground",
  current: "bg-brand px-1.5 py-0.5 text-brand-foreground ring-1 ring-foreground",
  alongside: "bg-brand/30 px-1.5 py-0.5 text-foreground ring-1 ring-foreground/50",
  next: "text-muted-foreground",
};

/** The seven phases, phase by phase: what happens in each, where the project is, where to go. */
export function JourneyPhases({
  overview,
  links,
  images = {},
}: {
  overview: ProjectOverview;
  links: Partial<Record<Phase, Array<{ href: string; label: string }>>>;
  /** The website's stage photographs, where a phase has one. */
  images?: Partial<Record<Phase, StaticImageData>>;
}) {
  const o = getTranslator("Overview");
  return (
    <ol className="ov-journey">
      {PHASES.map((phase, index) => {
        const state = overview.phases[phase];
        const fact = overview.phaseNotes[phase];
        const phaseLinks = links[phase] ?? [];
        return (
          <li key={phase} className={cn("ov-journey-phase", RAIL[state])} style={order(index)}>
            <div className="ov-journey-marker font-mono" aria-hidden="true">
              {state === "done" ? <CheckCheckIcon className="size-4" /> : String(index + 1).padStart(2, "0")}
            </div>
            <div className="ov-journey-body">
              <div className="flex min-w-0 flex-col gap-2">
                <h3 className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span
                    className={cn(
                      "font-heading text-3xl leading-none sm:text-4xl",
                      state === "next" && "text-muted-foreground",
                    )}
                  >
                    {o(`phases.${phase}`)}
                  </span>
                  <span
                    className={cn("rounded-sm font-mono text-[0.6875rem] tracking-widest uppercase", STATE_CHIP[state])}
                  >
                    {o(`journey.states.${state}`)}
                  </span>
                </h3>
                <p className="max-w-prose text-base text-pretty text-muted-foreground">{o(`phaseWhat.${phase}`)}</p>
                {fact && <p className="text-base font-medium">{o(`notes.${fact.key}`, fact.values)}</p>}
                {phaseLinks.length > 0 && (
                  <ul className="flex flex-wrap gap-2 pt-1">
                    {phaseLinks.map((link) => (
                      <li key={link.href}>
                        <Button asChild variant="outline" size="sm">
                          <Link href={link.href}>
                            {link.label}
                            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
                          </Link>
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {images[phase] && (
                <div className="ov-journey-photo p2b-unmask" style={order(Math.min(index, 2))}>
                  <Image
                    src={images[phase]!}
                    alt=""
                    sizes="(min-width: 40rem) 13rem, 100vw"
                    className="p2b-unmask-img"
                  />
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
