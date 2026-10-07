'use client';

import { useLayoutEffect, useRef, useState, type MouseEvent } from 'react';
import { HOLD } from '@/marketing/lib/hold';
import { getSmoothScroller } from '@/marketing/lib/smoothScroll';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { cx } from '@/marketing/lib/cx';
import { TYPE } from '@/marketing/lib/typography';
import type { StyleWithVars } from '@/marketing/lib/css';
import { LOADER_ON, LOADER_OPEN, LOADER_PACE, SEEN_KEY } from './prePaint';
import { useRootClass } from './useRootClass';
import './loader.css';

/** 0 hook on (beam above the screen), 1 lifting (beam drops in), 2 set down, 3 lift-off. */
type Stage = 0 | 1 | 2 | 3;

type Props = {
  wordmark: string;
  place: string;
  tag: string;
  statuses: string[];
  counterLabel: string;
  skipLabel: string;
  topLevel: number;
  /** Seconds; clamped to 1.8–4. */
  duration: number;
  once: boolean;
};

/** The intro's CSS timings (and the stage cues below) were authored for a 2.4s run. */
const AUTHORED_RUN_MS = 2400;
/** A run never gets shorter than this, however late the app started. */
const MIN_RUN_MS = 1100;
/** The run may end up to this long after the target, measured from navigation start. */
const LATE_ALLOWANCE_MS = 300;
const STAGE_CUES_MS: Array<[Stage, number]> = [
  [1, 120],
  [2, 1250],
];
/** The lift-off length (`--lift`); the stage unmounts a little after it ends. */
const LIFT_MS = 950;
const GONE_AFTER_MS = 1030;
/** The counter's ease-out exponent. */
const COUNTER_EASE = 1.7;

const level = (value: number) => `L${String(value).padStart(2, '0')}`;
const isModifierKey = (event: KeyboardEvent) =>
  event.metaKey || event.ctrlKey || event.altKey || /^(Shift|Control|Alt|Meta|CapsLock)$/.test(event.key);

/**
 * The loader itself. The pre-paint script has already decided whether it shows (class
 * `loader-go` on <html>); this runs the intro, the counter and the lift-off, and releases the
 * section reveals (`gd-hold-ld`) the moment the lift-off starts.
 */
export function LoaderStage({ wordmark, place, tag, statuses, counterLabel, skipLabel, topLevel, duration, once }: Props) {
  // The pre-paint script decides whether the loader shows; the class on <html> is the truth.
  const covering = useRootClass(LOADER_ON, true);
  const [opened, setOpened] = useState(false);
  const [stage, setStage] = useState<Stage>(0);
  const counterRef = useRef<HTMLElement>(null);
  const barRef = useRef<HTMLElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<() => void>(() => {});
  const top = Math.max(1, Math.min(99, Math.round(topLevel) || 22));

  // Layout effect: the first frame after hydration must already show the run state.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (!root.classList.contains(LOADER_ON)) {
      root.classList.remove(HOLD.loader);
      return;
    }
    try {
      if (once) sessionStorage.setItem(SEEN_KEY, '1');
    } catch {}

    // The run ends `duration` after navigation start (plus a little grace), so a slow start
    // does not stack the whole intro on top of the wait. Every intro timing scales with it.
    const target = Math.max(1.8, Math.min(4, duration)) * 1000;
    const startedAt = performance.now();
    const runMs = Math.max(MIN_RUN_MS, Math.min(target, target + LATE_ALLOWANCE_MS - startedAt));
    const pace = runMs / AUTHORED_RUN_MS;
    // Also tells the pre-paint script's fallback that the loader has started.
    root.style.setProperty(LOADER_PACE, pace.toFixed(3));

    const timers: number[] = [];
    let running = true;

    const showProgress = (eased: number) => {
      if (counterRef.current) counterRef.current.textContent = level(Math.round(eased * top));
      if (barRef.current) barRef.current.style.transform = `scaleX(${eased.toFixed(4)})`;
    };

    const stopCounter = onFrame({
      write: () => {
        // Smooth scrolling may register after this effect; keep it parked while the page is covered.
        const scroller = getSmoothScroller();
        if (scroller && !scroller.isStopped) scroller.stop();
        const progress = clamp01((performance.now() - startedAt) / runMs);
        showProgress(1 - (1 - progress) ** COUNTER_EASE);
        if (progress >= 1) stopCounter();
      },
    });

    const finish = () => {
      root.classList.remove(LOADER_ON, LOADER_OPEN, HOLD.loader);
      root.style.removeProperty(LOADER_PACE);
    };

    const open = () => {
      if (!running) return;
      running = false;
      timers.forEach((timer) => window.clearTimeout(timer));
      stopCounter();
      root.classList.remove(HOLD.loader);
      root.classList.add(LOADER_OPEN);
      getSmoothScroller()?.start();
      showProgress(1);
      setStage(3);
      setOpened(true);
      timers.push(window.setTimeout(finish, GONE_AFTER_MS));
    };
    openRef.current = open;

    const onKeyDown = (event: KeyboardEvent) => {
      if (!running) return;
      // Focus stays on the Skip control while the page underneath is covered.
      if (event.key === 'Tab') {
        event.preventDefault();
        skipRef.current?.focus({ preventScroll: true });
        return;
      }
      if (!isModifierKey(event)) open();
    };
    window.addEventListener('keydown', onKeyDown, true);

    for (const [cue, at] of STAGE_CUES_MS) timers.push(window.setTimeout(() => setStage(cue), at * pace));
    timers.push(window.setTimeout(open, runMs));

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
      stopCounter();
      window.removeEventListener('keydown', onKeyDown, true);
      root.style.removeProperty(LOADER_PACE);
    };
  }, [once, duration, top]);

  if (!covering) return null;

  const lastStatus = Math.max(0, statuses.length - 1);
  const status = statuses[stage === 0 ? 0 : stage === 1 ? Math.min(1, lastStatus) : lastStatus] ?? '';
  // The beam is sized from the wordmark's length so short and long names both fill it.
  const letters = Math.max(4, wordmark.length) * 0.52;
  const style: StyleWithVars = {
    ...TYPE.body,
    '--lift': `${LIFT_MS}ms`,
    '--fs': `clamp(46px, ${(72 / letters).toFixed(1)}vw, 190px)`,
    '--bw': `min(88vw, calc(var(--fs) * ${(letters + 0.5).toFixed(2)}))`,
  };
  const skip = (event: MouseEvent) => {
    event.stopPropagation();
    openRef.current();
  };

  return (
    // Any click or key skips the intro, as Skip does; the button is the keyboard route.
    <div
      className={cx('loader', `st-${stage}`, opened && 'is-open')}
      role="status"
      aria-live="polite"
      aria-label={`${wordmark} · ${counterLabel}`}
      onClick={() => openRef.current()}
      style={style}
    >
      <div className="loader-wall" aria-hidden="true">
        <i className="loader-grid" />
        <i className="loader-edge" />
      </div>
      <div className="loader-jib" aria-hidden="true">
        <i className="loader-trolley" />
      </div>
      <div className="loader-top">
        <span className="loader-tag" style={TYPE.mono}>
          <i aria-hidden="true" />
          {tag}
          {place && <em> · {place}</em>}
        </span>
        <button ref={skipRef} type="button" className="loader-skip" style={TYPE.mono} onClick={skip}>
          {skipLabel}
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
        </button>
      </div>
      <div className="loader-lift" aria-hidden="true">
        <i className="loader-cable" />
        <i className="loader-hook" />
        <svg className="loader-slings" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d="M50 0L2 100M50 0L98 100" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="loader-beam">
          <span className="loader-wm" style={TYPE.display}>
            {wordmark}
          </span>
        </div>
      </div>
      <div className="loader-foot" aria-hidden="true">
        <span className="loader-st" style={TYPE.mono}>
          <i />
          {status}
        </span>
        <span className="loader-cn" style={TYPE.mono}>
          <small>{counterLabel}</small>
          <b ref={counterRef}>{level(0)}</b>
        </span>
      </div>
      <div className="loader-line" aria-hidden="true">
        <i ref={barRef} />
      </div>
    </div>
  );
}
