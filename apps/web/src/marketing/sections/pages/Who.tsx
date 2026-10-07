import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import { Section } from '@/marketing/components/ui/Section';
import type { WhoContent } from '@/marketing/content/pages/forProfessionals';
import { revealDelay } from '@/marketing/lib/css';
import { pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import './pages.css';

/** "Who it is for": the categories open now on ruled rows, then the ones coming soon. */
export function Who({ content }: { content: WhoContent }) {
  return (
    <Section className="pg pg-who" style={{ background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}>
      <div className="gd-wrap pg-wrap">
        <header className="pg-head">
          <Eyebrow text={content.eyebrow} />
          <Heading text={content.heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
        </header>
        <ul className="pg-rows">
          {content.open.map((item, index) => (
            <li key={item.name} className="pg-row gd-rv" style={revealDelay(160 + index * 90, 16)}>
              <span className="pg-row-ix" style={TYPE.mono}>
                {pad2(index + 1)}
              </span>
              <h3 className="pg-row-name" style={TYPE.display}>
                {item.name}
              </h3>
              <p className="pg-row-text">{item.text}</p>
            </li>
          ))}
        </ul>
        <p className="pg-soon gd-rv" style={{ ...TYPE.mono, ...revealDelay(480) }}>
          <b>{content.soonLabel}</b>
          {content.soon.join(' · ')}
        </p>
      </div>
    </Section>
  );
}
