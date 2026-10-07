'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode, type RefObject } from 'react';
import type { SafetyCheck } from '@/marketing/content/sections/safety';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { pad2 } from '@/marketing/lib/text';
import { clamp01 } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';
import { CALLOUTS, DRAWING_HEIGHT, DRAWING_WIDTH, drawDelay } from './drawing';

/**
 * The drawing starts building when its top is 80% of the way down the viewport and is finished
 * by the time all of it is on screen (with a 24px margin at the bottom), so every card is in
 * view when it lands. A drawing taller than the viewport finishes once it is centred.
 */
const DRAW_START = 0.8;
const DRAW_MARGIN = 24;
/** Markers pop in a little after the strokes at their height, cards a little after that. */
const MARKER_LAG = 0.06;
const CARD_LAG = 0.12;
const LEADER_LAG = 0.08;
/** Section widths where the layout changes (the reference's JS breakpoints). */
const PHONE_BELOW = 810;
const TABLET_BELOW = 1100;

/** Hatched highlights sit under the line work, solid ones over it. */
const HATCHED_ZONES = [0, 3, 4];
const SOLID_ZONES = [1, 2];

type Layout = 'desktop' | 'tablet' | 'phone';

const subscribeNothing = () => () => {};

/**
 * The section's own width class. Styling switches through container queries; this only decides
 * behaviour: phones get the finished drawing without scrubbing, and only desktop has room for
 * the leader lines. Starts as desktop, like the reference's server render.
 */
function useLayout(ref: RefObject<HTMLElement | null>): Layout {
  const [width, setWidth] = useState(1440);
  // Measured before paint, so a phone never starts scrubbing for a frame.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = (measured: number) => {
      if (measured > 0) setWidth(Math.round(measured));
    };
    update(el.offsetWidth);
    const observer = new ResizeObserver(([entry]) => update(entry?.borderBoxSize?.[0]?.inlineSize || el.offsetWidth));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width < PHONE_BELOW ? 'phone' : width < TABLET_BELOW ? 'tablet' : 'desktop';
}

type SafetyShellProps = {
  id: string;
  checks: SafetyCheck[];
  checkWord: string;
  header: ReactNode;
  /** Server-rendered line work and labels of the drawing. */
  strokes: ReactNode;
  labels: ReactNode;
  /** Highlight shape per check, in check order. */
  zones: ReactNode[];
  certs: ReactNode;
};

/**
 * Client root of the Safety section: scroll-scrubbed drawing (`--dr`) and the active check,
 * which a marker or card sets on hover or focus and which lights its zone, leader and card.
 */
export function SafetyShell({ id, checks, checkWord, header, strokes, labels, zones, certs }: SafetyShellProps) {
  const ref = useRef<HTMLElement>(null);
  const reduced = usePrefersReducedMotion();
  const hydrated = useSyncExternalStore(subscribeNothing, () => true, () => false);
  const layout = useLayout(ref);
  const revealed = useReveal(ref);
  const [active, setActive] = useState(-1);
  const scrub = hydrated && !reduced && layout !== 'phone';

  // The drawing's offset and height within the section, measured on resize so the scroll
  // handler never reads layout.
  const geometry = useRef({ height: 1, figTop: 0, figHeight: 1 });
  useLayoutEffect(() => {
    const section = ref.current;
    const fig = section?.querySelector<HTMLElement>('.safety-fig');
    if (!section || !fig) return;
    const measure = () => {
      const box = section.getBoundingClientRect();
      const figBox = fig.getBoundingClientRect();
      geometry.current = { height: box.height || 1, figTop: figBox.top - box.top, figHeight: figBox.height || 1 };
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(section);
    observer.observe(fig);
    return () => observer.disconnect();
  }, []);

  const onProgress = useCallback((pass: number) => {
    const viewport = window.innerHeight || 1;
    const { height, figTop, figHeight } = geometry.current;
    // Back from the eased pass (0 when the section's top meets the viewport's bottom, 1 when its
    // bottom leaves the top) to where the drawing's top sits in the viewport.
    const top = viewport - pass * (viewport + height) + figTop;
    const start = viewport * DRAW_START;
    const end = Math.max(viewport - figHeight - DRAW_MARGIN, (viewport - figHeight) / 2);
    ref.current?.style.setProperty('--dr', clamp01((start - top) / Math.max(1, start - end)).toFixed(4));
  }, []);
  useScrollProgress(ref, { enabled: scrub, onProgress });
  useEffect(() => {
    if (!scrub) ref.current?.style.setProperty('--dr', '1');
  }, [scrub]);

  const enter = (index: number) => () => setActive(index);
  const leave = (index: number) => () => setActive((current) => (current === index ? -1 : current));
  const lagged = (y: number, lag: number) => (parseFloat(drawDelay(y)) + lag).toFixed(3);
  const zone = (index: number, kind: 'hat' | 'sol') =>
    index < checks.length && (
      <g key={index} className={cx('safety-zone', `is-${kind}`, active === index && 'is-on')}>
        {zones[index]}
      </g>
    );

  const sectionStyle: StyleWithVars = { ...TYPE.body, background: 'var(--gd-bone)', color: 'var(--gd-ink)', '--dr': 1 };

  return (
    <section
      ref={ref}
      id={id}
      className={cx('gd gd-sec safety', revealed && 'is-in', active >= 0 && 'has-act', scrub && 'is-scrub')}
      style={sectionStyle}
    >
      <div className="gd-wrap safety-wrap">
        {header}
        <div className="safety-stage gd-rv" style={revealDelay(300, 0)}>
          <div className="safety-grid" aria-hidden="true" />
          <div className="safety-fig">
            <svg className="safety-dw" viewBox={`0 0 ${DRAWING_WIDTH} ${DRAWING_HEIGHT}`} aria-hidden="true" focusable="false" style={TYPE.mono}>
              <defs>
                <pattern id="safety-hy" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="9" height="9" fill="var(--gd-brass)" opacity=".34" />
                  <rect width="4" height="9" fill="var(--gd-brass)" />
                </pattern>
                <pattern id="safety-hc" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="1" height="5" fill="var(--gd-ink)" opacity=".55" />
                </pattern>
              </defs>
              {HATCHED_ZONES.map((index) => zone(index, 'hat'))}
              {strokes}
              {SOLID_ZONES.map((index) => zone(index, 'sol'))}
              {labels}
              {layout === 'desktop' && (
                <g className="safety-ld">
                  {checks.map((_, index) => {
                    const callout = CALLOUTS[index];
                    if (!callout) return null;
                    const style: StyleWithVars = { '--a': lagged(callout.y, LEADER_LAG) };
                    return <path key={index} d={callout.leader} pathLength={1} className={cx(active === index && 'is-on')} style={style} />;
                  })}
                </g>
              )}
            </svg>
            {checks.map((check, index) => {
              const callout = CALLOUTS[index];
              if (!callout) return null;
              const style: StyleWithVars = {
                left: `${(callout.x / DRAWING_WIDTH) * 100}%`,
                top: `${(callout.y / DRAWING_HEIGHT) * 100}%`,
                '--a': lagged(callout.y, MARKER_LAG),
                ...TYPE.display,
              };
              return (
                <button
                  key={index}
                  type="button"
                  className={cx('safety-mk', active === index && 'is-on')}
                  aria-label={`${index + 1}. ${check.title}`}
                  aria-describedby={`safety-c${index}`}
                  style={style}
                  onMouseEnter={enter(index)}
                  onMouseLeave={leave(index)}
                  onFocus={enter(index)}
                  onBlur={leave(index)}
                >
                  <span>{index + 1}</span>
                </button>
              );
            })}
          </div>
          {checks.map((check, index) => {
            const callout = CALLOUTS[index];
            if (!callout) return null;
            const style: StyleWithVars = {
              '--y': `${((callout.ly / DRAWING_HEIGHT) * 100).toFixed(2)}%`,
              '--a': lagged(callout.y, CARD_LAG),
            };
            return (
              <div key={index} className={`safety-slot is-${callout.side}`} style={style}>
                <article
                  id={`safety-c${index}`}
                  className={cx('safety-card gd-lt', active === index && 'is-on')}
                  onMouseEnter={enter(index)}
                  onMouseLeave={leave(index)}
                >
                  <p className="safety-cn" style={TYPE.mono}>
                    <b style={TYPE.display}>{index + 1}</b>
                    <span>
                      {checkWord} {pad2(index + 1)}
                    </span>
                  </p>
                  <h3 className="safety-ch" style={TYPE.display}>
                    {check.title}
                  </h3>
                  {check.text && <p className="safety-cp">{check.text}</p>}
                </article>
              </div>
            );
          })}
        </div>
        {certs}
      </div>
    </section>
  );
}
