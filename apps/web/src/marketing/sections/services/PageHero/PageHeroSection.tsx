'use client';

import { useEffect, useRef, useState } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay } from '@/marketing/lib/css';
import { whenReleased } from '@/marketing/lib/hold';
import { TYPE } from '@/marketing/lib/typography';
import type { PageHeroContent } from '@/marketing/content/sections/pageHero';
import type { SiteInfo } from '@/marketing/content/types';

export type PageHeroSite = Pick<SiteInfo, 'bidHref' | 'licence' | 'projectsHref' | 'proof'>;
import { Crane } from './Crane';
import './pagehero.css';

type PageHeroProps = { content: PageHeroContent; site: PageHeroSite };

/**
 * The services page hero: headline and buttons on the left, a tower crane on the right that
 * keeps lowering a yellow beam carrying the next of `words`, and the site's proof line under a
 * ground line.
 *
 * Unlike the other sections it plays as soon as the page is shown (once the loader or page
 * transition has cleared), not when scrolled into view: it is the first thing on the page.
 */
export function PageHeroSection({ content, site }: PageHeroProps) {
  const ref = useRef<HTMLElement>(null);
  const reduced = usePrefersReducedMotion();
  const [released, setReleased] = useState(false);
  useEffect(() => whenReleased(() => setReleased(true)), []);
  useScrollProgress(ref);
  useMagnetic(ref);

  // is-in: entrance played. is-final: reduced motion, everything at rest. is-run: the crane loops.
  const shown = released || reduced;
  const running = released && !reduced;

  return (
    <section
      ref={ref}
      className={cx('gd gd-sec pagehero', `is-${content.ground}`, shown && 'is-in', reduced && 'is-final', running && 'is-run')}
      style={TYPE.body}
    >
      <div className="pagehero-grid" aria-hidden="true" />
      <div className="gd-wrap pagehero-in">
        <div className="pagehero-copy">
          <Eyebrow text={content.eyebrow} />
          <Heading text={content.title} as="h1" size="var(--pagehero-size)" lineHeight={0.94} delay={120} step={70} className="pagehero-h" />
          {content.lead && (
            <p className="pagehero-lead gd-rv" style={revealDelay(420)}>
              {content.lead}
            </p>
          )}
          {(content.mainButton || content.secondButton) && (
            <div className="pagehero-btns gd-rv" style={revealDelay(540)}>
              {content.mainButton && <Button href={content.mainLink.trim() || site.bidHref} label={content.mainButton} kind="solid" />}
              {content.secondButton && <Button href={content.secondLink || site.projectsHref} label={content.secondButton} kind="ghost" />}
            </div>
          )}
        </div>
        <div className={cx('pagehero-obj gd-rv', `is-${content.object}`)} aria-hidden="true" style={revealDelay(300, 30)}>
          <div className="pagehero-par">
            <Crane words={content.words} />
          </div>
        </div>
      </div>
      {content.showProof && (site.proof || site.licence) && (
        <div className="pagehero-ground">
          <div className="gd-wrap" style={TYPE.mono}>
            <p>{site.proof}</p>
            {site.licence && <p className="pagehero-lic">{site.licence}</p>}
          </div>
        </div>
      )}
    </section>
  );
}
