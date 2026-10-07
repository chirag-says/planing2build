'use client';

import { useEffect, useState, type RefObject } from 'react';
import { whenReleased } from '@/marketing/lib/hold';
import { onFrame } from '@/marketing/lib/ticker';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

/** How far the footer's lift must have progressed before content inside it may reveal. */
const LIFT_GATE = 0.24;

/**
 * True once the section has scrolled into view, after the loader or page-transition cover has
 * cleared. Reduced-motion visitors get `true` immediately.
 *
 * The visible fraction needed is `threshold`, or less for sections taller than the viewport
 * (30% of the viewport's height worth of the section is always enough).
 *
 * Keyboard focus inside the section reveals it at once and suspends its transitions
 * (`data-kb`), so tabbing never lands on something still fading in.
 */
export function useReveal(ref: RefObject<HTMLElement | null>, threshold = 0.16): boolean {
  const reduced = usePrefersReducedMotion();
  const [revealed, setRevealed] = useState(false);
  const [released, setReleased] = useState(false);

  useEffect(() => whenReleased(() => setReleased(true)), []);

  useEffect(() => {
    const el = ref.current;
    if (reduced || !released || !el) return;

    let stopLiftWatch = () => {};
    const onFocusIn = (event: FocusEvent) => {
      const target = event.target as Element | null;
      if (target?.matches(':focus-visible')) {
        el.setAttribute('data-kb', '');
        void el.offsetWidth; // apply the transition kill before the reveal class lands
      }
      setRevealed(true);
    };
    const onFocusOut = (event: FocusEvent) => {
      if (!el.contains(event.relatedTarget as Node | null)) el.removeAttribute('data-kb');
    };
    el.addEventListener('focusin', onFocusIn);
    el.addEventListener('focusout', onFocusOut);

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        stopLiftWatch = onFrame({
          write: () => {
            const lift = el.closest<HTMLElement>('.gd-rev.is-act');
            const progress = lift ? parseFloat(lift.style.getPropertyValue('--rv') || '0') : 1;
            if (progress > LIFT_GATE) {
              setRevealed(true);
              stopLiftWatch();
            }
          },
        });
      },
      {
        threshold: Math.min(threshold, Math.max(0.005, (window.innerHeight * 0.3) / Math.max(1, el.offsetHeight))),
        rootMargin: '0px 0px -6% 0px',
      },
    );
    observer.observe(el);

    return () => {
      observer.disconnect();
      stopLiftWatch();
      el.removeEventListener('focusin', onFocusIn);
      el.removeEventListener('focusout', onFocusOut);
    };
  }, [ref, threshold, reduced, released]);

  return reduced || revealed;
}
