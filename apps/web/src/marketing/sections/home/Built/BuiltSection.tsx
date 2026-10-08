'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react';
import type { BuiltContent } from '@/marketing/content/sections/built';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import type { StyleWithVars } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { scrollPageTo } from '@/marketing/lib/smoothScroll';
import { clamp01 } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';
import { BuiltPinned } from './BuiltPinned';
import { BuiltStack } from './BuiltStack';
import type { BuiltProject } from './model';

/** Below this section width the showcase becomes a list of cards. */
const PHONE_WIDTH = 810;
/** The section reveals once 10% of it is in view. */
const REVEAL_THRESHOLD = 0.1;
/**
 * Scroll is measured in "floors": one viewport height of scrolling per project. Each photo after
 * the first wipes in over the last 0.4 floor before its own floor, and becomes the active
 * project halfway through that wipe.
 */
const WIPE = 0.4;
/** Seconds the smooth scroller takes to travel to a floor from the arrow buttons. */
const STEP_DURATION = 0.9;

const easeInOutCubic = (value: number) => {
  const t = clamp01(value);
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
};

/** Floors of scroll the pinned section is given: n - 0.4, so the last project holds a moment. */
const travelFloors = (count: number) => Math.max(0.6, count - 0.4);

type Layout = 'pin' | 'stack';

type BuiltSectionProps = {
  content: BuiltContent;
  projects: BuiltProject[];
  heading: string;
  projectsHref: string;
};

/**
 * "Built by Girder": the projects as floors of a building under construction. On desktop and
 * tablet the section is (n + 0.6) viewports tall and its stage pins while the visitor scrolls
 * through one project per viewport; on phones, and for reduced motion, it is a list of cards.
 *
 * Until the section has measured its width both layouts are rendered and CSS shows the right
 * one, so the server HTML never shows the wrong layout; after that only one is mounted.
 */
export function BuiltSection({ content, projects, heading, projectsHref }: BuiltSectionProps) {
  const ref = useRef<HTMLElement>(null);
  const revealed = useReveal(ref, REVEAL_THRESHOLD);
  useMagnetic(ref);

  const reduced = usePrefersReducedMotion();
  const width = useSectionWidth(ref);
  const layout: Layout | null = reduced ? 'stack' : width === null ? null : width < PHONE_WIDTH ? 'stack' : 'pin';
  const count = projects.length;
  // Before measuring, the server-rendered class assumes the pinned layout (CSS corrects it on
  // phones); the scroll handler waits until the layout is known.
  const pinned = layout !== 'stack' && count > 1;
  const scrollDriven = layout === 'pin' && count > 1;

  const [active, setActive] = useState(0);
  const activeIndex = Math.min(active, Math.max(0, count - 1));

  // Read by the scroll handler, which must keep one identity across renders. `pin` is the
  // latest eased --pp; it is kept even while the layout is unknown so it can be applied late.
  const frameState = useRef({ count, scrollDriven, index: 0, pin: -1 });

  const applyProgress = useCallback(() => {
    const section = ref.current;
    const state = frameState.current;
    if (!section || !state.scrollDriven || state.pin < 0) return;
    const travel = state.pin * travelFloors(state.count);
    const photos = section.querySelectorAll<HTMLElement>('.built-ph');
    let index = 0;
    let wiping = 0;
    for (let floor = 1; floor < photos.length; floor++) {
      const cover = easeInOutCubic((travel - (floor - WIPE)) / WIPE);
      photos[floor]?.style.setProperty('--c', cover.toFixed(4));
      if (cover > 0 && cover < 1) wiping = cover;
      if (travel >= floor - WIPE * 0.5) index = floor;
    }
    // --cw drives the yellow slab riding the edge of the photo being wiped in; --car is the
    // lift's position on the rail (0 at the first floor, 1 at the last).
    section.style.setProperty('--cw', wiping.toFixed(4));
    section.style.setProperty('--car', clamp01(travel / Math.max(1, state.count - 1)).toFixed(4));
    if (index !== state.index) {
      state.index = index;
      setActive(index);
    }
  }, []);

  useLayoutEffect(() => {
    frameState.current.count = count;
    frameState.current.scrollDriven = scrollDriven;
    // Progress only reports changes, so catch up with any that arrived before the layout was known.
    applyProgress();
  }, [count, scrollDriven, applyProgress]);

  const onProgress = useCallback(
    (_pass: number, pin: number) => {
      frameState.current.pin = pin;
      applyProgress();
    },
    [applyProgress],
  );
  useScrollProgress(ref, { onProgress });

  /** Scrolls the page to the position where project `index` has fully arrived. */
  const step = useCallback(
    (index: number) => {
      const section = ref.current;
      if (!section || index < 0 || index > count - 1) return;
      const rect = section.getBoundingClientRect();
      const top =
        rect.top + window.scrollY + (index / travelFloors(count)) * (rect.height - window.innerHeight) + 2;
      scrollPageTo(top, { duration: STEP_DURATION });
    },
    [count],
  );

  /** Scrolls to the end of the pinned section, so the next one starts at the top of the viewport. */
  const skip = useCallback(() => {
    const section = ref.current;
    if (!section) return;
    scrollPageTo(section.getBoundingClientRect().bottom + window.scrollY, { duration: STEP_DURATION });
  }, []);

  const style: StyleWithVars = {
    ...TYPE.body,
    background: 'var(--gd-night)',
    color: 'var(--gd-cloud)',
    '--n': count,
  };

  return (
    <section
      ref={ref}
      id="built"
      className={cx('gd gd-sec gd-dark built', pinned && 'is-pin', revealed && 'is-in')}
      style={style}
    >
      {layout !== 'stack' && (
        <BuiltPinned
          content={content}
          projects={projects}
          heading={heading}
          projectsHref={projectsHref}
          active={activeIndex}
          pinned={scrollDriven}
          onStep={step}
          onSkip={skip}
        />
      )}
      {layout !== 'pin' && (
        <BuiltStack content={content} projects={projects} heading={heading} projectsHref={projectsHref} />
      )}
    </section>
  );
}

/** The section's rendered width, or null before it has been measured. */
function useSectionWidth(ref: RefObject<HTMLElement | null>): number | null {
  const [width, setWidth] = useState<number | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.round(entry?.borderBoxSize?.[0]?.inlineSize ?? el.offsetWidth);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
