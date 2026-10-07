'use client';

import { createContext, useCallback, useContext, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import type { StyleWithVars } from '@/marketing/lib/css';
import { clamp01 } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';

/**
 * How the stat figures show their digits:
 *   zero  – blank strips, waiting for the board to land
 *   roll  – each strip spins up to its digit (CSS animation), replayable on hover
 *   final – digits shown at rest (reduced motion)
 */
export type BoardMode = 'zero' | 'roll' | 'final';

const BoardModeContext = createContext<BoardMode>('zero');

export const useBoardMode = () => useContext(BoardModeContext);

/*
 * The rig follows the section's pass progress (--sp, 0 → 1 as it crosses the viewport):
 * it is lowered between 0.15 and 0.45 (cubic ease-out), swinging 1.25 times with a 1.3°
 * amplitude that dies out as it lands; between 0.45 and 0.51 the sling lifts away (--rt).
 * The figures start counting just after the release begins.
 */
const LOWER_FROM = 0.15;
const LOWER_SPAN = 0.3;
const SWING_HALF_TURNS = 2.5;
const SWING_DEGREES = 1.3;
const RELEASE_FROM = 0.45;
const RELEASE_SPAN = 0.06;
const COUNT_FROM = 0.455;

const subscribeNothing = () => () => {};

type BoardShellProps = { style?: StyleWithVars; children: ReactNode };

/** Section root of the site board: reveal, the crane-lowering scroll mechanic and the count mode. */
export function BoardShell({ style, children }: BoardShellProps) {
  const ref = useRef<HTMLElement>(null);
  const reduced = usePrefersReducedMotion();
  const hydrated = useSyncExternalStore(subscribeNothing, () => true, () => false);
  const revealed = useReveal(ref);
  const [landed, setLanded] = useState(false);
  const landedRef = useRef(false);

  const onProgress = useCallback((pass: number) => {
    const el = ref.current;
    if (!el) return;
    const lower = clamp01((pass - LOWER_FROM) / LOWER_SPAN);
    const swing = Math.sin(lower * Math.PI * SWING_HALF_TURNS) * (1 - lower) * SWING_DEGREES;
    el.style.setProperty('--lo', (1 - (1 - lower) ** 3).toFixed(4));
    el.style.setProperty('--sw', swing.toFixed(3));
    el.style.setProperty('--rt', clamp01((pass - RELEASE_FROM) / RELEASE_SPAN).toFixed(3));
    if (!landedRef.current && pass > COUNT_FROM) {
      landedRef.current = true;
      setLanded(true);
    }
  }, []);
  useScrollProgress(ref, { onProgress });

  const mode: BoardMode = reduced ? 'final' : landed && revealed ? 'roll' : 'zero';

  return (
    <section
      ref={ref}
      className={cx('gd gd-sec board', revealed && 'is-in', hydrated && !reduced && 'is-live')}
      style={{ ...TYPE.body, ...style }}
    >
      <BoardModeContext.Provider value={mode}>{children}</BoardModeContext.Provider>
    </section>
  );
}
