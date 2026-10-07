import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { Heading } from '@/marketing/components/ui/Heading';
import { projects } from '@/marketing/content/projects';
import type { BoardContent } from '@/marketing/content/sections/board';
import { site } from '@/marketing/content/site';
import type { Project } from '@/marketing/content/types';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { TYPE } from '@/marketing/lib/typography';
import { BoardShell } from './BoardShell';
import { BoardStatCell } from './BoardStatCell';
import './board.css';

const MAX_STATS = 6;
const MAX_TICKER_ITEMS = 8;
/** The ticker never loops faster than this many seconds. */
const MIN_TICKER_SECONDS = 12;

/** Recent handovers for the ticker; every named project when none is handed over yet. */
function tickerProjects(): Project[] {
  const named = projects.filter((project) => project.name);
  const handed = named.filter((project) => /handed/i.test(project.status));
  return (handed.length ? handed : named).slice(0, MAX_TICKER_ITEMS);
}

type TickerListProps = { items: Project[]; daysWord: string; duplicate?: boolean };

function TickerList({ items, daysWord, duplicate }: TickerListProps) {
  return (
    <ul className="board-mq-l" aria-hidden={duplicate || undefined}>
      {items.map((project) => (
        <li key={project.slug}>
          {project.status && <b>{project.status}</b>}
          <span className="board-mq-n">{project.name}</span>
          {project.daysOnSite > 0 && (
            <span>
              {project.daysOnSite} {daysWord}
            </span>
          )}
          {project.result && <span>{project.result}</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * "By the numbers": a site board hung from a crane cable that is lowered into place as the
 * section scrolls in, with figures that roll up once it lands, and a slow ticker of handovers.
 */
export function Board({ content }: { content: BoardContent }) {
  const { eyebrow, heading, subCopy, boardTitle, boardNote, showTicker, daysWord, tickerSpeed } = content;
  const stats = content.stats.filter((stat) => stat.value).slice(0, MAX_STATS);
  const yellowIndex = Math.round(content.yellowCell) - 1;
  // Desktop gives the yellow counter a wider column; phone and tablet use two equal columns (CSS).
  const columns = stats.map((_, index) => (index === yellowIndex ? '1.32fr' : '1fr')).join(' ');
  const ticker = tickerProjects();
  const cellsStyle: StyleWithVars = { '--board-cols': columns };
  const tickerStyle: StyleWithVars = {
    ...TYPE.mono,
    ...revealDelay(420, 14),
    '--dur': `${Math.max(MIN_TICKER_SECONDS, tickerSpeed)}s`,
  };

  return (
    <BoardShell style={{ background: 'var(--gd-bone)', color: 'var(--gd-ink)' }}>
      <div className="gd-wrap board-wrap">
        <header className="board-top">
          <div className="board-top-l">
            <Eyebrow text={eyebrow} />
            <Heading text={heading} size="clamp(44px,4.4vw,64px)" lineHeight={0.9} delay={80} />
          </div>
          {subCopy && (
            <p className="board-sub gd-rv" style={revealDelay(260)}>
              {subCopy}
            </p>
          )}
        </header>

        <div className="board-rig">
          <div className="board-sl" aria-hidden="true">
            <i className="board-cable" />
            <svg viewBox="0 0 100 100" preserveAspectRatio="none">
              <path d="M0 100L50 0L100 100" fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </svg>
            <i className="board-hook" />
          </div>
          <div className="board-board gd-dark">
            <div className="board-hz" aria-hidden="true" />
            <div className="board-bar" style={TYPE.mono}>
              <span className="board-bar-t">
                <i className="board-dot" aria-hidden="true" />
                {boardTitle.trim() || `${site.name} · Site board`}
              </span>
              {boardNote && <span className="board-bar-n">{boardNote}</span>}
              <span className="board-bolts" aria-hidden="true">
                <i />
                <i />
              </span>
            </div>
            <ul className="board-cells" style={cellsStyle}>
              {stats.map((stat, index) => (
                <BoardStatCell
                  key={index}
                  stat={stat}
                  index={index}
                  yellow={index === yellowIndex}
                  wide={stats.length % 2 === 1 && index === stats.length - 1}
                />
              ))}
            </ul>
          </div>
        </div>

        {showTicker && ticker.length > 0 && (
          // Focusable, so keyboard users can pause the moving list as pointer users do by hovering.
          <div className="board-mq gd-rv" style={tickerStyle} role="region" tabIndex={0} aria-label={content.tickerLabel || 'Recent handovers. Hover or focus to pause.'}>
            <div className="board-mq-v">
              {/* two identical lists; the track slides by exactly one list (-50%) per loop */}
              <div className="board-mq-t">
                <TickerList items={ticker} daysWord={daysWord} />
                <TickerList items={ticker} daysWord={daysWord} duplicate />
              </div>
            </div>
          </div>
        )}
      </div>
    </BoardShell>
  );
}
