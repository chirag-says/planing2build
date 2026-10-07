'use client';

import { useRef, type ReactNode } from 'react';
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import type { StyleWithVars } from '@/marketing/lib/css';
import { TYPE } from '@/marketing/lib/typography';

type SectionProps = {
  className: string;
  id?: string;
  /** Visible fraction needed before the section reveals (see useReveal). */
  revealThreshold?: number;
  /** Publish --sp / --pp scroll progress (see useScrollProgress). */
  trackScroll?: boolean;
  style?: StyleWithVars;
  children: ReactNode;
  'aria-label'?: string;
};

/**
 * Page section shell. Gives server-rendered section content the three behaviours every section
 * shares: the `is-in` reveal class, scroll-progress variables, and magnetic buttons.
 * Sections with their own client state call the hooks directly instead.
 */
export function Section({ className, revealThreshold, trackScroll = true, style, children, ...rest }: SectionProps) {
  const ref = useRef<HTMLElement>(null);
  const revealed = useReveal(ref, revealThreshold);
  useScrollProgress(ref, { enabled: trackScroll });
  useMagnetic(ref);
  return (
    <section ref={ref} className={cx('gd gd-sec', className, revealed && 'is-in')} style={{ ...TYPE.body, ...style }} {...rest}>
      {children}
    </section>
  );
}
