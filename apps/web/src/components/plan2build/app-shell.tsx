"use client";

// The signed-in app shell for homeowners and professionals (UI_DESIGN_SYSTEM.md section 9): a
// night sidebar with the navigation in labelled groups, a sticky top bar with the page context, the
// main action and the account avatar, and the website's blueprint ground under the content. Below
// 1024 px the sidebar moves into a slide-out menu. Navigation data comes from the host's layout;
// the icons are named, so a server layout can describe the items.
import { cn } from "cn";
import {
  ArrowRightIcon,
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
import logoNight from "@/marketing/assets/plan2build-logo-dark.png";
import logo from "@/marketing/assets/plan2build-logo.png";

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
  className,
}: {
  initials: string | null;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-brand font-mono text-xs font-semibold tracking-wider text-brand-foreground ring-1 ring-foreground",
        className,
      )}
    >
      {initials ?? <UserRoundIcon className="size-4" />}
    </span>
  );
}

function SidebarNav({
  sections,
  onNavigate,
}: {
  sections: ShellSection[];
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <div className="flex flex-col gap-6">
      {sections.map((section) => (
        <nav
          key={section.navLabel}
          aria-label={section.navLabel}
          className="flex flex-col gap-5"
        >
          {section.groups.map((group, index) => (
            <div key={group.label ?? index} className="flex flex-col gap-1">
              {group.label && (
                <p className="px-3 pb-1 font-mono text-xs tracking-widest text-muted-foreground uppercase">
                  {group.label}
                </p>
              )}
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
                          "group relative flex min-h-11 items-center gap-3 rounded-md px-3 text-base font-medium transition-colors",
                          "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                          current
                            ? "bg-foreground/10 text-foreground"
                            : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground",
                        )}
                      >
                        {/* The brass bar of the current item; it grows in, like the website's beam. */}
                        <span
                          aria-hidden="true"
                          className={cn(
                            "absolute inset-y-2 left-0 w-1 rounded-r-sm bg-brand transition-transform duration-300 ease-out",
                            current ? "scale-y-100" : "scale-y-0",
                          )}
                        />
                        <Icon
                          aria-hidden="true"
                          className={cn(
                            "size-[1.125rem] shrink-0 transition-colors",
                            current
                              ? "text-brand"
                              : "text-muted-foreground group-hover:text-foreground",
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate">
                          {item.label}
                        </span>
                        {item.count ? (
                          <span className="rounded-sm bg-brand px-1.5 py-1 font-mono text-xs leading-none font-semibold text-brand-foreground tabular-nums">
                            <span aria-hidden="true">{item.count}</span>
                            <span className="sr-only">
                              {shell("newCount", { count: item.count })}
                            </span>
                          </span>
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      ))}
    </div>
  );
}

function HelpCard({ href }: { href: string }) {
  return (
    <Link
      href={href}
      className="group block overflow-hidden rounded-md bg-foreground/5 ring-1 ring-foreground/10 transition-colors outline-none hover:bg-foreground/10 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <span
        aria-hidden="true"
        className="block h-1.5 bg-[repeating-linear-gradient(-45deg,var(--brand)_0_0.375rem,var(--background)_0.375rem_0.75rem)]"
      />
      <span className="flex items-center gap-3 px-3 py-2.5">
        <LifeBuoyIcon
          aria-hidden="true"
          className="size-4 shrink-0 text-brand"
        />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="font-heading text-base leading-tight">
            {shell("help")}
          </span>
          <span className="text-sm text-muted-foreground">
            {shell("helpLink")}
          </span>
        </span>
        <ArrowRightIcon
          aria-hidden="true"
          className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground"
        />
      </span>
    </Link>
  );
}

function Brand({
  brand,
  tag,
  homeHref,
}: {
  brand: string;
  tag: string;
  homeHref: string;
}) {
  return (
    <Link href={homeHref} className="flex flex-col gap-1 rounded-md">
      <Image
        src={logoNight}
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
  accountKind,
  sections,
  sidebarTop,
  helpHref,
  context,
  primaryAction,
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
  /** "Homeowner account", shown under the name in the account menu. */
  accountKind: string;
  sections: ShellSection[];
  /** Above the navigation: the project switcher on a project's pages. */
  sidebarTop?: ReactNode;
  helpHref?: string;
  /** The top bar's left side on wide screens: where you are. */
  context?: ReactNode;
  primaryAction?: { href: string; label: string };
  accountLinks: ShellLink[];
  /** Where a signed-out person lands. */
  signOutHref?: string;
  children: ReactNode;
}) {
  const { busy, signOut } = useSignOut(signOutHref);
  // Every link inside the menu closes it as it navigates.
  const [menuOpen, setMenuOpen] = useState(false);

  const sidebarBody = (onNavigate?: () => void) => (
    <>
      {sidebarTop}
      <SidebarNav sections={sections} onNavigate={onNavigate} />
    </>
  );

  return (
    <div data-app-shell className="flex w-full flex-1">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        {nav("skip")}
      </a>

      {/* The night column runs the full page height; the sidebar itself stays in view. */}
      <div className="surface-dark hidden w-64 shrink-0 bg-background text-foreground lg:block">
        <aside
          aria-label={shell("sidebar")}
          className="sticky top-0 flex h-dvh flex-col"
        >
          <div className="flex h-18 shrink-0 items-center border-b border-border px-5">
            <Brand brand={brand} tag={tag} homeHref={homeHref} />
          </div>
          <div
            className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-3 py-5"
            data-lenis-prevent
          >
            {sidebarBody()}
          </div>
          {helpHref && (
            <div className="shrink-0 border-t border-border p-3">
              <HelpCard href={helpHref} />
            </div>
          )}
        </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b-2 border-foreground/10 bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/75">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:h-18 lg:px-8">
            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="lg:hidden"
                  aria-label={nav("openMenu")}
                >
                  <MenuIcon aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent
                side="left"
                className="surface-dark w-72 gap-0 border-border bg-background p-0 text-foreground"
              >
                <SheetHeader className="h-18 justify-center border-b border-border px-5">
                  <SheetTitle className="sr-only">{nav("menu")}</SheetTitle>
                  <SheetDescription className="sr-only">
                    {brand}
                  </SheetDescription>
                  <Brand brand={brand} tag={tag} homeHref={homeHref} />
                </SheetHeader>
                <div
                  className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-3 py-5"
                  data-lenis-prevent
                >
                  {sidebarBody(() => setMenuOpen(false))}
                  <div className="flex flex-col gap-1 border-t border-border pt-4">
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

            <Link href={homeHref} className="shrink-0 rounded-md lg:hidden">
              <Image src={logo} alt="" className="h-6 w-auto sm:h-7" />
              <span className="sr-only">{brand}</span>
            </Link>

            <div className="hidden min-w-0 flex-1 lg:block">{context}</div>
            <div className="flex-1 lg:hidden" />

            <div className="flex shrink-0 items-center gap-2">
              {primaryAction && (
                <Button asChild className="hidden sm:inline-flex">
                  <Link href={primaryAction.href}>
                    <PlusIcon aria-hidden="true" data-icon="inline-start" />
                    {primaryAction.label}
                  </Link>
                </Button>
              )}
              {helpHref && (
                <Button
                  asChild
                  variant="ghost"
                  size="icon"
                  className="hidden sm:inline-flex"
                >
                  <Link href={helpHref} aria-label={shell("help")}>
                    <LifeBuoyIcon aria-hidden="true" />
                  </Link>
                </Button>
              )}
              {/* Non-modal, as in the WAI-ARIA menu button pattern: a modal menu hides the page
                  with aria-hidden while its links stay focusable (axe aria-hidden-focus). */}
              <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    aria-label={nav("account")}
                    className="h-11 gap-2 px-1.5 hover:bg-accent"
                  >
                    <Avatar initials={initials} />
                    {userName && (
                      <span className="hidden max-w-40 truncate text-base font-medium md:inline">
                        {userName}
                      </span>
                    )}
                    <ChevronDownIcon
                      aria-hidden="true"
                      className="hidden size-4 text-muted-foreground md:inline"
                    />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64 min-w-64">
                  <DropdownMenuLabel className="flex items-center gap-3 px-2 py-2">
                    <Avatar initials={initials} className="size-10" />
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-base font-semibold text-foreground">
                        {userName ?? shell("you")}
                      </span>
                      <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
                        {accountKind}
                      </span>
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
            </div>
          </div>
        </header>

        {/* The website's blueprint ground under every signed-in screen. */}
        <div className="p2b-ground flex flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
