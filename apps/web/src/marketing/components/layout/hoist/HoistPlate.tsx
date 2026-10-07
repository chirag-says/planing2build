'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { HoistCopy } from '@/marketing/content/sections/hoist';
import { HOLD } from '@/marketing/lib/hold';
import { TYPE } from '@/marketing/lib/typography';
import type { StyleWithVars } from '@/marketing/lib/css';
import { destinationName, hoistTarget, pathLabel, trimPath } from './destination';
import './hoist.css';

type Mode = 'idle' | 'leave' | 'arrive';
type View = { mode: Mode; name: string; path: string; arrivals: number };

type Props = { copy: HoistCopy; siteName: string };

/** The covered screen waits this much past the hoist before navigating, so the last frame lands. */
const NAVIGATE_AFTER_MS = 40;
/** If the next page has not rendered by then, lift the plate anyway. */
const ARRIVAL_TIMEOUT_MS = 4000;
/** Section reveals are released this long into the arrival (plus 45% of it): the plate is
    about halfway off, so entrances play where they can be seen. */
const RELEASE_BASE_MS = 80;
const RELEASE_SHARE = 0.45;
/** The plate is hidden this long after the arrival animation's nominal end. */
const IDLE_AFTER_MS = 200;

const seconds = (value: number) => Math.max(0.3, Math.min(1.2, value));

function GirderMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="6" fill="var(--gd-ink)" />
      <path d="M8 9h16M8 23h16M16 9v14" fill="none" stroke="var(--gd-brass)" strokeWidth="3.4" strokeLinecap="square" />
    </svg>
  );
}

/**
 * Takes over clicks on internal links to other pages: the plate is hoisted over the screen,
 * the route changes behind it, and once the new page has rendered (the pathname changes) the
 * plate lifts off it. Section reveals on the new page are held (`gd-hold-pt`) until then.
 */
export function HoistPlate({ copy, siteName }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [view, setView] = useState<View>({ mode: 'idle', name: '', path: '', arrivals: 0 });
  const mode = useRef<Mode>('idle');
  const timers = useRef<number[]>([]);
  const leaveSeconds = seconds(copy.duration);
  const enterSeconds = seconds(copy.enter);
  const names = useMemo(() => new Map(copy.names.map(({ label, path }) => [trimPath(path), label])), [copy.names]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
  }, []);
  const later = useCallback((run: () => void, ms: number) => {
    timers.current.push(window.setTimeout(run, ms));
  }, []);

  const arrive = useCallback(() => {
    clearTimers();
    mode.current = 'arrive';
    setView((current) => ({ ...current, mode: 'arrive', arrivals: current.arrivals + 1 }));
    const enterMs = enterSeconds * 1000;
    later(() => document.documentElement.classList.remove(HOLD.transition), RELEASE_BASE_MS + enterMs * RELEASE_SHARE);
    later(() => {
      mode.current = 'idle';
      setView((current) => ({ ...current, mode: 'idle' }));
    }, enterMs + IDLE_AFTER_MS);
  }, [clearTimers, later, enterSeconds]);

  // Capture phase on window: runs before Next's <Link> handler, so the cover plays first and
  // the navigation is ours to start.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (mode.current === 'leave' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const target = hoistTarget(event);
      if (!target) return;
      event.preventDefault();
      event.stopPropagation();

      const { url, anchor } = target;
      const href = url.pathname + url.search + url.hash;
      clearTimers();
      mode.current = 'leave';
      setView((current) => ({
        ...current,
        mode: 'leave',
        name: destinationName(url, anchor, names, copy.homeLabel),
        path: url.pathname,
      }));
      router.prefetch(href);
      later(() => {
        // The new page's sections mount while covered and must wait for the lift-off.
        document.documentElement.classList.add(HOLD.transition);
        router.push(href);
      }, leaveSeconds * 1000 + NAVIGATE_AFTER_MS);
      later(arrive, ARRIVAL_TIMEOUT_MS);
    };
    window.addEventListener('click', onClick, true);
    return () => {
      window.removeEventListener('click', onClick, true);
      clearTimers();
      document.documentElement.classList.remove(HOLD.transition);
    };
  }, [router, names, copy.homeLabel, leaveSeconds, arrive, clearTimers, later]);

  // The new route has committed: lift the plate off it. Also covers Back pressed mid-hoist.
  useEffect(() => {
    if (mode.current === 'leave') arrive();
  }, [pathname, arrive]);

  const style: StyleWithVars = {
    ...TYPE.body,
    '--dl': `${leaveSeconds}s`,
    '--de': `${enterSeconds}s`,
    pointerEvents: view.mode === 'leave' ? 'auto' : 'none',
  };
  const className =
    view.mode === 'leave' ? 'hoist hoist-on hoist-leave' : view.mode === 'arrive' ? 'hoist hoist-on hoist-enter' : 'hoist';

  return (
    // A new key per arrival restarts the lift-off animation from the covering position.
    <div key={view.mode === 'arrive' ? `arrive-${view.arrivals}` : view.mode} className={className} aria-hidden="true" style={style}>
      <div className="hoist-plate">
        <i className="hoist-sling is-l" />
        <i className="hoist-sling is-r" />
        <i className="hoist-edge is-t" />
        <i className="hoist-edge is-b" />
        <i className="hoist-fl is-t" />
        <i className="hoist-fl is-b" />
        <div className="hoist-top" style={TYPE.mono}>
          <span className="hoist-brand" style={TYPE.display}>
            <GirderMark />
            {siteName}
          </span>
          <span className="hoist-k">
            <i />
            {copy.kicker}
          </span>
        </div>
        <div className="hoist-mid">
          <p className="hoist-nm" style={TYPE.display}>
            {view.name || copy.homeLabel}
          </p>
          <p className="hoist-path" style={TYPE.mono}>
            {pathLabel(view.path)}
          </p>
        </div>
      </div>
    </div>
  );
}
