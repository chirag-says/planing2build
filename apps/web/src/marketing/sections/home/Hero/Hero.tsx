import imgHeroHouse from '@/marketing/assets/hero-house.webp';
import Image from 'next/image';
import { Button } from '@/marketing/components/ui/Button';
import { ARROW_UP_RIGHT } from '@/marketing/components/ui/glyphs';
import type { HeroContent } from '@/marketing/content/sections/hero';
import { parseHeadline, plainHeadline, pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import './hero.css';

/** The headline runs one step heavier than the kit's display weight. */
const HEADLINE = { ...TYPE.display, fontWeight: 900 };

/**
 * Home page hero: the "Build with clarity" headline and pitch on the left, the half-built,
 * half-drawn house on the right with its four labelled pointers, and the six-step rail along the
 * bottom. Everything is server-rendered.
 */
export function Hero({ content }: { content: HeroContent }) {
  const lines = parseHeadline(content.heading);

  return (
    <section className="gd ph" aria-labelledby="ph-title">
      <div className="ph-main">
        <div className="ph-copy">
          <p className="ph-eb ph-in" style={TYPE.mono}>
            <i aria-hidden="true" />
            {content.eyebrow}
          </p>
          <h1 id="ph-title" className="ph-h1" aria-label={plainHeadline(content.heading)} style={HEADLINE}>
            {lines.map((line, lineIndex) => (
              // The space between lines keeps the heading's text a sentence ("Build with clarity.")
              // for copy, search and text matching; the lines are blocks, so it is not seen.
              <span key={lineIndex} className="ph-ln" aria-hidden="true">
                {lineIndex > 0 && ' '}
                <span className="ph-lni" style={{ animationDelay: `${120 + lineIndex * 110}ms` }}>
                  {line.map((word, wordIndex) =>
                    word.accent ? (
                      <span key={wordIndex} className="ph-acc">
                        {word.text}
                        {word.tail}
                      </span>
                    ) : (
                      <span key={wordIndex}>
                        {word.text}
                        {word.tail}
                        {wordIndex < line.length - 1 ? ' ' : ''}
                      </span>
                    ),
                  )}
                </span>
              </span>
            ))}
          </h1>
          <p className="ph-sub ph-in" style={TYPE.body}>
            {content.subCopy}
          </p>
          <div className="ph-btns ph-in">
            <Button href={content.primaryLink} label={content.primary} kind="solid" glyph={ARROW_UP_RIGHT} />
            <Button href={content.secondaryLink} label={content.secondary} kind="ghost" glyph={ARROW_UP_RIGHT} className="ph-pro" />
          </div>
        </div>

        <div className="ph-art">
          <div className="ph-pic">
            <Image
              src={imgHeroHouse.src}
              alt={content.imageAlt}
              width={1536}
              height={1024}
              sizes="(max-width: 1099px) 100vw, 70vw"
              preload
            />
            <ul className="ph-tags">
              {content.callouts.map((callout) => (
                <li key={callout.title} className="ph-tag">
                  <i className="ph-tag-mk" aria-hidden="true" />
                  <b>{callout.title}</b>
                  {callout.lines.map((line) => (
                    <span key={line}>{line}</span>
                  ))}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="ph-rail" id="how-it-works">
        <ol className="ph-steps">
          {content.steps.map((step, index) => (
            <li key={step.title} style={{ animationDelay: `${700 + index * 70}ms` }}>
              <i className="ph-bar" aria-hidden="true" />
              <p className="ph-step-t" style={TYPE.mono}>
                <span>{pad2(index + 1)}</span>
                <b>{step.title}</b>
              </p>
              <p className="ph-step-d" style={TYPE.body}>
                {step.text}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
