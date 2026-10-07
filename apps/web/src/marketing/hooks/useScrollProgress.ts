'use client';

import { useEffect, type RefObject } from 'react';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { decodeImagesAhead } from '@/marketing/lib/images';

/** Fraction of the remaining distance the eased value covers each frame. */
const SMOOTHING = 0.18;

export type ScrollProgressListener = (pass: number, pin: number) => void;

/**
 * Publishes how far a section has travelled through the viewport as two CSS variables on the
 * section element, eased toward the true value every frame:
 *
 *   --sp  "pass": 0 when the section's top meets the bottom of the viewport, 1 when its bottom
 *         leaves the top.
 *   --pp  "pin": for sections taller than the viewport, 0 when the top reaches the top of the
 *         viewport and 1 when the bottom reaches the bottom. Otherwise equal to --sp.
 *
 * Off-screen sections stop measuring once their eased value has settled.
 */
export function useScrollProgress(
  ref: RefObject<HTMLElement | null>,
  { enabled = true, onProgress }: { enabled?: boolean; onProgress?: ScrollProgressListener } = {},
) {
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    decodeImagesAhead(el);

    let visible = true;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
    }, { rootMargin: '25% 0px 25% 0px' });
    observer.observe(el);

    let top = 0;
    let height = 0;
    let viewport = 1;
    let measured = false;
    let settled = false;
    let pass = -1;
    let pin = -1;
    let written = -9;

    const stop = onFrame({
      read: () => {
        if (!visible && settled) {
          measured = false;
          return;
        }
        const rect = el.getBoundingClientRect();
        top = rect.top;
        height = rect.height;
        viewport = window.innerHeight || 1;
        measured = true;
      },
      write: () => {
        if (!measured) return;
        const passTarget = clamp01((viewport - top) / (viewport + height));
        const pinTarget = height > viewport * 1.05 ? clamp01(-top / (height - viewport)) : passTarget;
        if (pass < 0) {
          pass = passTarget;
          pin = pinTarget;
        } else {
          pass += (passTarget - pass) * SMOOTHING;
          pin += (pinTarget - pin) * SMOOTHING;
          if (Math.abs(passTarget - pass) < 5e-4) pass = passTarget;
          if (Math.abs(pinTarget - pin) < 5e-4) pin = pinTarget;
        }
        settled = pass === passTarget && pin === pinTarget;
        if (Math.abs(pass + pin - written) < 3e-4) return;
        written = pass + pin;
        el.style.setProperty('--sp', pass.toFixed(4));
        el.style.setProperty('--pp', pin.toFixed(4));
        onProgress?.(pass, pin);
      },
    });

    return () => {
      stop();
      observer.disconnect();
    };
  }, [ref, enabled, onProgress]);
}
