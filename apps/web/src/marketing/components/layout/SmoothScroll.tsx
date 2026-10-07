'use client';

import type Lenis from 'lenis';
import { useEffect } from 'react';
import { registerSmoothScroller } from '@/marketing/lib/smoothScroll';
import { onFrame } from '@/marketing/lib/ticker';

/** Lenis lerp: each frame the page covers 10% of the remaining distance to the wheel target. */
const SMOOTHNESS = 0.1;
const WHEEL_SPEED = 1;
/** Same-page anchors land this far below the top, clear of the fixed header bar. */
const ANCHOR_OFFSET = 72;
/** Space kept between a focused control and the edge of the row it scrolls in. */
const FOCUS_MARGIN = 24;

/** Smooth wheel scrolling only where it helps: a mouse or trackpad, with motion allowed. */
const SMOOTH_QUERY = '(hover: hover) and (pointer: fine)';
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/**
 * Keyboard focus inside a sideways-scrolling row (tabs, chips, rails) scrolls the row so the
 * focused control is fully visible, 24px clear of the row's edge.
 */
function revealFocusedInRow(event: FocusEvent) {
  const target = event.target;
  if (!(target instanceof Element) || !target.matches(':focus-visible')) return;
  for (let row = target.parentElement; row && row !== document.body; row = row.parentElement) {
    const { overflowX } = getComputedStyle(row);
    // The 2px tolerance ignores rows that only overflow by rounding.
    if ((overflowX === 'auto' || overflowX === 'scroll') && row.scrollWidth > row.clientWidth + 2) {
      const rowBox = row.getBoundingClientRect();
      const box = target.getBoundingClientRect();
      if (box.left < rowBox.left + FOCUS_MARGIN) row.scrollLeft -= rowBox.left + FOCUS_MARGIN - box.left;
      else if (box.right > rowBox.right - FOCUS_MARGIN) row.scrollLeft += box.right - (rowBox.right - FOCUS_MARGIN);
      return;
    }
  }
}

/**
 * Same-page `#anchor` links glide to their target instead of jumping. Returns false when the
 * click is not one of them.
 */
function glideToAnchor(event: MouseEvent, lenis: Lenis): boolean {
  const link = event.target instanceof Element ? event.target.closest("a[href*='#']") : null;
  if (!link) return false;
  const href = link.getAttribute('href') ?? '';
  const hashAt = href.indexOf('#');
  const path = href.slice(0, hashAt);
  if (path && path !== window.location.pathname) return false;
  const id = href.slice(hashAt + 1);
  const target = id ? document.getElementById(id) : null;
  if (!target) return false;
  event.preventDefault();
  history.pushState(null, '', `#${id}`);
  // Start on the next frame: a link in the open phone menu closes it during this click, and
  // Lenis ignores scrollTo while the menu holds it stopped.
  requestAnimationFrame(() => lenis.scrollTo(target, { offset: -ANCHOR_OFFSET }));
  return true;
}

/**
 * Page-wide smooth scrolling (Lenis), advanced in the shared ticker's `pre` phase so every
 * section reads positions Lenis has already moved that frame. Loaded on demand: touch screens
 * and reduced-motion visitors never download it.
 */
export function SmoothScroll() {
  useEffect(() => {
    document.addEventListener('focusin', revealFocusedInRow);
    return () => document.removeEventListener('focusin', revealFocusedInRow);
  }, []);

  useEffect(() => {
    if (window.matchMedia(REDUCED_MOTION_QUERY).matches || !window.matchMedia(SMOOTH_QUERY).matches) return;

    let cancelled = false;
    let teardown = () => {};
    import('lenis')
      .then(({ default: LenisScroller }) => {
        if (cancelled) return;
        // Lenis adds and maintains the `lenis` class on <html> itself.
        const lenis = new LenisScroller({ lerp: SMOOTHNESS, wheelMultiplier: WHEEL_SPEED, smoothWheel: true });
        registerSmoothScroller(lenis);
        const stopFrames = onFrame({ pre: (time) => lenis.raf(time), write: () => {} });
        const onClick = (event: MouseEvent) => glideToAnchor(event, lenis);
        // Capture phase: the click is claimed before next/link's handler runs, which then
        // sees it prevented and stays out of the way.
        document.addEventListener('click', onClick, true);
        teardown = () => {
          document.removeEventListener('click', onClick, true);
          stopFrames();
          registerSmoothScroller(null);
          lenis.destroy();
        };
      })
      .catch(() => {
        // Without Lenis the page keeps native scrolling.
      });

    return () => {
      cancelled = true;
      teardown();
    };
  }, []);

  return null;
}
