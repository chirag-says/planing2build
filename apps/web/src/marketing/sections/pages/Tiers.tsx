import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import { Section } from '@/marketing/components/ui/Section';
import type { PlanTier, TiersContent } from '@/marketing/content/pages/forHomeowners';
import { revealDelay } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { TYPE } from '@/marketing/lib/typography';
import './pages.css';

function TierSheet({ tier, dark, delay }: { tier: PlanTier; dark?: boolean; delay: number }) {
  return (
    <article className={cx('pg-tier gd-rv', dark ? 'is-dark gd-dark' : 'gd-lt')} style={revealDelay(delay, 18)}>
      {dark && <div className="pg-hz" aria-hidden="true" />}
      <header className="pg-tier-bar" style={TYPE.mono}>
        <span>
          <i aria-hidden="true" />
          {tier.title}
        </span>
        <span className="pg-tier-note">{tier.note}</span>
      </header>
      <ul className="pg-tier-list">
        {tier.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </article>
  );
}

/** "Free, then one package": the free dashboard beside the package, with the steps between. */
export function Tiers({ content }: { content: TiersContent }) {
  return (
    <Section className="pg pg-tiers" style={{ background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}>
      <div className="gd-wrap pg-wrap">
        <header className="pg-head">
          <Eyebrow text={content.eyebrow} />
          <Heading text={content.heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
          <p className="pg-sub gd-rv" style={revealDelay(240)}>
            {content.subCopy}
          </p>
        </header>
        <div className="pg-tiers-grid">
          <TierSheet tier={content.free} delay={200} />
          <ol className="pg-steps gd-rv" style={{ ...TYPE.mono, ...revealDelay(320) }}>
            {content.steps.map((step, index) => (
              <li key={step}>
                <b>{String(index + 1).padStart(2, '0')}</b>
                {step}
              </li>
            ))}
          </ol>
          <TierSheet tier={content.paid} dark delay={420} />
        </div>
        <div className="pg-cta gd-rv" style={revealDelay(520)}>
          <Button href={content.buttonLink} label={content.button} />
        </div>
      </div>
    </Section>
  );
}
