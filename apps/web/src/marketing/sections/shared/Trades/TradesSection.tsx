'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { TradesContent } from '@/marketing/content/sections/trades';
import type { Service } from '@/marketing/content/types';

/** The service fields the rows and the hanging photo show. */
export type TradeService = Pick<Service, 'slug' | 'name' | 'line' | 'includes' | 'from' | 'timeline' | 'photo'>;
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { resolveHref } from '@/marketing/lib/routes';
import { pad2 } from '@/marketing/lib/text';
import { clamp01 } from '@/marketing/lib/ticker';
import { TYPE } from '@/marketing/lib/typography';
import { HangingPhoto } from './HangingPhoto';
import './trades.css';
import { framerPhoto } from '@/marketing/lib/images';

/**
 * Row entrance window, in viewport heights: a row starts wiping in when its top is 10% of the
 * viewport above the bottom edge and finishes 30% of the viewport later.
 */
const ROW_START = 0.1;
const ROW_SPAN = 0.3;
/** Re-measure after late layout shifts (fonts, images) the way the reference did. */
const REMEASURE_AFTER = [500, 1600];

const FINE_POINTER = '(hover:hover) and (pointer:fine)';

/** Chips rise one after another on hover, 50ms apart (`--k` is the chip's position). */
const chipDelay = (index: number): StyleWithVars => ({ '--k': index });

const easeOutCubic = (value: number) => 1 - (1 - clamp01(value)) ** 3;

function subscribeFinePointer(onChange: () => void) {
  const media = window.matchMedia(FINE_POINTER);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}

function useFinePointer(): boolean {
  return useSyncExternalStore(
    subscribeFinePointer,
    () => window.matchMedia(FINE_POINTER).matches,
    () => false,
  );
}

type Layout = { rows: HTMLElement[]; tops: number[]; height: number; viewport: number };

type TradesProps = { content: TradesContent; services: TradeService[] };

export function TradesSection({ content, services }: TradesProps) {
  const { eyebrow, heading, button, buttonLink, fromWord, rows, hoverPhoto } = content;
  const sectionRef = useRef<HTMLElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const layout = useRef<Layout>({ rows: [], tops: [], height: 1, viewport: 1 });
  const revealed = useReveal(sectionRef, 0.08);
  const reduced = usePrefersReducedMotion();
  const finePointer = useFinePointer();
  const [hovered, setHovered] = useState(-1);
  const clearHover = useCallback(() => setHovered(-1), []);
  useMagnetic(sectionRef);

  const shown = services.filter((service) => service.name).slice(0, Math.max(1, Math.round(rows) || 5));

  // Row offsets inside the section, re-read whenever the section resizes.
  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;
    const measure = () => {
      const top = section.getBoundingClientRect().top;
      const rowElements = Array.from(section.querySelectorAll<HTMLElement>('.trades-li'));
      layout.current = {
        rows: rowElements,
        tops: rowElements.map((row) => row.getBoundingClientRect().top - top),
        height: section.offsetHeight,
        viewport: window.innerHeight || 1,
      };
    };
    const observer = new ResizeObserver(measure);
    observer.observe(section);
    const timers = REMEASURE_AFTER.map((delay) => window.setTimeout(measure, delay));
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      timers.forEach((timer) => window.clearTimeout(timer));
      window.removeEventListener('resize', measure);
    };
  }, [shown.length]);

  // Each row wipes in on its own as it rises through the bottom of the viewport.
  const onProgress = useCallback((pass: number) => {
    const { rows: rowElements, tops, height, viewport } = layout.current;
    // How far the section's top has travelled up from the bottom of the viewport, in px.
    const travelled = pass * (viewport + height);
    rowElements.forEach((row, index) => {
      const local = clamp01((travelled - (tops[index] ?? 0) - viewport * ROW_START) / (viewport * ROW_SPAN));
      row.style.setProperty('--e', easeOutCubic(local * 1.4).toFixed(4));
      row.style.setProperty('--a', clamp01(local * 2).toFixed(4));
      row.style.setProperty('--b', clamp01(local * 2 - 1).toFixed(4));
    });
  }, []);
  useScrollProgress(sectionRef, { onProgress });

  const hanging = hoverPhoto && finePointer && !reduced;

  return (
    <section
      ref={sectionRef}
      className={cx('gd gd-sec trades', revealed && 'is-in')}
      style={{ ...TYPE.body, background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}
    >
      <div className="gd-wrap trades-wrap">
        <header className="trades-top">
          <div className="trades-top-l">
            <Eyebrow text={eyebrow} />
            <Heading text={heading} size="clamp(30px,min(4.4vw,5svh),64px)" lineHeight={0.9} delay={80} />
          </div>
          {button && (
            <div className="gd-rv" style={revealDelay(300)}>
              <Button href={buttonLink} label={button} kind="ghost" />
            </div>
          )}
        </header>
        <ul ref={listRef} className="trades-list">
          {shown.map((service, index) => (
            <TradeRow
              key={service.slug}
              service={service}
              index={index}
              fromWord={fromWord}
              onHover={() => setHovered(index)}
            />
          ))}
        </ul>
      </div>
      {hanging && revealed && (
        <HangingPhoto areaRef={listRef} services={shown} active={hovered} onLeave={clearHover} />
      )}
    </section>
  );
}

type TradeRowProps = { service: TradeService; index: number; fromWord: string; onHover: () => void };

function TradeRow({ service, index, fromWord, onHover }: TradeRowProps) {
  const includes = service.includes.slice(0, 5);
  const spec = [service.from ? `${fromWord} ${service.from}`.trim() : '', service.timeline].filter(Boolean).join(' · ');
  const thumb = framerPhoto(service.photo, '160px');
  return (
    <li id={service.slug} className="trades-li">
      <Link
        className="trades-row"
        href={resolveHref(`/services/${service.slug}`)}
        onPointerEnter={(event) => {
          if (event.pointerType === 'mouse') onHover();
        }}
      >
        <span className="trades-ix" style={TYPE.mono}>
          {pad2(index + 1)}
        </span>
        <h3 className="trades-nm" style={TYPE.display}>
          <span className="trades-nm-b" aria-hidden="true" />
          <span className="trades-nm-t">{service.name}</span>
        </h3>
        <div className="trades-meta">
          {service.line && <p className="trades-line">{service.line}</p>}
          {spec && (
            <p className="trades-spec" style={TYPE.mono}>
              {spec}
            </p>
          )}
        </div>
        {includes.length > 0 && (
          <ul className="trades-inc" style={TYPE.mono} aria-label="Includes">
            {includes.map((item, itemIndex) => (
              <li key={item} style={chipDelay(itemIndex)}>
                {item}
              </li>
            ))}
          </ul>
        )}
        <img
          className="trades-th"
          src={thumb.src}
          srcSet={thumb.srcSet}
          sizes={thumb.sizes}
          alt={service.name}
          loading="lazy"
          decoding="async"
          draggable={false}
        />
        <span className="trades-go" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" aria-hidden="true">
            <path d="M5 12h13M12.5 6l6 6-6 6" />
          </svg>
        </span>
      </Link>
    </li>
  );
}
