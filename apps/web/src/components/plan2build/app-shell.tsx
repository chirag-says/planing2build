"use client";

// The signed-in product shell for homeowners and professionals (UI_DESIGN_SYSTEM.md section 9):
// a light sidebar on wide screens with the places you go (on a project, its journey phases and
// their sections; a professional's work queue with brass counts of what waits), and a top bar with
// where you are, the main action and the account. Below 1024 px the sidebar becomes the slide-out
// menu. Navigation data comes from the host's layout; icons are named, so a server layout can
// describe the items.
import { cn } from "cn";
import {
  CalculatorIcon,
  ChevronDownIcon,
  ClipboardCheckIcon,
  ClipboardListIcon,
  DraftingCompassIcon,
  FilePenLineIcon,
  FileTextIcon,
  FolderOpenIcon,
  HardHatIcon,
  ImagesIcon,
  InboxIcon,
  LayoutDashboardIcon,
  LifeBuoyIcon,
  ListChecksIcon,
  LogOutIcon,
  MenuIcon,
  PackageIcon,
  PlusIcon,
  ReceiptIcon,
  ScaleIcon,
  SearchIcon,
  SparklesIcon,
  UserRoundIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import logo from "@/marketing/assets/plan2build-logo.png";
import "./sidebar-beam.css";

const nav = getTranslator("Nav");
const shell = getTranslator("Shell");

const ICONS = {
  overview: LayoutDashboardIcon,
  requirement: ClipboardListIcon,
  estimate: CalculatorIcon,
  designs: SparklesIcon,
  construction: HardHatIcon,
  specification: ListChecksIcon,
  documents: FileTextIcon,
  package: PackageIcon,
  buildPlan: DraftingCompassIcon,
  professionals: UsersIcon,
  quotes: ScaleIcon,
  projects: FolderOpenIcon,
  search: SearchIcon,
  billing: ReceiptIcon,
  help: LifeBuoyIcon,
  requests: InboxIcon,
  quoteRequests: FilePenLineIcon,
  inspections: ClipboardCheckIcon,
  profile: UserRoundIcon,
  portfolio: ImagesIcon,
} satisfies Record<string, LucideIcon>;

export type ShellIcon = keyof typeof ICONS;

export interface ShellItem {
  href: string;
  label: string;
  icon: ShellIcon;
  /** Current only on this exact path (an overview), not on the pages below it. */
  exact?: boolean;
  /** Something waiting there (new requests); shown as a brass count. */
  count?: number;
}

export interface ShellGroup {
  label?: string;
  items: ShellItem[];
  /** A journey phase: its state (a brass square where the project is) and, with no screen of its own, where it happens. */
  phase?: { state: "done" | "current" | "next" | "alongside"; stateLabel: string; note?: string };
  /** Secondary places (a professional's presence beside their work): smaller, quieter rows. */
  quiet?: boolean;
}

/** One landmark: a named <nav> holding one or more labelled groups. */
export interface ShellSection {
  navLabel: string;
  groups: ShellGroup[];
}

export interface ShellLink {
  href: string;
  label: string;
  icon: ShellIcon;
}

function isCurrent(pathname: string, item: Pick<ShellItem, "href" | "exact">) {
  if (pathname === item.href) return true;
  if (item.exact || item.href === "/") return false;
  return pathname.startsWith(`${item.href}/`);
}

/**
 * Sign out, then a full page load of sign-in: a soft refresh would keep the shared layout, so the
 * sidebar and avatar could stay on screen around the sign-in form.
 */
function useSignOut(to: string) {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try {
      await browserApi.POST("/api/v1/auth/logout");
    } finally {
      window.location.assign(to);
    }
  }
  return { busy, signOut };
}

/** The account mark: the website's brass square with an ink outline, initials in mono caps. */
export function Avatar({
  initials,
  photoUrl,
  className,
}: {
  initials: string | null;
  /** Their photo when the account has one; the brass monogram stands in until then. */
  photoUrl?: string | null;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      style={photoUrl ? { backgroundImage: `url("${photoUrl}")` } : undefined}
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-brand bg-cover bg-center font-mono text-xs font-semibold tracking-wider text-brand-foreground ring-1 ring-foreground",
        className,
      )}
    >
      {!photoUrl && (initials ?? <UserRoundIcon className="size-4" />)}
    </span>
  );
}

function PhaseMarker({ state }: { state: NonNullable<ShellGroup["phase"]>["state"] }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-2 shrink-0",
        state === "done" && "bg-foreground",
        state === "current" && "bg-brand ring-1 ring-foreground",
        state === "alongside" && "bg-brand/60 ring-1 ring-foreground/60",
        state === "next" && "ring-1 ring-foreground/40",
      )}
    />
  );
}

/**
 * The sidebar's places (and the phone menu's): named navigation landmarks of labelled groups. A
 * project's groups are its journey phases, each with its state; the current one sits on a brass
 * wash. The current page is an ink row; counts of what waits are brass.
 */
function SidebarNav({ sections, onNavigate }: { sections: ShellSection[]; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <div className="flex flex-col gap-6">
      {sections.map((section) => (
        <nav key={section.navLabel} aria-label={section.navLabel} className="flex flex-col gap-1">
          {section.groups.map((group, index) => (
            <div
              key={group.label ?? index}
              className={cn(
                "flex flex-col gap-0.5 rounded-md",
                group.label && "pt-2",
                group.phase?.state === "current" && "bg-brand/15 pb-1 ring-1 ring-brand/40",
              )}
            >
              {group.label && (
                <p className="flex items-center gap-2 px-3 pb-1 font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase">
                  {group.phase && <PhaseMarker state={group.phase.state} />}
                  {group.label}
                  {group.phase && <span className="sr-only">, {group.phase.stateLabel}</span>}
                </p>
              )}
              {group.items.length === 0 && group.phase?.note && (
                <p className="px-3 pb-1.5 text-sm text-muted-foreground">{group.phase.note}</p>
              )}
              {group.items.length > 0 && (
                <ul className="flex flex-col gap-0.5">
                  {group.items.map((item) => {
                    const current = isCurrent(pathname, item);
                    const Icon = ICONS[item.icon];
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          onClick={onNavigate}
                          aria-current={current ? "page" : undefined}
                          className={cn(
                            "sb-beam flex min-h-9 items-center gap-3 rounded-md px-3 font-medium transition-colors",
                            group.quiet ? "text-sm" : "text-[0.9375rem]",
                            "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                            current ? "bg-foreground text-background" : "text-foreground/80",
                          )}
                        >
                          <Icon
                            aria-hidden="true"
                            className={cn("sb-beam-icon size-[1.0625rem] shrink-0", current ? "text-brand" : "text-muted-foreground")}
                          />
                          <span className="sb-beam-label min-w-0 flex-1 truncate">{item.label}</span>
                          {item.count ? (
                            <span className="rounded-sm bg-brand px-1.5 py-1 font-mono text-xs leading-none font-semibold text-brand-foreground tabular-nums ring-1 ring-foreground">
                              <span aria-hidden="true">{item.count}</span>
                              <span className="sr-only">{shell("newCount", { count: item.count })}</span>
                            </span>
                          ) : null}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ))}
        </nav>
      ))}
    </div>
  );
}

function Brand({
  brand,
  tag,
  homeHref,
  onNavigate,
}: {
  brand: string;
  tag: string;
  homeHref: string;
  onNavigate?: () => void;
}) {
  return (
    <Link href={homeHref} onClick={onNavigate} className="flex flex-col gap-1 rounded-md">
      <Image
        src={logo}
        alt=""
        className="h-7 w-auto self-start"
        priority
      />
      <span className="sr-only">{brand}</span>
      <span
        aria-hidden="true"
        className="font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase"
      >
        {tag}
      </span>
    </Link>
  );
}

export function AppShell({
  brand,
  tag,
  homeHref = "/",
  userName,
  initials,
  photoUrl,
  accountKind,
  accountSubtitle,
  sections,
  sidebarTop,
  helpHref,
  context,
  primaryAction,
  headerActions,
  accountLinks,
  signOutHref = "/sign-in",
  children,
}: {
  brand: string;
  /** Small caps line under the logo ("Homeowner", "Professionals"). */
  tag: string;
  homeHref?: string;
  userName: string | null;
  initials: string | null;
  /** Their photo for the account mark, when there is one. */
  photoUrl?: string | null;
  /** A line under their name beside the avatar (a firm); the name alone when absent. */
  accountSubtitle?: string | null;
  /** "Homeowner account", shown under the name in the account menu. */
  accountKind: string;
  /** The places in the bar, flattened in order; groups label them in the phone menu. */
  sections: ShellSection[];
  /** Where you are, as a control: the project switcher on a project's pages. */
  sidebarTop?: ReactNode;
  helpHref?: string;
  /** Where you are, as text, when there is no switcher (a greeting). */
  context?: ReactNode;
  primaryAction?: { href: string; label: string };
  /** Controls beside the account button (a notifications bell). */
  headerActions?: ReactNode;
  accountLinks: ShellLink[];
  /** Where a signed-out person lands. */
  signOutHref?: string;
  children: ReactNode;
}) {
  const { busy, signOut } = useSignOut(signOutHref);
  // Every link inside the menu closes it as it navigates.
  const [menuOpen, setMenuOpen] = useState(false);

  const account = (
    // Non-modal, as in the WAI-ARIA menu button pattern: a modal menu hides the page with
    // aria-hidden while its links stay focusable (axe aria-hidden-focus).
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" aria-label={nav("account")} className="h-12 gap-2.5 px-1.5 hover:bg-accent">
          <Avatar initials={initials} photoUrl={photoUrl} className="size-10" />
          {userName && (
            <span className="hidden min-w-0 flex-col items-start text-left md:flex">
              <span className="max-w-44 truncate text-base leading-tight font-semibold">{userName}</span>
              {accountSubtitle && (
                <span className="max-w-44 truncate font-mono text-[0.6875rem] leading-tight tracking-widest text-muted-foreground uppercase">
                  {accountSubtitle}
                </span>
              )}
            </span>
          )}
          <ChevronDownIcon aria-hidden="true" className="hidden size-4 text-muted-foreground md:inline" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 min-w-64">
        <DropdownMenuLabel className="flex items-center gap-3 px-2 py-2">
          <Avatar initials={initials} photoUrl={photoUrl} className="size-10" />
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-base font-semibold text-foreground">{userName ?? shell("you")}</span>
            <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">{accountKind}</span>
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {accountLinks.map((link) => {
          const Icon = ICONS[link.icon];
          return (
            <DropdownMenuItem key={link.href} asChild className="py-2 text-base">
              <Link href={link.href}>
                <Icon aria-hidden="true" />
                {link.label}
              </Link>
            </DropdownMenuItem>
          );
        })}
        {accountLinks.length > 0 && <DropdownMenuSeparator />}
        <DropdownMenuItem disabled={busy} onSelect={signOut} className="py-2 text-base">
          <LogOutIcon aria-hidden="true" />
          {busy ? nav("signingOut") : nav("signOut")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div data-app-shell className="flex w-full flex-1">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        {nav("skip")}
      </a>

      {/* The sidebar: light, beside the content (never over it), and it stays as the page scrolls. */}
      <aside className="sticky top-0 hidden h-svh w-72 shrink-0 flex-col border-r-2 border-foreground/10 bg-card lg:flex">
        <div className="flex h-18 shrink-0 items-center border-b-2 border-foreground/10 px-5">
          <Brand brand={brand} tag={tag} homeHref={homeHref} />
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" data-lenis-prevent>
          {sidebarTop}
          <SidebarNav sections={sections} />
        </div>
        {helpHref && (
          <div className="shrink-0 border-t-2 border-foreground/10 p-3">
            <Link
              href={helpHref}
              className="flex min-h-10 items-center gap-3 rounded-md px-3 text-[0.9375rem] font-medium text-foreground/80 outline-none hover:bg-foreground/5 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <LifeBuoyIcon aria-hidden="true" className="size-[1.0625rem] text-muted-foreground" />
              {shell("help")}
            </Link>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Not sticky: a pinned bar's links would cover the page's own targets as it scrolls (WCAG 2.5.8). */}
        <header className="relative z-30 border-b-2 border-foreground/10 bg-background">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:h-18 lg:px-8">
            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="lg:hidden" aria-label={nav("openMenu")}>
                  <MenuIcon aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 gap-0 border-border bg-card p-0 text-foreground">
                <SheetHeader className="h-18 justify-center border-b-2 border-foreground/10 px-5">
                  <SheetTitle className="sr-only">{nav("menu")}</SheetTitle>
                  <SheetDescription className="sr-only">{brand}</SheetDescription>
                  <Brand brand={brand} tag={tag} homeHref={homeHref} onNavigate={() => setMenuOpen(false)} />
                </SheetHeader>
                <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-3 py-4" data-lenis-prevent>
                  {sidebarTop}
                  <SidebarNav sections={sections} onNavigate={() => setMenuOpen(false)} />
                  <div className="flex flex-col gap-1 border-t-2 border-foreground/10 pt-4">
                    <p className="px-3 pb-1 font-mono text-xs tracking-widest text-muted-foreground uppercase">
                      {userName ?? shell("you")}
                    </p>
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={async () => {
                        await signOut();
                        setMenuOpen(false);
                      }}
                    >
                      <LogOutIcon aria-hidden="true" />
                      {busy ? nav("signingOut") : nav("signOut")}
                    </Button>
                  </div>
                </div>
              </SheetContent>
            </Sheet>

            <div className="lg:hidden">
              <Brand brand={brand} tag={tag} homeHref={homeHref} />
            </div>
            {/* Where you are, as text: the greeting, or the project. */}
            <div className="hidden min-w-0 flex-1 md:block">{context}</div>
            <div className="flex-1 md:hidden" />

            <div className="flex shrink-0 items-center gap-2">
              {headerActions}
              {primaryAction && (
                <Button asChild className="hidden sm:inline-flex">
                  <Link href={primaryAction.href}>
                    <PlusIcon aria-hidden="true" data-icon="inline-start" />
                    {primaryAction.label}
                  </Link>
                </Button>
              )}
              {account}
            </div>
          </div>
        </header>

        {/* The website's blueprint ground under every signed-in screen. */}
        <div className="p2b-ground flex flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
