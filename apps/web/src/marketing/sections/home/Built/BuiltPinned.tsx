'use client';

import { useEffect, useRef, type RefObject } from 'react';
import type { BuiltContent } from '@/marketing/content/sections/built';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { resolveHref } from '@/marketing/lib/routes';
import { pad2 } from '@/marketing/lib/text';
import { clamp01, onFrame } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';
import { BuiltSpecs } from './BuiltSpecs';
import { formatCount, parseCount } from './countUp';
import type { BuiltProject } from './model';
import { framerPhoto } from '@/marketing/lib/images';

const PHOTO_SIZES = '(max-width: 1099px) 90vw, 55vw';
/** The spec figures count up from zero over 1s, starting 120ms after the project changes. */
const COUNT_DELAY = 120;
const COUNT_DURATION = 1000;

type BuiltPinnedProps = {
  content: BuiltContent;
  projects: BuiltProject[];
  heading: string;
  projectsHref: string;
  /** Index of the project on show. */
  active: number;
  /** Whether the section is pinned and scroll-driven (the spec count-up only runs then). */
  pinned: boolean;
  onStep: (index: number) => void;
  /** Scrolls past the pinned section to whatever follows it. */
  onSkip: () => void;
};

/**
 * Desktop and tablet layout: the stage sticks to the viewport while the section scrolls past,
 * with a level rail on the left, the photo stack in the middle and the project's copy on the
 * right. The per-frame variables (--c, --cw, --car) are written by the section; this renders
 * the active stage.
 */
export function BuiltPinned({ content, projects, heading, projectsHref, active, pinned, onStep, onSkip }: BuiltPinnedProps) {
  const infoRef = useRef<HTMLDivElement>(null);
  const count = projects.length;
  const project = projects[active];
  const level = content.levelLetter.trim() || 'L';

  useCountUp(infoRef, active, pinned);

  return (
    <div className="built-pin">
      <div className="built-grid" aria-hidden="true" />
      <div className="gd-wrap built-stage">
        <div className="built-rail" style={TYPE.mono} aria-hidden="true">
          <div className="built-track">
            <i className="built-done" />
            {projects.map((item, index) => (
              <span
                key={item.slug}
                className={cx('built-lv', index === active && 'is-on')}
                style={{ top: `${(1 - index / Math.max(1, count - 1)) * 100}%` }}
              >
                {level}
                {pad2(index + 1)}
              </span>
            ))}
            <div className="built-lift">
              <span className="built-car">
                {level}
                {pad2(active + 1)}
              </span>
            </div>
          </div>
        </div>

        <div className="built-view">
          <div className="built-dim" style={TYPE.mono} aria-hidden="true">
            <i />
            <span key={active}>{project?.size ?? ''}</span>
          </div>
          <a
            className="built-frame"
            href={resolveHref(project?.cta?.href ?? projectsHref)}
            tabIndex={-1}
            aria-hidden="true"
          >
            <div className="built-zoom">
              {projects.map((item, index) => {
                const photo = framerPhoto(item.photo, PHOTO_SIZES);
                // The first photo is always uncovered; each later one wipes up over the stack as
                // its --c goes 0 -> 1.
                const style: StyleWithVars = { zIndex: index, '--c': index === 0 ? 1 : 0 };
                return (
                  <div key={item.slug} className="built-ph" style={style}>
                    <img
                      src={photo.src}
                      srcSet={photo.srcSet}
                      sizes={photo.sizes}
                      alt={item.name}
                      loading="lazy"
                      decoding="async"
                      draggable={false}
                    />
                  </div>
                );
              })}
            </div>
            <i className="built-slab" />
            {project?.status && (
              <span key={active} className="built-tag built-sw" style={TYPE.mono}>
                {project.status}
              </span>
            )}
          </a>
        </div>

        <div ref={infoRef} className="built-info">
          <div className="built-info-top">
            <Eyebrow text={content.eyebrow} />
            <p className="built-count gd-rv" style={{ ...TYPE.mono, ...revealDelay(120) }} aria-live="polite">
              <b style={TYPE.display}>{pad2(active + 1)}</b>
              {' / '}
              {pad2(count)}
            </p>
          </div>
          <h2 className="gd-sr">{heading}</h2>
          {project && (
            <div className="built-body gd-rv" style={revealDelay(160)}>
              <h3 className="built-name" style={TYPE.display}>
                <span key={active} className="built-sw">
                  {project.name}
                </span>
              </h3>
              <p className="built-meta" style={TYPE.mono}>
                <span key={active} className="built-sw" style={{ animationDelay: '60ms' }}>
                  {project.meta}
                </span>
              </p>
              {project.summary && (
                <p className="built-sum">
                  <span key={active} className="built-sw" style={{ animationDelay: '100ms' }}>
                    {project.summary}
                  </span>
                </p>
              )}
              <BuiltSpecs project={project} swapKey={String(active)} />
              {project.cta && (
                <div className="built-btns">
                  <Button
                    href={project.cta.href}
                    label={project.cta.label}
                    kind="ghost"
                    ariaLabel={`${project.cta.label}: ${project.name}`}
                  />
                </div>
              )}
            </div>
          )}
          {count > 1 && (
            <div className="built-nav gd-rv" style={revealDelay(260)}>
              <button
                type="button"
                className="built-nb"
                aria-label="Previous stage"
                aria-disabled={active <= 0}
                onClick={() => onStep(active - 1)}
              >
                <ArrowIcon up={false} />
              </button>
              <button
                type="button"
                className="built-nb"
                aria-label="Next stage"
                aria-disabled={active >= count - 1}
                onClick={() => onStep(active + 1)}
              >
                <ArrowIcon up />
              </button>
              <div className="built-pips" aria-hidden="true">
                {projects.map((item, index) => (
                  <i key={item.slug} className={index <= active ? 'is-on' : undefined} />
                ))}
              </div>
              <button type="button" className="gd-skip" style={{ ...TYPE.mono, fontWeight: 600 }} onClick={onSkip}>
                Skip
                <ArrowIcon up={false} size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ArrowIcon({ up, size = 20 }: { up: boolean; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="square"
      aria-hidden="true"
      style={{ transform: up ? 'none' : 'rotate(180deg)' }}
    >
      <path d="M12 19V6M6 11.5l6-6 6 6" />
    </svg>
  );
}

/**
 * Each time the project changes, its spec figures count up from zero (ease-out cubic), written
 * straight into the freshly mounted value spans so React never re-renders per frame.
 */
function useCountUp(ref: RefObject<HTMLElement | null>, active: number, enabled: boolean) {
  useEffect(() => {
    const root = ref.current;
    if (!enabled || !root) return;
    const figures = Array.from(root.querySelectorAll<HTMLElement>('[data-ct]')).flatMap((el) => {
      const target = parseCount(el.dataset.ct ?? '');
      return target ? [{ el, target }] : [];
    });
    if (!figures.length) return;
    const start = performance.now();
    const stop = onFrame({
      write: (time) => {
        const eased = 1 - (1 - clamp01((time - start - COUNT_DELAY) / COUNT_DURATION)) ** 3;
        for (const { el, target } of figures) el.textContent = formatCount(target, target.value * eased);
        if (eased >= 1) stop();
      },
    });
    return stop;
  }, [ref, active, enabled]);
}
