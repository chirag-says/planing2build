/**
 * The estimate sheet's arithmetic, kept free of React so it can be tested on its own.
 * Every number here is the reference component's.
 */
import { splitList } from '@/marketing/lib/text';
import { clamp01 } from '@/marketing/lib/ticker';

/** Pricing for one job type. Sizes are in the sheet's unit (sq ft). */
export type Rate = {
  /** Price per unit of size. */
  rate: number;
  /** Smallest and largest size the slider offers. */
  min: number;
  max: number;
  /** Weeks = base + pace × √size. */
  base: number;
  pace: number;
};

export type Finish = { label: string; factor: number };

/** The result, in the order the motion layer animates it. */
export type Estimate = {
  /** Where the low and high ticks sit along the tape, 0–1. */
  tapeLow: number;
  tapeHigh: number;
  /** Budget range in rupees. */
  low: number;
  high: number;
  weeks: number;
};

/** Used for a job type that has no line in the rates. */
export const FALLBACK_RATE: Rate = { rate: 200, min: 1000, max: 50000, base: 5, pace: 0.12 };

/** Lower-case, dash-separated: "Design-build" -> "design-build", "Standard" -> "standard". */
export const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');

/** `slug:rate:min:max:base:pace; …`. Missing or broken fields take the fallback's value. */
export function parseRates(source: string): Record<string, Rate> {
  const rates: Record<string, Rate> = {};
  for (const line of splitList(source)) {
    const fields = line.split(':').map((field) => field.trim());
    if (!fields[0]) continue;
    const read = (index: number, fallback: number) => {
      const value = parseFloat(fields[index] ?? '');
      return Number.isFinite(value) ? value : fallback;
    };
    const min = Math.max(1, read(2, FALLBACK_RATE.min));
    rates[slugify(fields[0])] = {
      rate: Math.max(0.01, read(1, FALLBACK_RATE.rate)),
      min,
      max: Math.max(min + 1, read(3, FALLBACK_RATE.max)),
      base: Math.max(0, read(4, FALLBACK_RATE.base)),
      pace: Math.max(0, read(5, FALLBACK_RATE.pace)),
    };
  }
  return rates;
}

/** `Name:factor; …`. The factor is whatever follows the last colon; a missing or non-positive one is 1. */
export function parseFinishes(source: string): Finish[] {
  return splitList(source)
    .map((item) => {
      const colon = item.lastIndexOf(':');
      const factor = parseFloat(colon < 0 ? '' : item.slice(colon + 1));
      return {
        label: (colon < 0 ? item : item.slice(0, colon)).trim(),
        factor: Number.isFinite(factor) && factor > 0 ? factor : 1,
      };
    })
    .filter((finish) => finish.label);
}

/**
 * Slider step: about 200 stops across the range, rounded up to 1, 2 or 5 times a power of ten
 * (5,000–200,000 sq ft steps by 1,000).
 */
export function sliderStep(min: number, max: number): number {
  const raw = Math.max(1, (max - min) / 200);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const leading = raw / magnitude;
  return (leading <= 1 ? 1 : leading <= 2 ? 2 : leading <= 5 ? 5 : 10) * magnitude;
}

/** Before the visitor moves the slider a job type starts a tenth of the way along its range. */
export const defaultSize = (rate: Rate) => rate.min + (rate.max - rate.min) * 0.1;

/** Rounds to the slider's grid (counted from `min`) and keeps the size in range. */
export function snapSize(size: number, rate: Rate): number {
  const step = sliderStep(rate.min, rate.max);
  return Math.min(rate.max, Math.max(rate.min, rate.min + Math.round((size - rate.min) / step) * step));
}

/** How far along its range the size is, 0–1: the slider track's filled part. */
export const sizeFraction = (size: number, rate: Rate) => clamp01((size - rate.min) / Math.max(1, rate.max - rate.min));

type EstimateInput = {
  rate: Rate;
  size: number;
  finish: number;
  /** The dearest finish factor (at least 1): the tape's full length is the largest job at that finish. */
  topFinish: number;
  /** Plus and minus, in percent; clamped to 0–45. */
  spread: number;
  /** Phone layout: the tape is shorter, so the ticks use less of it. */
  narrow: boolean;
};

export function estimate({ rate, size, finish, topFinish, spread, narrow }: EstimateInput): Estimate {
  const plusMinus = Math.min(45, Math.max(0, Number(spread) || 0)) / 100;
  const cost = rate.rate * size * finish;
  // The tape starts a quarter of the way out so even the smallest job shows a span, and the
  // ^0.4 curve keeps small jobs from bunching at the case while the largest ones reach the end.
  const reach = 0.26 + (narrow ? 0.36 : 0.5) * clamp01(cost / (rate.rate * rate.max * topFinish)) ** 0.4;
  return {
    tapeLow: Math.max(0.1, reach * (1 - plusMinus)),
    tapeHigh: Math.min(narrow ? 0.72 : 0.86, reach * (1 + plusMinus)),
    low: cost * (1 - plusMinus),
    high: cost * (1 + plusMinus),
    weeks: Math.max(1, Math.round(rate.base + rate.pace * Math.sqrt(size))),
  };
}

/** Whole number with thousands commas: 25000 -> "25,000". */
export const formatCount = (value: number) =>
  Math.round(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ',');

/**
 * Indian units: "₹1.29 Cr" from one crore, "₹58.3 L" from one lakh (whole lakhs from ₹20 L up),
 * "₹95,000" below that. Negative values read as ₹0.
 */
export function formatMoney(value: number): string {
  // No figure yet (the API has not answered): a placeholder, never a made-up number.
  if (!Number.isFinite(value)) return '…';
  const amount = Math.max(0, value);
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(amount >= 2e6 ? 0 : 1)} L`;
  return `₹${Math.round(amount).toLocaleString('en-IN')}`;
}

/** The bid page link with the three answers added, as the reference built it. */
export function bidLink(bidHref: string, type: string, size: number, finishLabel: string): string {
  const joiner = bidHref.includes('?') ? '&' : '?';
  return `${bidHref}${joiner}type=${encodeURIComponent(type)}&size=${size}&finish=${encodeURIComponent(slugify(finishLabel))}`;
}
