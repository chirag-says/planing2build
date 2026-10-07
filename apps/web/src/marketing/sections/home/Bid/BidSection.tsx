'use client';

import Link from 'next/link';
import { useId, useRef, useState } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { resolveHref } from '@/marketing/lib/routes';
import { pad2, plainHeadline, splitList, telHref } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import type { BidContent } from '@/marketing/content/sections/bid';
import type { Photo, Service, SiteInfo } from '@/marketing/content/types';

export type BidService = Pick<Service, 'slug' | 'name'>;
export type BidSite = Pick<SiteInfo, 'bidHref' | 'licence' | 'phone' | 'proof'>;
import { bidRequestHref, headlineMeasure, headlineRuns } from './model';
import { useCardDrop } from './useCardDrop';
import '@/marketing/styles/card.css';
import './bid.css';
import { framerPhoto } from '@/marketing/lib/images';

const MAX_SERVICES = 6;
const MAX_START_OPTIONS = 5;

type BidProps = {
  content: BidContent;
  site: BidSite;
  services: BidService[];
  /** The background photo and its screen-reader description (the reference used its first project). */
  photo: Photo | null;
  photoLabel: string;
};

/**
 * "Request a bid": the closing section of the home page. A light bid card hangs on two slings
 * over the site photo; it drops into place as the section scrolls up and its answers are dealt
 * in after it. The two answers ride along on the bid link as query parameters.
 */
export function BidSection({ content, site, services, photo, photoLabel }: BidProps) {
  const ref = useRef<HTMLElement>(null);
  const bayRef = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const revealed = useReveal(ref, 0.12);
  useMagnetic(ref);
  useCardDrop(ref, bayRef, !reduced);

  const stepId = useId();
  const types = services.filter((service) => service.name).slice(0, MAX_SERVICES);
  const starts = splitList(content.startOptions).slice(0, MAX_START_OPTIONS);
  const [typeIndex, setTypeIndex] = useState(0);
  const [startIndex, setStartIndex] = useState(0);
  const type = types[Math.min(typeIndex, types.length - 1)];
  const start = starts[Math.min(startIndex, starts.length - 1)];
  const href = resolveHref(bidRequestHref(site.bidHref, type?.slug, start));

  const lines = headlineRuns(content.heading);
  const proof = content.proofLine.trim() || site.proof;
  const image = photo ? framerPhoto(photo.src) : null;
  // Chips, the drop zone and the button are dealt in one after another (see --i in bid.css).
  let dealOrder = 0;

  return (
    <section
      ref={ref}
      id="bid"
      className={cx('gd gd-sec gd-dark bid', revealed && 'is-in', reduced && 'is-fin')}
      style={{ ...TYPE.body, '--fe': headlineMeasure(lines) } as StyleWithVars}
    >
      {image && (
        <div className="bid-bg" aria-hidden="true">
          <img src={image.src} srcSet={image.srcSet} sizes="100vw" alt="" loading="lazy" decoding="async" draggable={false} />
        </div>
      )}
      <div className="bid-shade" aria-hidden="true" />
      <div className="bid-grid" aria-hidden="true" />
      {photoLabel && <span className="gd-sr">{photoLabel}</span>}

      <div className="gd-wrap bid-wrap">
        <div className="bid-main">
          <div className="bid-copy">
            {content.eyebrow && (
              <p className="bid-eb gd-rv" style={{ ...TYPE.mono, ...revealDelay(0, 12) }}>
                <i aria-hidden="true" />
                {content.eyebrow}
              </p>
            )}
            <div className="bid-say">
              <h2 className="bid-h" aria-label={plainHeadline(content.heading)} style={TYPE.display}>
                {lines.map((runs, lineIndex) => (
                  <span key={lineIndex} className="bid-ln" aria-hidden="true">
                    <span className="bid-lni" style={{ transitionDelay: `${120 + lineIndex * 120}ms` }}>
                      {runs.map((run, runIndex) =>
                        run.accent ? (
                          <span key={runIndex} className="bid-acc" style={{ '--sd': `${640 + lineIndex * 120}ms` } as StyleWithVars}>
                            <span className="bid-beam" aria-hidden="true" />
                            <span className="bid-acct">{run.text}</span>
                          </span>
                        ) : (
                          <span key={runIndex}>{run.text} </span>
                        ),
                      )}
                    </span>
                  </span>
                ))}
              </h2>
              {content.subCopy && (
                <p className="bid-sub gd-rv" style={revealDelay(420, 16)}>
                  {content.subCopy}
                </p>
              )}
            </div>
          </div>

          <div ref={bayRef} className="bid-bay">
            <div className="bid-rig">
              <span className="bid-sl is-l" aria-hidden="true" />
              <span className="bid-sl is-r" aria-hidden="true" />
              <div className="bid-card gd-lt">
                <span className="bid-haz" aria-hidden="true" />
                <p className="bid-top" style={TYPE.mono}>
                  <span>
                    <i aria-hidden="true" />
                    {content.cardLabel}
                  </span>
                  {content.cardNote && <span>{content.cardNote}</span>}
                </p>

                {types.length > 0 && (
                  <div className="bid-step" role="group" aria-labelledby={`${stepId}-1`}>
                    <StepTitle id={`${stepId}-1`} number={1} title={content.step1} />
                    <div className="bid-chips">
                      {types.map((service, index) => (
                        <Chip key={service.slug} label={service.name} selected={index === typeIndex} order={dealOrder++} onSelect={() => setTypeIndex(index)} />
                      ))}
                    </div>
                  </div>
                )}
                {starts.length > 0 && (
                  <div className="bid-step" role="group" aria-labelledby={`${stepId}-2`}>
                    <StepTitle id={`${stepId}-2`} number={types.length ? 2 : 1} title={content.step2} />
                    <div className="bid-chips">
                      {starts.map((option, index) => (
                        <Chip key={index} label={option} selected={index === startIndex} order={dealOrder++} onSelect={() => setStartIndex(index)} />
                      ))}
                    </div>
                  </div>
                )}
                <div className="bid-step">
                  <StepTitle number={1 + Number(types.length > 0) + Number(starts.length > 0)} title={content.step3} />
                  {/* A look only: there is no upload, it opens the bid page like the button. */}
                  <Link className="bid-drop" href={href} style={{ '--i': dealOrder++ } as StyleWithVars}>
                    <span className="bid-drop-ic" aria-hidden="true">
                      <DrawingIcon />
                    </span>
                    <span className="bid-drop-tx">
                      <span className="bid-drop-t">{content.dropText}</span>
                      {content.dropHint && <small style={TYPE.mono}>{content.dropHint}</small>}
                    </span>
                  </Link>
                </div>
                <div className="bid-go" style={{ '--i': dealOrder++ } as StyleWithVars}>
                  <Button href={href} label={content.button} kind="solid" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bid-foot gd-rv" style={revealDelay(560, 14)}>
          {proof && (
            <p className="bid-proof" style={TYPE.mono}>
              <i aria-hidden="true" />
              {proof}
            </p>
          )}
          {site.phone && (
            <p className="bid-call">
              {content.callLabel} <a href={telHref(site.phone)}>{site.phone}</a>
            </p>
          )}
          {site.licence && (
            <p className="bid-lic" style={TYPE.mono}>
              {site.licence}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function StepTitle({ id, number, title }: { id?: string; number: number; title: string }) {
  return (
    <p className="bid-st" id={id}>
      <b style={TYPE.mono}>{pad2(number)}</b>
      <span style={TYPE.display}>{title}</span>
    </p>
  );
}

type ChipProps = { label: string; selected: boolean; order: number; onSelect: () => void };

function Chip({ label, selected, order, onSelect }: ChipProps) {
  return (
    <button
      type="button"
      className={cx('bid-chip', selected && 'is-sel')}
      aria-pressed={selected}
      onClick={onSelect}
      style={{ '--i': order } as StyleWithVars}
    >
      <i aria-hidden="true" />
      {label}
    </button>
  );
}

/** A sheet of drawings with a folded corner. */
function DrawingIcon() {
  return (
    <svg viewBox="0 0 48 48" width="44" height="44" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square">
      <path d="M9 5h21l9 9v29H9z" />
      <path d="M30 5v9h9" />
      <path d="M15 36V24h8v12M23 30h10v6M15 36h18" />
      <path d="M15 18h9" />
    </svg>
  );
}
