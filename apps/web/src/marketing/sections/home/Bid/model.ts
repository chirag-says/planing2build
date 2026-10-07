import { parseHeadline } from '@/marketing/lib/text';

/** One run of a headline line: plain words, or a joined accent run that rides the beam. */
export type HeadlineRun = { text: string; accent: boolean };

/** Headline lines with each accent run joined into one piece, so one beam spans the run. */
export function headlineRuns(source: string): HeadlineRun[][] {
  return parseHeadline(source).map((line) => {
    const runs: HeadlineRun[] = [];
    for (const word of line) {
      const text = word.text + word.tail;
      const last = runs[runs.length - 1];
      if (word.accent && last?.accent) last.text += ` ${text}`;
      else runs.push({ text, accent: word.accent });
    }
    return runs;
  });
}

/**
 * Width of the longest headline line in characters, the unit the headline size is fitted to.
 * An accent run counts 0.7 of a character extra for the beam's side padding.
 */
export function headlineMeasure(lines: HeadlineRun[][]): number {
  return Math.max(1, ...lines.map((runs) => runs.reduce((sum, run) => sum + run.text.length + 1 + (run.accent ? 0.7 : 0), -1)));
}

/** `In 3–6 months` -> `in-3-6-months`. */
export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[–—]/g, '-')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** The bid link with the two answers added: `/request-a-bid?type=roofing&start=next-year`. */
export function bidRequestHref(bidHref: string, type: string | undefined, start: string | undefined): string {
  const params: string[] = [];
  if (type) params.push(`type=${encodeURIComponent(type)}`);
  if (start !== undefined) params.push(`start=${encodeURIComponent(slugify(start))}`);
  if (!params.length) return bidHref;
  return `${bidHref}${bidHref.includes('?') ? '&' : '?'}${params.join('&')}`;
}

/**
 * Card drop easing: overshoots past 1 (to about 1.07) before settling, so the card lands with
 * a small bounce on its slings.
 */
export function dropEase(progress: number): number {
  const t = Math.min(1, Math.max(0, progress)) - 1;
  return 1 + 2.4 * t * t * t + 1.4 * t * t;
}

