'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';
import { isGroundLight } from './ground';

/** Past this scroll position the bar turns solid. */
const SOLID_AFTER = 40;
/** Above this position the bar is always shown. */
const ALWAYS_SHOWN_ABOVE = 120;
/** Scroll movement between two samples (px) that counts as a direction. */
const DIRECTION_STEP = 6;
/** A new ground colour must hold this long before the bar follows it, so it does not flicker
 * while a thin band or an image edge passes under it. */
const GROUND_SETTLE_MS = 150;
/** Re-check a pending ground change just after it could have settled. */
const GROUND_RECHECK_MS = 170;
/** Trailing samples after the last scroll event, so the state is right once motion stops
 * (smooth scrolling and reveal transitions keep moving things after the event). */
const TRAILING_SAMPLES_MS = [260, 900];
/** Samples after mount, once fonts, images and the loader have moved things. */
const SETTLE_SAMPLES_MS = [900, 2400];

type HeaderScroll = {
  /** The page has moved off the top: the bar is a solid slab. */
  scrolled: boolean;
  /** Scrolling down: the bar slides away. */
  hidden: boolean;
  /** What is under the bar is light. */
  light: boolean;
  show: () => void;
};

/**
 * Scroll-driven header state, sampled once per animation frame after each scroll or resize
 * event (never per frame while idle). `onScrollDown` fires when the bar hides.
 */
export function useHeaderScroll(headerRef: RefObject<HTMLElement | null>, onScrollDown: () => void): HeaderScroll {
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [light, setLight] = useState(true);
  const onScrollDownRef = useRef(onScrollDown);

  useEffect(() => {
    onScrollDownRef.current = onScrollDown;
  }, [onScrollDown]);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;
    let lastY = window.scrollY;
    let committed: boolean | null = null;
    let pending: boolean | null = null;
    let pendingSince = 0;
    let frame = 0;
    let trailing: number[] = [];
    const timers: number[] = [];

    const followGround = () => {
      const next = isGroundLight(header);
      const now = performance.now();
      if (committed === null || (next !== committed && pending === next && now - pendingSince >= GROUND_SETTLE_MS)) {
        committed = next;
        pending = null;
        setLight(next);
      } else if (next === committed) {
        pending = null;
      } else if (pending !== next) {
        pending = next;
        pendingSince = now;
        timers.push(window.setTimeout(schedule, GROUND_RECHECK_MS));
      }
    };

    const sample = () => {
      const y = window.scrollY;
      setScrolled(y > SOLID_AFTER);
      const delta = y - lastY;
      if (y < ALWAYS_SHOWN_ABOVE) setHidden(false);
      else if (delta > DIRECTION_STEP) {
        setHidden(true);
        onScrollDownRef.current();
      } else if (delta < -DIRECTION_STEP) setHidden(false);
      lastY = y;
      followGround();
    };

    const sampleNextFrame = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(sample);
    };
    function schedule() {
      sampleNextFrame();
      trailing.forEach((id) => window.clearTimeout(id));
      trailing = TRAILING_SAMPLES_MS.map((ms) => window.setTimeout(sampleNextFrame, ms));
    }

    sample();
    SETTLE_SAMPLES_MS.forEach((ms) => timers.push(window.setTimeout(sample, ms)));
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      cancelAnimationFrame(frame);
      [...timers, ...trailing].forEach((id) => window.clearTimeout(id));
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
    };
  }, [headerRef]);

  return { scrolled, hidden, light, show: () => setHidden(false) };
}
