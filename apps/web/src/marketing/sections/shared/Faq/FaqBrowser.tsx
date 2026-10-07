'use client';

import { useState, useSyncExternalStore } from 'react';
import type { Faq } from '@/marketing/content/types';
import { usePrefersReducedMotion } from '@/marketing/hooks/usePrefersReducedMotion';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';

type FaqBrowserProps = {
  questions: Faq[];
  showTabs: boolean;
  allLabel: string;
  tagLetter: string;
};

const subscribeNever = () => () => {};

/** False in the server HTML and during hydration, true once the client has taken over. */
const useHydrated = () =>
  useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false,
  );

/** Scroll pass (--sp) at which the first row starts to rise in, and how much later each next row starts. */
const ROW_START = 0.16;
const ROW_STAGGER = 0.045;

/**
 * Group tabs and the accordion. Picking a tab filters the rows and opens the first one; one row
 * is open at a time.
 *
 * Once hydrated (and unless motion is reduced) the list gets `is-sc`, and each row then rises
 * in as the section scrolls past its own point (`--a`) of the section's --sp. The server HTML
 * has no `is-sc`, so every row is visible without JavaScript.
 */
export function FaqBrowser({ questions, showTabs, allLabel, tagLetter }: FaqBrowserProps) {
  const hydrated = useHydrated();
  const reduced = usePrefersReducedMotion();
  const [group, setGroup] = useState('');
  const [openIndex, setOpenIndex] = useState(0);

  const groups: string[] = [];
  for (const item of questions) {
    const name = item.group.trim();
    if (name && !groups.includes(name)) groups.push(name);
  }
  const countIn = (name: string) => questions.filter((item) => item.group.trim() === name).length;
  const activeGroup = showTabs && groups.includes(group) ? group : '';
  const shown = activeGroup ? questions.filter((item) => item.group.trim() === activeGroup) : questions;
  const tabs =
    showTabs && groups.length > 1
      ? [{ key: '', label: allLabel, count: questions.length }, ...groups.map((name) => ({ key: name, label: name, count: countIn(name) }))]
      : [];

  return (
    <div className={cx('faq-main', hydrated && !reduced && 'is-sc')}>
      {tabs.length > 0 && (
        <div className="faq-tabs gd-rv" role="group" aria-label="Filter the questions" style={{ ...TYPE.mono, ...revealDelay(200, 14) }}>
          {tabs.map((tab) => (
            <button
              key={tab.key || 'all'}
              type="button"
              className={tab.key === activeGroup ? 'is-on' : ''}
              aria-pressed={tab.key === activeGroup}
              onClick={() => {
                setGroup(tab.key);
                setOpenIndex(0);
              }}
            >
              {tab.label}
              <i>{pad2(tab.count)}</i>
            </button>
          ))}
        </div>
      )}
      {shown.length > 0 && (
        <ul className="faq-list">
          {shown.map((item, index) => {
            const open = index === openIndex;
            const id = `faq-${item.slug || index}`;
            const entrance: StyleWithVars = { '--a': (ROW_START + index * ROW_STAGGER).toFixed(3) };
            return (
              <li key={item.slug || index} className={cx('faq-row', open && 'is-open')} style={entrance}>
                <h3 className="faq-q">
                  <button
                    type="button"
                    id={`${id}-q`}
                    aria-expanded={open}
                    aria-controls={`${id}-a`}
                    onClick={() => setOpenIndex(open ? -1 : index)}
                  >
                    <span className="faq-tag" style={TYPE.mono}>
                      {tagLetter}
                      {pad2(questions.indexOf(item) + 1)}
                    </span>
                    <span className="faq-qt" style={TYPE.display}>
                      {item.question}
                    </span>
                    <span className="faq-pm" aria-hidden="true">
                      <i />
                      <i />
                    </span>
                  </button>
                </h3>
                <div className="faq-a" id={`${id}-a`} role="region" aria-labelledby={`${id}-q`}>
                  <div className="faq-ai">
                    <p>{item.answer}</p>
                    {item.group && (
                      <span className="faq-grp" style={TYPE.mono}>
                        {item.group}
                      </span>
                    )}
                  </div>
                </div>
                <i className="faq-beam" aria-hidden="true" />
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
