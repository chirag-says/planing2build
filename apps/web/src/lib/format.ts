// Display formatting. Amounts arrive from the API as decimal strings (never floats on the wire).
import { LOCALE } from "@/lib/i18n";

const INR = new Intl.NumberFormat(`${LOCALE}-IN`, {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatInr(amount: string): string {
  return INR.format(Number(amount));
}

const DATE = new Intl.DateTimeFormat(`${LOCALE}-IN`, {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Kolkata",
});

export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}

const DATE_TIME = new Intl.DateTimeFormat(`${LOCALE}-IN`, {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

/** A deadline within days (a connection's response window), to the minute, in IST. */
export function formatDateTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}

export function formatBytes(size: number): string {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const RUPEES = new Intl.NumberFormat(`${LOCALE}-IN`, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Billing amounts to the paisa, without the symbol (messages carry "₹"). */
export function formatRupees(amount: string): string {
  return RUPEES.format(Number(amount));
}
