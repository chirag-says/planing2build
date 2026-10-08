// The professional's command center (lib/pro-console.ts): who they are and whether they can be
// found, what needs them now, where their opportunities stand, the work on site, their listing and
// their record. Every section reads the Console model, never raw API responses. Motion is set out
// in pro-console.css: one movement per section, in reading order.
import { cn } from "cn";
import { ArrowRightIcon, CheckIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { Eyebrow } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { initialsOf } from "@/lib/session";
import type {
  Checkpoint,
  Console,
  ConsoleState,
  PipelineNode,
  ProjectSheet,
  QueueItem,
  RecordFact,
  Service,
  Todo,
} from "@/lib/pro-console";
import heroHouse from "@/marketing/assets/hero-house.webp";
import blueprint from "@/marketing/assets/house-blueprint.webp";
import villa from "@/marketing/assets/house-villa.webp";
import "./pro-console.css";

const t = getTranslator("Console");
const p = getTranslator("Pro");

const IST = "Asia/Kolkata";
const DAY = new Intl.DateTimeFormat("en-IN", { day: "2-digit", timeZone: IST });
const MONTH = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: IST });
const TIME = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: IST });
const HOUR = new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: IST });
const TODAY = new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: IST });

const HOUSES = [heroHouse, villa, blueprint];
const KIND_HREF = { connection: "/connections", quote: "/quotes", inspection: "/inspections", finding: "/projects" } as const;

const vars = (values: Record<string, string | number>) =>
  Object.fromEntries(Object.entries(values).map(([key, value]) => [`--${key}`, value])) as CSSProperties;

const pad = (n: number) => String(n).padStart(2, "0");

/** A figure that counts up from zero; the number itself is read out, the animation is not. */
function Figure({ value, plain, delay = 0, className }: { value: number; plain?: boolean; delay?: number; className?: string }) {
  return (
    <span className={className}>
      <span aria-hidden="true" className={cn("pc-num", plain && "is-plain")} style={vars({ to: value, d: delay })} />
      <span className="sr-only">{value}</span>
    </span>
  );
}

/** A section of the console: an ink rule, the heading in the display face, a technical caption. */
function SectionHead({ id, title, caption, aside }: { id: string; title: ReactNode; caption?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 border-t-2 border-foreground pt-4">
      <div className="flex min-w-0 flex-col gap-1.5">
        <h2 id={id} className="font-heading text-2xl leading-none sm:text-3xl">
          {title}
        </h2>
        {caption && <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{caption}</p>}
      </div>
      {aside}
    </div>
  );
}

function TextLink({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  return (
    <Link
      href={href}
      className={cn(
        "group inline-flex min-h-11 items-center gap-2 self-start rounded-sm font-mono text-sm font-semibold tracking-wider uppercase underline-offset-4 hover:underline",
        className,
      )}
    >
      {children}
      <ArrowRightIcon aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1" />
    </Link>
  );
}

/* ================================================================ 1. greeting and identity */

function greetingOf(name: string | null, state: ConsoleState, now: Date) {
  if (!name) return state === "setup" ? t("greeting.new") : t("greeting.noName");
  const hour = Number(HOUR.format(now));
  const first = name.trim().split(/\s+/)[0];
  return t(hour < 12 ? "greeting.morning" : hour < 17 ? "greeting.afternoon" : "greeting.evening", { name: first });
}

/** What is waiting, as one line of links: projects on site, requests to review, inspections due. */
function summaryOf(c: Console) {
  const requests = c.attention.items.filter((item) => item.kind === "connection" || item.kind === "quote").length;
  const parts = [
    { href: "/projects", text: c.projects.length ? t("summary.projects", { count: c.projects.length }) : null },
    { href: "/connections", text: requests ? t("summary.requests", { count: requests }) : null },
    {
      href: "/inspections",
      text: c.inspections.upcoming.length ? t("summary.inspections", { count: c.inspections.upcoming.length }) : null,
    },
  ];
  return parts.filter((part): part is { href: string; text: string } => part.text !== null);
}

/**
 * The page's opening: the greeting, one line of what is waiting (each a link), and who they are
 * and whether they are listed. The header already carries their name and photo.
 */
export function Greeting({ console: c, now }: { console: Console; now: Date }) {
  const { identity } = c;
  const summary = summaryOf(c);
  const who = [identity.firm ?? identity.name, identity.trade, identity.base].filter(Boolean);
  return (
    <header className="flex flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-3">
        <Eyebrow>{t("date", { date: TODAY.format(now) })}</Eyebrow>
        <h1 className="p2b-rise-clip font-heading text-4xl leading-[0.95] text-balance sm:text-5xl">
          <span className="p2b-rise-in">{greetingOf(identity.name, c.state, now)}</span>
        </h1>
        <span aria-hidden="true" className="p2b-beam" />
      </div>
      {summary.length > 0 ? (
        <ul className="flex flex-wrap gap-x-2 gap-y-1 text-lg">
          {summary.map((part, index) => (
            <li key={part.href} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden="true" className="text-muted-foreground">·</span>}
              <Link href={part.href} className="rounded-sm font-semibold underline decoration-brand decoration-2 underline-offset-4 hover:decoration-foreground">
                {part.text}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="max-w-prose text-lg text-pretty text-muted-foreground">{t(`lead.${c.state}`)}</p>
      )}
      <ul aria-label={t("identity.label")} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
        {who.map((part) => (
          <li key={part}>{part}</li>
        ))}
        <li>
          <span className={cn("pc-status text-foreground", `is-${identity.listing}`)}>
            <i aria-hidden="true" />
            {t(`identity.listing.${identity.listing}`)}
          </span>
        </li>
      </ul>
    </header>
  );
}

/**
 * The slim notice while the listing is unfinished: where they are and the next step, one link. It
 * sits above the work, not in place of it, and leaves the page once every step is done.
 */
export function ProfileNotice({ console: c }: { console: Console }) {
  const notice = c.notice;
  if (!notice) return null;
  const waiting = notice.key === "review";
  const link = notice.key === "review" || notice.key === "attention" ? t(`notice.link.${notice.key}`) : t(`notice.steps.${notice.key}`);
  return (
    <section
      aria-label={t("notice.label")}
      className="pc-notice flex flex-wrap items-center gap-x-4 gap-y-2 border-l-4 border-brand bg-card py-2.5 pr-3 pl-4 ring-1 ring-foreground/15"
    >
      <span className="flex items-center gap-2.5 font-mono text-xs tracking-widest uppercase">
        <span aria-hidden="true" className="pc-notice-line" style={vars({ done: notice.done })}>
          {Array.from({ length: 5 }, (_, i) => (
            <i key={i} className={i < notice.done ? "is-done" : undefined} />
          ))}
        </span>
        {t("notice.progress", { done: notice.done })}
      </span>
      <span className="min-w-0 flex-1 basis-60 text-sm text-pretty text-muted-foreground">
        <strong className="font-semibold text-foreground">{t(`notice.steps.${notice.key}`)}.</strong> {t(`notice.text.${notice.key}`)}
      </span>
      <Link
        href={notice.href}
        className="group inline-flex min-h-10 items-center gap-1.5 rounded-sm font-mono text-sm font-semibold tracking-wider uppercase underline underline-offset-4 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {link}
        <ArrowRightIcon aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1" />
      </Link>
      {waiting && <span className="sr-only">{t("notice.text.review")}</span>}
    </section>
  );
}

/* ================================================================ 2. needs your attention */

function DateTab({ due }: { due: QueueItem["due"] }) {
  if (!due)
    return (
      <span aria-hidden="true" className="pc-date is-none">
        <b>—</b>
      </span>
    );
  const at = new Date(due.at);
  return (
    <span aria-hidden="true" className={cn("pc-date", due.soon && "is-soon")}>
      <b>{DAY.format(at)}</b>
      <span>{MONTH.format(at)}</span>
    </span>
  );
}

/** One thing waiting: the date it is due as a calendar tab, what it is, where, and by when. */
export function QueueRow({ item }: { item: QueueItem }) {
  const title = item.title || t(`kinds.${item.kind}`);
  const when = item.due ? `${formatDate(item.due.at)} · ${TIME.format(new Date(item.due.at))}` : null;
  const facts = [
    item.brief?.floors != null ? t("brief.floors", { count: item.brief.floors }) : null,
    item.brief?.area != null ? t("brief.area", { value: item.brief.area.toLocaleString("en-IN") }) : null,
  ].filter((fact): fact is string => fact !== null);
  return (
    <li className="border-b border-foreground/15 last:border-b-0">
      <Link href={item.href} className="pc-row group outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
        <DateTab due={item.due} />
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{t(`kinds.${item.kind}`)}</span>
          <span className="truncate text-base font-semibold sm:text-lg">
            {title}
            {item.place && <span className="font-normal text-muted-foreground">{` · ${item.place}`}</span>}
          </span>
          {facts.length > 0 && <span className="text-sm text-muted-foreground">{facts.join(" · ")}</span>}
          {item.due && when && (
            <span className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {t(`due.${item.due.kind}`, { date: when })}
              {item.due.soon && (
                <span className="bg-brand px-1.5 py-0.5 font-mono text-[0.6875rem] tracking-widest text-brand-foreground uppercase">
                  {t("soon")}
                </span>
              )}
            </span>
          )}
        </span>
        <ArrowRightIcon aria-hidden="true" className="pc-row-arrow size-5 shrink-0 text-brand" />
      </Link>
    </li>
  );
}

/**
 * The work order: the most urgent kind of thing waiting, how many, when the first is due and the
 * one button to it; the queue beside it. Laid down as a dark sheet; caught up, it says so briefly.
 */
export function AttentionBoard({ console: c, max = 4 }: { console: Console; max?: number }) {
  const { lead, items } = c.attention;
  const listed = c.identity.listing === "listed";
  if (!lead) {
    return (
      <section
        aria-labelledby="attention-title"
        className="pc-board surface-dark rounded-sm bg-background text-foreground ring-1 ring-foreground"
      >
        <div className="pc-board-in grid items-center gap-4 p-6 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:gap-6 sm:p-8">
          <span aria-hidden="true" className="grid size-12 place-items-center bg-brand text-brand-foreground">
            <CheckIcon className="size-6" strokeWidth={2.5} />
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <Eyebrow>{t("attention.eyebrow")}</Eyebrow>
            <h2 id="attention-title" className="font-heading text-3xl leading-none">
              {listed ? t("attention.clear") : t("attention.none")}
            </h2>
            <p className="max-w-prose text-base text-pretty text-muted-foreground">
              {listed ? t(`attention.clearBody.${c.state === "working" ? "working" : "listed"}`) : t("attention.noneBody")}
            </p>
          </div>
          {!listed && <TextLink href="/services">{t("attention.clearLink")}</TextLink>}
        </div>
      </section>
    );
  }
  const shown = items.slice(0, max);
  return (
    <section
      aria-labelledby="attention-title"
      className="pc-board surface-dark overflow-hidden rounded-sm bg-background text-foreground ring-1 ring-foreground"
    >
      {lead.soonest && lead.soonest.when !== "later" && <span aria-hidden="true" className="pc-hazard" />}
      <div className="pc-board-in grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="flex flex-col gap-4 p-6 sm:p-8">
          <Eyebrow>{t("attention.eyebrow")}</Eyebrow>
          <h2 id="attention-title" className="flex flex-col gap-2">
            <Figure value={lead.count} className="font-heading text-6xl leading-[0.85] text-brand sm:text-7xl" />
            <span className="font-heading text-3xl leading-none text-balance sm:text-4xl">
              {t(`attention.lead.${lead.kind}`, { count: lead.count })}
            </span>
          </h2>
          {lead.soonest && (
            <p className="text-lg text-muted-foreground">
              {t(`attention.soonest.${lead.kind}.${lead.soonest.when}`, { date: formatDate(lead.soonest.at) })}
            </p>
          )}
          <Button asChild size="lg" className="mt-2 self-start">
            <Link href={KIND_HREF[lead.kind]}>
              {t(`attention.cta.${lead.kind}`)}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </div>
        <div className="flex flex-col gap-2 border-t border-foreground/15 p-6 sm:p-8 lg:border-t-0 lg:border-l">
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{t("attention.queue")}</p>
          <ul className="flex flex-col">
            {shown.map((item) => (
              <QueueRow key={`${item.kind}-${item.id}`} item={item} />
            ))}
          </ul>
          {items.length > max && (
            <TextLink href="/notifications" className="text-muted-foreground">
              {t("attention.more", { count: items.length - max })}
            </TextLink>
          )}
          {items.some((item) => item.kind === "connection") && (
            <p className="mt-1 text-sm text-muted-foreground">{t("attention.namesNote")}</p>
          )}
        </div>
      </div>
    </section>
  );
}

/* ================================================================ 3. the opportunity pipeline */

/**
 * Where each opportunity stands now: requests, RFQs, quotes with families, projects. Drawn as a
 * dimension line; the brass marker travels along it to the first stage that waits on them.
 */
export function Pipeline({ console: c, dormant = false }: { console: Console; dormant?: boolean }) {
  const nodes = c.pipeline;
  // The marker travels as far as the opportunities reach; stages that wait on them pulse.
  const focus = dormant ? -1 : nodes.map((node) => node.count > 0).lastIndexOf(true);
  return (
    <section aria-labelledby="pipeline-title" className="flex flex-col gap-6">
      <SectionHead id="pipeline-title" title={t("pipeline.title")} caption={dormant ? t("pipeline.dormant") : t("pipeline.caption")} />
      <div className={cn("pc-pipe", dormant && "is-dormant")} style={vars({ f: Math.max(focus, 0), fill: focus > 0 ? focus / 3 : 0 })}>
        <span aria-hidden="true" className="pc-rail">
          <span className="pc-rail-fill" />
        </span>
        {focus >= 0 && <span aria-hidden="true" className="pc-runner" />}
        <ol className="pc-nodes">
          {nodes.map((node, index) => (
            <PipelineStop key={node.key} node={node} index={index} focus={!dormant && node.hot} />
          ))}
        </ol>
      </div>
      <p className="max-w-prose text-sm text-muted-foreground">{t("pipeline.note")}</p>
    </section>
  );
}

function PipelineStop({ node, index, focus }: { node: PipelineNode; index: number; focus: boolean }) {
  const name = t(`pipeline.nodes.${node.key}.name`);
  const text = t(`pipeline.nodes.${node.key}.text`);
  return (
    <li
      className={cn("pc-node", node.count > 0 && "has-count", node.hot && "is-hot", node.count === 0 && "is-zero", focus && "is-focus")}
      style={vars({ i: index })}
    >
      <span aria-hidden="true" className="pc-mark" />
      <Link href={node.href} className="group">
        <span className="sr-only">{t("pipeline.sr", { name, count: node.count, text })}</span>
        <span aria-hidden="true" className="font-mono text-xs tracking-widest text-muted-foreground">
          {pad(index + 1)}
        </span>
        <span aria-hidden="true" className="pc-node-name font-heading text-xl leading-none sm:text-2xl">
          {name}
        </span>
        <span aria-hidden="true" className="pc-node-count font-heading text-5xl leading-none sm:text-6xl">
          <span className="pc-num" style={vars({ to: node.count, d: index })} />
        </span>
        <span aria-hidden="true" className="text-sm text-pretty text-muted-foreground">
          {text}
        </span>
        {node.hot && (
          <span
            aria-hidden="true"
            className="mt-1 self-start bg-brand px-1.5 py-0.5 font-mono text-[0.6875rem] font-semibold tracking-widest text-brand-foreground uppercase"
          >
            {t("pipeline.needsYou")}
          </span>
        )}
      </Link>
    </li>
  );
}

/* ================================================================ 4. active work */

function nextText(sheet: ProjectSheet) {
  const next = sheet.next;
  return "stage" in next ? t(`projects.nextAction.${next.key}`, { stage: next.stage }) : t(`projects.nextAction.${next.key}`);
}

function floorLabel(floor: number | null) {
  if (floor === null) return null;
  return floor < 0 ? "Basement" : floor === 0 ? "Ground floor" : `Floor ${floor}`;
}

/** A project as a sheet: the house, the code, the stage line and the next step. */
function Sheet({ sheet, index, wide }: { sheet: ProjectSheet; index: number; wide?: boolean }) {
  const done = sheet.segments.filter((look) => look === "done").length;
  const name = sheet.code ?? sheet.category;
  return (
    <article className={cn("pc-sheet", wide && "is-wide")}>
      <div className="pc-fig p2b-unmask" style={vars({ i: index })}>
        <Image src={HOUSES[index % HOUSES.length]} alt="" fill sizes={wide ? "(min-width: 768px) 40vw, 100vw" : "(min-width: 1024px) 30vw, 85vw"} />
        <span className="pc-plate">{name}</span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-4 p-5 sm:p-6">
        {sheet.family && (
          <p className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="grid size-10 shrink-0 place-items-center bg-foreground font-mono text-sm font-semibold tracking-wider text-background"
            >
              {initialsOf(sheet.family)}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-lg leading-tight font-semibold">{sheet.family}</span>
              <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{t("projects.family")}</span>
            </span>
          </p>
        )}
        <p className="truncate font-mono text-xs tracking-widest text-muted-foreground uppercase">
          {[sheet.category, sheet.place].filter(Boolean).join(" · ")}
        </p>
        {sheet.stage ? (
          <div className="flex flex-col gap-2">
            <p className="flex flex-wrap items-center gap-2 font-mono text-xs font-semibold tracking-widest uppercase">
              {t("projects.stage", { position: pad(sheet.stage.position), total: pad(sheet.stage.total) })}
              {(sheet.next.key === "rectify" || sheet.next.key === "onHold") && (
                <span className="pc-flag">{t(`projects.flag.${sheet.next.key}`)}</span>
              )}
            </p>
            <h3 className="font-heading text-2xl leading-none text-balance sm:text-3xl">
              {sheet.stage.name}
              {floorLabel(sheet.stage.floor) && (
                <span className="font-sans text-base font-medium tracking-normal normal-case text-muted-foreground">
                  {` · ${floorLabel(sheet.stage.floor)}`}
                </span>
              )}
            </h3>
            <div
              role="img"
              aria-label={t("projects.segments", { done, total: sheet.segments.length })}
              className="pc-seg mt-1"
              style={vars({ n: sheet.segments.length })}
            >
              {sheet.segments.map((look, i) => (
                <i key={i} className={`is-${look}`} style={vars({ i })} />
              ))}
            </div>
          </div>
        ) : (
          <h3 className="font-heading text-2xl leading-none sm:text-3xl">{t("projects.service")}</h3>
        )}
        <div className="flex flex-col gap-1 border-t border-foreground/15 pt-3">
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{t("projects.next")}</p>
          <p className="text-base font-medium text-pretty">{nextText(sheet)}</p>
        </div>
        <div className="mt-auto flex items-center justify-between gap-3 pt-1">
          <span className="text-sm text-muted-foreground">{t("projects.since", { date: formatDate(sheet.since) })}</span>
          <Link
            href={sheet.href}
            className="pc-stretch inline-flex min-h-11 items-center gap-2 font-mono text-sm font-semibold tracking-wider uppercase"
          >
            {t("projects.open")}
            <span className="sr-only">{`: ${name}`}</span>
            <ArrowRightIcon aria-hidden="true" className="pc-arrow size-4" />
          </Link>
        </div>
      </div>
    </article>
  );
}

/** With nothing on site: where the next project comes from. The listing notice carries the way there. */
function NoProjects({ console: c }: { console: Console }) {
  const setup = c.identity.listing !== "listed";
  return (
    <div className="flex flex-col gap-1 border-y border-foreground/15 py-6">
      <h3 className="font-heading text-2xl leading-none">{t("projects.empty")}</h3>
      <p className="max-w-prose text-base text-pretty text-muted-foreground">{t(`projects.emptyBody.${setup ? "setup" : "listed"}`)}</p>
    </div>
  );
}

/** The work on site: one project as a wide sheet, several as a rail of sheets. */
export function ActiveWork({ console: c, heading = true }: { console: Console; heading?: boolean }) {
  const projects = c.projects;
  const one = projects.length === 1;
  return (
    <section aria-labelledby="work-title" className="flex flex-col gap-6">
      {heading ? (
        <SectionHead
          id="work-title"
          title={one ? t("projects.titleOne") : t("projects.title")}
          caption={projects.length > 0 ? t("projects.count", { count: projects.length }) : undefined}
          aside={projects.length > 1 ? <TextLink href="/projects">{t("projects.allProjects")}</TextLink> : undefined}
        />
      ) : (
        <h2 id="work-title" className="sr-only">
          {t("projects.title")}
        </h2>
      )}
      {projects.length === 0 ? (
        <NoProjects console={c} />
      ) : one ? (
        <Sheet sheet={projects[0]} index={0} wide />
      ) : (
        <div className="pc-rail-scroll" role="region" tabIndex={0} aria-labelledby="work-title">
          {projects.map((sheet, index) => (
            <Sheet key={sheet.id} sheet={sheet} index={index} />
          ))}
        </div>
      )}
    </section>
  );
}

/* ================================================================ 5. listing */

function checkpointName(cp: Checkpoint) {
  return t(`checkpoints.${cp.key}`);
}

/** The listing's five checkpoints on a construction line; the brass line reaches the one to do now. */
export function ConstructionLine({ checkpoints, vertical = false }: { checkpoints: Checkpoint[]; vertical?: boolean }) {
  const at = checkpoints.findIndex((cp) => cp.state !== "done");
  const reach = at < 0 ? 1 : at / (checkpoints.length - 1);
  return (
    <ol aria-label={t("presence.line")} className={cn("pc-line", vertical && "is-v")} style={vars({ p: reach })}>
      {checkpoints.map((cp, index) => {
        const name = checkpointName(cp);
        const state = t(`checkpoints.states.${cp.state}`);
        return (
          <li
            key={cp.key}
            className={cn("pc-cp", `is-${cp.state}`)}
            style={vars({ i: index })}
            aria-current={index === at ? "step" : undefined}
          >
            <span aria-hidden="true" className="pc-cp-mark">
              {cp.state === "done" && <CheckIcon className="size-3" strokeWidth={3} />}
            </span>
            <span className="flex min-w-0 items-baseline gap-2">
              {!vertical && (
                <span aria-hidden="true" className="font-mono text-xs text-muted-foreground">
                  {pad(index + 1)}
                </span>
              )}
              <Link
                href={cp.href}
                className={cn("pc-cp-name rounded-sm font-heading leading-none underline-offset-4 hover:underline", vertical ? "text-lg" : "text-xl sm:text-2xl")}
              >
                {name}
                <span className="sr-only">{`, ${state}`}</span>
              </Link>
            </span>
            <span aria-hidden="true" className="pc-cp-state">
              {state}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function todoText(todo: Todo) {
  switch (todo.key) {
    case "profileField": {
      const known = ["display_name", "base_locality", "base_geom", "service_radius_km", "years_experience", "bio"];
      return t(`todos.profileField.${(known.includes(todo.field) ? todo.field : "other") as "other"}`);
    }
    case "addService":
      return t("todos.addService");
    case "evidence":
      return t("todos.evidence", { label: todo.label });
    case "submit":
      return t("todos.submit", { category: todo.category });
    case "changes":
      return t("todos.changes", { category: todo.category });
    case "portfolio":
      return t("todos.portfolio");
    case "review":
      return t("todos.review", { category: todo.category });
  }
}

/** What is still missing, each item a link to where it is done. */
export function Todos({ todos }: { todos: Todo[] }) {
  if (todos.length === 0) return <p className="text-base text-muted-foreground">{t("presence.nothingRemaining")}</p>;
  return (
    <ul className="flex flex-col">
      {todos.map((todo, index) => (
        <li key={`${todo.key}-${index}`} className="border-b border-foreground/15 last:border-b-0">
          <Link
            href={todo.href}
            className="group flex min-h-11 items-center gap-3 rounded-sm py-2.5 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <span
              aria-hidden="true"
              className={cn(
                "size-3 shrink-0 ring-1.5 ring-foreground",
                todo.key === "review" ? "bg-[repeating-linear-gradient(-45deg,var(--brand)_0_2px,var(--foreground)_2px_4px)]" : "ring-1",
              )}
            />
            <span className="flex min-w-0 flex-1 flex-col gap-x-3 gap-y-0.5 sm:flex-row sm:items-baseline sm:justify-between">
              <span className="text-base text-pretty">{todoText(todo)}</span>
              {todo.key === "evidence" && (
                <span className="shrink-0 font-mono text-xs tracking-widest text-muted-foreground uppercase">
                  {t("todos.evidenceMore", { remaining: todo.remaining, category: todo.category })}
                </span>
              )}
            </span>
            <ArrowRightIcon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ServiceRow({ service }: { service: Service }) {
  return (
    <li className="border-b border-foreground/15 last:border-b-0">
      <Link
        href={`/categories/${service.code}`}
        className="group grid min-h-11 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-sm py-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className="truncate text-base font-semibold">{service.name}</span>
        <StatusBadge kind="listing" status={service.state} withLabel />
        <span className="col-span-2 text-sm text-muted-foreground">
          {service.public ? p("dashboard.public") : service.hidden ? p("dashboard.hidden") : p("dashboard.notPublic")}
          {service.reviewDueAt && ` · ${p("dashboard.reviewDue", { date: formatDate(service.reviewDueAt) })}`}
        </span>
      </Link>
    </li>
  );
}

/** The services they are listed for (or working towards), and the way to add one. */
export function ServicesList({ console: c, add = true }: { console: Console; add?: boolean }) {
  if (c.services.length === 0)
    return (
      <div className="flex flex-col gap-1">
        <p className="font-heading text-xl leading-none">{t("listing.noServices")}</p>
        <p className="text-base text-muted-foreground">{t("listing.noServicesBody")}</p>
        <TextLink href="/services#add">{t("todos.addService")}</TextLink>
      </div>
    );
  return (
    <div className="flex flex-col gap-1">
      <ul className="flex flex-col">
        {c.services.map((service) => (
          <ServiceRow key={service.code} service={service} />
        ))}
      </ul>
      {add && c.addOptions.length > 0 && <TextLink href="/services#add">{t("listing.addService")}</TextLink>}
    </div>
  );
}

/* ================================================================ 6. record */

function FactValue({ fact, index }: { fact: RecordFact; index: number }) {
  const cls = "font-heading text-4xl leading-none sm:text-5xl";
  switch (fact.key) {
    case "replies":
      return (
        <span className={cls}>
          <Figure value={fact.answered} plain delay={index} />
          <span aria-hidden="true" className="text-muted-foreground">
            /
          </span>
          <span className="sr-only"> of </span>
          <Figure value={fact.received} plain delay={index} />
        </span>
      );
    case "quotes":
      return (
        <span className={cls}>
          <Figure value={fact.selected} plain delay={index} />
          <span aria-hidden="true" className="text-muted-foreground">
            /
          </span>
          <span className="sr-only"> of </span>
          <Figure value={fact.submitted} plain delay={index} />
        </span>
      );
    default:
      return <Figure value={fact.count} plain delay={index} className={cls} />;
  }
}

function factLabel(fact: RecordFact) {
  switch (fact.key) {
    case "verified":
      return t("record.verified.label", { count: fact.count });
    case "replies":
      return t("record.replies.label");
    case "quotes":
      return t("record.quotes.label");
    case "projects":
      return t("record.projects.label", { count: fact.count });
    case "inspections":
      return t("record.inspections.label", { count: fact.count });
  }
}

/** Their record on Plan2Build: facts from the platform, never a score. */
export function RecordPanel({ console: c }: { console: Console }) {
  return (
    <section aria-labelledby="record-title" className="flex flex-col gap-5">
      <SectionHead id="record-title" title={t("record.title")} />
      {c.record.length > 0 ? (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-6 lg:grid-cols-4">
          {c.record.map((fact, index) => (
            <div key={fact.key} className="flex flex-col-reverse gap-2 border-l-2 border-foreground/15 pl-4">
              <dt className="text-sm text-pretty text-muted-foreground">
                {factLabel(fact)}
                {fact.key === "verified" && <span className="block font-medium text-foreground">{fact.names.join(", ")}</span>}
              </dt>
              <dd className="m-0">
                <FactValue fact={fact} index={index} />
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-base text-muted-foreground">{t("record.empty")}</p>
      )}
      <p className="text-xs text-muted-foreground">{t("record.note")}</p>
    </section>
  );
}

/* ================================================================ inspections (auditors) */

export function InspectionsStrip({ console: c }: { console: Console }) {
  if (!c.inspections.auditor) return null;
  const upcoming = c.inspections.upcoming;
  return (
    <section aria-labelledby="inspections-title" className="flex flex-col gap-3">
      <SectionHead
        id="inspections-title"
        title={t("inspections.title")}
        aside={upcoming.length > 0 ? <TextLink href="/inspections">{t("inspections.open")}</TextLink> : undefined}
      />
      {upcoming.length > 0 ? (
        <ul className="flex flex-col">
          {upcoming.slice(0, 3).map((item) => (
            <QueueRow key={item.id} item={item} />
          ))}
        </ul>
      ) : (
        <p className="text-base text-muted-foreground">{t("inspections.none")}</p>
      )}
    </section>
  );
}
