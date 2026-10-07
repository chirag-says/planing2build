import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import { Section } from '@/marketing/components/ui/Section';
import type { ClosingContent } from '@/marketing/content/pages/forProfessionals';
import { revealDelay } from '@/marketing/lib/css';
import './pages.css';

/** A closing call to action on a site board: hazard edge, headline on the beam, one button. */
export function Closing({ content }: { content: ClosingContent }) {
  return (
    <Section className="pg pg-closing" style={{ background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}>
      <div className="gd-wrap pg-wrap">
        <div className="pg-board gd-dark">
          <div className="pg-hz" aria-hidden="true" />
          <div className="pg-board-in">
            <Eyebrow text={content.eyebrow} />
            <Heading text={content.heading} size="clamp(48px,5.2vw,84px)" lineHeight={0.9} delay={80} />
            <p className="pg-sub gd-rv" style={revealDelay(240)}>
              {content.subCopy}
            </p>
            <div className="gd-rv" style={revealDelay(340)}>
              <Button href={content.buttonLink} label={content.button} kind="ghost" />
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
}
