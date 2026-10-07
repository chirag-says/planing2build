/**
 * Parsers for the compact copy syntax the content uses.
 *
 * Headlines: `|` breaks a line and `*words*` marks the run that rides the yellow beam, e.g.
 * `The date and the budget,|*kept.*`. Trailing punctuation inside the run stays with the word.
 */
export type HeadlineWord = { text: string; tail: string; accent: boolean };

export function parseHeadline(source: string): HeadlineWord[][] {
  return source.split('|').map(parseHeadlineLine);
}

function parseHeadlineLine(line: string): HeadlineWord[] {
  // Mark every word of an accent run individually: "*one contract.*" -> "*one* *contract*."
  const marked = line.replace(/\*([^*]+)\*/g, (_, run: string) =>
    run
      .trim()
      .split(/\s+/)
      .map((word) => {
        const parts = word.match(/^(.*?)([.,!?;:’']*)$/);
        return parts?.[1] ? `*${parts[1]}*${parts[2]}` : word;
      })
      .join(' '),
  );
  return marked
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      const accent = word.match(/^\*(.+?)\*([.,!?;:’']*)$/);
      return accent
        ? { text: accent[1] ?? '', tail: accent[2] ?? '', accent: true }
        : { text: word.replace(/\*/g, ''), tail: '', accent: false };
    });
}

/** The headline as one plain sentence, for `aria-label`. */
export function plainHeadline(source: string): string {
  return source.replace(/\*/g, '').replace(/\s*\|\s*/g, ' ').replace(/\s+/g, ' ').trim();
}

/** Splits `a; b; c` into trimmed, non-empty items. */
export function splitList(source: string, separator: string | RegExp = ';'): string[] {
  return source
    .split(separator)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** Zero-pads to two digits: 3 -> "03". */
export const pad2 = (value: number | string) => String(value).padStart(2, '0');

/** Digits and a leading plus only, for `tel:` links. */
export const telHref = (phone: string) => `tel:${phone.replace(/[^\d+]/g, '')}`;
