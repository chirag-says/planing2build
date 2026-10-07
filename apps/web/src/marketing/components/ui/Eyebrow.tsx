import type { CSSProperties } from 'react';
import { cx } from '@/marketing/lib/cx';
import { TYPE } from '@/marketing/lib/typography';

type EyebrowProps = { text: string; delay?: number; className?: string; style?: CSSProperties };

/** The small label above a section headline ("02 · What we build"), with its marker dot. */
export function Eyebrow({ text, delay = 0, className, style }: EyebrowProps) {
  if (!text) return null;
  return (
    <p className={cx('gd-eb', className)} style={{ ...TYPE.mono, transitionDelay: `${delay}ms`, ...style }}>
      <i aria-hidden="true" />
      {text}
    </p>
  );
}
