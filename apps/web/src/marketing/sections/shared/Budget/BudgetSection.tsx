'use client';

import { useRef, useState } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { BudgetContent } from '@/marketing/content/sections/budget';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { TYPE } from '@/marketing/lib/typography';
import {
  bidLink,
  defaultSize,
  estimate,
  FALLBACK_RATE,
  formatCount,
  formatMoney,
  parseFinishes,
  parseRates,
  sizeFraction,
  sliderStep,
  slugify,
  snapSize,
} from './estimate';
import { useApiEstimate } from './useApiEstimate';
import { useEstimateMotion } from './useEstimateMotion';
import { getTranslator } from '@/lib/i18n';
import { useSectionWidth } from '@/marketing/hooks/useSectionWidth';
import { PHONE_MAX } from '@/marketing/lib/breakpoints';
import './budget.css';

/** The sheet offers at most this many job types, in the services' CMS order. */
const MAX_TYPES = 6;
const NO_FINISH = { label: '', factor: 1 };
/** The sheet's finish choices, in order, as the API names them. */
const FINISH_LEVELS = ['STANDARD', 'PREMIUM', 'LUXURY'] as const;
const estimateCopy = getTranslator('Estimate');

/** "08 · A rough budget": three answers give a budget range, a schedule and a prefilled bid link. */
type BudgetProps = {
  content: BudgetContent;
  /** Job types offered, in CMS order. */
  services: Array<{ slug: string; name: string }>;
  bidHref: string;
  siteName: string;
};

export function BudgetSection({ content, services, bidHref, siteName }: BudgetProps) {
  const {
    eyebrow,
    heading,
    subCopy,
    factNumber,
    factLabel,
    cardTitle,
    typeLabel,
    sizeLabel,
    unitLabel,
    finishLabel,
    resultLabel,
    scheduleLabel,
    weeksText,
    lowLabel,
    highLabel,
    note,
    cta,
  } = content;
  const sectionRef = useRef<HTMLElement>(null);
  const revealed = useReveal(sectionRef, 0.12);
  const reduced = usePrefersReducedMotion();
  const narrow = useSectionWidth(sectionRef) < PHONE_MAX;
  useMagnetic(sectionRef);

  const jobTypes = services.filter((service) => service.name.trim()).slice(0, MAX_TYPES);
  const rates = parseRates(content.rates);
  const finishes = parseFinishes(content.finishes);

  const [typeIndex, setTypeIndex] = useState(0);
  const [finishIndex, setFinishIndex] = useState(0);
  /** Each job type remembers its own size. */
  const [sizes, setSizes] = useState<Record<string, number>>({});

  const jobType = jobTypes[Math.min(typeIndex, Math.max(0, jobTypes.length - 1))];
  const typeSlug = jobType ? jobType.slug || slugify(jobType.name) : 'project';
  const rate = rates[typeSlug] ?? (jobType ? rates[slugify(jobType.name)] : undefined) ?? FALLBACK_RATE;
  const size = snapSize(sizes[typeSlug] ?? defaultSize(rate), rate);
  const finish = finishes[Math.min(finishIndex, Math.max(0, finishes.length - 1))] ?? NO_FINISH;
  // The tape's tick positions are the sheet's own drawing; the money and the time come from the
  // public estimator (floors: the first question's answers are Ground only to Ground + 3).
  const drawing = estimate({
    rate,
    size,
    finish: finish.factor,
    topFinish: Math.max(1, ...finishes.map((item) => item.factor)),
    spread: content.spread,
    narrow,
  });
  const api = useApiEstimate(Math.min(4, typeIndex + 1), size, FINISH_LEVELS[finishIndex] ?? 'STANDARD');
  const result = { ...drawing, low: api?.low ?? NaN, high: api?.high ?? NaN, weeks: api?.months ?? NaN };

  const { tapeRef, lowRef, highRef, weeksRef, onProgress, lock } = useEstimateMotion(sectionRef, result, !reduced);
  useScrollProgress(sectionRef, { onProgress });

  const [weeksBefore = '', ...weeksRest] = (weeksText || '{n}').split('{n}');
  const weeksAfter = weeksRest.join('');
  const sizeNumber = jobTypes.length > 0 ? '02' : '01';
  const finishNumber = jobTypes.length > 0 ? '03' : '02';

  return (
    <section
      ref={sectionRef}
      id="cost-check"
      className={cx('gd gd-sec budget', revealed && 'is-in')}
      style={{ ...TYPE.body, background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}
    >
      <div className="budget-grid" aria-hidden="true" />
      <div className="gd-wrap budget-cols">
        <div className="budget-side">
          <Eyebrow text={eyebrow} />
          <Heading text={heading} size="var(--budget-hd)" lineHeight={0.9} delay={80} className="budget-h" />
          {subCopy && (
            <p className="budget-sub gd-rv" style={revealDelay(260)}>
              {subCopy}
            </p>
          )}
          {(factNumber || factLabel) && (
            <div className="budget-fact gd-rv" style={revealDelay(380)}>
              {factNumber && (
                <span className="budget-fact-n" style={TYPE.display}>
                  <i aria-hidden="true" />
                  {factNumber}
                </span>
              )}
              {factLabel && (
                <span className="budget-fact-l" style={TYPE.mono}>
                  {factLabel}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="budget-card gd-lt gd-rv" style={revealDelay(180, 34)}>
          <p className="budget-top" style={TYPE.mono}>
            <span>
              <i className="budget-dot" aria-hidden="true" />
              {cardTitle}
            </span>
            <span>{siteName}</span>
          </p>

          {jobTypes.length > 0 && (
            <div className="budget-row">
              <p className="budget-lab" style={TYPE.mono} id="budget-l1">
                <b>01</b>
                {typeLabel}
              </p>
              <div className="budget-seg" role="group" aria-labelledby="budget-l1" style={TYPE.mono}>
                {jobTypes.map((service, index) => (
                  <button
                    key={service.slug || index}
                    type="button"
                    className={index === typeIndex ? 'is-on' : ''}
                    aria-pressed={index === typeIndex}
                    onClick={() => {
                      lock();
                      setTypeIndex(index);
                    }}
                  >
                    {service.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="budget-row">
            <p className="budget-lab" style={TYPE.mono}>
              <b>{sizeNumber}</b>
              {sizeLabel}
            </p>
            <div className="budget-size">
              <output className="budget-read" style={TYPE.mono} htmlFor="budget-size">
                {formatCount(size)}
                <small>{unitLabel}</small>
              </output>
              <input
                id="budget-size"
                className="budget-range"
                type="range"
                min={rate.min}
                max={rate.max}
                step={sliderStep(rate.min, rate.max)}
                value={size}
                aria-label={`${sizeLabel} (${unitLabel})`}
                aria-valuetext={`${formatCount(size)} ${unitLabel}`}
                style={{ '--f': sizeFraction(size, rate).toFixed(4) } as StyleWithVars}
                onChange={(event) => {
                  lock();
                  const value = parseFloat(event.target.value);
                  setSizes((previous) => ({ ...previous, [typeSlug]: value }));
                }}
              />
              <p className="budget-ends" style={TYPE.mono} aria-hidden="true">
                <span>{formatCount(rate.min)}</span>
                <span>
                  {formatCount(rate.max)} {unitLabel}
                </span>
              </p>
            </div>
          </div>

          {finishes.length > 0 && (
            <div className="budget-row">
              <p className="budget-lab" style={TYPE.mono} id="budget-l3">
                <b>{finishNumber}</b>
                {finishLabel}
              </p>
              <div className="budget-seg is-eq" role="group" aria-labelledby="budget-l3" style={TYPE.mono}>
                {finishes.map((item, index) => (
                  <button
                    key={index}
                    type="button"
                    className={index === finishIndex ? 'is-on' : ''}
                    aria-pressed={index === finishIndex}
                    onClick={() => {
                      lock();
                      setFinishIndex(index);
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="budget-out">
            <div className="budget-nums">
              <div>
                <p className="budget-k" style={TYPE.mono}>
                  {resultLabel}
                </p>
                <p className="budget-big" style={TYPE.display} aria-hidden="true">
                  <span ref={lowRef}>{formatMoney(result.low)}</span>
                  <i>–</i>
                  <span ref={highRef}>{formatMoney(result.high)}</span>
                </p>
              </div>
              <div className="budget-sch">
                <p className="budget-k" style={TYPE.mono}>
                  {scheduleLabel}
                </p>
                <p className="budget-wk" style={TYPE.display} aria-hidden="true">
                  {weeksBefore}
                  <span ref={weeksRef}>{Number.isFinite(result.weeks) ? result.weeks : '…'}</span>
                  {weeksAfter}
                </p>
              </div>
            </div>
            <p className="gd-sr" aria-live="polite">
              {`${resultLabel}: ${formatMoney(result.low)} to ${formatMoney(result.high)}. ${scheduleLabel}: ${weeksBefore}${Number.isFinite(result.weeks) ? result.weeks : '…'}${weeksAfter}.`}
            </p>
            <div
              ref={tapeRef}
              className="budget-tape"
              aria-hidden="true"
              style={{ ...TYPE.mono, '--lo': result.tapeLow.toFixed(4), '--hi': result.tapeHigh.toFixed(4) } as StyleWithVars}
            >
              <span className="budget-case">
                <i />
              </span>
              <div className="budget-run">
                <span className="budget-rule" />
                <span className="budget-blade" />
                <span className="budget-span" />
                <span className="budget-mk is-lo">
                  <i />
                  <b>{lowLabel}</b>
                </span>
                <span className="budget-mk is-hi">
                  <i />
                  <b>{highLabel}</b>
                </span>
              </div>
            </div>
            <div className="budget-foot">
              {note && (
                <p className="budget-note" style={TYPE.mono}>
                  {note}
                  {api?.isDemo && ` · ${estimateCopy('demoBadge')}`}
                </p>
              )}
              {cta && <Button href={content.ctaLink || bidLink(bidHref, typeSlug, size, finish.label)} label={cta} kind="solid" />}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
