/** A figure split around its number, so the number can be redrawn at any value: "$48.6M". */
export type CountTarget = { prefix: string; value: number; decimals: number; grouped: boolean; suffix: string };

/** Splits "310,000 sq ft" into prefix, number and suffix; null when the text holds no number. */
export function parseCount(text: string): CountTarget | null {
  const match = text.match(/^(.*?)(\d[\d,]*(?:\.\d+)?)(.*)$/);
  if (!match) return null;
  const digits = match[2] ?? '';
  return {
    prefix: match[1] ?? '',
    value: parseFloat(digits.replace(/,/g, '')),
    decimals: (digits.split('.')[1] ?? '').length,
    grouped: digits.includes(','),
    suffix: match[3] ?? '',
  };
}

/** The figure redrawn with `value`, keeping its decimals and thousands separators. */
export function formatCount(target: CountTarget, value: number): string {
  const number = target.grouped
    ? value.toLocaleString('en-US', { minimumFractionDigits: target.decimals, maximumFractionDigits: target.decimals })
    : value.toFixed(target.decimals);
  return target.prefix + number + target.suffix;
}
