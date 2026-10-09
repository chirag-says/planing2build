"use client";

// A project's sections in seven groups (Home, My project, Quotes, Construction, Verify, Records,
// Journey; decided 2026-10-08). In the sidebar only the group you are in opens; the others are one
// link each, to their first page, so the bar never lists every screen at once. On phones the same
// groups run as one row under the header that scrolls sideways, every section in it. Groups and
// sections come from the layout; only sections with content are passed in.
import { cn } from "cn";
import {
  BellIcon,
  CalculatorIcon,
  ClipboardCheckIcon,
  ClipboardListIcon,
  DraftingCompassIcon,
  FileTextIcon,
  FolderOpenIcon,
  HardHatIcon,
  BookCheckIcon,
  HouseIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  ListChecksIcon,
  MessageSquareTextIcon,
  PackageIcon,
  RouteIcon,
  ScaleIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UsersIcon,
  UsersRoundIcon,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const ICONS = {
  home: HouseIcon,
  overview: LayoutDashboardIcon,
  notifications: BellIcon,
  messages: MessageSquareTextIcon,
  team: UsersRoundIcon,
  project: FolderOpenIcon,
  requirement: ClipboardListIcon,
  estimate: CalculatorIcon,
  designs: SparklesIcon,
  package: PackageIcon,
  buildPlan: DraftingCompassIcon,
  quotes: ScaleIcon,
  professionals: UsersIcon,
  construction: HardHatIcon,
  specification: ListChecksIcon,
  verify: ShieldCheckIcon,
  inspections: ClipboardCheckIcon,
  records: FileTextIcon,
  documents: FileTextIcon,
  handover: KeyRoundIcon,
  buildRecord: BookCheckIcon,
  journey: RouteIcon,
} satisfies Record<string, LucideIcon>;

export type SectionIcon = keyof typeof ICONS;

export interface SectionItem {
  href: string;
  label: string;
  icon: SectionIcon;
  /** Current only on this exact path (the overview), not on pages below it. */
  exact?: boolean;
}

export interface SectionGroup {
  key: string;
  label: string;
  icon: SectionIcon;
  items: SectionItem[];
}

function isCurrent(pathname: string, item: SectionItem) {
  if (item.href.includes("#")) return false;
  return pathname === item.href || (!item.exact && pathname.startsWith(`${item.href}/`));
}

const linkClass = (current: boolean) =>
  cn(
    "sb-beam flex min-h-9 items-center gap-3 rounded-md px-3 text-[0.9375rem] font-medium transition-colors",
    "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
    current ? "bg-foreground text-background" : "text-foreground/80",
  );

function ItemLink({ item, current, label, onNavigate }: { item: SectionItem; current: boolean; label?: string; onNavigate?: () => void }) {
  const Icon = ICONS[item.icon];
  return (
    <Link href={item.href} onClick={onNavigate} aria-current={current ? "page" : undefined} className={linkClass(current)}>
      <Icon aria-hidden="true" className={cn("sb-beam-icon size-[1.0625rem] shrink-0", current ? "text-brand" : "text-muted-foreground")} />
      <span className="sb-beam-label min-w-0 flex-1 truncate">{label ?? item.label}</span>
    </Link>
  );
}

/** The sidebar (and the phone menu): seven groups, the current one open. */
export function ProjectSectionsNav({
  label,
  groups,
  onNavigate,
}: {
  label: string;
  groups: SectionGroup[];
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="flex flex-col gap-0.5">
      {groups.map((group) => {
        const currentItem = group.items.find((item) => isCurrent(pathname, item));
        const single = group.items.length === 1;
        const open = Boolean(currentItem) && !single;
        if (single) {
          // One section: the group is that section (Journey, Records, Verify).
          const item = group.items[0];
          return <ItemLink key={group.key} item={item} current={isCurrent(pathname, item)} onNavigate={onNavigate} />;
        }
        if (!open) {
          // Closed: the group itself, leading to its first section.
          const GroupIcon = ICONS[group.icon];
          return (
            <Link key={group.key} href={group.items[0].href} onClick={onNavigate} className={linkClass(false)}>
              <GroupIcon aria-hidden="true" className="sb-beam-icon size-[1.0625rem] shrink-0 text-muted-foreground" />
              <span className="sb-beam-label min-w-0 flex-1 truncate">{group.label}</span>
            </Link>
          );
        }
        return (
          <div key={group.key} className="my-1 flex flex-col gap-0.5 rounded-md bg-brand/10 pt-2 pb-1 ring-1 ring-brand/40">
            <p className="flex items-center gap-2 px-3 pb-1 font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase">
              <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
              {group.label}
            </p>
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => (
                <li key={item.href}>
                  <ItemLink item={item} current={item === currentItem} onNavigate={onNavigate} />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

/** Phones and tablets: the groups as one row under the header, every section in it. */
export function ProjectSectionsRow({ label, groups }: { label: string; groups: SectionGroup[] }) {
  const pathname = usePathname();
  const scroller = useRef<HTMLElement>(null);

  // The row scrolls: bring the current section into view, without moving the page.
  useEffect(() => {
    const box = scroller.current;
    const current = box?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!box || !current || box.scrollWidth <= box.clientWidth) return;
    box.scrollLeft = current.offsetLeft - (box.clientWidth - current.offsetWidth) / 2;
  }, [pathname]);

  return (
    <nav ref={scroller} aria-label={label} className="relative -mx-4 overflow-x-auto overscroll-x-contain px-4 sm:-mx-6 sm:px-6">
      <ol className="flex w-max items-stretch border-y-2 border-foreground">
        {groups.map((group) => {
          const here = group.items.some((item) => isCurrent(pathname, item));
          return (
            <li key={group.key} className={cn("flex flex-col gap-1 border-l border-foreground/15 px-1 py-2 first:border-l-0", here && "bg-brand/15")}>
              <p className="flex items-center gap-2 px-1.5 pt-0.5 font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase">
                <span aria-hidden="true" className={cn("size-2 shrink-0", here ? "bg-brand ring-1 ring-foreground" : "ring-1 ring-foreground/40")} />
                {group.label}
              </p>
              <ul className="flex gap-0.5">
                {group.items.map((item) => {
                  const current = isCurrent(pathname, item);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={current ? "page" : undefined}
                        className={cn(
                          "flex min-h-11 items-center rounded-md px-1.5 text-[0.9375rem] font-medium whitespace-nowrap transition-colors",
                          "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                          current ? "bg-foreground text-background" : "text-foreground/80 hover:bg-accent hover:text-foreground",
                        )}
                      >
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
