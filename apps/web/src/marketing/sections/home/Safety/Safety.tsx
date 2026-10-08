import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { SafetyContent } from '@/marketing/content/sections/safety';
import { revealDelay } from '@/marketing/lib/css';
import { TYPE } from '@/marketing/lib/typography';
import { DrawingLabels, DrawingStrokes } from './DrawingParts';
import { GRID_X, STOREYS } from './drawing';
import { SafetyShell } from './SafetyShell';
import './safety.css';

const MAX_CHECKS = 5;
const MAX_CERTS = 6;

/** The part of the building a check covers, highlighted while that check is active. */
function ZoneShape({ check }: { check: number }) {
  switch (check) {
    case 0: // foundations: basement box, raft and piles
      return (
        <>
          <rect x="224" y="600" width="312" height="106" />
          <rect x="216" y="688" width="328" height="18" />
          {GRID_X.map((x) => (
            <path key={x} d={`M${x - 8} 706V776L${x} 790L${x + 8} 776V706Z`} />
          ))}
        </>
      );
    case 1: // structure: every slab and column above ground
      return (
        <>
          {STOREYS.map(({ top }) => (
            <rect key={top} x="230" y={top} width="300" height="10" />
          ))}
          {STOREYS.map(({ base, top }) =>
            GRID_X.map((x) => <rect key={`${top}-${x}`} x={x - 6} y={top + 10} width="12" height={base - top - 10} />),
          )}
        </>
      );
    case 2: // envelope: both facades
      return (
        <>
          <rect x="221" y="146" width="10" height="444" />
          <rect x="529" y="146" width="10" height="444" />
        </>
      );
    case 3: // roof
      return <rect x="222" y="134" width="316" height="36" />;
    default: // people: the scaffold
      return <rect x="172" y="148" width="44" height="442" />;
  }
}

/**
 * "Safety & quality": an elevation drawing that draws itself from the piles up as the section
 * scrolls, with five numbered checks pinned to the parts of the building they cover, and the
 * audit plates underneath.
 */
export function Safety({ content }: { content: SafetyContent }) {
  const { eyebrow, heading, checkWord, certLabel } = content;
  const checks = content.checks.filter((check) => check.title).slice(0, MAX_CHECKS);
  const certs = content.certs.filter(Boolean).slice(0, MAX_CERTS);

  return (
    <SafetyShell
      id="safety"
      checks={checks}
      checkWord={checkWord}
      header={
        <header className="safety-top">
          <Eyebrow text={eyebrow} />
          <Heading text={heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
        </header>
      }
      strokes={<DrawingStrokes />}
      labels={<DrawingLabels />}
      zones={checks.map((_, index) => (
        <ZoneShape key={index} check={index} />
      ))}
      certs={
        certs.length > 0 && (
          <div className="safety-certs gd-rv" style={revealDelay(450)}>
            {certLabel.trim() && (
              <p className="safety-cl" style={TYPE.mono}>
                {certLabel}
              </p>
            )}
            <ul className="safety-plates" style={TYPE.mono}>
              {certs.map((cert, index) => (
                <li key={index}>
                  <i aria-hidden="true">
                    <svg viewBox="0 0 16 16">
                      <path d="M3.5 8.4l3 3 6-6.6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="square" />
                    </svg>
                  </i>
                  {cert}
                </li>
              ))}
            </ul>
          </div>
        )
      }
    />
  );
}
