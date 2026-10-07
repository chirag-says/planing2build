import type { CSSProperties } from 'react';
import { cx } from '@/marketing/lib/cx';
import type { StyleWithVars } from '@/marketing/lib/css';
import { parseHeadline, plainHeadline } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';

type HeadingProps = {
  /** Headline source: `|` breaks a line, `*words*` ride the yellow beam. */
  text: string;
  as?: 'h1' | 'h2' | 'h3' | 'p';
  /** Inline font-size. Pass a CSS variable when the size changes by breakpoint. */
  size?: string;
  lineHeight?: number | string;
  /** Delay (ms) before the first word rises. */
  delay?: number;
  /** Delay (ms) added for each following word. */
  step?: number;
  className?: string;
  style?: CSSProperties;
};

/**
 * Display headline whose words rise one after another out of their own clipping boxes when the
 * section reveals. Each word also exposes `--pd` (its delay plus 500ms), which section styles
 * use to time the beam that drops in behind the accent words.
 */
export function Heading({ text, as: Tag = 'h2', size, lineHeight = 0.92, delay = 0, step = 55, className, style }: HeadingProps) {
  let order = 0;
  return (
    <Tag
      className={cx('gd-hd', className)}
      aria-label={plainHeadline(text)}
      style={{ ...TYPE.display, ...(size ? { fontSize: size } : {}), lineHeight, ...style }}
    >
      {parseHeadline(text).map((line, lineIndex) => (
        <span key={lineIndex} className="gd-hd-l" aria-hidden="true">
          {line.map((word, wordIndex) => {
            const wordDelay = delay + order++ * step;
            const timing: StyleWithVars = { transitionDelay: `${wordDelay}ms`, '--pd': `${wordDelay + 500}ms` };
            return (
              <span key={wordIndex} className={cx('gd-hd-w', word.accent && 'is-accw')}>
                <span className={cx('gd-hd-i', word.accent && 'is-acc')} style={timing}>
                  {word.accent ? (
                    <span className="gd-it">
                      {word.text}
                      {word.tail}
                    </span>
                  ) : (
                    <>
                      {word.text}
                      {word.tail}
                    </>
                  )}
                </span>{' '}
              </span>
            );
          })}
        </span>
      ))}
    </Tag>
  );
}
