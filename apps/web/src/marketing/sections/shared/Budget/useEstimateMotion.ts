'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, type RefObject } from 'react';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { formatMoney, type Estimate } from './estimate';

/** Tape ticks: a damped spring, so they overshoot a little and settle. */
const SPRING_PULL = 0.085;
const SPRING_KEEP = 0.8;
/** Money and weeks: each frame closes 13% of the remaining distance. */
const EASE = 0.13;
/** Scroll pass (--sp) at which the figures start counting up, and the distance over which they reach full. */
const COUNT_FROM = 0.2;
const COUNT_OVER = 0.3;

type Values = [tapeLow: number, tapeHigh: number, low: number, high: number, weeks: number];

const toValues = (result: Estimate): Values => [result.tapeLow, result.tapeHigh, result.low, result.high, result.weeks];

type MotionState = {
  current: Values;
  velocity: Values;
  target: Values;
  /** Count-up factor every shown value is multiplied by. */
  scale: number;
  /** Set by the first interaction: from then on the figures are always shown at full scale. */
  locked: boolean;
  visible: boolean;
  /** What was last written, so unchanged frames touch nothing. */
  written: string;
};

/**
 * Animates the shown estimate toward the computed one without re-rendering React.
 *
 * Two motions overlay each other. Every change of answer eases the money and weeks and springs the
 * tape's ticks to their new places. And until the visitor first touches the sheet, every figure
 * is multiplied by a factor that counts up from 0 to 1 as the section scrolls in (--sp 0.2 to 0.5),
 * so the numbers run up from $0 on the way in.
 *
 * React renders the target values (server HTML and reduced motion show those); this hook rewrites
 * the four nodes after every render and on each frame while anything is still moving.
 */
export function useEstimateMotion(sectionRef: RefObject<HTMLElement | null>, result: Estimate, enabled: boolean) {
  const tapeRef = useRef<HTMLDivElement>(null);
  const lowRef = useRef<HTMLSpanElement>(null);
  const highRef = useRef<HTMLSpanElement>(null);
  const weeksRef = useRef<HTMLSpanElement>(null);
  const target = toValues(result);
  const state = useRef<MotionState>({
    current: [...target],
    velocity: [0, 0, 0, 0, 0],
    target,
    scale: 1,
    locked: false,
    visible: true,
    written: '',
  });

  const write = useCallback(() => {
    const motion = state.current;
    const tape = tapeRef.current;
    if (!tape) return;
    const { scale, current } = motion;
    const tapeLow = (current[0] * scale).toFixed(4);
    const tapeHigh = (current[1] * scale).toFixed(4);
    const low = formatMoney(current[2] * scale);
    const high = formatMoney(current[3] * scale);
    // Weeks never read 0 once the count-up has finished.
    const weeks = Number.isFinite(current[4]) ? String(Math.max(scale < 1 ? 0 : 1, Math.round(current[4]! * scale))) : '…';
    const key = `${tapeLow}|${tapeHigh}|${low}|${high}|${weeks}`;
    if (key === motion.written) return;
    motion.written = key;
    tape.style.setProperty('--lo', tapeLow);
    tape.style.setProperty('--hi', tapeHigh);
    if (lowRef.current) lowRef.current.textContent = low;
    if (highRef.current) highRef.current.textContent = high;
    if (weeksRef.current) weeksRef.current.textContent = weeks;
  }, []);

  // After every render React has put the target values back in the DOM; put the animated ones back.
  useLayoutEffect(() => {
    state.current.target = target;
    if (!enabled) return;
    state.current.written = '';
    write();
  });

  useEffect(() => {
    const section = sectionRef.current;
    if (!enabled || !section) return;
    const motion = state.current;
    const observer = new IntersectionObserver(
      ([entry]) => {
        motion.visible = entry?.isIntersecting ?? false;
      },
      { rootMargin: '120px' },
    );
    observer.observe(section);

    const stop = onFrame({
      write: () => {
        if (!motion.visible) return;
        for (let index = 0; index < 5; index++) {
          const goal = motion.target[index]!;
          // A figure that was not known yet (NaN) jumps straight to its first value.
          if (!Number.isFinite(motion.current[index]) || !Number.isFinite(goal)) {
            motion.current[index] = goal;
            motion.velocity[index] = 0;
            continue;
          }
          const gap = goal - motion.current[index]!;
          // Settled: within 0.2% of the target and moving slower than 0.04% of it per frame.
          if (Math.abs(gap) < Math.abs(goal) * 0.002 + 1e-6 && Math.abs(motion.velocity[index]!) < Math.abs(goal) * 4e-4 + 1e-6) {
            motion.current[index] = goal;
            motion.velocity[index] = 0;
            continue;
          }
          if (index < 2) {
            motion.velocity[index] = (motion.velocity[index]! + gap * SPRING_PULL) * SPRING_KEEP;
            motion.current[index]! += motion.velocity[index]!;
          } else {
            motion.current[index]! += gap * EASE;
          }
        }
        write();
      },
    });
    return () => {
      stop();
      observer.disconnect();
    };
  }, [enabled, sectionRef, write]);

  /** Scroll-progress listener: drives the count-up until the first interaction. */
  const onProgress = useCallback((pass: number) => {
    const motion = state.current;
    motion.scale = motion.locked ? 1 : clamp01((pass - COUNT_FROM) / COUNT_OVER);
  }, []);

  /** Call on any interaction with the sheet: the figures stop counting and show at full scale. */
  const lock = useCallback(() => {
    state.current.locked = true;
    state.current.scale = 1;
  }, []);

  return { tapeRef, lowRef, highRef, weeksRef, onProgress, lock };
}
