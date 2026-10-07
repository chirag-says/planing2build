'use client';

import { useEffect, type RefObject } from 'react';
import { decodeImagesAhead } from '@/marketing/lib/images';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { dropEase } from './model';

/** Fraction of the remaining distance the eased values cover each frame. */
const SMOOTHING = 0.18;
/** Below this section width the card hangs from the short rail (tablet and phone layouts). */
const STACKED_BELOW = 1100;
/** The photo has finished zooming out once 56% of the section's travel has passed. */
const ZOOM_SPAN = 0.56;

/**
 * Drives the section's scroll choreography through CSS variables on the section element:
 *
 *   --zo  photo zoom-out, 0 -> 1 over the first 56% of the section's pass through the viewport
 *   --dr  card drop, eased with an overshoot; 0 = hoisted up out of view, 1 = in place
 *   --sw  card sway in degrees, a decaying swing while it drops
 *   --dl  deal progress for the chips, drop zone and button (each waits its turn, see --i)
 *
 * All four follow the bay's position: `bay` is 0 when the card bay's top meets the bottom of
 * the viewport and 1 when it reaches the top. Side by side (desktop) the card drops while that
 * runs 0.16 -> 0.90 and the answers deal from 0.5; stacked, the drop is shorter (0.16 -> 0.58)
 * and the answers deal from 0.22.
 *
 * Also keeps keyboard focus inside the section visible: a focused control that lands under the
 * header or at the bottom edge is scrolled to the middle of the viewport.
 */
export function useCardDrop(sectionRef: RefObject<HTMLElement | null>, bayRef: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const section = sectionRef.current;
    const bay = bayRef.current;
    if (!enabled || !section || !bay) return;

    decodeImagesAhead(section);

    let visible = true;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
    }, { rootMargin: '25% 0px 25% 0px' });
    observer.observe(section);

    let measured = false;
    let sectionTop = 0;
    let sectionHeight = 1;
    let bayTop = 0;
    let viewport = 1;
    let stacked = false;
    let bayProgress = -9;
    let zoom = -9;
    let written = -9;

    const stop = onFrame({
      read: () => {
        if (!visible) {
          measured = false;
          return;
        }
        const rect = section.getBoundingClientRect();
        sectionTop = rect.top;
        sectionHeight = rect.height;
        bayTop = bay.getBoundingClientRect().top;
        viewport = window.innerHeight || 1;
        stacked = section.offsetWidth < STACKED_BELOW;
        measured = true;
      },
      write: () => {
        if (!measured) return;
        const bayTarget = (viewport - bayTop) / viewport;
        const zoomTarget = clamp01((viewport - sectionTop) / (viewport + sectionHeight) / ZOOM_SPAN);
        if (bayProgress < -8) {
          bayProgress = bayTarget;
          zoom = zoomTarget;
        } else {
          bayProgress += (bayTarget - bayProgress) * SMOOTHING;
          zoom += (zoomTarget - zoom) * SMOOTHING;
          if (Math.abs(bayTarget - bayProgress) < 5e-4) bayProgress = bayTarget;
          if (Math.abs(zoomTarget - zoom) < 5e-4) zoom = zoomTarget;
        }
        if (Math.abs(bayProgress + zoom - written) < 3e-4) return;
        written = bayProgress + zoom;

        const drop = clamp01((bayProgress - 0.16) / (stacked ? 0.42 : 0.74));
        // Two and a half swings that die out as the card lands; wider on the tall desktop drop.
        const sway = Math.sin(drop * Math.PI * 2.5) * (1 - drop) * (stacked ? 0.5 : 1.3);
        const deal = stacked ? (bayProgress - 0.22) / 0.36 : (bayProgress - 0.5) / 0.3;
        section.style.setProperty('--zo', zoom.toFixed(4));
        section.style.setProperty('--dr', dropEase(drop).toFixed(4));
        section.style.setProperty('--sw', sway.toFixed(3));
        section.style.setProperty('--dl', deal.toFixed(4));
      },
    });

    const onFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (!(target instanceof Element) || !target.matches(':focus-visible')) return;
      // Two frames: let the reveal and the card snap into place (data-kb) before measuring.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          const rect = target.getBoundingClientRect();
          if (rect.top < 96 || rect.bottom > window.innerHeight - 40) target.scrollIntoView({ block: 'center' });
        }),
      );
    };
    section.addEventListener('focusin', onFocusIn);

    return () => {
      stop();
      observer.disconnect();
      section.removeEventListener('focusin', onFocusIn);
      for (const name of ['--zo', '--dr', '--sw', '--dl']) section.style.removeProperty(name);
    };
  }, [sectionRef, bayRef, enabled]);
}
