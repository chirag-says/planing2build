"use client";

import { cn } from "cn";
import { CircleUserRoundIcon, LogOutIcon, MenuIcon, FolderOpenIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
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

const t = getTranslator("Nav");

export interface NavLink {
  href: string;
  label: string;
}

function isCurrent(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function useSignOut() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try {
      await browserApi.POST("/api/v1/auth/logout");
    } finally {
      router.refresh();
      setBusy(false);
    }
  }
  return { busy, signOut };
}

/**
 * The shell header shared by every host (UI_DESIGN_SYSTEM.md section 9). Each host passes its own
 * brand, links and account links; the behaviour (current page, account menu, phone menu, skip
 * link) is the same everywhere. The look is the public website's header bar: the logo with its
 * mono tag, mono caps links, and the brass square on the current page.
 */
export function HeaderNav({
  brand,
  tag,
  links,
  accountLinks = [],
  signedIn,
  signInHref = "/sign-in",
}: {
  brand: string;
  /** Small caps line under the logo ("Homeowner", "Professionals"). */
  tag?: string;
  links: NavLink[];
  accountLinks?: NavLink[];
  signedIn: boolean;
  signInHref?: string;
}) {
  const pathname = usePathname();
  const { busy, signOut } = useSignOut();
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = (onNavigate?: () => void, stacked = false) =>
    links.map((link) => {
      const current = isCurrent(pathname, link.href);
      return (
        <Link
          key={link.href}
          href={link.href}
          onClick={onNavigate}
          aria-current={current ? "page" : undefined}
          className={cn(
            "inline-flex min-h-11 items-center gap-2 rounded-md px-3 font-mono text-xs tracking-widest text-muted-foreground uppercase transition-colors hover:text-foreground sm:min-h-10",
            current && "text-foreground",
            stacked && "w-full text-sm",
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              "size-2 bg-brand ring-1 ring-foreground transition-transform",
              current ? "scale-100" : "scale-0",
            )}
          />
          {link.label}
        </Link>
      );
    });

  return (
    <header className="border-b-2 border-foreground/10 bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        {t("skip")}
      </a>
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:h-18 sm:px-6">
        <Link href="/" className="flex shrink-0 flex-col gap-1 rounded-md">
          <Image src={logo} alt="" className="h-7 w-auto sm:h-8" priority />
          <span className="sr-only">{brand}</span>
          {tag && (
            <span aria-hidden="true" className="font-mono text-[0.625rem] tracking-widest text-muted-foreground uppercase">
              {tag}
            </span>
          )}
        </Link>

        <nav aria-label={t("main")} className="hidden items-center gap-1 sm:flex">
          {navLinks()}
          {signedIn ? (
            // Non-modal, as in the WAI-ARIA menu button pattern: a modal menu hides the page with
            // aria-hidden while its links stay focusable (axe aria-hidden-focus).
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="ml-2">
                  <CircleUserRoundIcon aria-hidden="true" />
                  {t("account")}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-48">
                {accountLinks.map((link) => (
                  <DropdownMenuItem key={link.href} asChild>
                    <Link href={link.href}>
                      <FolderOpenIcon aria-hidden="true" />
                      {link.label}
                    </Link>
                  </DropdownMenuItem>
                ))}
                {accountLinks.length > 0 && <DropdownMenuSeparator />}
                <DropdownMenuItem disabled={busy} onSelect={signOut}>
                  <LogOutIcon aria-hidden="true" />
                  {busy ? t("signingOut") : t("signOut")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button asChild className="ml-2">
              <Link href={signInHref}>{t("signIn")}</Link>
            </Button>
          )}
        </nav>

        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" className="sm:hidden" aria-label={t("openMenu")}>
              <MenuIcon aria-hidden="true" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-72">
            <SheetHeader>
              <SheetTitle>{t("menu")}</SheetTitle>
              <SheetDescription className="sr-only">{brand}</SheetDescription>
            </SheetHeader>
            <nav aria-label={t("main")} className="flex flex-col gap-1 px-4">
              {navLinks(() => setMenuOpen(false), true)}
              <Separator className="my-3" />
              {signedIn ? (
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={async () => {
                    await signOut();
                    setMenuOpen(false);
                  }}
                >
                  <LogOutIcon aria-hidden="true" />
                  {busy ? t("signingOut") : t("signOut")}
                </Button>
              ) : (
                <Button asChild>
                  <Link href={signInHref} onClick={() => setMenuOpen(false)}>
                    {t("signIn")}
                  </Link>
                </Button>
              )}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
