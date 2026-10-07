import Link from 'next/link';
import type { CSSProperties, ReactNode } from 'react';
import { cx } from '@/marketing/lib/cx';
import { isOwnHost } from '@/marketing/lib/hosts';
import { resolveHref } from '@/marketing/lib/routes';

export type ButtonKind = 'solid' | 'ghost' | 'quiet';

type FaceProps = {
  label: ReactNode;
  sub?: string;
  /** SVG children (24-unit box) for the chip; it slides out and back in on hover. Default: the
   * girder glyph that swaps for an arrow. */
  glyph?: ReactNode;
};

/**
 * The inside of every button: a square chip whose girder glyph swaps for an arrow on hover,
 * and a label that a yellow fill rises behind.
 */
export function ButtonFace({ label, sub, glyph }: FaceProps) {
  return (
    <span className="gd-face">
      <span className="gd-chip" aria-hidden="true">
        <svg className="gd-g1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          {glyph ?? <path d="M5 5h14M5 19h14M12 5v14" />}
        </svg>
        <svg className="gd-g2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          {glyph ?? <path d="M5 12h14M13 5l7 7-7 7" />}
        </svg>
      </span>
      <span className="gd-lbl">
        {sub && <small className="gd-sub">{sub}</small>}
        <span className="gd-mark">
          <span className="gd-hl" aria-hidden="true" />
          {label}
        </span>
      </span>
    </span>
  );
}

type ButtonProps = FaceProps & {
  href: string;
  kind?: ButtonKind;
  className?: string;
  ariaLabel?: string;
  /** Which custom-cursor label a section shows over this button. */
  cursor?: string;
  style?: CSSProperties;
};

export function Button({ href, label, sub, glyph, kind = 'solid', className, ariaLabel, cursor = 'go', style }: ButtonProps) {
  const target = resolveHref(href);
  const shared = {
    className: cx('gd-btn', `gd-${kind}`, sub && 'gd-two', className),
    'data-mag': true,
    'data-cur': cursor,
    'aria-label': ariaLabel,
    style,
  };
  const face = <ButtonFace label={label} sub={sub} glyph={glyph} />;

  if (/^https?:\/\//.test(target) && !isOwnHost(target)) {
    return (
      <a href={target} target="_blank" rel="noopener" {...shared}>
        {face}
      </a>
    );
  }
  if (target.startsWith('/')) {
    return (
      <Link href={target} {...shared}>
        {face}
      </Link>
    );
  }
  return (
    <a href={target} {...shared}>
      {face}
    </a>
  );
}
