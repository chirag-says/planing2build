'use client';

import { useState, type PointerEvent } from 'react';
import type { BoardStat } from '@/marketing/content/sections/board';
import { cx } from '@/marketing/lib/cx';
import { pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { useBoardMode, type BoardMode } from './BoardShell';

/** First figure starts rolling 150ms after the count begins; each further cell 340ms later. */
const FIRST_DELAY = 150;
const CELL_STAGGER = 340;
/** Each digit strip of a figure starts 90ms after the one before. */
const DIGIT_STAGGER = 90;
/** Punctuation ("%", ",", "$") fades in 200ms after the figure starts. */
const SYMBOL_DELAY = 200;
/** A strip holds a blank and then ten digits ending on its own, so it lands on row 10. */
const STRIP_ROWS = 11;

type BoardStatCellProps = {
  stat: BoardStat;
  index: number;
  /** The yellow cell: a mechanical counter with one tile per digit. */
  yellow: boolean;
  /** Odd last cell spans both columns on phone and tablet. */
  wide: boolean;
};

/** One board cell. Hovering it with a mouse rolls its figure again from the start. */
export function BoardStatCell({ stat, index, yellow, wide }: BoardStatCellProps) {
  const mode = useBoardMode();
  const [replays, setReplays] = useState(0);
  const onPointerEnter = (event: PointerEvent) => {
    if (event.pointerType === 'mouse' && mode === 'roll') setReplays((count) => count + 1);
  };
  return (
    <li className={cx('board-cell', yellow && 'is-y gd-lt', wide && 'is-wide')} onPointerEnter={onPointerEnter}>
      <span className="board-ix" style={TYPE.mono} aria-hidden="true">
        {pad2(index + 1)}
      </span>
      <p className="board-num" style={TYPE.display}>
        <span className="gd-sr">{stat.value}</span>
        {/* a new key remounts the strips, which restarts their CSS animation */}
        <BoardFigure key={replays} value={stat.value} mode={mode} delay={replays ? 0 : FIRST_DELAY + index * CELL_STAGGER} tile={yellow} />
      </p>
      <p className="board-lb" style={TYPE.mono}>
        {stat.label}
      </p>
    </li>
  );
}

type BoardFigureProps = { value: string; mode: BoardMode; delay: number; tile: boolean };

/** The figure as rolling digit strips; other characters fade in. */
function BoardFigure({ value, mode, delay, tile }: BoardFigureProps) {
  let digitOrder = 0;
  return (
    <span className={cx('board-n', `is-${mode}`, tile && 'is-tile')} aria-hidden="true">
      {Array.from(value).map((char, position) => {
        if (!/\d/.test(char)) {
          return (
            <span key={position} className="board-ch" style={{ animationDelay: `${delay + SYMBOL_DELAY}ms` }}>
              {char}
            </span>
          );
        }
        const digit = Number(char);
        return (
          <span key={position} className="board-dg">
            <span className="board-dg-s">{char}</span>
            <span className="board-dg-t" style={{ animationDelay: `${delay + digitOrder++ * DIGIT_STAGGER}ms` }}>
              {Array.from({ length: STRIP_ROWS }, (_, row) => (
                <span key={row}>{row === 0 ? '' : (digit + row) % 10}</span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}
