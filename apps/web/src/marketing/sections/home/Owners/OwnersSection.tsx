'use client';

import './owners.css';
import { useCallback, useRef, useState, useSyncExternalStore } from 'react';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { OwnersContent } from '@/marketing/content/sections/owners';
import type { Review } from '@/marketing/content/types';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { scrollPageTo } from '@/marketing/lib/smoothScroll';
import { pad2, plainHeadline, splitList } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { useSectionWidth } from '@/marketing/hooks/useSectionWidth';
import { useViewportHeight } from '@/marketing/hooks/useViewportHeight';
import { PHONE_MAX, TABLET_MAX } from '@/marketing/lib/breakpoints';
import { framerPhoto } from '@/marketing/lib/images';

/** Shorter windows scroll the section normally: the pinned stage would not fit. */
const MIN_PIN_VIEWPORT = 660;
const MAX_REVIEWS = 8;
const MAX_CHECKS = 6;
/** Screens of scrolling each item gets while the stage is pinned (the section is one more). */
const SCREENS_PER_ITEM = 0.8;
/** Seconds the smooth scroller takes to bring a review into place when a button is pressed. */
const BUTTON_SCROLL_DURATION = 0.9;

type OwnersProps = { content: OwnersContent; reviews: Review[] };
type View = { current: number; previous: number };

const subscribeNothing = () => () => {};

/**
 * 07 · Owners' words. On tablet and desktop the section is two or more screens tall and its
 * stage pins; scrolling through it steps from one review to the next, and the buttons scroll to
 * the matching position. On phones the reviews sit in a sideways scroll-snap row.
 */
export function OwnersSection({ content, reviews }: OwnersProps) {
  const ref = useRef<HTMLElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const revealed = useReveal(ref, 0.12);
  const reduced = usePrefersReducedMotion();
  // False during server render and hydration, so the checklist starts ticked for no-JS visitors.
  const hydrated = useSyncExternalStore(subscribeNothing, () => true, () => false);
  const viewportHeight = useViewportHeight();
  const width = useSectionWidth(ref);
  const phone = width < PHONE_MAX;
  const tablet = !phone && width < TABLET_MAX;

  const items = reviews.filter((review) => review.quote || review.name).slice(0, MAX_REVIEWS);
  const count = items.length;
  const checks = splitList(content.checks).slice(0, MAX_CHECKS);
  const pinned = !phone && count > 1 && viewportHeight >= MIN_PIN_VIEWPORT && !reduced;

  // `previous` stays uncovered under the incoming photo while it wipes in.
  const [view, setView] = useState<View>({ current: 0, previous: -1 });
  const current = Math.min(view.current, Math.max(0, count - 1));
  const show = useCallback(
    (index: number) => setView((was) => (was.current === index ? was : { current: index, previous: was.current })),
    [],
  );

  // While pinned, the pin progress (0 → 1 across the section) splits evenly between the reviews.
  const scrolledIndex = useRef(0);
  const onProgress = useCallback(
    (_pass: number, pin: number) => {
      if (!pinned) return;
      const index = Math.min(count - 1, Math.floor(pin * count * 0.9999));
      if (index === scrolledIndex.current) return;
      scrolledIndex.current = index;
      show(index);
    },
    [pinned, count, show],
  );
  useScrollProgress(ref, { onProgress });

  const go = (target: number) => {
    const index = Math.min(count - 1, Math.max(0, target));
    if (index === current && !phone) return;
    if (phone) {
      const rail = railRef.current;
      const slide = rail?.children[index] as HTMLElement | undefined;
      const first = rail?.children[0] as HTMLElement | undefined;
      if (rail && slide && first) {
        rail.scrollTo({ left: slide.offsetLeft - first.offsetLeft, behavior: reduced ? 'auto' : 'smooth' });
      }
      return;
    }
    const section = ref.current;
    if (pinned && section) {
      // Scroll to the middle of that review's share of the pinned distance.
      const rect = section.getBoundingClientRect();
      const top = rect.top + window.scrollY + (rect.height - window.innerHeight) * ((index + 0.5) / count);
      scrollPageTo(top, { duration: BUTTON_SCROLL_DURATION });
      return;
    }
    scrolledIndex.current = index;
    show(index);
  };

  /** Scrolls to the end of the pinned section, so the next one starts at the top of the viewport. */
  const skip = () => {
    const section = ref.current;
    if (section) scrollPageTo(section.getBoundingClientRect().bottom + window.scrollY, { duration: BUTTON_SCROLL_DURATION });
  };

  // The phone row reports which slide is snapped in, so the counter and bar follow a swipe.
  const onRailScroll = () => {
    const rail = railRef.current;
    const first = rail?.children[0] as HTMLElement | undefined;
    if (!rail || !first) return;
    const second = rail.children[1] as HTMLElement | undefined;
    const stride = second ? second.offsetLeft - first.offsetLeft : first.offsetWidth;
    show(Math.min(count - 1, Math.max(0, Math.round(rail.scrollLeft / Math.max(1, stride)))));
  };

  const motion = hydrated && !reduced;
  const style: StyleWithVars = {
    ...TYPE.body,
    ...(pinned ? { height: `calc(100svh * ${(1 + count * SCREENS_PER_ITEM).toFixed(2)})` } : {}),
  };

  const heading = (
    <div className="owners-hd">
      <Eyebrow text={content.eyebrow} />
      <Heading text={content.heading} size="var(--owners-hd-size)" lineHeight={0.9} delay={80} className="owners-h" />
    </div>
  );

  const controls = count > 1 && (
    <div className="owners-ctl gd-rv" style={revealDelay(420)}>
      <div className="owners-btns">
        <button
          type="button"
          aria-label={content.prevLabel}
          aria-disabled={current === 0}
          className={current === 0 ? 'is-off' : undefined}
          onClick={() => go(current - 1)}
        >
          <Arrow back />
        </button>
        <button
          type="button"
          aria-label={content.nextLabel}
          aria-disabled={current === count - 1}
          className={current === count - 1 ? 'is-off' : undefined}
          onClick={() => go(current + 1)}
        >
          <Arrow />
        </button>
      </div>
      <p className="owners-idx" style={TYPE.mono} aria-live="polite">
        <b style={TYPE.display}>{pad2(current + 1)}</b> / {pad2(count)}
      </p>
      {/* Pinned, the bar fills with the section's own --pp; otherwise it steps with the index. */}
      <span
        className="owners-bar"
        aria-hidden="true"
        style={pinned ? undefined : ({ '--pp': (current / (count - 1)).toFixed(3) } as StyleWithVars)}
      >
        <i />
      </span>
      {pinned && content.skipLabel && (
        <button type="button" className="gd-skip" style={{ ...TYPE.mono, fontWeight: 600 }} onClick={skip}>
          {content.skipLabel}
          <Arrow down />
        </button>
      )}
    </div>
  );

  const active = items[current];

  return (
    <section
      ref={ref}
      className={cx(
        'gd gd-sec gd-dark owners',
        revealed && 'is-in',
        pinned && 'is-pin',
        motion && revealed && 'is-run',
        motion && !revealed && 'is-wait',
      )}
      style={style}
    >
      <div className="owners-stage">
        <div className="owners-grid" aria-hidden="true" />
        {phone ? (
          <div className="owners-flow">
            <div className="gd-wrap owners-phtop">
              {heading}
              {controls}
            </div>
            {count > 0 && (
              <div
                ref={railRef}
                className="owners-rail gd-rv"
                role="group"
                aria-label={plainHeadline(content.heading)}
                tabIndex={0}
                onScroll={onRailScroll}
                style={revealDelay(220, 30)}
              >
                {items.map((review, index) => (
                  <figure key={review.slug || index} className="owners-slide">
                    {content.showRating && <Stars rating={review.rating} />}
                    <blockquote className="owners-quote">
                      <p>{review.quote}</p>
                    </blockquote>
                    <Reviewer review={review} />
                    <HandoverSheet content={content} checks={checks} review={review} index={index} count={count} />
                  </figure>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="gd-wrap owners-cols">
            <div className="owners-left">
              {heading}
              {count > 0 && (
                <div className="owners-qs gd-rv" style={revealDelay(260)}>
                  {/* All reviews share one grid cell, so the stage keeps the tallest one's height. */}
                  {items.map((review, index) => (
                    <figure
                      key={review.slug || index}
                      className={cx('owners-q', index === current && 'is-on')}
                      aria-hidden={index !== current || undefined}
                    >
                      {content.showRating && <Stars rating={review.rating} />}
                      <blockquote className="owners-quote">
                        <p>{review.quote}</p>
                      </blockquote>
                      <Reviewer review={review} />
                    </figure>
                  ))}
                </div>
              )}
              {controls}
            </div>
            {active && (
              <div className="owners-right gd-rv" style={revealDelay(200, 40)}>
                <HandoverSheet
                  content={content}
                  checks={checks}
                  review={active}
                  index={current}
                  count={count}
                  photos={{ items, current, previous: view.previous, sizes: tablet ? '50vw' : '(max-width: 809px) 90vw, 40vw' }}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

/** Rating as five squares, filled up to the rating (missing or invalid ratings count as 5). */
function Stars({ rating }: { rating: number }) {
  const filled = Math.min(5, Math.max(0, Math.round(rating || 5)));
  return (
    <div className="owners-stars" role="img" aria-label={`${filled} out of 5`}>
      {[0, 1, 2, 3, 4].map((square) => (
        <i key={square} className={square < filled ? 'is-f' : undefined} />
      ))}
    </div>
  );
}

function Reviewer({ review }: { review: Review }) {
  return (
    <figcaption className="owners-who">
      {review.portrait && (
        <img {...framerPhoto(review.portrait, '56px')} alt={review.name} loading="lazy" decoding="async" draggable={false} />
      )}
      <span>
        <b>{review.name}</b>
        <small>{review.role}</small>
      </span>
    </figcaption>
  );
}

type SheetPhotos = { items: Review[]; current: number; previous: number; sizes: string };

type HandoverSheetProps = {
  content: OwnersContent;
  checks: string[];
  review: Review;
  index: number;
  count: number;
  /**
   * The desktop sheet stacks every project photo and wipes the current one in over the
   * previous one. Phone slides each show only their own.
   */
  photos?: SheetPhotos;
};

/**
 * The handover sheet: hazard edge, project photo, ticked checklist, result beam and stamp. With
 * no checklist, result or stamp it is the photo alone, which then takes the room they leave.
 */
function HandoverSheet({ content, checks, review, index, count, photos }: HandoverSheetProps) {
  const photoOnly = checks.length === 0 && !review.result && !content.stampText;
  return (
    <div className={cx('owners-card gd-lt', photoOnly && 'is-photo')}>
      <span className="owners-haz" aria-hidden="true" />
      <p className="owners-top" style={TYPE.mono}>
        <span>
          {content.cardLabel}
          {review.project && (
            <>
              {' · '}
              <b>{review.project}</b>
            </>
          )}
        </span>
        <span>
          {content.sheetLabel} {pad2(index + 1)} / {pad2(count)}
        </span>
      </p>
      <div className="owners-ph">
        {photos ? (
          photos.items.map((item, photoIndex) => {
            const on = photoIndex === photos.current;
            return (
              <img
                key={item.slug || photoIndex}
                className={on ? 'is-on' : photoIndex === photos.previous ? 'is-prv' : undefined}
                {...framerPhoto(item.projectPhoto, photos.sizes)}
                alt={on ? item.project || item.name : ''}
                aria-hidden={!on || undefined}
                loading="lazy"
                decoding="async"
                draggable={false}
              />
            );
          })
        ) : (
          <img
            className="is-on"
            {...framerPhoto(review.projectPhoto, '(max-width: 809px) 90vw, 40vw')}
            alt={review.project || review.name}
            loading="lazy"
            decoding="async"
            draggable={false}
          />
        )}
      </div>
      {/* Keyed by review on desktop so the boxes tick again for every review that arrives. */}
      {!photoOnly && (
        <div key={photos ? index : 'static'} className="owners-body">
          {checks.length > 0 && (
            <ul className="owners-checks">
              {checks.map((check, checkIndex) => (
                <li key={checkIndex} style={{ '--i': checkIndex } as StyleWithVars}>
                  <span className="owners-box" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="square">
                      <path d="M5 12.5l4.6 4.6L19 7.4" pathLength={1} />
                    </svg>
                  </span>
                  <span className="owners-ct">{check}</span>
                  <i aria-hidden="true" />
                </li>
              ))}
            </ul>
          )}
          {review.result && (
            <p className="owners-res" style={{ '--i': checks.length } as StyleWithVars}>
              <span style={TYPE.mono}>{content.resultLabel}</span>
              <b style={TYPE.display}>{review.result}</b>
            </p>
          )}
          {content.stampText && (
            <span className="owners-stamp" aria-hidden="true" style={TYPE.display}>
              {content.stampText}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function Arrow({ back = false, down = false }: { back?: boolean; down?: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="square"
      aria-hidden="true"
      style={back ? { transform: 'scaleX(-1)' } : down ? { transform: 'rotate(90deg)' } : undefined}
    >
      <path d="M4 12h15M13 5l7 7-7 7" />
    </svg>
  );
}
