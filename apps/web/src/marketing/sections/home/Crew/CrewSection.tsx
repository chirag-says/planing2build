'use client';

import './crew.css';
import { useCallback, useRef, useState } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import type { CrewContent } from '@/marketing/content/sections/crew';
import type { TeamMember } from '@/marketing/content/types';

/** The team fields a badge shows. */
export type CrewMember = Pick<
  TeamMember,
  'slug' | 'name' | 'role' | 'years' | 'certs' | 'quote' | 'phone' | 'email' | 'badge' | 'photo'
>;
import { useMagnetic } from '@/marketing/hooks/useMagnetic';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { useReveal } from '@/marketing/hooks/useReveal';
import { useScrollProgress } from '@/marketing/hooks/useScrollProgress';
import { cx } from '@/marketing/lib/cx';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { telHref } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { useSectionWidth } from '@/marketing/hooks/useSectionWidth';
import { PHONE_MAX } from '@/marketing/lib/breakpoints';
import { framerPhoto } from '@/marketing/lib/images';

const MAX_BADGES = 8;
/** The reference prints at most three certificates per badge. */
const MAX_CERTS = 3;
const PHOTO_SIZES = '(max-width: 809px) 72vw, (max-width: 1099px) 44vw, 320px';
/**
 * Badges drop onto their hooks one by one as the section scrolls through: the first when the
 * section's pass progress (--sp) passes 0.16, then one more every 0.035.
 */
const DROP_START = 0.16;
const DROP_STEP = 0.035;

type CrewProps = { content: CrewContent; team: CrewMember[]; siteName: string };

export function CrewSection({ content, team, siteName }: CrewProps) {
  const ref = useRef<HTMLElement>(null);
  const revealed = useReveal(ref);
  const reduced = usePrefersReducedMotion();
  const phone = useSectionWidth(ref) < PHONE_MAX;
  useMagnetic(ref);

  const members = team.filter((member) => member.name).slice(0, MAX_BADGES);
  const count = members.length;

  // How many badges have dropped. It only grows; the ref keeps scroll frames from touching state.
  const [dropped, setDropped] = useState(0);
  const droppedRef = useRef(0);
  const onProgress = useCallback(
    (pass: number) => {
      const due = pass > DROP_START ? Math.min(count, 1 + Math.floor((pass - DROP_START) / DROP_STEP)) : 0;
      if (due <= droppedRef.current) return;
      droppedRef.current = due;
      setDropped(due);
    },
    [count],
  );
  useScrollProgress(ref, { onProgress });

  const meta = (member: CrewMember) =>
    [member.years && `${member.years} ${content.yearsWord}`, member.badge && `${content.badgeWord} ${member.badge}`]
      .filter(Boolean)
      .join(' · ');

  return (
    <section
      ref={ref}
      id="crew"
      className={cx('gd gd-sec crew', revealed && 'is-in', reduced && 'is-flat')}
      style={TYPE.body}
    >
      <div className="gd-wrap crew-wrap">
        <header className="crew-top">
          <div className="crew-ttl">
            <Eyebrow text={content.eyebrow} />
            <Heading text={content.heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
            {content.subCopy.trim() && (
              <p className="crew-sub gd-rv" style={revealDelay(320)}>
                {content.subCopy}
              </p>
            )}
          </div>
          {content.allLabel.trim() && (
            <div className="gd-rv" style={revealDelay(400)}>
              <Button href={content.allLink || '/team'} label={content.allLabel} kind="ghost" />
            </div>
          )}
        </header>
        {count > 0 && (
          // A sideways-scrolling row on phones: focusable and named, so it scrolls from the keyboard.
          <div className="crew-scroll" role="region" tabIndex={0} aria-label={content.eyebrow || 'Team'}>
            <ul className="crew-row" style={{ '--n': Math.min(4, count) } as StyleWithVars}>
              {members.map((member, index) => {
                const first = member.name.trim().split(/\s+/)[0] ?? '';
                const certs = member.certs.slice(0, MAX_CERTS);
                const actions = <MemberActions member={member} first={first} meetWord={content.meetWord} />;
                return (
                  <li key={member.slug || index} className="crew-col">
                    <span className="crew-hook" aria-hidden="true" />
                    <div
                      className={cx('crew-hang', revealed && index < dropped && 'is-dropped')}
                      style={{ '--i': index } as StyleWithVars}
                    >
                      <div className="crew-swing">
                        <span className="crew-strap" aria-hidden="true" />
                        <span className="crew-clip" aria-hidden="true" />
                        {/* Focusable so keyboard users can turn the badge over: the flip runs on :focus. */}
                        <div
                          className="crew-flip"
                          tabIndex={phone ? undefined : 0}
                          role="group"
                          aria-label={`${member.name}, ${member.role}`}
                        >
                          <div className="crew-card">
                            <div className="crew-face crew-front gd-lt">
                              <span className="crew-slot" aria-hidden="true" />
                              <p className="crew-id" style={TYPE.mono}>
                                <span>
                                  <i aria-hidden="true" />
                                  {siteName} · {content.idLabel}
                                </span>
                                {member.badge && <span>No. {member.badge}</span>}
                              </p>
                              <div className="crew-pic">
                                <img
                                  {...framerPhoto(member.photo, PHOTO_SIZES)}
                                  alt={member.name}
                                  loading="lazy"
                                  decoding="async"
                                  draggable={false}
                                />
                              </div>
                              <h3 className="crew-name" style={TYPE.display}>
                                {member.name}
                              </h3>
                              <p className="crew-role">{member.role}</p>
                              {phone && member.quote && <p className="crew-q1">“{member.quote}”</p>}
                              <p className="crew-meta" style={TYPE.mono}>
                                {meta(member)}
                              </p>
                              {certs.length > 0 && (
                                <ul className="crew-chips" style={TYPE.mono}>
                                  {certs.map((cert, certIndex) => (
                                    <li key={certIndex}>{cert}</li>
                                  ))}
                                </ul>
                              )}
                              {phone && <div className="crew-act">{actions}</div>}
                            </div>
                            {!phone && (
                              <div className="crew-face crew-back gd-dark">
                                <span className="crew-slot" aria-hidden="true" />
                                <p className="crew-id" style={TYPE.mono}>
                                  <span>
                                    <i aria-hidden="true" />
                                    {first}
                                  </span>
                                  <span>{meta(member)}</span>
                                </p>
                                <p className="crew-q" style={TYPE.display}>
                                  <i aria-hidden="true" />
                                  {member.quote || member.role}
                                </p>
                                <p className="crew-by" style={TYPE.mono}>
                                  {member.name}
                                  <br />
                                  {member.role}
                                </p>
                                <div className="crew-act">{actions}</div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

type MemberActionsProps = { member: CrewMember; first: string; meetWord: string };

/** Phone and email links, then the profile button: on the back of the badge, or the front on phones. */
function MemberActions({ member, first, meetWord }: MemberActionsProps) {
  return (
    <>
      {(member.phone || member.email) && (
        <p className="crew-links" style={TYPE.mono}>
          {member.phone && <a href={telHref(member.phone)}>{member.phone}</a>}
          {member.email && <a href={`mailto:${member.email}`}>{member.email}</a>}
        </p>
      )}
      {meetWord.trim() && (
        <Button
          href={`/team/${member.slug}`}
          label={`${meetWord} ${first}`.trim()}
          kind="quiet"
          ariaLabel={`${meetWord} ${member.name}`}
        />
      )}
    </>
  );
}
