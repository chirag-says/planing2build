'use client';

import { useEffect, type RefObject } from 'react';

/** Pointer distance (px) inside which a button leans toward the cursor. */
const REACH = 150;
/** Furthest a button moves (px). */
const PULL = 8;

/**
 * Buttons marked `data-mag` inside the section lean toward a nearby mouse pointer, by up to
 * 8px, through the `--mx` / `--my` variables their hover transform reads. Fine pointers only.
 */
export function useMagnetic(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el || !window.matchMedia('(hover:hover) and (pointer:fine)').matches) return;

    const targets = () => Array.from(el.querySelectorAll<HTMLElement>('[data-mag]'));
    const onMove = (event: PointerEvent) => {
      for (const target of targets()) {
        const rect = target.getBoundingClientRect();
        const dx = event.clientX - (rect.left + rect.width / 2);
        const dy = event.clientY - (rect.top + rect.height / 2);
        const distance = Math.hypot(dx, dy);
        const pull = distance < REACH ? (1 - distance / REACH) * PULL : 0;
        target.style.setProperty('--mx', `${(dx / (distance || 1)) * pull}px`);
        target.style.setProperty('--my', `${(dy / (distance || 1)) * pull}px`);
      }
    };
    const onLeave = () => {
      for (const target of targets()) {
        target.style.setProperty('--mx', '0px');
        target.style.setProperty('--my', '0px');
      }
    };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
    };
  }, [ref]);
}
