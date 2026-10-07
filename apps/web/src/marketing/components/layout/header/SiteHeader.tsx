'use client';

import imgPlan2buildLogoDark from '@/marketing/assets/plan2build-logo-dark.png';
import imgPlan2buildLogo from '@/marketing/assets/plan2build-logo.png';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { ARROW_UP_RIGHT } from '@/marketing/components/ui/glyphs';
import type { HeaderContent } from '@/marketing/content/sections/header';
import { cx } from '@/marketing/lib/cx';
import { getSmoothScroller } from '@/marketing/lib/smoothScroll';
import { TYPE } from '@/marketing/lib/typography';
import './header.css';
import type { HeaderProject, HeaderService } from './data';
import { Drawer } from './Drawer';
import { Caret, Phone } from './icons';
import { NavAnchor } from './NavAnchor';
import { Sheet } from './Sheet';
import { useHeaderScroll } from './useHeaderScroll';

/** Below this width the nav and drawer give way to the burger and sheet (matches header.css). */
const COMPACT_QUERY = '(max-width: 1099.98px)';
/** Hover intent: the drawer opens after the mouse rests 90ms and closes 240ms after it leaves,
 * so crossing the gap between the link and the drawer does not drop it. */
const HOVER_OPEN_MS = 90;
const HOVER_CLOSE_MS = 240;
/** ArrowDown on the trigger opens the drawer, then focuses its first link once it is visible. */
const ARROW_FOCUS_MS = 60;
/** The opened sheet takes focus once its clip-path has started to reveal it. */
const SHEET_FOCUS_MS = 80;

type SiteHeaderProps = {
  copy: HeaderContent;
  siteName: string;
  phone: string;
  phoneHref: string;
  bidHref: string;
  projectsHref: string;
  /** Newest first; the drawer shows four, the sheet two. */
  projects: HeaderProject[];
  services: HeaderService[];
};

const trimSlash = (path: string) => path.replace(/\/+$/, '') || '/';

export function SiteHeader({ copy, siteName, phone, phoneHref, bidHref, projectsHref, projects, services }: SiteHeaderProps) {
  const headerRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const burgerRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef(0);
  const focusTimer = useRef(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const pathname = trimSlash(usePathname());
  const [menusPath, setMenusPath] = useState(pathname);

  // A route change closes whatever menu is open. Page transitions claim cross-route link clicks
  // before React sees them, so the header learns about the navigation from the pathname.
  if (menusPath !== pathname) {
    setMenusPath(pathname);
    setDrawerOpen(false);
    setSheetOpen(false);
  }

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const { scrolled, hidden, light, show } = useHeaderScroll(headerRef, closeDrawer);

  const isActive = (href: string) => {
    const path = trimSlash(href);
    return path === '/' ? pathname === '/' : pathname === path || pathname.startsWith(`${path}/`);
  };
  const isDrawerLink = (label: string) => !!copy.drawerFor.trim() && label.trim().toLowerCase() === copy.drawerFor.trim().toLowerCase();
  const hasDrawer = copy.links.some((link) => isDrawerLink(link.label)) && (projects.length > 0 || services.length > 0);

  // Back/forward closes whatever menu is open.
  useEffect(() => {
    const close = () => {
      setDrawerOpen(false);
      setSheetOpen(false);
    };
    window.addEventListener('popstate', close);
    return () => window.removeEventListener('popstate', close);
  }, []);

  // Crossing the compact breakpoint closes the menu that no longer exists at the new width.
  useEffect(() => {
    const media = window.matchMedia(COMPACT_QUERY);
    const onChange = () => (media.matches ? setDrawerOpen(false) : setSheetOpen(false));
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  // Escape closes the open menu and returns focus to the control that opened it.
  useEffect(() => {
    if (!drawerOpen && !sheetOpen) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (sheetOpen) {
        setSheetOpen(false);
        burgerRef.current?.focus();
      } else {
        setDrawerOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawerOpen, sheetOpen]);

  // A press anywhere outside the header closes the drawer.
  useEffect(() => {
    if (!drawerOpen) return;
    const onPointerDown = (event: globalThis.PointerEvent) => {
      if (!headerRef.current?.contains(event.target as Node)) setDrawerOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [drawerOpen]);

  // The open sheet is modal: the page stops scrolling (native and smooth) and Tab cycles
  // between the burger and the sheet's controls.
  useEffect(() => {
    if (!sheetOpen) return;
    const root = document.documentElement;
    const scroller = getSmoothScroller();
    root.style.overflow = 'hidden';
    scroller?.stop();
    const sheet = sheetRef.current;
    const focusSoon = window.setTimeout(() => sheet?.querySelector<HTMLElement>('a,button')?.focus(), SHEET_FOCUS_MS);
    const trapTab = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Tab' || !sheet) return;
      const inside = Array.from(sheet.querySelectorAll<HTMLElement>('a[href],button,input,[tabindex]:not([tabindex="-1"])'));
      const cycle = burgerRef.current ? [burgerRef.current, ...inside] : inside;
      const first = cycle[0];
      const last = cycle[cycle.length - 1];
      if (!first || !last) return;
      const current = document.activeElement as HTMLElement | null;
      if (!current || !cycle.includes(current)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && current === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && current === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', trapTab);
    return () => {
      window.clearTimeout(focusSoon);
      document.removeEventListener('keydown', trapTab);
      root.style.overflow = '';
      scroller?.start();
    };
  }, [sheetOpen]);

  useEffect(
    () => () => {
      window.clearTimeout(hoverTimer.current);
      window.clearTimeout(focusTimer.current);
    },
    [],
  );

  const drawerLinks = () => Array.from(drawerRef.current?.querySelectorAll<HTMLElement>('a[href]') ?? []);

  const hoverDrawer = (open: boolean) => (event: PointerEvent) => {
    if (event.pointerType !== 'mouse') return;
    window.clearTimeout(hoverTimer.current);
    hoverTimer.current = window.setTimeout(() => setDrawerOpen(open), open ? HOVER_OPEN_MS : HOVER_CLOSE_MS);
  };

  // The drawer sits after the bar in the DOM; Tab from the open trigger goes into it first,
  // ArrowDown opens it and moves in.
  const onTriggerKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Tab' && !event.shiftKey && drawerOpen) {
      const first = drawerLinks()[0];
      if (first) {
        event.preventDefault();
        first.focus();
      }
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setDrawerOpen(true);
      window.clearTimeout(focusTimer.current);
      focusTimer.current = window.setTimeout(() => drawerLinks()[0]?.focus(), ARROW_FOCUS_MS);
    }
  };

  // Leaving the drawer by keyboard: Shift+Tab off its first link returns to the trigger; Tab off
  // its last link closes it and continues with the bar control after the trigger.
  const onDrawerKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Tab') return;
    const links = drawerLinks();
    const trigger = triggerRef.current;
    if (!links.length || !trigger) return;
    if (event.shiftKey && document.activeElement === links[0]) {
      event.preventDefault();
      trigger.focus();
    } else if (!event.shiftKey && document.activeElement === links[links.length - 1]) {
      const barControls = Array.from(headerRef.current?.querySelectorAll<HTMLElement>('.header-in a[href],.header-in button') ?? []).filter(
        (control) => control === trigger || control.checkVisibility(),
      );
      const next = barControls[barControls.indexOf(trigger) + 1];
      if (next) {
        event.preventDefault();
        setDrawerOpen(false);
        next.focus();
      }
    }
  };

  // Following a link in the header closes the open menu (this covers same-page anchors, which
  // do not change the pathname).
  const onClick = (event: MouseEvent) => {
    if ((event.target as Element).closest('a[href]')) {
      setDrawerOpen(false);
      setSheetOpen(false);
    }
  };

  const dark = (!light && !drawerOpen) || sheetOpen;
  const className = cx(
    'gd header',
    scrolled && 'is-scr',
    hidden && !sheetOpen && !drawerOpen && 'is-hide',
    dark ? 'gd-dark is-dk' : 'is-lt',
    sheetOpen && 'is-sheet',
    drawerOpen && 'is-drawer',
  );

  return (
    <header ref={headerRef} className={className} style={TYPE.body} onFocus={show} onClick={onClick}>
      <div className="header-bar">
        <div className="header-in">
          <NavAnchor className="header-logo" href="/" aria-label={`${siteName} home`}>
            {/* Ink logo over light grounds, the white-lettered one over night. */}
            <Image className="header-mk header-mk-lt" src={imgPlan2buildLogo.src} alt="" width={480} height={111} preload />
            <Image className="header-mk header-mk-dk" src={imgPlan2buildLogoDark.src} alt="" width={480} height={111} />
            {copy.logoTag && (
              <small className="header-tag" style={TYPE.mono}>
                {copy.logoTag}
              </small>
            )}
          </NavAnchor>
          <nav className="header-nav" aria-label="Main">
            <ul>
              {copy.links.map((link) => {
                const active = isActive(link.href);
                return (
                  <li key={link.href}>
                    {hasDrawer && isDrawerLink(link.label) ? (
                      <button
                        ref={triggerRef}
                        type="button"
                        className={cx('header-link header-trig', active && 'is-act')}
                        style={TYPE.mono}
                        aria-expanded={drawerOpen}
                        aria-controls="header-drawer"
                        onClick={() => setDrawerOpen((open) => !open)}
                        onKeyDown={onTriggerKeyDown}
                        onPointerEnter={hoverDrawer(true)}
                        onPointerLeave={hoverDrawer(false)}
                      >
                        <span className="header-lt">{link.label}</span>
                        <Caret />
                      </button>
                    ) : (
                      <NavAnchor
                        href={link.href}
                        className={cx('header-link', active && 'is-act')}
                        style={TYPE.mono}
                        aria-current={active ? 'page' : undefined}
                      >
                        <span className="header-lt">{link.label}</span>
                      </NavAnchor>
                    )}
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="header-right">
            {copy.showPhone && phone && (
              <a className="header-tel" href={phoneHref}>
                <i aria-hidden="true">
                  <Phone />
                </i>
                {phone}
              </a>
            )}
            {copy.showCta && copy.ctaLabel && <Button href={copy.ctaHref || bidHref} label={copy.ctaLabel} kind="quiet" glyph={ARROW_UP_RIGHT} className="header-cta" />}
            <button
              ref={burgerRef}
              type="button"
              className="header-burger"
              aria-expanded={sheetOpen}
              aria-controls="header-sheet"
              aria-label={sheetOpen ? copy.closeLabel : copy.openMenuLabel}
              onClick={() => setSheetOpen((open) => !open)}
            >
              <i />
              <i />
              <i />
            </button>
          </div>
        </div>
      </div>
      {hasDrawer && (
        <Drawer
          ref={drawerRef}
          open={drawerOpen}
          copy={copy}
          projects={projects.slice(0, 4)}
          services={services}
          projectsHref={projectsHref}
          bidHref={bidHref}
          onKeyDown={onDrawerKeyDown}
          onPointerEnter={hoverDrawer(true)}
          onPointerLeave={hoverDrawer(false)}
        />
      )}
      <Sheet
        ref={sheetRef}
        open={sheetOpen}
        copy={copy}
        projects={projects.slice(0, 2)}
        bidHref={bidHref}
        phone={phone}
        phoneHref={phoneHref}
        isActive={isActive}
      />
    </header>
  );
}
