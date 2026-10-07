'use client';

import { useEffect, useRef, useState, useSyncExternalStore, type FocusEvent, type ReactNode } from 'react';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { cx } from '@/marketing/lib/cx';
import type { StyleWithVars } from '@/marketing/lib/css';
import { scrollPageTo } from '@/marketing/lib/smoothScroll';
import { clamp01, onFrame } from '@/marketing/lib/ticker';

/** Fraction of the remaining distance `--rv` covers each frame. */
const SMOOTHING = 0.18;
/** Changes smaller than this are not written (keeps style recalcs off settled frames). */
const WRITE_EPSILON = 4e-4;
/** Below this distance the eased value jumps to the target. */
const SNAP_EPSILON = 5e-4;

type LiftRevealProps = {
  /** Stacking order while lifted; must be lower than the content above (sections sit at 10). */
  layer?: number;
  style?: StyleWithVars;
  children: ReactNode;
};

const subscribeNever = () => () => {};

/** True after hydration, false while server rendering. */
function useMounted(): boolean {
  return useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );
}

/**
 * The "lift" reveal: the content waits pinned at the bottom of the viewport, underneath the page
 * above it, and is uncovered as that page slides up and away.
 *
 * Mechanics (rules in kit.css under `.gd-rev`): once active, the wrapper pulls itself up by the
 * content height `--t` (capped at one viewport) and the content becomes `position: sticky` at
 * `100vh - --t`; a spacer of `--t` below it supplies the scroll distance. `--rv` goes 0 → 1 over
 * that distance, eased per frame, and drives the shadow on the lifting edge, the darkening of
 * the uncovered content and any child reveals (useReveal waits for `--rv` > 0.24).
 *
 * Keyboard focus landing inside switches the lift off for good, so the focused control is never
 * left underneath the page above; pointer or programmatic focus instead scrolls to where the
 * lift is complete.
 */
export function LiftReveal({ layer = 9, style, children }: LiftRevealProps) {
  const mounted = useMounted();
  const reduced = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const spacerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [detached, setDetached] = useState(false);
  const measuring = mounted && !reduced;
  const active = measuring && height > 0 && !detached;

  useEffect(() => {
    const inner = innerRef.current;
    if (!measuring || !inner) return;
    // The observer reports once on observe, which supplies the first measurement.
    const observer = new ResizeObserver(() => setHeight(inner.offsetHeight));
    observer.observe(inner);
    return () => observer.disconnect();
  }, [measuring]);

  useEffect(() => {
    const root = rootRef.current;
    if (!active || !root) return;

    let visible = true;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
    }, { rootMargin: '30% 0px 30% 0px' });
    observer.observe(root);

    let measured = false;
    let lift = 0;
    let viewport = 1;
    let top = 0;
    let eased = -1;
    let written = -1;

    const stop = onFrame({
      read: () => {
        if (!visible) {
          measured = false;
          return;
        }
        lift = spacerRef.current?.offsetHeight ?? 0;
        viewport = window.innerHeight;
        top = root.getBoundingClientRect().top;
        measured = true;
      },
      write: () => {
        if (!measured || !lift) return;
        // 0 while the wrapper's top edge is a full lift below the viewport bottom, 1 once the
        // spacer has scrolled fully into view.
        const target = clamp01((viewport - lift - top) / lift);
        if (eased < 0 || root.dataset.snap) {
          eased = target;
          delete root.dataset.snap;
        } else {
          eased += (target - eased) * SMOOTHING;
          if (Math.abs(target - eased) < SNAP_EPSILON) eased = target;
        }
        if (Math.abs(eased - written) < WRITE_EPSILON) return;
        written = eased;
        root.style.setProperty('--rv', eased.toFixed(4));
      },
    });

    return () => {
      stop();
      observer.disconnect();
    };
  }, [active]);

  const onFocusCapture = (event: FocusEvent<HTMLDivElement>) => {
    const root = rootRef.current;
    if (!active || !root) return;
    const target = event.target as HTMLElement;

    if (target.matches(':focus-visible')) {
      setDetached(true);
      // Two frames: one for React to drop `is-act`, one for the page to lay out without it.
      requestAnimationFrame(() => requestAnimationFrame(() => target.scrollIntoView({ block: 'center' })));
      return;
    }

    // Scroll to where the lift has finished, and skip the easing so it lands there at once.
    const lift = spacerRef.current?.offsetHeight ?? 0;
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    const liftedAt = root.getBoundingClientRect().top + window.scrollY - window.innerHeight + 2 * lift;
    const destination = Math.max(0, Math.min(maxScroll, liftedAt));
    if (Math.abs(window.scrollY - destination) > 4) scrollPageTo(destination, { immediate: true });
    root.dataset.snap = '1';
    requestAnimationFrame(() => {
      const rect = target.getBoundingClientRect();
      if (rect.top < 0 || rect.bottom > window.innerHeight) target.scrollIntoView({ block: 'nearest' });
    });
  };

  const rootStyle: StyleWithVars = { ...style, '--h': `${height}px`, '--layer': layer };

  return (
    <div
      ref={rootRef}
      className={cx('gd-rev', active && 'is-act')}
      style={rootStyle}
      onFocusCapture={onFocusCapture}
    >
      <div ref={innerRef} className="gd-rev-in">
        {children}
      </div>
      <div ref={spacerRef} className="gd-rev-sp" aria-hidden="true" />
    </div>
  );
}
