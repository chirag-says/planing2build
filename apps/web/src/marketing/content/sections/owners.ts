/** Copy for the home page's add-on services ("07 · After handover"). The services come from `addons`. */
export type OwnersContent = {
  eyebrow: string;
  /** `|` breaks a line, `*words*` ride the yellow beam. */
  heading: string;
  /** Service-sheet checklist, separated by `;` (first six are used). */
  checks: string;
  /** Sheet title, followed by the item's project ("Add-on service · 2,650 sq ft · G+1 · Raipur"). */
  cardLabel: string;
  /** Sheet number label ("Service 01 / 04"). */
  sheetLabel: string;
  resultLabel: string;
  /** Pressed onto the sheet on hover; empty = no stamp. */
  stampText: string;
  /** The five-square rating above each item. */
  showRating: boolean;
  prevLabel: string;
  nextLabel: string;
};

export const owners: OwnersContent = {
  eyebrow: '07 · After handover',
  heading: 'Keys in hand.|*We stay on call.*',
  checks: 'Verified service provider; Fixed scope and quote up front; Work logged to your build record; Guarantee in writing',
  cardLabel: 'Add-on service',
  sheetLabel: 'Service',
  resultLabel: 'Provided by',
  stampText: 'On request',
  prevLabel: 'Previous service',
  nextLabel: 'Next service',
  showRating: false,
};
