'use client';

import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import type { StyleWithVars } from '@/marketing/lib/css';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';

/** The footer reveals when 5% of it is in view (and, when lifted, once the lift passes 0.24). */
const REVEAL_THRESHOLD = 0.05;
/** Without the lift, the beam lowers while the footer's pass progress runs 0.16 → 0.50. */
const FLAT_START = 0.16;
const FLAT_SPAN = 0.34;
/** Largest beam tilt (deg) with the pointer at either edge of the footer. */
const MAX_TILT = 0.6;
/** Fraction of the remaining tilt covered each frame: a slow, heavy swing. */
const TILT_SMOOTHING = 0.06;
/** The slings sit 47% of the footer width either side of the beam's centre. */
const SLING_ARM = 0.47;

type FooterRootProps = {
  id?: string;
  style: StyleWithVars;
  children: ReactNode;
};

/**
 * The `<footer>` element and its behaviour: reveal, magnetic buttons, the beam's descent
 * (`--rv`, read by footer.css as `--be`) and its tilt toward the pointer.
 */
export function FooterRoot({ id, style, children }: FooterRootProps) {
  const ref = useRef<HTMLElement>(null);
  const reduced = usePrefersReducedMotion();
  const revealed = useReveal(ref, REVEAL_THRESHOLD);
  useMagnetic(ref);

  // Inside an active lift the footer inherits the wrapper's --rv. Otherwise (lift off, or
  // switched off by keyboard focus) it drives its own from scroll and `data-flat` shortens the
  // beam's drop so it still reads as a descent over the shorter distance.
  const onProgress = useCallback((pass: number) => {
    const el = ref.current;
    if (!el) return;
    if (el.closest('.gd-rev')?.classList.contains('is-act')) {
      el.style.removeProperty('--rv');
      el.removeAttribute('data-flat');
      return;
    }
    el.setAttribute('data-flat', '');
    el.style.setProperty('--rv', clamp01((pass - FLAT_START) / FLAT_SPAN).toFixed(4));
  }, []);
  useScrollProgress(ref, { onProgress });

  useEffect(() => {
    const el = ref.current;
    if (reduced || !el || !window.matchMedia('(hover:hover) and (pointer:fine)').matches) return;

    let target = 0;
    let tilt = 0;
    let width = el.offsetWidth || 1;
    const onMove = (event: PointerEvent) => {
      width = el.offsetWidth || 1;
      target = Math.max(-1, Math.min(1, (event.clientX / width - 0.5) * 2)) * MAX_TILT;
    };
    const onLeave = () => {
      target = 0;
    };
    el.addEventListener('pointermove', onMove, { passive: true });
    el.addEventListener('pointerleave', onLeave);

    const stop = onFrame({
      write: () => {
        if (Math.abs(target - tilt) < 0.002) {
          if (tilt === target) return;
          tilt = target;
        } else {
          tilt += (target - tilt) * TILT_SMOOTHING;
        }
        el.style.setProperty('--tilt', tilt.toFixed(3));
        // Vertical travel of each sling's end as the beam rotates about its centre.
        el.style.setProperty('--dy', (Math.tan((tilt * Math.PI) / 180) * width * SLING_ARM).toFixed(2));
      },
    });

    return () => {
      stop();
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      el.style.removeProperty('--tilt');
      el.style.removeProperty('--dy');
    };
  }, [reduced]);

  return (
    <footer
      ref={ref}
      id={id}
      className={cx('gd gd-dark gd-sec footer', revealed && 'is-in', reduced && 'is-fin')}
      style={{ ...TYPE.body, ...(reduced ? { '--rv': 1 } : {}), ...style }}
    >
      {children}
    </footer>
  );
}
