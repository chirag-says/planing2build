/** Copy for the home page's "What you get" site board. The ticker lists the sample build plans. */

export type BoardStat = { value: string; label: string };

export type BoardContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  subCopy: string;
  /** Title in the board's top bar. Empty = "<site name> · Site board". */
  boardTitle: string;
  boardNote: string;
  /** Up to six. */
  stats: BoardStat[];
  /** 1-based position of the stat shown on the yellow split-flap counter; 0 = none. */
  yellowCell: number;
  showTicker: boolean;
  /** Unit after each project's days on site in the ticker. */
  daysWord: string;
  /** Seconds for one full loop of the ticker (at least 12). */
  tickerSpeed: number;
  /** Names the moving list for assistive technology; says how to pause it. */
  tickerLabel?: string;
};

export const board: BoardContent = {
  eyebrow: '01 · What you get',
  heading: 'Every decision,|*written down.*',
  subCopy:
    'A house is 16 stages and 67 material and system decisions. Your Build Plan gives each one a decide-by date, before the money is spent.',
  boardTitle: '',
  boardNote: 'Pilot city · Mumbai',
  stats: [
    { value: '67', label: 'decisions, each with a decide-by date' },
    { value: '16', label: 'construction stages tracked' },
    { value: '6', label: 'independent inspection gates' },
    { value: '₹0', label: 'paid by brands for a place in your plan' },
  ],
  yellowCell: 1,
  showTicker: true,
  daysWord: 'months',
  tickerSpeed: 60,
};
