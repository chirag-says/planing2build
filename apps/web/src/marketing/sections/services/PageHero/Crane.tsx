'use client';

import { useState, type AnimationEvent } from 'react';
import { pad2, splitList } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';

/** The drawing board the crane is laid out on; the whole board is scaled to fit (see --pagehero-s). */
const BOARD_WIDTH = 440;
const BOARD_HEIGHT = 460;
const MAX_WORDS = 8;

/**
 * A tower crane whose hook lowers a yellow beam, holds it, and hoists it back up (one 3.6s
 * cycle). Each time the beam is back up, the next word goes on it.
 */
export function Crane({ words: source }: { words: string }) {
  const words = splitList(source).slice(0, MAX_WORDS);
  const [cycle, setCycle] = useState(0);
  const current = words.length ? cycle % words.length : 0;

  const onCycle = (event: AnimationEvent<HTMLSpanElement>) => {
    // Only the hoist loop itself, not an animation bubbling up from a word.
    if (event.target === event.currentTarget && words.length > 1) setCycle((value) => (value + 1) % words.length);
  };

  return (
    <div className="pagehero-box">
      <svg className="pagehero-ties" width={BOARD_WIDTH} height={BOARD_HEIGHT} viewBox={`0 0 ${BOARD_WIDTH} ${BOARD_HEIGHT}`}>
        <path d="M341 20L96 58M341 20L424 58" />
      </svg>
      <span className="pagehero-mast" />
      <span className="pagehero-apex" />
      <span className="pagehero-cab" />
      <span className="pagehero-jib" />
      <span className="pagehero-cjib" />
      <span className="pagehero-foot" />
      <span className="pagehero-gl" />
      <span className="pagehero-trolley">
        <span className="pagehero-drop">
          <span className="pagehero-load" onAnimationIteration={onCycle}>
            <i className="pagehero-cable" />
            <i className="pagehero-hook" />
            <svg className="pagehero-slings" width="140" height="34" viewBox="0 0 140 34">
              <path d="M70 0L6 34M70 0L134 34" />
            </svg>
            <span className="pagehero-plate" style={TYPE.display}>
              {(words.length ? words : ['']).map((word, index) => (
                <b key={index} className={index === current ? 'is-cur' : ''}>
                  {word}
                </b>
              ))}
            </span>
            {words.length > 1 && (
              <em className="pagehero-count" style={TYPE.mono}>
                {pad2(current + 1)} / {pad2(words.length)}
              </em>
            )}
          </span>
        </span>
      </span>
    </div>
  );
}
