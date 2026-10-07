'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { ScheduleContent, SchedulePhase } from '@/marketing/content/sections/schedule';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { pad2, plainHeadline } from '@/marketing/lib/text';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';
import './schedule.css';

/** Where "today" stands before scrolling takes over (server render, first frame). */
const RESTING_PROGRESS = 0.55;
/**
 * The schedule runs from week 0 to the end while the section's pass progress goes from 0.15
 * to 0.6, i.e. roughly while the chart crosses the middle of the viewport.
 */
const SCROLL_START = 0.15;
const SCROLL_SPAN = 0.45;
/** Fraction of the remaining distance the TODAY line covers each frame. */
const LINE_EASE = 0.14;

/** Chart length: the last end week rounded up to a multiple of 4 (at least 4). */
const chartWeeks = (phases: SchedulePhase[]) =>
  Math.max(4, Math.ceil(Math.max(0, ...phases.map((phase) => phase.end)) / 4) * 4);

/** Axis tick spacing: every 2 weeks up to 24, every 4 up to 48, then every 8. */
const tickStep = (weeks: number) => (weeks <= 24 ? 2 : weeks <= 48 ? 4 : 8);

/** The last phase that has started by `week`. */
function phaseAt(phases: SchedulePhase[], week: number): number {
  let index = 0;
  phases.forEach((phase, i) => {
    if (phase.start <= week + 0.001) index = i;
  });
  return index;
}

/** Week numbers with at most one decimal: 7.25 -> "7.3". */
const formatWeek = (week: number) => String(Math.round(week * 10) / 10);

type Motion = {
  /** Scroll-driven schedule progress, 0..1. */
  progress: number;
  /** Eased TODAY position, 0..1. */
  line: number;
  writtenProgress: number;
  writtenLine: number;
  writtenWeek: number;
  active: number;
  hovered: number;
};

export function Schedule({ content }: { content: ScheduleContent }) {
  const { eyebrow, heading, subCopy, phases: allPhases, weekLabel, todayLabel, weeksWord, phaseWord, stageWord, note } =
    content;
  const phases = useMemo(() => allPhases.filter((phase) => phase.name && phase.end > phase.start).slice(0, 8), [allPhases]);
  const count = phases.length;
  // Stage numbers run on across phases: the first stage of each phase.
  const firstStage = phases.map((_, i) => phases.slice(0, i).reduce((sum, item) => sum + item.stages.length, 1));
  const stageRange = (i: number) => {
    const from = firstStage[i] ?? 1;
    const to = from + (phases[i]?.stages.length ?? 1) - 1;
    return from === to ? `${stageWord} ${pad2(from)}` : `${stageWord}s ${pad2(from)}–${pad2(to)}`;
  };
  const weeks = chartWeeks(phases);
  const step = tickStep(weeks);
  const ticks = Array.from({ length: Math.floor(weeks / step) + 1 }, (_, i) => i * step);

  const sectionRef = useRef<HTMLElement>(null);
  const weekRef = useRef<HTMLElement>(null);
  const revealed = useReveal(sectionRef);
  const reduced = usePrefersReducedMotion();
  const resting = reduced ? 1 : RESTING_PROGRESS;

  const [scrollActive, setScrollActive] = useState(-1);
  const [hovered, setHovered] = useState(-1);
  const motion = useRef<Motion>({
    progress: RESTING_PROGRESS,
    line: RESTING_PROGRESS,
    writtenProgress: -1,
    writtenLine: -1,
    writtenWeek: -1,
    active: -1,
    hovered: -1,
  });

  useEffect(() => {
    motion.current.hovered = hovered;
  }, [hovered]);

  const onProgress = useCallback((pass: number) => {
    motion.current.progress = clamp01((pass - SCROLL_START) / SCROLL_SPAN);
  }, []);
  useScrollProgress(sectionRef, { onProgress });

  // Per frame: publish --t, ease the TODAY line toward the progress (or the hovered bar's
  // midpoint), print its week, and switch the active phase when the progress crosses a start.
  useEffect(() => {
    const section = sectionRef.current;
    if (reduced || !section) return;
    return onFrame({
      write: () => {
        const state = motion.current;
        const hoveredPhase = phases[state.hovered];
        const target = hoveredPhase ? (hoveredPhase.start + hoveredPhase.end) / 2 / weeks : state.progress;
        state.line += (target - state.line) * LINE_EASE;
        if (Math.abs(target - state.line) < 5e-4) state.line = target;
        if (state.progress !== state.writtenProgress) {
          state.writtenProgress = state.progress;
          section.style.setProperty('--t', state.progress.toFixed(4));
        }
        if (state.line !== state.writtenLine) {
          state.writtenLine = state.line;
          section.style.setProperty('--tl', state.line.toFixed(4));
        }
        const week = Math.round(state.line * weeks);
        if (week !== state.writtenWeek && weekRef.current) {
          state.writtenWeek = week;
          weekRef.current.textContent = String(week);
        }
        const active = phaseAt(phases, state.progress * weeks);
        if (active !== state.active) {
          state.active = active;
          setScrollActive(active);
        }
      },
    });
  }, [reduced, phases, weeks]);

  const current = count
    ? Math.min(count - 1, hovered >= 0 ? hovered : scrollActive >= 0 ? scrollActive : phaseAt(phases, resting * weeks))
    : -1;
  // Without the frame loop (reduced motion) the line jumps straight to the hovered bar.
  const restingLine = reduced && phases[hovered] ? (phases[hovered].start + phases[hovered].end) / 2 / weeks : resting;
  const phase = phases[current];
  const sectionStyle: StyleWithVars = {
    ...TYPE.body,
    background: 'var(--gd-brass)',
    color: 'var(--gd-ink)',
    '--t': resting,
    '--tl': restingLine,
  };
  const percent = (week: number) => `${(week / weeks) * 100}%`;
  const barRate = (item: SchedulePhase): StyleWithVars => ({
    '--s': (item.start / weeks).toFixed(4),
    '--k': (weeks / (item.end - item.start)).toFixed(4),
  });

  return (
    <section
      ref={sectionRef}
      className={cx('gd gd-sec schedule', revealed && 'is-in')}
      style={sectionStyle}
    >
      <span className="schedule-haz" aria-hidden="true" />
      <span className="schedule-haz is-b" aria-hidden="true" />
      <div className="gd-wrap schedule-wrap">
        <header className="schedule-top">
          <div className="schedule-ttl">
            <Eyebrow text={eyebrow} />
            <Heading text={heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
          </div>
          {subCopy.trim() && (
            <p className="schedule-sub gd-rv" style={revealDelay(320)}>
              {subCopy}
            </p>
          )}
        </header>
        {count > 0 && (
          <>
            <div className="schedule-main gd-rv" style={revealDelay(380)}>
              <div className="schedule-chart">
                <div className="schedule-plot">
                  <div className="schedule-axis" style={TYPE.mono} aria-hidden="true">
                    {ticks.map((week, i) => {
                      const edge = i === 0 ? 'is-a' : i === ticks.length - 1 ? 'is-z' : undefined;
                      return (
                        <span key={week} className={edge} style={{ left: percent(week) }}>
                          {edge ? `${weekLabel} ${week}` : week}
                        </span>
                      );
                    })}
                  </div>
                  <div className="schedule-rows" role="group" aria-label={plainHeadline(heading)}>
                    <div className="schedule-grid" aria-hidden="true">
                      {ticks.map((week) => (
                        <i key={week} style={{ left: percent(week) }} />
                      ))}
                    </div>
                    {phases.map((item, i) => (
                      <div key={item.name} className={cx('schedule-row', i === current && 'is-act')}>
                        <span className="schedule-ix" style={TYPE.mono} aria-hidden="true">
                          {pad2(i + 1)}
                        </span>
                        <button
                          type="button"
                          className="schedule-bar"
                          aria-pressed={i === current}
                          aria-label={`${item.name}, ${weeksWord.toLowerCase()} ${formatWeek(item.start)} to ${formatWeek(item.end)}. ${stageRange(i)}: ${item.stages.map((stage) => stage.name).join(', ')}.`}
                          style={{ left: percent(item.start), width: percent(item.end - item.start), ...barRate(item) }}
                          onMouseEnter={() => setHovered(i)}
                          onMouseLeave={() => setHovered((last) => (last === i ? -1 : last))}
                          onFocus={() => setHovered(i)}
                          onBlur={() => setHovered((last) => (last === i ? -1 : last))}
                        >
                          <span className="schedule-ghost" style={TYPE.mono} aria-hidden="true">
                            <span>{item.name}</span>
                            <StageCuts count={item.stages.length} />
                          </span>
                          <span className="schedule-fill" style={TYPE.mono} aria-hidden="true">
                            <span>{item.name}</span>
                            <StageCuts count={item.stages.length} />
                          </span>
                          <i className="schedule-ms" aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="schedule-now" aria-hidden="true">
                    <span className="schedule-flag" style={TYPE.mono}>
                      <i />
                      {todayLabel} · {weekLabel} <b ref={weekRef}>{Math.round(restingLine * weeks)}</b>
                    </span>
                  </div>
                </div>
                <p className="schedule-dim" style={TYPE.mono}>
                  <span>
                    {weeks} {weeksWord.toLowerCase()}
                    {note.trim() ? ` · ${note}` : ''}
                  </span>
                </p>
              </div>
              {phase && (
                <aside className="schedule-panel gd-dark" aria-live="off">
                  {/* Every phase is laid out in the same cell so the panel keeps the height of
                      the longest one; only the current phase shows, re-mounted to slide in. */}
                  <div className="schedule-panel-stack">
                    {phases.map((item, i) => (
                      <div
                        key={i === current ? `on-${i}` : i}
                        className={cx('schedule-panel-in', i === current && 'is-on')}
                        aria-hidden={i !== current}
                      >
                        <p className="schedule-pn" style={TYPE.mono}>
                          <span>
                            <i aria-hidden="true" />
                            {phaseWord} {pad2(i + 1)} · {stageRange(i)}
                          </span>
                          <span>
                            {pad2(i + 1)} / {pad2(count)}
                          </span>
                        </p>
                        <h3 className="schedule-ph" style={TYPE.display}>
                          {item.name}
                        </h3>
                        <StageList phase={item} first={firstStage[i] ?? 1} />
                        <p className="schedule-pw">
                          <b style={TYPE.display}>
                            {weeksWord} {formatWeek(item.start)}–{formatWeek(item.end)}
                          </b>
                          <span style={TYPE.mono}>
                            {formatWeek(item.end - item.start)} {weeksWord.toLowerCase()}
                          </span>
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="schedule-steps" aria-hidden="true">
                    {phases.map((item, i) => (
                      <i key={item.name} className={cx(i === current && 'is-on', i < current && 'is-done')} />
                    ))}
                  </div>
                </aside>
              )}
            </div>
            {/* Phone: the same phases as a list, each with a short bar that fills with --t. */}
            <ol className="schedule-list gd-rv" style={revealDelay(380)}>
              {phases.map((item, i) => (
                <li key={item.name} className="schedule-li" style={barRate(item)}>
                  <p className="schedule-li-top" style={TYPE.mono}>
                    <span>
                      {pad2(i + 1)} · {stageRange(i)}
                    </span>
                    <span>
                      {weeksWord} {formatWeek(item.start)}–{formatWeek(item.end)}
                    </span>
                  </p>
                  <h3 className="schedule-li-h" style={TYPE.display}>
                    {item.name}
                  </h3>
                  <div className="schedule-mini" aria-hidden="true">
                    <span className="schedule-mini-b" style={{ left: percent(item.start), width: percent(item.end - item.start) }}>
                      <i />
                    </span>
                  </div>
                  <StageList phase={item} first={firstStage[i] ?? 1} />
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </section>
  );
}

/** Notches on a phase bar where one stage hands over to the next (stages share the bar evenly). */
function StageCuts({ count }: { count: number }) {
  if (count < 2) return null;
  return Array.from({ length: count - 1 }, (_, i) => (
    <i key={i} className="schedule-cut" style={{ left: `${((i + 1) / count) * 100}%` }} />
  ));
}

/** The phase's stages, numbered on from `first`, each with its gate chip. */
function StageList({ phase, first }: { phase: SchedulePhase; first: number }) {
  return (
    <ol className="schedule-stages">
      {phase.stages.map((stage, i) => (
        <li key={stage.name}>
          <span className="schedule-sn" style={TYPE.mono}>
            {pad2(first + i)}
          </span>
          <span className="schedule-sname">{stage.name}</span>
          {stage.tag?.trim() && (
            <span className="schedule-stag" style={TYPE.mono}>
              {stage.tag}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
